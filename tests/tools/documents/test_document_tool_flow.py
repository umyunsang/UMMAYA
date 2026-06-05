# SPDX-License-Identifier: Apache-2.0
"""Tool-loop regression tests for the Public AX document harness."""

from __future__ import annotations

import re
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from ummaya.tools.documents.adapter_registry import (
    DocumentAdapterRegistry,
    EngineBackedDocumentAdapter,
)
from ummaya.tools.documents.baselines import (
    BaselineField,
    BaselineTableGeometry,
    BaselineTextAnchor,
    ConformanceBaseline,
    ConformanceBaselineCatalog,
)
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.formats.ooxml import PythonDocxDocumentEngine
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FormField,
    KnownDocumentFormat,
    ParagraphBlock,
    TableBlock,
    TableCell,
    ToolResultStatus,
)
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import (
    DocumentApplyFillRequest,
    DocumentCopyForEditRequest,
    DocumentExtractRequest,
    DocumentFieldPatch,
    DocumentInspectRequest,
    DocumentLocator,
    DocumentPrimitiveRequest,
    DocumentRenderRequest,
    DocumentSaveRequest,
    DocumentValidatePublicFormRequest,
)
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import LookupError as LookupErrorModel
from ummaya.tools.registry import ToolRegistry


class FlowDocxEngine:
    """Small promoted engine double for end-to-end tool-loop tests."""

    document_format = DocumentFormat.docx
    engine_id = "flow-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=[
                ParagraphBlock(
                    block_id="paragraph-001",
                    text=f"Civil application extracted from {path.name}",
                    source_path="/word/document.xml/p[1]",
                )
            ],
            tables=[
                TableBlock(
                    block_id="table-001",
                    source_path="/word/document.xml/tbl[1]",
                    cells=[
                        TableCell(
                            row_index=0,
                            column_index=0,
                            text="Applicant",
                            source_path="/word/document.xml/tbl[1]/tr[1]/tc[1]",
                        )
                    ],
                )
            ],
            fields=[
                FormField(
                    field_id="applicant_name",
                    label="Applicant name",
                    path="/word/document.xml/field[applicant_name]",
                    field_type="text",
                    required=True,
                    current_value="Hong Gil-dong",
                    source_confidence=Decimal("1"),
                )
            ],
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        payload = path.read_bytes()
        marker = "|".join(operation.operation_id for operation in patch.operations)
        return payload + f"\npatched:{marker}".encode()

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        return (f"render:{artifact_id}:{path.name}".encode(),)


class WeeklyDocxEngine(FlowDocxEngine):
    """Engine double with weekly activity fields for autonomous planning."""

    engine_id = "weekly-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            fields=[
                FormField(
                    field_id="week_label",
                    label="주차",
                    path="/word/document.xml/field[week_label]",
                    field_type="text",
                    required=True,
                    current_value="13주차",
                    source_confidence=Decimal("1"),
                ),
                FormField(
                    field_id="activity_period",
                    label="활동기간",
                    path="/word/document.xml/field[activity_period]",
                    field_type="text",
                    required=True,
                    current_value="2026.06.01 ~ 2026.06.07",
                    source_confidence=Decimal("1"),
                ),
            ],
            metadata={"engine_id": self.engine_id},
        )


class IdentityDocxEngine(FlowDocxEngine):
    """Engine double with a sensitive identity field."""

    engine_id = "identity-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            fields=[
                FormField(
                    field_id="resident_registration_number",
                    label="주민등록번호",
                    path="/word/document.xml/field[resident_registration_number]",
                    field_type="text",
                    required=True,
                    current_value=None,
                    source_confidence=Decimal("1"),
                )
            ],
            metadata={"engine_id": self.engine_id},
        )


