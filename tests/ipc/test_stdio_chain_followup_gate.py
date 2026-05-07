# SPDX-License-Identifier: Apache-2.0
"""G-class chain enforcement — follow-up lookup gate tests.

Captures the donga-univ-poi-bug snap-001-01-kma-now (2026-05-04) regression:
K-EXAONE called ``resolve_location`` twice and then produced a fabricated
weather answer (16°C / 84% humidity vs raw KMA 20.7°C / 23%) without ever
invoking ``lookup(kma_current_observation)``. The fix adds
``_check_resolve_terminated_without_followup`` which runs at the
``if not tool_call_buf:`` boundary and rejects the final-answer turn when
the conversation invoked resolve_location but did not follow up with a
coord/admcd-input lookup despite the citizen query implying one.

Pure-function tests — no LLM harness required, no event loop, no monkeypatch.
The handler-level integration is exercised indirectly by the existing
test_chat_request_appends_available_tools_section + the manual snap-001
re-capture after this commit (see scripts/scn-final-integ).

Reference: AGENTS.md § seven-anti-patterns, pattern #1 (Final-state fallacy
— LLM was emitting a final answer that LOOKED correct but contained 100%
fabricated values; verifying ``lastFrame()`` never caught it).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from kosmos.ipc.stdio import (
    _build_verify_session_context,
    _check_chain_prerequisite,
    _check_duplicate_submit_prerequisite,
    _check_location_terminated_without_resolve,
    _check_resolve_terminated_without_followup,
    _check_sensitive_lookup_auth_prerequisite,
    _check_sensitive_lookup_terminated_without_lookup,
    _check_submit_terminated_without_submit,
    _check_verify_terminated_without_verify,
    _check_verify_tool_choice_prerequisite,
    _conversation_has_successful_lookup,
    _conversation_has_successful_primitive,
    _initial_verify_tool_choice_for_query,
    _location_independent_resolve_redirect_for_query,
    _normalize_lookup_args_for_query,
    _normalize_submit_args_for_query,
    _normalize_verify_args_for_query,
    _normalize_verify_tool_id_for_query,
    _query_implies_followup_lookup,
    _query_implies_location_resolution,
    _sensitive_lookup_verify_redirect_for_query,
    _submit_requirement_for_query,
)
from kosmos.llm.models import (
    ChatMessage as LLMChatMessage,
)
from kosmos.llm.models import (
    FunctionCall as LLMFunctionCall,
)
from kosmos.llm.models import (
    ToolCall as LLMToolCall,
)

# ---------------------------------------------------------------------------
# _query_implies_followup_lookup
# ---------------------------------------------------------------------------


def test_weather_query_implies_followup() -> None:
    """Korean weather keywords trigger the follow-up requirement."""
    assert _query_implies_followup_lookup("지금 부산 사하구 다대1동 날씨 어때")
    assert _query_implies_followup_lookup("내일 서울 기온 알려줘")
    assert _query_implies_followup_lookup("오늘 강수량 예보")


def test_hospital_query_implies_followup() -> None:
    """Hospital / ER / pharmacy keywords trigger the follow-up requirement."""
    assert _query_implies_followup_lookup("강남역 근처 응급실")
    assert _query_implies_followup_lookup("부산 내과 병원 찾아줘")
    assert _query_implies_followup_lookup("서울역 약국 위치")


def test_accident_query_implies_followup() -> None:
    """Traffic accident / hazard keywords trigger the follow-up requirement."""
    assert _query_implies_followup_lookup("강남역 사고다발지")
    assert _query_implies_followup_lookup("서울시 어린이보호구역 위험")


def test_english_query_keywords() -> None:
    """English fallback keywords also trigger the follow-up requirement."""
    assert _query_implies_followup_lookup("weather in Seoul today")
    assert _query_implies_followup_lookup("emergency hospital nearby")


def test_non_followup_query_does_not_trigger() -> None:
    """Pure address resolution / verify-class queries do NOT trigger."""
    assert not _query_implies_followup_lookup("부산 사하구 다대1동 주소가 어디?")
    assert not _query_implies_followup_lookup("종합소득세 신고해줘")
    assert not _query_implies_followup_lookup("정부24 등본 발급")
    assert not _query_implies_followup_lookup("")
    assert not _query_implies_followup_lookup("안녕하세요")


# ---------------------------------------------------------------------------
# _check_resolve_terminated_without_followup
# ---------------------------------------------------------------------------


def _msg_assistant_tool_call(name: str, args: dict[str, Any]) -> LLMChatMessage:
    return LLMChatMessage(
        role="assistant",
        content="",
        tool_calls=[
            LLMToolCall(
                id="call_test",
                type="function",
                function=LLMFunctionCall(name=name, arguments=json.dumps(args)),
            )
        ],
    )


def _msg_tool_result(name: str, payload: dict[str, Any]) -> LLMChatMessage:
    return LLMChatMessage(
        role="tool",
        content=json.dumps(payload),
        name=name,
        tool_call_id="call_test",
    )


def _auth_with_scope(scope: str) -> SimpleNamespace:
    return SimpleNamespace(delegation_context=SimpleNamespace(token=SimpleNamespace(scope=scope)))


def _hometax_lookup_args() -> dict[str, object]:
    return {
        "mode": "fetch",
        "tool_id": "mock_lookup_module_hometax_simplified",
        "params": {"year": 2025, "resident_id_prefix": "000000"},
    }


# ---------------------------------------------------------------------------
# Sensitive lookup auth gate
# ---------------------------------------------------------------------------


def test_sensitive_hometax_lookup_without_verify_is_rejected() -> None:
    """Citizen-specific Hometax records require verify delegation first."""
    msg = _check_sensitive_lookup_auth_prerequisite(
        "lookup",
        _hometax_lookup_args(),
        None,
    )

    assert msg is not None
    assert "mock_verify_module_modid" in msg
    assert "lookup:hometax.simplified" in msg
    assert "Do NOT answer" in msg


def test_sensitive_hometax_lookup_with_matching_scope_passes() -> None:
    """A cached delegation scope for lookup:hometax.simplified satisfies the gate."""
    msg = _check_sensitive_lookup_auth_prerequisite(
        "lookup",
        _hometax_lookup_args(),
        _auth_with_scope("lookup:hometax.simplified,submit:hometax.tax-return"),
    )

    assert msg is None


def test_sensitive_hometax_lookup_with_wrong_scope_is_rejected() -> None:
    """Wrong cached delegation scope must not unlock Hometax simplified data."""
    msg = _check_sensitive_lookup_auth_prerequisite(
        "lookup",
        _hometax_lookup_args(),
        _auth_with_scope("submit:hometax.tax-return"),
    )

    assert msg is not None
    assert "do not include 'lookup:hometax.simplified'" in msg


def test_sensitive_hometax_submit_query_redirects_lookup_to_verify() -> None:
    """Premature Hometax lookup in a submit flow is redirected before rendering."""
    redirect = _sensitive_lookup_verify_redirect_for_query(
        "lookup",
        _hometax_lookup_args(),
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
        None,
    )

    assert redirect is not None
    assert redirect["verify_tool_id"] == "mock_verify_module_modid"
    assert redirect["required_scopes"] == "lookup:hometax.simplified,submit:hometax.tax-return"


def test_sensitive_lookup_redirect_is_dormant_when_scope_is_cached() -> None:
    """Already verified sessions should dispatch the lookup normally."""
    assert (
        _sensitive_lookup_verify_redirect_for_query(
            "lookup",
            _hometax_lookup_args(),
            "홈택스 연말정산 간소화 자료 조회해줘",
            _auth_with_scope("lookup:hometax.simplified"),
        )
        is None
    )


def test_sensitive_lookup_redirect_ignores_unrelated_queries() -> None:
    """The redirect is scoped to citizen queries that imply the same verify contract."""
    assert (
        _sensitive_lookup_verify_redirect_for_query(
            "lookup",
            _hometax_lookup_args(),
            "부산 사하구 다대1동 날씨 알려줘",
            None,
        )
        is None
    )


def test_hometax_lookup_missing_tool_id_is_canonicalized_from_query() -> None:
    """Forced lookup turns still need the adapter id implied by the citizen query."""
    normalized = _normalize_lookup_args_for_query(
        "lookup",
        {"tool_id": "", "params": {}},
        "작년 연말정산 간소화 자료 중 의료비와 교육비 내역을 확인해줘",
    )

    assert normalized["tool_id"] == "mock_lookup_module_hometax_simplified"
    assert normalized["params"] == {"year": 2025, "resident_id_prefix": "000000"}


def test_hometax_lookup_generic_tool_id_is_canonicalized_from_query() -> None:
    """Some model turns echo the primitive name as tool_id; map it to the adapter."""
    normalized = _normalize_lookup_args_for_query(
        "lookup",
        {"tool_id": "lookup", "params": {"year": None}},
        "홈택스 연말정산 간소화 자료 조회해줘",
    )

    assert normalized["tool_id"] == "mock_lookup_module_hometax_simplified"
    assert normalized["params"] == {"year": 2025, "resident_id_prefix": "000000"}


def test_non_sensitive_lookup_does_not_trigger_auth_gate() -> None:
    """Public agency lookup adapters continue through the normal lookup path."""
    msg = _check_sensitive_lookup_auth_prerequisite(
        "lookup",
        {
            "mode": "fetch",
            "tool_id": "kma_current_observation",
            "params": {"lat": 35.18, "lon": 129.07},
        },
        None,
    )

    assert msg is None


def test_sensitive_hometax_after_verify_without_lookup_is_rejected() -> None:
    """Verify alone must not satisfy a citizen request for Hometax data."""
    msgs: list[Any] = [
        _msg_assistant_tool_call("lookup", _hometax_lookup_args()),
        _msg_tool_result(
            "lookup",
            {
                "kind": "lookup",
                "result": {"kind": "error", "reason": "auth_required"},
            },
        ),
    ]

    msg = _check_sensitive_lookup_terminated_without_lookup(
        msgs,
        "연말정산 간소화 자료 조회해서 의료비랑 교육비 항목만 요약해줘",
        _auth_with_scope("lookup:hometax.simplified"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_lookup_module_hometax_simplified"
    assert "Do NOT answer from the verify result alone" in msg["message"]


def test_sensitive_hometax_after_successful_lookup_passes() -> None:
    """A successful target lookup result clears the post-verify follow-up gate."""
    msgs: list[Any] = [
        _msg_assistant_tool_call("lookup", _hometax_lookup_args()),
        _msg_tool_result(
            "lookup",
            {
                "kind": "lookup",
                "result": {
                    "kind": "record",
                    "data": {"medical_expenses": 1_250_000, "education_expenses": 800_000},
                },
            },
        ),
    ]

    assert _conversation_has_successful_lookup(
        msgs,
        tool_id="mock_lookup_module_hometax_simplified",
    )
    assert (
        _check_sensitive_lookup_terminated_without_lookup(
            msgs,
            "연말정산 간소화 자료 조회해서 의료비랑 교육비 항목만 요약해줘",
            _auth_with_scope("lookup:hometax.simplified"),
        )
        is None
    )


def test_sensitive_hometax_without_auth_context_waits_for_verify_gate() -> None:
    """The post-verify lookup gate is dormant until delegation scope exists."""
    msg = _check_sensitive_lookup_terminated_without_lookup(
        [],
        "연말정산 간소화 자료 조회",
        None,
    )

    assert msg is None


def test_hometax_taxreturn_query_terminating_without_verify_is_rejected() -> None:
    """Tax-return filing prose must be forced through the multi-scope verify step."""
    msg = _check_verify_terminated_without_verify(
        [LLMChatMessage(role="user", content="종합소득세 신고서 제출")],
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_module_modid"
    assert msg["required_scopes"] == "lookup:hometax.simplified,submit:hometax.tax-return"
    assert "lookup:hometax.simplified" in msg["message"]
    assert "submit:hometax.tax-return" in msg["message"]


def test_hometax_taxreturn_rejects_lookup_only_verify_scope() -> None:
    """Tax-return filing verify must grant both lookup and submit scopes."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_module_modid",
            "params": {
                "scope_list": ["lookup:hometax.simplified"],
                "purpose_ko": "연말정산 간소화 자료 조회",
                "purpose_en": "Hometax simplified year-end tax lookup",
            },
        },
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_module_modid"
    assert "submit:hometax.tax-return" in msg["message"]


