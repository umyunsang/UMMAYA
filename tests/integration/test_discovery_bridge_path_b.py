# SPDX-License-Identifier: Apache-2.0
"""Integration tests — Epic ζ #2297 path B (live smoke 2026-04-30 follow-up).

Verifies:
  B-1: verify/submit/subscribe mock adapters appear in the main ToolRegistry's
       BM25 corpus (so lookup(mode="search") surfaces them alongside
       lookup-class adapters).
  B-2: AdapterCandidate exposes full per-domain REST schema metadata
       (input_schema_json with descriptions/types/patterns/constraints) so the
       LLM can fill params per domain without a second round-trip.
"""

from __future__ import annotations

import asyncio

import pytest

from kosmos.tools.executor import ToolExecutor
from kosmos.tools.lookup import lookup
from kosmos.tools.models import LookupSearchInput
from kosmos.tools.register_all import register_all_tools
from kosmos.tools.registry import ToolRegistry


@pytest.fixture(scope="module")
def loaded_registry() -> tuple[ToolRegistry, ToolExecutor]:
    r = ToolRegistry()
    e = ToolExecutor(registry=r)
    register_all_tools(r, e)
    return r, e


# ---------------------------------------------------------------------------
# B-1: BM25 corpus expansion — verify/submit/subscribe mocks discoverable
# ---------------------------------------------------------------------------


