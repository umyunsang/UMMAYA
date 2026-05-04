# SPDX-License-Identifier: Apache-2.0
"""Target-state citizen-demand dataset checks.

This dataset is not a current ToolRegistry eval. It protects the product target:
citizens ask for national administrative outcomes, and KOSMOS later maps those
requests onto live, mock, or handoff channels.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

_DATASET_PATH = (
    Path(__file__).parent.parent.parent
    / "eval"
    / "scenarios"
    / "national_ax_citizen_requests_v1.yaml"
)

_BANNED_CURRENT_CODE_KEYS = frozenset(
    {
        "adapter_id",
        "expected_tool_id",
        "expected_tool_sequence",
        "fixture_refs",
        "tool_id",
    }
)


def _load_dataset() -> dict[str, object]:
    with _DATASET_PATH.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)

    assert isinstance(loaded, dict), "Dataset root must be a mapping"
    return cast("dict[str, object]", loaded)


def _mapping(value: object, label: str) -> dict[str, object]:
    assert isinstance(value, dict), f"{label} must be a mapping"
    return cast("dict[str, object]", value)


def _list(value: object, label: str) -> list[object]:
    assert isinstance(value, list), f"{label} must be a list"
    return value


def _string_set(value: object, label: str) -> set[str]:
    items = _list(value, label)
    assert all(isinstance(item, str) for item in items), f"{label} must contain strings"
    return set(cast("list[str]", items))


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        keys: set[str] = set()
        for key, child in value.items():
            assert isinstance(key, str), "YAML keys must be strings"
            keys.add(key)
            keys.update(_walk_keys(child))
        return keys
    if isinstance(value, list):
        keys = set()
        for item in value:
            keys.update(_walk_keys(item))
        return keys
    return set()


def test_dataset_exists_and_declares_target_state_source() -> None:
    assert _DATASET_PATH.exists()

    dataset = _load_dataset()
    assert dataset["version"] == 1
    assert dataset["dataset_id"] == "national_ax_citizen_requests_v1"
    assert dataset["source_basis"] == "citizen_demand_target_state"


def test_dataset_is_not_current_adapter_inventory() -> None:
    dataset = _load_dataset()

    keys = _walk_keys(dataset)
    assert not (_BANNED_CURRENT_CODE_KEYS & keys), (
        "Target-state citizen scenarios must not be keyed to current adapter IDs, "
        "tool IDs, or fixture inventory"
    )


def test_dataset_covers_national_infrastructure_domains() -> None:
    dataset = _load_dataset()
    expected_domains = _string_set(dataset["coverage_domains"], "coverage_domains")
    scenarios = _list(dataset["scenarios"], "scenarios")
    scenario_domains = {
        _mapping(scenario, "scenario")["lifecycle_domain"] for scenario in scenarios
    }

    assert len(scenarios) >= 24
    assert expected_domains <= scenario_domains
    assert {
        "tax",
        "civil_affairs",
        "payments",
        "utilities",
        "identity",
        "welfare",
        "healthcare",
        "housing",
        "business",
        "labor",
        "education",
        "safety",
        "personal_data",
    } <= scenario_domains


def test_each_scenario_has_citizen_demand_and_ax_chain() -> None:
    dataset = _load_dataset()
    allowed_primitives = _string_set(dataset["allowed_primitives"], "allowed_primitives")
    scenarios = _list(dataset["scenarios"], "scenarios")

    for index, raw_scenario in enumerate(scenarios):
        scenario = _mapping(raw_scenario, f"scenario[{index}]")
        scenario_id = scenario["id"]
        request_ko = scenario["request_ko"]
        chain = _list(scenario["expected_ax_chain"], f"{scenario_id}.expected_ax_chain")

        assert isinstance(scenario_id, str)
        assert isinstance(request_ko, str)
        assert any(ord(char) > 127 for char in request_ko), (
            f"{scenario_id} must preserve a Korean citizen request"
        )
        assert scenario["priority"] in {"P0", "P1", "P2"}
        assert _list(scenario["agencies_or_infrastructure"], f"{scenario_id}.agencies")
        assert _list(scenario["citizen_intent_verbs"], f"{scenario_id}.intent_verbs")
        assert _mapping(
            scenario["permission_requirements"], f"{scenario_id}.permission_requirements"
        )
        assert _list(
            scenario["expected_system_behavior"], f"{scenario_id}.expected_system_behavior"
        )
        assert _list(scenario["evaluation_focus"], f"{scenario_id}.evaluation_focus")
        assert chain, f"{scenario_id} must declare at least one AX chain step"

        for step_index, raw_step in enumerate(chain):
            step = _mapping(raw_step, f"{scenario_id}.expected_ax_chain[{step_index}]")
            assert step["primitive"] in allowed_primitives
            assert isinstance(step["purpose"], str)
            assert step["purpose"]


def test_p0_scenarios_include_confirmation_for_sensitive_execution() -> None:
    dataset = _load_dataset()
    scenarios = _list(dataset["scenarios"], "scenarios")
    p0_scenarios = [
        _mapping(scenario, "scenario")
        for scenario in scenarios
        if _mapping(scenario, "scenario")["priority"] == "P0"
    ]

    assert len(p0_scenarios) >= 8
    for scenario in p0_scenarios:
        permissions = _mapping(
            scenario["permission_requirements"], f"{scenario['id']}.permission_requirements"
        )
        confirmations = _list(permissions["user_confirmations"], "user_confirmations")
        sensitive_data = _list(permissions["sensitive_data"], "sensitive_data")
        assert confirmations, f"{scenario['id']} must require explicit citizen confirmation"
        assert sensitive_data, f"{scenario['id']} must declare sensitive data categories"
