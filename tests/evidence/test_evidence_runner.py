# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path


def test_evidence_runner_emits_required_gates(tmp_path: Path) -> None:
    from ummaya.evidence.runner import run_dataset

    evidence = run_dataset(
        scenario_path=Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml"),
        source_ref="test",
    )

    assert evidence.schema_version == "evidence.v2"
    assert evidence.source_ref == "test"
    assert evidence.scenario_count > 0
    assert evidence.scenario_ids
    assert {gate.name for gate in evidence.gates} == {
        "contract",
        "scenario",
        "observability",
        "adversarial",
        "ux",
        "live_canary",
    }

    output_path = tmp_path / "run.json"
    output_path.write_text(evidence.model_dump_json(indent=2), encoding="utf-8")
    decoded = json.loads(output_path.read_text(encoding="utf-8"))
    assert decoded["schema_version"] == "evidence.v2"
    assert decoded["task_registry_id"] == "ummaya/evidence-task-registry"
    assert decoded["dataset_ref"] == "ummaya/national-ax-core@local"
    assert decoded["task_count"] == 1
    assert decoded["task_ids"] == ["ummaya/national-ax-core"]


def test_evidence_runner_rejects_model_visible_adapter_keys(tmp_path: Path) -> None:
    import pytest

    from ummaya.evidence.runner import EvidenceContractError, run_dataset

    scenario_path = tmp_path / "bad.yaml"
    scenario_path.write_text(
        """
version: 1
dataset_id: bad
coverage_domains: [tax]
scenarios:
  - id: TAX-001
    lifecycle_domain: tax
    request_ko: "세금 신고해줘."
    tool_id: leaked_internal_adapter
    expected_ax_chain:
      - primitive: verify
        purpose: identity
    permission_requirements:
      identity_assurance: high
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(EvidenceContractError, match="tool_id"):
        run_dataset(scenario_path=scenario_path, source_ref="test")


def test_default_task_registry_resolves_harbor_style_dataset() -> None:
    from ummaya.evidence.task_registry import load_task_registry

    registry = load_task_registry(Path("evidence/registry.yaml"))
    dataset = registry.resolve_dataset("ummaya/national-ax-core@local")

    assert registry.registry_id == "ummaya/evidence-task-registry"
    assert dataset.dataset_id == "national_ax_citizen_requests_v1"
    assert dataset.scenario_path == Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml")
    assert tuple(task.task_id for task in dataset.tasks) == ("ummaya/national-ax-core",)

    task = dataset.tasks[0]
    assert task.task_dir == Path("evidence/tasks/national-ax-core")
    assert task.instruction_path == Path("evidence/tasks/national-ax-core/instruction.md")
    assert task.verifier_path == Path("evidence/tasks/national-ax-core/tests/test.sh")
    assert task.environment_os == "linux"
    assert task.allow_internet is False


def test_task_registry_rejects_model_visible_implementation_keys(tmp_path: Path) -> None:
    import pytest

    from ummaya.evidence.task_registry import TaskRegistryError, load_task_registry

    task_dir = tmp_path / "tasks" / "bad"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Do the task.\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        """
schema_version = "1.1"

[task]
name = "ummaya/bad"
description = "Bad registry entry"

[metadata]
dataset_id = "bad"
tool_id = "leaked_internal_adapter"

[verifier]
timeout_sec = 120.0

[environment]
os = "linux"
allow_internet = false
""".strip(),
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        f"""
version: 1
registry_id: test/registry
datasets:
  - ref: test/bad@local
    dataset_id: bad
    scenario_path: evidence/scenarios/national_ax_citizen_requests_v1.yaml
    task_paths:
      - {task_dir}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(TaskRegistryError, match="tool_id"):
        load_task_registry(registry_path)