def test_hometax_taxreturn_allows_lookup_and_submit_verify_scopes() -> None:
    """Canonical tax-return verify scope_list passes the tool-choice gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_module_modid",
            "params": {
                "scope_list": ["lookup:hometax.simplified", "submit:hometax.tax-return"],
                "purpose_ko": "종합소득세 신고",
                "purpose_en": "Comprehensive income tax filing",
            },
        },
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert msg is None


def test_hometax_taxreturn_canonicalizes_lookup_adapter_scope_alias() -> None:
    """Adapter-id lookup scope aliases must map to the canonical Hometax scope."""
    verify_args = {
        "tool_id": "mock_verify_module_modid",
        "params": {
            "scope_list": [
                "lookup:mock.lookup_module_hometax_simplified",
                "submit:hometax.tax-return",
            ],
            "purpose_ko": "종합소득세 신고",
            "purpose_en": "Comprehensive income tax filing",
        },
    }

    normalized = _normalize_verify_args_for_query(
        "verify",
        verify_args,
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    params = normalized["params"]
    assert isinstance(params, dict)
    assert params["scope_list"] == [
        "lookup:hometax.simplified",
        "submit:hometax.tax-return",
    ]
    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            normalized,
            "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
        )
        is None
    )


def test_hometax_simplified_verify_drops_taxreturn_submit_scope() -> None:
    """Lookup-only Hometax consent must not mint submit delegation."""
    verify_args = {
        "tool_id": "mock_verify_module_modid",
        "params": {
            "scope_list": ["lookup:hometax.simplified", "submit:hometax.tax-return"],
            "purpose_ko": "연말정산 간소화 자료 조회",
            "purpose_en": "Hometax simplified year-end tax lookup",
        },
    }

    normalized = _normalize_verify_args_for_query(
        "verify",
        verify_args,
        "홈택스 연말정산 간소화에서 작년 의료비랑 교육비 공제 자료 조회해줘",
    )

    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            normalized,
            "홈택스 연말정산 간소화에서 작년 의료비랑 교육비 공제 자료 조회해줘",
        )
        is None
    )
    session_context = _build_verify_session_context(
        normalized,
        session_id="HOMETAX-SIMPLIFIED-SESSION-001",
    )
    assert session_context["scope_list"] == ["lookup:hometax.simplified"]


def test_hometax_taxreturn_submit_requirement_uses_fixture_defaults() -> None:
    """The submit gate can recover the mock tax-return payload without asking PII."""
    requirement = _submit_requirement_for_query(
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘"
    )

    assert requirement is not None
    assert requirement["tool_id"] == "mock_submit_module_hometax_taxreturn"
    assert requirement["scope"] == "submit:hometax.tax-return"
    params = json.loads(requirement["params_json"])
    assert params == {
        "tax_year": 2025,
        "income_type": "종합소득",
        "total_income_krw": 42_000_000,
        "session_id": "HOMETAX-TAXRETURN-SESSION-001",
    }


def test_hometax_taxreturn_suppresses_irrelevant_resolve_location() -> None:
    """Location-independent tax filing must not dispatch resolve_location."""
    redirect = _location_independent_resolve_redirect_for_query(
        "resolve_location",
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert redirect == {"primitive": "verify", "tool_id": "mock_verify_module_modid"}


def test_location_query_does_not_suppress_resolve_location() -> None:
    """Real place/address workflows keep the resolver path."""
    assert (
        _location_independent_resolve_redirect_for_query(
            "resolve_location",
            "하단역 근처 야간 응급실 찾아줘",
        )
        is None
    )


def test_gov24_lookup_suppresses_irrelevant_resolve_without_forcing_verify() -> None:
    """Read-only non-location workflows retry freely instead of resolving Seoul."""
    redirect = _location_independent_resolve_redirect_for_query(
        "resolve_location",
        "정부24에서 내가 발급 가능한 증명서 목록 조회해줘",
    )

    assert redirect == {"primitive": "free", "tool_id": ""}


def test_hometax_lookup_args_are_filled_from_citizen_query() -> None:
    """Hometax simplified lookup gets deterministic fixture fields."""
    normalized = _normalize_lookup_args_for_query(
        "lookup",
        {"tool_id": "mock_lookup_module_hometax_simplified"},
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert normalized["params"] == {"year": 2025, "resident_id_prefix": "000000"}


def test_hometax_lookup_relative_last_year_overrides_model_default() -> None:
    """The 2026-05-07 target-state fixture maps '작년' to 2025, not 2024."""
    normalized = _normalize_lookup_args_for_query(
        "lookup",
        {
            "tool_id": "mock_lookup_module_hometax_simplified",
            "params": {"year": 2024},
        },
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert normalized["params"]["year"] == 2025


def test_hometax_lookup_strips_model_noise_from_delegation_context() -> None:
    """Lookup-only fixture fields must not leak inside delegation_context."""
    normalized = _normalize_lookup_args_for_query(
        "lookup",
        {
            "tool_id": "mock_lookup_module_hometax_simplified",
            "params": {
                "delegation_context": {
                    "token": {"scope": "lookup:hometax.simplified"},
                    "year": 2024,
                    "resident_id_prefix": "991231",
                },
                "year": 2024,
            },
        },
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    params = normalized["params"]
    assert isinstance(params, dict)
    assert params["year"] == 2025
    delegation_context = params["delegation_context"]
    assert isinstance(delegation_context, dict)
    assert delegation_context == {"token": {"scope": "lookup:hometax.simplified"}}


def test_hometax_taxreturn_submit_args_override_model_classification() -> None:
    """The Hometax tax-return mock uses the fixture's comprehensive-tax payload."""
    normalized = _normalize_submit_args_for_query(
        "submit",
        {
            "tool_id": "mock_submit_module_hometax_taxreturn",
            "params": {
                "tax_year": 2024,
                "income_type": "근로소득",
                "total_income_krw": 1,
                "session_id": "MODEL-GUESSED-SESSION-001",
                "delegation_context": {"token": {"scope": "submit:hometax.tax-return"}},
            },
        },
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    params = normalized["params"]
    assert isinstance(params, dict)
    assert params["tax_year"] == 2025
    assert params["income_type"] == "종합소득"
    assert params["total_income_krw"] == 42_000_000
    assert params["session_id"] == "HOMETAX-TAXRETURN-SESSION-001"
    assert "delegation_context" in params


def test_hometax_taxreturn_after_verify_waits_for_lookup_before_submit() -> None:
    """The tax-return submit gate lets the sensitive lookup gate run first."""
    msg = _check_submit_terminated_without_submit(
        [
            _msg_assistant_tool_call(
                "verify",
                {
                    "tool_id": "mock_verify_module_modid",
                    "params": {
                        "scope_list": [
                            "lookup:hometax.simplified",
                            "submit:hometax.tax-return",
                        ]
                    },
                },
            ),
            _msg_tool_result("verify", {"status": "verified"}),
        ],
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
        _auth_with_scope("lookup:hometax.simplified,submit:hometax.tax-return"),
    )

    assert msg is None


def test_hometax_taxreturn_after_lookup_without_submit_is_rejected() -> None:
    """After verify and lookup succeed, tax-return filing must continue into submit."""
    msg = _check_submit_terminated_without_submit(
        [
            _msg_assistant_tool_call(
                "verify",
                {
                    "tool_id": "mock_verify_module_modid",
                    "params": {
                        "scope_list": [
                            "lookup:hometax.simplified",
                            "submit:hometax.tax-return",
                        ]
                    },
                },
            ),
            _msg_tool_result("verify", {"status": "verified"}),
            _msg_assistant_tool_call("lookup", _hometax_lookup_args()),
            _msg_tool_result(
                "lookup",
                {
                    "kind": "lookup",
                    "result": {
                        "kind": "record",
                        "data": {"medical_expenses": 1_250_000},
                    },
                },
            ),
        ],
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
        _auth_with_scope("lookup:hometax.simplified,submit:hometax.tax-return"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_submit_module_hometax_taxreturn"
    assert "HOMETAX-TAXRETURN-SESSION-001" in msg["message"]


def test_welfare_application_after_verify_without_submit_is_rejected() -> None:
    """A verified welfare application request must continue into submit."""
    msg = _check_submit_terminated_without_submit(
        [
            _msg_assistant_tool_call(
                "verify",
                {
                    "tool_id": "mock_verify_mydata",
                    "params": {"scope_list": ["submit:mydata.welfare_application"]},
                },
            ),
            _msg_tool_result("verify", {"status": "verified"}),
        ],
        (
            "한부모가족 아동양육비 지원을 신규 신청해줘. "
            "신청자 DI는 DI-TEST-HANPARENT-001이고 가구원 수는 2명이야."
        ),
        _auth_with_scope("submit:mydata.welfare_application"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_welfare_application_submit_v1"
    assert "DI-TEST-HANPARENT-001" in msg["message"]
    assert '"household_size": 2' in msg["message"]


def test_welfare_lookup_args_are_filled_from_citizen_query() -> None:
    """Single-parent child-support lookup gets deterministic SSIS filters."""
    normalized = _normalize_lookup_args_for_query(
        "lookup",
        {"tool_id": "mohw_welfare_eligibility_search"},
        "한부모가족 아동양육비 지원을 신규 신청해줘.",
    )

    assert normalized["params"] == {
        "search_wrd": "한부모가족 아동양육비",
        "trgter_indvdl_array": "060",
        "onap_psblt_yn": "Y",
    }


def test_welfare_lookup_arg_normalization_removes_life_stage_collision() -> None:
    """The lookup normalizer preserves model details but removes the SSIS NO DATA filter."""
    normalized = _normalize_lookup_args_for_query(
        "lookup",
        {
            "tool_id": "mohw_welfare_eligibility_search",
            "params": {"life_array": "002", "num_of_rows": 3},
        },
        "한부모 아동양육비 신청 가능 여부 확인",
    )

    assert normalized["params"]["num_of_rows"] == 3
    assert "life_array" not in normalized["params"]
    assert normalized["params"]["trgter_indvdl_array"] == "060"


def test_traffic_fine_payment_after_verify_without_submit_is_rejected() -> None:
    """Traffic fine payment requests use the mock fixture when no notice number exists."""
    msg = _check_submit_terminated_without_submit(
        [
            _msg_assistant_tool_call(
                "verify",
                {
                    "tool_id": "mock_verify_ganpyeon_injeung",
                    "params": {"scope_list": ["submit:traffic.fine-pay"]},
                },
            ),
            _msg_tool_result("verify", {"status": "verified"}),
        ],
        "교통 과태료가 있는지 확인하고 납부까지 진행해줘",
        _auth_with_scope("submit:traffic.fine-pay"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_traffic_fine_pay_v1"
    assert "MOCK-FINE-2026-001" in msg["message"]
    assert "virtual_account" in msg["message"]


def test_traffic_fine_verify_normalizes_lookup_and_payment_scope_aliases() -> None:
    """Traffic fine lookup wording should not block the payment submit scope."""
    verify_args = {
        "tool_id": "mock_verify_ganpyeon_injeung",
        "params": {
            "scope_list": [
                "lookup:traffic_fine.check",
                "lookup:traffic.fine",
                "lookup:traffic.fine.inquiry",
                "lookup:traffic.fine.search",
                "submit:traffic_fine.payment",
                "submit:traffic.fine.pay",
            ],
            "purpose_ko": "교통 과태료 확인 및 납부",
            "purpose_en": "Traffic fine check and payment",
        },
    }

    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            verify_args,
            "교통 과태료가 있는지 확인하고 납부까지 진행해줘",
        )
        is None
    )
    session_context = _build_verify_session_context(
        verify_args,
        session_id="TRAFFIC-FINE-SESSION-001",
    )
    assert session_context["scope_list"] == ["submit:traffic.fine-pay"]


def test_mydata_action_after_verify_without_submit_is_rejected() -> None:
    """Public MyData consent requests must continue from verify into submit."""
    msg = _check_submit_terminated_without_submit(
        [
            _msg_assistant_tool_call(
                "verify",
                {
                    "tool_id": "mock_verify_mydata",
                    "params": {"scope_list": ["submit:public_mydata.action"]},
                },
            ),
            _msg_tool_result("verify", {"status": "verified"}),
        ],
        "마이데이터 동의 상태 확인하고 필요한 공공 마이데이터 제공 동의까지 진행해줘",
        _auth_with_scope("submit:public_mydata.action"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_submit_module_public_mydata_action"
    assert "PUBLIC-MYDATA-MOCK" in msg["message"]
    assert "MYDATA-ACTION-SESSION-001" in msg["message"]


def test_submit_followup_gate_passes_after_successful_submit() -> None:
    """A prior successful submit clears the follow-up gate and blocks duplicates."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "주민등록등본"},
            },
        ),
        _msg_tool_result(
            "submit",
            {
                "kind": "submit",
                "result": {
                    "transaction_id": "urn:kosmos:submit:test",
                    "status": "succeeded",
                    "adapter_receipt": {"receipt_id": "gov24-2026-05-07-MW-TEST"},
                },
            },
        ),
    ]

    assert _conversation_has_successful_primitive(
        msgs,
        primitive="submit",
        tool_id="mock_submit_module_gov24_minwon",
    )
    assert (
        _check_submit_terminated_without_submit(
            msgs,
            "정부24에서 주민등록등본 발급 민원 신청해줘",
            _auth_with_scope("submit:gov24.minwon"),
        )
        is None
    )


def test_duplicate_submit_after_success_is_rejected() -> None:
    """A second submit call must finalize from the prior receipt."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "주민등록등본"},
            },
        ),
        _msg_tool_result(
            "submit",
            {
                "kind": "submit",
                "result": {
                    "transaction_id": "urn:kosmos:submit:test",
                    "status": "succeeded",
                    "adapter_receipt": {"receipt_id": "gov24-2026-05-07-MW-TEST"},
                },
            },
        ),
    ]

    msg = _check_duplicate_submit_prerequisite(
        "submit",
        {"tool_id": "mock_submit_module_gov24_minwon", "params": {}},
        msgs,
    )

    assert msg is not None
    assert "do NOT call submit again" in msg
    assert "prior successful submit tool_result" in msg


def test_gov24_submit_args_are_filled_from_citizen_query() -> None:
    """Known mock submit payload fields from the user request are restored before dispatch."""
    args = _normalize_submit_args_for_query(
        "submit",
        {
            "tool_id": "mock_submit_module_gov24_minwon",
            "params": {"delegation_context": {"token": {"scope": "submit:gov24.minwon"}}},
        },
        (
            "정부24에서 주민등록등본 발급 민원 신청해줘. 신청자 이름은 홍길동, "
            "수령 방법은 온라인 발급, 세션 ID는 GOV24-MINWON-SESSION-001이야."
        ),
    )

    params = args["params"]
    assert isinstance(params, dict)
    assert params["minwon_type"] == "주민등록등본"
    assert params["applicant_name"] == "홍길동"
    assert params["delivery_method"] == "online"
    assert params["session_id"] == "GOV24-MINWON-SESSION-001"
    assert "delegation_context" in params


def test_gov24_generic_submit_tool_id_is_canonicalized() -> None:
    """The model must not burn a permission decision on primitive-name-as-tool-id."""
    args = _normalize_submit_args_for_query(
        "submit",
        {
            "tool_id": "submit",
            "params": {"delegation_context": {"token": {"scope": "submit:gov24.minwon"}}},
        },
        (
            "정부24에서 주민등록등본 발급 민원 신청해줘. 신청자 이름은 홍길동, "
            "수령 방법은 온라인 발급, 세션 ID는 GOV24-MINWON-SESSION-001이야."
        ),
    )

    assert args["tool_id"] == "mock_submit_module_gov24_minwon"
    params = args["params"]
    assert isinstance(params, dict)
    assert params["minwon_type"] == "주민등록등본"
    assert params["session_id"] == "GOV24-MINWON-SESSION-001"


def test_gov24_minwon_drops_certificate_lookup_scope_alias() -> None:
    """Gov24 민원 submit does not delegate the public certificate lookup scope."""
    verify_args = {
        "tool_id": "mock_verify_module_simple_auth",
        "params": {
            "scope_list": [
                "lookup:gov24.certificate",
                "lookup:gov24.simplified",
                "submit:gov24.minwon",
            ],
            "purpose_ko": "주민등록등본 발급 민원 신청",
            "purpose_en": "Gov24 resident registration certificate civil petition",
        },
    }

    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            verify_args,
            "정부24에서 주민등록등본 발급 민원 신청해줘",
        )
        is None
    )
    session_context = _build_verify_session_context(
        verify_args,
        session_id="GOV24-MINWON-SESSION-001",
    )
    assert session_context["scope_list"] == ["submit:gov24.minwon"]


def test_gov24_minwon_drops_query_bound_lookup_scope_prefix() -> None:
    """Gov24 minwon submit should not delegate model-invented Gov24 lookup scopes."""
    verify_args = {
        "tool_id": "mock_verify_module_simple_auth",
        "params": {
            "scope_list": [
                "lookup:gov24.resident_certificate",
                "submit:gov24.minwon",
            ],
            "purpose_ko": "주민등록등본 발급 민원 신청",
            "purpose_en": "Gov24 resident registration certificate civil petition",
        },
    }
    normalized = _normalize_verify_args_for_query(
        "verify",
        verify_args,
        "정부24에서 주민등록등본 발급 민원 신청해줘",
    )

    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            normalized,
            "정부24에서 주민등록등본 발급 민원 신청해줘",
        )
        is None
    )
    session_context = _build_verify_session_context(
        normalized,
        session_id="GOV24-MINWON-SESSION-001",
    )
    assert session_context["scope_list"] == ["submit:gov24.minwon"]


