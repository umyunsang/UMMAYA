# SPDX-License-Identifier: Apache-2.0
"""Tests for stdio model-facing tool assembly decisions."""

from __future__ import annotations

from ummaya.ipc.stdio import _should_append_tui_tool_to_llm_tools


def test_should_append_tui_tool_keeps_root_wrappers_when_adapters_loaded():
    """Concrete adapter schemas augment root wrappers instead of replacing them."""
    backend_tool_names = {"kma_current_observation"}

    assert (
        _should_append_tui_tool_to_llm_tools(
            "find",
            backend_tool_names,
            has_concrete_backend_tools=True,
        )
        is True
    )
    assert (
        _should_append_tui_tool_to_llm_tools(
            "kma_current_observation",
            backend_tool_names,
            has_concrete_backend_tools=True,
        )
        is False
    )
    assert (
        _should_append_tui_tool_to_llm_tools(
            "ToolSearch",
            backend_tool_names,
            has_concrete_backend_tools=True,
        )
        is True
    )


def test_should_append_tui_tool_keeps_root_wrappers_for_legacy_turns():
    """Root primitives remain available when no concrete adapter was retrieved."""
    assert (
        _should_append_tui_tool_to_llm_tools(
            "find",
            set(),
            has_concrete_backend_tools=False,
        )
        is True
    )
