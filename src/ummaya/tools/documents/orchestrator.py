# SPDX-License-Identifier: Apache-2.0
"""Internal orchestration boundary for the model-facing document primitive."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ummaya.tools.documents.adapter_registry import (
    DocumentAdapterRegistry,
    build_document_adapter_registry_from_engine_registry,
)
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.inspection import inspect_document
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentIR,
    DocumentToolResult,
)


class DocumentInspectionOrchestrator(Protocol):
    """Minimal inspection boundary consumed by the document runtime."""

    def inspect_local_path(
        self,
        source_path: Path,
        *,
        expected_format: DocumentFormat | None,
        correlation_id: str,
    ) -> DocumentToolResult:
        """Inspect one local document path through adapter selection."""

    def build_document_ir(
        self,
        *,
        artifact_id: str,
        document_format: DocumentFormat,
        extraction: DocumentExtraction,
    ) -> DocumentIR:
        """Normalize inspected document content into planner-facing IR."""


class DocumentOrchestrator:
    """Coordinate intake, format selection, and adapter-backed inspection."""

    def __init__(
        self,
        *,
        adapter_registry: DocumentAdapterRegistry | None = None,
        engine_registry: DocumentEngineRegistry | None = None,
    ) -> None:
        self.engine_registry = engine_registry or DocumentEngineRegistry()
        self.adapter_registry = (
            adapter_registry
            or build_document_adapter_registry_from_engine_registry(self.engine_registry)
        )

    def inspect_local_path(
        self,
        source_path: Path,
        *,
        expected_format: DocumentFormat | None,
        correlation_id: str,
    ) -> DocumentToolResult:
        """Inspect a local source document without mutating it."""
        return inspect_document(
            source_path,
            expected_format=expected_format,
            engine_registry=self.engine_registry,
            adapter_registry=self.adapter_registry,
        )

    def build_document_ir(
        self,
        *,
        artifact_id: str,
        document_format: DocumentFormat,
        extraction: DocumentExtraction,
    ) -> DocumentIR:
        """Normalize inspected document content into planner-facing IR."""
        return DocumentIR.from_extraction(
            artifact_id=artifact_id,
            document_format=document_format,
            extraction=extraction,
            engine_id=_engine_id_for_extraction(extraction),
        )


def _engine_id_for_extraction(extraction: DocumentExtraction) -> str:
    for key in ("engine_id", "adapter_id", "format_adapter_id"):
        value = extraction.metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return "document-orchestrator"
