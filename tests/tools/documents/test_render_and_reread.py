# SPDX-License-Identifier: Apache-2.0
"""Render and re-read loop tests for generated document artifacts."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.baselines import load_conformance_baselines
from ummaya.tools.documents.diff import diff_from_patch
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.models import (
    ArtifactLineage,
    BlockedReason,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    FormField,
    OperationType,
    ParagraphBlock,
    TableBlock,
    TableCell,
    ToolResultStatus,
    ValidationDecision,
    ValidationReadiness,
)
from ummaya.tools.documents.render import render_document_evidence
from ummaya.tools.documents.reread import reread_derivative
from ummaya.tools.documents.validate import validate_public_form


class EvidenceEngine:
    """Engine-backed render and inspection test double."""

    def __init__(self, *, document_format: DocumentFormat, observed_name: str = "Hong Gil-dong"):
        self.document_format = document_format
        self.engine_id = f"evidence-engine-{document_format.value}"
        self.observed_name = observed_name
        self.rendered_paths: list[Path] = []
        self.inspected_paths: list[Path] = []

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        self.inspected_paths.append(path)
        return _birth_benefit_extraction(artifact_id=artifact_id, applicant_name=self.observed_name)

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        self.rendered_paths.append(path)
        return (
            f"render evidence for {artifact_id} page 1".encode(),
            f"render evidence for {artifact_id} page 2".encode(),
        )


class ExplodingRenderEngine(EvidenceEngine):
    """Render test double that models a native bridge panic."""

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        self.rendered_paths.append(path)
        raise RuntimeError("renderer exploded while laying out page border")


class SvgEvidenceEngine(EvidenceEngine):
    """SVG render test double with per-glyph text like RHWP output."""

    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        self.rendered_paths.append(path)
        return (
            """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80" viewBox="0 0 200 80">
<text x="20" y="40" font-size="16">1</text>
<text x="30" y="40" font-size="16">3</text>
<text x="50" y="40" font-size="16">주</text>
<text x="70" y="40" font-size="16">차</text>
</svg>""".encode(),
        )


class BeforeAfterSvgEvidenceEngine(EvidenceEngine):
    """SVG render test double that exposes different source and derivative pages."""

    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        self.rendered_paths.append(path)
        week = "12 주차" if artifact_id.startswith("source-") else "13 주차"
        return (
            f"""<svg xmlns="http://www.w3.org/2000/svg"
 width="420" height="594" viewBox="0 0 420 594">
<rect x="40" y="40" width="340" height="500"/>
<rect x="60" y="100" width="300" height="48"/>
<text x="110" y="78">주간활동일지</text>
<text x="74" y="130">{week}</text>
<text x="74" y="178">2026.06.01 ~ 2026.06.07</text>
</svg>""".encode(),
        )


class TitlePositionSvgEvidenceEngine(EvidenceEngine):
    """SVG render double matching the HWPX title-position crop regression."""

    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        self.rendered_paths.append(path)
        return (
            """<svg xmlns="http://www.w3.org/2000/svg"
 width="595" height="842" viewBox="0 0 595 842">
