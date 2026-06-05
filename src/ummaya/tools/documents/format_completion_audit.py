# SPDX-License-Identifier: Apache-2.0
"""All-format completion audit for the Public AX document harness."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.adapter_registry import (
    DocumentAdapterRegistry,
    build_default_document_adapter_registry,
)
from ummaya.tools.documents.conversion import (
    DocumentConversionRegistry,
    build_default_document_conversion_registry,
)
from ummaya.tools.documents.models import (
    KNOWN_DOCUMENT_FORMAT_FAMILIES,
    DocumentFormat,
    DocumentFormatFamily,
    KnownDocumentFormat,
)

FormatCompletionState = Literal[
    "write_render_save_promoted",
    "derivative_write_render_save_promoted",
    "attachment_derivative_write_render_save_promoted",
    "read_only_promoted",
    "probe_blocked",
    "passive_context_only",
]
FormatCapabilityScope = Literal[
    "document_write_render_save",
    "derivative_document_write_render_save",
    "document_read_only",
    "attachment_context",
    "passive_context",
]

_WRITE_RENDER_SAVE_PROMOTED = frozenset(
    {
        KnownDocumentFormat.hwpx,
        KnownDocumentFormat.owpml,
        KnownDocumentFormat.docx,
        KnownDocumentFormat.xlsx,
        KnownDocumentFormat.pptx,
        KnownDocumentFormat.pdf,
        KnownDocumentFormat.odt,
        KnownDocumentFormat.ods,
        KnownDocumentFormat.odp,
        KnownDocumentFormat.html,
        KnownDocumentFormat.htm,
        KnownDocumentFormat.txt,
        KnownDocumentFormat.rtf,
        KnownDocumentFormat.md,
        KnownDocumentFormat.epub,
        KnownDocumentFormat.csv,
        KnownDocumentFormat.tsv,
        KnownDocumentFormat.xml,
        KnownDocumentFormat.rdf,
        KnownDocumentFormat.ttl,
        KnownDocumentFormat.lod,
        KnownDocumentFormat.json,
        KnownDocumentFormat.jsonl,
        KnownDocumentFormat.yaml,
        KnownDocumentFormat.yml,
        KnownDocumentFormat.geojson,
        KnownDocumentFormat.gpx,
        KnownDocumentFormat.kml,
        KnownDocumentFormat.fasta,
        KnownDocumentFormat.sgml,
        KnownDocumentFormat.dtd,
        KnownDocumentFormat.python,
        KnownDocumentFormat.hml,
        KnownDocumentFormat.zip,
        KnownDocumentFormat.seven_z,
        KnownDocumentFormat.tar,
        KnownDocumentFormat.gz,
        KnownDocumentFormat.etc,
    }
)
_DERIVATIVE_WRITE_RENDER_SAVE_CANDIDATES = frozenset(
    {
        KnownDocumentFormat.hwp,
        KnownDocumentFormat.doc,
        KnownDocumentFormat.xls,
        KnownDocumentFormat.ppt,
    }
)
_READ_ONLY_PROMOTED = frozenset[KnownDocumentFormat]()
_LEGACY_OFFICE_PROBE_BLOCKED = frozenset(
    {
        KnownDocumentFormat.hwp,
        KnownDocumentFormat.doc,
        KnownDocumentFormat.xls,
        KnownDocumentFormat.ppt,
    }
)
_PDFA_CONFORMANCE_PROBE_BLOCKED = frozenset({KnownDocumentFormat.pdfa})
_ARCHIVE_CONTAINER_PROBE_BLOCKED = frozenset[KnownDocumentFormat]()
_IMAGE_ATTACHMENT_PROBE_BLOCKED = frozenset(
    {
        KnownDocumentFormat.png,
        KnownDocumentFormat.jpg,
        KnownDocumentFormat.jpeg,
        KnownDocumentFormat.gif,
        KnownDocumentFormat.tif,
        KnownDocumentFormat.tiff,
        KnownDocumentFormat.bmp,
        KnownDocumentFormat.webp,
    }
)
_GEOSPATIAL_ATTACHMENT_PROBE_BLOCKED = frozenset(
    {
        KnownDocumentFormat.shp,
        KnownDocumentFormat.shx,
        KnownDocumentFormat.dbf,
        KnownDocumentFormat.prj,
        KnownDocumentFormat.stl,
    }
)
_MEDIA_ATTACHMENT_PROBE_BLOCKED = frozenset(
    {
        KnownDocumentFormat.wav,
        KnownDocumentFormat.mp3,
        KnownDocumentFormat.mp4,
    }
)
_PASSIVE_ATTACHMENT_PROBE_BLOCKED = (
    _IMAGE_ATTACHMENT_PROBE_BLOCKED
    | _GEOSPATIAL_ATTACHMENT_PROBE_BLOCKED
    | _MEDIA_ATTACHMENT_PROBE_BLOCKED
)
_ATTACHMENT_DERIVATIVE_WRITE_RENDER_SAVE_PROMOTED = _PASSIVE_ATTACHMENT_PROBE_BLOCKED
_ODF_WRITE_PROMOTED_REASONS = (
    "bounded_odfdo_write_render_save_promoted",
    "libreoffice_layout_oracle_deferred",
)
_TEXT_WEB_WRITE_PROMOTED_REASONS = ("bounded_text_web_write_render_save_promoted",)
_DATA_FILE_WRITE_PROMOTED_REASONS = ("bounded_data_file_write_render_save_promoted",)
_CODE_FILE_WRITE_PROMOTED_REASONS = (
    "bounded_python_source_write_render_save_promoted",
    "python_ast_parse_gate",
    "no_source_code_execution",
)
_PDFA_WRITE_PROMOTED_REASONS = (
    "pdfa_runtime_aliases_pdf_adapter",
    "ghostscript_pdfa2b_export_promoted",
    "verapdf_postwrite_conformance_gate_promoted",
    "pypdf_pdfa_conformance_not_claimed",
)
_ARCHIVE_WRITE_PROMOTED_REASONS = (
    "archive_child_derivative_write_render_save_promoted",
    "no_in_place_archive_mutation",
)
_WRITE_PROMOTED_REASONS_BY_FORMAT: dict[KnownDocumentFormat, tuple[str, ...]] = {
    KnownDocumentFormat.owpml: ("owpml_hwpx_package_alias_write_render_save_promoted",),
    KnownDocumentFormat.odt: _ODF_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.ods: _ODF_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.odp: _ODF_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.html: _TEXT_WEB_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.htm: _TEXT_WEB_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.txt: _TEXT_WEB_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.rtf: _TEXT_WEB_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.md: _TEXT_WEB_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.csv: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.tsv: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.xml: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.rdf: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.ttl: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.lod: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.json: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.jsonl: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.yaml: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.yml: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.geojson: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.gpx: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.kml: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.fasta: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.sgml: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.dtd: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.python: _CODE_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.hml: _DATA_FILE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.epub: _ARCHIVE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.zip: _ARCHIVE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.seven_z: _ARCHIVE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.tar: _ARCHIVE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.gz: _ARCHIVE_WRITE_PROMOTED_REASONS,
    KnownDocumentFormat.etc: _DATA_FILE_WRITE_PROMOTED_REASONS,
}
_HWP_DERIVATIVE_REASONS = (
    "hwp_source_preserved",
    "hwp_to_hwpx_derivative_write_render_save_promoted",
    "direct_hwp_binary_mutation_blocked",
)
_DOC_DERIVATIVE_REASONS = (
    "doc_source_preserved",
    "doc_to_docx_derivative_write_render_save_promoted",
    "macos_textutil_or_libreoffice_bridge",
    "direct_legacy_doc_binary_mutation_blocked",
)
_XLS_DERIVATIVE_REASONS = (
    "xls_source_preserved",
    "xls_to_xlsx_derivative_write_render_save_promoted",
    "microsoft_excel_or_libreoffice_bridge",
    "direct_legacy_xls_binary_mutation_blocked",
)
_PPT_DERIVATIVE_REASONS = (
    "ppt_source_preserved",
    "ppt_to_pptx_derivative_write_render_save_promoted",
    "libreoffice_bridge",
    "direct_legacy_ppt_binary_mutation_blocked",
)
_READ_ONLY_REASONS = ("read_only_inspection_promoted", "direct_mutation_blocked")
_PROBE_BLOCKED_REASONS_BY_FORMAT: dict[KnownDocumentFormat, tuple[str, ...]] = {
    KnownDocumentFormat.hwp: (
        "hwp_to_hwpx_derivative_probe_required",
        "direct_hwp_binary_mutation_blocked",
    ),
    KnownDocumentFormat.doc: (
        "legacy_office_derivative_probe_required",
        "direct_legacy_office_write_blocked",
    ),
    KnownDocumentFormat.xls: (
        "legacy_office_derivative_probe_required",
        "direct_legacy_office_write_blocked",
    ),
    KnownDocumentFormat.ppt: (
        "legacy_office_derivative_probe_required",
        "direct_legacy_office_write_blocked",
    ),
    KnownDocumentFormat.pdfa: (
        "pdfa_runtime_aliases_pdf_adapter",
        "pdfa_conformance_probe_required",
        "pdfa_conformance_write_not_promoted",
        "pypdf_pdfa_conformance_not_claimed",
    ),
}
_IMAGE_ATTACHMENT_DERIVATIVE_REASONS = (
    "attachment_source_preserved",
    "attachment_context_markdown_derivative_write_render_save_promoted",
    "ocr_runtime_deferred",
    "no_in_place_raster_mutation",
)
_GEOSPATIAL_ATTACHMENT_DERIVATIVE_REASONS = (
    "attachment_source_preserved",
    "attachment_context_markdown_derivative_write_render_save_promoted",
    "gdal_feature_extraction_deferred",
    "geospatial_sidecar_lineage_required",
)
_MEDIA_ATTACHMENT_DERIVATIVE_REASONS = (
    "attachment_source_preserved",
    "attachment_context_markdown_derivative_write_render_save_promoted",
    "media_transcription_runtime_deferred",
    "media_original_preservation_required",
)
_ATTACHMENT_DERIVATIVE_REASONS_BY_FORMAT: dict[KnownDocumentFormat, tuple[str, ...]] = {}
_ATTACHMENT_DERIVATIVE_REASONS_BY_FORMAT.update(
    dict.fromkeys(_IMAGE_ATTACHMENT_PROBE_BLOCKED, _IMAGE_ATTACHMENT_DERIVATIVE_REASONS)
)
_ATTACHMENT_DERIVATIVE_REASONS_BY_FORMAT.update(
    dict.fromkeys(
        _GEOSPATIAL_ATTACHMENT_PROBE_BLOCKED,
        _GEOSPATIAL_ATTACHMENT_DERIVATIVE_REASONS,
    )
)
_ATTACHMENT_DERIVATIVE_REASONS_BY_FORMAT.update(
    dict.fromkeys(_MEDIA_ATTACHMENT_PROBE_BLOCKED, _MEDIA_ATTACHMENT_DERIVATIVE_REASONS)
)
_PASSIVE_CONTEXT_REASONS = (
    "passive_context_or_attachment_only",
    "write_render_save_not_document_form",
)


class DocumentFormatCompletionRecord(BaseModel):
    """Completion status for one known document-related extension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    known_format: KnownDocumentFormat
    family: DocumentFormatFamily
    completion_state: FormatCompletionState
    capability_scope: FormatCapabilityScope
    complete: bool
    adapter_id: str = Field(min_length=1)
    promoted_formats: tuple[str, ...]
    reasons: tuple[str, ...]


