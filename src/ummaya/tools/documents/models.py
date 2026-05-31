# SPDX-License-Identifier: Apache-2.0
"""Strict Pydantic models for the Public AX document harness."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class StrictDocumentModel(BaseModel):
    """Base model for immutable, schema-strict document harness entities."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class DocumentFormat(StrEnum):
    """Supported public-document artifact formats."""

    hwpx = "hwpx"
    hwp = "hwp"
    docx = "docx"
    pdf = "pdf"
    xlsx = "xlsx"
    pptx = "pptx"


class ArtifactLineage(StrEnum):
    """Artifact lifecycle category."""

    source = "source"
    working_copy = "working_copy"
    render = "render"
    validation_report = "validation_report"
    export = "export"


class SecurityState(StrEnum):
    """Pre-parse security decision for an artifact."""

    accepted = "accepted"
    blocked = "blocked"
    needs_manual_review = "needs_manual_review"


class BlockedReason(StrEnum):
    """Machine-readable blocked reasons shared by intake and tool results."""

    unsupported_format = "unsupported_format"
    extension_mismatch = "extension_mismatch"
    signature_mismatch = "signature_mismatch"
    mime_mismatch = "mime_mismatch"
    encrypted = "encrypted"
    corrupt = "corrupt"
    macro_detected = "macro_detected"
    external_link_detected = "external_link_detected"
    oversized_raw_bytes = "oversized_raw_bytes"
    oversized_expanded_bytes = "oversized_expanded_bytes"
    package_entry_limit_exceeded = "package_entry_limit_exceeded"
    path_traversal_detected = "path_traversal_detected"
    hidden_destination = "hidden_destination"
    public_root_destination = "public_root_destination"
    unsupported_operation = "unsupported_operation"
    validation_failed = "validation_failed"
    permission_denied = "permission_denied"


class PromotionCapability(StrEnum):
    """Capability evaluated by the format promotion gate."""

    read = "read"
    extract = "extract"
    write = "write"
    style = "style"
    render = "render"
    validate = "validate"


class PromotionState(StrEnum):
    """Model-visible capability state after scorecard evaluation."""

    blocked = "blocked"
    read_only = "read_only"
    write_enabled = "write_enabled"
    style_enabled = "style_enabled"


class OperationType(StrEnum):
    """Supported document patch operation kinds."""

    set_field_value = "set_field_value"
    set_table_cell = "set_table_cell"
    replace_text = "replace_text"
    insert_paragraph = "insert_paragraph"
    set_paragraph_style = "set_paragraph_style"
    set_run_style = "set_run_style"
    set_cell_style = "set_cell_style"
    set_document_metadata = "set_document_metadata"
    copy_for_edit = "copy_for_edit"


class PrimitiveName(Enum):
    """Existing UMMAYA root primitive family used by document tools."""

    find = "find"
    check = "check"
    send = "send"


class PermissionState(StrEnum):
    """Permission state attached to a document tool call."""

    not_required = "not_required"
    requested = "requested"
    approved = "approved"
    denied = "denied"


class ToolResultStatus(StrEnum):
    """Structured tool result status."""

    ok = "ok"
    blocked = "blocked"
    failed = "failed"
    needs_input = "needs_input"


class ValidationDecision(StrEnum):
    """Public-form conformance decision."""

    pass_ = "pass"  # noqa: S105 - public-form decision value, not a secret.
    fail = "fail"
    blocked = "blocked"
    needs_manual_review = "needs_manual_review"


class ValidationReadiness(StrEnum):
    """Machine-readable readiness state for validated public-form derivatives."""

    ready_for_review = "ready_for_review"
    not_ready = "not_ready"
    blocked = "blocked"
    unsupported = "unsupported"


type StyleAlignment = Literal["left", "center", "right", "justify", "distributed"]
type FieldType = Literal[
    "text",
    "number",
    "date",
    "choice",
    "checkbox",
    "signature",
    "attachment",
    "unknown",
]
type DestinationPolicy = Literal["working_copy", "export", "validation_only"]
type RuntimeKind = Literal[
    "python",
    "external_cli",
    "node_bridge",
    "rust_bridge",
    "manual_reference",
]
type SecurityFindingSeverity = Literal["blocked", "warning", "info"]
type ValidationFindingSeverity = Literal["hard_failure", "warning", "informational"]
type ScalarValue = str | int | Decimal | bool | date | datetime | None
type MetadataValue = str | int | Decimal | bool | date | datetime | None
type RequestScalar = str | int | float | bool | None
type RequestValue = RequestScalar | list[RequestScalar] | dict[str, RequestScalar]


