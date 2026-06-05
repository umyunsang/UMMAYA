# SPDX-License-Identifier: Apache-2.0
"""PDF adapter tests for AcroForm-only mutation and typed blocked cases."""

from __future__ import annotations

import base64
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import pytest
from pypdf.generic import BooleanObject

from ummaya.tools.documents.adapter_registry import build_default_document_adapter_registry
from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.formats.pdf import (
    PdfDocumentAdapter,
    PdfDocumentKind,
    PypdfAcroFormEngine,
    classify_pdf_document,
)
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    OperationType,
    StyleDescriptor,
    ToolResultStatus,
)
from ummaya.tools.documents.patch import apply_document_patch, copy_for_edit
from ummaya.tools.documents.pdfa_conformance import (
    PDFA_EXPORTER_ID,
    PDFA_FLAVOUR,
    PDFA_VALIDATOR_ID,
    PdfaConformanceReport,
    PdfaExportResult,
)
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.render import render_document_evidence
from ummaya.tools.documents.tool_defs import (
    DocumentCopyForEditRequest,
    DocumentInspectRequest,
    DocumentLocator,
    DocumentSaveRequest,
)


def test_default_registry_promotes_pdf_acroform_adapter() -> None:
    registry = build_default_document_adapter_registry()

    adapter = registry.require_promoted(DocumentFormat.pdf)

    assert isinstance(adapter, PdfDocumentAdapter)
    assert adapter.adapter_id == "pypdf-acroform-adapter"
    assert adapter.engine_id == "pypdf-acroform"


def test_pdf_acroform_fill_rereads_field_and_renders_visible_png(
    tmp_path: Path,
) -> None:
    source_path = _write_acroform_pdf(tmp_path / "application.pdf")
    store, working = _working_pdf_artifact(tmp_path, source_path, source_id="pdf-source")
    engine = PypdfAcroFormEngine()
    registry = DocumentEngineRegistry()
    registry.register(engine)
    before_png = engine.render(
        Path(working.source_path),
        artifact_id=working.artifact_id,
        output_dir=tmp_path,
    )[0]
    patch = _acroform_patch(working.artifact_id, field_name="applicant_name", value="Hong Gil Dong")

    result = apply_document_patch(
        store,
        working,
        patch,
        engine_registry=registry,
        artifact_id="pdf-filled",
        destination_name="filled.pdf",
    )

    assert result.status is ToolResultStatus.ok
    assert result.derivative_artifact is not None
    extraction = engine.inspect(
        Path(result.derivative_artifact.source_path),
        artifact_id="pdf-filled",
    )
    applicant = next(
        field for field in extraction.fields if field.path == "/acroform/fields/applicant_name"
    )
    assert applicant.current_value == "Hong Gil Dong"
    render_result = render_document_evidence(
        store,
        result.derivative_artifact,
        engine_registry=registry,
        correlation_id="corr-pdf-render",
        artifact_id_prefix="render-pdf",
    )
    assert render_result.status is ToolResultStatus.ok
    assert render_result.records[0].render_mime_type == "image/png"
    assert Path(render_result.records[0].render_path).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    after_png = Path(render_result.records[0].render_path).read_bytes()
    assert after_png != before_png


def test_pdf_acroform_fill_sets_need_appearances_for_korean_field_rendering(
    tmp_path: Path,
) -> None:
    pypdf = pytest.importorskip("pypdf")
    source_path = _write_acroform_pdf(tmp_path / "korean-application.pdf")
    store, working = _working_pdf_artifact(tmp_path, source_path, source_id="pdf-korean")
    registry = DocumentEngineRegistry()
    registry.register(PypdfAcroFormEngine())

    result = apply_document_patch(
        store,
        working,
        _acroform_patch(working.artifact_id, field_name="applicant_name", value="홍길동"),
        engine_registry=registry,
        artifact_id="pdf-korean-filled",
        destination_name="filled-korean.pdf",
    )

    assert result.status is ToolResultStatus.ok
    assert result.derivative_artifact is not None
    expected_path = tmp_path / "expected-auto-regenerate.pdf"
    reader = pypdf.PdfReader(str(source_path), strict=False)
    writer = pypdf.PdfWriter()
    writer.append(reader)
    writer.update_page_form_field_values(
        None,
        {"applicant_name": "홍길동"},
        auto_regenerate=True,
    )
    with expected_path.open("wb") as handle:
        writer.write(handle)

    engine = PypdfAcroFormEngine()
    actual_png = engine.render(
        Path(result.derivative_artifact.source_path),
        artifact_id="actual-korean",
        output_dir=tmp_path,
    )[0]
    expected_png = engine.render(
        expected_path,
        artifact_id="expected-korean",
        output_dir=tmp_path,
    )[0]
    assert actual_png == expected_png


