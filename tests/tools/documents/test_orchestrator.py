# SPDX-License-Identifier: Apache-2.0
"""Document orchestrator boundary tests."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from ummaya.tools.documents.adapter_registry import (
    DocumentAdapterRegistry,
    EngineBackedDocumentAdapter,
)
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentIR,
    KnownDocumentFormat,
    ParagraphBlock,
    ToolResultStatus,
)
from ummaya.tools.documents.tool_defs import DocumentInspectRequest, DocumentLocator


class OrchestratorDocxEngine:
    """Small engine double used behind the adapter boundary."""

    document_format = DocumentFormat.docx
    engine_id = "orchestrator-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=[
                ParagraphBlock(
                    block_id="paragraph-001",
                    text=f"orchestrated inspection for {path.name}",
                    source_path="/word/document.xml/p[1]",
                )
            ],
            metadata={"engine_id": self.engine_id},
        )


class RecordingOrchestrator:
    """Runtime injection double proving inspection crosses the orchestrator boundary."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, DocumentFormat | None, str]] = []

    def inspect_local_path(
        self,
        source_path: Path,
        *,
        expected_format: DocumentFormat | None,
        correlation_id: str,
    ) -> object:
        self.calls.append((source_path, expected_format, correlation_id))
        return _inspection_result(correlation_id)


def test_orchestrator_inspects_local_path_through_adapter_registry(tmp_path: Path) -> None:
    from ummaya.tools.documents.orchestrator import DocumentOrchestrator

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    adapter_registry = DocumentAdapterRegistry()
    adapter_registry.register(
        EngineBackedDocumentAdapter(
            adapter_id="orchestrator-docx-adapter",
            known_formats=(KnownDocumentFormat.docx,),
            promoted_formats=(DocumentFormat.docx,),
            inspection_engine=OrchestratorDocxEngine(),
        )
    )
    orchestrator = DocumentOrchestrator(
        adapter_registry=adapter_registry,
        engine_registry=DocumentEngineRegistry(),
    )

    result = orchestrator.inspect_local_path(
        source,
        expected_format=DocumentFormat.docx,
        correlation_id="corr-orchestrator",
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    assert "orchestrated inspection" in result.extraction.paragraphs[0].text
    assert "orchestrator-docx-engine" in result.text_summary


def test_document_runtime_delegates_path_inspection_to_orchestrator(
    tmp_path: Path,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    orchestrator = RecordingOrchestrator()
    runtime = DocumentToolRuntime(
        session_id="session-orchestrator-runtime",
        artifact_root=tmp_path / "artifacts",
        orchestrator=orchestrator,
    )

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-runtime-orchestrator",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.artifact_refs[0].startswith("source-")
    assert orchestrator.calls == [(source, DocumentFormat.docx, "corr-runtime-orchestrator")]


def test_orchestrator_builds_document_ir_from_inspection_result(tmp_path: Path) -> None:
    from ummaya.tools.documents.orchestrator import DocumentOrchestrator

    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    adapter_registry = DocumentAdapterRegistry()
    adapter_registry.register(
        EngineBackedDocumentAdapter(
            adapter_id="orchestrator-docx-adapter",
            known_formats=(KnownDocumentFormat.docx,),
            promoted_formats=(DocumentFormat.docx,),
            inspection_engine=OrchestratorDocxEngine(),
        )
    )
    orchestrator = DocumentOrchestrator(
        adapter_registry=adapter_registry,
        engine_registry=DocumentEngineRegistry(),
    )
    inspect_result = orchestrator.inspect_local_path(
        source,
        expected_format=DocumentFormat.docx,
        correlation_id="corr-ir",
    )
    assert inspect_result.extraction is not None

    document_ir = orchestrator.build_document_ir(
        artifact_id="source-corr-ir",
        document_format=DocumentFormat.docx,
        extraction=inspect_result.extraction,
    )

    assert isinstance(document_ir, DocumentIR)
    assert document_ir.artifact_id == "source-corr-ir"
    assert document_ir.document_format is DocumentFormat.docx
    assert document_ir.source_anchors[0].engine_id == "orchestrator-docx-engine"
    assert document_ir.source_anchors[0].format_path == "/word/document.xml/p[1]"


def test_orchestrator_builds_empty_partial_ir_when_extraction_has_no_blocks() -> None:
    from ummaya.tools.documents.orchestrator import DocumentOrchestrator

    orchestrator = DocumentOrchestrator(engine_registry=DocumentEngineRegistry())

    document_ir = orchestrator.build_document_ir(
        artifact_id="artifact-empty",
        document_format=DocumentFormat.pdf,
        extraction=DocumentExtraction(artifact_id="artifact-empty"),
    )

    assert document_ir.artifact_id == "artifact-empty"
    assert document_ir.source_anchors == ()
    assert document_ir.form_slots == ()
    assert document_ir.protected_ranges == ()


def _inspection_result(correlation_id: str) -> object:
    from ummaya.tools.documents.models import DocumentToolResult

    return DocumentToolResult(
        tool_id="document_inspect",
        correlation_id=correlation_id,
        status=ToolResultStatus.ok,
        extraction=DocumentExtraction(
            artifact_id=correlation_id,
            paragraphs=[
                ParagraphBlock(
                    block_id="paragraph-001",
                    text="runtime delegated through orchestrator",
                    source_path="orchestrator://paragraph/1",
                )
            ],
        ),
        text_summary="Document inspection via recording orchestrator.",
    )


def _write_minimal_docx(path: Path) -> None:
    path.write_bytes(
        _zip_bytes(
            {
                "[Content_Types].xml": b"<Types></Types>",
                "word/document.xml": b"<w:document></w:document>",
            }
        )
    )


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name, payload in entries.items():
            package.writestr(name, payload)
    return buffer.getvalue()
