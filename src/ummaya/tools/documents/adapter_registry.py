# SPDX-License-Identifier: Apache-2.0
"""Format adapter registry for the single document primitive."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ummaya.tools.documents.engines import DocumentEngineRegistry, DocumentInspectionEngine
from ummaya.tools.documents.formats.base import DocumentFormatAdapter
from ummaya.tools.documents.models import DocumentExtraction, DocumentFormat, KnownDocumentFormat

if TYPE_CHECKING:
    from ummaya.tools.documents.tool_defs import DocumentFieldPatch


_ODF_PROMOTED_FORMATS = (DocumentFormat.odt, DocumentFormat.ods, DocumentFormat.odp)
_TEXT_WEB_PROMOTED_FORMATS = (
    DocumentFormat.html,
    DocumentFormat.htm,
    DocumentFormat.txt,
    DocumentFormat.rtf,
    DocumentFormat.md,
)
_DATA_PROMOTED_FORMATS = (
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
)
_ARCHIVE_PROMOTED_FORMATS = (
    DocumentFormat.epub,
    DocumentFormat.zip,
    DocumentFormat.seven_z,
    DocumentFormat.tar,
    DocumentFormat.gz,
)
_CODE_PROMOTED_FORMATS = (DocumentFormat.python,)


class UnsupportedDocumentAdapterError(LookupError):
    """Raised when no document adapter is registered for a format."""

    def __init__(self, document_format: DocumentFormat | KnownDocumentFormat) -> None:
        super().__init__(f"No document adapter registered for {document_format.value}")
        self.document_format = document_format


class DocumentAdapterRegistry:
    """Session-local registry of format-scoped document adapters."""

    def __init__(self) -> None:
        self._by_adapter_id: dict[str, DocumentFormatAdapter] = {}
        self._by_known_format: dict[KnownDocumentFormat, DocumentFormatAdapter] = {}
        self._by_promoted_format: dict[DocumentFormat, DocumentFormatAdapter] = {}

    def register(self, adapter: DocumentFormatAdapter) -> None:
        """Register one adapter for its known and promoted formats."""
        self._validate_registration(adapter)

        self._by_adapter_id[adapter.adapter_id] = adapter
        for known_format in adapter.known_formats:
            self._by_known_format[known_format] = adapter
        for promoted_format in adapter.promoted_formats:
            self._by_promoted_format[promoted_format] = adapter

    def _validate_registration(self, adapter: DocumentFormatAdapter) -> None:
        """Validate adapter metadata before mutating registry state."""
        if not adapter.adapter_id:
            raise ValueError("adapter_id is required")
        if adapter.adapter_id in self._by_adapter_id:
            raise ValueError(f"adapter_id already registered: {adapter.adapter_id}")
        if not adapter.known_formats:
            raise ValueError("adapter must declare at least one known format")

        self._validate_format_sets(adapter)
        self._validate_no_existing_registration(adapter)

    def _validate_format_sets(self, adapter: DocumentFormatAdapter) -> None:
        """Validate one adapter's own format declarations."""
        if len(set(adapter.known_formats)) != len(adapter.known_formats):
            raise ValueError("adapter known formats must be unique")
        if len(set(adapter.promoted_formats)) != len(adapter.promoted_formats):
            raise ValueError("adapter promoted formats must be unique")

        known_formats = set(adapter.known_formats)
        for promoted_format in adapter.promoted_formats:
            if KnownDocumentFormat(promoted_format.value) not in known_formats:
                raise ValueError("adapter promoted format must also be declared as a known format")

    def _validate_no_existing_registration(self, adapter: DocumentFormatAdapter) -> None:
        """Validate that the registry has no conflicting adapter mapping."""
        for known_format in adapter.known_formats:
            if known_format in self._by_known_format:
                raise ValueError(f"known format already registered: {known_format.value}")

        for promoted_format in adapter.promoted_formats:
            if promoted_format in self._by_promoted_format:
                raise ValueError(f"promoted format already registered: {promoted_format.value}")

    def get_known(
        self,
        document_format: KnownDocumentFormat,
    ) -> DocumentFormatAdapter | None:
        """Return the adapter for a known format, if registered."""
        return self._by_known_format.get(document_format)

    def require_known(self, document_format: KnownDocumentFormat) -> DocumentFormatAdapter:
        """Return the adapter for a known format or fail closed."""
        adapter = self.get_known(document_format)
        if adapter is None:
            raise UnsupportedDocumentAdapterError(document_format)
        return adapter

    def get_promoted(
        self,
        document_format: DocumentFormat,
    ) -> DocumentFormatAdapter | None:
        """Return the adapter for a promoted runtime format, if registered."""
        return self._by_promoted_format.get(document_format)

    def require_promoted(self, document_format: DocumentFormat) -> DocumentFormatAdapter:
        """Return the adapter for a promoted runtime format or fail closed."""
        adapter = self.get_promoted(document_format)
        if adapter is None:
            raise UnsupportedDocumentAdapterError(document_format)
        return adapter


