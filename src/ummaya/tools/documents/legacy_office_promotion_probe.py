# SPDX-License-Identifier: Apache-2.0
"""Local legacy Office promotion diagnostics.

Legacy `.doc`, `.xls`, and `.ppt` files remain metadata-only in UMMAYA. This
module reports whether a local LibreOffice conversion bridge is available
without registering legacy Office binaries as directly mutable formats.
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

LEGACY_OFFICE_CONVERTER_ID = "libreoffice-headless-ooxml-export"
TEXTUTIL_DOC_CONVERTER_ID = "macos-textutil-doc-to-docx"
MICROSOFT_EXCEL_CONVERTER_ID = "microsoft-excel-applescript-xls-to-xlsx"
MICROSOFT_POWERPOINT_UNVERIFIED_CONVERTER_ID = (
    "microsoft-powerpoint-applescript-ppt-to-pptx-unverified"
)
LEGACY_OFFICE_CANDIDATE_ID = "libreoffice-legacy-office-to-ooxml-bridge"
LEGACY_OFFICE_READ_ADAPTER_ID = "legacy-office-metadata-only-adapter"
MICROSOFT_EXCEL_APP_ENV = "UMMAYA_MICROSOFT_EXCEL_APP"
MICROSOFT_POWERPOINT_APP_ENV = "UMMAYA_MICROSOFT_POWERPOINT_APP"
LEGACY_OFFICE_SOURCE_REFS = (
    "upstream:microsoft-office-binary-format-archive",
    "upstream:libreoffice-26.2-convert-to-ooxml",
    "upstream:apple-textutil-local-manpage",
    "upstream:apache-poi-hwpf-hssf-hslf-limitations",
    "upstream:microsoft-powerpoint-sdef-save-as-open-xml-presentation",
)

LegacyOfficePromotionProbeStatus = Literal["blocked", "candidate_available"]

_LEGACY_CONVERSIONS: tuple[
    tuple[KnownDocumentFormat, DocumentFormat, tuple[str, ...]],
    ...,
] = (
    (
        KnownDocumentFormat.doc,
        DocumentFormat.docx,
        (
            "--headless",
            "--convert-to",
            "docx:MS Word 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
    ),
    (
        KnownDocumentFormat.xls,
        DocumentFormat.xlsx,
        (
            "--headless",
            "--convert-to",
            "xlsx:Calc MS Excel 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
    ),
    (
        KnownDocumentFormat.ppt,
        DocumentFormat.pptx,
        (
            "--headless",
            "--convert-to",
            "pptx:Impress MS PowerPoint 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
    ),
)


class LegacyOfficePromotionProbeReport(BaseModel):
    """Current local availability of legacy Office conversion candidates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    known_format: KnownDocumentFormat
    family: DocumentFormatFamily
    status: LegacyOfficePromotionProbeStatus
    output_format: DocumentFormat
    read_adapter_id: str = Field(min_length=1)
    converter_id: str = Field(min_length=1)
    converter_available: bool
    converter_executable: Path | None
    recommended_args: tuple[str, ...]
    reasons: tuple[str, ...]
    required_gates: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def probe_legacy_office_promotion(
    *,
    env: Mapping[str, str] | None = None,
    search_path: Sequence[str] | None = None,
) -> tuple[LegacyOfficePromotionProbeReport, ...]:
    """Report legacy Office conversion readiness without mutating registries."""
    active_env = os.environ if env is None else env
    libreoffice_executable = _find_libreoffice_cli(
        active_env=active_env,
        search_path=search_path,
    )
    textutil_executable = _find_textutil_cli(active_env=active_env, search_path=search_path)
    excel_osascript_executable = _find_excel_osascript_cli(
        active_env=active_env,
        search_path=search_path,
    )
    powerpoint_osascript_executable = _find_powerpoint_osascript_cli(
        active_env=active_env,
        search_path=search_path,
    )
    return tuple(
        _report(
            known_format=known_format,
            output_format=output_format,
            libreoffice_executable=libreoffice_executable,
            textutil_executable=textutil_executable,
            excel_osascript_executable=excel_osascript_executable,
            powerpoint_osascript_executable=powerpoint_osascript_executable,
            libreoffice_args=recommended_args,
        )
        for known_format, output_format, recommended_args in _LEGACY_CONVERSIONS
    )


