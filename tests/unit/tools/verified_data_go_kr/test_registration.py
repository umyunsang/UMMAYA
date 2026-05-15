# SPDX-License-Identifier: Apache-2.0
"""Registration tests for verified data.go.kr adapters."""

from __future__ import annotations

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verified_data_go_kr import (
    VERIFIED_DATA_GO_KR_ADAPTERS,
)
from ummaya.tools.verified_data_go_kr import (
    register as register_verified_data_go_kr,
)


def test_register_verified_data_go_kr_tools_adds_all_adapters() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    register_verified_data_go_kr(registry, executor)

    expected_ids = {spec.tool_id for spec in VERIFIED_DATA_GO_KR_ADAPTERS}
    assert set(registry._tools) == expected_ids
    assert set(executor._adapters) == expected_ids


def test_registered_tools_are_find_live_read_only_with_policy_citations() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    register_verified_data_go_kr(registry, executor)

    for spec in VERIFIED_DATA_GO_KR_ADAPTERS:
        tool = registry.find(spec.tool_id)
        assert tool.primitive == "find"
        assert tool.adapter_mode == "live"
        assert tool.policy is not None
        assert tool.policy.citizen_facing_gate == "read-only"
        assert tool.policy.real_classification_url == spec.policy_url
        assert spec.dataset_id in tool.search_hint
