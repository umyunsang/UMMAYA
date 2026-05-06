# SPDX-License-Identifier: Apache-2.0
"""T031 — NMC discoverability via lookup(mode='search').

Created as a separate file rather than adding to test_lookup_search.py because:
  - test_lookup_search.py uses a module-scoped ``full_registry`` fixture that
    calls ``register_all_tools()``. NMC is intentionally NOT registered in
    ``register_all.py`` until Stage 3 (T033). Mixing a test-local NMC
    registration into a module-scoped fixture that also runs the full-registry
    tests would cause duplicate-registration errors and tight coupling.
  - Keeping NMC discovery tests isolated makes the Stage 3 integration
    (T033) straightforward: when NMC is added to register_all.py the
    test_lookup_search.py fixture will pick it up automatically, while this
    file continues testing the standalone NMC registration path.

No live API calls are made.
"""

from __future__ import annotations

import pytest

from kosmos.tools.executor import ToolExecutor
from kosmos.tools.lookup import lookup
from kosmos.tools.models import AdapterCandidate, LookupSearchInput, LookupSearchResult
from kosmos.tools.nmc.emergency_search import NMC_EMERGENCY_SEARCH_TOOL, register
from kosmos.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Fixtures: test-local registry with only NMC registered
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def nmc_only_registry() -> ToolRegistry:
    """ToolRegistry containing only nmc_emergency_search (module scope)."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)
    return registry


# ---------------------------------------------------------------------------
# T031: NMC discoverable via lookup(mode='search')
# ---------------------------------------------------------------------------


class TestNmcDiscoverable:
    """Verify nmc_emergency_search surfaces in search results for relevant queries."""

    @pytest.mark.asyncio
    async def test_nmc_discoverable_korean_query(self, nmc_only_registry: ToolRegistry) -> None:
        """lookup(mode='search', query='응급실') must include nmc_emergency_search as candidate."""
        inp = LookupSearchInput(mode="search", query="응급실")
        result = await lookup(inp, registry=nmc_only_registry)

        assert isinstance(result, LookupSearchResult), (
            f"Expected LookupSearchResult, got {type(result).__name__}"
        )
        assert result.kind == "search"

        # NMC is the only tool registered; it must appear in candidates.
        tool_ids = [c.tool_id for c in result.candidates]
        assert "nmc_emergency_search" in tool_ids, (
            f"nmc_emergency_search not found in search candidates: {tool_ids}"
        )

    @pytest.mark.asyncio
    async def test_nmc_discoverable_english_query(self, nmc_only_registry: ToolRegistry) -> None:
        """English query 'emergency room' must surface nmc_emergency_search."""
        inp = LookupSearchInput(mode="search", query="nearest emergency room")
        result = await lookup(inp, registry=nmc_only_registry)

        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates]
        assert "nmc_emergency_search" in tool_ids, (
            f"nmc_emergency_search not in English query candidates: {tool_ids}"
        )

    @pytest.mark.asyncio
    async def test_nmc_candidate_reflects_read_only_contract(
        self, nmc_only_registry: ToolRegistry
    ) -> None:
        """AdapterCandidate for NMC must reflect the read-only public lookup contract."""
        inp = LookupSearchInput(mode="search", query="응급실")
        result = await lookup(inp, registry=nmc_only_registry)

        assert isinstance(result, LookupSearchResult)
        nmc_candidates = [c for c in result.candidates if c.tool_id == "nmc_emergency_search"]
        assert nmc_candidates, "nmc_emergency_search not in candidates"

        candidate = nmc_candidates[0]
        assert isinstance(candidate, AdapterCandidate)

        assert candidate.tool_id == "nmc_emergency_search"
        assert NMC_EMERGENCY_SEARCH_TOOL.policy is not None
        assert NMC_EMERGENCY_SEARCH_TOOL.policy.citizen_facing_gate == "read-only"

    @pytest.mark.asyncio
    async def test_nmc_candidate_required_params(self, nmc_only_registry: ToolRegistry) -> None:
        """NMC candidate must expose required_params reflecting the input schema."""
        inp = LookupSearchInput(mode="search", query="응급실 병상")
        result = await lookup(inp, registry=nmc_only_registry)

        assert isinstance(result, LookupSearchResult)
        nmc_candidates = [c for c in result.candidates if c.tool_id == "nmc_emergency_search"]
        assert nmc_candidates

        candidate = nmc_candidates[0]
        # required_params must be a list (may be empty if schema has defaults,
        # but all NMC fields are required with no defaults).
        assert isinstance(candidate.required_params, list)

    @pytest.mark.asyncio
    async def test_nmc_search_result_is_valid_adapter_candidate(
        self, nmc_only_registry: ToolRegistry
    ) -> None:
        """All candidates from NMC registry search must be valid AdapterCandidate instances."""
        inp = LookupSearchInput(mode="search", query="응급 의료")
        result = await lookup(inp, registry=nmc_only_registry)

        assert isinstance(result, LookupSearchResult)
        for candidate in result.candidates:
            assert isinstance(candidate, AdapterCandidate)
            assert candidate.score >= 0.0
            assert isinstance(candidate.tool_id, str)
            assert candidate.tool_id  # non-empty

    @pytest.mark.asyncio
    async def test_nmc_tool_metadata_integrity(self) -> None:
        """NMC_EMERGENCY_SEARCH_TOOL constants match the spec contract."""
        assert NMC_EMERGENCY_SEARCH_TOOL.id == "nmc_emergency_search"
        assert NMC_EMERGENCY_SEARCH_TOOL.is_concurrency_safe is False
        assert NMC_EMERGENCY_SEARCH_TOOL.cache_ttl_seconds == 0