def test_submit_arg_normalization_preserves_model_payload_values() -> None:
    """Do not overwrite explicit non-empty submit params."""
    args = _normalize_submit_args_for_query(
        "submit",
        {
            "tool_id": "mock_submit_module_gov24_minwon",
            "params": {
                "minwon_type": "가족관계증명서",
                "applicant_name": "김철수",
                "delivery_method": "postal",
                "session_id": "GOV24-CUSTOM-SESSION-002",
            },
        },
        "정부24에서 주민등록등본 발급 민원 신청해줘. 신청자 이름은 홍길동이야.",
    )

    params = args["params"]
    assert isinstance(params, dict)
    assert params["minwon_type"] == "가족관계증명서"
    assert params["applicant_name"] == "김철수"
    assert params["delivery_method"] == "postal"
    assert params["session_id"] == "GOV24-CUSTOM-SESSION-002"


def test_ganpyeon_query_terminating_without_verify_is_rejected() -> None:
    """Auth wording that ends as prose must be forced back through verify."""
    msg = _check_verify_terminated_without_verify(
        [LLMChatMessage(role="user", content="간편인증 로그인")],
        "간편인증으로 로그인하고 내 행정서비스 이용 권한 확인해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_ganpyeon_injeung"
    assert msg["scope"] == "verify:ganpyeon.identity"
    assert "Do NOT ask" in msg["message"]


def test_verify_query_after_prior_verify_passes() -> None:
    """Once verify ran, the terminal verify gate stays out of the way."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "verify",
            {
                "tool_id": "mock_verify_ganpyeon_injeung",
                "params": {"scope_list": ["verify:ganpyeon.identity"]},
            },
        ),
        _msg_tool_result("verify", {"status": "verified"}),
    ]

    assert (
        _check_verify_terminated_without_verify(
            msgs,
            "간편인증으로 로그인하고 내 행정서비스 이용 권한 확인해줘",
        )
        is None
    )


def test_ganpyeon_query_rejects_mobile_id_verify_substitution() -> None:
    """간편인증 wording must not be silently routed to Mobile-ID verify."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_module_modid",
            "params": {
                "scope_list": [
                    "lookup:admin_service_registry",
                    "lookup:user_permission_query",
                ],
                "purpose_ko": "행정서비스 이용 권한 확인",
                "purpose_en": "Check administrative service usage rights",
            },
        },
        "간편인증으로 로그인하고 내 행정서비스 이용 권한 확인해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_ganpyeon_injeung"
    assert "mock_verify_module_modid" in msg["message"]
    assert "verify:ganpyeon.identity" in msg["message"]


