# SPDX-License-Identifier: Apache-2.0
"""Public-form conformance validation for extracted document artifacts."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from ummaya.tools.documents.baselines import (
    BaselineTableGeometry,
    BaselineTextAnchor,
    ConformanceBaseline,
)
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentExtraction,
    DocumentToolResult,
    PublicFormValidationReport,
    ToolResultStatus,
    ValidationDecision,
    ValidationFinding,
    ValidationReadiness,
)
from ummaya.tools.documents.scorecard import compute_public_form_metrics, table_shape


def validate_public_form(
    extraction: DocumentExtraction,
    *,
    baseline: ConformanceBaseline,
    artifact_id: str,
    correlation_id: str,
    round_trip_passed: bool = True,
    render_passed: bool = True,
    security_passed: bool = True,
) -> DocumentToolResult:
    """Validate one extracted derivative against a public-form baseline."""
    if not baseline.supports_conformance:
        finding = _finding(
            code="unsupported_for_conformance",
            message=baseline.unsupported_reason or "Public-form conformance is not supported.",
            anchor=f"template:{baseline.template_id}",
            remediation_hint="Use a promoted editable format with conformance evidence.",
        )
        report = _report(
            extraction,
            baseline=baseline,
            artifact_id=artifact_id,
            findings=[finding],
            decision=ValidationDecision.blocked,
            readiness=ValidationReadiness.unsupported,
            round_trip_passed=round_trip_passed,
            render_passed=render_passed,
            security_passed=security_passed,
        )
        return _result(
            report,
            status=ToolResultStatus.blocked,
            blocked_reason=BlockedReason.unsupported_operation,
            summary="Public-form validation blocked: conformance is unsupported.",
            correlation_id=correlation_id,
        )

    findings = _hard_rule_findings(extraction, baseline)
    if not security_passed:
        findings.append(
            _finding(
                code="security_check_failed",
                message="Security validation failed before public-form readiness.",
                anchor=f"artifact:{artifact_id}",
                remediation_hint="Resolve document security findings before validation.",
            )
        )
    if not round_trip_passed:
        findings.append(
            _finding(
                code="round_trip_mismatch",
                message="Round-trip extraction did not match intended document values.",
                anchor=f"artifact:{artifact_id}",
                remediation_hint="Re-read the derivative and repair mismatched values.",
            )
        )
    if not render_passed:
        findings.append(
            _finding(
                code="render_mismatch",
                message="Rendered derivative evidence did not match the expected layout.",
                anchor=f"artifact:{artifact_id}",
                remediation_hint="Repair layout drift and regenerate render evidence.",
            )
        )

    metrics = compute_public_form_metrics(extraction, baseline)
    hard_failure = any(finding.severity == "hard_failure" for finding in findings)
    decision, readiness = _decision(
        aggregate_score=metrics.aggregate_score,
        hard_failure=hard_failure,
        round_trip_passed=round_trip_passed,
        render_passed=render_passed,
        security_passed=security_passed,
    )
    report = _report(
        extraction,
        baseline=baseline,
        artifact_id=artifact_id,
        findings=findings,
        decision=decision,
        readiness=readiness,
        round_trip_passed=round_trip_passed,
        render_passed=render_passed,
        security_passed=security_passed,
    )
    if decision is ValidationDecision.pass_:
        return _result(
            report,
            status=ToolResultStatus.ok,
            blocked_reason=None,
            summary="Public-form validation passed; artifact is ready for human review.",
            correlation_id=correlation_id,
        )
    blocked_reason = (
        BlockedReason.unsupported_operation
        if readiness is ValidationReadiness.unsupported
        else BlockedReason.validation_failed
    )
    return _result(
        report,
        status=ToolResultStatus.blocked,
        blocked_reason=blocked_reason,
        summary="Public-form validation failed; artifact is not ready.",
        correlation_id=correlation_id,
    )


def _hard_rule_findings(
    extraction: DocumentExtraction,
    baseline: ConformanceBaseline,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    findings.extend(_required_field_findings(extraction, baseline))
    findings.extend(
        _required_text_findings(
            extraction,
            baseline.protected_text,
            "protected_text_missing",
        )
    )
    findings.extend(
        _required_text_findings(
            extraction,
            baseline.required_labels,
            "required_label_missing",
        )
    )
    findings.extend(_table_geometry_findings(extraction, baseline.table_geometries))
    findings.extend(
        _required_text_findings(
            extraction,
            baseline.signature_regions,
            "signature_or_seal_region_missing",
        )
    )
    findings.extend(_metadata_findings(extraction, baseline))
    return findings


def _required_field_findings(
    extraction: DocumentExtraction,
    baseline: ConformanceBaseline,
) -> list[ValidationFinding]:
    by_field_id = {field.field_id: field for field in extraction.fields}
    findings: list[ValidationFinding] = []
    for required in baseline.required_fields:
        observed = by_field_id.get(required.field_id)
        if observed is None or observed.current_value in {None, ""}:
            findings.append(
                _finding(
                    code="required_field_missing",
                    message=f"Required field {required.label!r} is missing or empty.",
                    anchor=required.path,
                    remediation_hint=f"Fill the {required.label!r} field before export.",
                )
            )
    return findings


def _required_text_findings(
    extraction: DocumentExtraction,
    expected: tuple[BaselineTextAnchor, ...],
    code: str,
) -> list[ValidationFinding]:
    observed_text = _combined_text(extraction)
    findings: list[ValidationFinding] = []
    for item in expected:
        if item.text not in observed_text:
            findings.append(
                _finding(
                    code=code,
                    message=f"Required public-form text {item.text!r} is missing.",
                    anchor=item.anchor,
                    remediation_hint=f"Restore required text {item.text!r} at the baseline anchor.",
                )
            )
    return findings


def _table_geometry_findings(
    extraction: DocumentExtraction,
    expected: tuple[BaselineTableGeometry, ...],
) -> list[ValidationFinding]:
    tables_by_id = {table.block_id: table for table in extraction.tables}
    findings: list[ValidationFinding] = []
    for geometry in expected:
        observed = tables_by_id.get(geometry.table_id)
        observed_rows, observed_columns = table_shape(observed)
        if observed_rows != geometry.rows or observed_columns != geometry.columns:
            findings.append(
                _finding(
                    code="table_geometry_mismatch",
                    message=(
                        f"Table {geometry.table_id!r} shape is "
                        f"{observed_rows}x{observed_columns}, expected "
                        f"{geometry.rows}x{geometry.columns}."
                    ),
                    anchor=geometry.anchor,
                    remediation_hint="Restore the protected table row and column geometry.",
                )
            )
    return findings


def _metadata_findings(
    extraction: DocumentExtraction,
    baseline: ConformanceBaseline,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    expected_metadata = dict(baseline.metadata_exact_matches)
    if baseline.expected_page_count is not None:
        expected_metadata["page_count"] = baseline.expected_page_count
    for key, expected in expected_metadata.items():
        observed = extraction.metadata.get(key)
        if observed != expected:
            findings.append(
                _finding(
                    code="metadata_mismatch",
                    message=f"Metadata {key!r} is {observed!r}, expected {expected!r}.",
                    anchor=f"metadata:{key}",
                    remediation_hint=f"Restore metadata {key!r} to the baseline value.",
                )
            )
    return findings


def _report(
    extraction: DocumentExtraction,
    *,
    baseline: ConformanceBaseline,
    artifact_id: str,
    findings: list[ValidationFinding],
    decision: ValidationDecision,
    readiness: ValidationReadiness,
    round_trip_passed: bool,
    render_passed: bool,
    security_passed: bool,
) -> PublicFormValidationReport:
    metrics = compute_public_form_metrics(extraction, baseline)
    return PublicFormValidationReport(
        report_id=f"validation-{artifact_id}-{baseline.template_id}",
        artifact_id=artifact_id,
        template_id=baseline.template_id,
        schema_id=baseline.schema_id,
        paragraph_block_f1=metrics.paragraph_block_f1,
        table_cell_f1=metrics.table_cell_f1,
        image_reference_f1=metrics.image_reference_f1,
        metadata_exact_match=metrics.metadata_exact_match,
        aggregate_score=metrics.aggregate_score,
        round_trip_passed=round_trip_passed,
        render_passed=render_passed,
        security_passed=security_passed,
        findings=findings,
        decision=decision,
        readiness=readiness,
    )


def _result(
    report: PublicFormValidationReport,
    *,
    status: ToolResultStatus,
    blocked_reason: BlockedReason | None,
    summary: str,
    correlation_id: str,
) -> DocumentToolResult:
    return DocumentToolResult(
        tool_id="document_validate_public_form",
        correlation_id=correlation_id,
        status=status,
        artifact_refs=[report.artifact_id],
        validation_report=report,
        findings=list(report.findings),
        text_summary=summary,
        blocked_reason=blocked_reason,
    )


def _decision(
    *,
    aggregate_score: Decimal,
    hard_failure: bool,
    round_trip_passed: bool,
    render_passed: bool,
    security_passed: bool,
) -> tuple[ValidationDecision, ValidationReadiness]:
    if not security_passed:
        return ValidationDecision.blocked, ValidationReadiness.blocked
    if hard_failure or not round_trip_passed or not render_passed:
        if not round_trip_passed or not render_passed:
            return ValidationDecision.needs_manual_review, ValidationReadiness.not_ready
        return ValidationDecision.fail, ValidationReadiness.not_ready
    if aggregate_score < Decimal("0.85"):
        return ValidationDecision.fail, ValidationReadiness.not_ready
    return ValidationDecision.pass_, ValidationReadiness.ready_for_review


def _combined_text(extraction: DocumentExtraction) -> str:
    parts = [paragraph.text for paragraph in extraction.paragraphs]
    parts.extend(cell.text for table in extraction.tables for cell in table.cells)
    parts.extend(field.label for field in extraction.fields)
    return "\n".join(parts)


def _finding(
    *,
    code: str,
    message: str,
    anchor: str,
    remediation_hint: str,
) -> ValidationFinding:
    digest = hashlib.sha256(f"{code}\0{anchor}\0{message}".encode()).hexdigest()[:12]
    return ValidationFinding(
        finding_id=f"validation-{code}-{digest}",
        severity="hard_failure",
        code=code,
        message=message,
        anchor=anchor,
        remediation_hint=remediation_hint,
    )
