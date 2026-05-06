# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the real-use audit report helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def _load_audit_module() -> Any:
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "realuse-audit-report.py"
    spec = importlib.util.spec_from_file_location("realuse_audit_report", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_collect_tool_calls_falls_back_to_sampled_scrollback(tmp_path: Path) -> None:
    """Final scrollback can be an error viewport while sampled snapshots hold tools."""
    audit = _load_audit_module()
    root = tmp_path
    (root / "final-scrollback.txt").write_text(
        "⏺ [KOSMOS backend error] Streaming idle timeout\n",
        encoding="utf-8",
    )
    (root / "snap-003-MOB-001-permission-0-before-allow-scrollback.txt").write_text(
        "⏺ auth(mock_verify_ganpyeon_injeung)\n",
        encoding="utf-8",
    )
    (root / "snap-004-MOB-001-permission-0-after-allow-scrollback.txt").write_text(
        "⏺ auth(mock_verify_ganpyeon_injeung)\n",
        encoding="utf-8",
    )
    (root / "snap-005-MOB-001-permission-1-before-allow-scrollback.txt").write_text(
        "⏺ auth(mock_verify_ganpyeon_injeung)\n"
        "⏺ auth(mock_verify_ganpyeon_injeung)\n",
        encoding="utf-8",
    )

    calls = audit.collect_tool_calls(root, audit.iter_text_files(root))

    assert [(call.name, call.argument) for call in calls] == [
        ("verify", "mock_verify_ganpyeon_injeung"),
        ("verify", "mock_verify_ganpyeon_injeung"),
    ]
