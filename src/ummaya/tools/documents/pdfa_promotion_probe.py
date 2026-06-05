# SPDX-License-Identifier: Apache-2.0
"""Local PDF/A conformance promotion diagnostics.

PDF/A artifacts can be parsed, rendered, and AcroForm-filled through the PDF
runtime boundary, but UMMAYA must not claim PDF/A-conformant output until a
local conformance validator verifies the post-write artifact.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from shutil import which
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.models import (
    DocumentFormat,
    DocumentFormatFamily,
    KnownDocumentFormat,
)
from ummaya.tools.documents.pdfa_conformance import (
    PDFA_EXPORTER_ID,
    PDFA_FLAVOUR,
    PDFA_VALIDATOR_ID,
    discover_ghostscript_pdfa_assets,
)

PDFA_CANDIDATE_ID = "verapdf-pdfa-postwrite-gate"
PDFA_READ_ADAPTER_ID = "pypdf-acroform-adapter"
PDFA_SOURCE_REFS = (
    "upstream:verapdf-home-pdfa-validation",
    "upstream:verapdf-cli-validation",
    "upstream:ghostscript-pdfa-pdfwrite",
    "upstream:pypdf-pdfa-no-guarantee",
    "upstream:pypdf-acroform-forms",
)
PDFA_RECOMMENDED_ARGS = (
    "gs",
    "--permit-file-read=srgb.icc",
    "-dPDFA=2",
    "-dBATCH",
    "-dNOPAUSE",
    "-dNOOUTERSAVE",
    "-sColorConversionStrategy=RGB",
    "-sDEVICE=pdfwrite",
    "-dPDFACompatibilityPolicy=1",
    "-sOutputFile={output}",
    "PDFA_def.ps",
    "{source}",
    "&&",
    "verapdf",
    "--format",
    "text",
    "--flavour",
    PDFA_FLAVOUR,
    "{output}",
)

PdfaPromotionProbeStatus = Literal["blocked", "candidate_available"]


class PdfaPromotionProbeReport(BaseModel):
    """Current local availability of PDF/A conformance validation candidates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    known_format: KnownDocumentFormat
    family: DocumentFormatFamily
    status: PdfaPromotionProbeStatus
    runtime_format: DocumentFormat
    read_adapter_id: str = Field(min_length=1)
    exporter_id: str = Field(min_length=1)
    exporter_available: bool
    exporter_executable: Path | None
    pdfa_def_path: Path | None
    srgb_icc_path: Path | None
    validator_id: str = Field(min_length=1)
    validator_available: bool
    validator_executable: Path | None
    recommended_args: tuple[str, ...]
    reasons: tuple[str, ...]
    required_gates: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def probe_pdfa_promotion(
    *,
    env: Mapping[str, str] | None = None,
    search_path: Sequence[str] | None = None,
) -> PdfaPromotionProbeReport:
    """Report PDF/A conformance-gate readiness without promoting output writes."""
    active_env = os.environ if env is None else env
    validator_executable = _find_verapdf_cli(active_env=active_env, search_path=search_path)
    exporter_executable = _find_ghostscript_cli(active_env=active_env, search_path=search_path)
    pdfa_assets = (
        discover_ghostscript_pdfa_assets(exporter_executable)
        if exporter_executable is not None
        else None
    )
    pdfa_def_path = pdfa_assets[0] if pdfa_assets is not None else None
    srgb_icc_path = pdfa_assets[1] if pdfa_assets is not None else None
    validator_available = validator_executable is not None
    exporter_available = exporter_executable is not None and pdfa_assets is not None
    status: PdfaPromotionProbeStatus = (
        "candidate_available" if validator_available and exporter_available else "blocked"
    )
    return PdfaPromotionProbeReport(
        candidate_id=PDFA_CANDIDATE_ID,
        known_format=KnownDocumentFormat.pdfa,
        family=DocumentFormatFamily.pdf,
        status=status,
        runtime_format=DocumentFormat.pdf,
        read_adapter_id=PDFA_READ_ADAPTER_ID,
        exporter_id=PDFA_EXPORTER_ID,
        exporter_available=exporter_available,
        exporter_executable=exporter_executable,
        pdfa_def_path=pdfa_def_path,
        srgb_icc_path=srgb_icc_path,
        validator_id=PDFA_VALIDATOR_ID,
        validator_available=validator_available,
        validator_executable=validator_executable,
        recommended_args=PDFA_RECOMMENDED_ARGS,
        reasons=_reasons(
            validator_available=validator_available,
            exporter_available=exporter_available,
        ),
        required_gates=(
            "pdfa_runtime_pdf_alias_intake_gate",
            "pdf_acroform_write_render_save_gate",
            "ghostscript_pdfa2b_export_available",
            "verapdf_cli_available",
            "verapdf_postwrite_conformance_gate",
            "pdfa_runtime_completion_promotion",
        ),
        evidence_refs=PDFA_SOURCE_REFS,
    )


def _find_verapdf_cli(
    *,
    active_env: Mapping[str, str],
    search_path: Sequence[str] | None,
) -> Path | None:
    path_env = os.pathsep.join(search_path) if search_path is not None else active_env.get("PATH")
    if not path_env:
        return None
    found = which("verapdf", path=path_env)
    if found is None:
        return None
    executable = Path(found).expanduser().resolve(strict=False)
    if not _is_executable_file(executable):
        return None
    return executable


def _find_ghostscript_cli(
    *,
    active_env: Mapping[str, str],
    search_path: Sequence[str] | None,
) -> Path | None:
    path_env = os.pathsep.join(search_path) if search_path is not None else active_env.get("PATH")
    if not path_env:
        return None
    found = which("gs", path=path_env)
    if found is None:
        return None
    executable = Path(found).expanduser().resolve(strict=False)
    if not _is_executable_file(executable):
        return None
    return executable


def _is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def _reasons(*, validator_available: bool, exporter_available: bool) -> tuple[str, ...]:
    reasons = [
        "pdfa_runtime_aliases_pdf_adapter",
        "pypdf_pdfa_conformance_not_claimed",
    ]
    if validator_available:
        reasons.append("verapdf_cli_found")
    else:
        reasons.append("verapdf_cli_not_found")
    if exporter_available:
        reasons.append("ghostscript_pdfa_exporter_found")
    else:
        reasons.append("ghostscript_pdfa_exporter_not_found")
    if validator_available and exporter_available:
        reasons.append("pdfa_postwrite_conformance_gate_available")
    else:
        reasons.append("pdfa_conformance_write_not_promoted")
    return tuple(reasons)