def test_ganpyeon_query_rejects_any_id_sso_scope_substitution() -> None:
    """간편인증 must not drift into generic SSO/admin-service scopes."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_module_any_id_sso",
            "params": {
                "scope_list": [
                    "lookup:admin_service.permission_check",
                    "submit:admin_service.permission_management",
                ],
                "purpose_ko": "간편인증 로그인",
                "purpose_en": "Simple authentication login",
            },
        },
        "간편인증으로 로그인하고 내 행정서비스 이용 권한 확인해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_ganpyeon_injeung"
    assert "mock_verify_module_any_id_sso" in msg["message"]
    assert "verify:ganpyeon.identity" in msg["message"]


def test_ganpyeon_query_allows_canonical_ganpyeon_verify() -> None:
    """Canonical 간편인증 verify tool and scope pass the tool-choice gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_ganpyeon_injeung",
            "params": {
                "scope_list": ["verify:ganpyeon.identity"],
                "purpose_ko": "간편인증 로그인",
                "purpose_en": "Simple authentication login",
            },
        },
        "간편인증으로 로그인하고 내 행정서비스 이용 권한 확인해줘",
    )

    assert msg is None


def test_mobile_id_query_rejects_identity_lookup_alias_scopes() -> None:
    """Mobile ID verify must use the canonical identity scope, not lookup aliases."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_mobile_id",
            "params": {
                "scope_list": ["lookup:identity.info", "lookup:identity.verify"],
                "purpose_ko": "모바일 신분증 본인확인",
                "purpose_en": "Mobile ID identity verification",
            },
        },
        "모바일 신분증으로 본인확인해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_mobile_id"
    assert msg["scope"] == "verify:mobile_id.identity"
    assert "lookup:identity.info" in msg["message"]


def test_mobile_id_query_allows_canonical_identity_scope() -> None:
    """Canonical Mobile ID verify scope passes the tool-choice gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_mobile_id",
            "params": {
                "scope_list": ["verify:mobile_id.identity"],
                "purpose_ko": "모바일 신분증 본인확인",
                "purpose_en": "Mobile ID identity verification",
            },
        },
        "모바일 신분증으로 본인확인해줘",
    )

    assert msg is None


