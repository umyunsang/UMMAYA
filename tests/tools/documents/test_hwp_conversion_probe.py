# SPDX-License-Identifier: Apache-2.0
"""Diagnostics for HWP-to-HWPX conversion bridge candidates."""

from __future__ import annotations

import os
from pathlib import Path

from ummaya.tools.documents.conversion import build_default_document_conversion_registry
from ummaya.tools.documents.hwp_conversion_probe import (
    HWPFORGE_HWP5_TO_HWPX_ARGS,
    probe_hwp_to_hwpx_bridge,
)
from ummaya.tools.documents.models import DocumentFormat


def test_probe_reports_missing_hwpforge_without_auto_registering_converter() -> None:
    report = probe_hwp_to_hwpx_bridge(env={}, search_path=())

    assert report.status == "missing"
    assert report.candidate_id == "hwpforge-cli-convert-hwp5"
    assert report.source_format is DocumentFormat.hwp
    assert report.output_format is DocumentFormat.hwpx
    assert "hwpforge_cli_not_found" in report.reasons
    assert "upstream:hwpforge-cli-v0.6.0-convert-hwp5" in report.evidence_refs
    assert report.recommended_args == HWPFORGE_HWP5_TO_HWPX_ARGS
    assert report.recommended_env["UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON"]

    registry = build_default_document_conversion_registry(env={})

    assert registry.get(DocumentFormat.hwp, DocumentFormat.hwpx) is None


def test_probe_detects_hwpforge_cli_on_path_without_mutating_registry(tmp_path: Path) -> None:
    executable = tmp_path / "hwpforge"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    report = probe_hwp_to_hwpx_bridge(
        env={},
        search_path=(str(tmp_path),),
    )

    assert report.status == "available"
    assert report.executable == executable.resolve()
    assert report.recommended_env["UMMAYA_HWP_TO_HWPX_CONVERTER"] == str(executable.resolve())
    assert report.recommended_args == (
        "--json",
        "convert-hwp5",
        "{source}",
        "--output",
        "{output}",
    )

    registry = build_default_document_conversion_registry(env={})

    assert registry.get(DocumentFormat.hwp, DocumentFormat.hwpx) is None


def test_probe_detects_hwpxjs_cli_on_path_without_mutating_registry(tmp_path: Path) -> None:
    executable = tmp_path / "hwpxjs"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    report = probe_hwp_to_hwpx_bridge(
        env={},
        search_path=(str(tmp_path),),
    )

    assert report.status == "available"
    assert report.candidate_id == "hwpxjs-cli-convert-hwp"
    assert report.executable == executable.resolve()
    assert report.recommended_env["UMMAYA_HWP_TO_HWPX_CONVERTER"] == str(executable.resolve())
    assert report.recommended_args == ("convert:hwp", "{source}", "{output}")
    assert "hwpxjs_cli_found_for_default_registration" in report.reasons
    assert "upstream:ssabro-hwpxjs-v0.4.0" in report.evidence_refs

    registry = build_default_document_conversion_registry(env={})

    assert registry.get(DocumentFormat.hwp, DocumentFormat.hwpx) is None


def test_probe_reports_explicit_env_bridge_as_configured(tmp_path: Path) -> None:
    executable = tmp_path / "hwpforge"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    env = {
        "UMMAYA_HWP_TO_HWPX_CONVERTER": str(executable),
        "UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON": (
            '["--json","convert-hwp5","{source}","--output","{output}"]'
        ),
        "UMMAYA_HWP_TO_HWPX_CONVERTER_ENGINE_ID": "hwpforge-cli-convert-hwp5",
    }

    report = probe_hwp_to_hwpx_bridge(env=env, search_path=())

    assert report.status == "configured"
    assert report.executable == executable.resolve()
    assert report.reasons == ("explicit_hwp_bridge_configured",)


def test_probe_uses_process_path_without_shell_expansion(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "hwpforge"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    report = probe_hwp_to_hwpx_bridge(env=os.environ)

    assert report.status == "available"
    assert report.executable == executable.resolve()
