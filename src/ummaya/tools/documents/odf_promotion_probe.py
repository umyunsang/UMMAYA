# SPDX-License-Identifier: Apache-2.0
"""Local ODF promotion diagnostics.

ODF is promoted for bounded odfdo-backed write/render/save operations. This
module keeps the separate LibreOffice layout-oracle bridge visible so evidence
does not confuse structural SVG rendering with original-page fidelity.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from importlib.util import find_spec
from pathlib import Path
from shutil import which
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.adapter_registry import build_default_document_adapter_registry
from ummaya.tools.documents.models import DocumentFormat, DocumentFormatFamily, KnownDocumentFormat

ODF_WRITER_PACKAGE = "odfdo"
ODF_WRITER_CANDIDATE_ID = "odfdo-odf-package-writer"
ODF_RENDER_ORACLE_ID = "libreoffice-headless-pdf-export"
ODF_READ_ADAPTER_ID = "odfdo-document-adapter"
ODF_SOURCE_REFS = (
    "upstream:oasis-open-document-v1.4",
    "upstream:odfdo-v3.22.8",
    "upstream:libreoffice-26.2-headless-pdf-export",
)
ODF_PROMOTION_FORMATS = (
    KnownDocumentFormat.odt,
    KnownDocumentFormat.ods,
    KnownDocumentFormat.odp,
)

OdfPromotionProbeStatus = Literal["blocked", "promoted_bounded"]


class OdfPromotionProbeReport(BaseModel):
    """Current local availability of ODF writer/render promotion candidates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    known_format: KnownDocumentFormat
    family: DocumentFormatFamily
    status: OdfPromotionProbeStatus
    read_adapter_id: str = Field(min_length=1)
    writer_package: str = Field(min_length=1)
    writer_available: bool
    render_oracle_id: str = Field(min_length=1)
    render_oracle_available: bool
    render_oracle_executable: Path | None
    reasons: tuple[str, ...]
    required_gates: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def probe_odf_promotion(
    *,
    env: Mapping[str, str] | None = None,
    search_path: Sequence[str] | None = None,
    importable_modules: frozenset[str] | None = None,
) -> tuple[OdfPromotionProbeReport, ...]:
    """Report ODF promotion readiness without mutating adapter registries."""
    active_env = os.environ if env is None else env
    writer_available = _is_importable(ODF_WRITER_PACKAGE, importable_modules=importable_modules)
    runtime_promoted = _is_runtime_promoted()
    render_oracle_executable = _find_libreoffice_cli(active_env=active_env, search_path=search_path)
    render_oracle_available = render_oracle_executable is not None
    status: OdfPromotionProbeStatus = (
        "promoted_bounded" if writer_available and runtime_promoted else "blocked"
    )
    reasons = _reasons(
        writer_available=writer_available,
        runtime_promoted=runtime_promoted,
        render_oracle_available=render_oracle_available,
    )
    return tuple(
        OdfPromotionProbeReport(
            candidate_id=ODF_WRITER_CANDIDATE_ID,
            known_format=known_format,
            family=DocumentFormatFamily.odf,
            status=status,
            read_adapter_id=ODF_READ_ADAPTER_ID,
            writer_package=ODF_WRITER_PACKAGE,
            writer_available=writer_available,
            render_oracle_id=ODF_RENDER_ORACLE_ID,
            render_oracle_available=render_oracle_available,
            render_oracle_executable=render_oracle_executable,
            reasons=reasons,
            required_gates=(
                "odf_writer_package_available",
                "odf_save_reread_fixture_gate",
                "odf_runtime_document_format_promotion",
                "odf_structural_svg_render_gate",
                "odf_layout_oracle_bridge_deferred",
            ),
            evidence_refs=ODF_SOURCE_REFS,
        )
        for known_format in ODF_PROMOTION_FORMATS
    )


def _is_importable(name: str, *, importable_modules: frozenset[str] | None) -> bool:
    if importable_modules is not None:
        return name in importable_modules
    return find_spec(name) is not None


def _is_runtime_promoted() -> bool:
    registry = build_default_document_adapter_registry()
    return all(
        document_format in registry.require_known(known_format).promoted_formats
        for known_format, document_format in (
            (KnownDocumentFormat.odt, DocumentFormat.odt),
            (KnownDocumentFormat.ods, DocumentFormat.ods),
            (KnownDocumentFormat.odp, DocumentFormat.odp),
        )
    )


def _find_libreoffice_cli(
    *,
    active_env: Mapping[str, str],
    search_path: Sequence[str] | None,
) -> Path | None:
    path_env = os.pathsep.join(search_path) if search_path is not None else active_env.get("PATH")
    if not path_env:
        return None
    for executable_name in ("soffice", "libreoffice"):
        found = which(executable_name, path=path_env)
        if found is None:
            continue
        executable = Path(found).expanduser().resolve(strict=False)
        if _is_executable_file(executable):
            return executable
    return None


def _is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def _reasons(
    *,
    writer_available: bool,
    runtime_promoted: bool,
    render_oracle_available: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if runtime_promoted:
        reasons.append("odf_runtime_promoted_bounded")
    else:
        reasons.append("odf_runtime_not_promoted")
    if writer_available:
        reasons.append("odfdo_package_registered")
    else:
        reasons.append("odfdo_package_not_found")
    if render_oracle_available:
        reasons.append("libreoffice_cli_found_layout_oracle_candidate")
    else:
        reasons.append("libreoffice_cli_not_found")
    reasons.append("libreoffice_layout_oracle_deferred")
    return tuple(reasons)
