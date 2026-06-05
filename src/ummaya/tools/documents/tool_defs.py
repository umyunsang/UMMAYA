# SPDX-License-Identifier: Apache-2.0
"""Model-visible tool definitions for the Public AX document harness."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ummaya.tools.documents.contracts import (
    DocumentPermission,
    DocumentToolContract,
    DocumentToolId,
    load_document_tool_contracts,
)
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentFormat,
    DocumentToolResult,
    ScalarValue,
    StyleAlignment,
    StyleDescriptor,
    ToolResultStatus,
)
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool

DOCUMENT_TOOL_IDS = cast(tuple[DocumentToolId, ...], load_document_tool_contracts().tool_ids)
DOCUMENT_POLICY_URL = (
    "https://github.com/umyunsang/UMMAYA/blob/main/specs/2802-public-doc-harness/spec.md"
)
_POLICY_VERIFIED_AT = datetime(2026, 6, 1, tzinfo=UTC)


class DocumentToolRequestModel(BaseModel):
    """Base model for model-visible document tool requests."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class DocumentLocator(DocumentToolRequestModel):
    """Local document locator passed by the LLM tool loop."""

    path: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Absolute or relative local file path for first intake of a "
            "user-provided document. Use document.path when the user gives a "
            "local file path such as /Users/name/form.hwpx."
        ),
    )
    artifact_id: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Previously returned local artifact identifier from artifact_refs. "
            "Do not invent artifact_id values."
        ),
    )
    expected_format: DocumentFormat | None = Field(
        default=None,
        description="Expected document format used to fail closed on mismatched files.",
    )

    @model_validator(mode="after")
    def _require_path_or_artifact_id(self) -> DocumentLocator:
        if self.path is None and self.artifact_id is None:
            raise ValueError("document locator requires path or artifact_id")
        return self


class DocumentInspectRequest(DocumentToolRequestModel):
    """Inspect a local public-document artifact."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator


class DocumentExtractRequest(DocumentToolRequestModel):
    """Extract normalized document content for LLM reasoning."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator
    include_tables: bool
    include_images: bool
    include_fields: bool


class DocumentFormSchemaRequest(DocumentToolRequestModel):
    """Return fillable/inferred public-form fields."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator


class DocumentCopyForEditRequest(DocumentToolRequestModel):
    """Create a working derivative before mutation."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator
    reason: str | None = Field(default=None, max_length=300)


class DocumentFieldPatch(DocumentToolRequestModel):
    """One field/cell value mutation requested by the LLM."""

    target_path: str = Field(min_length=1)
    value: ScalarValue


class DocumentApplyFillRequest(DocumentToolRequestModel):
    """Apply ordered value patches to a working derivative."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator
    patches: tuple[DocumentFieldPatch, ...] = Field(min_length=1)
    dry_run: bool = False


class DocumentPrimitiveRequest(DocumentToolRequestModel):
    """Single model-facing public-document operation request."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator
    operation: Literal["inspect", "extract", "fill", "style", "validate", "save"] = Field(
        default="fill",
        description=(
            "Requested document operation. Normal document authoring uses fill or "
            "style; the primitive still performs inspect/copy/render internally. "
            "For write intents such as 'understand the document and complete it', "
            "'fill it in', 'update it', 'revise it', or Korean requests like "
            "'문서내용을 파악하고 알아서 작성해/수정해/채워줘', choose fill. Use "
            "extract only for explicitly read-only requests that ask to inspect, "
            "summarize, or extract content without changing the document."
        ),
    )
    instruction: str = Field(
        min_length=1,
        max_length=1200,
        description=(
            "Citizen-facing document task in natural language. Use this as the "
            "high-level edit/review intent; do not call document_inspect or "
            "document_render separately."
        ),
    )
    patches: tuple[DocumentFieldPatch, ...] = Field(
        default=(),
        description=(
            "Optional explicit field or text patches when the target path is known "
            "from the document schema or prior context."
        ),
    )
    styles: tuple[DocumentStylePatch, ...] = Field(
        default=(),
        description="Optional explicit bounded style patches.",
    )
    template_id: str | None = Field(
        default=None,
        min_length=1,
        description="Optional offline public-form baseline to validate after editing.",
    )
    destination_display_name: str | None = Field(
        default=None,
        min_length=1,
        description="Optional local export display name after review.",
    )
    destination_path: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Optional explicit local output path for a reviewed derivative. Use only "
            "when the user asks to save/export the completed document to a local path."
        ),
    )