<text x="265.06" y="167.70" font-size="22.66" textLength="13.13">1</text>
<text x="278.20" y="167.70" font-size="22.66" textLength="13.13">3</text>
<text x="302.66" y="167.70" font-size="22.66">주</text>
<text x="325.33" y="167.70" font-size="22.66">차</text>
<text x="359.33" y="167.70" font-size="22.66">주</text>
<text x="382.00" y="167.70" font-size="22.66">간</text>
<text x="416.00" y="167.70" font-size="22.66">활</text>
<text x="438.66" y="167.70" font-size="22.66">동</text>
<text x="472.66" y="167.70" font-size="22.66">일</text>
<text x="495.33" y="167.70" font-size="22.66">지</text>
</svg>""".encode(),
        )


def test_render_uses_promoted_engine_and_records_page_artifacts(tmp_path: Path) -> None:
    store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.docx)
    registry = DocumentEngineRegistry()
    engine = EvidenceEngine(document_format=DocumentFormat.docx)
    registry.register(engine)

    result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-render",
        artifact_id_prefix="render-docx",
    )

    assert result.status is ToolResultStatus.ok
    assert engine.rendered_paths == [Path(derivative.source_path)]
    assert result.render_passed is True
    assert result.correlation_id == "corr-render"
    assert [record.page_number for record in result.records] == [1, 2]
    assert all(record.source_artifact_id == derivative.artifact_id for record in result.records)
    assert all(record.source_sha256 == derivative.sha256 for record in result.records)
    assert all(Path(record.render_path).is_file() for record in result.records)
    assert result.artifact_refs == [record.render_artifact_id for record in result.records]


def test_render_engine_exception_returns_blocked_result_without_artifacts(tmp_path: Path) -> None:
    store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.hwpx)
    registry = DocumentEngineRegistry()
    engine = ExplodingRenderEngine(document_format=DocumentFormat.hwpx)
    registry.register(engine)

    result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-render-explodes",
        artifact_id_prefix="render-hwpx-explodes",
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.validation_failed
    assert result.render_passed is False
    assert result.records == ()
    assert result.baseline_records == ()
    assert result.changed_viewports == ()
    assert result.artifact_refs == []
    assert "evidence-engine-hwpx" in result.text_summary
    assert "renderer exploded while laying out page border" in result.text_summary


def test_reread_compares_saved_derivative_against_intended_patch(tmp_path: Path) -> None:
    _store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.hwpx)
    registry = DocumentEngineRegistry()
    engine = EvidenceEngine(document_format=DocumentFormat.hwpx)
    registry.register(engine)
    patch = _applicant_patch(derivative.artifact_id, document_format=DocumentFormat.hwpx)

    result = reread_derivative(
        derivative,
        patch,
        engine_registry=registry,
        correlation_id="corr-reread",
    )

    assert result.status is ToolResultStatus.ok
    assert result.round_trip_passed is True
    assert result.correlation_id == "corr-reread"
    assert result.extraction.artifact_id == derivative.artifact_id
    assert result.mismatches == ()
    assert engine.inspected_paths == [Path(derivative.source_path)]


def test_reread_reports_mismatched_expected_values(tmp_path: Path) -> None:
    _store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.pdf)
    registry = DocumentEngineRegistry()
    engine = EvidenceEngine(document_format=DocumentFormat.pdf, observed_name="Wrong Name")
    registry.register(engine)
    patch = _applicant_patch(derivative.artifact_id, document_format=DocumentFormat.pdf)

    result = reread_derivative(
        derivative,
        patch,
        engine_registry=registry,
        correlation_id="corr-reread-mismatch",
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.validation_failed
    assert result.round_trip_passed is False
    assert len(result.mismatches) == 1
    assert result.mismatches[0].expected_value == "Hong Gil-dong"
    assert result.mismatches[0].observed_value == "Wrong Name"
    assert result.mismatches[0].target_path == "/body/section[1]/field[applicant_name]"


def test_structured_diff_can_include_render_artifact_records(tmp_path: Path) -> None:
    store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.xlsx)
    registry = DocumentEngineRegistry()
    registry.register(EvidenceEngine(document_format=DocumentFormat.xlsx))
    render_result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-diff-render",
        artifact_id_prefix="render-xlsx",
    )
    patch = _applicant_patch(derivative.artifact_id, document_format=DocumentFormat.xlsx)

    diff = diff_from_patch(
        patch,
        source_artifact_id="source-xlsx",
        derivative_artifact_id=derivative.artifact_id,
        render_artifacts=render_result.records,
    )

    assert diff.render_artifacts == render_result.records
    assert diff.render_artifacts[0].render_artifact_id == "render-xlsx-001"


def test_structured_diff_matches_engine_tail_against_absolute_document_path() -> None:
    extraction = DocumentExtraction(
        artifact_id="working-docx",
        paragraphs=[
            ParagraphBlock(
                block_id="docx-paragraph-001",
                text="13주차 활동일지",
                source_path="engine://python-docx/working.docx/paragraph/1",
            )
        ],
    )
    patch = DocumentPatch(
        patch_id="patch-docx-paragraph",
        target_artifact_id="working-docx",
        operations=[
            DocumentPatchOperation(
                operation_id="fill-docx-paragraph",
                operation_type=OperationType.set_field_value,
                target_path="/paragraph/1",
                value="14주차 활동일지",
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.docx,
        destination_policy="working_copy",
    )

    diff = diff_from_patch(
        patch,
        source_artifact_id="working-docx",
        derivative_artifact_id="derivative-docx",
        before_extraction=extraction,
    )

    assert [(change.before_value, change.after_value) for change in diff.changes] == [
        ("13주차 활동일지", "14주차 활동일지")
    ]


def test_structured_diff_labels_table_cell_change_from_left_neighbor() -> None:
    extraction = DocumentExtraction(
        artifact_id="working-hwpx",
        tables=[
            TableBlock(
                block_id="table-001",
                source_path="Contents/section0.xml#table[1]",
                cells=[
                    TableCell(
                        row_index=0,
                        column_index=0,
                        text="접수번호",
                        source_path="Contents/section0.xml#table[1]/r1c1",
                    ),
                    TableCell(
                        row_index=0,
                        column_index=1,
                        text="",
                        source_path="Contents/section0.xml#table[1]/r1c2",
                    ),
                ],
            )
        ],
    )
    patch = DocumentPatch(
        patch_id="patch-hwpx-table-cell",
        target_artifact_id="working-hwpx",
        operations=[
            DocumentPatchOperation(
                operation_id="fill-receipt-number",
                operation_type=OperationType.set_table_cell,
                target_path="Contents/section0.xml#table[1]/r1c2",
                value="UMMAYA-2026-0003",
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.hwpx,
        destination_policy="working_copy",
    )

    diff = diff_from_patch(
        patch,
        source_artifact_id="working-hwpx",
        derivative_artifact_id="derivative-hwpx",
        before_extraction=extraction,
    )

    assert diff.changes[0].display_label == "접수번호"
    assert diff.changes[0].target_path == "Contents/section0.xml#table[1]/r1c2"


def test_svg_render_detects_changed_viewports_without_mutating_page_render(tmp_path: Path) -> None:
    store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.hwpx)
    registry = DocumentEngineRegistry()
    registry.register(SvgEvidenceEngine(document_format=DocumentFormat.hwpx))
    diff = diff_from_patch(
        DocumentPatch(
            patch_id="patch-hwpx-diff",
            target_artifact_id=derivative.artifact_id,
            operations=[
                DocumentPatchOperation(
                    operation_id="fill-week",
                    operation_type=OperationType.set_field_value,
                    target_path="/hwpx/text[1]",
                    value="13 주차",
                )
            ],
            dry_run=False,
            expected_format=DocumentFormat.hwpx,
            destination_policy="working_copy",
        ),
        source_artifact_id="source-hwpx",
        derivative_artifact_id=derivative.artifact_id,
    )

    result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-svg-diff-render",
        artifact_id_prefix="render-hwpx-diff",
        diff=diff,
    )

    rendered_svg = Path(result.records[0].render_path).read_text(encoding="utf-8")
    assert 'id="ummaya-diff-overlay"' not in rendered_svg
    assert 'class="ummaya-diff-change"' not in rendered_svg
    assert ">1</text>" in rendered_svg
    assert ">3</text>" in rendered_svg
    assert len(result.changed_viewports) == 1
    viewport = result.changed_viewports[0]
    assert viewport.viewport_id == "viewport-render-hwpx-diff-001-change-001"
    assert viewport.change_ids == ("change-001",)
    assert viewport.source_render_artifact_id == "render-hwpx-diff-001"
    assert viewport.page_number == 1
    assert viewport.anchor_strategy == "exact_text_run"
    assert viewport.clip_rect.width > 0
    assert viewport.clip_rect.height > 0
    assert viewport.svg_artifact_ref == "viewport-render-hwpx-diff-001-change-001"
    assert viewport.svg_artifact_path is not None
    viewport_svg = Path(viewport.svg_artifact_path)
    assert viewport_svg.is_file()
    assert 'data-ummaya-viewport-id="viewport-render-hwpx-diff-001-change-001"' in (
        viewport_svg.read_text(encoding="utf-8")
    )
    assert "ummaya-diff-change" not in viewport_svg.read_text(encoding="utf-8")
    assert "+ 13 주차" in viewport.text_fallback


def test_svg_changed_viewport_centers_title_position_changes(tmp_path: Path) -> None:
    store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.hwpx)
    registry = DocumentEngineRegistry()
    registry.register(TitlePositionSvgEvidenceEngine(document_format=DocumentFormat.hwpx))
    diff = diff_from_patch(
        DocumentPatch(
            patch_id="patch-hwpx-title-position",
            target_artifact_id=derivative.artifact_id,
            operations=[
                DocumentPatchOperation(
                    operation_id="fill-week-title",
                    operation_type=OperationType.set_field_value,
                    target_path="/hwpx/text[2]",
                    value="13 주차",
                )
            ],
            dry_run=False,
            expected_format=DocumentFormat.hwpx,
            destination_policy="working_copy",
        ),
        source_artifact_id="source-hwpx",
        derivative_artifact_id=derivative.artifact_id,
    )

    result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-title-position-render",
        artifact_id_prefix="render-hwpx-title-position",
        diff=diff,
    )

    viewport = result.changed_viewports[0]
    assert viewport.clip_rect.x <= Decimal("210")
    assert viewport.clip_rect.width >= Decimal("220")
    assert viewport.clip_rect.height >= Decimal("120")


def test_svg_changed_viewport_writes_optional_png_raster_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_rsvg = bin_dir / "rsvg-convert"
    fake_rsvg.write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
printf '\\211PNG\\r\\n\\032\\nummaya-test-png' > "$out"
""",
        encoding="utf-8",
    )
    fake_rsvg.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.hwpx)
    registry = DocumentEngineRegistry()
    registry.register(SvgEvidenceEngine(document_format=DocumentFormat.hwpx))
    diff = diff_from_patch(
        DocumentPatch(
            patch_id="patch-hwpx-png-diff",
            target_artifact_id=derivative.artifact_id,
            operations=[
                DocumentPatchOperation(
                    operation_id="fill-week",
                    operation_type=OperationType.set_field_value,
                    target_path="/hwpx/text[1]",
                    value="13 주차",
                )
            ],
            dry_run=False,
            expected_format=DocumentFormat.hwpx,
            destination_policy="working_copy",
        ),
        source_artifact_id="source-hwpx",
        derivative_artifact_id=derivative.artifact_id,
    )

    result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-svg-png-diff-render",
        artifact_id_prefix="render-hwpx-png-diff",
        diff=diff,
    )

    viewport = result.changed_viewports[0]
    assert viewport.png_artifact_ref == "viewport-render-hwpx-png-diff-001-change-001-png"
    assert viewport.png_artifact_path is not None
    viewport_png = Path(viewport.png_artifact_path)
    assert viewport_png.is_file()
    assert viewport_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_svg_render_writes_full_page_png_raster_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_rsvg = bin_dir / "rsvg-convert"
    fake_rsvg.write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