@pytest.mark.asyncio
async def test_document_primitive_applies_fill_and_returns_rendered_diff(
    tmp_path: Path,
) -> None:
    """A single document primitive call must edit and render review evidence."""
    from ummaya.tools.documents.registry import register_document_tools

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(FlowDocxEngine())
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_document_tools(
        registry,
        executor,
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    result = await executor.invoke_raw(
        "document",
        {
            "correlation_id": "corr-document-primitive",
            "document": {"path": str(source), "expected_format": "docx"},
            "operation": "fill",
            "instruction": "Fill applicant name and show review evidence.",
            "patches": [
                {
                    "target_path": "/word/document.xml/field[applicant_name]",
                    "value": "Kim",
                }
            ],
        },
        request_id="req-document-primitive",
        session_identity=object(),
    )

    assert isinstance(result, dict)
    assert result["tool_id"] == "document"
    assert result["status"] == "ok"
    assert result["diff"]["changes"][0]["after_value"] == "Kim"
    assert result["render_artifacts"]
    assert result["artifact_refs"][0].startswith("source-")
    assert any(ref.startswith("derivative-") for ref in result["artifact_refs"])
    assert any(ref.startswith("render-") for ref in result["artifact_refs"])
    assert [(step["step_id"], step["status"]) for step in result["workflow_steps"]] == [
        ("inspect", "completed"),
        ("field_schema", "completed"),
        ("working_copy", "completed"),
        ("fill_style", "completed"),
        ("diff", "completed"),
        ("render", "completed"),
        ("validate", "pending"),
        ("save", "pending"),
    ]


@pytest.mark.asyncio
async def test_document_primitive_uses_autonomous_plan_when_patches_are_omitted(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import register_document_tools

    source = tmp_path / "weekly-form.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(WeeklyDocxEngine())
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_document_tools(
        registry,
        executor,
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    result = await executor.invoke_raw(
        "document",
        {
            "correlation_id": "corr-document-autonomous-plan",
            "document": {"path": str(source), "expected_format": "docx"},
            "operation": "fill",
            "instruction": "문서 내용을 파악하고 알아서 다음 주차 활동일지로 작성해.",
        },
        request_id="req-document-autonomous-plan",
        session_identity=object(),
    )

    assert isinstance(result, dict)
    assert result["status"] == "ok"
    changed_values = {change["after_value"] for change in result["diff"]["changes"]}
    assert changed_values == {"14주차", "2026.06.08~2026.06.14"}
    assert any(ref.startswith("working-") for ref in result["artifact_refs"])
    assert any(ref.startswith("render-") for ref in result["artifact_refs"])


@pytest.mark.asyncio
async def test_document_primitive_keeps_model_supplied_patch_for_autonomous_instruction(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import register_document_tools

    source = tmp_path / "weekly-form.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(WeeklyDocxEngine())
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_document_tools(
        registry,
        executor,
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    result = await executor.invoke_raw(
        "document",
        {
            "correlation_id": "corr-document-autonomous-broad-body",
            "document": {"path": str(source), "expected_format": "docx"},
            "operation": "fill",
            "instruction": "문서 내용을 파악하고 알아서 다음 주차 활동일지로 작성해.",
            "patches": [{"target_path": "/model/generated/summary", "value": "임의 활동 내용"}],
        },
        request_id="req-document-autonomous-broad-body",
        session_identity=object(),
    )

    assert isinstance(result, dict)
    assert result["status"] == "ok"
    changed_values = {change["after_value"] for change in result["diff"]["changes"]}
    assert changed_values == {"임의 활동 내용"}


@pytest.mark.asyncio
async def test_document_primitive_bounds_internal_copy_reason_for_long_instruction(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import register_document_tools

    source = tmp_path / "weekly-form.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(WeeklyDocxEngine())
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_document_tools(
        registry,
        executor,
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    long_instruction = (
        "문서내용을 파악하고 알아서 다음 주차 활동일지로 작성해줘. "
        "수정 후 변경된 부분을 바로 확인할 수 있게 보여주고 최종적으로 무엇을 "
        "바꿨는지 답변해줘. "
        + "사용자 자연어 요청의 원문은 문서 작성 의도 분석에만 사용해야 합니다. "
        * 8
    )

    result = await executor.invoke_raw(
        "document",
        {
            "correlation_id": "corr-document-long-instruction",
            "document": {"path": str(source), "expected_format": "docx"},
            "operation": "fill",
            "instruction": long_instruction,
        },
        request_id="req-document-long-instruction",
        session_identity=object(),
    )

    assert isinstance(result, dict)
    assert result["status"] == "ok"
    assert result["diff"]["changes"][0]["after_value"] == "14주차"


def test_document_primitive_blocks_protected_plan_before_working_copy(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "identity-form.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(IdentityDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-protected-plan",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-protected-plan",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction="문서 내용을 파악해서 주민등록번호도 알아서 채워줘.",
        )
    )

    assert result.status is ToolResultStatus.needs_input
    assert "resident_registration_number" in result.text_summary
    assert not any(ref.startswith("working-") for ref in result.artifact_refs)
    assert not any(ref.startswith("derivative-") for ref in result.artifact_refs)


def test_document_runtime_inspect_routes_through_adapter_registry(tmp_path: Path) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    adapter_registry = DocumentAdapterRegistry()
    adapter_registry.register(
        EngineBackedDocumentAdapter(
            adapter_id="flow-docx-adapter",
            known_formats=(KnownDocumentFormat.docx,),
            promoted_formats=(DocumentFormat.docx,),
            inspection_engine=FlowDocxEngine(),
        )
    )

    runtime = DocumentToolRuntime(
        session_id="session-doc-adapter-routing",
        artifact_root=tmp_path / "artifacts",
        engine_registry=DocumentEngineRegistry(),
        adapter_registry=adapter_registry,
        baseline_catalog=_baseline_catalog(),
    )

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-adapter-routing",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    assert "Civil application extracted" in " ".join(
        block.text for block in result.extraction.paragraphs
    )


@pytest.mark.asyncio
async def test_document_internal_stages_drive_inspect_to_save_flow(tmp_path: Path) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime, register_document_tools

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(FlowDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-flow",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_document_tools(registry, executor, runtime=runtime)

    unauthenticated_document_result = await executor.invoke_raw(
        "document",
        {
            "correlation_id": "corr-auth",
            "document": {"path": str(source), "expected_format": "docx"},
            "operation": "inspect",
            "instruction": "Inspect this local document.",
        },
        request_id="req-document-auth",
    )
    assert isinstance(unauthenticated_document_result, LookupErrorModel)
    assert unauthenticated_document_result.kind == "error"
    assert unauthenticated_document_result.reason.value == "auth_required"

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr001",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok
    assert inspect_result.artifact_refs
    source_artifact_id = inspect_result.artifact_refs[0]

    ambiguous_locator_result = runtime.extract(
        DocumentExtractRequest(
            correlation_id="corr001b",
            document=DocumentLocator(
                artifact_id=source_artifact_id,
                path=str(source.with_name("unexpected-civil-form.docx")),
                expected_format=DocumentFormat.docx,
            ),
            include_tables=True,
            include_images=True,
            include_fields=True,
        )
    )
    assert ambiguous_locator_result.status is ToolResultStatus.needs_input
    assert "artifact_id" in ambiguous_locator_result.text_summary
    assert "path" in ambiguous_locator_result.text_summary

    path_only_copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="corr001c",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )
    assert path_only_copy_result.status is ToolResultStatus.needs_input
    assert "document_inspect" in path_only_copy_result.text_summary
    assert "artifact_id" in path_only_copy_result.text_summary

    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="corr002",
            document=DocumentLocator(artifact_id=source_artifact_id),
        )
    )
    assert copy_result.status is ToolResultStatus.ok
    assert copy_result.artifact_refs
    working_artifact_id = copy_result.artifact_refs[-1]

    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="corr003",
            document=DocumentLocator(artifact_id=working_artifact_id),
            patches=(_field_patch("/word/document.xml/field[applicant_name]", "Kim"),),
        )
    )
    assert fill_result.status is ToolResultStatus.ok
    assert fill_result.artifact_refs
    assert fill_result.diff is not None
    filled_artifact_id = fill_result.artifact_refs[-1]
    assert fill_result.diff.source_artifact_id == working_artifact_id
    assert fill_result.diff.derivative_artifact_id == filled_artifact_id
    assert fill_result.diff.changes[0].change_type == "field"
    assert fill_result.diff.changes[0].target_path == ("/word/document.xml/field[applicant_name]")
    assert fill_result.diff.changes[0].after_value == "Kim"
    assert fill_result.diff.diff_id.startswith("diff-")
    assert len(fill_result.diff.diff_sha256) == 64
    assert fill_result.diff.resource_ref.startswith("document-diff://")
    assert [(step.step_id, step.status.value) for step in fill_result.workflow_steps] == [
        ("inspect", "completed"),
        ("field_schema", "completed"),
        ("working_copy", "completed"),
        ("fill_style", "completed"),
        ("diff", "completed"),
        ("render", "pending"),
        ("validate", "pending"),
        ("save", "pending"),
    ]

    render_result = runtime.render(
        DocumentRenderRequest(
            correlation_id="corr004",
            document=DocumentLocator(artifact_id=filled_artifact_id),
        )
    )
    assert render_result.status is ToolResultStatus.ok
    assert render_result.artifact_refs[-1].startswith("render-corr004")
    render_step = next(step for step in render_result.workflow_steps if step.step_id == "render")
    assert render_step.artifact_id is not None
    assert render_step.artifact_id.startswith("render-corr004")
    assert render_step.artifact_sha256 is not None
    assert len(render_step.artifact_sha256) == 64
    assert ("render", "completed") in [
        (step.step_id, step.status.value) for step in render_result.workflow_steps
    ]

    validation_result = runtime.validate_public_form(
        DocumentValidatePublicFormRequest(
            correlation_id="corr005",
            document=DocumentLocator(artifact_id=filled_artifact_id),
            template_id="civil-form-docx",
        )
    )
    assert validation_result.status is ToolResultStatus.ok
    assert validation_result.validation_report is not None
    assert validation_result.validation_report.decision == "pass"

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="corr006",
            document=DocumentLocator(artifact_id=filled_artifact_id),
            destination_display_name="civil-form-final.docx",
        )
    )
    assert save_result.status is ToolResultStatus.ok
    assert save_result.artifact_refs[-1].startswith("export-corr006")
    assert save_result.diff is not None
    assert save_result.diff.diff_id == fill_result.diff.diff_id
    assert save_result.diff.diff_sha256 == fill_result.diff.diff_sha256
    assert [(step.step_id, step.status.value) for step in save_result.workflow_steps] == [
        ("inspect", "completed"),
        ("field_schema", "completed"),
        ("working_copy", "completed"),
        ("fill_style", "completed"),
        ("diff", "completed"),
        ("render", "pending"),
        ("validate", "pending"),
        ("save", "completed"),
    ]


