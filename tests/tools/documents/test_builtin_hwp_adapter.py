# SPDX-License-Identifier: Apache-2.0
"""Legacy HWP adapter boundary tests."""

from __future__ import annotations

import hashlib
import io
import os
import stat
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from ummaya.tools.documents.adapter_registry import (
    UnsupportedDocumentAdapterError,
    build_default_document_adapter_registry,
    build_document_adapter_registry_from_engine_registry,
)
from ummaya.tools.documents.conversion import (
    DocumentConversionRegistry,
    LocalCliDocumentConversionEngine,
)
from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
    build_default_document_engine_registry,
)
from ummaya.tools.documents.formats.hwp import HwpDocumentAdapter, UnhwpReadOnlyInspectionEngine
from ummaya.tools.documents.formats.hwpx import HwpXPackageTextEngine
from ummaya.tools.documents.intake import inspect_document_intake
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentArtifact,
    DocumentExtraction,
    DocumentFormat,
    FormField,
    KnownDocumentFormat,
    ParagraphBlock,
    ToolResultStatus,
)
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import (
    DocumentCopyForEditRequest,
    DocumentFieldPatch,
    DocumentInspectRequest,
    DocumentLocator,
    DocumentPrimitiveRequest,
)


def test_hwp_static_registry_blocks_while_runtime_registry_promotes_read() -> None:
    registry = build_default_document_adapter_registry()
    engine_wrapped_registry = build_document_adapter_registry_from_engine_registry(
        build_default_document_engine_registry()
    )

    adapter = registry.require_known(KnownDocumentFormat.hwp)

    assert isinstance(adapter, HwpDocumentAdapter)
    assert adapter.known_formats == (KnownDocumentFormat.hwp,)
    assert adapter.promoted_formats == ()
    with pytest.raises(UnsupportedDocumentAdapterError):
        registry.require_promoted(DocumentFormat.hwp)

    promoted = engine_wrapped_registry.require_promoted(DocumentFormat.hwp)
    assert promoted.engine_id == "unhwp-read-only"


def test_default_runtime_inspects_public_ax_hwp_with_unhwp_read_engine(
    tmp_path: Path,
) -> None:
    source = _public_ax_hwp_fixtures()[0]
    runtime = DocumentToolRuntime(session_id="hwp-unhwp-read", artifact_root=tmp_path / "store")

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwp-unhwp-read",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    assert result.extraction.paragraphs
    assert result.extraction.metadata["engine_id"] == "unhwp-read-only"
    extracted_text = "\n".join(paragraph.text for paragraph in result.extraction.paragraphs)
    assert "제출 서류 목록" in extracted_text


def test_unhwp_read_engine_promotes_markdown_tables_and_field_candidates(
    tmp_path: Path,
) -> None:
    source = _public_ax_hwp_fixture_named("아이디어 기획서 양식")
    runtime = DocumentToolRuntime(session_id="hwp-unhwp-table-ir", artifact_root=tmp_path)

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwp-unhwp-table-ir",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    assert result.extraction.tables
    table_text = "\n".join(cell.text for table in result.extraction.tables for cell in table.cells)
    assert "팀명" in table_text
    assert "UMMAYA" in table_text
    field_by_label = {field.label: field for field in result.extraction.fields}
    assert field_by_label["팀명"].current_value == "UMMAYA"
    assert field_by_label["팀명"].path.startswith("/hwp/unhwp/table[")
    assert field_by_label["아이디어명"].current_value == (
        "공공데이터와 AX 기술을 활용한 UMMAYA 국가 인프라 에이전트"
    )
    assert result.extraction.metadata["table_count"] >= 1
    assert result.extraction.metadata["field_candidate_count"] >= 2


def test_default_runtime_hwp_fill_still_blocks_without_conversion_engine(
    tmp_path: Path,
) -> None:
    source = _public_ax_hwp_fixtures()[0]
    runtime = DocumentToolRuntime(
        session_id="hwp-default-fill-blocked",
        artifact_root=tmp_path,
        conversion_registry=DocumentConversionRegistry(),
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="hwp-default-fill-blocked",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
            operation="fill",
            instruction="문서 내용을 파악하고 알아서 작성해.",
        )
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.unsupported_operation
    assert "HWP to HWPX conversion" in result.text_summary
    assert not any(ref.startswith(("working-", "derivative-")) for ref in result.artifact_refs)