def test_mobile_id_query_normalizes_generic_verify_tool_id() -> None:
    """Generic verify tool_id becomes the canonical Mobile ID adapter on scope match."""
    normalized = _normalize_verify_tool_id_for_query(
        "verify",
        {
            "tool_id": "verify",
            "params": {
                "scope_list": ["verify:mobile_id.identity"],
                "purpose_ko": "모바일 신분증 본인확인",
                "purpose_en": "Mobile ID identity verification",
            },
        },
        "모바일 신분증으로 본인확인해줘",
    )

    assert normalized["tool_id"] == "mock_verify_mobile_id"
    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            normalized,
            "모바일 신분증으로 본인확인해줘",
        )
        is None
    )


def test_mobile_id_query_forces_initial_verify_tool_choice() -> None:
    """Identity-only Mobile ID requests enter the loop with verify constrained."""
    assert (
        _initial_verify_tool_choice_for_query([], "모바일 신분증으로 본인확인해줘")
        == "mock_verify_mobile_id"
    )


def test_mobile_id_query_does_not_force_verify_after_success() -> None:
    """Once Mobile ID verify succeeded, the initial force gate stays inactive."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "verify",
            {
                "tool_id": "mock_verify_mobile_id",
                "params": {"scope_list": ["verify:mobile_id.identity"]},
            },
        ),
        _msg_tool_result("verify", {"status": "verified"}),
    ]

    assert (
        _initial_verify_tool_choice_for_query(
            msgs,
            "모바일 신분증으로 본인확인해줘",
        )
        is None
    )


def test_mobile_id_verify_missing_scope_is_filled_from_query() -> None:
    """Forced verify can recover missing identity scope fields before dispatch."""
    normalized = _normalize_verify_args_for_query(
        "verify",
        {"tool_id": "mock_verify_mobile_id", "params": {}},
        "모바일 신분증으로 본인확인해줘",
    )

    assert normalized == {
        "tool_id": "mock_verify_mobile_id",
        "params": {
            "scope_list": ["verify:mobile_id.identity"],
            "purpose_ko": "모바일 신분증 본인확인",
            "purpose_en": "Mobile ID identity verification",
        },
    }
    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            normalized,
            "모바일 신분증으로 본인확인해줘",
        )
        is None
    )


def test_submit_scope_query_does_not_force_initial_verify_tool_choice() -> None:
    """Submit workflows keep their existing chain-specific first-step routing."""
    assert (
        _initial_verify_tool_choice_for_query(
            [],
            "정부24에서 주민등록등본 발급 신청해줘",
        )
        is None
    )


def test_mobile_id_query_keeps_generic_verify_tool_id_on_wrong_scope() -> None:
    """Generic verify is not canonicalized when the emitted scope is wrong."""
    original: dict[str, object] = {
        "tool_id": "verify",
        "params": {
            "scope_list": ["lookup:identity.info"],
            "purpose_ko": "모바일 신분증 본인확인",
            "purpose_en": "Mobile ID identity verification",
        },
    }
    normalized = _normalize_verify_tool_id_for_query(
        "verify",
        original,
        "모바일 신분증으로 본인확인해줘",
    )

    assert normalized == original
    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            normalized,
            "모바일 신분증으로 본인확인해줘",
        )
        is not None
    )


def test_mydata_action_query_requires_submit_scope_for_verify() -> None:
    """Public MyData action wording must bind verify to the downstream submit scope."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": [
                    "lookup:mydata.consent_status",
                    "submit:mydata.provide_consent",
                ],
                "purpose_ko": "마이데이터 동의 상태 확인",
                "purpose_en": "Check MyData consent status",
            },
        },
        "마이데이터 동의 상태 확인하고 필요한 공공 마이데이터 제공 동의까지 진행해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_mydata"
    assert msg["scope"] == "submit:public_mydata.action"
    assert "submit:public_mydata.action" in msg["message"]
    assert "lookup:mydata.consent_status" in msg["message"]