def test_pdf_acroform_korean_fill_changes_visible_field_region(
    tmp_path: Path,
) -> None:
    pytest.importorskip("PIL")
    from PIL import Image, ImageChops

    source_path = _write_acroform_pdf(tmp_path / "korean-visible-application.pdf")
    store, working = _working_pdf_artifact(tmp_path, source_path, source_id="pdf-korean-visible")
    engine = PypdfAcroFormEngine()
    registry = DocumentEngineRegistry()
    registry.register(engine)
    before_png = engine.render(
        Path(working.source_path),
        artifact_id="pdf-korean-visible-before",
        output_dir=tmp_path,
    )[0]

    result = apply_document_patch(
        store,
        working,
        _acroform_patch(working.artifact_id, field_name="applicant_name", value="홍길동"),
        engine_registry=registry,
        artifact_id="pdf-korean-visible-filled",
        destination_name="filled-korean-visible.pdf",
    )

    assert result.status is ToolResultStatus.ok
    assert result.derivative_artifact is not None
    after_png = engine.render(
        Path(result.derivative_artifact.source_path),
        artifact_id="pdf-korean-visible-after",
        output_dir=tmp_path,
    )[0]
    before_image = Image.open(BytesIO(before_png)).convert("RGB")
    after_image = Image.open(BytesIO(after_png)).convert("RGB")
    diff = ImageChops.difference(before_image, after_image)
    changed_bbox = diff.getbbox()
    assert changed_bbox is not None
    expected_field_rect = _pdf_rect_to_rendered_image_rect(
        before_image.size,
        pdf_rect=_APPLICANT_FIELD_RECT,
    )
    assert _boxes_intersect(changed_bbox, expected_field_rect)
    visible_field_change = diff.crop(expected_field_rect).convert("L")
    changed_pixels = sum(visible_field_change.histogram()[1:])
    assert changed_pixels > 100


def test_pdf_acroform_korean_font_fixture_embeds_appearance_without_viewer_regeneration(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source_path = _write_korean_font_acroform_pdf(tmp_path / "korean-font-application.pdf")
    store, working = _working_pdf_artifact(
        tmp_path,
        source_path,
        source_id="pdf-korean-font",
    )
    registry = DocumentEngineRegistry()
    registry.register(PypdfAcroFormEngine())
    caplog.set_level("WARNING")

    result = apply_document_patch(
        store,
        working,
        _acroform_patch(working.artifact_id, field_name="applicant_name", value="홍길동"),
        engine_registry=registry,
        artifact_id="pdf-korean-font-filled",
        destination_name="filled-korean-font.pdf",
    )

    assert result.status is ToolResultStatus.ok
    assert result.derivative_artifact is not None
    reader = pytest.importorskip("pypdf").PdfReader(
        str(result.derivative_artifact.source_path),
        strict=False,
    )
    acroform = reader.trailer["/Root"]["/AcroForm"].get_object()
    assert acroform.get("/NeedAppearances") in (None, BooleanObject(False))
    field = acroform["/Fields"][0].get_object()
    assert field["/V"] == "홍길동"
    assert "/AP" in field
    assert not any(
        "characters not supported by font encoding" in record.message for record in caplog.records
    )


def test_pdf_acroform_korean_fill_suppresses_misleading_font_encoding_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source_path = _write_acroform_pdf(tmp_path / "korean-warning.pdf")
    store, working = _working_pdf_artifact(tmp_path, source_path, source_id="pdf-korean-warning")
    registry = DocumentEngineRegistry()
    registry.register(PypdfAcroFormEngine())
    caplog.set_level("WARNING")

    result = apply_document_patch(
        store,
        working,
        _acroform_patch(working.artifact_id, field_name="applicant_name", value="홍길동"),
        engine_registry=registry,
        artifact_id="pdf-korean-warning-filled",
        destination_name="filled-korean-warning.pdf",
    )

    assert result.status is ToolResultStatus.ok
    assert not any(
        "characters not supported by font encoding" in record.message for record in caplog.records
    )


def test_document_save_exports_pdfa_through_postwrite_conformance_bridge(
    tmp_path: Path,
) -> None:
    source_path = _write_acroform_pdf(tmp_path / "application.pdf")
    destination = tmp_path / "exports" / "application.pdfa"
    bridge = FakePdfaConformanceBridge()
    runtime = DocumentToolRuntime(
        session_id="pdfa-export-save",
        artifact_root=tmp_path / "store-pdfa-export",
        pdfa_conformance_bridge=bridge,
        enable_default_pdfa_conformance_bridge=False,
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="pdfa-export-inspect",
            document=DocumentLocator(path=str(source_path), expected_format=DocumentFormat.pdf),
        )
    )
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="pdfa-export-copy",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[-1]),
        )
    )
    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="pdfa-export-save",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert inspect_result.status is ToolResultStatus.ok
    assert copy_result.status is ToolResultStatus.ok
    assert save_result.status is ToolResultStatus.ok
    assert bridge.called
    assert destination.is_file()
    assert save_result.saved_exports
    assert save_result.saved_exports[0].local_path == destination.resolve()
    assert destination.read_bytes().startswith(b"%PDF-")
    assert "PDF/A post-write conformance passed" in save_result.text_summary


