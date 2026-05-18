# SPDX-License-Identifier: Apache-2.0
"""Integration tests for live MobileID check registration."""

from __future__ import annotations

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verify_canonical_map import resolve_family


def test_live_mobileid_tool_is_registered_as_check_only() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    tool = registry.lookup("live_verify_mobile_id")

    assert tool.primitive == "check"
    assert tool.adapter_mode == "live"
    assert tool.published_tier_minimum == "mobile_id_mdl_aal2"
    assert tool.nist_aal_hint == "AAL2"
    assert "live_verify_mobile_id" in executor._adapters


def test_live_mobileid_canonical_map_resolves_to_mobile_id_family() -> None:
    assert resolve_family("live_verify_mobile_id") == "mobile_id"


def test_live_mobileid_registration_does_not_remove_mock_mobileid() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    ids = {tool.id for tool in registry.all_tools()}

    assert "live_verify_mobile_id" in ids
    assert "mock_verify_mobile_id" in ids
    assert "mock_verify_module_modid" in ids