printf '\\211PNG\\r\\n\\032\\nummaya-full-page-png' > "$out"
""",
        encoding="utf-8",
    )
    fake_rsvg.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.hwpx)
    registry = DocumentEngineRegistry()
    registry.register(SvgEvidenceEngine(document_format=DocumentFormat.hwpx))

    result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-svg-full-page-raster",
        artifact_id_prefix="render-hwpx-full-page",
    )

    record = result.records[0]
    assert record.raster_artifact_ref == "render-hwpx-full-page-001-png"
    assert record.raster_artifact_path is not None
    assert record.raster_mime_type == "image/png"
    page_png = Path(record.raster_artifact_path)
    assert page_png.is_file()
    assert page_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_svg_changed_viewport_writes_clean_before_after_comparison_rasters(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_rsvg = bin_dir / "rsvg-convert"
    fake_rsvg.write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
printf '\\211PNG\\r\\n\\032\\nummaya-test-png' > "$out"
""",
        encoding="utf-8",
    )
    fake_rsvg.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    store, source, derivative = _stored_source_and_derivative(
        tmp_path,
        document_format=DocumentFormat.hwpx,
    )
    registry = DocumentEngineRegistry()
    registry.register(BeforeAfterSvgEvidenceEngine(document_format=DocumentFormat.hwpx))
    diff = diff_from_patch(
        DocumentPatch(
            patch_id="patch-hwpx-comparison-diff",
            target_artifact_id=derivative.artifact_id,
            operations=[
                DocumentPatchOperation(
                    operation_id="fill-week",
                    operation_type=OperationType.set_field_value,
                    target_path="/hwpx/text[1]",
                    value="13 주차",
                )
            ],
            dry_run=False,
            expected_format=DocumentFormat.hwpx,
            destination_policy="working_copy",
        ),
        source_artifact_id=source.artifact_id,
        derivative_artifact_id=derivative.artifact_id,
    )

    result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-svg-comparison-diff-render",
        artifact_id_prefix="render-hwpx-comparison-diff",
        diff=diff,
        baseline_artifact=source,
    )

    viewport = result.changed_viewports[0]
    assert viewport.svg_artifact_path is not None
    assert viewport.after_svg_artifact_path == viewport.svg_artifact_path
    assert viewport.png_artifact_path is not None
    assert viewport.after_png_artifact_path == viewport.png_artifact_path
    assert viewport.before_svg_artifact_path is not None
    assert viewport.after_svg_artifact_path is not None
    assert viewport.before_png_artifact_path is not None
    assert viewport.after_png_artifact_path is not None

    before_svg = Path(viewport.before_svg_artifact_path)
    after_svg = Path(viewport.after_svg_artifact_path)
    assert "12 주차" in before_svg.read_text(encoding="utf-8")
    assert "13 주차" in after_svg.read_text(encoding="utf-8")
    assert "ummaya-diff-change" not in before_svg.read_text(encoding="utf-8")
    assert "ummaya-diff-change" not in after_svg.read_text(encoding="utf-8")

    for png_path in (
        viewport.before_png_artifact_path,
        viewport.after_png_artifact_path,
    ):
        assert png_path is not None
        assert Path(png_path).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_svg_render_exposes_full_page_viewport_camera_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_rsvg = bin_dir / "rsvg-convert"
    fake_rsvg.write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
