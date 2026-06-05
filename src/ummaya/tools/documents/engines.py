# SPDX-License-Identifier: Apache-2.0
"""Engine registry for the Public AX document harness."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
)


class DocumentMutationBlockedError(ValueError):
    """Raised when a mutation engine blocks with a typed document reason."""

    def __init__(self, reason: BlockedReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


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
    from ummaya.tools.documents.formats.archive import (  # noqa: PLC0415
        ArchiveContainerDocumentEngine,
    )
    from ummaya.tools.documents.formats.code_file import (  # noqa: PLC0415
        PythonSourceDocumentEngine,
    )
    from ummaya.tools.documents.formats.data_file import (  # noqa: PLC0415
        DataFileDocumentEngine,
    )
    from ummaya.tools.documents.formats.hwp import (  # noqa: PLC0415
        UnhwpReadOnlyInspectionEngine,
    )
    from ummaya.tools.documents.formats.hwpx import (  # noqa: PLC0415
        HwpXPackageTextEngine,
        OwpmlPackageTextEngine,
    )
    from ummaya.tools.documents.formats.odf import (  # noqa: PLC0415
        OdfdoPresentationDocumentEngine,
        OdfdoSpreadsheetDocumentEngine,
        OdfdoTextDocumentEngine,
    )
    from ummaya.tools.documents.formats.ooxml import (  # noqa: PLC0415
        OpenPyxlDocumentEngine,
        PythonDocxDocumentEngine,
        PythonPptxDocumentEngine,
    )
    from ummaya.tools.documents.formats.pdf import PypdfAcroFormEngine  # noqa: PLC0415
    from ummaya.tools.documents.formats.text_web import (  # noqa: PLC0415
        TextWebDocumentEngine,
    )

    registry = DocumentEngineRegistry()
    registry.register(HwpXPackageTextEngine())
    registry.register(OwpmlPackageTextEngine())
    registry.register(UnhwpReadOnlyInspectionEngine())
    registry.register(PythonDocxDocumentEngine())
    registry.register(OpenPyxlDocumentEngine())
    registry.register(PythonPptxDocumentEngine())
    registry.register(PypdfAcroFormEngine())
    registry.register(OdfdoTextDocumentEngine())
    registry.register(OdfdoSpreadsheetDocumentEngine())
    registry.register(OdfdoPresentationDocumentEngine())
    registry.register(TextWebDocumentEngine(DocumentFormat.html))
    registry.register(TextWebDocumentEngine(DocumentFormat.htm))
    registry.register(TextWebDocumentEngine(DocumentFormat.txt))
    registry.register(TextWebDocumentEngine(DocumentFormat.rtf))
    registry.register(TextWebDocumentEngine(DocumentFormat.md))
    registry.register(PythonSourceDocumentEngine())
    for document_format in (
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
        DocumentFormat.hml,
        DocumentFormat.etc,
    ):
        registry.register(DataFileDocumentEngine(document_format))
    for document_format in (
        DocumentFormat.epub,
        DocumentFormat.zip,
        DocumentFormat.seven_z,
        DocumentFormat.tar,
        DocumentFormat.gz,
    ):
        registry.register(ArchiveContainerDocumentEngine(document_format))
    return registry