class BorderDescriptor(StrictDocumentModel):
    """Portable border description for document styles."""

    style: str
    width_pt: Decimal | None = Field(default=None, gt=0)
    color_rgb: str | None = Field(default=None, pattern=r"^[0-9A-Fa-f]{6}$")


class StyleDescriptor(StrictDocumentModel):
    """Portable style representation shared by format adapters."""

    style_id: str
    target_path: str
    font_family: str | None = None
    font_size_pt: Decimal | None = Field(default=None, gt=0)
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    font_color_rgb: str | None = Field(default=None, pattern=r"^[0-9A-Fa-f]{6}$")
    fill_color_rgb: str | None = Field(default=None, pattern=r"^[0-9A-Fa-f]{6}$")
    alignment: StyleAlignment | None = None
    line_spacing: Decimal | None = Field(default=None, gt=0)
    border: BorderDescriptor | None = None
    number_format: str | None = None


class FormField(StrictDocumentModel):
    """Fillable or inferred public-form field."""

    field_id: str
    label: str
    path: str
    field_type: FieldType
    required: bool
    current_value: ScalarValue = None
    allowed_values: list[ScalarValue] = Field(default_factory=list)
    style_constraints: StyleDescriptor | None = None
    source_confidence: Decimal = Field(ge=0, le=1)


class DocumentArtifact(StrictDocumentModel):
    """User-provided source file or generated derivative metadata."""

    artifact_id: str
    session_id: str
    source_path: Path
    display_name: str
    format: DocumentFormat
    mime_type: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=0)
    expanded_byte_size: int = Field(ge=0)
    page_count: int | None = Field(default=None, ge=0)
    sheet_count: int | None = Field(default=None, ge=0)
    slide_count: int | None = Field(default=None, ge=0)
    section_count: int | None = Field(default=None, ge=0)
    created_at: datetime
    lineage: ArtifactLineage
    parent_artifact_id: str | None = None
    security_state: SecurityState
    blocked_reason: BlockedReason | None = None

    @field_validator("source_path")
    @classmethod
    def _canonicalize_source_path(cls, value: Path) -> Path:
        resolved = value.expanduser().resolve()
        if not resolved.is_absolute():
            raise ValueError("source_path must be absolute")
        return resolved

    @model_validator(mode="after")
    def _enforce_lineage_and_security(self) -> DocumentArtifact:
        if self.lineage is ArtifactLineage.source and self.parent_artifact_id is not None:
            raise ValueError("source artifacts cannot have parent_artifact_id")
        if self.lineage is not ArtifactLineage.source and self.parent_artifact_id is None:
            raise ValueError("Derivative artifacts require parent_artifact_id")
        if self.security_state is SecurityState.blocked and self.blocked_reason is None:
            raise ValueError("blocked artifacts require blocked_reason")
        if self.security_state is not SecurityState.blocked and self.blocked_reason is not None:
            raise ValueError("blocked_reason is only valid for blocked artifacts")
        return self


class ParagraphBlock(StrictDocumentModel):
    """Normalized paragraph block."""

    block_id: str
    text: str
    source_path: str
    style_id: str | None = None


class TableCell(StrictDocumentModel):
    """Normalized table cell with coordinate and span metadata."""

    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    text: str
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    source_path: str


class TableBlock(StrictDocumentModel):
    """Normalized table block."""

    block_id: str
    source_path: str
    cells: list[TableCell] = Field(default_factory=list)


class ImageReference(StrictDocumentModel):
    """Reference to embedded media in a document artifact."""

    image_id: str
    source_path: str
    content_type: str
    alt_text: str | None = None


class DocumentExtraction(StrictDocumentModel):
    """Normalized document content used by the LLM and validators."""

    artifact_id: str
    paragraphs: list[ParagraphBlock] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    images: list[ImageReference] = Field(default_factory=list)
    fields: list[FormField] = Field(default_factory=list)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    style_map: list[StyleDescriptor] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentPatchOperation(StrictDocumentModel):
    """One ordered mutation request against a working copy."""

    operation_id: str
    operation_type: OperationType
    target_path: str
    value: ScalarValue = None
    style: StyleDescriptor | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _enforce_operation_payload(self) -> DocumentPatchOperation:
        style_operations = {
            OperationType.set_paragraph_style,
            OperationType.set_run_style,
            OperationType.set_cell_style,
        }
        value_operations = {
            OperationType.set_field_value,
            OperationType.set_table_cell,
            OperationType.replace_text,
            OperationType.insert_paragraph,
            OperationType.set_document_metadata,
        }
        if self.operation_type in style_operations and self.style is None:
            raise ValueError("style operations require style")
        if self.operation_type in value_operations and self.value is None:
            raise ValueError("value operations require value")
        return self