def test_document_render_rehydrates_artifact_and_diff_for_same_session(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    artifact_root = tmp_path / "artifacts"
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(FlowDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-resume",
        artifact_root=artifact_root,
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-resume-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok
    source_artifact_id = inspect_result.artifact_refs[0]
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="corr-resume-copy",
            document=DocumentLocator(artifact_id=source_artifact_id),
        )
    )
    assert copy_result.status is ToolResultStatus.ok
    working_artifact_id = copy_result.artifact_refs[-1]
    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="corr-resume-fill",
            document=DocumentLocator(artifact_id=working_artifact_id),
            patches=(_field_patch("/word/document.xml/field[applicant_name]", "Kim"),),
        )
    )
    assert fill_result.status is ToolResultStatus.ok
    assert fill_result.diff is not None
    filled_artifact_id = fill_result.artifact_refs[-1]

    resumed_runtime = DocumentToolRuntime(
        session_id="session-doc-resume",
        artifact_root=artifact_root,
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )
    render_result = resumed_runtime.render(
        DocumentRenderRequest(
            correlation_id="corr-resume-render",
            document=DocumentLocator(artifact_id=filled_artifact_id),
        )
    )

    assert render_result.status is ToolResultStatus.ok
    assert render_result.diff is not None
    assert render_result.diff.diff_id == fill_result.diff.diff_id
    assert render_result.diff.derivative_artifact_id == filled_artifact_id
    assert render_result.artifact_refs[-1].startswith("render-corr-resume-render")
    workflow_artifacts = {step.step_id: step.artifact_id for step in render_result.workflow_steps}
    assert workflow_artifacts["working_copy"] == working_artifact_id
    assert workflow_artifacts["fill_style"] == filled_artifact_id
    assert workflow_artifacts["diff"] == filled_artifact_id
    render_artifact_id = workflow_artifacts["render"]
    assert render_artifact_id is not None
    assert render_artifact_id.startswith("render-corr-resume-render")


