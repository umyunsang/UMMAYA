# SPDX-License-Identifier: Apache-2.0
"""Public-form conformance validator tests for the document harness."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ummaya.tools.documents.baselines import (
    CONFORMANCE_BASELINE_FIXTURE_PATH,
    load_conformance_baselines,
)
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentExtraction,
    FormField,
    ParagraphBlock,
    TableBlock,
    TableCell,
    ToolResultStatus,
    ValidationDecision,
    ValidationReadiness,
)
from ummaya.tools.documents.validate import validate_public_form


def test_public_form_baseline_manifest_covers_format_authorities() -> None:
    catalog = load_conformance_baselines(CONFORMANCE_BASELINE_FIXTURE_PATH)

    assert Path(CONFORMANCE_BASELINE_FIXTURE_PATH).is_file()
    assert catalog.live_network_allowed is False
    assert {baseline.format for baseline in catalog.baselines} >= {
        "hwpx",
        "docx",
        "xlsx",
        "pptx",
        "pdf",
        "hwp",
    }
    assert catalog.by_template_id("birth-benefit-application-hwpx").authoritative_standard == (
        "KS X 6101 OWPML/HWPX"
    )
    assert catalog.by_template_id("civil-form-docx").authoritative_standard == (
        "ECMA-376 Office Open XML"
    )
    assert catalog.by_template_id("fillable-permit-pdf").authoritative_standard == (
        "PDF AcroForm and rendered appearance"
    )
    assert catalog.by_template_id("legacy-hwp-readonly").supports_conformance is False
    assert "HWP binary write is blocked" in (
        catalog.by_template_id("legacy-hwp-readonly").unsupported_reason or ""
    )


def test_validator_marks_known_good_derivative_ready_for_review() -> None:
    baseline = load_conformance_baselines().by_template_id("birth-benefit-application-hwpx")
    extraction = _matching_birth_benefit_extraction()

    result = validate_public_form(
        extraction,
        baseline=baseline,
        artifact_id="artifact-good",
        correlation_id="corr-good",
    )

    assert result.status is ToolResultStatus.ok
    assert result.blocked_reason is None
    assert result.validation_report is not None
    assert result.validation_report.decision is ValidationDecision.pass_
    assert result.validation_report.readiness is ValidationReadiness.ready_for_review
    assert result.validation_report.aggregate_score == Decimal("1")
    assert result.findings == []


def test_validator_blocks_hard_rule_drift_with_anchors_and_remediation() -> None:
    baseline = load_conformance_baselines().by_template_id("birth-benefit-application-hwpx")
    extraction = _matching_birth_benefit_extraction().model_copy(
        update={
            "fields": [
                FormField(
                    field_id="applicant_name",
                    label="Applicant name",
                    path="/body/section[1]/field[applicant_name]",
                    field_type="text",
                    required=True,
                    current_value="",
                    source_confidence=Decimal("1"),
                )
            ],
            "paragraphs": [
                ParagraphBlock(
                    block_id="p-001",
                    text="Birth benefit application",
                    source_path="/body/section[1]/p[1]",
                )
            ],
            "tables": [
                TableBlock(
                    block_id="applicant-table",
                    source_path="/body/section[1]/table[1]",
                    cells=[
                        TableCell(
                            row_index=0,
                            column_index=0,
                            text="Applicant",
                            source_path="/body/section[1]/table[1]/cell[1,1]",
                        )
                    ],
                )
            ],
        }
    )

    result = validate_public_form(
        extraction,
        baseline=baseline,
        artifact_id="artifact-damaged",
        correlation_id="corr-damaged",
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.validation_failed
    assert result.validation_report is not None
    assert result.validation_report.decision is ValidationDecision.fail
    assert result.validation_report.readiness is ValidationReadiness.not_ready
    hard_failures = [
        finding
        for finding in result.validation_report.findings
        if finding.severity == "hard_failure"
    ]
    assert {finding.code for finding in hard_failures} >= {
        "required_field_missing",
        "protected_text_missing",
        "table_geometry_mismatch",
        "signature_or_seal_region_missing",
    }
    assert all(finding.anchor for finding in hard_failures)
    assert all(finding.remediation_hint for finding in hard_failures)


def test_unsupported_conformance_returns_typed_blocked_result_without_guessing() -> None:
    baseline = load_conformance_baselines().by_template_id("legacy-hwp-readonly")

    result = validate_public_form(
        DocumentExtraction(artifact_id="artifact-hwp"),
        baseline=baseline,
        artifact_id="artifact-hwp",
        correlation_id="corr-hwp",
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.unsupported_operation
    assert result.validation_report is not None
    assert result.validation_report.decision is ValidationDecision.blocked
    assert result.validation_report.readiness is ValidationReadiness.unsupported
    assert result.validation_report.findings[0].code == "unsupported_for_conformance"
    assert result.validation_report.findings[0].anchor == "template:legacy-hwp-readonly"


def _matching_birth_benefit_extraction() -> DocumentExtraction:
    return DocumentExtraction(
        artifact_id="artifact-good",
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
                current_value="Hong Gil-dong",
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
