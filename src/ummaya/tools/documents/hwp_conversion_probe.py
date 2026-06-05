# SPDX-License-Identifier: Apache-2.0
"""Local HWP-to-HWPX bridge diagnostics.

This module does not register converters. It reports whether a local candidate
can satisfy the explicit `DocumentConversionEngine` environment boundary.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from shutil import which
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.models import DocumentFormat

HWP_CONVERTER_ENV = "UMMAYA_HWP_TO_HWPX_CONVERTER"
HWP_CONVERTER_ARGS_ENV = "UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON"
HWP_CONVERTER_ENGINE_ID_ENV = "UMMAYA_HWP_TO_HWPX_CONVERTER_ENGINE_ID"
HWP_CONVERTER_TIMEOUT_ENV = "UMMAYA_HWP_TO_HWPX_CONVERTER_TIMEOUT_SECONDS"
HWPFORGE_CANDIDATE_ID = "hwpforge-cli-convert-hwp5"
HWPFORGE_HWP5_TO_HWPX_ARGS = (
    "--json",
    "convert-hwp5",
    "{source}",
    "--output",
    "{output}",
)
HWPXJS_CANDIDATE_ID = "hwpxjs-cli-convert-hwp"
HWPXJS_HWP_TO_HWPX_ARGS = ("convert:hwp", "{source}", "{output}")
_HWPFORGE_SOURCE_REF = "upstream:hwpforge-cli-v0.6.0-convert-hwp5"
_HWPXJS_SOURCE_REF = "upstream:ssabro-hwpxjs-v0.4.0"
_ADR_REF = "adr:docs/adr/ADR-011-hwp-conversion-bridge.md"

BridgeProbeStatus = Literal["configured", "available", "missing", "misconfigured"]


class HwpToHwpxBridgeProbeReport(BaseModel):
    """Current local availability of the HWP-to-HWPX bridge candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    status: BridgeProbeStatus
    source_format: DocumentFormat
    output_format: DocumentFormat
    executable: Path | None
    recommended_args: tuple[str, ...]
    recommended_env: dict[str, str]
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def probe_hwp_to_hwpx_bridge(
    *,
    env: Mapping[str, str] | None = None,
    search_path: Sequence[str] | None = None,
) -> HwpToHwpxBridgeProbeReport:
    """Report whether a local HwpForge CLI bridge is configured or discoverable."""
    active_env = os.environ if env is None else env
    configured = active_env.get(HWP_CONVERTER_ENV)
    if configured:
        configured_path = Path(configured).expanduser().resolve(strict=False)
        if _is_executable_file(configured_path):
            return _report(
                candidate_id=active_env.get(HWP_CONVERTER_ENGINE_ID_ENV, HWPFORGE_CANDIDATE_ID),
                status="configured",
                executable=configured_path,
                recommended_args=_configured_args_or_default(active_env),
                reasons=("explicit_hwp_bridge_configured",),
                evidence_refs=(_ADR_REF,),
            )
        return _report(
            candidate_id=active_env.get(HWP_CONVERTER_ENGINE_ID_ENV, HWPFORGE_CANDIDATE_ID),
            status="misconfigured",
            executable=configured_path,
            recommended_args=_configured_args_or_default(active_env),
            reasons=("explicit_hwp_bridge_not_executable",),
            evidence_refs=(_ADR_REF,),
        )

    discovered_hwpxjs = _find_executable("hwpxjs", active_env=active_env, search_path=search_path)
    if discovered_hwpxjs is not None:
        return _report(
            candidate_id=HWPXJS_CANDIDATE_ID,
            status="available",
            executable=discovered_hwpxjs,
            recommended_args=HWPXJS_HWP_TO_HWPX_ARGS,
            reasons=("hwpxjs_cli_found_for_default_registration",),
            evidence_refs=(_HWPXJS_SOURCE_REF, _ADR_REF),
        )

    discovered = _find_executable("hwpforge", active_env=active_env, search_path=search_path)
    if discovered is None:
        return _report(
            candidate_id=HWPFORGE_CANDIDATE_ID,
            status="missing",
            executable=None,
            recommended_args=HWPFORGE_HWP5_TO_HWPX_ARGS,
            reasons=("hwpforge_cli_not_found",),
            evidence_refs=(_HWPFORGE_SOURCE_REF, _ADR_REF),
        )
    return _report(
        candidate_id=HWPFORGE_CANDIDATE_ID,
        status="available",
        executable=discovered,
        recommended_args=HWPFORGE_HWP5_TO_HWPX_ARGS,
        reasons=("hwpforge_cli_found_but_not_registered",),
        evidence_refs=(_HWPFORGE_SOURCE_REF, _ADR_REF),
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
    candidate = Path(found).expanduser().resolve(strict=False)
    if not _is_executable_file(candidate):
        return None
    return candidate


def _is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def _configured_args_or_default(active_env: Mapping[str, str]) -> tuple[str, ...]:
    raw = active_env.get(HWP_CONVERTER_ARGS_ENV)
    if not raw:
        return HWPFORGE_HWP5_TO_HWPX_ARGS
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return HWPFORGE_HWP5_TO_HWPX_ARGS
    if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
        return HWPFORGE_HWP5_TO_HWPX_ARGS
    return tuple(decoded)


def _report(
    *,
    candidate_id: str,
    status: BridgeProbeStatus,
    executable: Path | None,
    recommended_args: tuple[str, ...],
    reasons: tuple[str, ...],
    evidence_refs: tuple[str, ...],
) -> HwpToHwpxBridgeProbeReport:
    recommended_env = {
        HWP_CONVERTER_ARGS_ENV: json.dumps(list(recommended_args)),
        HWP_CONVERTER_ENGINE_ID_ENV: candidate_id,
        HWP_CONVERTER_TIMEOUT_ENV: "120",
    }
    if executable is not None:
        recommended_env[HWP_CONVERTER_ENV] = str(executable)
    return HwpToHwpxBridgeProbeReport(
        candidate_id=candidate_id,
        status=status,
        source_format=DocumentFormat.hwp,
        output_format=DocumentFormat.hwpx,
        executable=executable,
        recommended_args=recommended_args,
        recommended_env=recommended_env,
        reasons=reasons,
        evidence_refs=evidence_refs,
    )