class DocumentFormatCompletionAuditReport(BaseModel):
    """Aggregate completion status for the public-document harness."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    all_formats_complete: bool
    complete_formats: tuple[str, ...]
    incomplete_formats: tuple[str, ...]
    records: tuple[DocumentFormatCompletionRecord, ...]


def audit_document_format_completion(
    *,
    derivative_promoted_formats: frozenset[KnownDocumentFormat] | None = None,
    pdfa_conformance_promoted: bool | None = None,
    conversion_registry: DocumentConversionRegistry | None = None,
) -> DocumentFormatCompletionAuditReport:
    """Return the current truthful completion state for every known format."""
    registry = build_default_document_adapter_registry()
    promoted_derivatives = (
        _detect_derivative_promoted_formats(conversion_registry=conversion_registry)
        if derivative_promoted_formats is None
        else derivative_promoted_formats
    )
    promoted_pdfa = (
        _detect_pdfa_conformance_promoted()
        if pdfa_conformance_promoted is None
        else pdfa_conformance_promoted
    )
    records = tuple(
        _record_for_known_format(
            known_format,
            registry=registry,
            derivative_promoted_formats=promoted_derivatives,
            pdfa_conformance_promoted=promoted_pdfa,
        )
        for known_format in KnownDocumentFormat
    )
    complete_formats = tuple(record.known_format.value for record in records if record.complete)
    incomplete_formats = tuple(
        record.known_format.value for record in records if not record.complete
    )
    return DocumentFormatCompletionAuditReport(
        all_formats_complete=not incomplete_formats,
        complete_formats=complete_formats,
        incomplete_formats=incomplete_formats,
        records=records,
    )


def _record_for_known_format(
    known_format: KnownDocumentFormat,
    *,
    registry: DocumentAdapterRegistry,
    derivative_promoted_formats: frozenset[KnownDocumentFormat],
    pdfa_conformance_promoted: bool,
) -> DocumentFormatCompletionRecord:
    adapter = registry.require_known(known_format)
    promoted_formats = tuple(document_format.value for document_format in adapter.promoted_formats)
    completion_state = _completion_state_for_known_format(
        known_format,
        derivative_promoted_formats=derivative_promoted_formats,
        pdfa_conformance_promoted=pdfa_conformance_promoted,
    )
    complete = completion_state in {
        "write_render_save_promoted",
        "derivative_write_render_save_promoted",
        "attachment_derivative_write_render_save_promoted",
    }
    return DocumentFormatCompletionRecord(
        known_format=known_format,
        family=KNOWN_DOCUMENT_FORMAT_FAMILIES[known_format],
        completion_state=completion_state,
        capability_scope=_capability_scope_for_state(
            known_format,
            completion_state,
        ),
        complete=complete,
        adapter_id=adapter.adapter_id,
        promoted_formats=promoted_formats,
        reasons=_reasons_for_state(known_format, completion_state),
    )


def _completion_state_for_known_format(
    known_format: KnownDocumentFormat,
    *,
    derivative_promoted_formats: frozenset[KnownDocumentFormat],
    pdfa_conformance_promoted: bool,
) -> FormatCompletionState:
    if known_format in _WRITE_RENDER_SAVE_PROMOTED:
        return "write_render_save_promoted"
    if known_format is KnownDocumentFormat.pdfa and pdfa_conformance_promoted:
        return "write_render_save_promoted"
    if known_format in derivative_promoted_formats:
        return "derivative_write_render_save_promoted"
    if known_format in _ATTACHMENT_DERIVATIVE_WRITE_RENDER_SAVE_PROMOTED:
        return "attachment_derivative_write_render_save_promoted"
    if known_format in _READ_ONLY_PROMOTED:
        return "read_only_promoted"
    if (
        known_format
        in _LEGACY_OFFICE_PROBE_BLOCKED
        | _PDFA_CONFORMANCE_PROBE_BLOCKED
        | _ARCHIVE_CONTAINER_PROBE_BLOCKED
    ):
        return "probe_blocked"
    return "passive_context_only"


def _detect_derivative_promoted_formats(
    *,
    conversion_registry: DocumentConversionRegistry | None,
) -> frozenset[KnownDocumentFormat]:
    registry = conversion_registry or build_default_document_conversion_registry()
    promoted: set[KnownDocumentFormat] = set()
    for known_format, source_format, output_format in (
        (KnownDocumentFormat.hwp, DocumentFormat.hwp, DocumentFormat.hwpx),
        (KnownDocumentFormat.doc, DocumentFormat.doc, DocumentFormat.docx),
        (KnownDocumentFormat.xls, DocumentFormat.xls, DocumentFormat.xlsx),
        (KnownDocumentFormat.ppt, DocumentFormat.ppt, DocumentFormat.pptx),
    ):
        if registry.get(source_format, output_format) is not None:
            promoted.add(known_format)
    return frozenset(promoted & _DERIVATIVE_WRITE_RENDER_SAVE_CANDIDATES)


def _detect_pdfa_conformance_promoted() -> bool:
    from ummaya.tools.documents.pdfa_promotion_probe import (  # noqa: PLC0415
        probe_pdfa_promotion,
    )

    return probe_pdfa_promotion().status == "candidate_available"


def _reasons_for_state(
    known_format: KnownDocumentFormat,
    completion_state: FormatCompletionState,
) -> tuple[str, ...]:
    if completion_state == "write_render_save_promoted":
        if known_format is KnownDocumentFormat.pdfa:
            return _PDFA_WRITE_PROMOTED_REASONS
        return _WRITE_PROMOTED_REASONS_BY_FORMAT.get(
            known_format,
            ("bounded_write_render_save_promoted",),
        )
    if completion_state == "derivative_write_render_save_promoted":
        if known_format is KnownDocumentFormat.doc:
            return _DOC_DERIVATIVE_REASONS
        if known_format is KnownDocumentFormat.xls:
            return _XLS_DERIVATIVE_REASONS
        if known_format is KnownDocumentFormat.ppt:
            return _PPT_DERIVATIVE_REASONS
        return _HWP_DERIVATIVE_REASONS
    if completion_state == "attachment_derivative_write_render_save_promoted":
        return _ATTACHMENT_DERIVATIVE_REASONS_BY_FORMAT[known_format]
    if known_format in _READ_ONLY_PROMOTED:
        return _READ_ONLY_REASONS
    if completion_state == "probe_blocked":
        return _PROBE_BLOCKED_REASONS_BY_FORMAT[known_format]
    return _PASSIVE_CONTEXT_REASONS


def _capability_scope_for_state(
    known_format: KnownDocumentFormat,
    completion_state: FormatCompletionState,
) -> FormatCapabilityScope:
    if completion_state == "write_render_save_promoted":
        return "document_write_render_save"
    if completion_state == "derivative_write_render_save_promoted":
        return "derivative_document_write_render_save"
    if completion_state == "attachment_derivative_write_render_save_promoted":
        return "attachment_context"
    if completion_state == "read_only_promoted":
        return "document_read_only"
    if known_format in _PASSIVE_ATTACHMENT_PROBE_BLOCKED:
        return "attachment_context"
    if completion_state == "passive_context_only":
        return "passive_context"
    return "document_write_render_save"
