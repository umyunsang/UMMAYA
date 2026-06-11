# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.diff import diff_from_patch
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.models import (
    ArtifactLineage,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    OperationType,
    ParagraphBlock,
    StyleDescriptor,
    TableBlock,
    TableCell,
)
from ummaya.tools.documents.render import render_document_evidence
from ummaya.tools.documents.render_comparison import build_render_comparison_evidence


class BeforeAfterStyleSvgEngine:
    document_format = DocumentFormat.hwpx
    engine_id = "before-after-style-svg-engine"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        _ = path
        return _style_extraction(artifact_id=artifact_id, font_family="Malgun Gothic")

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        _ = path
        _ = output_dir
        week = "12 주차" if artifact_id.startswith("source-") else "13 주차"
        return (
            f"""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="594">
<text x="74" y="130" font-size="16">{week}</text>
</svg>""".encode(),
        )


def test_render_comparison_records_changed_regions_and_style_deltas(tmp_path: Path) -> None:
    store, source, derivative = _stored_source_and_derivative(tmp_path)
    before_extraction = _style_extraction(artifact_id=source.artifact_id, font_family="Arial")
    after_extraction = _style_extraction(
        artifact_id=derivative.artifact_id,
        font_family="Malgun Gothic",
    )
    patch = _style_patch(derivative.artifact_id)
    diff = diff_from_patch(
        patch,
        source_artifact_id=source.artifact_id,
        derivative_artifact_id=derivative.artifact_id,
        before_extraction=before_extraction,
        after_extraction=after_extraction,
    )
    registry = DocumentEngineRegistry()
    registry.register(BeforeAfterStyleSvgEngine())

    render_result = render_document_evidence(
        store,
        derivative,
        engine_registry=registry,
        correlation_id="corr-render-comparison",
        artifact_id_prefix="render-style-comparison",
        diff=diff,
        baseline_artifact=source,
    )
    rendered_diff = diff.model_copy(
        update={
            "render_artifacts": render_result.records,
            "baseline_render_artifacts": render_result.baseline_records,
            "changed_viewports": render_result.changed_viewports,
            "viewport_cameras": render_result.viewport_cameras,
        }
    )

    evidence = build_render_comparison_evidence(
        source,
        derivative,
        diff=rendered_diff,
        before_extraction=before_extraction,
        after_extraction=after_extraction,
        confidence_threshold=Decimal("0.80"),
    )

    assert evidence.status == "pass"
    assert evidence.source_sha256 == source.sha256
    assert evidence.derivative_sha256 == derivative.sha256
    assert evidence.threshold_status == "pass"
    assert (
        evidence.changed_regions[0].region_id == "viewport-render-style-comparison-001-change-001"
    )
    assert evidence.changed_regions[0].source_render_sha256 == (
        render_result.baseline_records[0].render_sha256
    )
    assert evidence.changed_regions[0].derivative_render_sha256 == (
        render_result.records[0].render_sha256
    )
    style_delta_names = {delta.property_name for delta in evidence.style_deltas}
    assert style_delta_names >= {
        "font_family",
        "font_size_pt",
        "fill_color_rgb",
        "alignment",
    }
    assert evidence.style_deltas[0].target_path == "/body/table[1]/r1c2"
    assert evidence.table_geometry_deltas[0].target_path == "/body/table[1]/r1c2"
    assert evidence.table_geometry_deltas[0].before_column_span == 1
    assert evidence.table_geometry_deltas[0].after_column_span == 2


def test_render_comparison_blocks_without_source_to_derivative_record(
    tmp_path: Path,
) -> None:
    _store, source, derivative = _stored_source_and_derivative(tmp_path)
    before_extraction = _style_extraction(artifact_id=source.artifact_id, font_family="Arial")
    after_extraction = _style_extraction(
        artifact_id=derivative.artifact_id,
        font_family="Malgun Gothic",
    )
    diff = diff_from_patch(
        _style_patch(derivative.artifact_id),
        source_artifact_id=source.artifact_id,
        derivative_artifact_id=derivative.artifact_id,
        before_extraction=before_extraction,
        after_extraction=after_extraction,
    )

    evidence = build_render_comparison_evidence(
        source,
        derivative,
        diff=diff,
        before_extraction=before_extraction,
        after_extraction=after_extraction,
        confidence_threshold=Decimal("0.80"),
    )

    assert evidence.status == "blocked"
    assert evidence.threshold_status == "blocked"
    assert evidence.changed_regions == ()
    assert evidence.failure_reason == "source-to-derivative render comparison is missing"


def _stored_source_and_derivative(tmp_path: Path):
    original = tmp_path / "source.hwpx"
    original.write_text("source bytes", encoding="utf-8")
    store = DocumentArtifactStore(root=tmp_path / "store", session_id="session-render-compare")
    source = store.store_source(
        original,
        artifact_id="source-hwpx-style",
        document_format=DocumentFormat.hwpx,
        mime_type="application/octet-stream",
    )
    derivative = store.write_derivative(
        source,
        artifact_id="derivative-hwpx-style",
        lineage=ArtifactLineage.working_copy,
        destination_name="derivative.hwpx",
        payload=b"derivative bytes",
    )
    return store, source, derivative


def _style_extraction(*, artifact_id: str, font_family: str) -> DocumentExtraction:
    is_before = font_family == "Arial"
    return DocumentExtraction(
        artifact_id=artifact_id,
        paragraphs=[
            ParagraphBlock(
                block_id="p-week",
                text="13 주차",
                source_path="/hwpx/text[1]",
            )
        ],
        tables=[
            TableBlock(
                block_id="table-001",
                source_path="/body/table[1]",
                cells=[
                    TableCell(
                        row_index=0,
                        column_index=1,
                        text="12 주차" if is_before else "13 주차",
                        column_span=1 if is_before else 2,
                        source_path="/body/table[1]/r1c2",
                    )
                ],
            )
        ],
        style_map=[
            StyleDescriptor(
                style_id=f"style-{font_family}",
                target_path="/body/table[1]/r1c2",
                font_family=font_family,
                font_size_pt=Decimal("11") if is_before else Decimal("12"),
                fill_color_rgb="FFFFFF" if is_before else "FFF2CC",
                alignment="left" if is_before else "center",
            )
        ],
    )


def _style_patch(artifact_id: str) -> DocumentPatch:
    return DocumentPatch(
        patch_id="patch-render-style",
        target_artifact_id=artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="fill-week",
                operation_type=OperationType.set_field_value,
                target_path="/hwpx/text[1]",
                value="13 주차",
            ),
            DocumentPatchOperation(
                operation_id="style-table-cell",
                operation_type=OperationType.set_cell_style,
                target_path="/body/table[1]/r1c2",
                style=StyleDescriptor(
                    style_id="style-approved",
                    target_path="/body/table[1]/r1c2",
                    font_family="Malgun Gothic",
                    font_size_pt=Decimal("12"),
                    fill_color_rgb="FFF2CC",
                    alignment="center",
                ),
            ),
        ],
        dry_run=False,
        expected_format=DocumentFormat.hwpx,
        destination_policy="working_copy",
    )
