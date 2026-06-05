# SPDX-License-Identifier: Apache-2.0
"""All-format completion audit for the public document harness."""

from __future__ import annotations

from ummaya.tools.documents.format_completion_audit import audit_document_format_completion
from ummaya.tools.documents.models import KnownDocumentFormat


def test_audit_reports_all_known_formats_and_does_not_claim_complete_coverage() -> None:
    report = audit_document_format_completion(
        derivative_promoted_formats=frozenset({KnownDocumentFormat.hwp, KnownDocumentFormat.doc}),
        pdfa_conformance_promoted=False,
    )

    assert len(report.records) == len(KnownDocumentFormat)
    assert not report.all_formats_complete
    assert report.complete_formats == (
        "hwpx",
        "hwp",
        "hml",
        "owpml",
        "docx",
        "xlsx",
        "pptx",
        "doc",
        "pdf",
        "odt",
        "ods",
        "odp",
        "html",
        "htm",
        "txt",
        "rtf",
        "md",
        "epub",
        "csv",
        "tsv",
        "xml",
        "rdf",
        "ttl",
        "lod",
        "json",
        "jsonl",
        "yaml",
        "yml",
        "geojson",
        "gpx",
        "kml",
        "fasta",
        "sgml",
        "dtd",
        "py",
        "png",
        "jpg",
        "jpeg",
        "gif",
        "tif",
        "tiff",
        "bmp",
        "webp",
        "shp",
        "shx",
        "dbf",
        "prj",
        "stl",
        "wav",
        "mp3",
        "mp4",
        "zip",
        "7z",
        "tar",
        "gz",
        "etc",
    )
    assert "hwp" not in report.incomplete_formats
    assert "odt" not in report.incomplete_formats
    assert "doc" not in report.incomplete_formats
    assert "csv" not in report.incomplete_formats
    assert "py" not in report.incomplete_formats
    assert "png" not in report.incomplete_formats
    assert "mp3" not in report.incomplete_formats
    assert "shp" not in report.incomplete_formats
    assert "zip" not in report.incomplete_formats
    assert "7z" not in report.incomplete_formats


def test_audit_classifies_promoted_read_only_probe_and_passive_families() -> None:
    records = {
        record.known_format: record
        for record in audit_document_format_completion(
            derivative_promoted_formats=frozenset(
                {KnownDocumentFormat.hwp, KnownDocumentFormat.doc}
            ),
            pdfa_conformance_promoted=False,
        ).records
    }

    assert records[KnownDocumentFormat.hwpx].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.hwpx].capability_scope == "document_write_render_save"
    assert records[KnownDocumentFormat.owpml].completion_state == "write_render_save_promoted"
    assert (
        "owpml_hwpx_package_alias_write_render_save_promoted"
        in records[KnownDocumentFormat.owpml].reasons
    )
    assert records[KnownDocumentFormat.docx].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.xlsx].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.pptx].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.pdf].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.odt].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.ods].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.odp].completion_state == "write_render_save_promoted"
    assert "bounded_odfdo_write_render_save_promoted" in records[KnownDocumentFormat.odt].reasons
    assert "libreoffice_layout_oracle_deferred" in records[KnownDocumentFormat.odt].reasons
    assert records[KnownDocumentFormat.html].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.htm].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.txt].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.rtf].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.md].completion_state == "write_render_save_promoted"
    assert (
        "bounded_text_web_write_render_save_promoted" in records[KnownDocumentFormat.html].reasons
    )
    assert records[KnownDocumentFormat.epub].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.zip].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.seven_z].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.tar].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.gz].completion_state == "write_render_save_promoted"
    assert (
        "archive_child_derivative_write_render_save_promoted"
        in records[KnownDocumentFormat.zip].reasons
    )
    assert (
        "archive_child_derivative_write_render_save_promoted"
        in records[KnownDocumentFormat.seven_z].reasons
    )
    assert records[KnownDocumentFormat.csv].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.json].completion_state == "write_render_save_promoted"
    assert records[KnownDocumentFormat.xml].completion_state == "write_render_save_promoted"
    assert (
        "bounded_data_file_write_render_save_promoted" in records[KnownDocumentFormat.csv].reasons
    )

    assert (
        records[KnownDocumentFormat.hwp].completion_state == "derivative_write_render_save_promoted"
    )
    assert (
        records[KnownDocumentFormat.hwp].capability_scope == "derivative_document_write_render_save"
    )
    assert "hwp_source_preserved" in records[KnownDocumentFormat.hwp].reasons
    assert "direct_hwp_binary_mutation_blocked" in records[KnownDocumentFormat.hwp].reasons

    assert (
        records[KnownDocumentFormat.doc].completion_state == "derivative_write_render_save_promoted"
    )
    assert records[KnownDocumentFormat.xls].completion_state == "probe_blocked"
    assert records[KnownDocumentFormat.ppt].completion_state == "probe_blocked"
    assert "doc_source_preserved" in records[KnownDocumentFormat.doc].reasons
    assert (
        "doc_to_docx_derivative_write_render_save_promoted"
        in records[KnownDocumentFormat.doc].reasons
    )
    assert records[KnownDocumentFormat.pdfa].completion_state == "probe_blocked"
    assert records[KnownDocumentFormat.pdfa].capability_scope == "document_write_render_save"
    assert "pdfa_conformance_probe_required" in records[KnownDocumentFormat.pdfa].reasons
    assert "pypdf_pdfa_conformance_not_claimed" in records[KnownDocumentFormat.pdfa].reasons
    assert records[KnownDocumentFormat.png].completion_state == (
        "attachment_derivative_write_render_save_promoted"
    )
    assert records[KnownDocumentFormat.png].capability_scope == "attachment_context"
    assert (
        "attachment_context_markdown_derivative_write_render_save_promoted"
        in records[KnownDocumentFormat.png].reasons
    )
    assert "ocr_runtime_deferred" in records[KnownDocumentFormat.png].reasons
    assert records[KnownDocumentFormat.mp3].completion_state == (
        "attachment_derivative_write_render_save_promoted"
    )
    assert records[KnownDocumentFormat.mp3].capability_scope == "attachment_context"
    assert "media_transcription_runtime_deferred" in records[KnownDocumentFormat.mp3].reasons
    assert records[KnownDocumentFormat.shp].completion_state == (
        "attachment_derivative_write_render_save_promoted"
    )
    assert records[KnownDocumentFormat.shp].capability_scope == "attachment_context"
    assert "gdal_feature_extraction_deferred" in records[KnownDocumentFormat.shp].reasons
    assert records[KnownDocumentFormat.python].completion_state == "write_render_save_promoted"
    assert (
        "bounded_python_source_write_render_save_promoted"
        in records[KnownDocumentFormat.python].reasons
    )
    assert "no_source_code_execution" in records[KnownDocumentFormat.python].reasons