class EngineBackedDocumentAdapter:
    """Adapter wrapper around one promoted inspection engine."""

    def __init__(
        self,
        *,
        adapter_id: str,
        known_formats: tuple[KnownDocumentFormat, ...],
        promoted_formats: tuple[DocumentFormat, ...],
        inspection_engine: DocumentInspectionEngine,
    ) -> None:
        self.adapter_id = adapter_id
        self.known_formats = known_formats
        self.promoted_formats = promoted_formats
        self._inspection_engine = inspection_engine

    @property
    def engine_id(self) -> str:
        """Return the wrapped engine id for diagnostics and result text."""
        return self._inspection_engine.engine_id

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Delegate inspection to the wrapped promoted engine."""
        return self._inspection_engine.inspect(path, artifact_id=artifact_id)

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Return fill patches unchanged for adapters without target aliases."""
        _ = extraction
        return patches


def build_default_document_adapter_registry() -> DocumentAdapterRegistry:
    """Build the default adapter registry for currently promoted engines."""
    from ummaya.tools.documents.formats.archive import (  # noqa: PLC0415
        ArchiveContainerDocumentEngine,
    )
    from ummaya.tools.documents.formats.code_file import (  # noqa: PLC0415
        PythonSourceDocumentAdapter,
    )
    from ummaya.tools.documents.formats.data_file import DataFileDocumentAdapter  # noqa: PLC0415
    from ummaya.tools.documents.formats.hwp import HwpDocumentAdapter  # noqa: PLC0415
    from ummaya.tools.documents.formats.hwpx import HwpXDocumentAdapter  # noqa: PLC0415
    from ummaya.tools.documents.formats.odf import OdfdoDocumentAdapter  # noqa: PLC0415
    from ummaya.tools.documents.formats.ooxml import (  # noqa: PLC0415
        DocxDocumentAdapter,
        OpenPyxlDocumentEngine,
        PptxDocumentAdapter,
        PythonPptxDocumentEngine,
        XlsxDocumentAdapter,
    )
    from ummaya.tools.documents.formats.pdf import PdfDocumentAdapter  # noqa: PLC0415
    from ummaya.tools.documents.formats.text_web import TextWebDocumentAdapter  # noqa: PLC0415

    registry = DocumentAdapterRegistry()
    registry.register(HwpXDocumentAdapter())
    registry.register(HwpDocumentAdapter())
    registry.register(DocxDocumentAdapter())
    registry.register(XlsxDocumentAdapter(OpenPyxlDocumentEngine()))
    registry.register(PptxDocumentAdapter(PythonPptxDocumentEngine()))
    registry.register(PdfDocumentAdapter())
    registry.register(OdfdoDocumentAdapter())
    registry.register(TextWebDocumentAdapter())
    registry.register(DataFileDocumentAdapter())
    registry.register(PythonSourceDocumentAdapter())
    for document_format in _ARCHIVE_PROMOTED_FORMATS:
        _register_engine_backed_adapter(
            registry,
            document_format=document_format,
            engine=ArchiveContainerDocumentEngine(document_format),
        )
    _register_passive_known_only_adapters(registry)
    return registry


def build_document_adapter_registry_from_engine_registry(
    engine_registry: DocumentEngineRegistry,
) -> DocumentAdapterRegistry:
    """Wrap currently registered promoted engines in document adapters."""
    from ummaya.tools.documents.formats.hwp import HwpDocumentAdapter  # noqa: PLC0415
    from ummaya.tools.documents.formats.ooxml import (  # noqa: PLC0415
        PptxDocumentAdapter,
        XlsxDocumentAdapter,
    )
    from ummaya.tools.documents.formats.pdf import PdfDocumentAdapter  # noqa: PLC0415

    registry = DocumentAdapterRegistry()
    if engine_registry.get(DocumentFormat.hwp) is None:
        registry.register(HwpDocumentAdapter())
    if engine_registry.get(DocumentFormat.xlsx) is None:
        registry.register(XlsxDocumentAdapter())
    if engine_registry.get(DocumentFormat.pptx) is None:
        registry.register(PptxDocumentAdapter())
    if engine_registry.get(DocumentFormat.pdf) is None:
        registry.register(PdfDocumentAdapter(promote_default=False))
    registered_family_formats = _register_promoted_family_adapters(registry, engine_registry)
    _register_passive_known_only_adapters(registry)
    for document_format in DocumentFormat:
        engine = engine_registry.get(document_format)
        if engine is None:
            continue
        if document_format in registered_family_formats:
            continue
        _register_engine_backed_adapter(
            registry,
            document_format=document_format,
            engine=engine,
        )
    return registry


