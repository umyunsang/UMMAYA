# SPDX-License-Identifier: Apache-2.0
"""Diagnostics for archive/container document routing candidates."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.archive_container_probe import probe_archive_container_promotion
from ummaya.tools.documents.models import KnownDocumentFormat


def test_probe_reports_promoted_archive_child_derivatives_without_in_place_mutation(
    tmp_path: Path,
) -> None:
    bsdtar = _fake_executable(tmp_path / "bsdtar")
    reports = probe_archive_container_promotion(env={}, search_path=(str(tmp_path),))
    by_format = {report.known_format: report for report in reports}

    assert set(by_format) == {
        KnownDocumentFormat.epub,
        KnownDocumentFormat.zip,
        KnownDocumentFormat.seven_z,
        KnownDocumentFormat.tar,
        KnownDocumentFormat.gz,
    }
    assert by_format[KnownDocumentFormat.zip].status == "candidate_available"
    assert by_format[KnownDocumentFormat.zip].container_runtime_id == "python-stdlib-zipfile"
    assert by_format[KnownDocumentFormat.zip].runtime_available
    assert by_format[KnownDocumentFormat.zip].child_routing_available
    assert not by_format[KnownDocumentFormat.zip].direct_mutation_promoted
    assert "archive_child_derivative_promoted" in by_format[KnownDocumentFormat.zip].reasons
    assert "no_in_place_archive_mutation" in by_format[KnownDocumentFormat.zip].reasons

    assert by_format[KnownDocumentFormat.tar].status == "candidate_available"
    assert "archive_child_derivative_promoted" in by_format[KnownDocumentFormat.tar].reasons
    assert "tarfile_data_filter_required" in by_format[KnownDocumentFormat.tar].reasons
    assert by_format[KnownDocumentFormat.gz].status == "candidate_available"
    assert "archive_child_derivative_promoted" in by_format[KnownDocumentFormat.gz].reasons
    assert "gzip_single_child_candidate" in by_format[KnownDocumentFormat.gz].reasons
    assert by_format[KnownDocumentFormat.epub].status == "candidate_available"
    assert "epub_child_payload_writer_promoted" in by_format[KnownDocumentFormat.epub].reasons

    assert by_format[KnownDocumentFormat.seven_z].status == "candidate_available"
    assert by_format[KnownDocumentFormat.seven_z].container_runtime_id == "libarchive-bsdtar-7zip"
    assert by_format[KnownDocumentFormat.seven_z].runtime_available
    assert by_format[KnownDocumentFormat.seven_z].runtime_executable == bsdtar.resolve()
    assert by_format[KnownDocumentFormat.seven_z].child_routing_available
    assert not by_format[KnownDocumentFormat.seven_z].direct_mutation_promoted
    assert "bsdtar_7zip_runtime_promoted" in by_format[KnownDocumentFormat.seven_z].reasons
    assert "archive_child_derivative_promoted" in by_format[KnownDocumentFormat.seven_z].reasons
    assert all(
        "upstream:owasp-file-upload-archive-limits" in report.evidence_refs for report in reports
    )


def test_probe_reports_missing_7z_runtime_as_blocked() -> None:
    reports = probe_archive_container_promotion(env={}, search_path=())
    by_format = {report.known_format: report for report in reports}

    seven_z = by_format[KnownDocumentFormat.seven_z]

    assert seven_z.status == "blocked"
    assert seven_z.container_runtime_id == "libarchive-bsdtar-7zip"
    assert not seven_z.runtime_available
    assert seven_z.runtime_executable is None
    assert not seven_z.child_routing_available
    assert not seven_z.direct_mutation_promoted
    assert "bsdtar_7zip_runtime_not_found" in seven_z.reasons
    assert "7z_repack_blocked" in seven_z.reasons


def _fake_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path