def test_document_save_blocks_pdfa_export_without_postwrite_conformance_bridge(
    tmp_path: Path,
) -> None:
    source_path = _write_acroform_pdf(tmp_path / "application.pdf")
    destination = tmp_path / "exports" / "application.pdfa"
    runtime = DocumentToolRuntime(
        session_id="pdfa-export-blocked",
        artifact_root=tmp_path / "store-pdfa-blocked",
        enable_default_pdfa_conformance_bridge=False,
    )
    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="pdfa-blocked-inspect",
            document=DocumentLocator(path=str(source_path), expected_format=DocumentFormat.pdf),
        )
    )
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="pdfa-blocked-copy",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[-1]),
        )
    )

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="pdfa-blocked-save",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason is BlockedReason.validation_failed
    assert not destination.exists()


@pytest.mark.parametrize(
    ("fixture_name", "expected_kind", "expected_reason"),
    [
        ("static", PdfDocumentKind.static, BlockedReason.static_pdf),
        ("scanned", PdfDocumentKind.scanned, BlockedReason.scanned_pdf),
        ("xfa", PdfDocumentKind.xfa, BlockedReason.xfa_detected),
        ("signed", PdfDocumentKind.signed, BlockedReason.signature_detected),
        ("encrypted", PdfDocumentKind.encrypted, BlockedReason.encrypted),
    ],
)
def test_pdf_mutation_blocks_non_acroform_cases_with_typed_reasons(
    tmp_path: Path,
    fixture_name: str,
    expected_kind: PdfDocumentKind,
    expected_reason: BlockedReason,
) -> None:
    fixture_writer = _PDF_FIXTURE_WRITERS[fixture_name]
    source_path = fixture_writer(tmp_path / f"{expected_kind.value}.pdf")
    profile = classify_pdf_document(source_path)
    store, working = _working_pdf_artifact(
        tmp_path,
        source_path,
        source_id=f"source-{expected_kind.value}",
    )
    registry = DocumentEngineRegistry()
    registry.register(PypdfAcroFormEngine())

    result = apply_document_patch(
        store,
        working,
        _acroform_patch(working.artifact_id, field_name="applicant_name", value="Hong Gil Dong"),
        engine_registry=registry,
        artifact_id=f"blocked-{expected_kind.value}",
        destination_name="blocked.pdf",
    )

    assert profile.kind is expected_kind
    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is expected_reason
    assert expected_kind.value in result.text_summary
    assert result.derivative_artifact is None