printf '\\211PNG\\r\\n\\032\\nummaya-full-page-camera-png' > "$out"
""",
        encoding="utf-8",
    )
    fake_rsvg.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    store, source, derivative = _stored_source_and_derivative(
        tmp_path,
        document_format=DocumentFormat.hwpx,
    )
    registry = DocumentEngineRegistry()
    registry.register(BeforeAfterSvgEvidenceEngine(document_format=DocumentFormat.hwpx))
    diff = diff_from_patch(
        DocumentPatch(
            patch_id="patch-hwpx-camera-diff",
            target_artifact_id=derivative.artifact_id,
            operations=[
                DocumentPatchOperation(
                    operation_id="fill-week",
                    operation_type=OperationType.set_field_value,
                    target_path="/hwpx/text[1]",
                    value="13 주차",
                )
            ],
            dry_run=False,
            expected_format=DocumentFormat.hwpx,
            destination_policy="working_copy",
        ),
        source_artifact_id=source.artifact_id,
        derivative_artifact_id=derivative.artifact_id,
    )

    result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-svg-camera-diff-render",
        artifact_id_prefix="render-hwpx-camera-diff",
        diff=diff,
        baseline_artifact=source,
    )

    assert result.records
    assert result.baseline_records
    camera = result.viewport_cameras[0]
    viewport = result.changed_viewports[0]
    assert camera.source_render_artifact_id == result.records[0].render_artifact_id
    assert camera.baseline_render_artifact_id == result.baseline_records[0].render_artifact_id
    assert camera.page_index == 0
    assert camera.zoom == Decimal("1")
    assert camera.change_ids == viewport.change_ids
    assert camera.viewport_rect == viewport.clip_rect
    assert result.baseline_records[0].raster_artifact_path is not None
    assert Path(result.baseline_records[0].raster_artifact_path).is_file()


def test_svg_render_reuses_identical_artifacts_for_repeated_viewport_camera_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_rsvg = bin_dir / "rsvg-convert"
    fake_rsvg.write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    out="$1"
  fi
  shift
done
printf '\\211PNG\\r\\n\\032\\nummaya-repeat-camera-png' > "$out"
""",
        encoding="utf-8",
    )
    fake_rsvg.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    store, source, derivative = _stored_source_and_derivative(
        tmp_path,
        document_format=DocumentFormat.hwpx,
    )
    registry = DocumentEngineRegistry()
    registry.register(BeforeAfterSvgEvidenceEngine(document_format=DocumentFormat.hwpx))
    diff = diff_from_patch(
        DocumentPatch(
            patch_id="patch-hwpx-repeat-camera-diff",
            target_artifact_id=derivative.artifact_id,
            operations=[
                DocumentPatchOperation(
                    operation_id="fill-week",
                    operation_type=OperationType.set_field_value,
                    target_path="/hwpx/text[1]",
                    value="13 주차",
                )
            ],
            dry_run=False,
            expected_format=DocumentFormat.hwpx,
            destination_policy="working_copy",
        ),
        source_artifact_id=source.artifact_id,
        derivative_artifact_id=derivative.artifact_id,
    )

    first = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-svg-repeat-camera-diff-render",
        artifact_id_prefix="render-hwpx-repeat-camera-diff",
        diff=diff,
        baseline_artifact=source,
    )
    second = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-svg-repeat-camera-diff-render",
        artifact_id_prefix="render-hwpx-repeat-camera-diff",
        diff=diff,
        baseline_artifact=source,
    )

    assert second.status is ToolResultStatus.ok
    assert [record.render_artifact_id for record in second.records] == [
        record.render_artifact_id for record in first.records
    ]
    assert [record.render_artifact_id for record in second.baseline_records] == [
        record.render_artifact_id for record in first.baseline_records
    ]
    assert [viewport.viewport_id for viewport in second.changed_viewports] == [
        viewport.viewport_id for viewport in first.changed_viewports
    ]
    assert second.viewport_cameras == first.viewport_cameras
    assert second.changed_viewports[0].before_svg_artifact_ref is not None
    assert second.changed_viewports[0].after_svg_artifact_ref is not None
    assert second.records[0].raster_artifact_ref == first.records[0].raster_artifact_ref
    assert second.baseline_records[0].raster_artifact_ref == (
        first.baseline_records[0].raster_artifact_ref
    )


