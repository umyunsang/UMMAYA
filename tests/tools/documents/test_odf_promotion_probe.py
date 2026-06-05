# SPDX-License-Identifier: Apache-2.0
"""Diagnostics for ODF promotion candidates."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.adapter_registry import build_default_document_adapter_registry
from ummaya.tools.documents.models import DocumentFormat, KnownDocumentFormat
from ummaya.tools.documents.odf_promotion_probe import probe_odf_promotion


def test_probe_reports_odf_as_bounded_promoted_without_layout_oracle() -> None:
    reports = probe_odf_promotion(env={}, search_path=(), importable_modules=frozenset({"odfdo"}))

    assert {report.known_format for report in reports} == {
        KnownDocumentFormat.odt,
        KnownDocumentFormat.ods,
        KnownDocumentFormat.odp,
    }
    assert all(report.status == "promoted_bounded" for report in reports)
    assert all(report.writer_package == "odfdo" for report in reports)
    assert all(report.writer_available for report in reports)
    assert all(not report.render_oracle_available for report in reports)
    assert all("odf_runtime_promoted_bounded" in report.reasons for report in reports)
    assert all("odfdo_package_registered" in report.reasons for report in reports)
    assert all("libreoffice_cli_not_found" in report.reasons for report in reports)
    assert all("libreoffice_layout_oracle_deferred" in report.reasons for report in reports)
    assert all("upstream:oasis-open-document-v1.4" in report.evidence_refs for report in reports)
    assert all("upstream:odfdo-v3.22.8" in report.evidence_refs for report in reports)

    registry = build_default_document_adapter_registry()

    assert DocumentFormat.odt in registry.require_known(KnownDocumentFormat.odt).promoted_formats
    assert DocumentFormat.ods in registry.require_known(KnownDocumentFormat.ods).promoted_formats
    assert DocumentFormat.odp in registry.require_known(KnownDocumentFormat.odp).promoted_formats


def test_probe_detects_missing_writer_as_blocked() -> None:
    reports = probe_odf_promotion(env={}, search_path=(), importable_modules=frozenset())

    assert all(report.status == "blocked" for report in reports)
    assert all(not report.writer_available for report in reports)
    assert all("odfdo_package_not_found" in report.reasons for report in reports)
    assert all("odf_runtime_promoted_bounded" in report.reasons for report in reports)


def test_probe_detects_libreoffice_cli_as_deferred_layout_oracle(tmp_path: Path) -> None:
    executable = tmp_path / "soffice"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    reports = probe_odf_promotion(
        env={},
        search_path=(str(tmp_path),),
        importable_modules=frozenset({"odfdo"}),
    )

    assert all(report.status == "promoted_bounded" for report in reports)
    assert all(report.writer_available for report in reports)
    assert all(report.render_oracle_available for report in reports)
    assert all(report.render_oracle_executable == executable.resolve() for report in reports)
    assert all("odf_runtime_promoted_bounded" in report.reasons for report in reports)
    assert all("odfdo_package_registered" in report.reasons for report in reports)
    assert all(
        "libreoffice_cli_found_layout_oracle_candidate" in report.reasons for report in reports
    )
    assert all("libreoffice_layout_oracle_deferred" in report.reasons for report in reports)