class DocumentPatch(StrictDocumentModel):
    """Requested document write operation set."""

    patch_id: str
    target_artifact_id: str
    operations: list[DocumentPatchOperation] = Field(min_length=1)
    dry_run: bool
    expected_format: DocumentFormat
    destination_policy: DestinationPolicy


class FormatCapabilityProfile(StrictDocumentModel):
    """Observed support for one format and one engine."""

    profile_id: str
    format: DocumentFormat
    engine_name: str
    engine_version: str
    license: str
    runtime: RuntimeKind
    supports_read: bool
    supports_extract: bool
    supports_write: bool
    supports_style: bool
    supports_render: bool
    supports_validation: bool
    blocked_operations: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    fixture_results: list[str] = Field(default_factory=list)
    last_evaluated_at: datetime

    @model_validator(mode="after")
    def _enforce_hwp_write_boundary(self) -> FormatCapabilityProfile:
        if self.format is DocumentFormat.hwp and self.supports_write:
            raise ValueError("HWP binary write is blocked")
        return self


class PromotionGateResult(StrictDocumentModel):
    """Scorecard result controlling model-visible format capabilities."""

    gate_id: str
    profile_id: str
    capability: PromotionCapability
    score_total: int = Field(ge=0, le=100)
    extraction_fidelity: int = Field(ge=0, le=20)
    write_fidelity: int = Field(ge=0, le=20)
    style_layout_control: int = Field(ge=0, le=15)
    deterministic_round_trip: int = Field(ge=0, le=15)
    public_form_validation: int = Field(ge=0, le=15)
    security_privacy: int = Field(ge=0, le=10)
    license_maintenance_tool_usability: int = Field(ge=0, le=5)
    hard_gates_passed: bool
    hard_gate_failures: list[str] = Field(default_factory=list)
    promotion_state: PromotionState
    evidence_record_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_promotion_thresholds(self) -> PromotionGateResult:
        if self.hard_gate_failures and self.promotion_state is not PromotionState.blocked:
            raise ValueError("hard_gate_failures force blocked promotion_state")
        if not self.hard_gates_passed and self.promotion_state is not PromotionState.blocked:
            raise ValueError("failed hard gates force blocked promotion_state")
        if self.promotion_state is PromotionState.read_only and self.score_total < 75:
            raise ValueError("read-only promotion requires score_total >= 75")
        if (
            self.promotion_state
            in {
                PromotionState.write_enabled,
                PromotionState.style_enabled,
            }
            and self.score_total < 85
        ):
            raise ValueError("write promotion requires score_total >= 85")
        return self


class ValidationFinding(StrictDocumentModel):
    """Public-form validation finding."""

    finding_id: str
    severity: ValidationFindingSeverity
    code: str
    message: str
    anchor: str | None = None
    remediation_hint: str | None = None


class DocumentSecurityFinding(StrictDocumentModel):
    """Security finding emitted by document intake or processing."""

    finding_id: str
    severity: SecurityFindingSeverity
    code: BlockedReason
    message: str
    anchor: str | None = None