def test_mydata_action_rejects_lookup_to_verify_adapter() -> None:
    """Verify adapters surfaced by discovery must not be called through lookup."""
    msg = _check_verify_tool_choice_prerequisite(
        "lookup",
        {
            "tool_id": "mock_verify_mydata",
            "params": {},
        },
        "마이데이터 동의 상태 확인하고 필요한 공공 마이데이터 제공 동의까지 진행해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_mydata"
    assert msg["scope"] == "submit:public_mydata.action"
    assert "Verify primitive prerequisite mismatch" in msg["message"]
    assert "verify(tool_id='mock_verify_mydata'" in msg["message"]
    assert "lookup" in msg["message"]


def test_welfare_application_lookup_first_is_not_verify_primitive_mismatch() -> None:
    """Eligibility lookup remains legal before the welfare submit verify step."""
    msg = _check_verify_tool_choice_prerequisite(
        "lookup",
        {
            "tool_id": "mohw_welfare_eligibility_search",
            "params": {"search_wrd": "한부모가족 아동양육비"},
        },
        "한부모가족 아동양육비 지원을 신규 신청해줘. 신청 가능한지 먼저 확인해줘.",
    )

    assert msg is None


def test_welfare_application_normalizes_lookup_and_mock_submit_scope_aliases() -> None:
    """Known welfare verify scope aliases collapse to the canonical MyData scope."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": [
                    "lookup:mohw.welfare_eligibility_search",
                    "lookup:pub.mohw.welfare_eligibility",
                    "lookup:mydata.welfare_eligibility_search",
                    "lookup:public_mydata.welfare_eligibility_search",
                    "lookup:mydata.welfare",
                    "submit:mock.welfare_application_submit_v1",
                    "submit:pub.mohw.welfare_application",
                ],
                "purpose_ko": "한부모가족 아동양육비 지원 신청",
                "purpose_en": "Single-parent family child support application",
            },
        },
        "한부모가족 아동양육비 지원을 신규 신청해줘. 신청 가능한지 먼저 확인해줘.",
    )

    assert msg is None


def test_welfare_application_session_context_drops_public_lookup_scope_alias() -> None:
    """Verify dispatch should not mint delegation tokens for public lookup scopes."""
    session_context = _build_verify_session_context(
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": [
                    "lookup:mohw.welfare_eligibility_search",
                    "lookup:pub.mohw.welfare_eligibility",
                    "lookup:mydata.welfare_eligibility_search",
                    "lookup:public_mydata.welfare_eligibility_search",
                    "lookup:mydata.welfare",
                    "submit:mock.welfare_application_submit_v1",
                    "submit:pub.mohw.welfare_application",
                    "submit:mock_welfare_application_submit_v1",
                ],
                "purpose_ko": "한부모가족 아동양육비 지원 신청",
            },
        },
        session_id="test-session",
    )

    assert session_context["scope_list"] == ["submit:mydata.welfare_application"]
    assert session_context["session_id"] == "test-session"


def test_welfare_application_allows_canonical_submit_scope() -> None:
    """The canonical welfare application verify scope passes the gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": ["submit:mydata.welfare_application"],
                "purpose_ko": "한부모가족 아동양육비 지원 신청",
                "purpose_en": "Single-parent family child support application",
            },
        },
        "한부모가족 아동양육비 지원을 신규 신청해줘. 신청 가능한지 먼저 확인해줘.",
    )

    assert msg is None