def test_document_inspect_missing_local_path_returns_needs_input_with_candidates(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    requested = downloads / "SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식.hwpx"
    template = downloads / "SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx"
    generated = downloads / (
        "SW중심대학사업 현장미러형연계프로젝트 주간활동일지(컴퓨터공학과_GovOn)_13주차_테스트.hwpx"
    )
    template.write_bytes(b"not-a-real-hwpx")
    generated.write_bytes(b"not-a-real-hwpx")
    runtime = DocumentToolRuntime(
        session_id="session-doc-missing-path",
        artifact_root=tmp_path / "artifacts",
    )

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="weekly_activity_log_13th_week",
            document=DocumentLocator(path=str(requested), expected_format=DocumentFormat.hwpx),
        )
    )

    assert result.status is ToolResultStatus.needs_input
    assert result.blocked_reason is None
    assert "Document path does not exist" in result.text_summary
    assert str(template) in result.text_summary
    assert str(generated) in result.text_summary
    assert "unsupported_format" not in result.text_summary


def test_document_inspect_reuses_existing_source_artifact_for_repeated_path_call(
    tmp_path: Path,
) -> None:
    """Repeated model retries for the same path must not raise artifact conflicts."""
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "official-form.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(FlowDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-repeated-source",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )
    request = DocumentInspectRequest(
        correlation_id="same-source-correlation",
        document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
    )

    first = runtime.inspect(request)
    second = runtime.inspect(request)

    assert first.status is ToolResultStatus.ok
    assert second.status is ToolResultStatus.ok
    assert first.artifact_refs == second.artifact_refs
    assert second.text_summary == first.text_summary


