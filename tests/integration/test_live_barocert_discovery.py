# SPDX-License-Identifier: Apache-2.0
"""Integration coverage for live BaroCert check discovery metadata."""

from __future__ import annotations

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verify_canonical_map import resolve_family


def test_live_barocert_check_is_discoverable_and_check_only() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    tool = registry.find("live_verify_ganpyeon_injeung")

    assert tool.primitive == "check"
    assert tool.adapter_mode == "live"
    assert "check" in tool.category
    assert "live" in tool.category
    assert resolve_family("live_verify_ganpyeon_injeung") == "ganpyeon_injeung"


def test_mock_and_live_ganpyeon_ids_resolve_to_same_family() -> None:
    assert resolve_family("mock_verify_ganpyeon_injeung") == "ganpyeon_injeung"
    assert resolve_family("live_verify_ganpyeon_injeung") == "ganpyeon_injeung"
