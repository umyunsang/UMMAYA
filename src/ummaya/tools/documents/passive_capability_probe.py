# SPDX-License-Identifier: Apache-2.0
"""Local passive attachment capability diagnostics."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from importlib.util import find_spec
from pathlib import Path
from shutil import which
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.models import DocumentFormatFamily, KnownDocumentFormat

PASSIVE_CAPABILITY_CANDIDATE_ID = "passive-attachment-extraction-boundary"
PASSIVE_CAPABILITY_SOURCE_REFS = (
    "upstream:tesseract-ocr-cli",
    "upstream:ffmpeg-ffprobe",
    "upstream:gdal-ogrinfo",
    "upstream:pyshp",
    "upstream:trimesh",
    "upstream:owasp-file-upload-attachment-limits",
)

PassiveCapabilityProbeStatus = Literal["blocked", "candidate_available"]

_IMAGE_FORMATS = (
    KnownDocumentFormat.png,
    KnownDocumentFormat.jpg,
    KnownDocumentFormat.jpeg,
    KnownDocumentFormat.gif,
    KnownDocumentFormat.tif,
    KnownDocumentFormat.tiff,
    KnownDocumentFormat.bmp,
    KnownDocumentFormat.webp,
)
_GEOSPATIAL_FORMATS = (
    KnownDocumentFormat.shp,
    KnownDocumentFormat.shx,
    KnownDocumentFormat.dbf,
    KnownDocumentFormat.prj,
    KnownDocumentFormat.stl,
)
_MEDIA_FORMATS = (
    KnownDocumentFormat.wav,
    KnownDocumentFormat.mp3,
    KnownDocumentFormat.mp4,
)


class PassiveCapabilityProbeReport(BaseModel):
    """Current local availability of passive attachment extraction candidates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    known_format: KnownDocumentFormat
    family: DocumentFormatFamily
    status: PassiveCapabilityProbeStatus
    read_adapter_id: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    runtime_available: bool
    runtime_executable: Path | None
    extraction_available: bool
    direct_mutation_promoted: bool
    reasons: tuple[str, ...]
    required_gates: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def probe_passive_capabilities(
    *,
    env: Mapping[str, str] | None = None,
    search_path: Sequence[str] | None = None,
    importable_modules: frozenset[str] | None = None,
) -> tuple[PassiveCapabilityProbeReport, ...]:
    """Report passive attachment readiness without promoting document writes."""
    active_env = os.environ if env is None else env
    tesseract = _find_executable("tesseract", active_env=active_env, search_path=search_path)
    ffprobe = _find_executable("ffprobe", active_env=active_env, search_path=search_path)
    geospatial_available = _geospatial_runtime_available(
        active_env=active_env,
        search_path=search_path,
        importable_modules=importable_modules,
    )
    reports: list[PassiveCapabilityProbeReport] = []
    reports.extend(_image_reports(tesseract=tesseract))
    reports.extend(_geospatial_reports(runtime_available=geospatial_available))
    reports.extend(_media_reports(ffprobe=ffprobe))
    return tuple(reports)


def _image_reports(*, tesseract: Path | None) -> tuple[PassiveCapabilityProbeReport, ...]:
    runtime_available = tesseract is not None
    reasons = (
        "image_ocr_candidate_available" if runtime_available else "tesseract_cli_not_found",
        "image_document_write_not_promoted",
        "no_in_place_raster_mutation",
    )
    return tuple(
        _report(
            known_format=known_format,
            family=DocumentFormatFamily.image_scan,
            read_adapter_id="image-scan-extraction-only-adapter",
            runtime_id="tesseract-ocr-cli",
            runtime_available=runtime_available,
            runtime_executable=tesseract,
            extraction_available=runtime_available,
            reasons=reasons,
            required_gates=(
                "image_ocr_runtime_available",
                "image_text_extraction_gate",
                "document_derivative_write_gate",
                "image_original_preservation_gate",
            ),
        )
        for known_format in _IMAGE_FORMATS
    )