def test_document_generated_artifact_ids_survive_model_correlation_text(
    tmp_path: Path,
) -> None:
    """Model-written Korean correlation text must not become raw artifact IDs."""
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "weekly-log.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(FlowDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-correlation-text",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="13주차 문서 작성",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok
    assert inspect_result.correlation_id == "13주차 문서 작성"
    source_artifact_id = inspect_result.artifact_refs[0]
    assert source_artifact_id.startswith("source-")
    assert _SAFE_ARTIFACT_ID_RE.fullmatch(source_artifact_id)
    assert " " not in source_artifact_id
    assert "주차" not in source_artifact_id

    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="13주차 편집본 생성",
            document=DocumentLocator(artifact_id=source_artifact_id),
        )
    )
    assert copy_result.status is ToolResultStatus.ok
    working_artifact_id = copy_result.artifact_refs[-1]
    assert working_artifact_id.startswith("working-")
    assert _SAFE_ARTIFACT_ID_RE.fullmatch(working_artifact_id)

    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="13주차 값 입력",
            document=DocumentLocator(artifact_id=working_artifact_id),
            patches=(_field_patch("/word/document.xml/field[applicant_name]", "Kim"),),
        )
    )
    assert fill_result.status is ToolResultStatus.ok
    derivative_artifact_id = fill_result.artifact_refs[-1]
    assert derivative_artifact_id.startswith("derivative-")
    assert _SAFE_ARTIFACT_ID_RE.fullmatch(derivative_artifact_id)

    render_result = runtime.render(
        DocumentRenderRequest(
            correlation_id="13주차 렌더",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
        )
    )
    assert render_result.status is ToolResultStatus.ok
    render_artifact_id = render_result.artifact_refs[-1]
    assert render_artifact_id.startswith("render-")
    assert _SAFE_ARTIFACT_ID_RE.fullmatch(render_artifact_id)

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="13주차 저장",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name="weekly-log-final.docx",
        )
    )
    assert save_result.status is ToolResultStatus.ok
    export_artifact_id = save_result.artifact_refs[-1]
    assert export_artifact_id.startswith("export-")
    assert _SAFE_ARTIFACT_ID_RE.fullmatch(export_artifact_id)


