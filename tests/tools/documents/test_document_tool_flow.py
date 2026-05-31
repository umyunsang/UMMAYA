# SPDX-License-Identifier: Apache-2.0
"""Tool-loop regression tests for the Public AX document harness."""

from __future__ import annotations

import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from ummaya.tools.documents.baselines import (
    BaselineField,
    BaselineTableGeometry,
    BaselineTextAnchor,
    ConformanceBaseline,
    ConformanceBaselineCatalog,
)
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FormField,
    ParagraphBlock,
    TableBlock,
    TableCell,
)
from ummaya.tools.executor import ToolExecutor
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


@pytest.mark.asyncio
async def test_document_tools_drive_inspect_to_save_flow_through_executor(tmp_path: Path) -> None:
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

    inspect_result = await executor.invoke_raw(
        "document_inspect",
        {
            "correlation_id": "corr001",
            "document": {"path": str(source), "expected_format": "docx"},
        },
        request_id="req-inspect",
    )
    assert isinstance(inspect_result, dict)
    assert inspect_result["status"] == "ok"
    source_artifact_id = inspect_result["artifact_refs"][0]

    unauthenticated_copy = await executor.invoke_raw(
        "document_copy_for_edit",
        {"correlation_id": "corr002", "document": {"artifact_id": source_artifact_id}},
        request_id="req-copy-auth",
    )
    assert unauthenticated_copy.kind == "error"
    assert unauthenticated_copy.reason.value == "auth_required"

    session_identity = object()
    copy_result = await executor.invoke_raw(
        "document_copy_for_edit",
        {"correlation_id": "corr002", "document": {"artifact_id": source_artifact_id}},
        request_id="req-copy",
        session_identity=session_identity,
    )
    assert isinstance(copy_result, dict)
    assert copy_result["status"] == "ok"
    working_artifact_id = copy_result["artifact_refs"][-1]

    fill_result = await executor.invoke_raw(
        "document_apply_fill",
        {
            "correlation_id": "corr003",
            "document": {"artifact_id": working_artifact_id},
            "patches": [
                {
                    "target_path": "/word/document.xml/field[applicant_name]",
                    "value": "Kim",
                }
            ],
        },
        request_id="req-fill",
        session_identity=session_identity,
    )
    assert isinstance(fill_result, dict)
    assert fill_result["status"] == "ok"
    filled_artifact_id = fill_result["artifact_refs"][-1]

    render_result = await executor.invoke_raw(
        "document_render",
        {"correlation_id": "corr004", "document": {"artifact_id": filled_artifact_id}},
        request_id="req-render",
    )
    assert isinstance(render_result, dict)
    assert render_result["status"] == "ok"
    assert render_result["artifact_refs"][-1].startswith("render-corr004")

    validation_result = await executor.invoke_raw(
        "document_validate_public_form",
        {
            "correlation_id": "corr005",
            "document": {"artifact_id": filled_artifact_id},
            "template_id": "civil-form-docx",
        },
        request_id="req-validate",
    )
    assert isinstance(validation_result, dict)
    assert validation_result["status"] == "ok"
    assert validation_result["validation_report"]["decision"] == "pass"

    save_result = await executor.invoke_raw(
        "document_save",
        {
            "correlation_id": "corr006",
            "document": {"artifact_id": filled_artifact_id},
            "destination_display_name": "civil-form-final.docx",
        },
        request_id="req-save",
        session_identity=session_identity,
    )
    assert isinstance(save_result, dict)
    assert save_result["status"] == "ok"
    assert save_result["artifact_refs"][-1].startswith("export-corr006")


def _write_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")


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
