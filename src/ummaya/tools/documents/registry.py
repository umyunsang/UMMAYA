# SPDX-License-Identifier: Apache-2.0
"""Registry wiring and execution orchestration for document harness tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.baselines import (
    ConformanceBaselineCatalog,
    load_conformance_baselines,
)
from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
    build_default_document_engine_registry,
)
from ummaya.tools.documents.inspection import inspect_document
from ummaya.tools.documents.models import (
    ArtifactLineage,
    BlockedReason,
    DocumentArtifact,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    DocumentToolResult,
    OperationType,
    ToolResultStatus,
)
from ummaya.tools.documents.patch import apply_document_patch, copy_for_edit
from ummaya.tools.documents.render import render_document_evidence
from ummaya.tools.documents.tool_defs import (
    DOCUMENT_TOOL_IDS,
    DocumentApplyFillRequest,
    DocumentApplyStyleRequest,
    DocumentCopyForEditRequest,
    DocumentExtractRequest,
    DocumentFieldPatch,
    DocumentFormSchemaRequest,
    DocumentInspectRequest,
    DocumentRenderRequest,
    DocumentSaveRequest,
    DocumentStylePatch,
    DocumentValidatePublicFormRequest,
    build_document_tool_definitions,
    needs_input_document_tool_result,
    unsupported_document_tool_result,
)
from ummaya.tools.documents.validate import validate_public_form
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry


class DocumentToolRuntime:
    """Session-local runtime state for document harness tool execution."""

    def __init__(
        self,
        *,
        session_id: str = "default",
        artifact_root: str | Path | None = None,
        engine_registry: DocumentEngineRegistry | None = None,
        baseline_catalog: ConformanceBaselineCatalog | None = None,
    ) -> None:
        self.store = DocumentArtifactStore(session_id=session_id, root=artifact_root)
        self.engine_registry = engine_registry or build_default_document_engine_registry()
        self.baseline_catalog = baseline_catalog or load_conformance_baselines()
        self._artifacts: dict[str, DocumentArtifact] = {}
        self._extractions: dict[str, DocumentExtraction] = {}

    async def handle(self, tool_id: str, request: BaseModel) -> dict[str, Any]:
        """Dispatch one validated document tool request."""
        if tool_id == "document_inspect":
            result = self.inspect(cast(DocumentInspectRequest, request))
        elif tool_id == "document_extract":
            result = self.extract(cast(DocumentExtractRequest, request))
        elif tool_id == "document_form_schema":
            result = self.form_schema(cast(DocumentFormSchemaRequest, request))
        elif tool_id == "document_copy_for_edit":
            result = self.copy_for_edit(cast(DocumentCopyForEditRequest, request))
        elif tool_id == "document_apply_fill":
            result = self.apply_fill(cast(DocumentApplyFillRequest, request))
        elif tool_id == "document_apply_style":
            result = self.apply_style(cast(DocumentApplyStyleRequest, request))
        elif tool_id == "document_render":
            result = self.render(cast(DocumentRenderRequest, request))
        elif tool_id == "document_validate_public_form":
            result = self.validate_public_form(cast(DocumentValidatePublicFormRequest, request))
        elif tool_id == "document_save":
            result = self.save(cast(DocumentSaveRequest, request))
        else:
            result = unsupported_document_tool_result(
                tool_id=tool_id,
                correlation_id="unknown",
                message=f"Unknown document harness tool: {tool_id}.",
            )
        return result.model_dump(mode="json")

    def inspect(self, request: DocumentInspectRequest) -> DocumentToolResult:
        """Inspect and store a local source document artifact."""
        if request.document.path is None:
            artifact = self._artifact_by_id(request.document.artifact_id, request.correlation_id)
            if isinstance(artifact, DocumentToolResult):
                return artifact
            extraction = self._extraction_for_artifact(artifact, request.correlation_id)
            return DocumentToolResult(
                tool_id="document_inspect",
                correlation_id=request.correlation_id,
                status=ToolResultStatus.ok,
                artifact_refs=[artifact.artifact_id],
                extraction=extraction,
                text_summary="Document artifact is already available in the local harness store.",
            )

        result = inspect_document(
            request.document.path,
            expected_format=request.document.expected_format,
            engine_registry=self.engine_registry,
        )
        if result.status is not ToolResultStatus.ok:
            return DocumentToolResult(
                tool_id="document_inspect",
                correlation_id=request.correlation_id,
                status=result.status,
                artifact_refs=result.artifact_refs,
                extraction=result.extraction,
                findings=result.findings,
                text_summary=result.text_summary,
                blocked_reason=result.blocked_reason,
            )

        source_path = Path(request.document.path)
        document_format = request.document.expected_format
        if document_format is None:
            document_format = _format_from_extraction_or_suffix(result.extraction, source_path)
        artifact_id = _source_artifact_id(request.correlation_id)
        artifact = self.store.store_source(
            source_path,
            artifact_id=artifact_id,
            document_format=document_format,
            mime_type=_mime_for_format(document_format),
        )
        self._artifacts[artifact.artifact_id] = artifact
        if result.extraction is not None:
            self._extractions[artifact.artifact_id] = result.extraction

        return DocumentToolResult(
            tool_id="document_inspect",
            correlation_id=request.correlation_id,
            status=ToolResultStatus.ok,
            artifact_refs=[artifact.artifact_id],
            extraction=result.extraction,
            findings=result.findings,
            text_summary=result.text_summary,
        )

    def extract(self, request: DocumentExtractRequest) -> DocumentToolResult:
        """Return normalized extraction for a source or derivative artifact."""
        artifact = self._resolve_artifact_for_read(request.document, request.correlation_id)
        if isinstance(artifact, DocumentToolResult):
            return artifact
        extraction = self._extraction_for_artifact(artifact, request.correlation_id)
        if not request.include_tables:
            extraction = extraction.model_copy(update={"tables": []})
        if not request.include_images:
            extraction = extraction.model_copy(update={"images": []})
        if not request.include_fields:
            extraction = extraction.model_copy(update={"fields": []})
        return DocumentToolResult(
            tool_id="document_extract",
            correlation_id=request.correlation_id,
            status=ToolResultStatus.ok,
            artifact_refs=[artifact.artifact_id],
            extraction=extraction,
            text_summary="Document extraction returned normalized local content.",
        )

    def form_schema(self, request: DocumentFormSchemaRequest) -> DocumentToolResult:
        """Return fillable fields as the model-facing form schema."""
        artifact = self._resolve_artifact_for_read(request.document, request.correlation_id)
        if isinstance(artifact, DocumentToolResult):
            return artifact
        extraction = self._extraction_for_artifact(artifact, request.correlation_id)
        form_schema = DocumentExtraction(
            artifact_id=extraction.artifact_id,
            fields=extraction.fields,
            metadata=extraction.metadata,
            warnings=extraction.warnings,
        )
        return DocumentToolResult(
            tool_id="document_form_schema",
            correlation_id=request.correlation_id,
            status=ToolResultStatus.ok,
            artifact_refs=[artifact.artifact_id],
            extraction=form_schema,
            text_summary=f"Returned {len(form_schema.fields)} public-form field(s).",
        )

    def copy_for_edit(self, request: DocumentCopyForEditRequest) -> DocumentToolResult:
        """Create a working derivative for a source artifact."""
        source = self._resolve_artifact_for_read(request.document, request.correlation_id)
        if isinstance(source, DocumentToolResult):
            return source
        artifact_id = f"working-{request.correlation_id}"
        derivative = copy_for_edit(
            self.store,
            source,
            artifact_id=artifact_id,
            destination_name=f"{artifact_id}.{source.format.value}",
        )
        self._artifacts[derivative.artifact_id] = derivative
        self._extractions[derivative.artifact_id] = self._extraction_for_artifact(
            source,
            request.correlation_id,
        )
        return DocumentToolResult(
            tool_id="document_copy_for_edit",
            correlation_id=request.correlation_id,
            status=ToolResultStatus.ok,
            artifact_refs=[source.artifact_id, derivative.artifact_id],
            text_summary="Created a local working copy for document editing.",
        )

    def apply_fill(self, request: DocumentApplyFillRequest) -> DocumentToolResult:
        """Apply value patches to a working derivative."""
        working = self._resolve_artifact_for_write(request.document, request.correlation_id)
        if isinstance(working, DocumentToolResult):
            return working
        patch = _fill_patch(request, working)
        return self._apply_patch_result(
            tool_id="document_apply_fill",
            correlation_id=request.correlation_id,
            working=working,
            patch=patch,
        )

    def apply_style(self, request: DocumentApplyStyleRequest) -> DocumentToolResult:
        """Apply style patches to a working derivative."""
        working = self._resolve_artifact_for_write(request.document, request.correlation_id)
        if isinstance(working, DocumentToolResult):
            return working
        patch = _style_patch(request, working)
        return self._apply_patch_result(
            tool_id="document_apply_style",
            correlation_id=request.correlation_id,
            working=working,
            patch=patch,
        )

    def render(self, request: DocumentRenderRequest) -> DocumentToolResult:
        """Render local evidence for a document derivative."""
        artifact = self._resolve_artifact_for_read(request.document, request.correlation_id)
        if isinstance(artifact, DocumentToolResult):
            return artifact
        render_result = render_document_evidence(
            self.store,
            artifact,
            engine_registry=self.engine_registry,
            correlation_id=request.correlation_id,
            artifact_id_prefix=f"render-{request.correlation_id}",
        )
        blocked_reason = render_result.blocked_reason
        return DocumentToolResult(
            tool_id="document_render",
            correlation_id=request.correlation_id,
            status=render_result.status,
            artifact_refs=render_result.artifact_refs,
            text_summary=render_result.text_summary,
            blocked_reason=blocked_reason,
        )

    def validate_public_form(
        self,
        request: DocumentValidatePublicFormRequest,
    ) -> DocumentToolResult:
        """Validate one derivative against the offline conformance baseline catalog."""
        artifact = self._resolve_artifact_for_read(request.document, request.correlation_id)
        if isinstance(artifact, DocumentToolResult):
            return artifact
        try:
            baseline = self.baseline_catalog.by_template_id(request.template_id)
        except KeyError:
            return unsupported_document_tool_result(
                tool_id="document_validate_public_form",
                correlation_id=request.correlation_id,
                artifact_refs=(artifact.artifact_id,),
                message=f"Unknown public-form baseline: {request.template_id}.",
                reason=BlockedReason.validation_failed,
            )
        extraction = self._extraction_for_artifact(artifact, request.correlation_id)
        return validate_public_form(
            extraction,
            baseline=baseline,
            artifact_id=artifact.artifact_id,
            correlation_id=request.correlation_id,
        )

    def save(self, request: DocumentSaveRequest) -> DocumentToolResult:
        """Persist a reviewed derivative as an export artifact."""
        artifact = self._resolve_artifact_for_write(request.document, request.correlation_id)
        if isinstance(artifact, DocumentToolResult):
            return artifact
        payload = Path(artifact.source_path).read_bytes()
        export_artifact = self.store.write_derivative(
            artifact,
            artifact_id=f"export-{request.correlation_id}",
            lineage=ArtifactLineage.export,
            destination_name=request.destination_display_name,
            payload=payload,
        )
        self._artifacts[export_artifact.artifact_id] = export_artifact
        self._extractions[export_artifact.artifact_id] = self._extraction_for_artifact(
            artifact,
            request.correlation_id,
        )
        return DocumentToolResult(
            tool_id="document_save",
            correlation_id=request.correlation_id,
            status=ToolResultStatus.ok,
            artifact_refs=[artifact.artifact_id, export_artifact.artifact_id],
            text_summary="Saved local export artifact for human review or external handoff.",
        )

    def _apply_patch_result(
        self,
        *,
        tool_id: str,
        correlation_id: str,
        working: DocumentArtifact,
        patch: DocumentPatch,
    ) -> DocumentToolResult:
        result = apply_document_patch(
            self.store,
            working,
            patch,
            engine_registry=self.engine_registry,
            artifact_id=f"derivative-{correlation_id}",
            destination_name=f"derivative-{correlation_id}.{working.format.value}",
        )
        if result.status is not ToolResultStatus.ok or result.derivative_artifact is None:
            return DocumentToolResult(
                tool_id=tool_id,
                correlation_id=correlation_id,
                status=result.status,
                artifact_refs=[working.artifact_id],
                text_summary=result.text_summary,
                blocked_reason=result.blocked_reason or BlockedReason.unsupported_operation,
            )
        self._artifacts[result.derivative_artifact.artifact_id] = result.derivative_artifact
        self._extractions[result.derivative_artifact.artifact_id] = self._extraction_for_artifact(
            result.derivative_artifact,
            correlation_id,
        )
        return DocumentToolResult(
            tool_id=tool_id,
            correlation_id=correlation_id,
            status=ToolResultStatus.ok,
            artifact_refs=[working.artifact_id, result.derivative_artifact.artifact_id],
            text_summary=result.text_summary,
        )

    def _resolve_artifact_for_read(
        self,
        document: Any,
        correlation_id: str,
    ) -> DocumentArtifact | DocumentToolResult:
        if document.artifact_id is not None:
            return self._artifact_by_id(document.artifact_id, correlation_id)
        result = self.inspect(
            DocumentInspectRequest(correlation_id=correlation_id, document=document)
        )
        if result.status is not ToolResultStatus.ok or not result.artifact_refs:
            return result
        return self._artifact_by_id(result.artifact_refs[0], correlation_id)

    def _resolve_artifact_for_write(
        self,
        document: Any,
        correlation_id: str,
    ) -> DocumentArtifact | DocumentToolResult:
        artifact = self._resolve_artifact_for_read(document, correlation_id)
        if isinstance(artifact, DocumentToolResult):
            return artifact
        if artifact.lineage is ArtifactLineage.source:
            return unsupported_document_tool_result(
                tool_id="document_write_boundary",
                correlation_id=correlation_id,
                artifact_refs=(artifact.artifact_id,),
                message="Document writes require a working copy created by document_copy_for_edit.",
                reason=BlockedReason.permission_denied,
            )
        return artifact

    def _artifact_by_id(
        self,
        artifact_id: str | None,
        correlation_id: str,
    ) -> DocumentArtifact | DocumentToolResult:
        if artifact_id is None:
            return needs_input_document_tool_result(
                tool_id="document_artifact_lookup",
                correlation_id=correlation_id,
                message="artifact_id is required for this document tool call.",
            )
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return needs_input_document_tool_result(
                tool_id="document_artifact_lookup",
                correlation_id=correlation_id,
                artifact_refs=(artifact_id,),
                message=f"Unknown local document artifact: {artifact_id}.",
            )
        return artifact

    def _extraction_for_artifact(
        self,
        artifact: DocumentArtifact,
        correlation_id: str,
    ) -> DocumentExtraction:
        extraction = self._extractions.get(artifact.artifact_id)
        if extraction is not None:
            return extraction
        engine = self.engine_registry.require(artifact.format)
        extraction = engine.inspect(Path(artifact.source_path), artifact_id=correlation_id)
        self._extractions[artifact.artifact_id] = extraction
        return extraction


def register_document_tools(
    registry: ToolRegistry,
    executor: ToolExecutor,
    *,
    runtime: DocumentToolRuntime | None = None,
) -> None:
    """Register document harness tools and their executor adapters."""
    active_runtime = runtime or DocumentToolRuntime()
    for tool in build_document_tool_definitions():
        registry.register(tool)

        async def _adapter(inp: BaseModel, *, _tool_id: str = tool.id) -> dict[str, Any]:
            return await active_runtime.handle(_tool_id, inp)

        executor.register_adapter(tool.id, _adapter)


def _source_artifact_id(correlation_id: str) -> str:
    return f"source-{correlation_id}"


def _format_from_extraction_or_suffix(
    extraction: DocumentExtraction | None,
    source_path: Path,
) -> DocumentFormat:
    if extraction is not None and isinstance(extraction.metadata.get("format"), str):
        return _coerce_document_format(extraction.metadata["format"])
    return _coerce_document_format(source_path.suffix.lower().lstrip("."))


def _coerce_document_format(value: object) -> DocumentFormat:
    if isinstance(value, DocumentFormat):
        return value
    if isinstance(value, str):
        return DocumentFormat(value)
    raise ValueError(f"Unsupported document format value: {value!r}")


def _mime_for_format(document_format: Any) -> str:
    value = str(getattr(document_format, "value", document_format))
    return {
        "hwpx": "application/owpml",
        "hwp": "application/x-hwp",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(value, "application/octet-stream")


def _fill_patch(request: DocumentApplyFillRequest, working: DocumentArtifact) -> DocumentPatch:
    return DocumentPatch(
        patch_id=f"fill-{request.correlation_id}",
        target_artifact_id=working.artifact_id,
        operations=[
            _field_patch_operation(item, index=index)
            for index, item in enumerate(request.patches, start=1)
        ],
        dry_run=request.dry_run,
        expected_format=working.format,
        destination_policy="working_copy",
    )


def _style_patch(request: DocumentApplyStyleRequest, working: DocumentArtifact) -> DocumentPatch:
    return DocumentPatch(
        patch_id=f"style-{request.correlation_id}",
        target_artifact_id=working.artifact_id,
        operations=[
            _style_patch_operation(item, index=index)
            for index, item in enumerate(request.styles, start=1)
        ],
        dry_run=request.dry_run,
        expected_format=working.format,
        destination_policy="working_copy",
    )


def _field_patch_operation(item: DocumentFieldPatch, *, index: int) -> DocumentPatchOperation:
    return DocumentPatchOperation(
        operation_id=f"fill-{index:03d}",
        operation_type=OperationType.set_field_value,
        target_path=item.target_path,
        value=item.value,
    )


def _style_patch_operation(item: DocumentStylePatch, *, index: int) -> DocumentPatchOperation:
    return DocumentPatchOperation(
        operation_id=f"style-{index:03d}",
        operation_type=OperationType.set_paragraph_style,
        target_path=item.target_path,
        style=item.to_style_descriptor(style_id=f"style-{index:03d}"),
    )


__all__ = [
    "DOCUMENT_TOOL_IDS",
    "DocumentToolRuntime",
    "register_document_tools",
]
