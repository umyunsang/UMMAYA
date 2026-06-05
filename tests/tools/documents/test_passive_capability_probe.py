# SPDX-License-Identifier: Apache-2.0
"""Diagnostics for non-form passive attachment capability candidates."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.models import KnownDocumentFormat
from ummaya.tools.documents.passive_capability_probe import probe_passive_capabilities


def test_probe_reports_image_media_and_geospatial_capability_boundaries(
    tmp_path: Path,
) -> None:
    tesseract = _fake_executable(tmp_path / "tesseract")
    ffprobe = _fake_executable(tmp_path / "ffprobe")
    _fake_executable(tmp_path / "ffmpeg")

    reports = probe_passive_capabilities(
        env={},
        search_path=(str(tmp_path),),
        importable_modules=frozenset({"PIL"}),
    )
    by_format = {report.known_format: report for report in reports}

    assert by_format[KnownDocumentFormat.png].status == "candidate_available"
    assert by_format[KnownDocumentFormat.png].runtime_id == "tesseract-ocr-cli"
    assert by_format[KnownDocumentFormat.png].runtime_available
    assert by_format[KnownDocumentFormat.png].runtime_executable == tesseract.resolve()
    assert by_format[KnownDocumentFormat.png].extraction_available
    assert not by_format[KnownDocumentFormat.png].direct_mutation_promoted
    assert "image_ocr_candidate_available" in by_format[KnownDocumentFormat.png].reasons
    assert "image_document_write_not_promoted" in by_format[KnownDocumentFormat.png].reasons

    assert by_format[KnownDocumentFormat.mp4].status == "candidate_available"
    assert by_format[KnownDocumentFormat.mp4].runtime_id == "ffprobe-media-metadata"
    assert by_format[KnownDocumentFormat.mp4].runtime_available
    assert by_format[KnownDocumentFormat.mp4].runtime_executable == ffprobe.resolve()
    assert "media_metadata_candidate_available" in by_format[KnownDocumentFormat.mp4].reasons
    assert "media_transcription_not_promoted" in by_format[KnownDocumentFormat.mp4].reasons

    assert KnownDocumentFormat.python not in by_format

    assert by_format[KnownDocumentFormat.shp].status == "blocked"
    assert by_format[KnownDocumentFormat.shp].runtime_id == "gdal-or-pyshp-geospatial-reader"
    assert not by_format[KnownDocumentFormat.shp].runtime_available
    assert not by_format[KnownDocumentFormat.shp].extraction_available
    assert "geospatial_runtime_not_found" in by_format[KnownDocumentFormat.shp].reasons
    assert "geospatial_document_write_not_promoted" in by_format[KnownDocumentFormat.shp].reasons


def test_probe_reports_missing_image_and_media_runtimes_as_blocked() -> None:
    reports = probe_passive_capabilities(
        env={},
        search_path=(),
        importable_modules=frozenset(),
    )
    by_format = {report.known_format: report for report in reports}

    assert by_format[KnownDocumentFormat.png].status == "blocked"
    assert not by_format[KnownDocumentFormat.png].runtime_available
    assert "tesseract_cli_not_found" in by_format[KnownDocumentFormat.png].reasons
    assert by_format[KnownDocumentFormat.mp3].status == "blocked"
    assert "ffprobe_cli_not_found" in by_format[KnownDocumentFormat.mp3].reasons


def _fake_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path