def test_static_pdf_inspection_declares_template_overlay_policy(
    tmp_path: Path,
) -> None:
    source_path = _write_static_pdf(tmp_path / "static-application.pdf")

    extraction = PypdfAcroFormEngine().inspect(source_path, artifact_id="static-application")

    assert extraction.metadata["pdf_kind"] == "static"
    assert extraction.metadata["mutation_policy"] == "acroform_only"
    assert extraction.metadata["template_overlay_capability"] == "requires_template_baseline"
    assert extraction.metadata["template_overlay_available"] is False
    assert extraction.metadata["template_overlay_required_evidence"] == (
        "baseline_bounding_boxes_and_pypdfium2_render_comparison"
    )
    assert extraction.metadata["render_oracle"] == "pypdfium2"
    assert any("template overlay" in warning for warning in extraction.warnings)


def test_pdf_acroform_blocks_generic_style_operations(
    tmp_path: Path,
) -> None:
    source_path = _write_acroform_pdf(tmp_path / "style-blocked-application.pdf")
    store, working = _working_pdf_artifact(
        tmp_path,
        source_path,
        source_id="pdf-style-blocked",
    )
    registry = DocumentEngineRegistry()
    registry.register(PypdfAcroFormEngine())
    patch = DocumentPatch(
        patch_id="pdf-style-blocked",
        target_artifact_id=working.artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="style-pdf-field",
                operation_type=OperationType.set_run_style,
                target_path="/acroform/fields/applicant_name",
                style=StyleDescriptor(
                    style_id="pdf-run-style",
                    target_path="/acroform/fields/applicant_name",
                    font_family="Malgun Gothic",
                    bold=True,
                ),
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.pdf,
        destination_policy="working_copy",
    )

    result = apply_document_patch(
        store,
        working,
        patch,
        engine_registry=registry,
        artifact_id="pdf-style-blocked-filled",
        destination_name="style-blocked.pdf",
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.validation_failed
    assert "AcroForm set_field_value operations only" in result.text_summary
    assert "set_run_style" in result.text_summary
    assert result.derivative_artifact is None


def _working_pdf_artifact(
    tmp_path: Path,
    source_path: Path,
    *,
    source_id: str,
):
    store = DocumentArtifactStore(
        root=tmp_path / f"store-{source_id}",
        session_id=f"session-{source_id}",
    )
    source = store.store_source(
        source_path,
        artifact_id=source_id,
        document_format=DocumentFormat.pdf,
        mime_type="application/pdf",
    )
    working = copy_for_edit(
        store,
        source,
        artifact_id=f"working-{source_id}",
        destination_name=source_path.name,
    )
    return store, working


class FakePdfaConformanceBridge:
    """Test double that proves the save path invoked the PDF/A bridge."""

    bridge_id = "fake-pdfa-conformance-bridge"

    def __init__(self) -> None:
        self.called = False

    def export_pdfa(self, payload: bytes) -> PdfaExportResult:
        self.called = True
        return PdfaExportResult(
            payload=payload,
            report=PdfaConformanceReport(
                exporter_id=PDFA_EXPORTER_ID,
                validator_id=PDFA_VALIDATOR_ID,
                pdfa_flavour=PDFA_FLAVOUR,
                sha256="0" * 64,
                byte_size=len(payload),
                summary="PASS fake-output.pdf 2b",
            ),
        )


def _acroform_patch(target_artifact_id: str, *, field_name: str, value: str) -> DocumentPatch:
    return DocumentPatch(
        patch_id=f"patch-{field_name}",
        target_artifact_id=target_artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id=f"set-{field_name}",
                operation_type=OperationType.set_field_value,
                target_path=f"/acroform/fields/{field_name}",
                value=value,
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.pdf,
        destination_policy="working_copy",
    )


def _write_acroform_pdf(path: Path) -> Path:
    reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    from reportlab.lib.pagesizes import letter

    canvas = reportlab_canvas.Canvas(str(path), pagesize=letter)
    canvas.drawString(72, 742, "Applicant name")
    canvas.acroForm.textfield(
        name="applicant_name",
        tooltip="Applicant name",
        x=180,
        y=728,
        width=220,
        height=20,
        borderStyle="inset",
        forceBorder=True,
    )
    canvas.save()
    return path


def _write_korean_font_acroform_pdf(path: Path) -> Path:
    reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = _local_korean_font_path()
    if font_path is None:
        pytest.skip("local Korean TrueType font fixture is not available")
    font_name = f"UMMAYAKoreanFont{abs(hash(font_path))}"
    pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    canvas = reportlab_canvas.Canvas(str(path), pagesize=letter)
    canvas.setFont(font_name, 12)
    canvas.drawString(72, 742, "신청인 성명")
    canvas.acroForm.textfield(
        name="applicant_name",
        tooltip="Applicant name",
        x=180,
        y=728,
        width=220,
        height=20,
        borderStyle="inset",
        forceBorder=True,
    )
    canvas.save()
    return path


def _local_korean_font_path() -> Path | None:
    candidates = (
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
        Path("/Library/Fonts/NanumGothic.ttf"),
    )
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _pdf_rect_to_rendered_image_rect(
    image_size: tuple[int, int],
    *,
    pdf_rect: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    image_width, image_height = image_size
    x, y, width, height = pdf_rect
    scale_x = image_width / _LETTER_PAGE_WIDTH_PT
    scale_y = image_height / _LETTER_PAGE_HEIGHT_PT
    left = max(int(x * scale_x) - 2, 0)
    top = max(int((_LETTER_PAGE_HEIGHT_PT - y - height) * scale_y) - 2, 0)
    right = min(int((x + width) * scale_x) + 2, image_width)
    bottom = min(int((_LETTER_PAGE_HEIGHT_PT - y) * scale_y) + 2, image_height)
    return left, top, right, bottom


def _boxes_intersect(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    first_left, first_top, first_right, first_bottom = first
    second_left, second_top, second_right, second_bottom = second
    return (
        first_left < second_right
        and first_right > second_left
        and first_top < second_bottom
        and first_bottom > second_top
    )


def _write_static_pdf(path: Path) -> Path:
    reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    from reportlab.lib.pagesizes import letter

    canvas = reportlab_canvas.Canvas(str(path), pagesize=letter)
    canvas.drawString(72, 742, "Static public form text")
    canvas.save()
    return path


def _write_scanned_pdf(path: Path) -> Path:
    reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    from reportlab.lib.pagesizes import letter

    image_path = path.with_suffix(".png")
    image_path.write_bytes(base64.b64decode(_ONE_PIXEL_PNG_BASE64))
    canvas = reportlab_canvas.Canvas(str(path), pagesize=letter)
    canvas.drawImage(str(image_path), 72, 700, width=120, height=80, mask="auto")
    canvas.save()
    return path


def _write_xfa_pdf(path: Path) -> Path:
    _write_acroform_pdf(path)
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import NameObject, TextStringObject

    reader = pypdf.PdfReader(str(path), strict=False)
    writer = pypdf.PdfWriter()
    writer.append(reader)
    acroform = writer._root_object["/AcroForm"]
    acroform[NameObject("/XFA")] = TextStringObject("<xdp:xdp/>")
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _write_signed_pdf(path: Path) -> Path:
    _write_acroform_pdf(path)
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import NameObject, TextStringObject

    reader = pypdf.PdfReader(str(path), strict=False)
    writer = pypdf.PdfWriter()
    writer.append(reader)
    field = writer._root_object["/AcroForm"]["/Fields"][0].get_object()
    field[NameObject("/FT")] = NameObject("/Sig")
    field[NameObject("/T")] = TextStringObject("signature")
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _write_encrypted_pdf(path: Path) -> Path:
    _write_static_pdf(path)
    pypdf = pytest.importorskip("pypdf")

    reader = pypdf.PdfReader(str(path), strict=False)
    writer = pypdf.PdfWriter()
    writer.append(reader)
    writer.encrypt("secret")
    with path.open("wb") as handle:
        writer.write(handle)
    return path


_ONE_PIXEL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)

_LETTER_PAGE_WIDTH_PT = 612
_LETTER_PAGE_HEIGHT_PT = 792
_APPLICANT_FIELD_RECT = (180, 728, 220, 20)

_PDF_FIXTURE_WRITERS: dict[str, Callable[[Path], Path]] = {
    "static": _write_static_pdf,
    "scanned": _write_scanned_pdf,
    "xfa": _write_xfa_pdf,
    "signed": _write_signed_pdf,
    "encrypted": _write_encrypted_pdf,
}