def test_b1_total_tool_count_includes_mocks(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Path B-1: bridge registers non-core mock adapters into main registry.

    Expected total: 21 (lookup-class + 5 primitives) + 10 verify + 6 submit + 3 subscribe = 40.
    """
    r, _ = loaded_registry
    total = len(r.all_tools())
    assert total == 40, (
        f"Expected 40 total tools after discovery_bridge runs; got {total}. "
        f"Verify the bridge registered all 19 mock adapters."
    )


def test_b1_verify_mocks_in_registry(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """All 10 canonical verify family tool_ids are registered."""
    r, _ = loaded_registry
    ids = {t.id for t in r.all_tools()}
    expected = {
        "mock_verify_module_modid",
        "mock_verify_module_kec",
        "mock_verify_module_geumyung",
        "mock_verify_module_simple_auth",
        "mock_verify_module_any_id_sso",
        "mock_verify_gongdong_injeungseo",
        "mock_verify_geumyung_injeungseo",
        "mock_verify_ganpyeon_injeung",
        "mock_verify_mobile_id",
        "mock_verify_mydata",
    }
    missing = expected - ids
    assert not missing, f"Missing verify adapters in main registry: {missing}"


def test_b1_submit_mocks_in_registry(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """All 6 submit mock tool_ids are registered (3 ε + 3 real-use/Spec 031)."""
    r, _ = loaded_registry
    ids = {t.id for t in r.all_tools()}
    expected = {
        "mock_submit_module_hometax_taxreturn",
        "mock_submit_module_gov24_minwon",
        "mock_submit_module_public_mydata_action",
        "mock_koroad_driver_fitness_reservation_v1",
        "mock_traffic_fine_pay_v1",
        "mock_welfare_application_submit_v1",
    }
    missing = expected - ids
    assert not missing, f"Missing submit adapters in main registry: {missing}"


def test_b1_subscribe_mocks_in_registry(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """All 3 subscribe mock tool_ids are registered (CBS + REST-pull + RSS)."""
    r, _ = loaded_registry
    ids = {t.id for t in r.all_tools()}
    expected = {
        "mock_cbs_disaster_v1",
        "mock_rest_pull_tick_v1",
        "mock_rss_public_notices_v1",
    }
    missing = expected - ids
    assert not missing, f"Missing subscribe adapters in main registry: {missing}"


# ---------------------------------------------------------------------------
# B-1 + B-2 end-to-end: lookup(mode="search") returns verify/submit candidates
# with full schema metadata for the citizen tax-return query.
# ---------------------------------------------------------------------------


def test_b1_b2_citizen_taxreturn_search_surfaces_chain_candidates(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """For "종합소득세 신고" the top BM25 hits include the chain's submit + lookup adapters.

    Asserts:
      - mock_submit_module_hometax_taxreturn is in the top 3 (chain's submit step)
      - mock_lookup_module_hometax_simplified is in the top 3 (chain's lookup step)
      - Each candidate exposes input_schema_json with non-empty properties (B-2)
    """
    r, e = loaded_registry

    async def _run() -> list:  # type: ignore[type-arg]
        inp = LookupSearchInput(mode="search", query="종합소득세 신고", top_k=5)
        result = await lookup(inp, registry=r, executor=e, session_identity="test")
        return list(result.candidates)

    candidates = asyncio.run(_run())
    top_ids = [c.tool_id for c in candidates[:3]]
    assert "mock_submit_module_hometax_taxreturn" in top_ids
    assert "mock_lookup_module_hometax_simplified" in top_ids

    # B-2: every candidate has full input_schema_json
    for c in candidates:
        assert isinstance(c.input_schema_json, dict)
        assert "properties" in c.input_schema_json or "type" in c.input_schema_json


def test_b2_hometax_taxreturn_schema_fields_have_descriptions(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """The submit adapter's input_schema_json carries per-field descriptions
    (so LLM can fill REST-shape params per domain)."""
    r, e = loaded_registry

    async def _run():  # noqa: ANN202
        inp = LookupSearchInput(mode="search", query="종합소득세 신고", top_k=5)
        return await lookup(inp, registry=r, executor=e, session_identity="test")

    result = asyncio.run(_run())
    target = next(
        (c for c in result.candidates if c.tool_id == "mock_submit_module_hometax_taxreturn"),
        None,
    )
    assert target is not None, "hometax_taxreturn submit not in search results"

    props = target.input_schema_json.get("properties", {})
    expected_fields = {"tax_year", "income_type", "total_income_krw", "session_id"}
    missing = expected_fields - set(props.keys())
    assert not missing, f"Missing expected hometax fields: {missing}"

    # Each field must have a description (B-2 invariant — LLM can read it)
    for fname in expected_fields:
        fdef = props[fname]
        assert isinstance(fdef, dict)
        assert fdef.get("description"), (
            f"Field {fname!r} has no description — LLM cannot judge what to fill."
        )


def test_b2_submit_candidate_declares_delegation_source_and_scope_instruction(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Submit candidates must tell the model which verify adapter + scope unlocks them."""
    r, _ = loaded_registry
    target = r.lookup("mock_submit_module_hometax_taxreturn")

    assert target.delegation_source_tool_id == "mock_verify_module_modid"
    assert target.llm_description is not None
    assert "mock_verify_module_modid" in target.llm_description
    assert "submit:hometax.tax-return" in target.llm_description


def test_b2_gov24_minwon_declares_ganpyeon_delegation_source(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Gov24 submit accepts 간편인증-family delegation, not simple_auth_module."""
    r, _ = loaded_registry
    target = r.lookup("mock_submit_module_gov24_minwon")

    assert target.delegation_source_tool_id == "mock_verify_ganpyeon_injeung"
    assert target.llm_description is not None
    assert "mock_verify_ganpyeon_injeung" in target.llm_description
    assert "submit:gov24.minwon" in target.llm_description


def test_b1_civil_movein_query_surfaces_gov24_sequence_candidates(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """CIV-001 wording must retrieve the move-in lookup before submit."""
    r, e = loaded_registry

    async def _run():  # noqa: ANN202
        inp = LookupSearchInput(
            mode="search",
            query="이사 전입신고 자동차 건강보험 학교 주소 변경",
            top_k=8,
        )
        return await lookup(inp, registry=r, executor=e, session_identity="test")

    result = asyncio.run(_run())
    top_ids = [c.tool_id for c in result.candidates[:5]]
    assert "mock_lookup_module_gov24_movein_sequence" in top_ids
    assert "mock_submit_module_gov24_minwon" in top_ids


def test_b1_vat_sales_query_surfaces_hometax_chain_candidates(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """TAX-002 wording (부가세/매출자료/납부) should not be hijacked by generic pay tools."""
    r, e = loaded_registry

    async def _run():  # noqa: ANN202
        inp = LookupSearchInput(
            mode="search",
            query="개인사업자 부가세 매출 자료 모아서 납부",
            top_k=5,
        )
        return await lookup(inp, registry=r, executor=e, session_identity="test")

    result = asyncio.run(_run())
    top_ids = [c.tool_id for c in result.candidates[:3]]
    assert "mock_submit_module_hometax_taxreturn" in top_ids
    assert "mock_lookup_module_hometax_simplified" in top_ids


def test_b1_cross_domain_search_returns_correct_candidates(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Different citizen queries surface domain-specific candidates."""
    r, e = loaded_registry

    async def _search(q: str) -> list:  # type: ignore[type-arg]
        inp = LookupSearchInput(mode="search", query=q, top_k=3)
        result = await lookup(inp, registry=r, executor=e, session_identity="test")
        return [c.tool_id for c in result.candidates]

    # KEC corporate certificate path
    kec_results = asyncio.run(_search("사업자 등록증 발급"))
    assert "mock_verify_module_kec" in kec_results

    # CBS disaster broadcast path
    cbs_results = asyncio.run(_search("재난방송 긴급재난문자"))
    assert "mock_cbs_disaster_v1" in cbs_results


# ---------------------------------------------------------------------------
# B-2: real_classification_url surfaced for verify mocks (agency policy citation)
# ---------------------------------------------------------------------------


def test_b2_verify_candidate_has_policy_url(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Verify mock candidates surface the agency-published policy URL."""
    r, e = loaded_registry

    async def _run():  # noqa: ANN202
        inp = LookupSearchInput(mode="search", query="모바일ID 인증", top_k=5)
        return await lookup(inp, registry=r, executor=e, session_identity="test")

    result = asyncio.run(_run())
    target = next(
        (c for c in result.candidates if c.tool_id == "mock_verify_module_modid"),
        None,
    )
    assert target is not None, "modid verify not in search results"
    assert target.real_classification_url is not None
    assert target.real_classification_url.startswith("http")
    assert target.primitive == "verify"