def test_audit_reports_xls_derivative_completion_when_bridge_is_verified() -> None:
    report = audit_document_format_completion(
        derivative_promoted_formats=frozenset(
            {KnownDocumentFormat.hwp, KnownDocumentFormat.doc, KnownDocumentFormat.xls}
        ),
        pdfa_conformance_promoted=False,
    )
    records = {record.known_format: record for record in report.records}

    assert records[KnownDocumentFormat.xls].completion_state == (
        "derivative_write_render_save_promoted"
    )
    assert "xls" in report.complete_formats
    assert "xls" not in report.incomplete_formats
    assert "xls_source_preserved" in records[KnownDocumentFormat.xls].reasons
    assert (
        "xls_to_xlsx_derivative_write_render_save_promoted"
        in records[KnownDocumentFormat.xls].reasons
    )
    assert "direct_legacy_xls_binary_mutation_blocked" in records[KnownDocumentFormat.xls].reasons


def test_audit_does_not_claim_derivative_legacy_formats_without_verified_bridge() -> None:
    report = audit_document_format_completion(
        derivative_promoted_formats=frozenset(),
        pdfa_conformance_promoted=False,
    )
    records = {record.known_format: record for record in report.records}

    assert records[KnownDocumentFormat.hwp].completion_state == "probe_blocked"
    assert records[KnownDocumentFormat.doc].completion_state == "probe_blocked"
    assert records[KnownDocumentFormat.xls].completion_state == "probe_blocked"
    assert records[KnownDocumentFormat.ppt].completion_state == "probe_blocked"
    assert "hwp" in report.incomplete_formats
    assert "doc" in report.incomplete_formats
    assert "xls" in report.incomplete_formats
    assert "ppt" in report.incomplete_formats


def test_audit_claims_pdfa_completion_only_after_conformance_gate_is_promoted() -> None:
    report = audit_document_format_completion(
        derivative_promoted_formats=frozenset(
            {
                KnownDocumentFormat.hwp,
                KnownDocumentFormat.doc,
                KnownDocumentFormat.xls,
                KnownDocumentFormat.ppt,
            }
        ),
        pdfa_conformance_promoted=True,
    )
    records = {record.known_format: record for record in report.records}

    assert report.all_formats_complete
    assert records[KnownDocumentFormat.pdfa].completion_state == "write_render_save_promoted"
    assert "pdfa" in report.complete_formats
    assert "pdfa" not in report.incomplete_formats
    assert (
        "verapdf_postwrite_conformance_gate_promoted" in records[KnownDocumentFormat.pdfa].reasons
    )
    assert "ghostscript_pdfa2b_export_promoted" in records[KnownDocumentFormat.pdfa].reasons
