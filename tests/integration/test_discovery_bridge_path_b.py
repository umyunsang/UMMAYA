# SPDX-License-Identifier: Apache-2.0
"""Integration tests — Epic ζ #2297 path B (live smoke 2026-04-30 follow-up).

Verifies:
  B-1: verify/submit mock adapters appear in the main ToolRegistry's
       BM25 corpus (so find(mode="search") surfaces them alongside
       find-class adapters).
  B-2: AdapterCandidate exposes full per-domain REST schema metadata
       (input_schema_json with descriptions/types/patterns/constraints) so the
       LLM can fill params per domain without a second round-trip.
"""

from __future__ import annotations

import asyncio

import pytest

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.lookup import lookup
from ummaya.tools.models import LookupSearchInput
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry


@pytest.fixture(scope="module")
def loaded_registry() -> tuple[ToolRegistry, ToolExecutor]:
    r = ToolRegistry()
    e = ToolExecutor(registry=r)
    register_all_tools(r, e)
    return r, e


# ---------------------------------------------------------------------------
# B-1: BM25 corpus expansion — verify/submit mocks discoverable
# ---------------------------------------------------------------------------


def test_b1_total_tool_count_includes_mocks(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Path B-1: bridge registers active non-core mock adapters into main registry.

    Expected total: 153 after active KMA APIHub structured, URL adapter, and
    TAGO route-station expansion.
    """
    r, _ = loaded_registry
    total = len(r.all_tools())
    assert total == 153, (
        f"Expected 153 total tools after discovery_bridge runs; got {total}. "
        f"Verify the bridge registered the active mock adapters."
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
    """All 7 submit mock tool_ids are registered (3 ε + 2 Spec 031 + 2 OpenGiro)."""
    r, _ = loaded_registry
    ids = {t.id for t in r.all_tools()}
    expected = {
        "mock_submit_module_hometax_taxreturn",
        "mock_submit_module_gov24_minwon",
        "mock_submit_module_public_mydata_action",
        "mock_kftc_opengiro_bill_send_v1",
        "mock_kftc_opengiro_payment_send_v1",
        "mock_traffic_fine_pay_v1",
        "mock_welfare_application_submit_v1",
    }
    missing = expected - ids
    assert not missing, f"Missing submit adapters in main registry: {missing}"


# ---------------------------------------------------------------------------
# B-1 + B-2 end-to-end: find(mode="search") returns check/send candidates
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


def test_b1_welfare_application_search_surfaces_mydata_verify_before_sso(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Welfare benefit application discovery must surface MyData, not identity-only SSO.

    The system prompt maps 한부모가족/아동양육비 benefit application to
    mock_verify_mydata -> mock_welfare_application_submit_v1. Any-ID SSO is
    identity-only and cannot produce the DelegationToken required by submit.
    """
    r, e = loaded_registry

    async def _run() -> list:  # type: ignore[type-arg]
        inp = LookupSearchInput(
            mode="search",
            query="한부모가족 아동양육비 지원 신규 복지 급여 신청",
            top_k=8,
        )
        result = await lookup(inp, registry=r, executor=e, session_identity="test")
        return list(result.candidates)

    candidates = asyncio.run(_run())
    ids = [c.tool_id for c in candidates]
    top_five = ids[:5]

    assert "mock_verify_mydata" in top_five
    assert "mock_welfare_application_submit_v1" in top_five
    assert "mock_verify_module_any_id_sso" not in top_five


def test_b1_public_mydata_action_search_surfaces_mydata_verify(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """MyData consent actions must surface the MyData verify family."""
    r, e = loaded_registry

    async def _run() -> list:  # type: ignore[type-arg]
        inp = LookupSearchInput(
            mode="search",
            query="마이데이터 동의 상태 확인 공공 마이데이터 제공 동의 진행",
            top_k=5,
        )
        result = await lookup(inp, registry=r, executor=e, session_identity="test")
        return list(result.candidates)

    candidates = asyncio.run(_run())
    ids = [c.tool_id for c in candidates]

    assert "mock_verify_mydata" in ids
    assert "mock_submit_module_public_mydata_action" in ids


def test_b1_ganpyeon_login_search_surfaces_canonical_verify(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """간편인증 login wording must surface the canonical ganpyeon verify adapter."""
    r, e = loaded_registry

    async def _run() -> list:  # type: ignore[type-arg]
        inp = LookupSearchInput(
            mode="search",
            query="간편인증으로 로그인하고 내 행정서비스 이용 권한 확인해줘",
            top_k=5,
        )
        result = await lookup(inp, registry=r, executor=e, session_identity="test")
        return list(result.candidates)

    candidates = asyncio.run(_run())
    ids = [c.tool_id for c in candidates]

    assert "mock_verify_ganpyeon_injeung" in ids
    assert "mock_verify_module_modid" in ids
    assert ids.index("mock_verify_ganpyeon_injeung") < ids.index("mock_verify_module_modid")


def test_b1_mydata_verify_description_contains_canonical_action_scope(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Discovery prose must carry the exact MyData action scope before dispatch."""
    r, _ = loaded_registry
    tool = r.lookup("mock_verify_mydata")

    assert tool.llm_description is not None
    assert "check(tool_id='mock_verify_mydata'" in tool.llm_description
    assert "send:public_mydata.action" in tool.llm_description
    assert "send:mydata.welfare_application" in tool.llm_description
    assert "never include find:mohw.welfare_eligibility_search" in tool.llm_description
    assert "send:mock.welfare_application_submit_v1" in tool.llm_description
    assert "never invent find:mydata.public.consent" in tool.llm_description


def test_b1_identity_verify_descriptions_contain_canonical_scopes(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Discovery prose must keep identity-only verify scopes concrete."""
    r, _ = loaded_registry
    mobile = r.lookup("mock_verify_mobile_id")
    ganpyeon = r.lookup("mock_verify_ganpyeon_injeung")

    assert mobile.llm_description is not None
    assert "check:mobile_id.identity" in mobile.llm_description
    assert "find:identity.info" in mobile.llm_description
    assert "find:identity.verify" in mobile.llm_description
    assert ganpyeon.llm_description is not None
    assert "check:ganpyeon.identity" in ganpyeon.llm_description
    assert "admin_service scopes" in ganpyeon.llm_description


def test_b1_verify_descriptions_warn_against_family_ids_as_tool_ids(
    loaded_registry: tuple[ToolRegistry, ToolExecutor],
) -> None:
    """Family labels may appear in scopes, but LLM tool_id must stay canonical."""

    r, _ = loaded_registry
    simple_auth = r.lookup("mock_verify_module_simple_auth")
    mobile = r.lookup("mock_verify_mobile_id")

    assert simple_auth.llm_description is not None
    assert "Do not set tool_id to 'simple_auth_module'" in simple_auth.llm_description
    assert "mock_verify_module_simple_auth" in simple_auth.llm_description
    assert mobile.llm_description is not None
    assert "Do not set tool_id to 'mobile_id'" in mobile.llm_description
    assert "mock_verify_mobile_id" in mobile.llm_description


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

    # GOV24 submit path
    gov24_results = asyncio.run(_search("정부24 민원 신청"))
    assert "mock_submit_module_gov24_minwon" in gov24_results


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
    assert target.primitive == "check"