def test_document_save_promotes_reviewed_derivative_to_explicit_local_path(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    export_path = tmp_path / "exports" / "civil-form-final.docx"
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(FlowDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-local-export",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="local-export-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok
    source_artifact_id = inspect_result.artifact_refs[-1]
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="local-export-copy",
            document=DocumentLocator(artifact_id=source_artifact_id),
        )
    )
    assert copy_result.status is ToolResultStatus.ok
    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="local-export-fill",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
            patches=(_field_patch("/word/document.xml/field[applicant_name]", "Kim"),),
        )
    )
    assert fill_result.status is ToolResultStatus.ok
    derivative_artifact_id = fill_result.artifact_refs[-1]

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="local-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name="civil-form-final.docx",
            destination_path=str(export_path),
        )
    )

    assert save_result.status is ToolResultStatus.ok
    assert export_path.is_file()
    assert save_result.saved_exports
    saved_export = save_result.saved_exports[0]
    assert saved_export.export_artifact_id == save_result.artifact_refs[-1]
    assert saved_export.local_path == export_path
    assert saved_export.sha256 == _sha256(export_path)
    assert export_path.read_bytes().endswith(b"patched:fill-001")
    assert (
        next(step for step in save_result.workflow_steps if step.step_id == "save").status.value
        == "completed"
    )


