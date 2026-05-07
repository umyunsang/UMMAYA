# SPDX-License-Identifier: Apache-2.0
"""Spec 1979 T018 — install → invoke integration tests.

Verifies the full citizen flow:
1. plugin_op_request:install → register_plugin_adapter populates ToolRegistry
2. Next ChatRequestFrame.tools[] auto-includes the new plugin via
   ToolRegistry.export_core_tools_openai() fallback path (R-6 verdict)
3. Plugin tool surfaces via the active primitive surface

Because a true E2E install requires fixture catalog + bundle + SLSA setup,
these tests exercise the post-install registry surface via direct
register_plugin_adapter calls. The dispatcher path is covered by
test_plugin_op_dispatch.py.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def stub_tool() -> Any:
    """Build a minimal GovAPITool that satisfies registry invariants."""
    from pydantic import BaseModel, ConfigDict, Field

    from kosmos.tools.models import GovAPITool

    class _LookupInput(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid")
        query: str = Field(min_length=1)

    class _LookupOutput(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid")
        result: str

    return GovAPITool(
        id="plugin.fixture_test.lookup",
        ministry="OTHER",
        category=["test"],
        endpoint="https://test.local/lookup",
        name_ko="픽스처 테스트 플러그인",
        name_en="Fixture test plugin",
        description_ko="T018 통합 테스트용 fixture 플러그인",
        description_en="T018 integration-test fixture plugin",
        search_hint="fixture test plugin lookup 픽스처 테스트",
        auth_type="public",
        auth_level="public",
        pipa_class="non_personal",
        dpa_reference=None,
        requires_auth=False,
        is_personal_data=False,
        is_concurrency_safe=True,
        cache_ttl_seconds=60,
        rate_limit_per_minute=30,
        is_irreversible=False,
        is_core=True,
        input_schema=_LookupInput,
        output_schema=_LookupOutput,
    )


class TestInstallToInvoke:
    """T018 — installed plugin tool surfaces in core_tools + export_core_tools_openai."""

    def test_registered_plugin_appears_in_core_tools(self, stub_tool: Any) -> None:
        from kosmos.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(stub_tool)

        core = registry.core_tools()
        assert any(t.id == "plugin.fixture_test.lookup" for t in core), (
            "freshly registered plugin tool must surface in core_tools"
        )

    def test_registered_plugin_appears_in_export_core_tools_openai(self, stub_tool: Any) -> None:
        from kosmos.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(stub_tool)

        exported = registry.export_core_tools_openai()
        ids = [t.get("function", {}).get("name") if isinstance(t, dict) else None for t in exported]
        assert "plugin.fixture_test.lookup" in ids, (
            "freshly registered plugin tool must surface in OpenAI tool export "
            "(this is the R-6 fallback path consumed by stdio.py:1192-1195)"
        )

    def test_inactive_plugin_excluded_from_core_tools(self, stub_tool: Any) -> None:
        """R-3+R-4 verdict: _inactive shadow set filters core_tools."""
        from kosmos.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(stub_tool)
        registry.set_active("plugin.fixture_test.lookup", False)

        assert not registry.is_active("plugin.fixture_test.lookup")
        core = registry.core_tools()
        assert all(t.id != "plugin.fixture_test.lookup" for t in core), (
            "inactive plugin tool must not surface in core_tools"
        )

    def test_inactive_plugin_excluded_from_openai_export(self, stub_tool: Any) -> None:
        from kosmos.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(stub_tool)
        registry.set_active("plugin.fixture_test.lookup", False)

        exported = registry.export_core_tools_openai()
        ids = [t.get("function", {}).get("name") if isinstance(t, dict) else None for t in exported]
        assert "plugin.fixture_test.lookup" not in ids, (
            "inactive plugin must not surface in the LLM-visible tool inventory"
        )

    def test_deregister_removes_plugin_entirely(self, stub_tool: Any) -> None:
        """Spec 1979 ToolRegistry.deregister — full removal (used by uninstall_plugin)."""
        from kosmos.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(stub_tool)
        assert "plugin.fixture_test.lookup" in registry

        registry.deregister("plugin.fixture_test.lookup")
        assert "plugin.fixture_test.lookup" not in registry
        assert all(t.id != "plugin.fixture_test.lookup" for t in registry.all_tools())