class DocumentStylePatch(DocumentToolRequestModel):
    """One bounded style mutation requested by the LLM."""

    target_path: str = Field(min_length=1)
    font_family: str | None = None
    font_size_pt: Decimal | None = Field(default=None, gt=0)
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    font_color_rgb: str | None = Field(default=None, pattern=r"^[0-9A-Fa-f]{6}$")
    fill_color_rgb: str | None = Field(default=None, pattern=r"^[0-9A-Fa-f]{6}$")
    alignment: StyleAlignment | None = None

    def to_style_descriptor(self, *, style_id: str) -> StyleDescriptor:
        """Convert the request patch to the internal portable style descriptor."""
        return StyleDescriptor(
            style_id=style_id,
            target_path=self.target_path,
            font_family=self.font_family,
            font_size_pt=self.font_size_pt,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            font_color_rgb=self.font_color_rgb,
            fill_color_rgb=self.fill_color_rgb,
            alignment=self.alignment,
        )


class DocumentApplyStyleRequest(DocumentToolRequestModel):
    """Apply ordered style patches to a working derivative."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator
    styles: tuple[DocumentStylePatch, ...] = Field(min_length=1)
    dry_run: bool = False


class DocumentRenderRequest(DocumentToolRequestModel):
    """Render reviewer-readable local evidence for a derivative."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator
    page_limit: int | None = Field(default=None, ge=1)