def _register_promoted_family_adapters(
    registry: DocumentAdapterRegistry,
    engine_registry: DocumentEngineRegistry,
) -> set[DocumentFormat]:
    """Register multi-format promoted adapters and return their owned formats."""
    registered: set[DocumentFormat] = set()
    if _has_any_engine(engine_registry, _ODF_PROMOTED_FORMATS):
        _register_promoted_odf_adapter(registry, engine_registry)
        registered.update(_ODF_PROMOTED_FORMATS)
    if _has_any_engine(engine_registry, _TEXT_WEB_PROMOTED_FORMATS):
        _register_promoted_text_web_adapter(registry, engine_registry)
        registered.update(_TEXT_WEB_PROMOTED_FORMATS)
    if _has_any_engine(engine_registry, _DATA_PROMOTED_FORMATS):
        _register_promoted_data_adapter(registry, engine_registry)
        registered.update(_DATA_PROMOTED_FORMATS)
    if _has_any_engine(engine_registry, _CODE_PROMOTED_FORMATS):
        _register_promoted_code_adapter(registry, engine_registry)
        registered.update(_CODE_PROMOTED_FORMATS)
    if _has_any_engine(engine_registry, _ARCHIVE_PROMOTED_FORMATS):
        registered.update(_register_promoted_archive_adapters(registry, engine_registry))
    return registered


def _has_any_engine(
    engine_registry: DocumentEngineRegistry,
    document_formats: tuple[DocumentFormat, ...],
) -> bool:
    """Return whether any format in a family has a promoted engine."""
    return any(
        engine_registry.get(document_format) is not None for document_format in document_formats
    )


def _register_passive_known_only_adapters(registry: DocumentAdapterRegistry) -> None:
    """Register known-only passive adapters for non-promoted document families."""
    from ummaya.tools.documents.formats.passive import (  # noqa: PLC0415
        ArchiveDocumentSetAdapter,
        CodeFileDocumentAdapter,
        DataFileDocumentAdapter,
        GeospatialDocumentAdapter,
        ImageScanDocumentAdapter,
        LegacyOfficeDocumentAdapter,
        MediaAssetDocumentAdapter,
        OdfDocumentAdapter,
        TextWebExportAdapter,
    )

    if registry.get_known(KnownDocumentFormat.odt) is None:
        registry.register(OdfDocumentAdapter())
    registry.register(LegacyOfficeDocumentAdapter())
    if registry.get_known(KnownDocumentFormat.csv) is None:
        registry.register(DataFileDocumentAdapter())
    if registry.get_known(KnownDocumentFormat.html) is None:
        registry.register(TextWebExportAdapter())
    if registry.get_known(KnownDocumentFormat.python) is None:
        registry.register(CodeFileDocumentAdapter())
    registry.register(ImageScanDocumentAdapter())
    registry.register(GeospatialDocumentAdapter())
    registry.register(MediaAssetDocumentAdapter())
    remaining_archive_formats = tuple(
        known_format
        for known_format in (
            KnownDocumentFormat.epub,
            KnownDocumentFormat.zip,
            KnownDocumentFormat.seven_z,
            KnownDocumentFormat.tar,
            KnownDocumentFormat.gz,
        )
        if registry.get_known(known_format) is None
    )
    if remaining_archive_formats:
        registry.register(ArchiveDocumentSetAdapter(known_formats=remaining_archive_formats))


def _register_promoted_archive_adapters(
    registry: DocumentAdapterRegistry,
    engine_registry: DocumentEngineRegistry,
) -> set[DocumentFormat]:
    """Register promoted archive engines individually."""
    registered: set[DocumentFormat] = set()
    for document_format in _ARCHIVE_PROMOTED_FORMATS:
        engine = engine_registry.get(document_format)
        if engine is None:
            continue
        _register_engine_backed_adapter(
            registry,
            document_format=document_format,
            engine=engine,
        )
        registered.add(document_format)
    return registered


def _register_promoted_odf_adapter(
    registry: DocumentAdapterRegistry,
    engine_registry: DocumentEngineRegistry,
) -> None:
    """Register one promoted adapter for ODT, ODS, and ODP engines."""
    from ummaya.tools.documents.formats.odf import (  # noqa: PLC0415
        OdfdoDocumentAdapter,
        OdfdoPresentationDocumentEngine,
        OdfdoSpreadsheetDocumentEngine,
        OdfdoTextDocumentEngine,
    )

    text_engine = engine_registry.get(DocumentFormat.odt)
    spreadsheet_engine = engine_registry.get(DocumentFormat.ods)
    presentation_engine = engine_registry.get(DocumentFormat.odp)
    registry.register(
        OdfdoDocumentAdapter(
            text_engine=(text_engine if isinstance(text_engine, OdfdoTextDocumentEngine) else None),
            spreadsheet_engine=(
                spreadsheet_engine
                if isinstance(spreadsheet_engine, OdfdoSpreadsheetDocumentEngine)
                else None
            ),
            presentation_engine=(
                presentation_engine
                if isinstance(presentation_engine, OdfdoPresentationDocumentEngine)
                else None
            ),
        )
    )