def test_unhwp_read_engine_blocks_corrupt_hwp_with_parse_error(tmp_path: Path) -> None:
    source = _write_minimal_hwp(tmp_path / "corrupt.hwp")
    engine = UnhwpReadOnlyInspectionEngine()

    with pytest.raises(ValueError, match="unhwp could not parse HWP"):
        engine.inspect(source, artifact_id="corrupt-hwp")


def test_copied_hwp_public_ax_fixtures_classify_but_document_fill_is_blocked(
    tmp_path: Path,
) -> None:
    sources = _public_ax_hwp_fixtures()

    for index, source in enumerate(sources, start=1):
        intake_result = inspect_document_intake(source, expected_format=DocumentFormat.hwp)

        assert intake_result.status is ToolResultStatus.ok
        assert intake_result.detected_format is DocumentFormat.hwp
        assert intake_result.known_format is KnownDocumentFormat.hwp

        runtime = DocumentToolRuntime(
            session_id=f"public-ax-hwp-blocked-{index}",
            artifact_root=tmp_path / f"store-{index}",
            conversion_registry=DocumentConversionRegistry(),
        )
        result = runtime.document(
            DocumentPrimitiveRequest(
                correlation_id=f"public-ax-hwp-blocked-{index}",
                document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
                operation="fill",
                instruction="문서 내용을 파악하고 알아서 작성해.",
            )
        )

        assert result.status is ToolResultStatus.blocked
        assert result.blocked_reason is BlockedReason.unsupported_operation
        assert "HWP binary direct writing is blocked" in result.text_summary
        assert "Use a HWPX or DOCX editable template" in result.text_summary
        assert not any(ref.startswith(("working-", "derivative-")) for ref in result.artifact_refs)


def test_hwp_copy_for_edit_without_conversion_engine_is_blocked(tmp_path: Path) -> None:
    source = _write_minimal_hwp(tmp_path / "legacy-form.hwp")
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(_FakeHwpReadEngine())
    runtime = DocumentToolRuntime(
        session_id="hwp-copy-no-conversion",
        artifact_root=tmp_path / "store",
        engine_registry=engine_registry,
        conversion_registry=DocumentConversionRegistry(),
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-hwp-no-conversion-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok

    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="corr-hwp-no-conversion-copy",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )

    assert copy_result.status is ToolResultStatus.blocked
    assert copy_result.blocked_reason is BlockedReason.unsupported_operation
    assert "HWP to HWPX conversion" in copy_result.text_summary
    assert not any(ref.startswith("working-") for ref in copy_result.artifact_refs)


def test_hwp_copy_for_edit_uses_promoted_conversion_to_hwpx_derivative(
    tmp_path: Path,
) -> None:
    source = _write_minimal_hwp(tmp_path / "legacy-form.hwp")
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(_FakeHwpReadEngine())
    engine_registry.register(_FakeHwpXReadEngine())
    conversion = _FakeHwpToHwpXConversionEngine()
    conversion_registry = DocumentConversionRegistry()
    conversion_registry.register(conversion)
    runtime = DocumentToolRuntime(
        session_id="hwp-copy-with-conversion",
        artifact_root=tmp_path / "store",
        engine_registry=engine_registry,
        conversion_registry=conversion_registry,
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-hwp-conversion-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok
    source_artifact_id = inspect_result.artifact_refs[0]

    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="corr-hwp-conversion-copy",
            document=DocumentLocator(artifact_id=source_artifact_id),
        )
    )

    assert copy_result.status is ToolResultStatus.ok
    assert copy_result.artifact_refs == [source_artifact_id, "working-corr-hwp-conversion-copy"]
    assert "Converted HWP to editable HWPX derivative" in copy_result.text_summary
    assert conversion.source_artifact_id == source_artifact_id
    derivative = runtime.store.load_artifact(copy_result.artifact_refs[-1])
    assert derivative is not None
    assert derivative.format is DocumentFormat.hwpx
    assert derivative.mime_type == "application/owpml"
    assert derivative.parent_artifact_id == source_artifact_id
    assert Path(derivative.source_path).suffix == ".hwpx"
    assert Path(derivative.source_path).read_bytes() == conversion.payload
    assert source.read_bytes() == _MINIMAL_HWP_BYTES


