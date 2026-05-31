# SPDX-License-Identifier: Apache-2.0
"""Engine registry for the Public AX document harness."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ummaya.tools.documents.models import DocumentExtraction, DocumentFormat, DocumentPatch


class DocumentInspectionEngine(Protocol):
    """Promoted engine that can inspect one document format."""

    document_format: DocumentFormat
    engine_id: str

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Return LLM-readable document IR for a local artifact."""


@runtime_checkable
class DocumentMutationEngine(DocumentInspectionEngine, Protocol):
    """Promoted engine that can apply an ordered patch to one document format."""

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Return derivative bytes after applying the patch."""


class UnsupportedDocumentEngineError(LookupError):
    """Raised when no promoted engine is registered for a format."""

    def __init__(self, document_format: DocumentFormat) -> None:
        super().__init__(f"No promoted document engine registered for {document_format.value}")
        self.document_format = document_format


class DocumentEngineRegistry:
    """Session-local registry of promoted document engines."""

    def __init__(self) -> None:
        self._engines: dict[DocumentFormat, DocumentInspectionEngine] = {}

    def register(self, engine: DocumentInspectionEngine) -> None:
        """Register one promoted engine for its document format."""
        if engine.document_format in self._engines:
            raise ValueError(
                f"document engine already registered for {engine.document_format.value}"
            )
        self._engines[engine.document_format] = engine

    def get(self, document_format: DocumentFormat) -> DocumentInspectionEngine | None:
        """Return the promoted engine for a format, if present."""
        return self._engines.get(document_format)

    def require(self, document_format: DocumentFormat) -> DocumentInspectionEngine:
        """Return the promoted engine or fail closed."""
        engine = self.get(document_format)
        if engine is None:
            raise UnsupportedDocumentEngineError(document_format)
        return engine

    def require_mutation(self, document_format: DocumentFormat) -> DocumentMutationEngine:
        """Return a mutation-capable engine or fail closed."""
        engine = self.require(document_format)
        if not isinstance(engine, DocumentMutationEngine):
            raise UnsupportedDocumentEngineError(document_format)
        return engine


def build_default_document_engine_registry() -> DocumentEngineRegistry:
    """Build the default promoted-engine registry for local document tools."""
    from ummaya.tools.documents.formats.hwpx import (  # noqa: PLC0415
        HwpXPackageTextEngine,
    )
    from ummaya.tools.documents.formats.ooxml import (  # noqa: PLC0415
        PythonDocxInspectionEngine,
    )

    registry = DocumentEngineRegistry()
    registry.register(HwpXPackageTextEngine())
    registry.register(PythonDocxInspectionEngine())
    return registry
