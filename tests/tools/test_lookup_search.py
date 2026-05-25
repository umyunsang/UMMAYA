# SPDX-License-Identifier: Apache-2.0
"""Tests for lookup(mode='search') BM25 retrieval gate — T020.

Verifies that koroad_accident_hazard_search surfaces as a top candidate
when a relevant query is submitted via the lookup facade.

No live API calls are made.
"""

from __future__ import annotations

import pytest

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.lookup import lookup
from ummaya.tools.models import (
    AdapterCandidate,
    LookupSearchInput,
    LookupSearchResult,
)
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry


@pytest.fixture(scope="module")
def full_registry() -> ToolRegistry:
    """A ToolRegistry with all tools registered (module scope for speed)."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    return registry


@pytest.fixture(scope="module")
def full_executor(full_registry) -> ToolExecutor:
    executor = ToolExecutor(full_registry)
    return executor


# ---------------------------------------------------------------------------
# T020: koroad_accident_hazard_search must rank in top results for relevant query
# ---------------------------------------------------------------------------


class TestLookupSearchHazardRanking:
    @pytest.mark.asyncio
    async def test_korean_query_surfaces_hazard_search(self, full_registry, full_executor):
        """Korean accident hazard query must return koroad_accident_hazard_search."""
        inp = LookupSearchInput(mode="search", query="교통사고 위험지점 행정동코드")
        result = await lookup(inp, registry=full_registry, executor=full_executor)
        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates]
        assert "koroad_accident_hazard_search" in tool_ids, (
            f"koroad_accident_hazard_search not in candidates: {tool_ids}"
        )

    @pytest.mark.asyncio
    async def test_english_query_surfaces_hazard_search(self, full_registry, full_executor):
        """English query for accident hazard must return koroad_accident_hazard_search."""
        inp = LookupSearchInput(mode="search", query="accident hazard spot adm_cd")
        result = await lookup(inp, registry=full_registry, executor=full_executor)
        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates]
        assert "koroad_accident_hazard_search" in tool_ids, (
            f"koroad_accident_hazard_search not in candidates: {tool_ids}"
        )

    @pytest.mark.asyncio
    async def test_search_result_candidates_are_adapter_candidates(
        self, full_registry, full_executor
    ):
        """All candidates must be AdapterCandidate instances with valid fields."""
        inp = LookupSearchInput(mode="search", query="교통사고")
        result = await lookup(inp, registry=full_registry, executor=full_executor)
        assert isinstance(result, LookupSearchResult)
        for c in result.candidates:
            assert isinstance(c, AdapterCandidate)
            assert c.score >= 0.0
            assert isinstance(c.required_params, list)

    @pytest.mark.asyncio
    async def test_station_emergency_query_surfaces_poi_locate_adapter(
        self, full_registry, full_executor
    ):
        """Station-nearby ER queries must keep a coordinate-producing locate adapter."""
        inp = LookupSearchInput(
            mode="search",
            query="아이가 열이 나는데 하단역 근처 야간 응급실이 어디야?",
            top_k=5,
        )
        result = await lookup(inp, registry=full_registry, executor=full_executor)
        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates]
        assert "nmc_emergency_search" in tool_ids
        assert "kakao_keyword_search" in tool_ids

    @pytest.mark.asyncio
    async def test_child_zone_accident_query_surfaces_koroad_adapter(
        self, full_registry, full_executor
    ):
        """Natural Korean spacing around accident risk must still retrieve KOROAD."""
        inp = LookupSearchInput(
            mode="search",
            query="강남역 주변 어린이보호구역 사고 위험 구간 알려줘",
            top_k=5,
        )
        result = await lookup(inp, registry=full_registry, executor=full_executor)
        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates]
        assert "koroad_accident_hazard_search" in tool_ids
        assert "koroad_accident_search" not in tool_ids

    @pytest.mark.asyncio
    async def test_empty_registry_returns_empty_result(self):
        """Empty registry returns LookupSearchResult with empty candidates."""
        empty_registry = ToolRegistry()
        inp = LookupSearchInput(mode="search", query="교통사고")
        result = await lookup(inp, registry=empty_registry)
        assert isinstance(result, LookupSearchResult)
        assert result.candidates == []
        assert result.reason == "empty_registry"

    @pytest.mark.asyncio
    async def test_top_k_clamp_respects_registry_size(self, full_registry, full_executor):
        """effective_top_k must not exceed registry size or 20."""
        # top_k is clamped at input model level to [1, 20]; use max allowed value
        inp = LookupSearchInput(mode="search", query="위험", top_k=20)
        result = await lookup(inp, registry=full_registry, executor=full_executor)
        assert isinstance(result, LookupSearchResult)
        assert result.effective_top_k <= 20
        assert result.effective_top_k <= result.total_registry_size

    @pytest.mark.asyncio
    async def test_domain_filter_narrows_results(self, full_registry, full_executor):
        """Domain filter must exclude tools not matching the given category."""
        inp = LookupSearchInput(
            mode="search",
            query="사고 위험",
            domain="교통안전",
            top_k=20,
        )
        result = await lookup(inp, registry=full_registry, executor=full_executor)
        assert isinstance(result, LookupSearchResult)
        # All returned candidates must have the domain in their tool categories
        for c in result.candidates:
            tool = full_registry.lookup(c.tool_id)
            assert any("교통안전" in cat for cat in tool.category), (
                f"Tool {c.tool_id!r} categories {tool.category!r} do not contain '교통안전'"
            )

    @pytest.mark.asyncio
    async def test_no_registry_returns_empty_result(self):
        """No registry provided returns empty LookupSearchResult (graceful)."""
        inp = LookupSearchInput(mode="search", query="교통사고")
        result = await lookup(inp, registry=None)
        assert isinstance(result, LookupSearchResult)
        assert result.candidates == []