def test_render_or_reread_mismatch_downgrades_validation_readiness(tmp_path: Path) -> None:
    _store, derivative = _stored_derivative(tmp_path, document_format=DocumentFormat.hwpx)
    baseline = load_conformance_baselines().by_template_id("birth-benefit-application-hwpx")
    extraction = _birth_benefit_extraction(
        artifact_id=derivative.artifact_id,
        applicant_name="Hong Gil-dong",
    )

    result = validate_public_form(
        extraction,
        baseline=baseline,
        artifact_id=derivative.artifact_id,
        correlation_id="corr-validation-downgrade",
        round_trip_passed=False,
        render_passed=False,
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.validation_failed
    assert result.validation_report is not None
    assert result.validation_report.decision is ValidationDecision.needs_manual_review
    assert result.validation_report.readiness is ValidationReadiness.not_ready
    assert {finding.code for finding in result.validation_report.findings} >= {
        "round_trip_mismatch",
        "render_mismatch",
    }


def _stored_derivative(
    tmp_path: Path,
    *,
    document_format: DocumentFormat,
):
    store, _source, derivative = _stored_source_and_derivative(
        tmp_path,
        document_format=document_format,
    )
    return store, derivative


def _stored_source_and_derivative(
    tmp_path: Path,
    *,
    document_format: DocumentFormat,
):
    original = tmp_path / f"source.{document_format.value}"
    original.write_text("source bytes", encoding="utf-8")
    store = DocumentArtifactStore(root=tmp_path / "store", session_id=f"session-{document_format}")
    source = store.store_source(
        original,
        artifact_id=f"source-{document_format.value}",
        document_format=document_format,
        mime_type="application/octet-stream",
    )
    derivative = store.write_derivative(
        source,
        artifact_id=f"derivative-{document_format.value}",
        lineage=ArtifactLineage.working_copy,
        destination_name=f"derivative.{document_format.value}",
        payload=b"derivative bytes",
    )
    return store, source, derivative


def _applicant_patch(
    artifact_id: str,
    *,
    document_format: DocumentFormat,
) -> DocumentPatch:
    return DocumentPatch(
        patch_id=f"patch-{document_format.value}",
        target_artifact_id=artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="fill-applicant-name",
                operation_type=OperationType.set_field_value,
                target_path="/body/section[1]/field[applicant_name]",
                value="Hong Gil-dong",
            )
        ],
        dry_run=False,
        expected_format=document_format,
        destination_policy="working_copy",
    )