def test_hwp_copy_for_edit_uses_local_cli_bridge_and_rereads_hwpx_derivative(
    tmp_path: Path,
) -> None:
    source = _write_minimal_hwp(tmp_path / "legacy-form.hwp")
    payload = _minimal_hwpx_package("홍길동")
    executable = _write_local_cli_converter(tmp_path / "hwp-to-hwpx.py", payload)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(_FakeHwpReadEngine())
    engine_registry.register(HwpXPackageTextEngine())
    conversion_registry = DocumentConversionRegistry()
    conversion_registry.register(
        LocalCliDocumentConversionEngine(
            source_format=DocumentFormat.hwp,
            output_format=DocumentFormat.hwpx,
            engine_id="local-hwpforge-dry-run",
            executable=executable,
            args=("{source}", "{output}"),
        )
    )
    runtime = DocumentToolRuntime(
        session_id="hwp-copy-local-cli-bridge",
        artifact_root=tmp_path / "store",
        engine_registry=engine_registry,
        conversion_registry=conversion_registry,
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-hwp-local-cli-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="corr-hwp-local-cli-copy",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )

    assert copy_result.status is ToolResultStatus.ok
    assert "local-hwpforge-dry-run" in copy_result.text_summary
    derivative_id = copy_result.artifact_refs[-1]
    derivative = runtime.store.load_artifact(derivative_id)
    assert derivative is not None
    assert derivative.format is DocumentFormat.hwpx
    reread = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-hwp-local-cli-reread",
            document=DocumentLocator(artifact_id=derivative_id),
        )
    )
    assert reread.status is ToolResultStatus.ok
    assert reread.extraction is not None
    assert [paragraph.text for paragraph in reread.extraction.paragraphs] == ["홍길동"]
    assert source.read_bytes() == _MINIMAL_HWP_BYTES


def test_hwp_document_primitive_blocks_direct_hwp_destination_after_conversion(
    tmp_path: Path,
) -> None:
    source = _write_minimal_hwp(tmp_path / "legacy-weekly-form.hwp")
    source_sha256_before = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "direct-output.hwp"
    executable = _write_local_cli_converter(
        tmp_path / "hwp-to-hwpx.py",
        _minimal_hwpx_package("12주차"),
    )
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(_FakeHwpReadEngine())
    engine_registry.register(_FakeHwpXMutationRenderEngine())
    conversion_registry = DocumentConversionRegistry()
    conversion_registry.register(
        LocalCliDocumentConversionEngine(
            source_format=DocumentFormat.hwp,
            output_format=DocumentFormat.hwpx,
            engine_id="local-hwp-to-hwpx-for-direct-hwp-block",
            executable=executable,
            args=("{source}", "{output}"),
        )
    )
    runtime = DocumentToolRuntime(
        session_id="hwp-direct-destination-blocked",
        artifact_root=tmp_path / "store",
        engine_registry=engine_registry,
        conversion_registry=conversion_registry,
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-hwp-direct-destination-blocked",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
            operation="fill",
            instruction="문서 내용을 파악하고 13주차 활동일지로 작성한 뒤 HWP로 저장해.",
            patches=(DocumentFieldPatch(target_path="/hwpx/text[1]", value="13주차"),),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.extension_mismatch
    assert "extension must match .hwpx" in result.text_summary
    assert not result.saved_exports
    assert not destination.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha256_before


def test_document_primitive_fills_converted_hwp_derivative_through_single_operation(
    tmp_path: Path,
) -> None:
    source = _write_minimal_hwp(tmp_path / "legacy-weekly-form.hwp")
    conversion = _FakeHwpToWeeklyHwpXConversionEngine()
    conversion_registry = DocumentConversionRegistry()
    conversion_registry.register(conversion)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(_FakeHwpReadEngine())
    engine_registry.register(_FakeHwpXMutationRenderEngine())
    runtime = DocumentToolRuntime(
        session_id="hwp-document-primitive-conversion",
        artifact_root=tmp_path / "store",
        engine_registry=engine_registry,
        conversion_registry=conversion_registry,
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-hwp-document-conversion",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
            operation="fill",
            instruction="문서 내용을 파악하고 13주차 활동일지로 알아서 작성해.",
        )
    )

    assert result.status is ToolResultStatus.ok
    assert conversion.source_artifact_id == "source-corr-hwp-document-conversion"
    assert result.diff is not None
    changed = {
        (change.target_path, change.before_value, change.after_value)
        for change in result.diff.changes
    }
    assert ("/hwpx/text[1]", "12주차", "13주차") in changed
    assert result.render_artifacts
    assert result.artifact_refs[:2] == [
        "source-corr-hwp-document-conversion",
        "working-corr-hwp-document-conversion",
    ]
    working = runtime.store.load_artifact("working-corr-hwp-document-conversion")
    assert working is not None
    assert working.format is DocumentFormat.hwpx
    derivative = runtime.store.load_artifact("derivative-corr-hwp-document-conversion")
    assert derivative is not None
    reread = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-hwp-document-conversion-reread",
            document=DocumentLocator(artifact_id=derivative.artifact_id),
        )
    )
    assert reread.status is ToolResultStatus.ok
    assert reread.extraction is not None
    assert [paragraph.text for paragraph in reread.extraction.paragraphs] == ["13주차"]
    assert source.read_bytes() == _MINIMAL_HWP_BYTES


