# SPDX-License-Identifier: Apache-2.0
"""Tests for central tool registration entry point (T039)."""

import pytest

from kosmos.tools.executor import ToolExecutor
from kosmos.tools.register_all import register_all_tools
from kosmos.tools.registry import ToolRegistry


class TestToolRegistration:
    """Verify register_all_tools() wires all adapters correctly."""

    def test_registers_all_tools(self) -> None:
        """All tools are registered after calling register_all_tools.

        Count history (Epic #507):
          T049  —2 (address_to_region, address_to_grid removed)
          Stage 3 (T033/T048/T056)  +3 (nmc_emergency_search,
            kma_forecast_fetch, hira_hospital_search)
          Phase 2 (spec 029)  +2 (nfa_emergency_info_service,
            mohw_welfare_eligibility_search)
        Total: 15 (= 2 MVP core + 8 legacy adapters + 3 seed adapters + 2 Phase 2 stubs).
        """
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        # Spec 2296 SC-003: 12 Live + 2 MVP-surface (resolve_location, lookup)
        # + 2 lookup mocks (mock_lookup_module_hometax_simplified,
        # mock_lookup_module_gov24_certificate) = 16
        # Epic η #2298 FR-021: + 2 primitive surfaces (verify, submit) = 18.
        # Required so the LLM can emit the
        # citizen-OPAQUE chain via OpenAI tool_calls schema.
        # Epic ζ #2297 path B (live smoke 2026-04-30): + 15 non-core mock
        # adapter wrappers (10 verify + 5 submit via discovery_bridge) = 33.
        # is_core=False so the LLM's primary tool list stays at active
        # primitives + lookup-class; these participate in
        # lookup(mode="search") BM25 corpus only.
        assert len(registry) == 33

    def test_tool_ids_present(self) -> None:
        """Each expected tool_id is in the registry.

        Note: address_to_region and address_to_grid were removed in T049 (Epic
        #507).  Administrative code and grid resolution are now backend-only
        (juso/sgis helpers and latlon_to_lcc respectively).
        """
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        expected = {
            # MVP LLM-visible core surface (T028)
            "resolve_location",
            "lookup",
            # Adapters
            "koroad_accident_search",
            "koroad_accident_hazard_search",
            "kma_weather_alert_status",
            "kma_current_observation",
            # Stage 3 seed adapters (Epic #507)
            "nmc_emergency_search",
            "kma_forecast_fetch",
            "hira_hospital_search",
            # Phase 2 adapters (spec 029)
            "nfa_emergency_info_service",
            "mohw_welfare_eligibility_search",
        }
        for tool_id in expected:
            assert tool_id in registry, f"{tool_id} not found in registry"

    def test_adapters_bound(self) -> None:
        """Each adapter tool has a corresponding adapter in the executor.

        Note: resolve_location and lookup are core surface tools — they are
        handled directly by the orchestrator and do NOT have executor adapters.
        Note: address_to_region and address_to_grid were removed in T049 (Epic
        #507) — they are no longer LLM-visible tools.
        """
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        expected = {
            "koroad_accident_search",
            "koroad_accident_hazard_search",
            "kma_weather_alert_status",
            "kma_current_observation",
            # Stage 3 seed adapters (Epic #507)
            "nmc_emergency_search",
            "kma_forecast_fetch",
            "hira_hospital_search",
            # Phase 2 adapters (spec 029)
            "nfa_emergency_info_service",
            "mohw_welfare_eligibility_search",
        }
        for tool_id in expected:
            assert tool_id in executor._adapters, f"No adapter for {tool_id}"

    def test_no_import_errors(self) -> None:
        """register_all_tools completes without import errors."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        # Should not raise
        register_all_tools(registry, executor)

    def test_core_tools_include_mvp_surface(self) -> None:
        """resolve_location and lookup must appear in core_tools() (T028, FR-001)."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        core_ids = {t.id for t in registry.core_tools()}
        assert "resolve_location" in core_ids
        assert "lookup" in core_ids

    def test_idempotent_fails_on_duplicate(self) -> None:
        """Calling register_all_tools twice raises DuplicateToolError."""
        from kosmos.tools.errors import DuplicateToolError

        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        with pytest.raises(DuplicateToolError):
            register_all_tools(registry, executor)