class DocumentValidatePublicFormRequest(DocumentToolRequestModel):
    """Validate a derivative against an offline public-form baseline."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator
    template_id: str = Field(min_length=1)


class DocumentSaveRequest(DocumentToolRequestModel):
    """Save a reviewed derivative as a local export artifact."""

    correlation_id: str = Field(min_length=1)
    document: DocumentLocator
    destination_display_name: str = Field(min_length=1)
    destination_path: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Optional explicit local output path. If omitted, save remains an "
            "artifact-store export only."
        ),
    )


class DocumentInspectResult(DocumentToolResult):
    """Output schema for document inspection tools."""


class DocumentExtractionResult(DocumentToolResult):
    """Output schema for document extraction and form-schema tools."""


class DocumentMutationResult(DocumentToolResult):
    """Output schema for derivative-producing document tools."""


class DocumentPrimitiveResult(DocumentToolResult):
    """Output schema for the model-facing document primitive."""


class DocumentValidationResult(DocumentToolResult):
    """Output schema for public-form validation tools."""


_REQUEST_MODELS: dict[str, type[BaseModel]] = {
    "document": DocumentPrimitiveRequest,
    "document_inspect": DocumentInspectRequest,
    "document_extract": DocumentExtractRequest,
    "document_form_schema": DocumentFormSchemaRequest,
    "document_copy_for_edit": DocumentCopyForEditRequest,
    "document_apply_fill": DocumentApplyFillRequest,
    "document_apply_style": DocumentApplyStyleRequest,
    "document_render": DocumentRenderRequest,
    "document_validate_public_form": DocumentValidatePublicFormRequest,
    "document_save": DocumentSaveRequest,
}

_OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "document": DocumentPrimitiveResult,
    "document_inspect": DocumentInspectResult,
    "document_extract": DocumentExtractionResult,
    "document_form_schema": DocumentExtractionResult,
    "document_copy_for_edit": DocumentMutationResult,
    "document_apply_fill": DocumentMutationResult,
    "document_apply_style": DocumentMutationResult,
    "document_render": DocumentMutationResult,
    "document_validate_public_form": DocumentValidationResult,
    "document_save": DocumentMutationResult,
}

_DISPLAY_NAMES: dict[str, str] = {
    "document": "문서 작업",
    "document_inspect": "문서 검사",
    "document_extract": "문서 구조 추출",
    "document_form_schema": "공문서 양식 필드 조회",
    "document_copy_for_edit": "문서 편집본 생성",
    "document_apply_fill": "문서 값 입력",
    "document_apply_style": "문서 서식 적용",
    "document_render": "문서 렌더 증거 생성",
    "document_validate_public_form": "공문서 서식 검증",
    "document_save": "문서 저장",
}

_DESCRIPTIONS: dict[str, str] = {
    "document": (
        "Single document primitive for local public-document authoring and review. "
        "Use this one tool for HWPX, HWP, DOCX, PDF, XLSX, or PPTX document work. "
        "It internally performs inspect, schema/extraction, working-copy creation, "
        "fill/style mutation, render evidence, and automatic compact diff review. "
        "For local files pass document.path. Do not call locate for files. Do not "
        "call document_inspect, document_apply_fill, or document_render separately; "
        "those are internal stages, not the model-facing workflow. Do not call "
        "document_render separately after editing because automatic compact diff "
        "review is included in this tool result. Do not claim that a "
        "local/Downloads file is missing before this tool checks it; say only "
        "that you are checking the document location and contents first."
    ),
    "document_inspect": (
        "Inspect a local HWPX, HWP, DOCX, PDF, XLSX, or PPTX artifact through a "
        "promoted document engine. Returns artifact IDs, normalized structure, "
        "style/form cues, and fail-closed security findings without mutating bytes. "
        "For a user-provided local file path, call document_inspect first with "
        "document.path and optional expected_format. Do not call locate for "
        "files. Do not invent artifact_id values; only reuse artifact_refs "
        "returned by prior document tool results."
    ),
    "document_extract": (
        "Extract LLM-readable paragraphs, tables, images, fields, metadata, and styles "
        "from a previously inspected public-document artifact."
    ),
    "document_form_schema": (
        "Return the fillable or inferred public-form field schema so the model can "
        "prepare values before requesting a derivative write."
    ),
    "document_copy_for_edit": (
        "Create an immutable working copy before any fill or style operation. This "
        "tool writes only below the session artifact store and requires permission."
    ),
    "document_apply_fill": (
        "Apply ordered value patches to a working derivative through a promoted "
        "mutation engine while preserving protected form content."
    ),
    "document_apply_style": (
        "Apply bounded font, color, alignment, and cell/paragraph style patches "
        "through a promoted mutation engine."
    ),
    "document_render": (
        "Render reviewer-readable local evidence for generated derivatives and return "
        "hash-linked render artifact IDs."
    ),
    "document_validate_public_form": (
        "Validate a generated derivative against an offline public-form conformance "
        "baseline before it can be treated as ready for human review."
    ),
    "document_save": (
        "Save a reviewed derivative to a local export artifact without sending it to "
        "an external agency channel."
    ),
}

_TRIGGER_EXAMPLES: dict[str, list[str]] = {
    "document": [
        "HWPX 양식을 13주차 활동일지로 작성해줘",
        "공문서 파일을 채우고 내가 볼 수 있게 변경사항을 보여줘",
        "주민등록등본 양식의 성명 칸을 채워줘",
    ],
    "document_inspect": ["이 HWPX 공문서 읽어줘", "PDF 양식 구조 확인", "엑셀 민원 서식 검사"],
    "document_extract": ["문서 표와 필드 추출", "공문서 본문 읽기"],
    "document_form_schema": ["제출양식 입력칸 알려줘", "작성해야 할 필드 확인"],
    "document_copy_for_edit": ["편집본 만들어줘", "원본 건드리지 말고 복사본 생성"],
    "document_apply_fill": ["신청서에 값 입력", "양식 필드 채워줘"],
    "document_apply_style": ["폰트와 정렬 맞춰줘", "공문서 서식 적용"],
    "document_render": ["작성본을 렌더링해서 확인", "검토용 미리보기 생성"],
    "document_validate_public_form": ["제출 전 서식 검증", "공문서 규격 맞는지 확인"],
    "document_save": ["완성본 저장", "최종 제출 파일로 저장"],
}


def build_document_tool_definitions() -> tuple[GovAPITool, ...]:
    """Build all model-visible document harness tool definitions."""
    catalog = load_document_tool_contracts()
    return tuple(_build_tool(contract) for contract in catalog.tools)


def input_model_for_tool(tool_id: DocumentToolId) -> type[BaseModel]:
    """Return the Pydantic input model for a document tool contract."""
    return _REQUEST_MODELS[tool_id]


def permission_for_tool(tool_id: DocumentToolId) -> DocumentPermission:
    """Return the document artifact permission kind for a model-visible tool."""
    return load_document_tool_contracts().by_tool_id(tool_id).permission


def unsupported_document_tool_result(
    *,
    tool_id: str,
    correlation_id: str,
    message: str,
    artifact_refs: tuple[str, ...] = (),
    reason: BlockedReason = BlockedReason.unsupported_operation,
) -> DocumentToolResult:
    """Build a typed blocked result for unsupported document capabilities."""
    return DocumentToolResult(
        tool_id=tool_id,
        correlation_id=correlation_id,
        status=ToolResultStatus.blocked,
        artifact_refs=list(artifact_refs),
        text_summary=message,
        blocked_reason=reason,
    )


def needs_input_document_tool_result(
    *,
    tool_id: str,
    correlation_id: str,
    message: str,
    artifact_refs: tuple[str, ...] = (),
) -> DocumentToolResult:
    """Build a typed needs-input result for incomplete document tool calls."""
    return DocumentToolResult(
        tool_id=tool_id,
        correlation_id=correlation_id,
        status=ToolResultStatus.needs_input,
        artifact_refs=list(artifact_refs),
        text_summary=message,
    )


def _build_tool(contract: DocumentToolContract) -> GovAPITool:
    permission = contract.permission
    gate: Literal["read-only", "action"] = "action"
    auth_type: Literal["public", "oauth"] = "public" if gate == "read-only" else "oauth"
    tool_id = contract.tool_id
    return GovAPITool(
        id=tool_id,
        name_ko=_DISPLAY_NAMES[tool_id],
        ministry="UMMAYA",
        category=["document", "public_ax", permission, contract.primitive],
        endpoint=f"local://document-harness/{tool_id}",
        auth_type=auth_type,
        input_schema=_REQUEST_MODELS[tool_id],
        output_schema=_OUTPUT_MODELS[tool_id],
        search_hint=_search_hint(tool_id, contract),
        policy=AdapterRealDomainPolicy(
            real_classification_url=DOCUMENT_POLICY_URL,
            real_classification_text=(
                "UMMAYA local document artifact harness policy for session-scoped "
                "read, derivative write, validation, and export operations."
            ),
            citizen_facing_gate=gate,
            last_verified=_POLICY_VERIFIED_AT,
        ),
        adapter_mode="live",
        is_concurrency_safe=False,
        cache_ttl_seconds=0,
        rate_limit_per_minute=30,
        is_core=False,
        primitive=contract.primitive,
        llm_description=_DESCRIPTIONS[tool_id],
        trigger_examples=_TRIGGER_EXAMPLES[tool_id],
    )


def _search_hint(tool_id: DocumentToolId, contract: DocumentToolContract) -> str:
    return (
        f"문서 공문서 양식 서식 파일 {tool_id} {contract.permission} "
        "single document primitive automatic compact diff hwpx hwp docx pdf xlsx pptx "
        "public document harness form fill style render validate save local file path "
        "document.path do not call locate do not call document_inspect do not call "
        "document_apply_fill do not call document_render"
    )


__all__ = [
    "DOCUMENT_POLICY_URL",
    "DOCUMENT_TOOL_IDS",
    "DocumentApplyFillRequest",
    "DocumentApplyStyleRequest",
    "DocumentCopyForEditRequest",
    "DocumentExtractRequest",
    "DocumentFieldPatch",
    "DocumentFormSchemaRequest",
    "DocumentExtractionResult",
    "DocumentInspectResult",
    "DocumentPrimitiveRequest",
    "DocumentPrimitiveResult",
    "DocumentMutationResult",
    "DocumentInspectRequest",
    "DocumentLocator",
    "DocumentRenderRequest",
    "DocumentSaveRequest",
    "DocumentStylePatch",
    "DocumentValidationResult",
    "DocumentToolRequestModel",
    "DocumentValidatePublicFormRequest",
    "build_document_tool_definitions",
    "input_model_for_tool",
    "needs_input_document_tool_result",
    "permission_for_tool",
    "unsupported_document_tool_result",
]
