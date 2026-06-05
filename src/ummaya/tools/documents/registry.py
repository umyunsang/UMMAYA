# SPDX-License-Identifier: Apache-2.0
"""Registry wiring and execution orchestration for document harness tools."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from ummaya.tools.documents.adapter_registry import (
    DocumentAdapterRegistry,
    build_document_adapter_registry_from_engine_registry,
)
from ummaya.tools.documents.artifact_store import ArtifactStoreError, DocumentArtifactStore
from ummaya.tools.documents.baselines import (
    ConformanceBaselineCatalog,
    load_conformance_baselines,
)
from ummaya.tools.documents.conversion import (
    DocumentConversionRegistry,
    UnsupportedDocumentConversionError,
    build_default_document_conversion_registry,
)
from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
    build_default_document_engine_registry,
)
from ummaya.tools.documents.formats.base import DocumentFormatAdapter
from ummaya.tools.documents.models import (
    ArtifactLineage,
    AutonomousFillPlan,
    BlockedReason,
    DocumentArtifact,
    DocumentDiff,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    DocumentSavedExport,
    DocumentToolResult,
    DocumentWorkflowStep,
    DocumentWorkflowStepStatus,
    OperationType,
    RenderArtifactRecord,
    ToolResultStatus,
)
from ummaya.tools.documents.orchestrator import (
    DocumentInspectionOrchestrator,
    DocumentOrchestrator,
)
from ummaya.tools.documents.patch import apply_document_patch, copy_for_edit
from ummaya.tools.documents.pdfa_conformance import (
    PdfaConformanceBridge,
    PdfaConformanceBridgeError,
    build_default_pdfa_conformance_bridge,
)
from ummaya.tools.documents.planner import plan_autonomous_fill
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
    DocumentLocator,
    DocumentPrimitiveRequest,
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

_DOCUMENT_STEM_NOISE_RE = re.compile(
    r"(?:hwpx|hwp|docx|pdf|xlsx|pptx|양식|서식|파일|문서)",
    re.IGNORECASE,
)
_EXPLICIT_LOCAL_DOCUMENT_PATH_RE = re.compile(
    r"(?:~|/|\.{1,2}/)[^\s\"'`<>|]+\.(?:hwpx|hwp|doc|docx|pdf|xls|xlsx|ppt|pptx)\b",
    re.IGNORECASE,
)
_DOCUMENT_SAVE_INTENT_RE = re.compile(r"(저장|내보내|export|save)", re.IGNORECASE)
_MIN_LOCAL_DOCUMENT_CANDIDATE_SCORE = 0.58
_COPY_FOR_EDIT_REASON_MAX_LENGTH = 300
_AUTONOMOUS_FILL_INSTRUCTION_RE = re.compile(
    r"(알아서|문서\s*내용|내용을\s*파악|다음\s*주차|autonomous|infer)",
    re.IGNORECASE,
)
_DOCX_TABLE_FILL_TARGET_RE = re.compile(
    r"(?:^|/)tables?/\d+/rows?/\d+/cells?/\d+$|(?:^|/)table/\d+/r\d+c\d+$"
)
_XLSX_CELL_FILL_TARGET_RE = re.compile(r"^/sheets/[^/]+/cells/[A-Za-z]{1,3}\d+$")
_PPTX_TABLE_FILL_TARGET_RE = re.compile(r"^/slides/\d+/tables/\d+/rows/\d+/cells/\d+$")
_HWPX_TABLE_CELL_SOURCE_RE = re.compile(
    r"^Contents/section[0-9]+\.xml#table\[[1-9][0-9]*\]/"
    r"r[1-9][0-9]*c[1-9][0-9]*$"
)
_EDITABLE_DERIVATIVE_FORMAT_BY_SOURCE: dict[DocumentFormat, DocumentFormat] = {
    DocumentFormat.hwp: DocumentFormat.hwpx,
    DocumentFormat.doc: DocumentFormat.docx,
    DocumentFormat.xls: DocumentFormat.xlsx,
    DocumentFormat.ppt: DocumentFormat.pptx,
}
_DERIVATIVE_LABEL_BY_FORMAT = {
    DocumentFormat.hwp: ("HWP", "HWPX"),
    DocumentFormat.doc: ("DOC", "DOCX"),
    DocumentFormat.xls: ("XLS", "XLSX"),
    DocumentFormat.ppt: ("PPT", "PPTX"),
}


class DocumentToolRuntime:
    """Session-local runtime state for document harness tool execution."""

    def __init__(
        self,
        *,
        session_id: str = "default",
        artifact_root: str | Path | None = None,
        engine_registry: DocumentEngineRegistry | None = None,
        adapter_registry: DocumentAdapterRegistry | None = None,
        conversion_registry: DocumentConversionRegistry | None = None,
        orchestrator: DocumentInspectionOrchestrator | None = None,
        baseline_catalog: ConformanceBaselineCatalog | None = None,
        pdfa_conformance_bridge: PdfaConformanceBridge | None = None,
        enable_default_pdfa_conformance_bridge: bool = True,
    ) -> None:
        self.store = DocumentArtifactStore(session_id=session_id, root=artifact_root)
        self.engine_registry = engine_registry or build_default_document_engine_registry()
        self.conversion_registry = (
            conversion_registry
            if conversion_registry is not None
            else build_default_document_conversion_registry()
        )
        self.adapter_registry = (
            adapter_registry
            or build_document_adapter_registry_from_engine_registry(self.engine_registry)
        )
        self.orchestrator = orchestrator or DocumentOrchestrator(
            adapter_registry=self.adapter_registry,
            engine_registry=self.engine_registry,
        )
        self.baseline_catalog = baseline_catalog or load_conformance_baselines()
        self.pdfa_conformance_bridge = (
            pdfa_conformance_bridge
            if pdfa_conformance_bridge is not None
            else (
                build_default_pdfa_conformance_bridge()
                if enable_default_pdfa_conformance_bridge
                else None
            )
        )
        self._artifacts: dict[str, DocumentArtifact] = {}
        self._extractions: dict[str, DocumentExtraction] = {}
        self._diffs_by_artifact_id: dict[str, DocumentDiff] = {}

    async def handle(self, tool_id: str, request: BaseModel) -> dict[str, Any]:  # noqa: C901
        """Dispatch one validated document tool request."""
        if tool_id == "document":
            result = self.document(cast(DocumentPrimitiveRequest, request))
        elif tool_id == "document_inspect":
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
        return self._with_runtime_workflow_steps(result).model_dump(mode="json")

    def document(self, request: DocumentPrimitiveRequest) -> DocumentToolResult:  # noqa: C901
        """Run one model-facing document operation through internal stages."""
        source_or_read = self._resolve_artifact_for_read(
            request.document,
            request.correlation_id,
            tool_id="document_inspect",
        )
        if isinstance(source_or_read, DocumentToolResult):
            if source_or_read.status is ToolResultStatus.ok and request.operation in {
                "inspect",
                "extract",
            }:
                return _with_workflow_steps(
                    source_or_read.model_copy(
                        update={
                            "tool_id": "document",
                            "correlation_id": request.correlation_id,
                        }
                    ),
                    artifacts=self._artifacts,
                )
            if (
                source_or_read.status is ToolResultStatus.ok
                and _is_attachment_context_extraction(source_or_read.extraction)
                and request.operation in {"fill", "save"}
            ):
                return self._attachment_context_derivative_result(request, source_or_read)
            if source_or_read.status is ToolResultStatus.ok:
                return unsupported_document_tool_result(
                    tool_id="document",
                    correlation_id=request.correlation_id,
                    artifact_refs=tuple(source_or_read.artifact_refs),
                    message=(
                        "Document format is known-only and read-only in the current "
                        "harness capability profile; mutation, render, and save are "
                        "not promoted for this artifact."
                    ),
                    reason=BlockedReason.unsupported_operation,
                )
            return _document_result_from_stage(
                source_or_read,
                correlation_id=request.correlation_id,
            )
        source = source_or_read

        if request.operation in {"inspect", "extract"}:
            extraction = self._extraction_for_artifact(source, request.correlation_id)
            return _with_workflow_steps(
                DocumentToolResult(
                    tool_id="document",
                    correlation_id=request.correlation_id,
                    status=ToolResultStatus.ok,
                    artifact_refs=[source.artifact_id],
                    extraction=extraction,
                    text_summary="Document inspection completed through the document primitive.",
                ),
                artifacts=self._artifacts,
            )

        mutation_result: DocumentToolResult | None = None
        working_artifact_id: str | None = None
        autonomous_plan: AutonomousFillPlan | None = None
        autonomous_save_path: str | None = None
        autonomous_save_display_name: str | None = None
        if request.operation == "style":
            if not request.styles:
                return needs_input_document_tool_result(
                    tool_id="document",
                    correlation_id=request.correlation_id,
                    artifact_refs=(source.artifact_id,),
                    message="Document style operation requires at least one bounded style patch.",
                )
            copy_result = self.copy_for_edit(
                DocumentCopyForEditRequest(
                    correlation_id=request.correlation_id,
                    document=DocumentLocator(artifact_id=source.artifact_id),
                    reason=_copy_for_edit_reason(request.instruction),
                )
            )
            if copy_result.status is not ToolResultStatus.ok:
                return _document_result_from_stage(
                    copy_result,
                    correlation_id=request.correlation_id,
                )
            working_artifact_id = copy_result.artifact_refs[-1]
            mutation_result = self.apply_style(
                DocumentApplyStyleRequest(
                    correlation_id=request.correlation_id,
                    document=DocumentLocator(artifact_id=working_artifact_id),
                    styles=request.styles,
                )
            )
        elif request.operation in {"fill", "validate", "save"}:
            planning_artifact = source
            if _editable_derivative_format(source.format) is not None:
                copy_result = self.copy_for_edit(
                    DocumentCopyForEditRequest(
                        correlation_id=request.correlation_id,
                        document=DocumentLocator(artifact_id=source.artifact_id),
                        reason=_copy_for_edit_reason(request.instruction),
                    )
                )
                if copy_result.status is not ToolResultStatus.ok:
                    return _document_result_from_stage(
                        copy_result,
                        correlation_id=request.correlation_id,
                    )
                working_artifact_id = copy_result.artifact_refs[-1]
                working_artifact = self._artifact_by_id(
                    working_artifact_id,
                    request.correlation_id,
                )
                if isinstance(working_artifact, DocumentToolResult):
                    return _document_result_from_stage(
                        working_artifact,
                        correlation_id=request.correlation_id,
                    )
                planning_artifact = working_artifact

            extraction = self._extraction_for_artifact(planning_artifact, request.correlation_id)
            candidate_patches = request.patches
            candidate_style_patches = request.styles
            if not candidate_patches or _should_prefer_autonomous_fill_plan(
                request.instruction,
                candidate_patches,
            ):
                document_ir = self.orchestrator.build_document_ir(
                    artifact_id=planning_artifact.artifact_id,
                    document_format=planning_artifact.format,
                    extraction=extraction,
                )
                autonomous_plan = plan_autonomous_fill(
                    document_ir,
                    instruction=request.instruction,
                )
                if autonomous_plan.requires_human_review:
                    return needs_input_document_tool_result(
                        tool_id="document",
                        correlation_id=request.correlation_id,
                        artifact_refs=(source.artifact_id,),
                        message=(
                            "Document autonomous fill requires human review for "
                            "blocked or missing slot(s): "
                            f"{', '.join(autonomous_plan.blocked_slot_ids)}."
                        ),
                    )
                candidate_patches = _fill_patches_from_autonomous_plan(autonomous_plan)
                if not candidate_style_patches:
                    candidate_style_patches = _style_patches_from_autonomous_plan(
                        autonomous_plan
                    )
                if autonomous_plan.save_intent is not None:
                    autonomous_save_path = autonomous_plan.save_intent.destination_path
                    autonomous_save_display_name = (
                        autonomous_plan.save_intent.destination_display_name
                    )
            if not candidate_patches:
                return needs_input_document_tool_result(
                    tool_id="document",
                    correlation_id=request.correlation_id,
                    artifact_refs=(source.artifact_id,),
                    message=(
                        "Document fill operation requires at least one explicit patch "
                        "or a safe autonomous fill plan."
                    ),
                )
            patches = _document_primitive_fill_patches(
                candidate_patches,
                adapter=self.adapter_registry.require_promoted(planning_artifact.format),
                extraction=extraction,
            )
            if not patches:
                return needs_input_document_tool_result(
                    tool_id="document",
                    correlation_id=request.correlation_id,
                    artifact_refs=(source.artifact_id,),
                    message=(
                        "Document fill operation could not map any natural-language patch "
                        "target to extracted document fields."
                    ),
                )
            if working_artifact_id is None:
                copy_result = self.copy_for_edit(
                    DocumentCopyForEditRequest(
                        correlation_id=request.correlation_id,
                        document=DocumentLocator(artifact_id=source.artifact_id),
                        reason=_copy_for_edit_reason(request.instruction),
                    )
                )
                if copy_result.status is not ToolResultStatus.ok:
                    return _document_result_from_stage(
                        copy_result,
                        correlation_id=request.correlation_id,
                    )
                working_artifact_id = copy_result.artifact_refs[-1]
            working_artifact = self._artifact_by_id(
                working_artifact_id,
                request.correlation_id,
            )
            if isinstance(working_artifact, DocumentToolResult):
                return _document_result_from_stage(
                    working_artifact,
                    correlation_id=request.correlation_id,
                )
            mutation_result = self._apply_patch_result(
                tool_id="document_apply_fill",
                correlation_id=request.correlation_id,
                working=working_artifact,
                patch=_fill_style_patch(
                    correlation_id=request.correlation_id,
                    patches=patches,
                    styles=candidate_style_patches,
                    working=working_artifact,
                ),
            )

        if mutation_result is None:
            artifact_refs: tuple[str, ...] = (source.artifact_id,)
            if working_artifact_id is not None:
                artifact_refs = (source.artifact_id, working_artifact_id)
            return unsupported_document_tool_result(
                tool_id="document",
                correlation_id=request.correlation_id,
                artifact_refs=artifact_refs,
                message=f"Unsupported document primitive operation: {request.operation}.",
            )
        if working_artifact_id is None:
            return unsupported_document_tool_result(
                tool_id="document",
                correlation_id=request.correlation_id,
                artifact_refs=(source.artifact_id,),
                message="Document mutation did not create a working copy.",
            )
        if mutation_result.status is not ToolResultStatus.ok:
            return _document_result_from_stage(
                mutation_result,
                correlation_id=request.correlation_id,
            )
        derivative_artifact_id = mutation_result.artifact_refs[-1]

        render_result = self.render(
            DocumentRenderRequest(
                correlation_id=request.correlation_id,
                document=DocumentLocator(artifact_id=derivative_artifact_id),
            )
        )
        if render_result.status is not ToolResultStatus.ok:
            return _document_result_from_stage(render_result, correlation_id=request.correlation_id)

        render_artifact_refs = _unique_artifact_refs(
            [source.artifact_id, working_artifact_id, *render_result.artifact_refs]
        )
        result = render_result.model_copy(
            update={
                "tool_id": "document",
                "artifact_refs": render_artifact_refs,
                "text_summary": (
                    "Document edit completed with automatic compact diff review evidence."
                ),
            }
        )

        if request.template_id is not None:
            validation_result = self.validate_public_form(
                DocumentValidatePublicFormRequest(
                    correlation_id=request.correlation_id,
                    document=DocumentLocator(artifact_id=derivative_artifact_id),
                    template_id=request.template_id,
                )
            )
            result = result.model_copy(
                update={"validation_report": validation_result.validation_report}
            )

        destination_path = (
            request.destination_path
            or autonomous_save_path
            or _explicit_save_path_from_instruction(
                request.instruction,
                source_artifact=source,
            )
        )
        if request.destination_display_name is not None or destination_path is not None:
            destination_display_name = (
                request.destination_display_name or autonomous_save_display_name
            )
            if destination_display_name is None:
                destination_display_name = Path(cast(str, destination_path)).name
            save_result = self.save(
                DocumentSaveRequest(
                    correlation_id=request.correlation_id,
                    document=DocumentLocator(artifact_id=derivative_artifact_id),
                    destination_display_name=destination_display_name,
                    destination_path=destination_path,
                )
            )
            if save_result.status is not ToolResultStatus.ok:
                return _document_result_from_stage(
                    save_result,
                    correlation_id=request.correlation_id,
                )
            result = result.model_copy(
                update={
                    "artifact_refs": _unique_artifact_refs(
                        [*result.artifact_refs, *save_result.artifact_refs]
                    ),
                    "saved_exports": save_result.saved_exports,
                    "workflow_steps": _merge_save_workflow_steps(
                        result.workflow_steps,
                        save_result.workflow_steps,
                    ),
                }
            )
        return result

    def inspect(self, request: DocumentInspectRequest) -> DocumentToolResult:
        """Inspect and store a local source document artifact."""
        locator_guard = self._ambiguous_locator_result(
            request.document,
            request.correlation_id,
            tool_id="document_inspect",
        )
        if locator_guard is not None:
            return locator_guard

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

        source_path = Path(request.document.path).expanduser()
        if not source_path.is_file():
            return _missing_local_document_result(
                source_path,
                correlation_id=request.correlation_id,
                tool_id="document_inspect",
                expected_format=request.document.expected_format,
            )

        result = self.orchestrator.inspect_local_path(
            source_path,
            expected_format=request.document.expected_format,
            correlation_id=request.correlation_id,
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

        document_format = request.document.expected_format
        if document_format is None:
            try:
                document_format = _format_from_extraction_or_suffix(result.extraction, source_path)
            except ValueError:
                return DocumentToolResult(
                    tool_id="document_inspect",
                    correlation_id=request.correlation_id,
                    status=ToolResultStatus.ok,
                    artifact_refs=[],
                    extraction=result.extraction,
                    findings=result.findings,
                    text_summary=result.text_summary,
                )
        artifact_id = _source_artifact_id(request.correlation_id)
        source_artifact = self._source_artifact_for_inspected_path(
            artifact_id=artifact_id,
            source_path=source_path,
            document_format=document_format,
            correlation_id=request.correlation_id,
        )
        if isinstance(source_artifact, DocumentToolResult):
            return source_artifact
        self._artifacts[source_artifact.artifact_id] = source_artifact
        if result.extraction is not None:
            self._extractions[source_artifact.artifact_id] = result.extraction

        return DocumentToolResult(
            tool_id="document_inspect",
            correlation_id=request.correlation_id,
            status=ToolResultStatus.ok,
            artifact_refs=[source_artifact.artifact_id],
            extraction=result.extraction,
            findings=result.findings,
            text_summary=result.text_summary,
        )

    def extract(self, request: DocumentExtractRequest) -> DocumentToolResult:
        """Return normalized extraction for a source or derivative artifact."""
        artifact = self._resolve_artifact_for_read(
            request.document,
            request.correlation_id,
            tool_id="document_extract",
        )
        if isinstance(artifact, DocumentToolResult):
            if artifact.status is ToolResultStatus.ok and artifact.extraction is not None:
                extraction = _filtered_extraction(
                    artifact.extraction,
                    include_tables=request.include_tables,
                    include_images=request.include_images,
                    include_fields=request.include_fields,
                )
                return DocumentToolResult(
                    tool_id="document_extract",
                    correlation_id=request.correlation_id,
                    status=ToolResultStatus.ok,
                    artifact_refs=artifact.artifact_refs,
                    extraction=extraction,
                    text_summary=(
                        "Document extraction returned normalized known-only local content."
                    ),
                )
            return artifact
        extraction = self._extraction_for_artifact(artifact, request.correlation_id)
        extraction = _filtered_extraction(
            extraction,
            include_tables=request.include_tables,
            include_images=request.include_images,
            include_fields=request.include_fields,
        )
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
        artifact = self._resolve_artifact_for_read(
            request.document,
            request.correlation_id,
            tool_id="document_form_schema",
        )
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
        source = self._resolve_artifact_for_read(
            request.document,
            request.correlation_id,
            tool_id="document_copy_for_edit",
        )
        if isinstance(source, DocumentToolResult):
            return source
        derivative_format = _editable_derivative_format(source.format)
        if derivative_format is not None:
            return self._copy_source_for_edit_as_derivative(
                source,
                request,
                derivative_format=derivative_format,
            )
        artifact_id = _generated_artifact_id("working", request.correlation_id)
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

    def _copy_source_for_edit_as_derivative(
        self,
        source: DocumentArtifact,
        request: DocumentCopyForEditRequest,
        *,
        derivative_format: DocumentFormat,
    ) -> DocumentToolResult:
        source_label, derivative_label = _conversion_labels(source.format, derivative_format)
        try:
            engine = self.conversion_registry.require(source.format, derivative_format)
        except UnsupportedDocumentConversionError:
            return unsupported_document_tool_result(
                tool_id="document_copy_for_edit",
                correlation_id=request.correlation_id,
                artifact_refs=(source.artifact_id,),
                message=_conversion_missing_message(
                    source_format=source.format,
                    derivative_format=derivative_format,
                    source_label=source_label,
                    derivative_label=derivative_label,
                ),
            )
        artifact_id = _generated_artifact_id("working", request.correlation_id)
        try:
            payload = engine.convert_for_edit(source)
        except ValueError as exc:
            return unsupported_document_tool_result(
                tool_id="document_copy_for_edit",
                correlation_id=request.correlation_id,
                artifact_refs=(source.artifact_id,),
                message=f"{source_label} to {derivative_label} conversion failed validation: {exc}",
                reason=BlockedReason.validation_failed,
            )
        derivative = self.store.write_derivative(
            source,
            artifact_id=artifact_id,
            lineage=ArtifactLineage.working_copy,
            destination_name=f"{artifact_id}.{derivative_format.value}",
            payload=payload,
            document_format=derivative_format,
            mime_type=_mime_for_format(derivative_format),
            expanded_byte_size=len(payload),
        )
        self._artifacts[derivative.artifact_id] = derivative
        self._extractions[derivative.artifact_id] = self._extraction_for_artifact(
            derivative,
            request.correlation_id,
        )
        return DocumentToolResult(
            tool_id="document_copy_for_edit",
            correlation_id=request.correlation_id,
            status=ToolResultStatus.ok,
            artifact_refs=[source.artifact_id, derivative.artifact_id],
            text_summary=(
                f"Converted {source_label} to editable {derivative_label} derivative "
                "for document editing "
                f"through {engine.engine_id}."
            ),
        )

    def apply_fill(self, request: DocumentApplyFillRequest) -> DocumentToolResult:
        """Apply value patches to a working derivative."""
        working = self._resolve_artifact_for_write(
            request.document,
            request.correlation_id,
            tool_id="document_apply_fill",
        )
        if isinstance(working, DocumentToolResult):
            return working
        extraction = self._extraction_for_artifact(working, request.correlation_id)
        normalized_request = request.model_copy(
            update={
                "patches": self.adapter_registry.require_promoted(
                    working.format
                ).normalize_fill_patches(
                    request.patches,
                    extraction=extraction,
                )
            }
        )
        patch = _fill_patch(normalized_request, working)
        return self._apply_patch_result(
            tool_id="document_apply_fill",
            correlation_id=request.correlation_id,
            working=working,
            patch=patch,
        )

    def apply_style(self, request: DocumentApplyStyleRequest) -> DocumentToolResult:
        """Apply style patches to a working derivative."""
        working = self._resolve_artifact_for_write(
            request.document,
            request.correlation_id,
            tool_id="document_apply_style",
        )
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
        artifact = self._resolve_artifact_for_read(
            request.document,
            request.correlation_id,
            tool_id="document_render",
        )
        if isinstance(artifact, DocumentToolResult):
            return artifact
        try:
            diff = self._diff_for_artifact(artifact.artifact_id)
        except ArtifactStoreError as exc:
            return DocumentToolResult(
                tool_id="document_diff_lookup",
                correlation_id=request.correlation_id,
                status=ToolResultStatus.failed,
                artifact_refs=[artifact.artifact_id],
                text_summary=f"Document diff metadata failed validation: {exc}",
            )
        baseline_artifact: DocumentArtifact | None = None
        if diff is not None:
            baseline = self._artifact_by_id(diff.source_artifact_id, request.correlation_id)
            if isinstance(baseline, DocumentToolResult):
                return baseline
            baseline_artifact = baseline
        render_result = render_document_evidence(
            self.store,
            artifact,
            engine_registry=self.engine_registry,
            correlation_id=request.correlation_id,
            artifact_id_prefix=_generated_artifact_id("render", request.correlation_id),
            diff=diff,
            baseline_artifact=baseline_artifact,
        )
        if diff is not None and render_result.records:
            diff = diff.model_copy(
                update={
                    "render_artifacts": render_result.records,
                    "baseline_render_artifacts": render_result.baseline_records,
                    "changed_viewports": render_result.changed_viewports,
                    "viewport_cameras": render_result.viewport_cameras,
                }
            )
            self._diffs_by_artifact_id[artifact.artifact_id] = diff
            self.store.store_diff(diff)
        blocked_reason = render_result.blocked_reason
        return _with_workflow_steps(
            DocumentToolResult(
                tool_id="document_render",
                correlation_id=request.correlation_id,
                status=render_result.status,
                artifact_refs=[artifact.artifact_id, *render_result.artifact_refs],
                promotion_gate_result=render_result.promotion_gate_result,
                diff=diff,
                render_artifacts=render_result.records,
                text_summary=render_result.text_summary,
                blocked_reason=blocked_reason,
            ),
            artifacts=self._artifacts,
            render_records=render_result.records,
        )

    def validate_public_form(
        self,
        request: DocumentValidatePublicFormRequest,
    ) -> DocumentToolResult:
        """Validate one derivative against the offline conformance baseline catalog."""
        artifact = self._resolve_artifact_for_read(
            request.document,
            request.correlation_id,
            tool_id="document_validate_public_form",
        )
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
        artifact = self._resolve_artifact_for_write(
            request.document,
            request.correlation_id,
            tool_id="document_save",
        )
        if isinstance(artifact, DocumentToolResult):
            return artifact
        pdfa_export_requested = _pdfa_export_requested(
            artifact,
            destination_display_name=request.destination_display_name,
            destination_path=request.destination_path,
        )
        blocked_destination = _blocked_local_export_destination_result(
            request,
            artifact,
            allow_pdfa_alias=pdfa_export_requested,
        )
        if blocked_destination is not None:
            return blocked_destination
        payload = Path(artifact.source_path).read_bytes()
        pdfa_summary: str | None = None
        if pdfa_export_requested:
            if artifact.format is not DocumentFormat.pdf:
                return unsupported_document_tool_result(
                    tool_id="document_save",
                    correlation_id=request.correlation_id,
                    artifact_refs=(artifact.artifact_id,),
                    message="PDF/A export is only available for PDF derivatives.",
                    reason=BlockedReason.extension_mismatch,
                )
            if self.pdfa_conformance_bridge is None:
                return unsupported_document_tool_result(
                    tool_id="document_save",
                    correlation_id=request.correlation_id,
                    artifact_refs=(artifact.artifact_id,),
                    message=(
                        "PDF/A export requires a local Ghostscript PDF/A exporter "
                        "and veraPDF post-write validator."
                    ),
                    reason=BlockedReason.validation_failed,
                )
            try:
                pdfa_result = self.pdfa_conformance_bridge.export_pdfa(payload)
            except PdfaConformanceBridgeError as exc:
                return unsupported_document_tool_result(
                    tool_id="document_save",
                    correlation_id=request.correlation_id,
                    artifact_refs=(artifact.artifact_id,),
                    message=f"PDF/A post-write conformance gate failed: {exc}",
                    reason=BlockedReason.validation_failed,
                )
            payload = pdfa_result.payload
            pdfa_summary = (
                " PDF/A post-write conformance passed through "
                f"{pdfa_result.report.exporter_id} and "
                f"{pdfa_result.report.validator_id}."
            )
        export_artifact = self.store.write_derivative(
            artifact,
            artifact_id=_generated_artifact_id("export", request.correlation_id),
            lineage=ArtifactLineage.export,
            destination_name=request.destination_display_name,
            payload=payload,
            document_format=artifact.format,
            mime_type=artifact.mime_type,
            expanded_byte_size=len(payload),
        )
        self._artifacts[export_artifact.artifact_id] = export_artifact
        self._extractions[export_artifact.artifact_id] = self._extraction_for_artifact(
            export_artifact,
            request.correlation_id,
        )
        saved_exports: tuple[DocumentSavedExport, ...] = ()
        if request.destination_path is not None:
            try:
                saved_exports = (
                    _write_explicit_local_export(
                        artifact,
                        export_artifact=export_artifact,
                        payload=payload,
                        destination_path=request.destination_path,
                        allow_pdfa_alias=pdfa_export_requested,
                    ),
                )
            except _LocalExportBlockedError as exc:
                return unsupported_document_tool_result(
                    tool_id="document_save",
                    correlation_id=request.correlation_id,
                    artifact_refs=(artifact.artifact_id, export_artifact.artifact_id),
                    message=str(exc),
                    reason=exc.reason,
                )
        try:
            diff = self._diff_for_artifact(artifact.artifact_id)
        except ArtifactStoreError as exc:
            return DocumentToolResult(
                tool_id="document_diff_lookup",
                correlation_id=request.correlation_id,
                status=ToolResultStatus.failed,
                artifact_refs=[artifact.artifact_id],
                text_summary=f"Document diff metadata failed validation: {exc}",
            )
        return _with_workflow_steps(
            DocumentToolResult(
                tool_id="document_save",
                correlation_id=request.correlation_id,
                status=ToolResultStatus.ok,
                artifact_refs=[artifact.artifact_id, export_artifact.artifact_id],
                diff=diff,
                saved_exports=saved_exports,
                text_summary=(
                    "Saved local export artifact for human review or external handoff."
                    + (pdfa_summary or "")
                ),
            ),
            artifacts=self._artifacts,
        )

    def _apply_patch_result(
        self,
        *,
        tool_id: str,
        correlation_id: str,
        working: DocumentArtifact,
        patch: DocumentPatch,
    ) -> DocumentToolResult:
        derivative_artifact_id = _generated_artifact_id("derivative", correlation_id)
        result = apply_document_patch(
            self.store,
            working,
            patch,
            engine_registry=self.engine_registry,
            artifact_id=derivative_artifact_id,
            destination_name=f"{derivative_artifact_id}.{working.format.value}",
        )
        if result.status is not ToolResultStatus.ok or result.derivative_artifact is None:
            return _with_workflow_steps(
                DocumentToolResult(
                    tool_id=tool_id,
                    correlation_id=correlation_id,
                    status=result.status,
                    artifact_refs=[working.artifact_id],
                    text_summary=result.text_summary,
                    blocked_reason=result.blocked_reason or BlockedReason.unsupported_operation,
                )
            )
        self._artifacts[result.derivative_artifact.artifact_id] = result.derivative_artifact
        self._extractions[result.derivative_artifact.artifact_id] = self._extraction_for_artifact(
            result.derivative_artifact,
            correlation_id,
        )
        if result.diff is not None:
            self._diffs_by_artifact_id[result.derivative_artifact.artifact_id] = result.diff
            self.store.store_diff(result.diff)
        return _with_workflow_steps(
            DocumentToolResult(
                tool_id=tool_id,
                correlation_id=correlation_id,
                status=ToolResultStatus.ok,
                artifact_refs=[working.artifact_id, result.derivative_artifact.artifact_id],
                diff=result.diff,
                text_summary=result.text_summary,
            ),
            artifacts=self._artifacts,
        )

    def _resolve_artifact_for_read(
        self,
        document: Any,
        correlation_id: str,
        *,
        tool_id: str,
    ) -> DocumentArtifact | DocumentToolResult:
        locator_guard = self._ambiguous_locator_result(
            document,
            correlation_id,
            tool_id=tool_id,
        )
        if locator_guard is not None:
            return locator_guard

        if (
            tool_id in _ARTIFACT_ID_REQUIRED_TOOL_IDS
            and document.artifact_id is None
            and document.path is not None
        ):
            return needs_input_document_tool_result(
                tool_id=tool_id,
                correlation_id=correlation_id,
                message=(
                    "Call document_inspect first and pass the returned artifact_id "
                    f"before {tool_id}."
                ),
            )

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
        *,
        tool_id: str,
    ) -> DocumentArtifact | DocumentToolResult:
        artifact = self._resolve_artifact_for_read(
            document,
            correlation_id,
            tool_id=tool_id,
        )
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

    def _ambiguous_locator_result(
        self,
        document: Any,
        correlation_id: str,
        *,
        tool_id: str,
    ) -> DocumentToolResult | None:
        artifact_id = getattr(document, "artifact_id", None)
        path = getattr(document, "path", None)
        if artifact_id is None or path is None:
            return None
        return needs_input_document_tool_result(
            tool_id=tool_id,
            correlation_id=correlation_id,
            artifact_refs=(artifact_id,),
            message=(
                "Document locator is ambiguous: pass artifact_id for an existing "
                "local artifact or path for first inspection, not both."
            ),
        )

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
            try:
                artifact = self.store.load_artifact(artifact_id)
            except ArtifactStoreError as exc:
                return DocumentToolResult(
                    tool_id="document_artifact_lookup",
                    correlation_id=correlation_id,
                    status=ToolResultStatus.failed,
                    artifact_refs=[artifact_id],
                    text_summary=f"Document artifact metadata failed validation: {exc}",
                )
        if artifact is None:
            return needs_input_document_tool_result(
                tool_id="document_artifact_lookup",
                correlation_id=correlation_id,
                artifact_refs=(artifact_id,),
                message=f"Unknown local document artifact: {artifact_id}.",
            )
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def _diff_for_artifact(self, artifact_id: str) -> DocumentDiff | None:
        diff = self._diffs_by_artifact_id.get(artifact_id)
        if diff is not None:
            return diff
        diff = self.store.load_diff(artifact_id)
        if diff is not None:
            self._diffs_by_artifact_id[artifact_id] = diff
        return diff

    def _extraction_for_artifact(
        self,
        artifact: DocumentArtifact,
        correlation_id: str,
    ) -> DocumentExtraction:
        extraction = self._extractions.get(artifact.artifact_id)
        if extraction is not None:
            return extraction
        adapter = self.adapter_registry.require_promoted(artifact.format)
        extraction = adapter.inspect(Path(artifact.source_path), artifact_id=correlation_id)
        self._extractions[artifact.artifact_id] = extraction
        return extraction

    def _existing_source_artifact_for_path(
        self,
        *,
        artifact_id: str,
        source_path: Path,
        document_format: DocumentFormat,
    ) -> DocumentArtifact | None:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            artifact = self.store.load_artifact(artifact_id)
        if artifact is None:
            return None
        source = source_path.expanduser().resolve()
        source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        if (
            artifact.lineage is ArtifactLineage.source
            and artifact.format is document_format
            and artifact.display_name == source.name
            and artifact.sha256 == source_sha256
        ):
            self._artifacts[artifact.artifact_id] = artifact
            return artifact
        return None

    def _source_artifact_for_inspected_path(
        self,
        *,
        artifact_id: str,
        source_path: Path,
        document_format: DocumentFormat,
        correlation_id: str,
    ) -> DocumentArtifact | DocumentToolResult:
        existing = self._existing_source_artifact_for_path(
            artifact_id=artifact_id,
            source_path=source_path,
            document_format=document_format,
        )
        if existing is not None:
            return existing
        try:
            return self.store.store_source(
                source_path,
                artifact_id=artifact_id,
                document_format=document_format,
                mime_type=_mime_for_format(document_format),
            )
        except ArtifactStoreError as exc:
            return DocumentToolResult(
                tool_id="document_inspect",
                correlation_id=correlation_id,
                status=ToolResultStatus.failed,
                artifact_refs=[artifact_id],
                text_summary=f"Document source artifact storage failed: {exc}",
                blocked_reason=BlockedReason.validation_failed,
            )

    def _with_runtime_workflow_steps(self, result: DocumentToolResult) -> DocumentToolResult:
        return _with_workflow_steps(result, artifacts=self._artifacts)

    def _attachment_context_derivative_result(
        self,
        request: DocumentPrimitiveRequest,
        source_result: DocumentToolResult,
    ) -> DocumentToolResult:
        extraction = source_result.extraction
        if extraction is None or request.document.path is None:
            return unsupported_document_tool_result(
                tool_id="document",
                correlation_id=request.correlation_id,
                artifact_refs=tuple(source_result.artifact_refs),
                message=(
                    "Attachment-context derivative creation requires a local source path "
                    "with extraction metadata."
                ),
                reason=BlockedReason.unsupported_operation,
            )
        source_path = Path(request.document.path).expanduser().resolve()
        payload = _attachment_context_markdown_payload(
            extraction,
            source_path=source_path,
            instruction=request.instruction,
        ).encode("utf-8")
        source_artifact_id = _generated_artifact_id(
            "source",
            f"{request.correlation_id}-attachment-context",
        )
        source_display_name = _attachment_context_display_name(source_path)
        with tempfile.TemporaryDirectory(prefix="ummaya-attachment-context-") as raw_temp_dir:
            generated_path = Path(raw_temp_dir) / source_display_name
            generated_path.write_bytes(payload)
            generated_source = self.store.store_source(
                generated_path,
                artifact_id=source_artifact_id,
                document_format=DocumentFormat.md,
                mime_type=_mime_for_format(DocumentFormat.md),
                display_name=source_display_name,
            )
        self._artifacts[generated_source.artifact_id] = generated_source
        self._extractions[generated_source.artifact_id] = self._extraction_for_artifact(
            generated_source,
            request.correlation_id,
        )

        copy_result = self.copy_for_edit(
            DocumentCopyForEditRequest(
                correlation_id=request.correlation_id,
                document=DocumentLocator(artifact_id=generated_source.artifact_id),
                reason=_copy_for_edit_reason(request.instruction),
            )
        )
        if copy_result.status is not ToolResultStatus.ok:
            return _document_result_from_stage(copy_result, correlation_id=request.correlation_id)
        working_artifact_id = copy_result.artifact_refs[-1]

        render_result = self.render(
            DocumentRenderRequest(
                correlation_id=request.correlation_id,
                document=DocumentLocator(artifact_id=working_artifact_id),
            )
        )
        if render_result.status is not ToolResultStatus.ok:
            return _document_result_from_stage(render_result, correlation_id=request.correlation_id)

        result = render_result.model_copy(
            update={
                "tool_id": "document",
                "artifact_refs": _unique_artifact_refs(
                    [
                        generated_source.artifact_id,
                        working_artifact_id,
                        *render_result.artifact_refs,
                    ]
                ),
                "extraction": extraction,
                "text_summary": (
                    "Attachment context derivative document created with local render evidence."
                ),
            }
        )

        if (
            request.operation == "save"
            or request.destination_display_name is not None
            or request.destination_path is not None
        ):
            destination_display_name = request.destination_display_name
            if destination_display_name is None and request.destination_path is not None:
                destination_display_name = Path(request.destination_path).name
            if destination_display_name is None:
                destination_display_name = source_display_name
            save_result = self.save(
                DocumentSaveRequest(
                    correlation_id=request.correlation_id,
                    document=DocumentLocator(artifact_id=working_artifact_id),
                    destination_display_name=destination_display_name,
                    destination_path=request.destination_path,
                )
            )
            if save_result.status is not ToolResultStatus.ok:
                return _document_result_from_stage(
                    save_result,
                    correlation_id=request.correlation_id,
                )
            result = result.model_copy(
                update={
                    "artifact_refs": _unique_artifact_refs(
                        [*result.artifact_refs, *save_result.artifact_refs]
                    ),
                    "saved_exports": save_result.saved_exports,
                    "workflow_steps": _merge_save_workflow_steps(
                        result.workflow_steps,
                        save_result.workflow_steps,
                    ),
                }
            )
        return result


class _SessionDocumentRuntimePool:
    """Lazily allocate one document runtime per caller session."""

    def __init__(
        self,
        *,
        artifact_root: str | Path | None = None,
        engine_registry: DocumentEngineRegistry | None = None,
        adapter_registry: DocumentAdapterRegistry | None = None,
        conversion_registry: DocumentConversionRegistry | None = None,
        baseline_catalog: ConformanceBaselineCatalog | None = None,
    ) -> None:
        self._artifact_root = artifact_root
        self._engine_registry = engine_registry
        self._adapter_registry = adapter_registry
        self._conversion_registry = conversion_registry
        self._baseline_catalog = baseline_catalog
        self._runtimes: dict[str, DocumentToolRuntime] = {}

    def runtime_for(self, session_identity: object | None) -> DocumentToolRuntime:
        session_id = _runtime_session_id(session_identity)
        runtime = self._runtimes.get(session_id)
        if runtime is None:
            runtime = DocumentToolRuntime(
                session_id=session_id,
                artifact_root=self._artifact_root,
                engine_registry=self._engine_registry,
                adapter_registry=self._adapter_registry,
                conversion_registry=self._conversion_registry,
                baseline_catalog=self._baseline_catalog,
            )
            self._runtimes[session_id] = runtime
        return runtime


def register_document_tools(
    registry: ToolRegistry,
    executor: ToolExecutor,
    *,
    runtime: DocumentToolRuntime | None = None,
    artifact_root: str | Path | None = None,
    engine_registry: DocumentEngineRegistry | None = None,
    adapter_registry: DocumentAdapterRegistry | None = None,
    conversion_registry: DocumentConversionRegistry | None = None,
    baseline_catalog: ConformanceBaselineCatalog | None = None,
) -> None:
    """Register document harness tools and their executor adapters."""
    runtime_pool = None
    if runtime is None:
        runtime_pool = _SessionDocumentRuntimePool(
            artifact_root=artifact_root,
            engine_registry=engine_registry,
            adapter_registry=adapter_registry,
            conversion_registry=conversion_registry,
            baseline_catalog=baseline_catalog,
        )

    for tool in build_document_tool_definitions():
        registry.register(tool)

        if runtime is not None:

            async def _adapter(inp: BaseModel, *, _tool_id: str = tool.id) -> dict[str, Any]:
                return await runtime.handle(_tool_id, inp)

            executor.register_adapter(tool.id, _adapter)
            continue

        assert runtime_pool is not None
        active_pool = runtime_pool

        async def _session_adapter(
            inp: BaseModel,
            session_identity: object | None,
            *,
            _tool_id: str = tool.id,
            _runtime_pool: _SessionDocumentRuntimePool = active_pool,
        ) -> dict[str, Any]:
            return await _runtime_pool.runtime_for(session_identity).handle(_tool_id, inp)

        executor.register_session_adapter(tool.id, _session_adapter)


_SAFE_RUNTIME_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _runtime_session_id(session_identity: object | None) -> str:
    if session_identity is None:
        return "anonymous"
    raw = str(session_identity).strip() or "anonymous"
    if _SAFE_RUNTIME_SESSION_ID_RE.fullmatch(raw):
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    label = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("._-")[:48] or "session"
    return f"{label}-{digest}"


def _source_artifact_id(correlation_id: str) -> str:
    return _generated_artifact_id("source", correlation_id)


_SAFE_ARTIFACT_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_MAX_ARTIFACT_COMPONENT_LENGTH = 128


def _generated_artifact_id(prefix: str, correlation_id: str) -> str:
    """Build a store-safe artifact id from model-supplied correlation text."""
    safe_prefix = _ascii_component(prefix, fallback="artifact", max_length=32)
    raw = correlation_id.strip()
    candidate = f"{safe_prefix}-{raw}"
    if len(candidate) <= _MAX_ARTIFACT_COMPONENT_LENGTH and _SAFE_ARTIFACT_COMPONENT_RE.fullmatch(
        candidate
    ):
        return candidate

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    max_slug_length = _MAX_ARTIFACT_COMPONENT_LENGTH - len(safe_prefix) - len(digest) - 2
    slug = _ascii_component(raw, fallback="corr", max_length=max_slug_length)
    return f"{safe_prefix}-{slug}-{digest}"


def _ascii_component(value: str, *, fallback: str, max_length: int) -> str:
    component = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("._-")
    component = re.sub(r"-{2,}", "-", component)
    if not component:
        component = fallback
    if not re.match(r"^[A-Za-z0-9]", component):
        component = f"{fallback}-{component}"
    component = component[: max(max_length, 1)].strip("._-")
    if not component:
        component = fallback
    if not re.match(r"^[A-Za-z0-9]", component):
        component = f"{fallback}-{component}"
    return component[:max_length]


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


_ATTACHMENT_CONTEXT_MUTATION_POLICIES = frozenset(
    {
        "extraction_only",
        "metadata_only_geospatial_asset",
        "metadata_only_media_asset",
    }
)


def _is_attachment_context_extraction(extraction: DocumentExtraction | None) -> bool:
    if extraction is None:
        return False
    return extraction.metadata.get("mutation_policy") in _ATTACHMENT_CONTEXT_MUTATION_POLICIES


def _attachment_context_display_name(source_path: Path) -> str:
    safe_stem = _ascii_component(source_path.stem, fallback="attachment", max_length=80)
    return f"{safe_stem}-context.md"


def _attachment_context_markdown_payload(
    extraction: DocumentExtraction,
    *,
    source_path: Path,
    instruction: str,
) -> str:
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    known_format = _metadata_as_text(extraction.metadata.get("known_format"))
    mutation_policy = _metadata_as_text(extraction.metadata.get("mutation_policy"))
    byte_size = _metadata_as_text(extraction.metadata.get("byte_size"))
    lines = [
        "# Attachment Context Derivative",
        "",
        "This generated document records attachment evidence for public-document authoring.",
        "It does not mutate the original attachment file.",
        "",
        "## Source",
        f"- source_file: {source_path.name}",
        f"- source_sha256: {source_sha256}",
        f"- known_format: {known_format}",
        f"- byte_size: {byte_size}",
        f"- mutation_policy: {mutation_policy}",
        "",
        "## Extracted References",
    ]
    if extraction.images:
        for image in extraction.images:
            lines.append(f"- image: {image.image_id} ({image.content_type})")
    if extraction.paragraphs:
        for paragraph in extraction.paragraphs[:12]:
            lines.append(f"- paragraph: {paragraph.text}")
    if not extraction.images and not extraction.paragraphs:
        lines.append("- metadata-only attachment; no document text was extracted.")
    lines.extend(
        [
            "",
            "## Runtime Boundaries",
            "- OCR text: not available; no OCR runtime was applied.",
            "- Geospatial feature extraction: not available unless a vetted GDAL bridge is active.",
            (
                "- Media transcript: not available unless a vetted "
                "ffprobe/transcription bridge is active."
            ),
            "",
            "## User Instruction",
            instruction.strip(),
            "",
        ]
    )
    if extraction.warnings:
        lines.extend(["## Warnings", *[f"- {warning}" for warning in extraction.warnings], ""])
    return "\n".join(lines)


def _metadata_as_text(value: object) -> str:
    if value is None:
        return "unknown"
    return str(value)


def _filtered_extraction(
    extraction: DocumentExtraction,
    *,
    include_tables: bool,
    include_images: bool,
    include_fields: bool,
) -> DocumentExtraction:
    updates: dict[str, list[object]] = {}
    if not include_tables:
        updates["tables"] = []
    if not include_images:
        updates["images"] = []
    if not include_fields:
        updates["fields"] = []
    if not updates:
        return extraction
    return extraction.model_copy(update=updates)


def _missing_local_document_result(
    path: Path,
    *,
    correlation_id: str,
    tool_id: str,
    expected_format: DocumentFormat | None,
) -> DocumentToolResult:
    candidates = _matching_local_document_candidates(path, expected_format=expected_format)
    lines = [f"Document path does not exist: {path}."]
    if candidates:
        lines.append("Matching local candidates require explicit selection:")
        lines.extend(f"- {candidate}" for candidate in candidates[:5])
    else:
        lines.append("No matching local document candidates were found in the requested directory.")
    return needs_input_document_tool_result(
        tool_id=tool_id,
        correlation_id=correlation_id,
        message="\n".join(lines),
    )


def _matching_local_document_candidates(
    path: Path,
    *,
    expected_format: DocumentFormat | None,
) -> list[Path]:
    parent = path.parent
    if not parent.is_dir():
        return []
    suffixes = (
        (f".{expected_format.value}",)
        if expected_format is not None
        else tuple(f".{document_format.value}" for document_format in DocumentFormat)
    )
    requested_stem = _normalized_document_stem(path.stem)
    if not requested_stem:
        return []
    scored_candidates: list[tuple[float, Path]] = []
    for candidate in sorted(parent.iterdir(), key=lambda item: item.name):
        if not candidate.is_file() or candidate.suffix.lower() not in suffixes:
            continue
        candidate_stem = _normalized_document_stem(candidate.stem)
        score = _document_stem_match_score(requested_stem, candidate_stem)
        if score >= _MIN_LOCAL_DOCUMENT_CANDIDATE_SCORE:
            scored_candidates.append((score, candidate))
    return [
        candidate
        for _, candidate in sorted(
            scored_candidates,
            key=lambda item: (-item[0], item[1].name),
        )
    ]


def _normalized_document_stem(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).casefold()
    alphanumeric = re.sub(r"[^0-9a-z가-힣]+", "", normalized)
    return _DOCUMENT_STEM_NOISE_RE.sub("", alphanumeric)


def _document_stem_match_score(requested_stem: str, candidate_stem: str) -> float:
    if not requested_stem or not candidate_stem:
        return 0.0
    if requested_stem in candidate_stem or candidate_stem in requested_stem:
        return 1.0
    return SequenceMatcher(None, requested_stem, candidate_stem).ratio()


def _mime_for_format(document_format: Any) -> str:
    value = str(getattr(document_format, "value", document_format))
    return {
        "hwpx": "application/owpml",
        "owpml": "application/owpml",
        "hwp": "application/x-hwp",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ppt": "application/vnd.ms-powerpoint",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "md": "text/markdown",
        "epub": "application/epub+zip",
        "zip": "application/zip",
        "tar": "application/x-tar",
        "gz": "application/gzip",
    }.get(value, "application/octet-stream")


def _editable_derivative_format(document_format: DocumentFormat) -> DocumentFormat | None:
    return _EDITABLE_DERIVATIVE_FORMAT_BY_SOURCE.get(document_format)


def _conversion_labels(
    source_format: DocumentFormat,
    derivative_format: DocumentFormat,
) -> tuple[str, str]:
    return _DERIVATIVE_LABEL_BY_FORMAT.get(
        source_format,
        (source_format.value.upper(), derivative_format.value.upper()),
    )


def _conversion_missing_message(
    *,
    source_format: DocumentFormat,
    derivative_format: DocumentFormat,
    source_label: str,
    derivative_label: str,
) -> str:
    if source_format is DocumentFormat.hwp:
        return (
            "HWP binary direct writing is blocked. HWP to HWPX conversion is "
            "required before editing legacy HWP files. Direct HWP binary working "
            "copies remain blocked. Use a HWPX or DOCX editable template, or "
            "register a vetted local HWP to HWPX conversion engine."
        )
    return (
        f"{source_label} binary direct writing is blocked. {source_label} to "
        f"{derivative_label} conversion is required before editing legacy Office "
        f"files. Direct {source_label} binary working copies remain blocked. "
        f"Install or register a vetted local LibreOffice/soffice conversion bridge "
        f"for {source_format.value} -> {derivative_format.value}."
    )


def _document_primitive_fill_patches(
    patches: tuple[DocumentFieldPatch, ...],
    *,
    adapter: DocumentFormatAdapter,
    extraction: DocumentExtraction | None,
) -> tuple[DocumentFieldPatch, ...]:
    return adapter.normalize_fill_patches(patches, extraction=extraction)


def _should_prefer_autonomous_fill_plan(
    instruction: str,
    patches: tuple[DocumentFieldPatch, ...],
) -> bool:
    """Return True when deterministic planning should replace model-supplied patches."""
    _ = instruction
    _ = patches
    return False


def _copy_for_edit_reason(instruction: str) -> str:
    """Bound long citizen instructions to the copy-for-edit audit field."""
    normalized = " ".join(instruction.split())
    if len(normalized) <= _COPY_FOR_EDIT_REASON_MAX_LENGTH:
        return normalized
    suffix = "…"
    return normalized[: _COPY_FOR_EDIT_REASON_MAX_LENGTH - len(suffix)].rstrip() + suffix


def _fill_patches_from_autonomous_plan(
    plan: AutonomousFillPlan,
) -> tuple[DocumentFieldPatch, ...]:
    return tuple(
        DocumentFieldPatch(
            target_path=slot.source_anchor.format_path,
            value=slot.candidate_value,
        )
        for slot in plan.slots
        if not slot.protected and slot.candidate_value is not None
    )


def _style_patches_from_autonomous_plan(
    plan: AutonomousFillPlan,
) -> tuple[DocumentStylePatch, ...]:
    return tuple(
        DocumentStylePatch(
            target_path=style_intent.target_path,
            font_family=style_intent.style.font_family,
            font_size_pt=style_intent.style.font_size_pt,
            bold=style_intent.style.bold,
            italic=style_intent.style.italic,
            underline=style_intent.style.underline,
            font_color_rgb=style_intent.style.font_color_rgb,
            fill_color_rgb=style_intent.style.fill_color_rgb,
            alignment=style_intent.style.alignment,
        )
        for style_intent in plan.style_intents
    )


def _fill_patch(
    request: DocumentApplyFillRequest,
    working: DocumentArtifact,
) -> DocumentPatch:
    return DocumentPatch(
        patch_id=f"fill-{request.correlation_id}",
        target_artifact_id=working.artifact_id,
        operations=[
            _field_patch_operation(
                item,
                index=index,
                document_format=working.format,
            )
            for index, item in enumerate(request.patches, start=1)
        ],
        dry_run=request.dry_run,
        expected_format=working.format,
        destination_policy="working_copy",
    )


def _fill_style_patch(
    *,
    correlation_id: str,
    patches: tuple[DocumentFieldPatch, ...],
    styles: tuple[DocumentStylePatch, ...],
    working: DocumentArtifact,
) -> DocumentPatch:
    operations = [
        _field_patch_operation(
            item,
            index=index,
            document_format=working.format,
        )
        for index, item in enumerate(patches, start=1)
    ]
    operations.extend(
        _style_patch_operation(item, index=index, document_format=working.format)
        for index, item in enumerate(styles, start=1)
    )
    return DocumentPatch(
        patch_id=f"fill-style-{correlation_id}",
        target_artifact_id=working.artifact_id,
        operations=operations,
        dry_run=False,
        expected_format=working.format,
        destination_policy="working_copy",
    )


def _style_patch(request: DocumentApplyStyleRequest, working: DocumentArtifact) -> DocumentPatch:
    return DocumentPatch(
        patch_id=f"style-{request.correlation_id}",
        target_artifact_id=working.artifact_id,
        operations=[
            _style_patch_operation(item, index=index, document_format=working.format)
            for index, item in enumerate(request.styles, start=1)
        ],
        dry_run=request.dry_run,
        expected_format=working.format,
        destination_policy="working_copy",
    )


def _field_patch_operation(
    item: DocumentFieldPatch,
    *,
    index: int,
    document_format: DocumentFormat,
) -> DocumentPatchOperation:
    return DocumentPatchOperation(
        operation_id=f"fill-{index:03d}",
        operation_type=_field_patch_operation_type(
            item.target_path,
            document_format=document_format,
        ),
        target_path=item.target_path,
        value=item.value,
    )


def _field_patch_operation_type(
    target_path: str,
    *,
    document_format: DocumentFormat,
) -> OperationType:
    if document_format is DocumentFormat.xlsx and _XLSX_CELL_FILL_TARGET_RE.match(target_path):
        return OperationType.set_table_cell
    if document_format is DocumentFormat.docx and _DOCX_TABLE_FILL_TARGET_RE.search(target_path):
        return OperationType.set_table_cell
    if document_format is DocumentFormat.pptx and _PPTX_TABLE_FILL_TARGET_RE.match(target_path):
        return OperationType.set_table_cell
    if document_format in {DocumentFormat.hwpx, DocumentFormat.owpml} and (
        _HWPX_TABLE_CELL_SOURCE_RE.match(target_path)
    ):
        return OperationType.set_table_cell
    return OperationType.set_field_value


def _style_patch_operation(
    item: DocumentStylePatch,
    *,
    index: int,
    document_format: DocumentFormat,
) -> DocumentPatchOperation:
    return DocumentPatchOperation(
        operation_id=f"style-{index:03d}",
        operation_type=_style_patch_operation_type(
            item.target_path,
            document_format=document_format,
        ),
        target_path=item.target_path,
        style=item.to_style_descriptor(style_id=f"style-{index:03d}"),
    )


def _style_patch_operation_type(
    target_path: str,
    *,
    document_format: DocumentFormat,
) -> OperationType:
    if document_format is DocumentFormat.xlsx and _XLSX_CELL_FILL_TARGET_RE.match(target_path):
        return OperationType.set_cell_style
    if document_format is DocumentFormat.docx and "/runs/" in target_path:
        return OperationType.set_run_style
    if document_format is DocumentFormat.docx and _DOCX_TABLE_FILL_TARGET_RE.search(target_path):
        return OperationType.set_cell_style
    return OperationType.set_paragraph_style


_WORKFLOW_DEFINITION: tuple[tuple[str, str], ...] = (
    ("inspect", "Inspect"),
    ("field_schema", "Field schema"),
    ("working_copy", "Working copy"),
    ("fill_style", "Fill/style"),
    ("diff", "Diff"),
    ("render", "Render"),
    ("validate", "Validate"),
    ("save", "Save"),
)

_WORKFLOW_STEP_INDEX = {
    step_id: index for index, (step_id, _label) in enumerate(_WORKFLOW_DEFINITION)
}

_TOOL_WORKFLOW_STEP_ID = {
    "document_inspect": "inspect",
    "document_extract": "field_schema",
    "document_form_schema": "field_schema",
    "document_copy_for_edit": "working_copy",
    "document_apply_fill": "fill_style",
    "document_apply_style": "fill_style",
    "document_render": "render",
    "document_validate_public_form": "validate",
    "document_save": "save",
}

_ARTIFACT_ID_REQUIRED_TOOL_IDS = frozenset(
    {
        "document_copy_for_edit",
        "document_apply_fill",
        "document_apply_style",
        "document_render",
        "document_validate_public_form",
        "document_save",
    }
)


def _with_workflow_steps(
    result: DocumentToolResult,
    *,
    artifacts: dict[str, DocumentArtifact] | None = None,
    render_records: tuple[RenderArtifactRecord, ...] = (),
) -> DocumentToolResult:
    if result.workflow_steps:
        return result
    workflow_steps = _workflow_steps_for_result(
        result,
        artifacts=artifacts or {},
        render_records=render_records,
    )
    if not workflow_steps:
        return result
    return result.model_copy(update={"workflow_steps": workflow_steps})


def _workflow_steps_for_result(
    result: DocumentToolResult,
    *,
    artifacts: dict[str, DocumentArtifact],
    render_records: tuple[RenderArtifactRecord, ...],
) -> list[DocumentWorkflowStep]:
    current_step_id = _TOOL_WORKFLOW_STEP_ID.get(result.tool_id)
    if current_step_id is None:
        return []
    current_index = _WORKFLOW_STEP_INDEX[current_step_id]
    statuses = [DocumentWorkflowStepStatus.pending for _step in _WORKFLOW_DEFINITION]

    if result.status is ToolResultStatus.ok:
        _mark_ok_workflow_statuses(result, statuses, current_index)
    elif result.status is ToolResultStatus.blocked:
        for index in range(_completed_before_blocked_step(current_step_id) + 1):
            statuses[index] = DocumentWorkflowStepStatus.completed
        statuses[current_index] = DocumentWorkflowStepStatus.blocked
        statuses[_WORKFLOW_STEP_INDEX["save"]] = DocumentWorkflowStepStatus.skipped
    elif result.status is ToolResultStatus.failed:
        for index in range(max(current_index - 1, -1) + 1):
            statuses[index] = DocumentWorkflowStepStatus.completed
        statuses[current_index] = DocumentWorkflowStepStatus.failed
        statuses[_WORKFLOW_STEP_INDEX["save"]] = DocumentWorkflowStepStatus.skipped
    elif result.status is ToolResultStatus.needs_input:
        statuses[current_index] = DocumentWorkflowStepStatus.current

    return [
        _workflow_step(
            result,
            step_id=step_id,
            label=label,
            status=statuses[index],
            artifacts=artifacts,
            render_records=render_records,
        )
        for index, (step_id, label) in enumerate(_WORKFLOW_DEFINITION)
    ]


def _mark_ok_workflow_statuses(
    result: DocumentToolResult,
    statuses: list[DocumentWorkflowStepStatus],
    current_index: int,
) -> None:
    if result.tool_id == "document_save":
        completed_through = (
            _WORKFLOW_STEP_INDEX["diff"]
            if result.diff is not None
            else _WORKFLOW_STEP_INDEX["working_copy"]
        )
        for index in range(completed_through + 1):
            statuses[index] = DocumentWorkflowStepStatus.completed
        statuses[_WORKFLOW_STEP_INDEX["save"]] = DocumentWorkflowStepStatus.completed
        return

    completed_through = _completed_workflow_index(result, current_index)
    for index in range(completed_through + 1):
        statuses[index] = DocumentWorkflowStepStatus.completed


def _workflow_step(
    result: DocumentToolResult,
    *,
    step_id: str,
    label: str,
    status: DocumentWorkflowStepStatus,
    artifacts: dict[str, DocumentArtifact],
    render_records: tuple[RenderArtifactRecord, ...],
) -> DocumentWorkflowStep:
    artifact_id = _workflow_artifact_id(result, step_id, render_records)
    artifact_sha256 = _workflow_artifact_sha256(
        artifact_id,
        artifacts=artifacts,
        render_records=render_records,
    )
    return DocumentWorkflowStep(
        step_id=step_id,
        label=label,
        status=status,
        artifact_id=artifact_id,
        artifact_sha256=artifact_sha256,
        detail=_workflow_detail(result, step_id),
    )


def _workflow_artifact_id(
    result: DocumentToolResult,
    step_id: str,
    render_records: tuple[RenderArtifactRecord, ...],
) -> str | None:
    if result.tool_id == "document_save":
        return _save_workflow_artifact_id(result, step_id)
    if step_id == "fill_style" and result.diff is not None:
        return result.diff.derivative_artifact_id
    if step_id == "diff" and result.diff is not None:
        return result.diff.derivative_artifact_id
    if step_id == "render" and render_records:
        return render_records[0].render_artifact_id
    return _workflow_artifact_id_from_refs(result, step_id)


def _save_workflow_artifact_id(result: DocumentToolResult, step_id: str) -> str | None:
    if step_id == "save" and len(result.artifact_refs) > 1:
        return result.artifact_refs[1]
    if step_id in {"inspect", "field_schema", "working_copy", "fill_style", "diff"}:
        return result.artifact_refs[0] if result.artifact_refs else None
    return None


def _workflow_artifact_id_from_refs(
    result: DocumentToolResult,
    step_id: str,
) -> str | None:
    if result.tool_id in {"document_render", "document_validate_public_form"} and step_id in {
        "working_copy",
        "fill_style",
        "diff",
    }:
        if step_id == "working_copy" and result.diff is not None:
            return result.diff.source_artifact_id
        return result.artifact_refs[0] if result.artifact_refs else None
    if step_id in {"inspect", "field_schema"} and result.artifact_refs:
        return result.artifact_refs[0]
    if step_id == "working_copy" and len(result.artifact_refs) > 1:
        return result.artifact_refs[1]
    if step_id == "render" and result.tool_id == "document_render" and result.artifact_refs:
        return result.artifact_refs[0]
    return None


def _workflow_artifact_sha256(
    artifact_id: str | None,
    *,
    artifacts: dict[str, DocumentArtifact],
    render_records: tuple[RenderArtifactRecord, ...],
) -> str | None:
    if artifact_id is None:
        return None
    artifact = artifacts.get(artifact_id)
    if artifact is not None:
        return artifact.sha256
    for record in render_records:
        if record.render_artifact_id == artifact_id:
            return record.render_sha256
    return None


def _workflow_detail(result: DocumentToolResult, step_id: str) -> str | None:
    if step_id == "diff" and result.diff is not None:
        return result.diff.diff_id
    if step_id == "render" and result.promotion_gate_result is not None:
        failures = result.promotion_gate_result.hard_gate_failures
        return failures[0] if failures else result.promotion_gate_result.promotion_state.value
    return None


def _completed_workflow_index(result: DocumentToolResult, current_index: int) -> int:
    if (
        result.tool_id in {"document_apply_fill", "document_apply_style"}
        and result.diff is not None
    ):
        return _WORKFLOW_STEP_INDEX["diff"]
    return current_index


def _completed_before_blocked_step(current_step_id: str) -> int:
    if current_step_id == "render":
        return _WORKFLOW_STEP_INDEX["working_copy"]
    return max(_WORKFLOW_STEP_INDEX[current_step_id] - 1, -1)


def _document_result_from_stage(
    result: DocumentToolResult,
    *,
    correlation_id: str,
) -> DocumentToolResult:
    return result.model_copy(update={"tool_id": "document", "correlation_id": correlation_id})


def _unique_artifact_refs(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _merge_save_workflow_steps(
    base_steps: list[DocumentWorkflowStep],
    save_steps: list[DocumentWorkflowStep],
) -> list[DocumentWorkflowStep]:
    save_by_id = {step.step_id: step for step in save_steps}
    merged: list[DocumentWorkflowStep] = []
    for step in base_steps:
        if step.step_id == "save":
            merged.append(save_by_id.get("save", step))
        else:
            merged.append(step)
    return merged


def _explicit_save_path_from_instruction(
    instruction: str,
    *,
    source_artifact: DocumentArtifact,
) -> str | None:
    if not _DOCUMENT_SAVE_INTENT_RE.search(instruction):
        return None
    source_path = Path(source_artifact.source_path).expanduser().resolve()
    candidates: list[Path] = []
    allowed_suffixes = {f".{source_artifact.format.value}"}
    derivative_format = _editable_derivative_format(source_artifact.format)
    if derivative_format is not None:
        allowed_suffixes.add(f".{derivative_format.value}")
    for match in _EXPLICIT_LOCAL_DOCUMENT_PATH_RE.finditer(instruction):
        candidate = Path(match.group(0).rstrip(".,;:)]}）")).expanduser().resolve()
        if candidate == source_path:
            continue
        if candidate.suffix.lower() not in allowed_suffixes:
            continue
        candidates.append(candidate)
    if not candidates:
        return None
    return str(candidates[-1])


class _LocalExportBlockedError(ValueError):
    """Raised when an explicit local export path is unsafe or incompatible."""

    def __init__(self, reason: BlockedReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _write_explicit_local_export(
    source_artifact: DocumentArtifact,
    *,
    export_artifact: DocumentArtifact,
    payload: bytes,
    destination_path: str,
    allow_pdfa_alias: bool = False,
) -> DocumentSavedExport:
    destination = _validated_local_export_destination(
        destination_path,
        document_format=source_artifact.format,
        allow_pdfa_alias=allow_pdfa_alias,
    )
    overwrite_existing = destination.exists()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _write_tempfile_for_replace(destination, payload)
    try:
        os.replace(temp_path, destination)
        _fsync_directory_best_effort(destination.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return DocumentSavedExport(
        export_artifact_id=export_artifact.artifact_id,
        source_artifact_id=source_artifact.artifact_id,
        local_path=destination,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload),
        overwrite_existing=overwrite_existing,
    )


def _blocked_local_export_destination_result(
    request: DocumentSaveRequest,
    artifact: DocumentArtifact,
    *,
    allow_pdfa_alias: bool = False,
) -> DocumentToolResult | None:
    if request.destination_path is None:
        return None
    try:
        _validated_local_export_destination(
            request.destination_path,
            document_format=artifact.format,
            allow_pdfa_alias=allow_pdfa_alias,
        )
    except _LocalExportBlockedError as exc:
        return unsupported_document_tool_result(
            tool_id="document_save",
            correlation_id=request.correlation_id,
            artifact_refs=(artifact.artifact_id,),
            message=str(exc),
            reason=exc.reason,
        )
    return None


def _validated_local_export_destination(
    destination_path: str,
    *,
    document_format: DocumentFormat,
    allow_pdfa_alias: bool = False,
) -> Path:
    destination = Path(destination_path).expanduser().resolve()
    if destination.name in {"", ".", ".."} or destination.name.startswith("."):
        raise _LocalExportBlockedError(
            BlockedReason.hidden_destination,
            f"Document local export destination is hidden or invalid: {destination}",
        )
    if any(part.startswith(".") for part in destination.parts if part not in {"/", "."}):
        raise _LocalExportBlockedError(
            BlockedReason.hidden_destination,
            f"Document local export destination contains a hidden path component: {destination}",
        )
    if destination.exists() and destination.is_dir():
        raise _LocalExportBlockedError(
            BlockedReason.validation_failed,
            f"Document local export destination is a directory: {destination}",
        )
    expected_suffix = f".{document_format.value}"
    allowed_suffixes = {expected_suffix}
    if allow_pdfa_alias and document_format is DocumentFormat.pdf:
        allowed_suffixes.add(".pdfa")
    if destination.suffix.lower() not in allowed_suffixes:
        raise _LocalExportBlockedError(
            BlockedReason.extension_mismatch,
            (
                "Document local export destination extension must match "
                f"{' or '.join(sorted(allowed_suffixes))}: {destination}"
            ),
        )
    return destination


def _pdfa_export_requested(
    artifact: DocumentArtifact,
    *,
    destination_display_name: str,
    destination_path: str | None,
) -> bool:
    if artifact.format is not DocumentFormat.pdf:
        return False
    if Path(destination_display_name).suffix.lower() == ".pdfa":
        return True
    if (
        destination_path is not None
        and Path(destination_path).expanduser().suffix.lower() == ".pdfa"
    ):
        return True
    return Path(artifact.display_name).suffix.lower() == ".pdfa"


def _write_tempfile_for_replace(destination: Path, payload: bytes) -> Path:
    fd, raw_temp_path = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temp_path = Path(raw_temp_path)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return temp_path


def _fsync_directory_best_effort(directory: Path) -> None:
    try:
        directory_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


__all__ = [
    "DOCUMENT_TOOL_IDS",
    "DocumentToolRuntime",
    "register_document_tools",
]