def test_welfare_application_drops_hometax_scope_before_verify_gate() -> None:
    """Welfare submit verify should drop stale Hometax lookup scope drift."""
    verify_args = {
        "tool_id": "mock_verify_mydata",
        "params": {
            "scope_list": [
                "lookup:hometax.simplified",
                "submit:mydata.welfare_application",
            ],
            "purpose_ko": "한부모가족 아동양육비 지원 신청",
            "purpose_en": "Single-parent family child support application",
        },
    }
    normalized = _normalize_verify_args_for_query(
        "verify",
        verify_args,
        "한부모가족 아동양육비 지원을 신규 신청해줘. 신청 가능한지 먼저 확인해줘.",
    )

    assert normalized["params"]["scope_list"] == ["submit:mydata.welfare_application"]
    assert (
        _check_verify_tool_choice_prerequisite(
            "verify",
            normalized,
            "한부모가족 아동양육비 지원을 신규 신청해줘. 신청 가능한지 먼저 확인해줘.",
        )
        is None
    )


def test_mydata_action_query_allows_submit_scope_verify() -> None:
    """The worked-example Public MyData verify scope passes the gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "verify",
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": ["submit:public_mydata.action"],
                "purpose_ko": "공공 마이데이터 제공 동의",
                "purpose_en": "Public MyData consent action",
            },
        },
        "마이데이터 동의 상태 확인하고 필요한 공공 마이데이터 제공 동의까지 진행해줘",
    )

    assert msg is None


def test_unknown_location_query_implies_resolution() -> None:
    """Fake-looking addresses are still resolver inputs, not prose-only failures."""
    assert _query_implies_location_resolution("존재하지않는주소 근처 응급실 찾아줘")

    msg = _check_location_terminated_without_resolve(
        [LLMChatMessage(role="user", content="존재하지않는주소 근처 응급실 찾아줘")],
        "존재하지않는주소 근처 응급실 찾아줘",
    )

    assert msg is not None
    assert "resolve_location" in msg
    assert "do NOT invent coordinates" in msg


def test_location_query_after_prior_resolve_passes() -> None:
    """A prior resolver call satisfies the terminal location gate."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "resolve_location",
            {"query": "존재하지않는주소", "want": "coords_and_admcd"},
        ),
        _msg_tool_result("resolve_location", {"kind": "error", "reason": "not_found"}),
    ]

    assert (
        _check_location_terminated_without_resolve(
            msgs,
            "존재하지않는주소 근처 응급실 찾아줘",
        )
        is None
    )


