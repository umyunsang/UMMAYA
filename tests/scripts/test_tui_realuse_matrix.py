# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_matrix_module() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "tui-realuse-matrix.py"
    spec = importlib.util.spec_from_file_location("tui_realuse_matrix", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_matrix_contains_core_primitives_and_negative_flows() -> None:
    module = load_matrix_module()
    matrix = Path("specs/2773-rollback-debug-infra/scenario-matrix.json")
    scenarios = module.load_matrix(matrix)

    ids = {scenario.id for scenario in scenarios}
    assert "LOC-ER-HADAN-001" in ids
    assert "LOC-WEATHER-DADAE-001" in ids
    assert "WELFARE-APPLICATION-001" in ids
    assert "NEG-PERMISSION-DENY-SUBMIT-001" in ids

    expected_tokens = " ".join(" ".join(scenario.expected_chain) for scenario in scenarios)
    for token in ("resolve_location", "verify", "submit"):
        assert token in expected_tokens


def test_dry_run_builds_capture_and_audit_commands(tmp_path: Path) -> None:
    module = load_matrix_module()
    matrix = Path("specs/2773-rollback-debug-infra/scenario-matrix.json")
    scenario = next(
        item for item in module.load_matrix(matrix) if item.id == "LOC-WEATHER-DADAE-001"
    )

    result = module.run_scenario(
        scenario,
        capture_root=tmp_path,
        strict_frames=True,
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["capture_cmd"][0] == "bun"
    assert "--expect-chain" in result["audit_cmd"]
    assert "--require-expanded-trace" in result["audit_cmd"]
    assert "--strict-frames" in result["audit_cmd"]


def test_audit_only_reuses_existing_capture_dir(tmp_path: Path) -> None:
    module = load_matrix_module()
    matrix = Path("specs/2773-rollback-debug-infra/scenario-matrix.json")
    scenario = next(
        item for item in module.load_matrix(matrix) if item.id == "WELFARE-APPLICATION-001"
    )
    (tmp_path / scenario.id).mkdir()

    commands: list[list[str]] = []

    def fake_run_command(command: list[str], env: dict[str, str]) -> int:
        commands.append(command)
        return 0

    module.run_command = fake_run_command
    result = module.run_scenario(
        scenario,
        capture_root=tmp_path,
        strict_frames=True,
        dry_run=False,
        audit_only=True,
    )

    assert result["status"] == "pass"
    assert result["capture_status"] == 0
    assert result["audit_status"] == 0
    assert len(commands) == 1
    assert commands[0][1] == "scripts/tui-realuse-audit.py"