def test_document_primitive_saves_to_destination_path_without_separate_stage(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "weekly-form.docx"
    _write_minimal_docx(source)
    export_path = tmp_path / "exports" / "weekly-form-14.docx"
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(WeeklyDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-primitive-local-export",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="primitive-local-export",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction="문서내용을 파악하고 알아서 다음 주차 활동일지로 작성한 뒤 저장해줘.",
            destination_path=str(export_path),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert export_path.is_file()
    assert result.diff is not None
    assert result.diff.changes[0].after_value == "14주차"
    assert result.saved_exports
    assert result.saved_exports[0].local_path == export_path
    assert result.saved_exports[0].sha256 == _sha256(export_path)


def test_document_primitive_derives_explicit_save_path_from_instruction(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "weekly-form.docx"
    _write_minimal_docx(source)
    export_path = tmp_path / "exports" / "weekly-form-14.docx"
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(WeeklyDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-primitive-instruction-export",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="primitive-instruction-export",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction=(
                "문서내용을 파악하고 알아서 다음 주차 활동일지로 작성한 뒤 "
                f"{export_path} 로 저장해줘."
            ),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert export_path.is_file()
    assert result.saved_exports
    assert result.saved_exports[0].local_path == export_path
    assert (
        next(step for step in result.workflow_steps if step.step_id == "save").status.value
        == "completed"
    )


def test_document_primitive_autonomous_docx_fill_style_save_to_destination_path(
    tmp_path: Path,
) -> None:
    source = _copy_seoul_culture_docx(tmp_path)
    export_path = tmp_path / "exports" / "seoul-culture-filled.docx"
    runtime = _real_docx_runtime(tmp_path)

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="primitive-docx-fill-style-save",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction=(
                "문서내용을 파악하고 팀명 옆 빈칸에는 GovOn Design AX를 넣어줘. "
                "Malgun Gothic 12pt bold, 글자색 1F4E79, 배경색 FFF2CC, 가운데 정렬로 맞추고 "
                f"저장은 {export_path} 로 해줘."
            ),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert export_path.is_file()
    assert result.saved_exports
    assert result.saved_exports[0].local_path == export_path
    assert result.saved_exports[0].sha256 == _sha256(export_path)
    assert result.render_artifacts
    assert result.diff is not None
    observed_changes = [
        (change.change_type, change.display_label, change.after_value)
        for change in result.diff.changes
    ]
    assert observed_changes == [
        ("table_cell", "팀명", "GovOn Design AX"),
        ("style", "팀명", "GovOn Design AX"),
    ]
    assert sum(ref.startswith("working-") for ref in result.artifact_refs) == 1
    assert any(ref.startswith("derivative-") for ref in result.artifact_refs)
    assert _saved_docx_cell_text(export_path, table_index=0, row_index=2, cell_index=1) == (
        "GovOn Design AX"
    )
    document_xml = _docx_xml(export_path, "word/document.xml")
    assert 'w:eastAsia="Malgun Gothic"' in document_xml
    styles_xml = _docx_xml(export_path, "word/styles.xml")
    assert 'w:eastAsia="Malgun Gothic"' not in styles_xml
    assert 'w:sz w:val="24"' in document_xml
    assert "w:b" in document_xml
    assert 'w:color w:val="1F4E79"' in document_xml
    assert 'w:fill="FFF2CC"' in document_xml
    assert 'w:jc w:val="center"' in document_xml
    assert (
        next(step for step in result.workflow_steps if step.step_id == "save").status.value
        == "completed"
    )


def test_document_primitive_combined_style_does_not_create_second_working_copy(
    tmp_path: Path,
) -> None:
    source = _copy_seoul_culture_docx(tmp_path)
    runtime = _real_docx_runtime(tmp_path)

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="primitive-docx-single-working-copy",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction=(
                "문서내용을 파악하고 팀명 옆 빈칸에는 GovOn Design AX를 넣어줘. "
                "Malgun Gothic 12pt bold로 맞춰줘."
            ),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert sum(ref.startswith("working-") for ref in result.artifact_refs) == 1
    assert sum(ref.startswith("derivative-") for ref in result.artifact_refs) == 1
    assert result.diff is not None
    assert [change.change_type for change in result.diff.changes] == ["table_cell", "style"]


def test_document_primitive_save_claim_requires_saved_export_file(tmp_path: Path) -> None:
    source = _copy_seoul_culture_docx(tmp_path)
    runtime = _real_docx_runtime(tmp_path)

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="primitive-docx-no-save-claim",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction=(
                "문서내용을 파악하고 팀명 옆 빈칸에는 GovOn Design AX를 넣어줘. "
                "Malgun Gothic 12pt bold로 맞춰줘."
            ),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert not result.saved_exports
    assert (
        next(step for step in result.workflow_steps if step.step_id == "save").status.value
        == "pending"
    )


def test_document_primitive_combined_style_blocks_destination_extension_mismatch(
    tmp_path: Path,
) -> None:
    source = _copy_seoul_culture_docx(tmp_path)
    mismatched_export_path = tmp_path / "exports" / "seoul-culture-filled.pdf"
    runtime = _real_docx_runtime(tmp_path)

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="primitive-docx-fill-style-save-mismatch",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction=(
                "문서내용을 파악하고 팀명 옆 빈칸에는 GovOn Design AX를 넣어줘. "
                "Malgun Gothic 12pt bold로 맞추고 "
                f"저장은 {mismatched_export_path} 로 해줘."
            ),
        )
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason == "extension_mismatch"
    assert not mismatched_export_path.exists()
    assert not result.saved_exports
    assert not any(ref.startswith("export-") for ref in result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))
    assert not any(
        step.step_id == "save"
        and (
            step.status.value == "completed"
            or (step.artifact_id is not None and step.artifact_id.startswith("export-"))
        )
        for step in result.workflow_steps
    )


def test_document_save_blocks_explicit_local_path_extension_mismatch(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(FlowDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-local-export-mismatch",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )
    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="local-export-mismatch-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="local-export-mismatch-copy",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[-1]),
        )
    )
    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="local-export-mismatch-fill",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
            patches=(_field_patch("/word/document.xml/field[applicant_name]", "Kim"),),
        )
    )

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="local-export-mismatch-save",
            document=DocumentLocator(artifact_id=fill_result.artifact_refs[-1]),
            destination_display_name="civil-form-final.docx",
            destination_path=str(tmp_path / "exports" / "civil-form-final.pdf"),
        )
    )

    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "extension_mismatch"
    assert not (tmp_path / "exports" / "civil-form-final.pdf").exists()
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))
    assert not any(
        step.step_id == "save"
        and (
            step.status.value == "completed"
            or (step.artifact_id is not None and step.artifact_id.startswith("export-"))
        )
        for step in save_result.workflow_steps
    )


