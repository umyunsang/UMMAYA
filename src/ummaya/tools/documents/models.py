# SPDX-License-Identifier: Apache-2.0
"""Strict Pydantic models for the Public AX document harness."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import Path
from typing import Final, Literal

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
    owpml = "owpml"
    docx = "docx"
    doc = "doc"
    pdf = "pdf"
    xlsx = "xlsx"
    xls = "xls"
    pptx = "pptx"
    ppt = "ppt"
    odt = "odt"
    ods = "ods"
    odp = "odp"
    html = "html"
    htm = "htm"
    txt = "txt"
    rtf = "rtf"
    md = "md"
    epub = "epub"
    csv = "csv"
    tsv = "tsv"
    xml = "xml"
    rdf = "rdf"
    ttl = "ttl"
    lod = "lod"
    json = "json"
    jsonl = "jsonl"
    yaml = "yaml"
    yml = "yml"
    geojson = "geojson"
    gpx = "gpx"
    kml = "kml"
    fasta = "fasta"
    sgml = "sgml"
    dtd = "dtd"
    python = "py"
    hml = "hml"
    zip = "zip"
    seven_z = "7z"
    tar = "tar"
    gz = "gz"
    etc = "etc"


class KnownDocumentFormat(StrEnum):
    """Known national-infrastructure document families, promoted or blocked."""

    hwpx = "hwpx"
    hwp = "hwp"
    hml = "hml"
    owpml = "owpml"
    docx = "docx"
    xlsx = "xlsx"
    pptx = "pptx"
    doc = "doc"
    xls = "xls"
    ppt = "ppt"
    pdf = "pdf"
    pdfa = "pdfa"
    odt = "odt"
    ods = "ods"
    odp = "odp"
    html = "html"
    htm = "htm"
    txt = "txt"
    rtf = "rtf"
    md = "md"
    epub = "epub"
    csv = "csv"
    tsv = "tsv"
    xml = "xml"
    rdf = "rdf"
    ttl = "ttl"
    lod = "lod"
    json = "json"
    jsonl = "jsonl"
    yaml = "yaml"
    yml = "yml"
    geojson = "geojson"
    gpx = "gpx"
    kml = "kml"
    fasta = "fasta"
    sgml = "sgml"
    dtd = "dtd"
    python = "py"
    png = "png"
    jpg = "jpg"
    jpeg = "jpeg"
    gif = "gif"
    tif = "tif"
    tiff = "tiff"
    bmp = "bmp"
    webp = "webp"
    shp = "shp"
    shx = "shx"
    dbf = "dbf"
    prj = "prj"
    stl = "stl"
    wav = "wav"
    mp3 = "mp3"
    mp4 = "mp4"
    zip = "zip"
    seven_z = "7z"
    tar = "tar"
    gz = "gz"
    etc = "etc"


class DocumentFormatFamily(StrEnum):
    """Coarse document family used before adapter promotion."""

    hwp = "hwp"
    ooxml = "ooxml"
    legacy_office = "legacy_office"
    pdf = "pdf"
    odf = "odf"
    text_web_export = "text_web_export"
    data_file = "data_file"
    image_scan = "image_scan"
    geospatial_data = "geospatial_data"
    media_asset = "media_asset"
    code_file = "code_file"
    archive = "archive"


PROMOTED_RUNTIME_DOCUMENT_FORMATS: Final[tuple[DocumentFormat, ...]] = (
    DocumentFormat.hwpx,
    DocumentFormat.hwp,
    DocumentFormat.owpml,
    DocumentFormat.docx,
    DocumentFormat.pdf,
    DocumentFormat.xlsx,
    DocumentFormat.pptx,
    DocumentFormat.odt,
    DocumentFormat.ods,
    DocumentFormat.odp,
    DocumentFormat.html,
    DocumentFormat.htm,
    DocumentFormat.txt,
    DocumentFormat.rtf,
    DocumentFormat.md,
    DocumentFormat.epub,
    DocumentFormat.csv,
    DocumentFormat.tsv,
    DocumentFormat.xml,
    DocumentFormat.rdf,
    DocumentFormat.ttl,
    DocumentFormat.lod,
    DocumentFormat.json,
    DocumentFormat.jsonl,
    DocumentFormat.yaml,
    DocumentFormat.yml,
    DocumentFormat.geojson,
    DocumentFormat.gpx,
    DocumentFormat.kml,
    DocumentFormat.fasta,
    DocumentFormat.sgml,
    DocumentFormat.dtd,
    DocumentFormat.python,
    DocumentFormat.hml,
    DocumentFormat.zip,
    DocumentFormat.seven_z,
    DocumentFormat.tar,
    DocumentFormat.gz,
    DocumentFormat.etc,
)

KNOWN_DOCUMENT_FORMAT_FAMILIES: Final[dict[KnownDocumentFormat, DocumentFormatFamily]] = {
    KnownDocumentFormat.hwpx: DocumentFormatFamily.hwp,
    KnownDocumentFormat.hwp: DocumentFormatFamily.hwp,
    KnownDocumentFormat.hml: DocumentFormatFamily.data_file,
    KnownDocumentFormat.owpml: DocumentFormatFamily.hwp,
    KnownDocumentFormat.docx: DocumentFormatFamily.ooxml,
    KnownDocumentFormat.xlsx: DocumentFormatFamily.ooxml,
    KnownDocumentFormat.pptx: DocumentFormatFamily.ooxml,
    KnownDocumentFormat.doc: DocumentFormatFamily.legacy_office,
    KnownDocumentFormat.xls: DocumentFormatFamily.legacy_office,
    KnownDocumentFormat.ppt: DocumentFormatFamily.legacy_office,
    KnownDocumentFormat.pdf: DocumentFormatFamily.pdf,
    KnownDocumentFormat.pdfa: DocumentFormatFamily.pdf,
    KnownDocumentFormat.odt: DocumentFormatFamily.odf,
    KnownDocumentFormat.ods: DocumentFormatFamily.odf,
    KnownDocumentFormat.odp: DocumentFormatFamily.odf,
    KnownDocumentFormat.html: DocumentFormatFamily.text_web_export,
    KnownDocumentFormat.htm: DocumentFormatFamily.text_web_export,
    KnownDocumentFormat.txt: DocumentFormatFamily.text_web_export,
    KnownDocumentFormat.rtf: DocumentFormatFamily.text_web_export,
    KnownDocumentFormat.md: DocumentFormatFamily.text_web_export,
    KnownDocumentFormat.epub: DocumentFormatFamily.archive,
    KnownDocumentFormat.csv: DocumentFormatFamily.data_file,
    KnownDocumentFormat.tsv: DocumentFormatFamily.data_file,
    KnownDocumentFormat.xml: DocumentFormatFamily.data_file,
    KnownDocumentFormat.rdf: DocumentFormatFamily.data_file,
    KnownDocumentFormat.ttl: DocumentFormatFamily.data_file,
    KnownDocumentFormat.lod: DocumentFormatFamily.data_file,
    KnownDocumentFormat.json: DocumentFormatFamily.data_file,
    KnownDocumentFormat.jsonl: DocumentFormatFamily.data_file,
    KnownDocumentFormat.yaml: DocumentFormatFamily.data_file,
    KnownDocumentFormat.yml: DocumentFormatFamily.data_file,
    KnownDocumentFormat.geojson: DocumentFormatFamily.data_file,
    KnownDocumentFormat.gpx: DocumentFormatFamily.data_file,
    KnownDocumentFormat.kml: DocumentFormatFamily.data_file,
    KnownDocumentFormat.fasta: DocumentFormatFamily.data_file,
    KnownDocumentFormat.sgml: DocumentFormatFamily.data_file,
    KnownDocumentFormat.dtd: DocumentFormatFamily.data_file,
    KnownDocumentFormat.python: DocumentFormatFamily.code_file,
    KnownDocumentFormat.png: DocumentFormatFamily.image_scan,
    KnownDocumentFormat.jpg: DocumentFormatFamily.image_scan,
    KnownDocumentFormat.jpeg: DocumentFormatFamily.image_scan,
    KnownDocumentFormat.gif: DocumentFormatFamily.image_scan,
    KnownDocumentFormat.tif: DocumentFormatFamily.image_scan,
    KnownDocumentFormat.tiff: DocumentFormatFamily.image_scan,
    KnownDocumentFormat.bmp: DocumentFormatFamily.image_scan,
    KnownDocumentFormat.webp: DocumentFormatFamily.image_scan,
    KnownDocumentFormat.shp: DocumentFormatFamily.geospatial_data,
    KnownDocumentFormat.shx: DocumentFormatFamily.geospatial_data,
    KnownDocumentFormat.dbf: DocumentFormatFamily.geospatial_data,
    KnownDocumentFormat.prj: DocumentFormatFamily.geospatial_data,
    KnownDocumentFormat.stl: DocumentFormatFamily.geospatial_data,
    KnownDocumentFormat.wav: DocumentFormatFamily.media_asset,
    KnownDocumentFormat.mp3: DocumentFormatFamily.media_asset,
    KnownDocumentFormat.mp4: DocumentFormatFamily.media_asset,
    KnownDocumentFormat.zip: DocumentFormatFamily.archive,
    KnownDocumentFormat.seven_z: DocumentFormatFamily.archive,
    KnownDocumentFormat.tar: DocumentFormatFamily.archive,
    KnownDocumentFormat.gz: DocumentFormatFamily.archive,
    KnownDocumentFormat.etc: DocumentFormatFamily.data_file,
}


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
    static_pdf = "static_pdf"
    scanned_pdf = "scanned_pdf"
    xfa_detected = "xfa_detected"
    signature_detected = "signature_detected"
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


class PromotionChecklistStatus(StrEnum):
    """Promotion checklist status for deferred capabilities."""

    required = "required"
    passed = "passed"
    failed = "failed"


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


class DocumentWorkflowStepStatus(StrEnum):
    """Model-visible document workflow step state."""

    pending = "pending"
    completed = "completed"
    current = "current"
    blocked = "blocked"
    failed = "failed"
    skipped = "skipped"


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


class ProtectedRangeCategory(StrEnum):
    """Public-document ranges that require explicit review before mutation."""

    legal_text = "legal_text"
    consent = "consent"
    signature = "signature"
    seal = "seal"
    identity_number = "identity_number"
    address = "address"
    phone_number = "phone_number"
    bank_account = "bank_account"
    fixed_notice = "fixed_notice"
    health_data = "health_data"
    other_sensitive = "other_sensitive"


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
type DocumentIntentOperation = Literal[
    "inspect",
    "extract",
    "fill",
    "style",
    "validate",
    "save",
    "summarize",
]
type ProtectedRangeOperation = Literal[
    "autonomous_fill",
    "replace_text",
    "delete",
    "style",
    "send",
]
type DocumentViewportAnchorStrategy = Literal[
    "exact_text_run",
    "table_cell",
    "field_locator",
    "overlay_marker",
    "visual_bbox",
    "unavailable",
]
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


class DocumentSavedExport(StrictDocumentModel):
    """A reviewed derivative written to a user-visible local path."""

    export_artifact_id: str
    source_artifact_id: str
    local_path: Path | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=0)
    overwrite_existing: bool

    @field_validator("local_path")
    @classmethod
    def _canonicalize_local_path(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        resolved = value.expanduser().resolve()
        if not resolved.is_absolute():
            raise ValueError("local_path must be absolute")
        return resolved


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
    field_path: str | None = None


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


DocumentChangeType = Literal["field", "table_cell", "text", "style", "metadata", "copy"]


class DocumentChange(StrictDocumentModel):
    """One structured change derived from a document patch operation."""

    change_id: str
    operation_id: str
    change_type: DocumentChangeType
    target_path: str
    display_label: str | None = None
    before_value: str | None = None
    after_value: str | None = None


class RenderArtifactRecord(StrictDocumentModel):
    """One reviewer-readable render artifact tied to a derivative hash."""

    render_artifact_id: str
    source_artifact_id: str
    source_sha256: str
    render_sha256: str
    render_path: Path
    render_mime_type: str | None = None
    raster_artifact_ref: str | None = None
    raster_artifact_path: Path | None = None
    raster_mime_type: str | None = None
    page_number: int = Field(ge=1)
    correlation_id: str
    engine_id: str


class DocumentClipRect(StrictDocumentModel):
    """Page-coordinate rectangle for a document viewport crop."""

    x: Decimal = Field(ge=0)
    y: Decimal = Field(ge=0)
    width: Decimal = Field(gt=0)
    height: Decimal = Field(gt=0)


class DocumentChangedViewport(StrictDocumentModel):
    """Rendered page viewport focused on one or more structured document changes."""

    viewport_id: str
    change_ids: tuple[str, ...] = Field(min_length=1)
    page_number: int = Field(ge=1)
    source_render_artifact_id: str
    clip_rect: DocumentClipRect
    padding_x: Decimal = Field(default=Decimal("12"), ge=0)
    padding_y: Decimal = Field(default=Decimal("18"), ge=0)
    svg_artifact_ref: str | None = None
    svg_artifact_path: Path | None = None
    png_artifact_ref: str | None = None
    png_artifact_path: Path | None = None
    before_svg_artifact_ref: str | None = None
    before_svg_artifact_path: Path | None = None
    before_png_artifact_ref: str | None = None
    before_png_artifact_path: Path | None = None
    after_svg_artifact_ref: str | None = None
    after_svg_artifact_path: Path | None = None
    after_png_artifact_ref: str | None = None
    after_png_artifact_path: Path | None = None
    text_fallback: tuple[str, ...] = ()
    anchor_strategy: DocumentViewportAnchorStrategy
    confidence: Decimal = Field(ge=0, le=1)
    warnings: tuple[str, ...] = ()


class DocumentViewportCamera(StrictDocumentModel):
    """Viewport camera derived from full-page before/after render artifacts."""

    source_render_artifact_id: str
    baseline_render_artifact_id: str
    page_index: int = Field(ge=0)
    viewport_rect: DocumentClipRect
    zoom: Decimal = Field(default=Decimal("1"), gt=0)
    change_ids: tuple[str, ...] = Field(min_length=1)


class SourceAnchor(StrictDocumentModel):
    """Stable native-format and optional layout locator for document IR items."""

    format_path: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    sheet_index: int | None = Field(default=None, ge=0)
    slide_index: int | None = Field(default=None, ge=0)
    bbox: DocumentClipRect | None = None
    confidence: Decimal = Field(ge=0, le=1)
    engine_id: str = Field(min_length=1)


class FormSlot(StrictDocumentModel):
    """Planner-facing fillable slot anchored to native document structure."""

    slot_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    field_type: FieldType
    required: bool
    protected: bool = False
    source_anchor: SourceAnchor
    current_value: ScalarValue = None
    candidate_value: ScalarValue = None
    confidence: Decimal = Field(ge=0, le=1)
    evidence_text: str | None = None


class DocumentProtectedRange(StrictDocumentModel):
    """Native document span that the autonomous planner must not mutate silently."""

    range_id: str = Field(min_length=1)
    category: ProtectedRangeCategory
    label: str = Field(min_length=1)
    source_anchor: SourceAnchor
    reason: str = Field(min_length=1)
    blocked_operations: tuple[ProtectedRangeOperation, ...] = ("autonomous_fill",)
    requires_human_review: bool = True

    @model_validator(mode="after")
    def _enforce_protected_boundary(self) -> DocumentProtectedRange:
        if not self.blocked_operations:
            raise ValueError("blocked_operations must not be empty")
        if not self.requires_human_review:
            raise ValueError("protected ranges require human review")
        return self


class DocumentIntent(StrictDocumentModel):
    """Bounded natural-language intent inferred for autonomous document work."""

    intent_id: str = Field(min_length=1)
    operation: DocumentIntentOperation
    instruction: str = Field(min_length=1)
    confidence: Decimal = Field(ge=0, le=1)


class AutonomousStyleIntent(StrictDocumentModel):
    intent_id: str = Field(min_length=1)
    source_slot_id: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    style: StyleDescriptor
    confidence: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _enforce_style_target(self) -> AutonomousStyleIntent:
        if self.style.target_path != self.target_path:
            raise ValueError("style target_path must match AutonomousStyleIntent target_path")
        return self


class AutonomousSaveIntent(StrictDocumentModel):
    destination_path: str = Field(min_length=1)
    destination_display_name: str = Field(min_length=1)
    confidence: Decimal = Field(ge=0, le=1)


class AutonomousFillPlan(StrictDocumentModel):
    """Deterministic fill plan produced before any document mutation."""

    plan_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    intent: DocumentIntent
    slots: tuple[FormSlot, ...] = ()
    style_intents: tuple[AutonomousStyleIntent, ...] = ()
    save_intent: AutonomousSaveIntent | None = None
    blocked_slot_ids: tuple[str, ...] = ()
    requires_human_review: bool
    confidence: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _enforce_plan_safety(self) -> AutonomousFillPlan:
        slot_ids = {slot.slot_id for slot in self.slots}
        if len(slot_ids) != len(self.slots):
            raise ValueError("AutonomousFillPlan slot_id values must be unique")
        if set(self.blocked_slot_ids) - slot_ids:
            raise ValueError("blocked_slot_ids must reference known slots")
        slots_by_id = {slot.slot_id: slot for slot in self.slots}
        blocked_slot_ids = set(self.blocked_slot_ids)
        style_intent_ids = {style_intent.intent_id for style_intent in self.style_intents}
        if len(style_intent_ids) != len(self.style_intents):
            raise ValueError("AutonomousFillPlan style intent_id values must be unique")
        for style_intent in self.style_intents:
            source_slot = slots_by_id.get(style_intent.source_slot_id)
            if source_slot is None:
                raise ValueError("style_intents must reference known slots")
            if style_intent.source_slot_id in blocked_slot_ids or source_slot.protected:
                raise ValueError("style_intents must not reference protected or blocked slots")
            if style_intent.target_path != source_slot.source_anchor.format_path:
                raise ValueError("style_intents must target the source slot anchor")
        protected_edits = [
            slot for slot in self.slots if slot.protected and slot.candidate_value is not None
        ]
        if protected_edits and not self.requires_human_review:
            raise ValueError("protected slots require human review")
        return self


class DocumentIR(StrictDocumentModel):
    """Format-neutral structured document representation for planning."""

    artifact_id: str = Field(min_length=1)
    document_format: DocumentFormat
    extraction: DocumentExtraction
    source_anchors: tuple[SourceAnchor, ...] = ()
    form_slots: tuple[FormSlot, ...] = ()
    protected_ranges: tuple[DocumentProtectedRange, ...] = ()
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @classmethod
    def from_extraction(
        cls,
        *,
        artifact_id: str,
        document_format: DocumentFormat,
        extraction: DocumentExtraction,
        engine_id: str,
    ) -> DocumentIR:
        """Create an initial IR view from existing normalized extraction output."""
        anchors = _source_anchors_from_extraction(extraction, engine_id=engine_id)
        slots, protected_ranges = _field_slots_and_ranges_from_extraction(
            extraction,
            engine_id=engine_id,
        )
        inferred_slots, inferred_ranges = _inferred_slots_and_ranges_from_extraction(
            extraction,
            engine_id=engine_id,
            existing_paths={slot.source_anchor.format_path for slot in slots},
        )
        slots.extend(inferred_slots)
        protected_ranges.extend(inferred_ranges)

        return cls(
            artifact_id=artifact_id,
            document_format=document_format,
            extraction=extraction,
            source_anchors=tuple(anchors),
            form_slots=tuple(slots),
            protected_ranges=tuple(protected_ranges),
            metadata=extraction.metadata,
        )


def _source_anchors_from_extraction(
    extraction: DocumentExtraction,
    *,
    engine_id: str,
) -> list[SourceAnchor]:
    anchors: list[SourceAnchor] = []
    for paragraph in extraction.paragraphs:
        anchors.append(
            _source_anchor_for_path(
                paragraph.source_path,
                confidence=Decimal("1"),
                engine_id=engine_id,
            )
        )
    for table in extraction.tables:
        anchors.append(
            _source_anchor_for_path(
                table.source_path,
                confidence=Decimal("1"),
                engine_id=engine_id,
            )
        )
        for cell in table.cells:
            anchors.append(
                _source_anchor_for_path(
                    cell.field_path or cell.source_path,
                    confidence=Decimal("1"),
                    engine_id=engine_id,
                )
            )
    return anchors


def _field_slots_and_ranges_from_extraction(
    extraction: DocumentExtraction,
    *,
    engine_id: str,
) -> tuple[list[FormSlot], list[DocumentProtectedRange]]:
    slots: list[FormSlot] = []
    protected_ranges: list[DocumentProtectedRange] = []
    for field in extraction.fields:
        slot = _form_slot_from_field(field, engine_id=engine_id)
        slots.append(slot)
        protected_category = _protected_category_for_slot(slot)
        if protected_category is not None:
            protected_ranges.append(_protected_range_for_slot(slot, category=protected_category))
    return slots, protected_ranges


def _form_slot_from_field(field: FormField, *, engine_id: str) -> FormSlot:
    source_anchor = _source_anchor_for_path(
        field.path,
        confidence=field.source_confidence,
        engine_id=engine_id,
    )
    protected_category = _protected_range_category_for_text(
        field_type=field.field_type,
        identifier=field.field_id,
        label=field.label,
        path=field.path,
    )
    return FormSlot(
        slot_id=field.field_id,
        label=field.label,
        field_type=field.field_type,
        required=field.required,
        protected=protected_category is not None,
        source_anchor=source_anchor,
        current_value=field.current_value,
        confidence=field.source_confidence,
    )


def _inferred_slots_and_ranges_from_extraction(
    extraction: DocumentExtraction,
    *,
    engine_id: str,
    existing_paths: set[str],
) -> tuple[list[FormSlot], list[DocumentProtectedRange]]:
    slots: list[FormSlot] = []
    protected_ranges: list[DocumentProtectedRange] = []
    seen_slot_paths = set(existing_paths)
    inferred_slots = [
        *_table_slots_from_extraction(extraction, engine_id=engine_id),
        *_slide_text_slots_from_extraction(extraction, engine_id=engine_id),
    ]
    for slot in inferred_slots:
        if slot.source_anchor.format_path in seen_slot_paths:
            continue
        protected_slot, protected_range = _protect_slot_if_needed(slot)
        slots.append(protected_slot)
        seen_slot_paths.add(protected_slot.source_anchor.format_path)
        if protected_range is not None:
            protected_ranges.append(protected_range)
    return slots, protected_ranges


def _table_slots_from_extraction(
    extraction: DocumentExtraction,
    *,
    engine_id: str,
) -> list[FormSlot]:
    slots: list[FormSlot] = []
    for table_index, table in enumerate(extraction.tables):
        slots.extend(
            _table_slots_from_label_value_pairs(
                table,
                table_index=table_index,
                engine_id=engine_id,
            )
        )
    return slots


def _slide_text_slots_from_extraction(
    extraction: DocumentExtraction,
    *,
    engine_id: str,
) -> list[FormSlot]:
    slots: list[FormSlot] = []
    for paragraph_index, paragraph in enumerate(extraction.paragraphs):
        if not paragraph.source_path.startswith("/slides/"):
            continue
        slots.append(
            FormSlot(
                slot_id=f"slide_text_{paragraph_index + 1}",
                label="slide text",
                field_type="text",
                required=False,
                source_anchor=_source_anchor_for_path(
                    paragraph.source_path,
                    confidence=Decimal("0.80"),
                    engine_id=engine_id,
                ),
                current_value=paragraph.text,
                confidence=Decimal("0.80"),
            )
        )
    return slots


def _protect_slot_if_needed(
    slot: FormSlot,
) -> tuple[FormSlot, DocumentProtectedRange | None]:
    protected_category = _protected_category_for_slot(slot)
    if protected_category is None:
        return slot, None
    protected_slot = slot.model_copy(update={"protected": True})
    return (
        protected_slot,
        _protected_range_for_slot(protected_slot, category=protected_category),
    )


def _protected_category_for_slot(slot: FormSlot) -> ProtectedRangeCategory | None:
    return _protected_range_category_for_text(
        field_type=slot.field_type,
        identifier=slot.slot_id,
        label=slot.label,
        path=slot.source_anchor.format_path,
    )


def _table_slots_from_label_value_pairs(
    table: TableBlock,
    *,
    table_index: int,
    engine_id: str,
) -> list[FormSlot]:
    slots: list[FormSlot] = []
    rows: dict[int, list[TableCell]] = {}
    for cell in table.cells:
        rows.setdefault(cell.row_index, []).append(cell)
    for row_index, row_cells in sorted(rows.items()):
        ordered_cells = sorted(row_cells, key=lambda cell: cell.column_index)
        field_slots_added = False
        for value_cell in ordered_cells:
            if value_cell.field_path is None:
                continue
            label_cell = _nearest_left_table_label_cell(ordered_cells, value_cell)
            if label_cell is None:
                continue
            slots.append(
                _table_slot_from_label_value_cell(
                    label_cell.text.strip(),
                    value_cell,
                    table_index=table_index,
                    row_index=row_index,
                    engine_id=engine_id,
                )
            )
            field_slots_added = True
        if field_slots_added:
            continue
        for label_cell, value_cell in zip(ordered_cells, ordered_cells[1:], strict=False):
            label = label_cell.text.strip()
            if not _meaningful_table_slot_label(label):
                continue
            slots.append(
                _table_slot_from_label_value_cell(
                    label,
                    value_cell,
                    table_index=table_index,
                    row_index=row_index,
                    engine_id=engine_id,
                )
            )
            break
    return slots


def _nearest_left_table_label_cell(
    ordered_cells: list[TableCell],
    value_cell: TableCell,
) -> TableCell | None:
    left_cells = [
        candidate for candidate in ordered_cells if candidate.column_index < value_cell.column_index
    ]
    for candidate in reversed(left_cells):
        if _meaningful_table_slot_label(candidate.text.strip()):
            return candidate
    return None


def _meaningful_table_slot_label(label: str) -> bool:
    normalized = _normalized_protected_field_key(label)
    return len(normalized) >= 2


def _table_slot_from_label_value_cell(
    label: str,
    value_cell: TableCell,
    *,
    table_index: int,
    row_index: int,
    engine_id: str,
) -> FormSlot:
    value_path = value_cell.field_path or value_cell.source_path
    return FormSlot(
        slot_id=_form_slot_id_for_label(
            label,
            fallback=f"table_{table_index + 1}_{row_index + 1}_{value_cell.column_index + 1}",
        ),
        label=label,
        field_type="text",
        required=False,
        source_anchor=_source_anchor_for_path(
            value_path,
            confidence=Decimal("0.85"),
            engine_id=engine_id,
            sheet_index=table_index,
        ),
        current_value=value_cell.text,
        confidence=Decimal("0.85"),
    )


def _source_anchor_for_path(
    format_path: str,
    *,
    confidence: Decimal,
    engine_id: str,
    sheet_index: int | None = None,
) -> SourceAnchor:
    slide_index = _slide_index_for_path(format_path)
    resolved_sheet_index = sheet_index
    if resolved_sheet_index is None and format_path.startswith("/sheets/"):
        resolved_sheet_index = 0
    return SourceAnchor(
        format_path=format_path,
        sheet_index=resolved_sheet_index,
        slide_index=slide_index,
        confidence=confidence,
        engine_id=engine_id,
    )


def _slide_index_for_path(format_path: str) -> int | None:
    match = re.match(r"^/slides/(?P<slide_number>[0-9]+)(?:/|$)", format_path)
    if match is None:
        return None
    return max(int(match.group("slide_number")) - 1, 0)


def _form_slot_id_for_label(label: str, *, fallback: str) -> str:
    normalized = _normalized_protected_field_key(label)
    if normalized:
        return normalized
    return fallback


def _protected_range_for_slot(
    slot: FormSlot,
    *,
    category: ProtectedRangeCategory,
) -> DocumentProtectedRange:
    return DocumentProtectedRange(
        range_id=f"protected-{slot.slot_id}",
        category=category,
        label=slot.label,
        source_anchor=slot.source_anchor,
        reason=f"{slot.label} requires explicit human review before mutation.",
    )


def _protected_range_category_for_text(
    *,
    field_type: FieldType,
    identifier: str,
    label: str,
    path: str,
) -> ProtectedRangeCategory | None:
    field_key = _normalized_protected_field_key(f"{identifier} {label} {path}")
    if field_type == "signature" or any(token in field_key for token in ("서명", "signature")):
        return ProtectedRangeCategory.signature
    if any(token in field_key for token in ("동의", "consent")):
        return ProtectedRangeCategory.consent
    if any(
        token in field_key
        for token in (
            "성명",
            "이름",
            "신청인",
            "applicant",
            "주민등록",
            "identity",
            "residentregistration",
        )
    ):
        return ProtectedRangeCategory.identity_number
    if any(token in field_key for token in ("주소", "address")):
        return ProtectedRangeCategory.address
    if any(token in field_key for token in ("전화", "휴대폰", "phone", "mobile")):
        return ProtectedRangeCategory.phone_number
    if any(token in field_key for token in ("계좌", "은행", "bank", "account")):
        return ProtectedRangeCategory.bank_account
    if any(token in field_key for token in ("인감", "날인", "seal")):
        return ProtectedRangeCategory.seal
    if any(token in field_key for token in ("고지", "fixednotice", "notice")):
        return ProtectedRangeCategory.fixed_notice
    if any(token in field_key for token in ("진료", "건강", "health", "medical")):
        return ProtectedRangeCategory.health_data
    return None


def _normalized_protected_field_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


class DocumentDiff(StrictDocumentModel):
    """Diff between one working artifact and its derivative."""

    diff_id: str
    diff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resource_ref: str
    source_artifact_id: str
    derivative_artifact_id: str
    changes: tuple[DocumentChange, ...]
    render_artifacts: tuple[RenderArtifactRecord, ...] = ()
    baseline_render_artifacts: tuple[RenderArtifactRecord, ...] = ()
    changed_viewports: tuple[DocumentChangedViewport, ...] = ()
    viewport_cameras: tuple[DocumentViewportCamera, ...] = ()
    inline_truncated: bool = False
    omitted_change_count: int = Field(default=0, ge=0)


class DocumentWorkflowStep(StrictDocumentModel):
    """One visible step in the public-document authoring workflow."""

    step_id: str
    label: str
    status: DocumentWorkflowStepStatus
    artifact_id: str | None = None
    artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    detail: str | None = None


class PromotionChecklistItem(StrictDocumentModel):
    """One required evidence item before promoting a deferred capability."""

    check_id: str
    capability: PromotionCapability
    status: PromotionChecklistStatus
    evidence_required: str
    detail: str | None = None


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
    promotion_checklist: list[PromotionChecklistItem] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_promotion_thresholds(self) -> PromotionGateResult:
        if self.hard_gate_failures and self.promotion_state is not PromotionState.blocked:
            raise ValueError("hard_gate_failures force blocked promotion_state")
        if not self.hard_gates_passed and self.promotion_state is not PromotionState.blocked:
            raise ValueError("failed hard gates force blocked promotion_state")
        if self.promotion_state is PromotionState.read_only and self.score_total < 75:
            raise ValueError("read-only promotion requires score_total >= 75")
        if self.promotion_state is PromotionState.write_enabled and self.score_total < 85:
            raise ValueError("write promotion requires score_total >= 85")
        if self.promotion_state is PromotionState.style_enabled and self.score_total < 85:
            raise ValueError("style promotion requires score_total >= 85")
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
    known_format: KnownDocumentFormat | None = None
    format_family: DocumentFormatFamily | None = None
    expected_format: DocumentFormat | None = None
    declared_mime_type: str | None = None
    mime_type: str | None = None
    byte_size: int = Field(ge=0)
    expanded_byte_size: int = Field(ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    security_state: SecurityState
    blocked_reason: BlockedReason | None = None
    findings: list[DocumentSecurityFinding] = Field(default_factory=list)
    next_safe_actions: list[str] = Field(default_factory=list)
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
    diff: DocumentDiff | None = None
    render_artifacts: tuple[RenderArtifactRecord, ...] = ()
    saved_exports: tuple[DocumentSavedExport, ...] = ()
    workflow_steps: list[DocumentWorkflowStep] = Field(default_factory=list)
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
