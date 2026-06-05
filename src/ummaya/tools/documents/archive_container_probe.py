# SPDX-License-Identifier: Apache-2.0
"""Local archive/container promotion diagnostics."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from shutil import which
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.models import DocumentFormatFamily, KnownDocumentFormat

ARCHIVE_CANDIDATE_ID = "archive-container-child-routing"
ARCHIVE_READ_ADAPTER_ID = "archive-document-set-read-only-adapter"
ARCHIVE_SOURCE_REFS = (
    "upstream:python-3.12-zipfile",
    "upstream:python-3.12-tarfile-data-filter",
    "upstream:python-3.12-gzip",
    "upstream:libarchive-bsdtar-7zip",
    "upstream:owasp-file-upload-archive-limits",
)

ArchiveContainerProbeStatus = Literal["blocked", "candidate_available"]


class ArchiveContainerProbeReport(BaseModel):
    """Current local availability of archive child-routing candidates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    known_format: KnownDocumentFormat
    family: DocumentFormatFamily
    status: ArchiveContainerProbeStatus
    read_adapter_id: str = Field(min_length=1)
    container_runtime_id: str = Field(min_length=1)
    runtime_available: bool
    runtime_executable: Path | None
    child_routing_available: bool
    direct_mutation_promoted: bool
    reasons: tuple[str, ...]
    required_gates: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def probe_archive_container_promotion(
    *,
    env: Mapping[str, str] | None = None,
    search_path: Sequence[str] | None = None,
) -> tuple[ArchiveContainerProbeReport, ...]:
    """Report archive/container routing readiness without promoting repack writes."""
    active_env = os.environ if env is None else env
    bsdtar = _find_executable("bsdtar", active_env=active_env, search_path=search_path)
    seven_z_available = bsdtar is not None
    return (
        _report(
            known_format=KnownDocumentFormat.epub,
            runtime_id="python-stdlib-zipfile-epub-container",
            runtime_available=True,
            runtime_executable=None,
            child_routing_available=True,
            reasons=(
                "archive_child_derivative_promoted",
                "epub_child_payload_writer_promoted",
                "no_in_place_archive_mutation",
            ),
        ),
        _report(
            known_format=KnownDocumentFormat.zip,
            runtime_id="python-stdlib-zipfile",
            runtime_available=True,
            runtime_executable=None,
            child_routing_available=True,
            reasons=(
                "archive_child_derivative_promoted",
                "no_in_place_archive_mutation",
            ),
        ),
        _report(
            known_format=KnownDocumentFormat.seven_z,
            runtime_id="libarchive-bsdtar-7zip",
            runtime_available=seven_z_available,
            runtime_executable=bsdtar,
            child_routing_available=seven_z_available,
            reasons=(
                (
                    "bsdtar_7zip_runtime_promoted"
                    if seven_z_available
                    else "bsdtar_7zip_runtime_not_found"
                ),
                "archive_child_derivative_promoted" if seven_z_available else "7z_repack_blocked",
                "no_in_place_archive_mutation",
            ),
        ),
        _report(
            known_format=KnownDocumentFormat.tar,
            runtime_id="python-stdlib-tarfile",
            runtime_available=True,
            runtime_executable=None,
            child_routing_available=True,
            reasons=(
                "archive_child_derivative_promoted",
                "tarfile_data_filter_required",
                "no_in_place_archive_mutation",
            ),
        ),
        _report(
            known_format=KnownDocumentFormat.gz,
            runtime_id="python-stdlib-gzip",
            runtime_available=True,
            runtime_executable=None,
            child_routing_available=True,
            reasons=(
                "archive_child_derivative_promoted",
                "gzip_single_child_candidate",
                "no_in_place_archive_mutation",
            ),
        ),
    )


def _report(
    *,
    known_format: KnownDocumentFormat,
    runtime_id: str,
    runtime_available: bool,
    runtime_executable: Path | None,
    child_routing_available: bool,
    reasons: tuple[str, ...],
) -> ArchiveContainerProbeReport:
    return ArchiveContainerProbeReport(
        candidate_id=ARCHIVE_CANDIDATE_ID,
        known_format=known_format,
        family=DocumentFormatFamily.archive,
        status="candidate_available" if child_routing_available else "blocked",
        read_adapter_id=ARCHIVE_READ_ADAPTER_ID,
        container_runtime_id=runtime_id,
        runtime_available=runtime_available,
        runtime_executable=runtime_executable,
        child_routing_available=child_routing_available,
        direct_mutation_promoted=False,
        reasons=reasons,
        required_gates=(
            "archive_intake_security_gate",
            "archive_child_routing_gate",
            "child_document_promotion_gate",
            "archive_repack_write_gate",
            "archive_runtime_completion_promotion",
        ),
        evidence_refs=ARCHIVE_SOURCE_REFS,
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
    return Path(found).resolve() if found else None