_SAFE_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_PUBLIC_FORM_FIXTURE_DIR = (
    Path(__file__).parents[2] / "fixtures" / "documents" / "public_forms" / "sources"
)
_SEOUL_CULTURE_DOCX = _PUBLIC_FORM_FIXTURE_DIR / "seoul-culture-application-plan.docx"


def _write_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field_patch(target_path: str, value: str) -> DocumentFieldPatch:
    return DocumentFieldPatch(target_path=target_path, value=value)


def _copy_seoul_culture_docx(tmp_path: Path) -> Path:
    assert _SEOUL_CULTURE_DOCX.exists()
    destination = tmp_path / _SEOUL_CULTURE_DOCX.name
    destination.write_bytes(_SEOUL_CULTURE_DOCX.read_bytes())
    return destination


def _real_docx_runtime(tmp_path: Path) -> DocumentToolRuntime:
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(PythonDocxDocumentEngine())
    return DocumentToolRuntime(
        session_id="session-docx-runtime-orchestration",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )


def _docx_xml(path: Path, package_path: str) -> str:
    with zipfile.ZipFile(path) as package:
        return package.read(package_path).decode("utf-8")


def _saved_docx_cell_text(
    path: Path,
    *,
    table_index: int,
    row_index: int,
    cell_index: int,
) -> str:
    document = PythonDocxDocumentEngine().inspect(path, artifact_id="saved-docx")
    table = document.tables[table_index]
    matching_cell = next(
        cell
        for cell in table.cells
        if cell.row_index == row_index and cell.column_index == cell_index
    )
    return matching_cell.text


def _baseline_catalog() -> ConformanceBaselineCatalog:
    return ConformanceBaselineCatalog(
        version=1,
        catalog_id="document-flow-baseline",
        source_policy="offline_fixtures_only",
        live_network_allowed=False,
        baselines=(
            ConformanceBaseline(
                template_id="civil-form-docx",
                schema_id="civil-form-docx-flow-v1",
                format=DocumentFormat.docx,
                authoritative_standard="ECMA-376 Office Open XML",
                authority_refs=("tests/tools/documents/test_document_tool_flow.py",),
                supports_conformance=True,
                required_fields=(
                    BaselineField(
                        field_id="applicant_name",
                        label="Applicant name",
                        path="/word/document.xml/field[applicant_name]",
                    ),
                ),
                protected_text=(
                    BaselineTextAnchor(
                        text="Civil application extracted from derivative-corr003.docx",
                        anchor="/word/document.xml/p[1]",
                    ),
                ),
                table_geometries=(
                    BaselineTableGeometry(
                        table_id="table-001",
                        anchor="/word/document.xml/tbl[1]",
                        rows=1,
                        columns=1,
                    ),
                ),
            ),
        ),
    )