def _register_promoted_text_web_adapter(
    registry: DocumentAdapterRegistry,
    engine_registry: DocumentEngineRegistry,
) -> None:
    """Register one promoted adapter for text and web-export engines."""
    from ummaya.tools.documents.formats.text_web import (  # noqa: PLC0415
        TextWebDocumentAdapter,
        TextWebDocumentEngine,
    )

    engines: dict[DocumentFormat, TextWebDocumentEngine] = {}
    for document_format in _TEXT_WEB_PROMOTED_FORMATS:
        engine = engine_registry.get(document_format)
        if isinstance(engine, TextWebDocumentEngine):
            engines[document_format] = engine
    registry.register(TextWebDocumentAdapter(engines=engines or None))


def _register_promoted_data_adapter(
    registry: DocumentAdapterRegistry,
    engine_registry: DocumentEngineRegistry,
) -> None:
    """Register one promoted adapter for public-data engines."""
    from ummaya.tools.documents.formats.data_file import (  # noqa: PLC0415
        DataFileDocumentAdapter,
        DataFileDocumentEngine,
    )

    engines: dict[DocumentFormat, DataFileDocumentEngine] = {}
    for document_format in _DATA_PROMOTED_FORMATS:
        engine = engine_registry.get(document_format)
        if isinstance(engine, DataFileDocumentEngine):
            engines[document_format] = engine
    registry.register(DataFileDocumentAdapter(engines=engines or None))


def _register_promoted_code_adapter(
    registry: DocumentAdapterRegistry,
    engine_registry: DocumentEngineRegistry,
) -> None:
    """Register the promoted adapter for Python source attachments."""
    from ummaya.tools.documents.formats.code_file import (  # noqa: PLC0415
        PythonSourceDocumentAdapter,
        PythonSourceDocumentEngine,
    )

    engine = engine_registry.get(DocumentFormat.python)
    registry.register(
        PythonSourceDocumentAdapter(
            engine=(engine if isinstance(engine, PythonSourceDocumentEngine) else None)
        )
    )


def _register_engine_backed_adapter(
    registry: DocumentAdapterRegistry,
    *,
    document_format: DocumentFormat,
    engine: DocumentInspectionEngine,
) -> None:
    """Register the format adapter that owns one promoted engine."""
    if document_format in {DocumentFormat.hwpx, DocumentFormat.owpml}:
        from ummaya.tools.documents.formats.hwpx import HwpXDocumentAdapter  # noqa: PLC0415

        if registry.get_known(KnownDocumentFormat.hwpx) is not None:
            return
        registry.register(HwpXDocumentAdapter(inspection_engine=engine))
        return
    if document_format is DocumentFormat.docx:
        from ummaya.tools.documents.formats.ooxml import DocxDocumentAdapter  # noqa: PLC0415

        registry.register(DocxDocumentAdapter(inspection_engine=engine))
        return
    if document_format is DocumentFormat.xlsx:
        from ummaya.tools.documents.formats.ooxml import XlsxDocumentAdapter  # noqa: PLC0415

        registry.register(XlsxDocumentAdapter(inspection_engine=engine))
        return
    if document_format is DocumentFormat.pptx:
        from ummaya.tools.documents.formats.ooxml import PptxDocumentAdapter  # noqa: PLC0415

        registry.register(PptxDocumentAdapter(inspection_engine=engine))
        return
    if document_format is DocumentFormat.pdf:
        from ummaya.tools.documents.formats.pdf import PdfDocumentAdapter  # noqa: PLC0415

        registry.register(PdfDocumentAdapter(inspection_engine=engine))
        return
    registry.register(
        EngineBackedDocumentAdapter(
            adapter_id=f"{engine.engine_id}-adapter",
            known_formats=_known_formats_for_promoted_format(document_format),
            promoted_formats=(document_format,),
            inspection_engine=engine,
        )
    )


def _known_formats_for_promoted_format(
    document_format: DocumentFormat,
) -> tuple[KnownDocumentFormat, ...]:
    if document_format in {DocumentFormat.hwpx, DocumentFormat.owpml}:
        return (KnownDocumentFormat.hwpx, KnownDocumentFormat.owpml)
    return (KnownDocumentFormat(document_format.value),)