def test_chain_complete_passes_through() -> None:
    """resolve → lookup chain that completed both steps is allowed."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 날씨"),
        _msg_assistant_tool_call("resolve_location", {"query": "부산"}),
        _msg_tool_result("resolve_location", {"lat": 35.18, "lon": 129.07, "admcd": "21000"}),
        _msg_assistant_tool_call(
            "lookup",
            {
                "mode": "fetch",
                "tool_id": "kma_current_observation",
                "params": {"lat": 35.18, "lon": 129.07},
            },
        ),
        _msg_tool_result("lookup", {"t1h": 20.7, "reh": 23}),
    ]
    assert _check_resolve_terminated_without_followup(msgs, "부산 날씨") is None


def test_resolve_only_then_terminate_is_rejected() -> None:
    """G-class regression: resolve called but no follow-up lookup → reject."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="지금 부산 사하구 다대1동 날씨 어때"),
        _msg_assistant_tool_call(
            "resolve_location",
            {"query": "부산 사하구 다대1동", "want": "coords_and_admcd"},
        ),
        _msg_tool_result("resolve_location", {"lat": 35.05915, "lon": 128.97132}),
        _msg_assistant_tool_call(
            "resolve_location",
            {"query": "부산 사하구 다대1동", "want": "all"},
        ),
        _msg_tool_result("resolve_location", {"lat": 35.05915, "lon": 128.97132}),
    ]
    msg = _check_resolve_terminated_without_followup(msgs, "지금 부산 사하구 다대1동 날씨 어때")
    assert msg is not None
    assert "Chain incomplete" in msg
    assert "lookup" in msg.lower()
    assert "fabrication" in msg.lower()


def test_resolve_only_with_non_observable_query_passes() -> None:
    """When the query doesn't imply a follow-up, the gate stays out of the way."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 사하구 다대1동 주소"),
        _msg_assistant_tool_call("resolve_location", {"query": "부산 사하구 다대1동"}),
        _msg_tool_result("resolve_location", {"lat": 35.05915, "lon": 128.97132}),
    ]
    assert _check_resolve_terminated_without_followup(msgs, "부산 사하구 다대1동 주소") is None


def test_no_resolve_call_no_gate() -> None:
    """No resolve_location → gate doesn't fire even on observable queries."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="강남역 응급실"),
    ]
    assert _check_resolve_terminated_without_followup(msgs, "강남역 응급실") is None


def test_lookup_without_fetch_mode_still_counts() -> None:
    """K-EXAONE often omits ``mode`` when ``tool_id`` is set — that variant
    still satisfies the chain because the dispatcher treats it as fetch.
    """
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 날씨"),
        _msg_assistant_tool_call("resolve_location", {"query": "부산"}),
        _msg_tool_result("resolve_location", {"lat": 35.18, "lon": 129.07}),
        _msg_assistant_tool_call(
            "lookup",
            {
                "tool_id": "kma_current_observation",
                "params": {"lat": 35.18, "lon": 129.07},
            },
        ),
    ]
    assert _check_resolve_terminated_without_followup(msgs, "부산 날씨") is None


# ---------------------------------------------------------------------------
# Cross-check: existing _check_chain_prerequisite still rejects coord-input
# tools called WITHOUT a prior resolve_location.
# ---------------------------------------------------------------------------


def test_existing_prerequisite_gate_unchanged() -> None:
    """Sanity: the inverse-direction gate still rejects lookup-before-resolve.

    This test is defensive — it ensures the new gate refactor did not break
    the existing chain-prerequisite path that protects against the LLM
    guessing coordinates from parametric memory before resolve_location ran.
    """
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 날씨"),
    ]
    # registry=None → the schema-introspection branch falls through; the
    # explicit-coord-args branch fires because lat/lon ARE in params.
    err = _check_chain_prerequisite(
        "lookup",
        {
            "mode": "fetch",
            "tool_id": "kma_current_observation",
            "params": {"lat": 35.18, "lon": 129.07},
        },
        msgs,
        registry=None,
    )
    assert err is not None
    assert "resolve_location" in err


def test_nmc_prerequisite_message_names_region_mode() -> None:
    """NMC recovery must point at want='all' + region mode, not coords-only retry."""
    msgs: list[Any] = [LLMChatMessage(role="user", content="하단역 근처 응급실")]

    err = _check_chain_prerequisite(
        "lookup",
        {
            "mode": "fetch",
            "tool_id": "nmc_emergency_search",
            "params": {"mode": "coordinate", "lat": 35.1062, "lon": 128.9668, "limit": 5},
        },
        msgs,
        registry=None,
    )

    assert err is not None
    assert "want='all'" in err
    assert "mode:'region'" in err
    assert "q0:region.region_1depth_name" in err


def test_nmc_coordinate_mode_after_resolve_is_rejected() -> None:
    """A prior coords-only resolve is not enough for NMC citizen ER search."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="하단역 근처 응급실"),
        _msg_assistant_tool_call("resolve_location", {"query": "하단역", "want": "coords"}),
        _msg_tool_result("resolve_location", {"lat": 35.1062, "lon": 128.9668}),
    ]

    err = _check_chain_prerequisite(
        "lookup",
        {
            "mode": "fetch",
            "tool_id": "nmc_emergency_search",
            "params": {"mode": "coordinate", "lat": 35.1062, "lon": 128.9668, "limit": 5},
        },
        msgs,
        registry=None,
    )

    assert err is not None
    assert "official getEgytListInfoInqire region operation" in err
    assert "Do NOT retry coordinate mode" in err


def test_nmc_region_mode_after_resolve_is_allowed() -> None:
    """Region-mode NMC lookup may proceed after resolve_location."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="하단역 근처 응급실"),
        _msg_assistant_tool_call("resolve_location", {"query": "하단역", "want": "all"}),
        _msg_tool_result(
            "resolve_location",
            {
                "coords": {"lat": 35.1062, "lon": 128.9668},
                "region": {"region_1depth_name": "부산광역시", "region_2depth_name": "사하구"},
            },
        ),
    ]

    err = _check_chain_prerequisite(
        "lookup",
        {
            "mode": "fetch",
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "region",
                "q0": "부산광역시",
                "q1": "사하구",
                "origin_lat": 35.1062,
                "origin_lon": 128.9668,
                "limit": 5,
            },
        },
        msgs,
        registry=None,
    )

    assert err is None