def test_default_runtime_converts_public_ax_hwp_derivative_renders_html_and_saves(
    tmp_path: Path,
) -> None:
    if not _repo_local_hwpxjs().is_file():
        pytest.skip("repo-local hwpxjs bridge is not installed")
    source = _public_ax_hwp_fixture_named("아이디어 기획서 양식")
    source_sha256_before = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "completed-from-hwp.hwpx"
    runtime = DocumentToolRuntime(
        session_id="hwp-public-ax-real-derivative",
        artifact_root=tmp_path / "store",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="hwp-public-ax-real-derivative",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
            operation="save",
            instruction=(f"팀명을 GovOn-HWP로 보정한 뒤 HWPX derivative로 {destination}에 저장해."),
            patches=(DocumentFieldPatch(target_path="팀명", value="GovOn-HWP"),),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.diff is not None
    assert result.render_artifacts
    first_render = result.render_artifacts[0]
    assert first_render.render_mime_type == "text/html"
    assert first_render.engine_id == "hwpxjs-html-render"
    render_html = Path(first_render.render_path).read_text(encoding="utf-8")
    assert 'data-ummaya-render-engine="hwpxjs-html-render"' in render_html
    assert "GovOn-HWP" in render_html
    assert "hwpx-table" in render_html
    assert result.saved_exports
    assert destination.is_file()
    assert destination.suffix == ".hwpx"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha256_before

    reread = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwp-public-ax-real-derivative-reread",
            document=DocumentLocator(path=str(destination), expected_format=DocumentFormat.hwpx),
        )
    )
    assert reread.status is ToolResultStatus.ok
    assert reread.extraction is not None
    assert "GovOn-HWP" in "\n".join(paragraph.text for paragraph in reread.extraction.paragraphs)


