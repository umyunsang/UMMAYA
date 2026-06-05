# SPDX-License-Identifier: Apache-2.0
"""Strict model tests for the Public AX document harness."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ummaya.tools.documents.models import (
    KNOWN_DOCUMENT_FORMAT_FAMILIES,
    PROMOTED_RUNTIME_DOCUMENT_FORMATS,
    ArtifactLineage,
    AutonomousFillPlan,
    BlockedReason,
    DocumentArtifact,
    DocumentExtraction,
    DocumentFormat,
    DocumentFormatFamily,
    DocumentIntent,
    DocumentIR,
    DocumentPatch,
    DocumentPatchOperation,
    DocumentProtectedRange,
    DocumentSecurityFinding,
    DocumentToolCall,
    DocumentToolResult,
    FormatCapabilityProfile,
    FormField,
    FormSlot,
    KnownDocumentFormat,
    OperationType,
    ParagraphBlock,
    PermissionState,
    PrimitiveName,
    PromotionCapability,
    PromotionGateResult,
    PromotionState,
    ProtectedRangeCategory,
    SecurityState,
    SourceAnchor,
    StyleDescriptor,
    ToolResultStatus,
    ValidationDecision,
    ValidationFinding,
)

NOW = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
SHA256 = "0" * 64


def test_known_document_formats_separate_all_format_classification_from_runtime_promotion() -> None:
    assert {document_format.value for document_format in DocumentFormat} == {
        "hwpx",
        "hwp",
        "owpml",
        "doc",
        "docx",
        "pdf",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "odt",
        "ods",
        "odp",
        "html",
        "htm",
        "txt",
        "rtf",
        "md",
        "epub",
        "csv",
        "tsv",
        "xml",
        "rdf",
        "ttl",
        "lod",
        "json",
        "jsonl",
        "yaml",
        "yml",
        "geojson",
        "gpx",
        "kml",
        "fasta",
        "sgml",
        "dtd",
        "py",
        "hml",
        "zip",
        "7z",
        "tar",
        "gz",
        "etc",
    }
    promoted_runtime_values = tuple(
        document_format.value for document_format in PROMOTED_RUNTIME_DOCUMENT_FORMATS
    )
    assert promoted_runtime_values == (
        "hwpx",
        "hwp",
        "owpml",
        "docx",
        "pdf",
        "xlsx",
        "pptx",
        "odt",
        "ods",
        "odp",
        "html",
        "htm",
        "txt",
        "rtf",
        "md",
        "epub",
        "csv",
        "tsv",
        "xml",
        "rdf",
        "ttl",
        "lod",
        "json",
        "jsonl",
        "yaml",
        "yml",
        "geojson",
        "gpx",
        "kml",
        "fasta",
        "sgml",
        "dtd",
        "py",
        "hml",
        "zip",
        "7z",
        "tar",
        "gz",
        "etc",
    )
    assert "doc" not in promoted_runtime_values
    assert "xls" not in promoted_runtime_values
    assert "ppt" not in promoted_runtime_values

    known_values = {known_format.value for known_format in KnownDocumentFormat}
    assert {
        "hwpx",
        "hwp",
        "hml",
        "owpml",
        "docx",
        "xlsx",
        "pptx",
        "doc",
        "xls",
        "ppt",
        "pdf",
        "pdfa",
        "odt",
        "ods",
        "odp",
        "html",
        "txt",
        "rtf",
        "md",
        "epub",
        "csv",
        "tsv",
        "xml",
        "rdf",
        "ttl",
        "lod",
        "json",
        "jsonl",
        "yaml",
        "yml",
        "geojson",
        "gpx",
        "kml",
        "fasta",
        "sgml",
        "dtd",
        "py",
        "png",
        "jpg",
        "jpeg",
        "gif",
        "tif",
        "tiff",
        "bmp",
        "webp",
        "shp",
        "shx",
        "dbf",
        "prj",
        "stl",
        "wav",
        "mp3",
        "mp4",
        "zip",
        "7z",
        "tar",
        "gz",
        "etc",
    }.issubset(known_values)

    assert KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.odt] is DocumentFormatFamily.odf
    assert KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.csv] is DocumentFormatFamily.data_file
    assert KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.ttl] is DocumentFormatFamily.data_file
    assert (
        KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.geojson]
        is DocumentFormatFamily.data_file
    )
    assert (
        KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.png] is DocumentFormatFamily.image_scan
    )
    assert (
        KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.gif] is DocumentFormatFamily.image_scan
    )
    assert (
        KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.shp]
        is DocumentFormatFamily.geospatial_data
    )
    assert (
        KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.mp4] is DocumentFormatFamily.media_asset
    )
    assert (
        KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.python] is DocumentFormatFamily.code_file
    )
    assert KNOWN_DOCUMENT_FORMAT_FAMILIES[KnownDocumentFormat.zip] is DocumentFormatFamily.archive


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


def test_document_ir_wraps_extraction_with_source_anchors_and_form_slots() -> None:
    extraction = DocumentExtraction(
        artifact_id="artifact-ir-001",
        paragraphs=[
            ParagraphBlock(
                block_id="paragraph-001",
                text="신청인 성명",
                source_path="/body/section[1]/p[1]",
            )
        ],
        fields=[
            FormField(
                field_id="applicant_name",
                label="신청인 성명",
                path="/body/section[1]/table[1]/cell[2,1]",
                field_type="text",
                required=True,
                current_value=None,
                source_confidence=Decimal("0.92"),
            )
        ],
    )

    document_ir = DocumentIR.from_extraction(
        artifact_id="artifact-ir-001",
        document_format=DocumentFormat.hwpx,
        extraction=extraction,
        engine_id="hwpx-package-text-adapter",
    )

    assert document_ir.document_format is DocumentFormat.hwpx
    assert document_ir.extraction is extraction
    assert document_ir.source_anchors[0].format_path == "/body/section[1]/p[1]"
    assert document_ir.source_anchors[0].engine_id == "hwpx-package-text-adapter"
    assert document_ir.form_slots[0].slot_id == "applicant_name"
    assert document_ir.form_slots[0].source_anchor.format_path == (
        "/body/section[1]/table[1]/cell[2,1]"
    )
    assert document_ir.form_slots[0].confidence == Decimal("0.92")


def test_source_anchor_and_autonomous_fill_plan_are_strict_and_review_safe() -> None:
    anchor = SourceAnchor(
        format_path="/body/section[1]/table[1]/cell[4,1]",
        page_number=1,
        bbox={
            "x": Decimal("10"),
            "y": Decimal("20"),
            "width": Decimal("120"),
            "height": Decimal("24"),
        },
        confidence=Decimal("0.90"),
        engine_id="hwpx-package-text-adapter",
    )
    slot = FormSlot(
        slot_id="consent_signature",
        label="서명",
        field_type="signature",
        required=True,
        protected=True,
        source_anchor=anchor,
        current_value=None,
        candidate_value="홍길동",
        confidence=Decimal("0.80"),
    )
    intent = DocumentIntent(
        intent_id="intent-001",
        operation="fill",
        instruction="문서 내용을 파악하고 알아서 작성해",
        confidence=Decimal("0.70"),
    )

    with pytest.raises(ValidationError, match="protected slots require human review"):
        AutonomousFillPlan(
            plan_id="plan-001",
            artifact_id="artifact-ir-001",
            intent=intent,
            slots=(slot,),
            requires_human_review=False,
            confidence=Decimal("0.70"),
        )

    plan = AutonomousFillPlan(
        plan_id="plan-001",
        artifact_id="artifact-ir-001",
        intent=intent,
        slots=(slot,),
        requires_human_review=True,
        confidence=Decimal("0.70"),
        blocked_slot_ids=("consent_signature",),
    )
    assert plan.blocked_slot_ids == ("consent_signature",)

    with pytest.raises(ValidationError, match="blocked_slot_ids must reference known slots"):
        AutonomousFillPlan(
            plan_id="plan-002",
            artifact_id="artifact-ir-001",
            intent=intent,
            slots=(slot,),
            requires_human_review=True,
            confidence=Decimal("0.70"),
            blocked_slot_ids=("unknown-slot",),
        )

    with pytest.raises(ValidationError, match="Input should be less than or equal to 1"):
        SourceAnchor(
            format_path="/body/section[1]/p[1]",
            confidence=Decimal("1.10"),
            engine_id="hwpx-package-text-adapter",
        )


def test_document_ir_carries_protected_ranges_for_sensitive_public_form_areas() -> None:
    anchor = SourceAnchor(
        format_path="/body/section[1]/table[1]/cell[5,2]",
        confidence=Decimal("0.96"),
        engine_id="hwpx-package-text-adapter",
    )
    protected_range = DocumentProtectedRange(
        range_id="range-resident-registration-number",
        category=ProtectedRangeCategory.identity_number,
        label="주민등록번호",
        source_anchor=anchor,
        reason="Identity numbers require explicit human review before mutation.",
    )
    document_ir = DocumentIR(
        artifact_id="artifact-ir-protected",
        document_format=DocumentFormat.hwpx,
        extraction=DocumentExtraction(artifact_id="artifact-ir-protected"),
        protected_ranges=(protected_range,),
    )

    assert document_ir.protected_ranges[0].category is ProtectedRangeCategory.identity_number
    assert document_ir.protected_ranges[0].blocked_operations == ("autonomous_fill",)

    with pytest.raises(ValidationError, match="protected ranges require human review"):
        DocumentProtectedRange(
            range_id="range-unsafe",
            category=ProtectedRangeCategory.bank_account,
            label="계좌번호",
            source_anchor=anchor,
            reason="Bank account values require review.",
            requires_human_review=False,
        )

    with pytest.raises(ValidationError, match="blocked_operations must not be empty"):
        DocumentProtectedRange(
            range_id="range-empty",
            category=ProtectedRangeCategory.signature,
            label="서명",
            source_anchor=anchor,
            reason="Signature fields require review.",
            blocked_operations=(),
        )


def test_document_ir_from_extraction_promotes_sensitive_fields_to_protected_ranges() -> None:
    extraction = DocumentExtraction(
        artifact_id="artifact-sensitive",
        fields=[
            FormField(
                field_id="resident_registration_number",
                label="주민등록번호",
                path="/body/section[1]/table[1]/cell[5,2]",
                field_type="text",
                required=True,
                current_value=None,
                source_confidence=Decimal("0.94"),
            )
        ],
    )

    document_ir = DocumentIR.from_extraction(
        artifact_id="artifact-sensitive",
        document_format=DocumentFormat.hwpx,
        extraction=extraction,
        engine_id="hwpx-package-text-adapter",
    )

    assert document_ir.form_slots[0].protected is True
    assert document_ir.protected_ranges[0].category is ProtectedRangeCategory.identity_number
    assert document_ir.protected_ranges[0].source_anchor.format_path == (
        "/body/section[1]/table[1]/cell[5,2]"
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


def test_promotion_gate_models_allow_style_capability_and_state() -> None:
    style_gate = PromotionGateResult(
        gate_id="gate-style",
        profile_id="profile-hwpx-style",
        capability=PromotionCapability.style,
        score_total=90,
        extraction_fidelity=20,
        write_fidelity=20,
        style_layout_control=15,
        deterministic_round_trip=15,
        public_form_validation=15,
        security_privacy=5,
        license_maintenance_tool_usability=0,
        hard_gates_passed=True,
        promotion_state=PromotionState.style_enabled,
        evidence_record_ids=["evidence-style-001"],
    )

    assert PromotionCapability("style") is PromotionCapability.style
    assert PromotionState("style_enabled") is PromotionState.style_enabled
    assert style_gate.capability is PromotionCapability.style
    assert style_gate.promotion_state is PromotionState.style_enabled

    with pytest.raises(ValidationError, match="style promotion requires score_total >= 85"):
        PromotionGateResult(
            gate_id="gate-style-low-score",
            profile_id="profile-hwpx-style",
            capability=PromotionCapability.style,
            score_total=84,
            extraction_fidelity=20,
            write_fidelity=20,
            style_layout_control=15,
            deterministic_round_trip=14,
            public_form_validation=10,
            security_privacy=5,
            license_maintenance_tool_usability=0,
            hard_gates_passed=True,
            promotion_state=PromotionState.style_enabled,
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