def _birth_benefit_extraction(
    *,
    artifact_id: str,
    applicant_name: str,
) -> DocumentExtraction:
    return DocumentExtraction(
        artifact_id=artifact_id,
        paragraphs=[
            ParagraphBlock(
                block_id="p-001",
                text="Birth benefit application",
                source_path="/body/section[1]/p[1]",
            ),
            ParagraphBlock(
                block_id="p-002",
                text="Applicant signature or seal",
                source_path="/body/section[1]/p[2]",
            ),
            ParagraphBlock(
                block_id="p-003",
                text="Required attachments",
                source_path="/body/section[2]/p[1]",
            ),
        ],
        tables=[
            TableBlock(
                block_id="applicant-table",
                source_path="/body/section[1]/table[1]",
                cells=[
                    TableCell(
                        row_index=0,
                        column_index=0,
                        text="Applicant",
                        source_path="/body/section[1]/table[1]/cell[1,1]",
                    ),
                    TableCell(
                        row_index=0,
                        column_index=1,
                        text="Name",
                        source_path="/body/section[1]/table[1]/cell[1,2]",
                    ),
                    TableCell(
                        row_index=1,
                        column_index=0,
                        text="Child",
                        source_path="/body/section[1]/table[1]/cell[2,1]",
                    ),
                    TableCell(
                        row_index=1,
                        column_index=1,
                        text="Date of birth",
                        source_path="/body/section[1]/table[1]/cell[2,2]",
                    ),
                ],
            )
        ],
        fields=[
            FormField(
                field_id="applicant_name",
                label="Applicant name",
                path="/body/section[1]/field[applicant_name]",
                field_type="text",
                required=True,
                current_value=applicant_name,
                source_confidence=Decimal("1"),
            ),
            FormField(
                field_id="child_birth_date",
                label="Child birth date",
                path="/body/section[1]/field[child_birth_date]",
                field_type="date",
                required=True,
                current_value="2026-05-01",
                source_confidence=Decimal("1"),
            ),
        ],
        metadata={
            "page_count": 2,
            "margin_top_mm": Decimal("20"),
            "margin_bottom_mm": Decimal("15"),
        },
    )
