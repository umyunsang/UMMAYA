# SPDX-License-Identifier: Apache-2.0
"""Strict model tests for the Public AX document harness."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ummaya.tools.documents.models import (
    ArtifactLineage,
    BlockedReason,
    DocumentArtifact,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    DocumentSecurityFinding,
    DocumentToolCall,
    DocumentToolResult,
    FormatCapabilityProfile,
    FormField,
    OperationType,
    PermissionState,
    PrimitiveName,
    PromotionCapability,
    PromotionGateResult,
    PromotionState,
    SecurityState,
    StyleDescriptor,
    ToolResultStatus,
    ValidationDecision,
    ValidationFinding,
)

NOW = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
SHA256 = "0" * 64


def test_document_artifact_is_strict_frozen_and_blocks_unknown_fields(tmp_path: Path) -> None:
    artifact = DocumentArtifact(
        artifact_id="artifact-001",
        session_id="session-001",
        source_path=tmp_path / "form.hwpx",
        display_name="form.hwpx",
        format=DocumentFormat.hwpx,
        mime_type="application/hwpx+zip",
        sha256=SHA256,
        byte_size=1024,
        expanded_byte_size=4096,
        created_at=NOW,
        lineage=ArtifactLineage.source,
        security_state=SecurityState.accepted,
    )

    assert artifact.source_path == (tmp_path / "form.hwpx").resolve()
    assert artifact.parent_artifact_id is None

    with pytest.raises(ValidationError, match="frozen"):
        artifact.display_name = "mutated.hwpx"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DocumentArtifact(
            artifact_id="artifact-001",
            session_id="session-001",
            source_path=tmp_path / "form.hwpx",
            display_name="form.hwpx",
            format=DocumentFormat.hwpx,
            mime_type="application/hwpx+zip",
            sha256=SHA256,
            byte_size=1024,
            expanded_byte_size=4096,
            created_at=NOW,
            lineage=ArtifactLineage.source,
            security_state=SecurityState.accepted,
            unsafe_extra=True,
        )

    with pytest.raises(ValidationError, match="Input should be a valid integer"):
        DocumentArtifact(
            artifact_id="artifact-001",
            session_id="session-001",
            source_path=tmp_path / "form.hwpx",
            display_name="form.hwpx",
            format=DocumentFormat.hwpx,
            mime_type="application/hwpx+zip",
            sha256=SHA256,
            byte_size="1024",
            expanded_byte_size=4096,
            created_at=NOW,
            lineage=ArtifactLineage.source,
            security_state=SecurityState.accepted,
        )


def test_document_artifact_enforces_lineage_and_security_invariants(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="Derivative artifacts require parent_artifact_id"):
        DocumentArtifact(
            artifact_id="artifact-derivative",
            session_id="session-001",
            source_path=tmp_path / "working.hwpx",
            display_name="working.hwpx",
            format=DocumentFormat.hwpx,
            mime_type="application/hwpx+zip",
            sha256=SHA256,
            byte_size=1024,
            expanded_byte_size=4096,
            created_at=NOW,
            lineage=ArtifactLineage.working_copy,
            security_state=SecurityState.accepted,
        )

    with pytest.raises(ValidationError, match="blocked artifacts require blocked_reason"):
        DocumentArtifact(
            artifact_id="artifact-blocked",
            session_id="session-001",
            source_path=tmp_path / "blocked.pdf",
            display_name="blocked.pdf",
            format=DocumentFormat.pdf,
            mime_type="application/pdf",
            sha256=SHA256,
            byte_size=1024,
            expanded_byte_size=1024,
            created_at=NOW,
            lineage=ArtifactLineage.source,
            security_state=SecurityState.blocked,
        )

    with pytest.raises(ValidationError, match="source artifacts cannot have parent_artifact_id"):
        DocumentArtifact(
            artifact_id="artifact-source",
            session_id="session-001",
            source_path=tmp_path / "source.docx",
            display_name="source.docx",
            format=DocumentFormat.docx,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            sha256=SHA256,
            byte_size=1024,
            expanded_byte_size=4096,
            created_at=NOW,
            lineage=ArtifactLineage.source,
            parent_artifact_id="parent-001",
            security_state=SecurityState.accepted,
        )


def test_style_and_field_models_reject_invalid_public_form_values() -> None:
    style = StyleDescriptor(
        style_id="style-001",
        target_path="/section[1]/paragraph[1]/run[1]",
        font_family="Noto Sans CJK KR",
        font_size_pt=Decimal("10.5"),
        bold=True,
        font_color_rgb="112233",
        alignment="center",
    )

    field = FormField(
        field_id="field-001",
        label="Applicant name",
        path="/section[1]/field[applicant_name]",
        field_type="text",
        required=True,
        current_value="홍길동",
        allowed_values=["홍길동", "김영희"],
        style_constraints=style,
        source_confidence=Decimal("0.95"),
    )

    assert field.current_value == "홍길동"
    assert field.style_constraints == style

    with pytest.raises(ValidationError, match="String should match pattern"):
        StyleDescriptor(
            style_id="style-002",
            target_path="/paragraph[1]",
            font_color_rgb="#112233",
        )

    with pytest.raises(ValidationError):
        FormField(
            field_id="field-002",
            label="Bad confidence",
            path="/field[bad]",
            field_type="text",
            required=False,
            source_confidence=Decimal("1.01"),
        )


def test_patch_models_preserve_ordered_operations_and_require_expected_format() -> None:
    patch = DocumentPatch(
        patch_id="patch-001",
        target_artifact_id="artifact-working",
        operations=[
            DocumentPatchOperation(
                operation_id="operation-001",
                operation_type=OperationType.set_field_value,
                target_path="/field[name]",
                value="홍길동",
            ),
            DocumentPatchOperation(
                operation_id="operation-002",
                operation_type=OperationType.set_paragraph_style,
                target_path="/paragraph[1]",
                style=StyleDescriptor(style_id="style-001", target_path="/paragraph[1]", bold=True),
            ),
        ],
        dry_run=False,
        expected_format=DocumentFormat.hwpx,
        destination_policy="working_copy",
    )

    assert [operation.operation_id for operation in patch.operations] == [
        "operation-001",
        "operation-002",
    ]

    with pytest.raises(ValidationError, match="List should have at least 1 item"):
        DocumentPatch(
            patch_id="patch-empty",
            target_artifact_id="artifact-working",
            operations=[],
            dry_run=True,
            expected_format=DocumentFormat.hwpx,
            destination_policy="working_copy",
        )


def test_promotion_gate_models_enforce_score_and_hwp_write_boundaries() -> None:
    read_gate = PromotionGateResult(
        gate_id="gate-read",
        profile_id="profile-hwpx",
        capability=PromotionCapability.read,
        score_total=80,
        extraction_fidelity=20,
        write_fidelity=5,
        style_layout_control=10,
        deterministic_round_trip=15,
        public_form_validation=15,
        security_privacy=10,
        license_maintenance_tool_usability=5,
        hard_gates_passed=True,
        promotion_state=PromotionState.read_only,
        evidence_record_ids=["evidence-001"],
    )

    assert read_gate.promotion_state is PromotionState.read_only

    with pytest.raises(ValidationError, match="write promotion requires score_total >= 85"):
        PromotionGateResult(
            gate_id="gate-write",
            profile_id="profile-hwpx",
            capability=PromotionCapability.write,
            score_total=84,
            extraction_fidelity=20,
            write_fidelity=19,
            style_layout_control=15,
            deterministic_round_trip=15,
            public_form_validation=15,
            security_privacy=10,
            license_maintenance_tool_usability=5,
            hard_gates_passed=True,
            promotion_state=PromotionState.write_enabled,
        )

    with pytest.raises(ValidationError, match="HWP binary write is blocked"):
        FormatCapabilityProfile(
            profile_id="profile-hwp",
            format=DocumentFormat.hwp,
            engine_name="legacy-hwp-reader",
            engine_version="0.1.0",
            license="unknown",
            runtime="python",
            supports_read=True,
            supports_extract=True,
            supports_write=True,
            supports_style=False,
            supports_render=False,
            supports_validation=False,
            last_evaluated_at=NOW,
        )


def test_extraction_validation_and_tool_envelopes_are_typed_and_joinable() -> None:
    finding = ValidationFinding(
        finding_id="finding-001",
        severity="hard_failure",
        code="missing_signature",
        message="Signature block is required.",
        anchor="/section[1]/table[2]/row[4]",
        remediation_hint="Fill the signature block before export.",
    )
    extraction = DocumentExtraction(
        artifact_id="artifact-001",
        paragraphs=[],
        tables=[],
        images=[],
        fields=[
            FormField(
                field_id="field-001",
                label="Applicant name",
                path="/field[name]",
                field_type="text",
                required=True,
                source_confidence=Decimal("0.9"),
            )
        ],
        metadata={"title": "Public form"},
        style_map=[],
        warnings=[],
    )
    tool_result = DocumentToolResult(
        tool_id="document_inspect",
        correlation_id="corr-001",
        status=ToolResultStatus.blocked,
        artifact_refs=["artifact-001"],
        extraction=extraction,
        findings=[
            DocumentSecurityFinding(
                finding_id="security-001",
                severity="blocked",
                code=BlockedReason.external_link_detected,
                message="External link detected.",
            ),
            finding,
        ],
        text_summary="Inspection blocked by security policy.",
        blocked_reason=BlockedReason.external_link_detected,
    )
    tool_call = DocumentToolCall(
        tool_id="document_inspect",
        primitive=PrimitiveName.check,
        correlation_id=tool_result.correlation_id,
        request={"artifact_id": "artifact-001"},
        permission_state=PermissionState.not_required,
    )

    assert tool_call.correlation_id == "corr-001"
    assert tool_result.findings[1].severity == "hard_failure"
    assert extraction.fields[0].field_id == "field-001"

    with pytest.raises(ValidationError, match="blocked results require blocked_reason"):
        DocumentToolResult(
            tool_id="document_inspect",
            correlation_id="corr-002",
            status=ToolResultStatus.blocked,
            text_summary="Blocked without reason.",
        )


def test_validation_report_security_failure_forces_blocked_decision() -> None:
    from ummaya.tools.documents.models import PublicFormValidationReport

    with pytest.raises(ValidationError, match="failed security check forces blocked decision"):
        PublicFormValidationReport(
            report_id="report-001",
            artifact_id="artifact-001",
            template_id="template-001",
            schema_id="schema-001",
            paragraph_block_f1=Decimal("0.90"),
            table_cell_f1=Decimal("0.90"),
            image_reference_f1=Decimal("0.90"),
            metadata_exact_match=Decimal("1.00"),
            aggregate_score=Decimal("0.90"),
            round_trip_passed=True,
            render_passed=True,
            security_passed=False,
            decision=ValidationDecision.pass_,
        )
