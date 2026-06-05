# SPDX-License-Identifier: Apache-2.0
"""Diagnostics for legacy Office promotion candidates."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.adapter_registry import build_default_document_adapter_registry
from ummaya.tools.documents.legacy_office_promotion_probe import probe_legacy_office_promotion
from ummaya.tools.documents.models import DocumentFormat, KnownDocumentFormat


def test_probe_reports_legacy_office_as_conversion_required_without_libreoffice() -> None:
    reports = probe_legacy_office_promotion(env={}, search_path=())

    assert {report.known_format for report in reports} == {
        KnownDocumentFormat.doc,
        KnownDocumentFormat.xls,
        KnownDocumentFormat.ppt,
    }
    assert {report.output_format for report in reports} == {
        DocumentFormat.docx,
        DocumentFormat.xlsx,
        DocumentFormat.pptx,
    }
    assert all(report.status == "blocked" for report in reports)
    assert all(
        report.read_adapter_id == "legacy-office-metadata-only-adapter" for report in reports
    )
    assert all(not report.converter_available for report in reports)
    assert all("legacy_office_runtime_not_promoted" in report.reasons for report in reports)
    assert all("direct_legacy_office_write_blocked" in report.reasons for report in reports)
    assert all("libreoffice_cli_not_found" in report.reasons for report in reports)
    assert all(
        "upstream:libreoffice-26.2-convert-to-ooxml" in report.evidence_refs for report in reports
    )

    registry = build_default_document_adapter_registry()

    assert registry.require_known(KnownDocumentFormat.doc).promoted_formats == ()
    assert registry.require_known(KnownDocumentFormat.xls).promoted_formats == ()
    assert registry.require_known(KnownDocumentFormat.ppt).promoted_formats == ()


def test_probe_detects_libreoffice_cli_for_default_derivative_bridge(tmp_path: Path) -> None:
    executable = tmp_path / "libreoffice"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    reports = probe_legacy_office_promotion(env={}, search_path=(str(tmp_path),))

    assert all(report.status == "candidate_available" for report in reports)
    assert all(report.converter_available for report in reports)
    assert all(report.converter_executable == executable.resolve() for report in reports)
    assert all(
        "libreoffice_cli_found_for_default_derivative_bridge" in report.reasons
        for report in reports
    )
    assert {report.known_format: report.recommended_args for report in reports} == {
        KnownDocumentFormat.doc: (
            "--headless",
            "--convert-to",
            "docx:MS Word 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
        KnownDocumentFormat.xls: (
            "--headless",
            "--convert-to",
            "xlsx:Calc MS Excel 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
        KnownDocumentFormat.ppt: (
            "--headless",
            "--convert-to",
            "pptx:Impress MS PowerPoint 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
    }

    registry = build_default_document_adapter_registry()

    assert registry.require_known(KnownDocumentFormat.doc).promoted_formats == ()
    assert registry.require_known(KnownDocumentFormat.xls).promoted_formats == ()
    assert registry.require_known(KnownDocumentFormat.ppt).promoted_formats == ()


def test_probe_detects_textutil_for_doc_only_derivative_bridge(tmp_path: Path) -> None:
    executable = tmp_path / "textutil"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    reports = probe_legacy_office_promotion(env={}, search_path=(str(tmp_path),))
    by_format = {report.known_format: report for report in reports}

    assert by_format[KnownDocumentFormat.doc].status == "candidate_available"
    assert by_format[KnownDocumentFormat.doc].converter_available
    assert by_format[KnownDocumentFormat.doc].converter_executable == executable.resolve()
    assert by_format[KnownDocumentFormat.doc].converter_id == "macos-textutil-doc-to-docx"
    assert by_format[KnownDocumentFormat.doc].recommended_args == (
        "-convert",
        "docx",
        "-output",
        "{output}",
        "{source}",
    )
    assert (
        "textutil_cli_found_for_doc_derivative_bridge" in by_format[KnownDocumentFormat.doc].reasons
    )
    assert by_format[KnownDocumentFormat.xls].status == "blocked"
    assert "libreoffice_cli_not_found" in by_format[KnownDocumentFormat.xls].reasons
    assert by_format[KnownDocumentFormat.ppt].status == "blocked"
    assert "libreoffice_cli_not_found" in by_format[KnownDocumentFormat.ppt].reasons


def test_probe_detects_excel_for_xls_only_derivative_bridge(tmp_path: Path) -> None:
    osascript = tmp_path / "osascript"
    osascript.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    osascript.chmod(0o755)
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()

    reports = probe_legacy_office_promotion(
        env={"UMMAYA_MICROSOFT_EXCEL_APP": str(excel_app)},
        search_path=(str(tmp_path),),
    )
    by_format = {report.known_format: report for report in reports}

    assert by_format[KnownDocumentFormat.xls].status == "candidate_available"
    assert by_format[KnownDocumentFormat.xls].converter_available
    assert by_format[KnownDocumentFormat.xls].converter_executable == osascript.resolve()
    assert (
        by_format[KnownDocumentFormat.xls].converter_id == "microsoft-excel-applescript-xls-to-xlsx"
    )
    assert (
        "microsoft_excel_app_found_for_xls_derivative_bridge"
        in by_format[KnownDocumentFormat.xls].reasons
    )
    assert by_format[KnownDocumentFormat.doc].status == "blocked"
    assert by_format[KnownDocumentFormat.ppt].status == "blocked"


def test_probe_reports_powerpoint_app_as_unverified_ppt_bridge(tmp_path: Path) -> None:
    osascript = tmp_path / "osascript"
    osascript.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    osascript.chmod(0o755)
    powerpoint_app = tmp_path / "Microsoft PowerPoint.app"
    powerpoint_app.mkdir()

    reports = probe_legacy_office_promotion(
        env={"UMMAYA_MICROSOFT_POWERPOINT_APP": str(powerpoint_app)},
        search_path=(str(tmp_path),),
    )
    by_format = {report.known_format: report for report in reports}

    assert by_format[KnownDocumentFormat.ppt].status == "blocked"
    assert not by_format[KnownDocumentFormat.ppt].converter_available
    assert by_format[KnownDocumentFormat.ppt].converter_id == (
        "microsoft-powerpoint-applescript-ppt-to-pptx-unverified"
    )
    assert (
        "microsoft_powerpoint_app_found_but_applescript_bridge_unverified"
        in by_format[KnownDocumentFormat.ppt].reasons
    )
    assert "libreoffice_cli_not_found" in by_format[KnownDocumentFormat.ppt].reasons