class DocumentIntakeResult(StrictDocumentModel):
    """Pre-parse intake result for one local document artifact."""

    tool_id: str
    correlation_id: str
    status: ToolResultStatus
    artifact_refs: list[str] = Field(default_factory=list)
    source_path: Path
    display_name: str
    detected_format: DocumentFormat | None = None
    expected_format: DocumentFormat | None = None
    declared_mime_type: str | None = None
    mime_type: str | None = None
    byte_size: int = Field(ge=0)
    expanded_byte_size: int = Field(ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    security_state: SecurityState
    blocked_reason: BlockedReason | None = None
    findings: list[DocumentSecurityFinding] = Field(default_factory=list)
    text_summary: str

    @field_validator("source_path")
    @classmethod
    def _canonicalize_source_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @model_validator(mode="after")
    def _enforce_blocked_reason(self) -> DocumentIntakeResult:
        if self.status is ToolResultStatus.blocked and self.blocked_reason is None:
            raise ValueError("blocked intake results require blocked_reason")
        if self.status is not ToolResultStatus.blocked and self.blocked_reason is not None:
            raise ValueError("blocked_reason is only valid for blocked intake results")
        if self.security_state is SecurityState.blocked and self.blocked_reason is None:
            raise ValueError("blocked security_state requires blocked_reason")
        return self


class PublicFormValidationReport(StrictDocumentModel):
    """Public-form conformance check report."""

    report_id: str
    artifact_id: str
    template_id: str
    schema_id: str
    paragraph_block_f1: Decimal = Field(ge=0, le=1)
    table_cell_f1: Decimal = Field(ge=0, le=1)
    image_reference_f1: Decimal = Field(ge=0, le=1)
    metadata_exact_match: Decimal = Field(ge=0, le=1)
    aggregate_score: Decimal = Field(ge=0, le=1)
    round_trip_passed: bool
    render_passed: bool
    security_passed: bool
    findings: list[ValidationFinding] = Field(default_factory=list)
    decision: ValidationDecision
    readiness: ValidationReadiness = ValidationReadiness.not_ready

    @model_validator(mode="after")
    def _enforce_decision_rules(self) -> PublicFormValidationReport:
        if not self.security_passed and self.decision is not ValidationDecision.blocked:
            raise ValueError("failed security check forces blocked decision")
        if self.decision is ValidationDecision.pass_ and self.aggregate_score < Decimal("0.85"):
            raise ValueError("pass decision requires aggregate_score >= 0.85")
        if self.decision is ValidationDecision.pass_ and not self.render_passed:
            raise ValueError("render mismatch prevents pass decision")
        if self.decision is ValidationDecision.pass_ and not self.round_trip_passed:
            raise ValueError("round-trip mismatch prevents pass decision")
        if (
            self.decision is ValidationDecision.pass_
            and self.readiness is not ValidationReadiness.ready_for_review
        ):
            raise ValueError("pass decision requires ready_for_review readiness")
        if (
            self.readiness is ValidationReadiness.ready_for_review
            and self.decision is not ValidationDecision.pass_
        ):
            raise ValueError("ready_for_review requires pass decision")
        return self


class DocumentToolCall(StrictDocumentModel):
    """Tool-loop input envelope for document capabilities."""

    tool_id: str
    primitive: PrimitiveName
    correlation_id: str
    request: dict[str, RequestValue]
    permission_state: PermissionState


class DocumentToolResult(StrictDocumentModel):
    """Tool-loop output envelope for document capabilities."""

    tool_id: str
    correlation_id: str
    status: ToolResultStatus
    artifact_refs: list[str] = Field(default_factory=list)
    extraction: DocumentExtraction | None = None
    validation_report: PublicFormValidationReport | None = None
    promotion_gate_result: PromotionGateResult | None = None
    findings: list[DocumentSecurityFinding | ValidationFinding] = Field(default_factory=list)
    text_summary: str
    blocked_reason: BlockedReason | None = None

    @model_validator(mode="after")
    def _enforce_blocked_reason(self) -> DocumentToolResult:
        if self.status is ToolResultStatus.blocked and self.blocked_reason is None:
            raise ValueError("blocked results require blocked_reason")
        if self.status is not ToolResultStatus.blocked and self.blocked_reason is not None:
            raise ValueError("blocked_reason is only valid for blocked results")
        return self

    @field_serializer("extraction", when_used="json")
    def _serialize_extraction_for_tool_output(
        self,
        extraction: DocumentExtraction | None,
    ) -> object | None:
        """Serialize extraction without raw local paths or document-byte markers."""
        if extraction is None:
            return None
        return _sanitize_model_visible_document_payload(extraction.model_dump(mode="json"))


_MODEL_VISIBLE_FORBIDDEN_KEYS = frozenset(
    {
        "document_bytes",
        "raw_bytes",
        "source_bytes",
        "source_path",
    }
)


def _sanitize_model_visible_document_payload(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            if key in _MODEL_VISIBLE_FORBIDDEN_KEYS:
                continue
            sanitized[key] = _sanitize_model_visible_document_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_model_visible_document_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_model_visible_document_payload(item) for item in value)
    if isinstance(value, str) and _looks_like_raw_document_payload(value):
        return "[redacted-document-content]"
    return value


def _looks_like_raw_document_payload(value: str) -> bool:
    lowered = value.lower()
    return (
        "%pdf" in lowered
        or "raw document bytes" in lowered
        or "/users/" in lowered
        or "\\users\\" in lowered
        or "-----begin " in lowered
    )