def test_hwp_document_primitive_derives_hwpx_save_path_from_instruction(
    tmp_path: Path,
) -> None:
    if not _repo_local_hwpxjs().is_file():
        pytest.skip("repo-local hwpxjs bridge is not installed")
    source = _public_ax_hwp_fixture_named("아이디어 기획서 양식")
    source_sha256_before = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "instruction-derived-from-hwp.hwpx"
    runtime = DocumentToolRuntime(
        session_id="hwp-instruction-derived-save-path",
        artifact_root=tmp_path / "store",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="hwp-instruction-derived-save-path",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
            operation="fill",
            instruction=(
                "팀명은 GovOn-HWP로 작성하고, "
                f"저장은 {destination} 로 해줘."
            ),
            patches=(DocumentFieldPatch(target_path="팀명", value="GovOn-HWP"),),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert destination.is_file()
    assert result.saved_exports
    assert result.saved_exports[0].local_path == destination
    assert result.saved_exports[0].sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha256_before


def test_document_primitive_keeps_llm_planned_patches_for_autonomous_hwp_prompt(
    tmp_path: Path,
) -> None:
    if not _repo_local_hwpxjs().is_file():
        pytest.skip("repo-local hwpxjs bridge is not installed")
    source = _public_ax_hwp_fixture_named("아이디어 기획서 양식")
    runtime = DocumentToolRuntime(
        session_id="hwp-autonomous-with-planned-patch",
        artifact_root=tmp_path / "store",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="hwp-autonomous-with-planned-patch",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
            operation="fill",
            instruction="문서 내용을 파악하고 팀명은 GovOn-HWP로 알아서 작성해.",
            patches=(DocumentFieldPatch(target_path="팀명", value="GovOn-HWP"),),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.diff is not None
    assert ("/hwpx/text[3]", "UMMAYA", "GovOn-HWP") in {
        (change.target_path, change.before_value, change.after_value)
        for change in result.diff.changes
    }
    assert result.render_artifacts
    assert result.render_artifacts[0].engine_id == "hwpxjs-html-render"


def test_default_runtime_uses_explicit_env_hwp_conversion_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_minimal_hwp(tmp_path / "legacy-form.hwp")
    payload = _minimal_hwpx_package("환경변수 변환")
    executable = _write_local_cli_converter(tmp_path / "hwp-to-hwpx.py", payload)
    monkeypatch.setenv("UMMAYA_HWP_TO_HWPX_CONVERTER", str(executable))
    monkeypatch.setenv("UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON", '["{source}", "{output}"]')
    monkeypatch.setenv("UMMAYA_HWP_TO_HWPX_CONVERTER_ENGINE_ID", "local-env-hwp-to-hwpx")
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(_FakeHwpReadEngine())
    engine_registry.register(HwpXPackageTextEngine())
    runtime = DocumentToolRuntime(
        session_id="hwp-copy-env-cli-bridge",
        artifact_root=tmp_path / "store",
        engine_registry=engine_registry,
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-hwp-env-cli-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwp),
        )
    )
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="corr-hwp-env-cli-copy",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )

    assert copy_result.status is ToolResultStatus.ok
    assert "local-env-hwp-to-hwpx" in copy_result.text_summary
    derivative = runtime.store.load_artifact(copy_result.artifact_refs[-1])
    assert derivative is not None
    assert derivative.format is DocumentFormat.hwpx
    assert source.read_bytes() == _MINIMAL_HWP_BYTES


def _public_ax_hwp_fixtures() -> list[Path]:
    evidence_root = (
        Path(__file__).resolve().parents[3]
        / ".evidence"
        / "document-fixtures"
        / "public-ax-samples"
    )
    if not evidence_root.exists():
        pytest.skip("public AX local evidence fixture directory is not available")
    matches = sorted(path for path in evidence_root.iterdir() if path.suffix == ".hwp")
    if not matches:
        pytest.skip("public AX local HWP fixtures are not available")
    expected_hashes = {
        "2. [서식1~서식5] 2026년 경기도 공공데이터·AI 활용 창업경진대회 제출 서류.hwp": (
            "9252a7b5692bb44e2533326942921de060d81bc3151445e24153d35a7e2a3503"
        ),
        (
            "2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_"
            "개인정보 수집·이용 동의서.hwp"
        ): ("8ffe8877b57b5b4de11b9654b7bbb8afecea9803a15ef138a213ce2fd072ec36"),
        ("2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_아이디어 기획서 양식.hwp"): (
            "aee02b7477ae8abbafb4a2ce222c143fb43c4105876a850f80052e60f0696c3c"
        ),
        "2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_참가서약서.hwp": (
            "58e23b06274ee3b2b341c521dbf5c73df078ec9d5e2db328023544d376d80cb9"
        ),
    }
    for path in matches:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expected_hashes[path.name]
    return matches


def _public_ax_hwp_fixture_named(name_part: str) -> Path:
    matches = [path for path in _public_ax_hwp_fixtures() if name_part in path.name]
    assert len(matches) == 1
    return matches[0]