def _report(
    *,
    known_format: KnownDocumentFormat,
    output_format: DocumentFormat,
    libreoffice_executable: Path | None,
    textutil_executable: Path | None,
    excel_osascript_executable: Path | None,
    powerpoint_osascript_executable: Path | None,
    libreoffice_args: tuple[str, ...],
) -> LegacyOfficePromotionProbeReport:
    converter_executable = libreoffice_executable
    converter_id = LEGACY_OFFICE_CONVERTER_ID
    recommended_args = libreoffice_args
    reasons = _reasons(converter_available=libreoffice_executable is not None)
    if libreoffice_executable is None and known_format is KnownDocumentFormat.doc:
        converter_executable = textutil_executable
        converter_id = TEXTUTIL_DOC_CONVERTER_ID
        recommended_args = ("-convert", "docx", "-output", "{output}", "{source}")
        reasons = _doc_textutil_reasons(textutil_available=textutil_executable is not None)
    if libreoffice_executable is None and known_format is KnownDocumentFormat.xls:
        converter_executable = excel_osascript_executable
        converter_id = MICROSOFT_EXCEL_CONVERTER_ID
        recommended_args = (
            "osascript",
            "excel_xls_to_xlsx",
            "{source}",
            "{output}",
        )
        reasons = _xls_excel_reasons(excel_available=excel_osascript_executable is not None)
    if libreoffice_executable is None and known_format is KnownDocumentFormat.ppt:
        converter_executable = None
        converter_id = MICROSOFT_POWERPOINT_UNVERIFIED_CONVERTER_ID
        recommended_args = (
            "osascript",
            "powerpoint_ppt_to_pptx_unverified",
            "{source}",
            "{output}",
        )
        reasons = _ppt_powerpoint_reasons(
            powerpoint_available=powerpoint_osascript_executable is not None
        )

    converter_available = converter_executable is not None
    status: LegacyOfficePromotionProbeStatus = (
        "candidate_available" if converter_available else "blocked"
    )
    return LegacyOfficePromotionProbeReport(
        candidate_id=LEGACY_OFFICE_CANDIDATE_ID,
        known_format=known_format,
        family=DocumentFormatFamily.legacy_office,
        status=status,
        output_format=output_format,
        read_adapter_id=LEGACY_OFFICE_READ_ADAPTER_ID,
        converter_id=converter_id,
        converter_available=converter_available,
        converter_executable=converter_executable,
        recommended_args=recommended_args,
        reasons=reasons,
        required_gates=(
            "legacy_office_converter_available",
            "legacy_office_derivative_lineage_gate",
            "ooxml_save_reread_fixture_gate",
            "legacy_office_runtime_derivative_promotion",
        ),
        evidence_refs=LEGACY_OFFICE_SOURCE_REFS,
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


def _find_textutil_cli(
    *,
    active_env: Mapping[str, str],
    search_path: Sequence[str] | None,
) -> Path | None:
    path_env = os.pathsep.join(search_path) if search_path is not None else active_env.get("PATH")
    if not path_env:
        return None
    found = which("textutil", path=path_env)
    if found is None:
        return None
    executable = Path(found).expanduser().resolve(strict=False)
    if _is_executable_file(executable):
        return executable
    return None


def _find_excel_osascript_cli(
    *,
    active_env: Mapping[str, str],
    search_path: Sequence[str] | None,
) -> Path | None:
    if _find_microsoft_excel_app(active_env) is None:
        return None
    path_env = os.pathsep.join(search_path) if search_path is not None else active_env.get("PATH")
    if not path_env:
        return None
    found = which("osascript", path=path_env)
    if found is None:
        return None
    executable = Path(found).expanduser().resolve(strict=False)
    if _is_executable_file(executable):
        return executable
    return None


def _find_powerpoint_osascript_cli(
    *,
    active_env: Mapping[str, str],
    search_path: Sequence[str] | None,
) -> Path | None:
    if _find_microsoft_powerpoint_app(active_env) is None:
        return None
    path_env = os.pathsep.join(search_path) if search_path is not None else active_env.get("PATH")
    if not path_env:
        return None
    found = which("osascript", path=path_env)
    if found is None:
        return None
    executable = Path(found).expanduser().resolve(strict=False)
    if _is_executable_file(executable):
        return executable
    return None


def _find_microsoft_excel_app(active_env: Mapping[str, str]) -> Path | None:
    configured = active_env.get(MICROSOFT_EXCEL_APP_ENV)
    if configured:
        candidate = Path(configured).expanduser().resolve(strict=False)
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None
    if active_env is not os.environ:
        return None
    candidate = Path("/Applications/Microsoft Excel.app")
    if candidate.exists() and candidate.is_dir():
        return candidate
    return None


def _find_microsoft_powerpoint_app(active_env: Mapping[str, str]) -> Path | None:
    configured = active_env.get(MICROSOFT_POWERPOINT_APP_ENV)
    if configured:
        candidate = Path(configured).expanduser().resolve(strict=False)
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None
    if active_env is not os.environ:
        return None
    candidate = Path("/Applications/Microsoft PowerPoint.app")
    if candidate.exists() and candidate.is_dir():
        return candidate
    return None


def _is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def _reasons(*, converter_available: bool) -> tuple[str, ...]:
    reasons = [
        "legacy_office_runtime_not_promoted",
        "direct_legacy_office_write_blocked",
    ]
    if converter_available:
        reasons.append("libreoffice_cli_found_for_default_derivative_bridge")
    else:
        reasons.append("libreoffice_cli_not_found")
    return tuple(reasons)


def _doc_textutil_reasons(*, textutil_available: bool) -> tuple[str, ...]:
    reasons = [
        "legacy_office_runtime_not_promoted",
        "direct_legacy_office_write_blocked",
    ]
    if textutil_available:
        reasons.append("textutil_cli_found_for_doc_derivative_bridge")
    else:
        reasons.append("libreoffice_cli_not_found")
        reasons.append("textutil_cli_not_found_for_doc")
    return tuple(reasons)


def _xls_excel_reasons(*, excel_available: bool) -> tuple[str, ...]:
    reasons = [
        "legacy_office_runtime_not_promoted",
        "direct_legacy_office_write_blocked",
    ]
    if excel_available:
        reasons.append("microsoft_excel_app_found_for_xls_derivative_bridge")
    else:
        reasons.append("libreoffice_cli_not_found")
        reasons.append("microsoft_excel_app_or_osascript_not_found_for_xls")
    return tuple(reasons)


def _ppt_powerpoint_reasons(*, powerpoint_available: bool) -> tuple[str, ...]:
    reasons = [
        "legacy_office_runtime_not_promoted",
        "direct_legacy_office_write_blocked",
        "libreoffice_cli_not_found",
    ]
    if powerpoint_available:
        reasons.append("microsoft_powerpoint_app_found_but_applescript_bridge_unverified")
        reasons.append("powerpoint_applescript_save_open_xml_probe_required")
    else:
        reasons.append("microsoft_powerpoint_app_or_osascript_not_found_for_ppt")
    return tuple(reasons)
