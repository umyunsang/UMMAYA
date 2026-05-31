# SPDX-License-Identifier: Apache-2.0
"""Render and re-read loop tests for generated document artifacts."""

from __future__ import annotations

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
    return store, derivative


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