def _repo_local_hwpxjs() -> Path:
    return Path(__file__).resolve().parents[3] / "node_modules" / ".bin" / "hwpxjs"


_MINIMAL_HWP_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"minimal-hwp-fixture"


def _write_minimal_hwp(path: Path) -> Path:
    path.write_bytes(_MINIMAL_HWP_BYTES)
    return path


def _minimal_hwpx_package(text: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/owpml")
        archive.writestr("version.xml", "<version />")
        archive.writestr("Contents/header.xml", "<header />")
        archive.writestr(
            "Contents/section0.xml",
            (
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<hs:sec xmlns:hp='http://www.hancom.co.kr/hwpml/2011/paragraph' "
                "xmlns:hs='http://www.hancom.co.kr/hwpml/2011/section'>"
                f"<hp:p><hp:run><hp:t>{escape(text)}</hp:t></hp:run></hp:p>"
                "</hs:sec>"
            ),
        )
        archive.writestr("META-INF/manifest.xml", "<manifest />")
        archive.writestr("Preview/PrvText.txt", f"<{text}>")
    return output.getvalue()


def _write_local_cli_converter(path: Path, payload: bytes) -> Path:
    payload_path = path.with_suffix(".payload")
    payload_path.write_bytes(payload)
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "source = Path(sys.argv[1])",
                "output = Path(sys.argv[2])",
                "_ = source.read_bytes()",
                f"output.write_bytes(Path({str(payload_path)!r}).read_bytes())",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert os.access(path, os.X_OK)
    return path


class _FakeHwpReadEngine:
    document_format = DocumentFormat.hwp
    engine_id = "fake-hwp-read"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=[
                ParagraphBlock(
                    block_id="hwp-paragraph-001",
                    text=f"Legacy HWP extracted from {path.name}",
                    source_path="/hwp/body/paragraph[1]",
                )
            ],
            fields=[
                FormField(
                    field_id="legacy-hwp-field",
                    label="성명",
                    path="/hwp/text[1]",
                    field_type="text",
                    required=False,
                    current_value="",
                    source_confidence=Decimal("1"),
                )
            ],
            metadata={"engine_id": self.engine_id},
        )


class _FakeHwpXReadEngine:
    document_format = DocumentFormat.hwpx
    engine_id = "fake-hwpx-read"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            fields=[
                FormField(
                    field_id="converted-hwpx-field",
                    label="성명",
                    path="/hwpx/text[1]",
                    field_type="text",
                    required=False,
                    current_value=path.read_text(encoding="utf-8"),
                    source_confidence=Decimal("1"),
                )
            ],
            metadata={"engine_id": self.engine_id},
        )


class _FakeHwpToHwpXConversionEngine:
    source_format = DocumentFormat.hwp
    output_format = DocumentFormat.hwpx
    engine_id = "fake-hwp-to-hwpx"
    payload = b"converted-hwpx-payload"

    def __init__(self) -> None:
        self.source_artifact_id: str | None = None

    def convert_for_edit(self, source: DocumentArtifact) -> bytes:
        self.source_artifact_id = source.artifact_id
        return self.payload


class _FakeHwpToWeeklyHwpXConversionEngine:
    source_format = DocumentFormat.hwp
    output_format = DocumentFormat.hwpx
    engine_id = "fake-hwp-to-weekly-hwpx"
    payload = _minimal_hwpx_package("12주차")

    def __init__(self) -> None:
        self.source_artifact_id: str | None = None

    def convert_for_edit(self, source: DocumentArtifact) -> bytes:
        self.source_artifact_id = source.artifact_id
        return self.payload


class _FakeHwpXMutationRenderEngine(HwpXPackageTextEngine):
    engine_id = "fake-hwpx-mutation-render"
    render_engine_id = "fake-hwpx-render"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        _ = artifact_id
        output_dir.mkdir(parents=True, exist_ok=True)
        text = "\n".join(
            paragraph.text for paragraph in self.inspect(path, artifact_id="r").paragraphs
        )
        return (
            (
                "<svg xmlns='http://www.w3.org/2000/svg' width='420' height='120'>"
                f"<text x='24' y='64'>{text}</text>"
                "</svg>"
            ).encode(),
        )