def _geospatial_reports(
    *,
    runtime_available: bool,
) -> tuple[PassiveCapabilityProbeReport, ...]:
    reasons = (
        "geospatial_runtime_candidate_available"
        if runtime_available
        else "geospatial_runtime_not_found",
        "geospatial_document_write_not_promoted",
        "geospatial_sidecar_lineage_required",
    )
    return tuple(
        _report(
            known_format=known_format,
            family=DocumentFormatFamily.geospatial_data,
            read_adapter_id="geospatial-metadata-only-adapter",
            runtime_id="gdal-or-pyshp-geospatial-reader",
            runtime_available=runtime_available,
            runtime_executable=None,
            extraction_available=runtime_available,
            reasons=reasons,
            required_gates=(
                "geospatial_runtime_available",
                "sidecar_set_integrity_gate",
                "geometry_metadata_extraction_gate",
                "document_derivative_write_gate",
            ),
        )
        for known_format in _GEOSPATIAL_FORMATS
    )


def _media_reports(*, ffprobe: Path | None) -> tuple[PassiveCapabilityProbeReport, ...]:
    runtime_available = ffprobe is not None
    reasons = (
        "media_metadata_candidate_available" if runtime_available else "ffprobe_cli_not_found",
        "media_transcription_not_promoted",
        "media_document_write_not_promoted",
    )
    return tuple(
        _report(
            known_format=known_format,
            family=DocumentFormatFamily.media_asset,
            read_adapter_id="media-metadata-only-adapter",
            runtime_id="ffprobe-media-metadata",
            runtime_available=runtime_available,
            runtime_executable=ffprobe,
            extraction_available=runtime_available,
            reasons=reasons,
            required_gates=(
                "media_metadata_runtime_available",
                "transcription_or_metadata_extraction_gate",
                "document_derivative_write_gate",
                "media_original_preservation_gate",
            ),
        )
        for known_format in _MEDIA_FORMATS
    )


def _report(
    *,
    known_format: KnownDocumentFormat,
    family: DocumentFormatFamily,
    read_adapter_id: str,
    runtime_id: str,
    runtime_available: bool,
    runtime_executable: Path | None,
    extraction_available: bool,
    reasons: tuple[str, ...],
    required_gates: tuple[str, ...],
) -> PassiveCapabilityProbeReport:
    return PassiveCapabilityProbeReport(
        candidate_id=PASSIVE_CAPABILITY_CANDIDATE_ID,
        known_format=known_format,
        family=family,
        status="candidate_available" if extraction_available else "blocked",
        read_adapter_id=read_adapter_id,
        runtime_id=runtime_id,
        runtime_available=runtime_available,
        runtime_executable=runtime_executable,
        extraction_available=extraction_available,
        direct_mutation_promoted=False,
        reasons=reasons,
        required_gates=required_gates,
        evidence_refs=PASSIVE_CAPABILITY_SOURCE_REFS,
    )


def _geospatial_runtime_available(
    *,
    active_env: Mapping[str, str],
    search_path: Sequence[str] | None,
    importable_modules: frozenset[str] | None,
) -> bool:
    return (
        _find_executable("ogrinfo", active_env=active_env, search_path=search_path) is not None
        or _find_executable("gdalinfo", active_env=active_env, search_path=search_path) is not None
        or _is_importable("shapefile", importable_modules=importable_modules)
        or _is_importable("trimesh", importable_modules=importable_modules)
    )


def _find_executable(
    name: str,
    *,
    active_env: Mapping[str, str],
    search_path: Sequence[str] | None,
) -> Path | None:
    path_env = os.pathsep.join(search_path) if search_path is not None else active_env.get("PATH")
    if not path_env:
        return None
    found = which(name, path=path_env)
    if found is None:
        return None
    executable = Path(found).expanduser().resolve(strict=False)
    if not _is_executable_file(executable):
        return None
    return executable


def _is_importable(name: str, *, importable_modules: frozenset[str] | None) -> bool:
    if importable_modules is not None:
        return name in importable_modules
    return find_spec(name) is not None


def _is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)
