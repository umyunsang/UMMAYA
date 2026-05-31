# SPDX-License-Identifier: Apache-2.0
"""G-class chain enforcement — follow-up lookup gate tests.

Captures the donga-univ-poi-bug snap-001-01-kma-now (2026-05-04) regression:
K-EXAONE called ``locate`` twice and then produced a fabricated
weather answer (16°C / 84% humidity vs raw KMA 20.7°C / 23%) without ever
invoking ``lookup(kma_current_observation)``. The fix adds
``_check_resolve_terminated_without_followup`` which runs at the
``if not tool_call_buf:`` boundary and rejects the final-answer turn when
the conversation invoked resolve_location but did not follow up with a
coord/admcd-input lookup despite the dynamic available_adapters block
surfacing a registry-selected find candidate.

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
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from ummaya.ipc.stdio import (
    _available_adapters_block_has_find_candidate,
    _build_verify_session_context,
    _check_chain_prerequisite,
    _check_current_weather_terminated_without_observation,
    _check_direct_public_data_tool_choice_prerequisite,
    _check_duplicate_submit_prerequisite,
    _check_kma_aviation_tool_choice_prerequisite,
    _check_location_terminated_without_resolve,
    _check_medical_emergency_terminated_without_aed,
    _check_resolve_terminated_without_followup,
    _check_sensitive_lookup_auth_prerequisite,
    _check_sensitive_lookup_terminated_without_lookup,
    _check_submit_terminated_without_submit,
    _check_verify_terminated_without_verify,
    _check_verify_tool_choice_prerequisite,
    _conversation_has_successful_identical_primitive_call,
    _conversation_has_successful_lookup,
    _conversation_has_successful_primitive,
    _effective_chat_max_tokens,
    _final_answer_looks_like_generic_retry_after_success,
    _final_answer_looks_like_incomplete_sentence,
    _final_answer_looks_like_mismatched_kma_forecast_hour_label,
    _final_answer_looks_like_pending_tool_plan,
    _final_answer_looks_like_recursive_tool_message,
    _final_answer_looks_like_tool_call_narration,
    _final_answer_looks_like_unclosed_markdown,
    _final_answer_missing_current_weather_observation_values,
    _initial_concrete_tool_choice_for_query,
    _latest_citizen_user_utterance,
    _location_independent_resolve_redirect_for_query,
    _maybe_reroute_locate_admin_keyword_args,
    _maybe_reroute_locate_poi_address_args,
    _normalize_hira_lookup_args_from_prior_locate,
    _normalize_koroad_lookup_args_from_prior_locate,
    _normalize_lookup_args_for_query,
    _normalize_lookup_args_from_cached_locate_result,
    _normalize_nmc_lookup_args_from_prior_locate,
    _normalize_pps_bid_args_from_user_query,
    _normalize_reverse_geocode_args_from_prior_locate,
    _normalize_root_primitive_adapter_envelope,
    _normalize_submit_args_for_query,
    _normalize_verify_args_for_query,
    _normalize_verify_tool_id_for_query,
    _pps_current_week_window,
    _query_implies_current_weather_observation,
    _query_implies_location_resolution,
    _sensitive_lookup_verify_redirect_for_query,
    _submit_requirement_for_query,
    _tool_result_payload_is_error,
)
from ummaya.llm.models import (
    ChatMessage as LLMChatMessage,
)
from ummaya.llm.models import (
    FunctionCall as LLMFunctionCall,
)
from ummaya.llm.models import (
    ToolCall as LLMToolCall,
)

# ---------------------------------------------------------------------------
# Dynamic available_adapters follow-up signal
# ---------------------------------------------------------------------------


def test_available_adapters_find_candidate_triggers_followup_signal() -> None:
    """Registry-selected find candidates, not static keywords, trigger follow-up."""
    block = "\n".join(
        [
            '<available_adapters query="다대1동 근처 내과">',
            "- hira_hospital_search (primitive=find) [18.40] — 병원 검색",
            "- kakao_keyword_search (primitive=locate) [12.00] — 장소 검색",
            "</available_adapters>",
        ]
    )
    assert _available_adapters_block_has_find_candidate(block)


def test_locate_only_available_adapters_do_not_trigger_followup_signal() -> None:
    """Pure locate candidate blocks stay out of the follow-up gate."""
    block = "\n".join(
        [
            '<available_adapters query="부산 사하구 다대1동 주소">',
            "- kakao_address_search (primitive=locate) [12.00] — 주소 검색",
            "- kakao_coord_to_region (primitive=locate) [8.00] — 좌표 역변환",
            "</available_adapters>",
        ]
    )
    assert not _available_adapters_block_has_find_candidate(block)


def test_current_weather_query_requires_observation() -> None:
    """Current/today weather should use current observation before final prose."""
    assert _query_implies_current_weather_observation("다대포해수욕장 오늘 날씨 알려줘")
    assert _query_implies_current_weather_observation("부산 지금 기온")
    assert _query_implies_current_weather_observation("다대포 산책 가도 될까? 비 오는지만 봐줘")
    assert not _query_implies_current_weather_observation(
        "kma_ultra_short_term_forecast 도구로 서울 종로구 현재 초단기예보 조회해줘"
    )
    assert not _query_implies_current_weather_observation(
        "kma_ultra_short_term_forecast 도구로 서울 종로구 현재 초단기예보를 조회해서 "
        "15시와 16시 날씨를 요약해줘"
    )
    assert _query_implies_current_weather_observation("서울 현재 기온과 초단기예보 둘 다 알려줘")
    assert not _query_implies_current_weather_observation("내일 서울 날씨 예보")
    assert not _query_implies_current_weather_observation(
        "다대1동에서 오늘 전화해볼 만한 내과나 이비인후과 3곳 알려줘"
    )


def test_locate_admin_keyword_args_reroute_to_address_adapter() -> None:
    """Bare 행정동 text must paint and execute as Kakao address search."""
    args = {
        "tool_id": "kakao_keyword_search",
        "params": {"query": "부산 사하구 다대1동에서"},
    }

    rerouted = _maybe_reroute_locate_admin_keyword_args("locate", args)

    assert rerouted == {
        "tool_id": "kakao_address_search",
        "params": {"query": "부산 사하구 다대1동"},
    }


def test_locate_poi_keyword_args_are_not_rerouted() -> None:
    """POI names such as beaches still use Kakao keyword search."""
    args = {
        "tool_id": "kakao_keyword_search",
        "params": {"query": "다대포해수욕장"},
    }

    assert _maybe_reroute_locate_admin_keyword_args("locate", args) == args


def test_locate_poi_address_args_reroute_to_keyword_adapter() -> None:
    """Named POIs should not burn a Kakao address-search error first."""
    args = {
        "tool_id": "kakao_address_search",
        "params": {"query": "부산 사하구 다대포해수욕장"},
    }

    rerouted = _maybe_reroute_locate_poi_address_args("locate", args)

    assert rerouted == {
        "tool_id": "kakao_keyword_search",
        "params": {"query": "부산 사하구 다대포해수욕장"},
    }


def test_locate_road_address_args_are_not_rerouted_to_keyword() -> None:
    """Concrete road addresses remain on Kakao address search."""
    args = {
        "tool_id": "kakao_address_search",
        "params": {"query": "부산 사하구 낙동대로 408"},
    }

    assert _maybe_reroute_locate_poi_address_args("locate", args) == args


def test_recursive_tool_message_final_answer_is_rejected() -> None:
    """A final answer must not recursively quote tool error wrapper prose."""
    assert _final_answer_looks_like_recursive_tool_message(
        '도구가 반환한 메시지: "도구가 반환한 메시지: \\"도구가 반환한 메시지: ...\\""'
    )
    assert not _final_answer_looks_like_recursive_tool_message(
        '도구가 반환한 메시지: "Adapter returned a schema error."'
    )
    assert not _final_answer_looks_like_recursive_tool_message(
        "기상청 자료에 따르면 현재 기온은 16.0°C입니다."
    )


def test_unclosed_markdown_final_answer_is_rejected() -> None:
    """A final answer must not end with a dangling Markdown emphasis marker."""
    assert _final_answer_looks_like_unclosed_markdown("**응급실:**\n- 큐병원\n\n**")
    assert not _final_answer_looks_like_unclosed_markdown("**응급실:**\n- 큐병원")
    assert not _final_answer_looks_like_unclosed_markdown(
        "기상청 자료에 따르면 현재 기온은 16.0°C입니다."
    )


def test_tool_call_narration_final_answer_is_rejected() -> None:
    """A final answer should start with citizen-facing results, not tool history."""
    assert _final_answer_looks_like_tool_call_narration(
        "방금 카카오 키워드 검색 도구를 호출해 위치를 조회했습니다. 결과는 다음과 같습니다."
    )
    assert _final_answer_looks_like_tool_call_narration(
        "HIRA 병원 검색 도구로 조회한 결과, 가까운 병원은 부산본병원입니다."
    )
    assert not _final_answer_looks_like_tool_call_narration(
        "가까운 병원은 부산본병원이며, 자료 출처는 건강보험심사평가원입니다."
    )


def test_kma_forecast_final_answer_rejects_mismatched_hour_labels() -> None:
    """KMA forecast final prose must use returned fcst_time literally."""
    messages = [
        _msg_assistant_tool_call(
            "find",
            {
                "tool_id": "kma_ultra_short_term_forecast",
                "params": {"base_date": "20260518", "base_time": "1500", "nx": 61, "ny": 128},
            },
        ),
        _msg_tool_result(
            "find",
            {
                "ok": True,
                "result": {
                    "kind": "collection",
                    "items": [
                        {
                            "base_date": "20260518",
                            "base_time": "1530",
                            "fcst_date": "20260518",
                            "fcst_time": "1600",
                            "category": "T1H",
                            "fcst_value": "30",
                        }
                    ],
                },
            },
        ),
    ]

    assert _final_answer_looks_like_mismatched_kma_forecast_hour_label(
        "15시(16:00) 예보 기온은 30°C입니다.",
        messages,
    )
    assert not _final_answer_looks_like_mismatched_kma_forecast_hour_label(
        "16:00 예보 기온은 30°C입니다.",
        messages,
    )


def test_generic_retry_final_answer_after_success_is_rejected() -> None:
    """A final answer must not ask for retry after successful data returned."""
    assert _final_answer_looks_like_generic_retry_after_success(
        "정확한 정보는 기상청 https://www.weather.go.kr 또는 기상특보 131에서 "
        "확인하시기 바랍니다.\n\n"
        "다른 검색어로 재시도하시겠습니까?"
    )
    assert not _final_answer_looks_like_generic_retry_after_success(
        "기상청 관측 기준 현재 기온은 15.8°C이고 강수량은 0mm입니다. "
        "정확한 특보는 기상청에서 확인할 수 있습니다."
    )


def test_meta_instruction_final_answer_after_success_is_rejected() -> None:
    """A final answer must not expose self-instructions after successful tools."""
    assert _final_answer_looks_like_pending_tool_plan(
        "AED 검색 결과를 얻었습니다. 이제 응급 상황에 대한 지침을 제공해야 합니다. "
        "최종 답변은 다음과 같아야 합니다: 119에 즉시 전화하세요."
    )
    assert _final_answer_looks_like_pending_tool_plan(
        "각 시설의 정확한 주소, 연락처, 거리 정보는 도구 결과에서 그대로 가져와야 합니다."
    )
    assert _final_answer_looks_like_pending_tool_plan(
        "부산광역시의 미세먼지 정보를 확인해 보겠습니다."
    )
    assert not _final_answer_looks_like_pending_tool_plan(
        "119에 즉시 전화하고, 부산여객터미널 2층 갱웨이 AED를 가져오도록 주변 사람에게 요청하세요."
    )


def test_current_weather_final_answer_must_include_kma_values() -> None:
    """Successful KMA current observation must be reflected in final prose."""
    messages = [
        _msg_assistant_tool_call(
            "find",
            {
                "tool_id": "kma_current_observation",
                "params": {"nx": 97, "ny": 74, "base_date": "20260514", "base_time": "0400"},
            },
        ),
        _msg_tool_result(
            "find",
            {
                "ok": True,
                "result": {
                    "kind": "record",
                    "item": {
                        "base_date": "20260514",
                        "base_time": "0400",
                        "nx": 97,
                        "ny": 74,
                        "t1h": 15.8,
                        "rn1": 0,
                        "reh": 79,
                        "wsd": 1,
                    },
                },
            },
        ),
    ]
    assert _final_answer_missing_current_weather_observation_values(
        "정확한 정보는 기상청에서 확인하시기 바랍니다. 다른 검색어로 재시도하시겠습니까?",
        messages,
        "부산 사하구 다대1동 지금 날씨 알려줘",
    )
    assert not _final_answer_missing_current_weather_observation_values(
        "기상청 관측 기준 현재 기온은 15.8°C, 강수량은 0mm, 습도는 79%입니다.",
        messages,
        "부산 사하구 다대1동 지금 날씨 알려줘",
    )


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


def _msg_available_adapters(*, find: bool = True) -> LLMChatMessage:
    candidate = (
        "- kma_current_observation (primitive=find) [18.40] — 기상청 현재 관측"
        if find
        else "- kakao_address_search (primitive=locate) [12.00] — 주소 검색"
    )
    return LLMChatMessage(
        role="system",
        content="\n".join(
            [
                '<available_adapters query="테스트">',
                candidate,
                "</available_adapters>",
            ]
        ),
    )


def _msg_emergency_available_adapters(*, aed: bool = True) -> LLMChatMessage:
    lines = [
        '<available_adapters query="부산역 근처에 사람이 쓰러졌어">',
        "- nmc_emergency_search (primitive=find) [21.50] — 응급실 검색",
    ]
    if aed:
        lines.append("- nmc_aed_site_locate (primitive=find) [20.80] — AED 위치 검색")
    lines.append("</available_adapters>")
    return LLMChatMessage(role="system", content="\n".join(lines))


def _auth_with_scope(scope: str) -> SimpleNamespace:
    return SimpleNamespace(delegation_context=SimpleNamespace(token=SimpleNamespace(scope=scope)))


def test_medical_collapse_requires_aed_after_successful_er_lookup() -> None:
    """Collapse wording needs AED search as well as emergency-room search."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"),
        _msg_emergency_available_adapters(aed=True),
        _msg_assistant_tool_call(
            "nmc_emergency_search",
            {"mode": "region", "q0": "부산광역시", "q1": "동구", "limit": 5},
        ),
        _msg_tool_result(
            "nmc_emergency_search",
            {
                "ok": True,
                "result": {
                    "kind": "collection",
                    "items": [{"name": "봉생기념병원", "distance_m": 910}],
                },
            },
        ),
    ]

    msg = _check_medical_emergency_terminated_without_aed(
        msgs,
        "부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?",
    )

    assert msg is not None
    assert "nmc_aed_site_locate" in msg
    assert "Do NOT produce a final answer" in msg


def test_medical_collapse_aed_gate_passes_after_aed_attempt() -> None:
    """Once AED was attempted, final prose may report its result or failure."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"),
        _msg_emergency_available_adapters(aed=True),
        _msg_assistant_tool_call(
            "nmc_emergency_search",
            {"mode": "region", "q0": "부산광역시", "q1": "동구", "limit": 5},
        ),
        _msg_tool_result(
            "nmc_emergency_search",
            {"ok": True, "result": {"kind": "collection", "items": [{"name": "응급실"}]}},
        ),
        _msg_assistant_tool_call(
            "nmc_aed_site_locate",
            {"q0": "부산광역시", "q1": "동구", "limit": 5},
        ),
    ]

    assert (
        _check_medical_emergency_terminated_without_aed(
            msgs,
            "부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?",
        )
        is None
    )


def test_medical_collapse_aed_gate_ignores_non_collapse_emergency_call_box() -> None:
    """Civil-safety call-box wording must not be converted into AED routing."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산역 근처 비상벨이나 안심벨 어디 있어?"),
        _msg_emergency_available_adapters(aed=True),
        _msg_assistant_tool_call(
            "nmc_emergency_search",
            {"mode": "region", "q0": "부산광역시", "q1": "동구", "limit": 5},
        ),
        _msg_tool_result(
            "nmc_emergency_search",
            {"ok": True, "result": {"kind": "collection", "items": [{"name": "응급실"}]}},
        ),
    ]

    assert (
        _check_medical_emergency_terminated_without_aed(
            msgs,
            "부산역 근처 비상벨이나 안심벨 어디 있어?",
        )
        is None
    )


def test_medical_collapse_aed_gate_waits_for_aed_adapter_surface() -> None:
    """The gate is driven by the model-facing adapter surface, not a static route."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"),
        _msg_emergency_available_adapters(aed=False),
        _msg_assistant_tool_call(
            "nmc_emergency_search",
            {"mode": "region", "q0": "부산광역시", "q1": "동구", "limit": 5},
        ),
        _msg_tool_result(
            "nmc_emergency_search",
            {"ok": True, "result": {"kind": "collection", "items": [{"name": "응급실"}]}},
        ),
    ]

    assert (
        _check_medical_emergency_terminated_without_aed(
            msgs,
            "부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?",
        )
        is None
    )


def _hometax_lookup_args() -> dict[str, object]:
    return {
        "mode": "fetch",
        "tool_id": "mock_lookup_module_hometax_simplified",
        "params": {"year": 2025, "resident_id_prefix": "000000"},
    }


# ---------------------------------------------------------------------------
# Duplicate primitive non-progress guard
# ---------------------------------------------------------------------------


def _hira_lookup_args() -> dict[str, object]:
    return {
        "tool_id": "hira_hospital_search",
        "params": {
            "xPos": 128.962741189119,
            "yPos": 35.0465263488422,
            "dgsbjt": "내과,이비인후과",
        },
    }


def _successful_hira_messages() -> list[LLMChatMessage]:
    return [
        _msg_assistant_tool_call("find", _hira_lookup_args()),
        _msg_tool_result(
            "find",
            {
                "ok": True,
                "result": {
                    "kind": "collection",
                    "total_count": 33,
                    "items": [
                        {
                            "yadmNm": "서울성모내과의원",
                            "addr": "부산광역시 사하구 다대로 694, 6층 (다대동)",
                            "telno": "051-262-8575",
                            "clCdNm": "의원",
                            "matchedDgsbjtNm": "내과",
                            "distance": 283,
                        },
                        {
                            "yadmNm": "다대원이비인후과의원",
                            "addr": "부산광역시 사하구 다대로 702, 6층 (다대동)",
                            "telno": "051-265-7555",
                            "clCdNm": "의원",
                            "matchedDgsbjtNm": "이비인후과",
                            "distance": 392,
                        },
                    ],
                },
            },
        ),
    ]


def test_duplicate_primitive_call_detects_successful_identical_result() -> None:
    """Repeated same-args primitive calls after success are non-progress."""
    messages = _successful_hira_messages()

    assert _conversation_has_successful_identical_primitive_call(
        messages,
        primitive="find",
        args=_hira_lookup_args(),
    )
    assert not _conversation_has_successful_identical_primitive_call(
        messages,
        primitive="find",
        args={
            "tool_id": "hira_hospital_search",
            "params": {
                "xPos": 128.962741189119,
                "yPos": 35.0465263488422,
                "dgsbjt": "소아청소년과",
            },
        },
    )


def test_incomplete_final_sentence_is_rejected_after_tool_success() -> None:
    """A dangling final sentence should be routed back through the model loop."""
    assert _final_answer_looks_like_incomplete_sentence("기상청 현재관측 자료에 따르면,")
    assert _final_answer_looks_like_incomplete_sentence("조회 결과는 다음과 같습니다:")
    assert not _final_answer_looks_like_incomplete_sentence("비는 오지 않습니다.")


# ---------------------------------------------------------------------------
# Sensitive lookup auth gate
# ---------------------------------------------------------------------------


def test_sensitive_hometax_lookup_without_verify_is_rejected() -> None:
    """Citizen-specific Hometax records require verify delegation first."""
    msg = _check_sensitive_lookup_auth_prerequisite(
        "find",
        _hometax_lookup_args(),
        None,
    )

    assert msg is not None
    assert "mock_verify_module_modid" in msg
    assert "find:hometax.simplified" in msg
    assert "Do NOT answer" in msg


def test_sensitive_hometax_lookup_with_matching_scope_passes() -> None:
    """A cached delegation scope for find:hometax.simplified satisfies the gate."""
    msg = _check_sensitive_lookup_auth_prerequisite(
        "find",
        _hometax_lookup_args(),
        _auth_with_scope("find:hometax.simplified,send:hometax.tax-return"),
    )

    assert msg is None


def test_sensitive_hometax_lookup_with_wrong_scope_is_rejected() -> None:
    """Wrong cached delegation scope must not unlock Hometax simplified data."""
    msg = _check_sensitive_lookup_auth_prerequisite(
        "find",
        _hometax_lookup_args(),
        _auth_with_scope("send:hometax.tax-return"),
    )

    assert msg is not None
    assert "do not include 'find:hometax.simplified'" in msg


def test_sensitive_hometax_submit_query_redirects_lookup_to_verify() -> None:
    """Premature Hometax lookup in a submit flow is redirected before rendering."""
    redirect = _sensitive_lookup_verify_redirect_for_query(
        "find",
        _hometax_lookup_args(),
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
        None,
    )

    assert redirect is not None
    assert redirect["verify_tool_id"] == "mock_verify_module_modid"
    assert redirect["required_scopes"] == "find:hometax.simplified,send:hometax.tax-return"


def test_sensitive_lookup_redirect_is_dormant_when_scope_is_cached() -> None:
    """Already verified sessions should dispatch the lookup normally."""
    assert (
        _sensitive_lookup_verify_redirect_for_query(
            "find",
            _hometax_lookup_args(),
            "홈택스 연말정산 간소화 자료 조회해줘",
            _auth_with_scope("find:hometax.simplified"),
        )
        is None
    )


def test_sensitive_lookup_redirect_ignores_unrelated_queries() -> None:
    """The redirect is scoped to citizen queries that imply the same verify contract."""
    assert (
        _sensitive_lookup_verify_redirect_for_query(
            "find",
            _hometax_lookup_args(),
            "부산 사하구 다대1동 날씨 알려줘",
            None,
        )
        is None
    )


def test_hometax_lookup_missing_tool_id_is_canonicalized_from_query() -> None:
    """Forced lookup turns still need the adapter id implied by the citizen query."""
    normalized = _normalize_lookup_args_for_query(
        "find",
        {"tool_id": "", "params": {}},
        "작년 연말정산 간소화 자료 중 의료비와 교육비 내역을 확인해줘",
    )

    assert normalized["tool_id"] == "mock_lookup_module_hometax_simplified"
    assert normalized["params"] == {"year": 2025, "resident_id_prefix": "000000"}


def test_hometax_lookup_generic_tool_id_is_canonicalized_from_query() -> None:
    """Some model turns echo the primitive name as tool_id; map it to the adapter."""
    normalized = _normalize_lookup_args_for_query(
        "find",
        {"tool_id": "find", "params": {"year": None}},
        "홈택스 연말정산 간소화 자료 조회해줘",
    )

    assert normalized["tool_id"] == "mock_lookup_module_hometax_simplified"
    assert normalized["params"] == {"year": 2025, "resident_id_prefix": "000000"}


def test_lookup_result_count_uses_adapter_schema_field_name() -> None:
    """Citizen-stated counts are preserved through the adapter input schema."""
    normalized = _normalize_lookup_args_for_query(
        "find",
        {
            "tool_id": "hira_hospital_search",
            "params": {"xPos": 128.971316, "yPos": 35.059152},
        },
        "부산 사하구 다대1동에서 가까운 내과 3곳만 알려줘",
        adapter_param_names={"xPos", "yPos", "numOfRows", "pageNo"},
    )

    assert normalized["params"]["numOfRows"] == 3


def test_non_sensitive_lookup_does_not_trigger_auth_gate() -> None:
    """Public agency lookup adapters continue through the normal lookup path."""
    msg = _check_sensitive_lookup_auth_prerequisite(
        "find",
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
        _msg_assistant_tool_call("find", _hometax_lookup_args()),
        _msg_tool_result(
            "find",
            {
                "kind": "find",
                "result": {"kind": "error", "reason": "auth_required"},
            },
        ),
    ]

    msg = _check_sensitive_lookup_terminated_without_lookup(
        msgs,
        "연말정산 간소화 자료 조회해서 의료비랑 교육비 항목만 요약해줘",
        _auth_with_scope("find:hometax.simplified"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_lookup_module_hometax_simplified"
    assert "Do NOT answer from the verify result alone" in msg["message"]


def test_sensitive_hometax_after_successful_lookup_passes() -> None:
    """A successful target lookup result clears the post-verify follow-up gate."""
    msgs: list[Any] = [
        _msg_assistant_tool_call("find", _hometax_lookup_args()),
        _msg_tool_result(
            "find",
            {
                "kind": "find",
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
            _auth_with_scope("find:hometax.simplified"),
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
    assert msg["required_scopes"] == "find:hometax.simplified,send:hometax.tax-return"
    assert "find:hometax.simplified" in msg["message"]
    assert "send:hometax.tax-return" in msg["message"]


def test_hometax_taxreturn_rejects_lookup_only_verify_scope() -> None:
    """Tax-return filing verify must grant both lookup and submit scopes."""
    msg = _check_verify_tool_choice_prerequisite(
        "check",
        {
            "tool_id": "mock_verify_module_modid",
            "params": {
                "scope_list": ["find:hometax.simplified"],
                "purpose_ko": "연말정산 간소화 자료 조회",
                "purpose_en": "Hometax simplified year-end tax lookup",
            },
        },
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_module_modid"
    assert "send:hometax.tax-return" in msg["message"]


def test_hometax_taxreturn_allows_lookup_and_submit_verify_scopes() -> None:
    """Canonical tax-return verify scope_list passes the tool-choice gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "check",
        {
            "tool_id": "mock_verify_module_modid",
            "params": {
                "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
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
                "find:mock.lookup_module_hometax_simplified",
                "send:hometax.tax-return",
            ],
            "purpose_ko": "종합소득세 신고",
            "purpose_en": "Comprehensive income tax filing",
        },
    }

    normalized = _normalize_verify_args_for_query(
        "check",
        verify_args,
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    params = normalized["params"]
    assert isinstance(params, dict)
    assert params["scope_list"] == [
        "find:hometax.simplified",
        "send:hometax.tax-return",
    ]
    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
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
            "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
            "purpose_ko": "연말정산 간소화 자료 조회",
            "purpose_en": "Hometax simplified year-end tax lookup",
        },
    }

    normalized = _normalize_verify_args_for_query(
        "check",
        verify_args,
        "홈택스 연말정산 간소화에서 작년 의료비랑 교육비 공제 자료 조회해줘",
    )

    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
            normalized,
            "홈택스 연말정산 간소화에서 작년 의료비랑 교육비 공제 자료 조회해줘",
        )
        is None
    )
    session_context = _build_verify_session_context(
        normalized,
        session_id="HOMETAX-SIMPLIFIED-SESSION-001",
    )
    assert session_context["scope_list"] == ["find:hometax.simplified"]


def test_hometax_taxreturn_submit_requirement_uses_fixture_defaults() -> None:
    """The submit gate can recover the mock tax-return payload without asking PII."""
    requirement = _submit_requirement_for_query(
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘"
    )

    assert requirement is not None
    assert requirement["tool_id"] == "mock_submit_module_hometax_taxreturn"
    assert requirement["scope"] == "send:hometax.tax-return"
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
        "locate",
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert redirect == {"primitive": "check", "tool_id": "mock_verify_module_modid"}


def test_hometax_lookup_detail_word_does_not_imply_location() -> None:
    """Korean '내역' must not be treated as a station suffix."""
    query = "작년 연말정산 간소화 자료 중 의료비와 교육비 내역 확인해줘"

    assert not _query_implies_location_resolution(query)
    redirect = _location_independent_resolve_redirect_for_query("locate", query)
    assert redirect == {"primitive": "check", "tool_id": "mock_verify_module_modid"}


def test_root_primitive_envelope_strips_duplicate_nested_tool_id() -> None:
    """Backend stdio dispatch mirrors the TUI root primitive normalizer."""
    normalized = _normalize_root_primitive_adapter_envelope(
        "locate",
        {
            "tool_id": "kakao_keyword_search",
            "params": {"tool_id": "kakao_keyword_search", "query": "김포공항"},
        },
    )

    assert normalized == {
        "tool_id": "kakao_keyword_search",
        "params": {"query": "김포공항"},
    }


def test_airport_aviation_query_rejects_locate_substitution() -> None:
    """Flight/visibility wording should force KMA aviation adapters first."""
    msg = _check_kma_aviation_tool_choice_prerequisite(
        "locate",
        {"tool_id": "kakao_keyword_search", "params": {"query": "김해공항"}},
        "오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘",
    )

    assert msg is not None
    assert "kma_apihub_url_air_metar_decoded" in msg
    assert "ordinary KMA current observation" in msg


def test_latest_citizen_user_utterance_skips_available_adapters_suffix() -> None:
    """Dynamic adapter context must not become the latest citizen utterance."""
    citizen_text = "부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"
    latest = _latest_citizen_user_utterance(
        [
            SimpleNamespace(role="user", content=citizen_text),
            SimpleNamespace(
                role="user",
                content=(
                    '<available_adapters query="부산역 근처에 사람이 쓰러졌어">'
                    "kma_apihub_url_air_metar_decoded METAR 김해공항 김포공항 시정"
                    "</available_adapters>"
                ),
            ),
        ]
    )

    assert latest == citizen_text
    assert (
        _check_kma_aviation_tool_choice_prerequisite(
            "locate",
            {"tool_id": "kakao_keyword_search", "params": {"query": "부산역"}},
            latest,
        )
        is None
    )


def test_initial_concrete_tool_choice_for_unambiguous_public_data_queries() -> None:
    available = {
        "find",
        "locate",
        "pps_bid_public_info",
        "airkorea_ctprvn_air_quality",
        "kma_apihub_url_analysis_weather_chart_image",
        "kma_apihub_url_air_metar_decoded",
        "tago_bus_route_search",
    }

    assert (
        _initial_concrete_tool_choice_for_query(
            "이번 주 부산시 전기공사 입찰 올라온 거 있어?",
            available,
        )
        == "pps_bid_public_info"
    )
    assert (
        _initial_concrete_tool_choice_for_query(
            "지금 부산 중구 미세먼지 괜찮아? 마스크 써야 해?",
            available,
        )
        == "airkorea_ctprvn_air_quality"
    )
    assert (
        _initial_concrete_tool_choice_for_query(
            "오늘 오후 전국 비구름 흐름이 어떤지 공식 기상도나 위성 자료 기준으로 설명해줘",
            available,
        )
        == "kma_apihub_url_analysis_weather_chart_image"
    )
    assert (
        _initial_concrete_tool_choice_for_query(
            "오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘",
            available,
        )
        == "kma_apihub_url_air_metar_decoded"
    )
    assert (
        _initial_concrete_tool_choice_for_query(
            "부산역에서 1001번 버스 곧 와?",
            available,
        )
        == "tago_bus_route_search"
    )


def test_public_data_tool_choice_rejects_unrelated_concrete_adapters() -> None:
    preferred, message = _check_direct_public_data_tool_choice_prerequisite(
        "airkorea_ctprvn_air_quality",
        {"sido_name": "부산"},
        "부산역에서 1001번 버스 곧 와?",
    ) or (None, "")
    assert preferred == "tago_bus_route_search"
    assert "Public-data tool-choice mismatch" in message
    assert "airkorea_ctprvn_air_quality" in message

    preferred, message = _check_direct_public_data_tool_choice_prerequisite(
        "airkorea_ctprvn_air_quality",
        {"sido_name": "부산"},
        "퇴근하고 해운대 산책 갈 건데 지금 비 와? 우산 챙겨야 해?",
    ) or (None, "")
    assert preferred == "kakao_keyword_search"
    assert "KMA current observation" in message

    assert (
        _check_direct_public_data_tool_choice_prerequisite(
            "airkorea_ctprvn_air_quality",
            {"sido_name": "부산"},
            "부산 중구 미세먼지 지금 어때? 마스크 써야 해?",
        )
        is None
    )


def test_pps_bid_args_fill_region_and_keyword_from_citizen_query() -> None:
    normalized = _normalize_pps_bid_args_from_user_query(
        "find",
        {
            "tool_id": "pps_bid_public_info",
            "params": {
                "inqry_bgn_dt": "202605250000",
                "inqry_end_dt": "202605292359",
            },
        },
        "이번 주 부산시 전기공사 입찰 올라온 거 있어?",
    )

    assert normalized["params"]["bid_ntce_nm"] == "전기공사"
    assert normalized["params"]["region_name"] == "부산광역시"
    assert normalized["params"]["prtcpt_lmt_rgn_nm"] == "부산광역시"
    assert normalized["params"]["indstryty_nm"] == "전기공사업"
    assert normalized["params"]["inqry_bgn_dt"] == _pps_current_week_window()[0]
    assert normalized["params"]["inqry_end_dt"] == _pps_current_week_window()[1]


def test_pps_current_week_window_uses_kst_monday_to_today() -> None:
    start, end = _pps_current_week_window(
        datetime(2026, 5, 29, 1, 39, tzinfo=ZoneInfo("Asia/Seoul"))
    )

    assert start == "202605250000"
    assert end == "202605292359"


def test_kma_aviation_tool_choice_rejects_unrelated_concrete_adapters() -> None:
    message = _check_kma_aviation_tool_choice_prerequisite(
        "airkorea_ctprvn_air_quality",
        {"sido_name": "경남"},
        "오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘",
    )
    assert message is not None
    assert "KMA aviation tool-choice mismatch" in message


def test_tool_call_text_is_never_valid_final_answer_after_tool_result() -> None:
    assert _final_answer_looks_like_tool_call_narration(
        '<tool_call>{"name":"find_weather_kma","arguments":{"station_id":"109"}}</tool_call>'
    )


def test_location_query_does_not_suppress_resolve_location() -> None:
    """Real place/address workflows keep the resolver path."""
    assert (
        _location_independent_resolve_redirect_for_query(
            "locate",
            "하단역 근처 야간 응급실 찾아줘",
        )
        is None
    )


def test_station_name_still_implies_location_resolution() -> None:
    """Station-like place names keep the locate path."""
    assert _query_implies_location_resolution("하단역 근처 야간 응급실 찾아줘")


def test_gov24_lookup_suppresses_irrelevant_resolve_without_forcing_verify() -> None:
    """Read-only non-location workflows retry freely instead of resolving Seoul."""
    redirect = _location_independent_resolve_redirect_for_query(
        "locate",
        "정부24에서 내가 발급 가능한 증명서 목록 조회해줘",
    )

    assert redirect == {"primitive": "free", "tool_id": ""}


def test_hometax_lookup_args_are_filled_from_citizen_query() -> None:
    """Hometax simplified lookup gets deterministic fixture fields."""
    normalized = _normalize_lookup_args_for_query(
        "find",
        {"tool_id": "mock_lookup_module_hometax_simplified"},
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
    )

    assert normalized["params"] == {"year": 2025, "resident_id_prefix": "000000"}


def test_hometax_lookup_relative_last_year_overrides_model_default() -> None:
    """The 2026-05-07 target-state fixture maps '작년' to 2025, not 2024."""
    normalized = _normalize_lookup_args_for_query(
        "find",
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
        "find",
        {
            "tool_id": "mock_lookup_module_hometax_simplified",
            "params": {
                "delegation_context": {
                    "token": {"scope": "find:hometax.simplified"},
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
    assert delegation_context == {"token": {"scope": "find:hometax.simplified"}}


def test_hometax_taxreturn_submit_args_override_model_classification() -> None:
    """The Hometax tax-return mock uses the fixture's comprehensive-tax payload."""
    normalized = _normalize_submit_args_for_query(
        "send",
        {
            "tool_id": "mock_submit_module_hometax_taxreturn",
            "params": {
                "tax_year": 2024,
                "income_type": "근로소득",
                "total_income_krw": 1,
                "session_id": "MODEL-GUESSED-SESSION-001",
                "delegation_context": {"token": {"scope": "send:hometax.tax-return"}},
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
                "check",
                {
                    "tool_id": "mock_verify_module_modid",
                    "params": {
                        "scope_list": [
                            "find:hometax.simplified",
                            "send:hometax.tax-return",
                        ]
                    },
                },
            ),
            _msg_tool_result("check", {"status": "verified"}),
        ],
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
        _auth_with_scope("find:hometax.simplified,send:hometax.tax-return"),
    )

    assert msg is None


def test_hometax_taxreturn_after_lookup_without_submit_is_rejected() -> None:
    """After verify and lookup succeed, tax-return filing must continue into submit."""
    msg = _check_submit_terminated_without_submit(
        [
            _msg_assistant_tool_call(
                "check",
                {
                    "tool_id": "mock_verify_module_modid",
                    "params": {
                        "scope_list": [
                            "find:hometax.simplified",
                            "send:hometax.tax-return",
                        ]
                    },
                },
            ),
            _msg_tool_result("check", {"status": "verified"}),
            _msg_assistant_tool_call("find", _hometax_lookup_args()),
            _msg_tool_result(
                "find",
                {
                    "kind": "find",
                    "result": {
                        "kind": "record",
                        "data": {"medical_expenses": 1_250_000},
                    },
                },
            ),
        ],
        "작년 종합소득세 신고서를 제출하기 전 검토하고 최종 제출까지 진행해줘",
        _auth_with_scope("find:hometax.simplified,send:hometax.tax-return"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_submit_module_hometax_taxreturn"
    assert "HOMETAX-TAXRETURN-SESSION-001" in msg["message"]


def test_welfare_application_after_verify_without_submit_is_rejected() -> None:
    """A verified welfare application request must continue into submit."""
    msg = _check_submit_terminated_without_submit(
        [
            _msg_assistant_tool_call(
                "check",
                {
                    "tool_id": "mock_verify_mydata",
                    "params": {"scope_list": ["send:mydata.welfare_application"]},
                },
            ),
            _msg_tool_result("check", {"status": "verified"}),
        ],
        (
            "한부모가족 아동양육비 지원을 신규 신청해줘. "
            "신청자 DI는 DI-TEST-HANPARENT-001이고 가구원 수는 2명이야."
        ),
        _auth_with_scope("send:mydata.welfare_application"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_welfare_application_submit_v1"
    assert "DI-TEST-HANPARENT-001" in msg["message"]
    assert '"household_size": 2' in msg["message"]


def test_welfare_lookup_args_are_filled_from_citizen_query() -> None:
    """Single-parent child-support lookup gets deterministic SSIS filters."""
    normalized = _normalize_lookup_args_for_query(
        "find",
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
        "find",
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
                "check",
                {
                    "tool_id": "mock_verify_ganpyeon_injeung",
                    "params": {"scope_list": ["send:traffic.fine-pay"]},
                },
            ),
            _msg_tool_result("check", {"status": "verified"}),
        ],
        "교통 과태료가 있는지 확인하고 납부까지 진행해줘",
        _auth_with_scope("send:traffic.fine-pay"),
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
                "find:traffic_fine.check",
                "find:traffic.fine",
                "find:traffic.fine.inquiry",
                "find:traffic.fine.search",
                "send:traffic_fine.payment",
                "send:traffic.fine.pay",
                "send:traffic_fine_pay_v1",
                "send:traffic.fine_pay_v1",
            ],
            "purpose_ko": "교통 과태료 확인 및 납부",
            "purpose_en": "Traffic fine check and payment",
        },
    }

    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
            verify_args,
            "교통 과태료가 있는지 확인하고 납부까지 진행해줘",
        )
        is None
    )
    session_context = _build_verify_session_context(
        verify_args,
        session_id="TRAFFIC-FINE-SESSION-001",
    )
    assert session_context["scope_list"] == ["send:traffic.fine-pay"]


def test_mydata_action_after_verify_without_submit_is_rejected() -> None:
    """Public MyData consent requests must continue from verify into submit."""
    msg = _check_submit_terminated_without_submit(
        [
            _msg_assistant_tool_call(
                "check",
                {
                    "tool_id": "mock_verify_mydata",
                    "params": {"scope_list": ["send:public_mydata.action"]},
                },
            ),
            _msg_tool_result("check", {"status": "verified"}),
        ],
        "마이데이터 동의 상태 확인하고 필요한 공공 마이데이터 제공 동의까지 진행해줘",
        _auth_with_scope("send:public_mydata.action"),
    )

    assert msg is not None
    assert msg["tool_id"] == "mock_submit_module_public_mydata_action"
    assert "PUBLIC-MYDATA-MOCK" in msg["message"]
    assert "MYDATA-ACTION-SESSION-001" in msg["message"]


def test_submit_followup_gate_passes_after_successful_submit() -> None:
    """A prior successful submit clears the follow-up gate and blocks duplicates."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "send",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "주민등록등본"},
            },
        ),
        _msg_tool_result(
            "send",
            {
                "kind": "send",
                "result": {
                    "transaction_id": "urn:ummaya:send:test",
                    "status": "succeeded",
                    "adapter_receipt": {"receipt_id": "gov24-2026-05-07-MW-TEST"},
                },
            },
        ),
    ]

    assert _conversation_has_successful_primitive(
        msgs,
        primitive="send",
        tool_id="mock_submit_module_gov24_minwon",
    )
    assert (
        _check_submit_terminated_without_submit(
            msgs,
            "정부24에서 주민등록등본 발급 민원 신청해줘",
            _auth_with_scope("send:gov24.minwon"),
        )
        is None
    )


def test_duplicate_submit_after_success_is_rejected() -> None:
    """A second submit call must finalize from the prior receipt."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "send",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "주민등록등본"},
            },
        ),
        _msg_tool_result(
            "send",
            {
                "kind": "send",
                "result": {
                    "transaction_id": "urn:ummaya:send:test",
                    "status": "succeeded",
                    "adapter_receipt": {"receipt_id": "gov24-2026-05-07-MW-TEST"},
                },
            },
        ),
    ]

    msg = _check_duplicate_submit_prerequisite(
        "send",
        {"tool_id": "mock_submit_module_gov24_minwon", "params": {}},
        msgs,
    )

    assert msg is not None
    assert "do NOT call send again" in msg
    assert "prior successful submit tool_result" in msg


def test_gov24_submit_args_are_filled_from_citizen_query() -> None:
    """Known mock submit payload fields from the user request are restored before dispatch."""
    args = _normalize_submit_args_for_query(
        "send",
        {
            "tool_id": "mock_submit_module_gov24_minwon",
            "params": {"delegation_context": {"token": {"scope": "send:gov24.minwon"}}},
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


def test_gov24_submit_args_are_filled_for_natural_demo_request() -> None:
    """Gov24 submit calls get schema-required fields even when the model emits only auth."""
    args = _normalize_submit_args_for_query(
        "send",
        {
            "tool_id": "mock_submit_module_gov24_minwon",
            "params": {"delegation_context": {"token": {"scope": "send:gov24.minwon"}}},
        },
        "정부24에서 주민등록등본 온라인 발급 신청을 진행해줘. 접수번호가 나오면 알려줘.",
    )

    params = args["params"]
    assert isinstance(params, dict)
    assert params["minwon_type"] == "주민등록등본"
    assert params["applicant_name"] == "MOCK_APPLICANT"
    assert params["delivery_method"] == "online"
    assert params["session_id"] == "GOV24-MINWON-SESSION-001"
    assert "delegation_context" in params


def test_adapter_invocation_failed_tool_result_is_error() -> None:
    """Adapter validation failures must not be interpreted as successful tool results."""
    assert _tool_result_payload_is_error(
        {
            "kind": "send",
            "result": {
                "reason": "adapter_invocation_failed",
                "tool_id": "mock_submit_module_gov24_minwon",
                "structured": {
                    "exception_type": "ValidationError",
                    "message": "missing required fields",
                },
                "message": "Adapter raised ValidationError.",
            },
        }
    )


def test_gov24_generic_submit_tool_id_is_canonicalized() -> None:
    """The model must not burn a permission decision on primitive-name-as-tool-id."""
    args = _normalize_submit_args_for_query(
        "send",
        {
            "tool_id": "send",
            "params": {"delegation_context": {"token": {"scope": "send:gov24.minwon"}}},
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
                "find:gov24.certificate",
                "find:gov24.simplified",
                "send:gov24.minwon",
            ],
            "purpose_ko": "주민등록등본 발급 민원 신청",
            "purpose_en": "Gov24 resident registration certificate civil petition",
        },
    }

    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
            verify_args,
            "정부24에서 주민등록등본 발급 민원 신청해줘",
        )
        is None
    )
    session_context = _build_verify_session_context(
        verify_args,
        session_id="GOV24-MINWON-SESSION-001",
    )
    assert session_context["scope_list"] == ["send:gov24.minwon"]


def test_gov24_minwon_drops_query_bound_lookup_scope_prefix() -> None:
    """Gov24 minwon submit should not delegate model-invented Gov24 lookup scopes."""
    verify_args = {
        "tool_id": "mock_verify_module_simple_auth",
        "params": {
            "scope_list": [
                "find:gov24.resident_certificate",
                "send:gov24.minwon",
            ],
            "purpose_ko": "주민등록등본 발급 민원 신청",
            "purpose_en": "Gov24 resident registration certificate civil petition",
        },
    }
    normalized = _normalize_verify_args_for_query(
        "check",
        verify_args,
        "정부24에서 주민등록등본 발급 민원 신청해줘",
    )

    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
            normalized,
            "정부24에서 주민등록등본 발급 민원 신청해줘",
        )
        is None
    )
    session_context = _build_verify_session_context(
        normalized,
        session_id="GOV24-MINWON-SESSION-001",
    )
    assert session_context["scope_list"] == ["send:gov24.minwon"]


def test_submit_arg_normalization_preserves_model_payload_values() -> None:
    """Do not overwrite explicit non-empty submit params."""
    args = _normalize_submit_args_for_query(
        "send",
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
    assert msg["scope"] == "check:ganpyeon.identity"
    assert "Do NOT ask" in msg["message"]


def test_verify_query_after_prior_verify_passes() -> None:
    """Once verify ran, the terminal verify gate stays out of the way."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "check",
            {
                "tool_id": "mock_verify_ganpyeon_injeung",
                "params": {"scope_list": ["check:ganpyeon.identity"]},
            },
        ),
        _msg_tool_result("check", {"status": "verified"}),
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
        "check",
        {
            "tool_id": "mock_verify_module_modid",
            "params": {
                "scope_list": [
                    "find:admin_service_registry",
                    "find:user_permission_query",
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
    assert "check:ganpyeon.identity" in msg["message"]


def test_ganpyeon_query_rejects_any_id_sso_scope_substitution() -> None:
    """간편인증 must not drift into generic SSO/admin-service scopes."""
    msg = _check_verify_tool_choice_prerequisite(
        "check",
        {
            "tool_id": "mock_verify_module_any_id_sso",
            "params": {
                "scope_list": [
                    "find:admin_service.permission_check",
                    "send:admin_service.permission_management",
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
    assert "check:ganpyeon.identity" in msg["message"]


def test_ganpyeon_query_allows_canonical_ganpyeon_verify() -> None:
    """Canonical 간편인증 verify tool and scope pass the tool-choice gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "check",
        {
            "tool_id": "mock_verify_ganpyeon_injeung",
            "params": {
                "scope_list": ["check:ganpyeon.identity"],
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
        "check",
        {
            "tool_id": "mock_verify_mobile_id",
            "params": {
                "scope_list": ["find:identity.info", "find:identity.verify"],
                "purpose_ko": "모바일 신분증 본인확인",
                "purpose_en": "Mobile ID identity verification",
            },
        },
        "모바일 신분증으로 본인확인해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_mobile_id"
    assert msg["scope"] == "check:mobile_id.identity"
    assert "check:mobile_id.identity" in msg["message"]


def test_income_certificate_query_rejects_find_alias_identity_tool() -> None:
    """Protected certificate issuance must recover fake find aliases to check."""
    msg = _check_verify_tool_choice_prerequisite(
        "find",
        {"tool_id": "mobile_id", "params": {}},
        "소득금액증명원 오늘 바로 필요해",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_module_simple_auth"
    assert "mock_verify_module_simple_auth" in msg["message"]
    assert "Do NOT call check adapters through find" in msg["message"]


def test_mobile_id_query_allows_canonical_identity_scope() -> None:
    """Canonical Mobile ID verify scope passes the tool-choice gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "check",
        {
            "tool_id": "mock_verify_mobile_id",
            "params": {
                "scope_list": ["check:mobile_id.identity"],
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
        "check",
        {
            "tool_id": "check",
            "params": {
                "scope_list": ["check:mobile_id.identity"],
                "purpose_ko": "모바일 신분증 본인확인",
                "purpose_en": "Mobile ID identity verification",
            },
        },
        "모바일 신분증으로 본인확인해줘",
    )

    assert normalized["tool_id"] == "mock_verify_mobile_id"
    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
            normalized,
            "모바일 신분증으로 본인확인해줘",
        )
        is None
    )


def test_mobile_id_query_requests_check_before_final_answer() -> None:
    """Identity-only Mobile ID requests are recovered through the routing gate."""
    msg = _check_verify_terminated_without_verify([], "모바일 신분증으로 본인확인해줘")

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_mobile_id"
    assert "call check" in msg["message"]


def test_mobile_id_query_does_not_request_check_after_tool_call() -> None:
    """Once Mobile ID check was invoked, the terminal recovery gate stays inactive."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "check",
            {
                "tool_id": "mock_verify_mobile_id",
                "params": {"scope_list": ["check:mobile_id.identity"]},
            },
        ),
        _msg_tool_result("check", {"status": "verified"}),
    ]

    assert _check_verify_terminated_without_verify(msgs, "모바일 신분증으로 본인확인해줘") is None


def test_mobile_id_verify_missing_scope_is_filled_from_query() -> None:
    """Forced verify can recover missing identity scope fields before dispatch."""
    normalized = _normalize_verify_args_for_query(
        "check",
        {"tool_id": "mock_verify_mobile_id", "params": {}},
        "모바일 신분증으로 본인확인해줘",
    )

    assert normalized == {
        "tool_id": "mock_verify_mobile_id",
        "params": {
            "scope_list": ["check:mobile_id.identity"],
            "purpose_ko": "모바일 신분증 본인확인",
            "purpose_en": "Mobile ID identity verification",
        },
    }
    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
            normalized,
            "모바일 신분증으로 본인확인해줘",
        )
        is None
    )


def test_submit_scope_query_requests_check_before_final_answer() -> None:
    """Submit workflows may require a check turn before send can proceed."""
    msg = _check_verify_terminated_without_verify(
        [],
        "정부24에서 주민등록등본 발급 신청해줘",
    )

    assert msg is not None
    assert msg["scope"] == "send:gov24.minwon"
    assert "call check" in msg["message"]


def test_mobile_id_query_keeps_generic_verify_tool_id_on_wrong_scope() -> None:
    """Generic verify is not canonicalized when the emitted scope is wrong."""
    original: dict[str, object] = {
        "tool_id": "check",
        "params": {
            "scope_list": ["find:identity.info"],
            "purpose_ko": "모바일 신분증 본인확인",
            "purpose_en": "Mobile ID identity verification",
        },
    }
    normalized = _normalize_verify_tool_id_for_query(
        "check",
        original,
        "모바일 신분증으로 본인확인해줘",
    )

    assert normalized == original
    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
            normalized,
            "모바일 신분증으로 본인확인해줘",
        )
        is not None
    )


def test_mydata_action_query_requires_submit_scope_for_verify() -> None:
    """Public MyData action wording must bind verify to the downstream submit scope."""
    msg = _check_verify_tool_choice_prerequisite(
        "check",
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": [
                    "find:mydata.consent_status",
                    "send:mydata.provide_consent",
                ],
                "purpose_ko": "마이데이터 동의 상태 확인",
                "purpose_en": "Check MyData consent status",
            },
        },
        "마이데이터 동의 상태 확인하고 필요한 공공 마이데이터 제공 동의까지 진행해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_mydata"
    assert msg["scope"] == "send:public_mydata.action"
    assert "send:public_mydata.action" in msg["message"]
    assert "mock_verify_mydata" in msg["message"]


def test_mydata_action_rejects_lookup_to_verify_adapter() -> None:
    """Verify adapters surfaced by discovery must not be called through lookup."""
    msg = _check_verify_tool_choice_prerequisite(
        "find",
        {
            "tool_id": "mock_verify_mydata",
            "params": {},
        },
        "마이데이터 동의 상태 확인하고 필요한 공공 마이데이터 제공 동의까지 진행해줘",
    )

    assert msg is not None
    assert msg["verify_tool_id"] == "mock_verify_mydata"
    assert msg["scope"] == "send:public_mydata.action"
    assert "Check primitive prerequisite mismatch" in msg["message"]
    assert "check(tool_id='mock_verify_mydata'" in msg["message"]
    assert "find" in msg["message"]


def test_welfare_application_lookup_first_is_not_verify_primitive_mismatch() -> None:
    """Eligibility lookup remains legal before the welfare submit verify step."""
    msg = _check_verify_tool_choice_prerequisite(
        "find",
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
        "check",
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": [
                    "find:mohw.welfare_eligibility_search",
                    "find:pub.mohw.welfare_eligibility",
                    "find:mydata.welfare_eligibility_search",
                    "find:public_mydata.welfare_eligibility_search",
                    "find:mydata.welfare",
                    "send:mock.welfare_application_submit_v1",
                    "send:pub.mohw.welfare_application",
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
                    "find:mohw.welfare_eligibility_search",
                    "find:pub.mohw.welfare_eligibility",
                    "find:mydata.welfare_eligibility_search",
                    "find:public_mydata.welfare_eligibility_search",
                    "find:mydata.welfare",
                    "send:mock.welfare_application_submit_v1",
                    "send:pub.mohw.welfare_application",
                    "send:mock_welfare_application_submit_v1",
                ],
                "purpose_ko": "한부모가족 아동양육비 지원 신청",
            },
        },
        session_id="test-session",
    )

    assert session_context["scope_list"] == ["send:mydata.welfare_application"]
    assert session_context["session_id"] == "test-session"


def test_welfare_application_allows_canonical_submit_scope() -> None:
    """The canonical welfare application verify scope passes the gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "check",
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": ["send:mydata.welfare_application"],
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
                "find:hometax.simplified",
                "send:mydata.welfare_application",
            ],
            "purpose_ko": "한부모가족 아동양육비 지원 신청",
            "purpose_en": "Single-parent family child support application",
        },
    }
    normalized = _normalize_verify_args_for_query(
        "check",
        verify_args,
        "한부모가족 아동양육비 지원을 신규 신청해줘. 신청 가능한지 먼저 확인해줘.",
    )

    assert normalized["params"]["scope_list"] == ["send:mydata.welfare_application"]
    assert (
        _check_verify_tool_choice_prerequisite(
            "check",
            normalized,
            "한부모가족 아동양육비 지원을 신규 신청해줘. 신청 가능한지 먼저 확인해줘.",
        )
        is None
    )


def test_mydata_action_query_allows_submit_scope_verify() -> None:
    """The worked-example Public MyData verify scope passes the gate."""
    msg = _check_verify_tool_choice_prerequisite(
        "check",
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": ["send:public_mydata.action"],
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
    assert "kakao_keyword_search" in msg
    assert "kakao_address_search" in msg
    assert "locate(tool_id=" not in msg
    assert "do NOT invent coordinates" in msg


def test_location_gate_accepts_concrete_locate_result() -> None:
    """Concrete adapter calls exposed to the LLM still satisfy locate gates."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="다대1동 날씨"),
        _msg_assistant_tool_call("kakao_address_search", {"query": "부산 사하구 다대1동"}),
        _msg_tool_result(
            "kakao_address_search",
            {"kind": "locate", "result": {"lat": 35.059152, "lon": 128.971316}},
        ),
    ]

    assert _check_location_terminated_without_resolve(msgs, "다대1동 날씨") is None


def test_concrete_locate_ok_result_satisfies_kma_chain_gate() -> None:
    """AdapterTool ok/result payloads must still satisfy primitive chain state."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id == "kakao_address_search":
                return SimpleNamespace(
                    primitive="locate",
                    input_schema=SimpleNamespace(model_json_schema=lambda: {"properties": {}}),
                )
            if tool_id == "kma_current_observation":
                return SimpleNamespace(
                    primitive="find",
                    input_schema=SimpleNamespace(
                        model_json_schema=lambda: {
                            "properties": {"base_date": {}, "base_time": {}, "nx": {}, "ny": {}},
                            "required": ["base_date", "base_time", "nx", "ny"],
                        }
                    ),
                )
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="다대1동 날씨"),
        _msg_assistant_tool_call("kakao_address_search", {"query": "부산 사하구 다대1동"}),
        _msg_tool_result(
            "kakao_address_search",
            {
                "ok": True,
                "result": {
                    "kind": "bundle",
                    "coords": {"lat": 35.059152, "lon": 128.971316, "nx": 97, "ny": 74},
                },
            },
        ),
    ]

    assert (
        _check_chain_prerequisite(
            "find",
            {
                "tool_id": "kma_current_observation",
                "params": {
                    "base_date": "20260524",
                    "base_time": "2300",
                    "nx": 97,
                    "ny": 74,
                },
            },
            msgs,
            registry=Registry(),
            user_query="부산 사하구 다대1동 현재 날씨",
        )
        is None
    )


def test_kma_forecast_fetch_recovery_hint_names_lat_lon_not_grid() -> None:
    """lat/lon KMA adapters must not be repaired with nx/ny instructions."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id == "kakao_address_search":
                return SimpleNamespace(
                    primitive="locate",
                    input_schema=SimpleNamespace(model_json_schema=lambda: {"properties": {}}),
                )
            if tool_id == "kma_forecast_fetch":
                return SimpleNamespace(
                    primitive="find",
                    input_schema=SimpleNamespace(
                        model_json_schema=lambda: {
                            "properties": {"lat": {}, "lon": {}, "base_date": {}, "base_time": {}},
                            "required": ["lat", "lon", "base_date", "base_time"],
                        }
                    ),
                )
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 사하구 다대1동 오늘 저녁 예보"),
        _msg_assistant_tool_call("kakao_address_search", {"query": "부산 사하구 다대1동"}),
        _msg_tool_result(
            "kakao_address_search",
            {"ok": True, "result": {"lat": 35.059152, "lon": 128.971316, "nx": 97, "ny": 74}},
        ),
    ]

    err = _check_chain_prerequisite(
        "find",
        {
            "tool_id": "kma_forecast_fetch",
            "params": {"lat": 35.059152, "lon": 128.971316},
        },
        msgs,
        registry=Registry(),
        user_query="부산 사하구 다대1동 오늘 저녁 예보",
    )

    assert err is not None
    assert "WGS-84 lat/lon" in err
    assert "nx/ny" not in err


def test_effective_chat_max_tokens_clamps_interactive_default(
    monkeypatch: Any,
) -> None:
    """Interactive chat keeps a bounded generation budget unless explicitly raised."""
    monkeypatch.delenv("UMMAYA_CHAT_MAX_TOKENS", raising=False)
    assert _effective_chat_max_tokens(8192) == 4096
    assert _effective_chat_max_tokens(2048) == 2048

    monkeypatch.setenv("UMMAYA_CHAT_MAX_TOKENS", "1024")
    assert _effective_chat_max_tokens(8192) == 1024


def test_location_query_after_prior_resolve_passes() -> None:
    """A prior resolver call satisfies the terminal location gate."""
    msgs: list[Any] = [
        _msg_assistant_tool_call(
            "locate",
            {"query": "존재하지않는주소", "want": "coords_and_admcd"},
        ),
        _msg_tool_result("locate", {"kind": "error", "reason": "not_found"}),
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
        _msg_assistant_tool_call("locate", {"query": "부산"}),
        _msg_tool_result("locate", {"lat": 35.18, "lon": 129.07, "admcd": "21000"}),
        _msg_assistant_tool_call(
            "find",
            {
                "mode": "fetch",
                "tool_id": "kma_current_observation",
                "params": {"lat": 35.18, "lon": 129.07},
            },
        ),
        _msg_tool_result("find", {"t1h": 20.7, "reh": 23}),
    ]
    assert _check_resolve_terminated_without_followup(msgs, "부산 날씨") is None


def test_today_weather_forecast_only_is_rejected_until_current_observation() -> None:
    """Forecast alone must not justify current/today weather final prose."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="다대포해수욕장 오늘 날씨 알려줘"),
        _msg_assistant_tool_call(
            "locate",
            {"tool_id": "kakao_keyword_search", "params": {"query": "다대포해수욕장"}},
        ),
        _msg_tool_result(
            "locate",
            {"result": {"lat": 37.498086, "lon": 127.028001, "nx": 62, "ny": 126}},
        ),
        _msg_assistant_tool_call(
            "find",
            {
                "tool_id": "kma_forecast_fetch",
                "params": {
                    "lat": 37.498086,
                    "lon": 127.028001,
                    "base_date": "20260513",
                    "base_time": "0200",
                },
            },
        ),
        _msg_tool_result("find", {"result": {"kind": "timeseries", "points": []}}),
    ]

    msg = _check_current_weather_terminated_without_observation(
        msgs,
        "다대포해수욕장 오늘 날씨 알려줘",
    )

    assert msg is not None
    assert "kma_current_observation" in msg
    assert "find(tool_id=" not in msg
    assert "Do NOT claim" in msg

    msgs.append(
        _msg_assistant_tool_call(
            "find",
            {
                "tool_id": "kma_current_observation",
                "params": {"base_date": "20260513", "base_time": "0200", "nx": 62, "ny": 126},
            },
        )
    )
    assert (
        _check_current_weather_terminated_without_observation(
            msgs,
            "다대포해수욕장 오늘 날씨 알려줘",
        )
        is None
    )


def test_explicit_ultra_short_forecast_can_finish_without_current_observation() -> None:
    """Forecast-intent prompt should not demand kma_current_observation."""
    msgs: list[Any] = [
        LLMChatMessage(
            role="user",
            content=(
                "kma_ultra_short_term_forecast 도구로 서울 종로구 현재 초단기예보를 조회해서 "
                "15시와 16시 날씨를 요약해줘"
            ),
        ),
        _msg_assistant_tool_call(
            "locate",
            {"tool_id": "kakao_address_search", "params": {"query": "서울 종로구"}},
        ),
        _msg_tool_result(
            "locate",
            {"result": {"lat": 37.5735, "lon": 126.9788, "nx": 61, "ny": 128}},
        ),
        _msg_assistant_tool_call(
            "find",
            {
                "tool_id": "kma_ultra_short_term_forecast",
                "params": {
                    "base_date": "20260518",
                    "base_time": "1500",
                    "nx": 61,
                    "ny": 128,
                },
            },
        ),
        _msg_tool_result(
            "find",
            {
                "result": {
                    "kind": "collection",
                    "items": [
                        {
                            "base_date": "20260518",
                            "base_time": "1530",
                            "fcst_date": "20260518",
                            "fcst_time": "1600",
                            "category": "T1H",
                            "fcst_value": "29",
                        }
                    ],
                }
            },
        ),
    ]

    assert (
        _check_current_weather_terminated_without_observation(
            msgs,
            "kma_ultra_short_term_forecast 도구로 서울 종로구 현재 초단기예보를 조회해서 "
            "15시와 16시 날씨를 요약해줘",
        )
        is None
    )


def test_resolve_only_then_terminate_is_rejected() -> None:
    """G-class regression: resolve called but no follow-up lookup → reject."""
    msgs: list[Any] = [
        _msg_available_adapters(find=True),
        LLMChatMessage(role="user", content="지금 부산 사하구 다대1동 날씨 어때"),
        _msg_assistant_tool_call(
            "locate",
            {"query": "부산 사하구 다대1동", "want": "coords_and_admcd"},
        ),
        _msg_tool_result("locate", {"lat": 35.05915, "lon": 128.97132}),
        _msg_assistant_tool_call(
            "locate",
            {"query": "부산 사하구 다대1동", "want": "all"},
        ),
        _msg_tool_result("locate", {"lat": 35.05915, "lon": 128.97132}),
    ]
    msg = _check_resolve_terminated_without_followup(msgs, "지금 부산 사하구 다대1동 날씨 어때")
    assert msg is not None
    assert "Chain incomplete" in msg
    assert "find" in msg.lower()
    assert "fabrication" in msg.lower()


def test_resolve_only_with_non_observable_query_passes() -> None:
    """When retrieval returns only locate candidates, the gate stays out of the way."""
    msgs: list[Any] = [
        _msg_available_adapters(find=False),
        LLMChatMessage(role="user", content="부산 사하구 다대1동 주소"),
        _msg_assistant_tool_call("locate", {"query": "부산 사하구 다대1동"}),
        _msg_tool_result("locate", {"lat": 35.05915, "lon": 128.97132}),
    ]
    assert _check_resolve_terminated_without_followup(msgs, "부산 사하구 다대1동 주소") is None


def test_no_resolve_call_no_gate() -> None:
    """No resolve_location → gate doesn't fire even on observable queries."""
    msgs: list[Any] = [
        _msg_available_adapters(find=True),
        LLMChatMessage(role="user", content="동아대학교 응급실"),
    ]
    assert _check_resolve_terminated_without_followup(msgs, "동아대학교 응급실") is None


def test_lookup_without_fetch_mode_still_counts() -> None:
    """K-EXAONE often omits ``mode`` when ``tool_id`` is set — that variant
    still satisfies the chain because the dispatcher treats it as fetch.
    """
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 날씨"),
        _msg_assistant_tool_call("locate", {"query": "부산"}),
        _msg_tool_result("locate", {"lat": 35.18, "lon": 129.07}),
        _msg_assistant_tool_call(
            "find",
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
        "find",
        {
            "mode": "fetch",
            "tool_id": "kma_current_observation",
            "params": {"lat": 35.18, "lon": 129.07},
        },
        msgs,
        registry=None,
    )
    assert err is not None
    assert "kakao_keyword_search" in err
    assert "find(tool_id=" not in err
    assert "locate(tool_id=" not in err


def test_explicit_find_tool_id_mismatch_is_rejected() -> None:
    """A citizen-specified adapter id must not be silently substituted."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id == "kma_ultra_short_term_forecast":
                return SimpleNamespace(primitive="find")
            if tool_id == "kma_forecast_fetch":
                return SimpleNamespace(primitive="find")
            raise KeyError(tool_id)

    err = _check_chain_prerequisite(
        "find",
        {
            "tool_id": "kma_forecast_fetch",
            "params": {"lat": 37.5747, "lon": 126.9796, "base_date": "20260518"},
        },
        [],
        registry=Registry(),
        user_query="반드시 kma_ultra_short_term_forecast tool_id로 호출해.",
    )

    assert err is not None
    assert "kma_ultra_short_term_forecast" in err
    assert "kma_forecast_fetch" in err


def test_nmc_prerequisite_message_names_region_mode() -> None:
    """NMC recovery must point at locate adapter + region mode, not coords-only retry."""
    msgs: list[Any] = [LLMChatMessage(role="user", content="하단역 근처 응급실")]

    err = _check_chain_prerequisite(
        "find",
        {
            "mode": "fetch",
            "tool_id": "nmc_emergency_search",
            "params": {"mode": "coordinate", "lat": 35.1062, "lon": 128.9668, "limit": 5},
        },
        msgs,
        registry=None,
    )

    assert err is not None
    assert "kakao_coord_to_region" in err
    assert "find(tool_id=" not in err
    assert "locate(tool_id=" not in err
    assert "mode:'region'" in err
    assert "q0:region.region_1depth_name" in err


def test_nmc_coordinate_mode_after_resolve_is_rejected() -> None:
    """A prior coords-only resolve is not enough for NMC citizen ER search."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="하단역 근처 응급실"),
        _msg_assistant_tool_call("locate", {"query": "하단역", "want": "coords"}),
        _msg_tool_result("locate", {"lat": 35.1062, "lon": 128.9668}),
    ]

    err = _check_chain_prerequisite(
        "find",
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


def test_nmc_lookup_args_are_derived_from_prior_default_locate_result() -> None:
    """A default locate bundle with adm_cd is enough to build NMC region params."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="동아대 승학캠퍼스 근처 야간 응급실"),
        _msg_assistant_tool_call("locate", {"query": "동아대학교"}),
        _msg_tool_result(
            "locate",
            {
                "kind": "locate",
                "result": {
                    "kind": "bundle",
                    "coords": {"kind": "coords", "lat": 35.115446, "lon": 128.967669},
                    "adm_cd": {
                        "kind": "adm_cd",
                        "code": "2638010300",
                        "name": "부산광역시 사하구 하단동",
                        "level": "eupmyeondong",
                    },
                },
            },
        ),
    ]
    args = {
        "mode": "fetch",
        "tool_id": "nmc_emergency_search",
        "params": {},
    }

    normalized = _normalize_nmc_lookup_args_from_prior_locate("find", args, msgs)

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "사하구",
        "origin_lat": 35.115446,
        "origin_lon": 128.967669,
        "limit": 5,
    }
    assert (
        _check_chain_prerequisite(
            "find",
            normalized,
            msgs,
            registry=None,
        )
        is None
    )


def test_nmc_lookup_args_expand_abbreviated_sido_from_prior_locate_result() -> None:
    """Kakao may echo abbreviated Korean sido text from an address query."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="하단역 근처 야간 응급실"),
        _msg_assistant_tool_call("locate", {"query": "하단역"}),
        _msg_tool_result(
            "locate",
            {
                "kind": "locate",
                "result": {
                    "kind": "bundle",
                    "coords": {
                        "kind": "coords",
                        "lat": 35.1148094646099,
                        "lon": 128.952594462616,
                    },
                    "adm_cd": {
                        "kind": "adm_cd",
                        "code": "2638010500",
                        "name": "부산 사하구 하단동",
                        "level": "eupmyeondong",
                    },
                },
            },
        ),
    ]
    args = {
        "mode": "fetch",
        "tool_id": "nmc_emergency_search",
        "params": {"mode": "coordinate", "lat": 35, "lon": 128},
    }

    normalized = _normalize_nmc_lookup_args_from_prior_locate("find", args, msgs)

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "사하구",
        "origin_lat": 35.1148094646099,
        "origin_lon": 128.952594462616,
        "limit": 5,
    }
    assert (
        _check_chain_prerequisite(
            "find",
            normalized,
            msgs,
            registry=None,
        )
        is None
    )


def test_nmc_lookup_args_are_derived_from_prior_concrete_locate_result() -> None:
    """TUI stores concrete Kakao adapter calls, so NMC recovery needs registry context."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id in {"kakao_address_search", "nmc_emergency_search"}:
                primitive = "locate" if tool_id.startswith("kakao_") else "find"
                return SimpleNamespace(primitive=primitive)
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="하단역 근처 야간 응급실"),
        _msg_assistant_tool_call("kakao_address_search", {"query": "부산 사하구 하단동"}),
        _msg_tool_result(
            "kakao_address_search",
            {
                "ok": True,
                "result": {
                    "kind": "bundle",
                    "coords": {
                        "kind": "coords",
                        "lat": 35.1148094646099,
                        "lon": 128.952594462616,
                    },
                    "adm_cd": {
                        "kind": "adm_cd",
                        "code": "2638010500",
                        "name": "부산 사하구 하단동",
                        "level": "eupmyeondong",
                    },
                },
            },
        ),
    ]
    args = {
        "tool_id": "nmc_emergency_search",
        "params": {"mode": "coordinate", "lat": 35, "origin_lat": 35, "origin_lon": 128},
    }

    normalized = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        args,
        msgs,
        registry=Registry(),
    )

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "사하구",
        "origin_lat": 35.1148094646099,
        "origin_lon": 128.952594462616,
        "limit": 5,
    }


def test_reverse_geocode_args_reuse_exact_prior_locate_coords_when_model_rounds() -> None:
    """A rounded reverse-geocode retry must copy exact decimals from prior locate output."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 사하구 다대1동 근처 야간 응급실"),
        _msg_assistant_tool_call("kakao_address_search", {"query": "부산 사하구 다대1동"}),
        _msg_tool_result(
            "locate",
            {
                "kind": "locate",
                "result": {
                    "kind": "bundle",
                    "coords": {
                        "kind": "coords",
                        "lat": 35.0591517638253,
                        "lon": 128.971316010861,
                    },
                    "address": {
                        "kind": "address",
                        "jibun_address": "부산 사하구 다대1동",
                    },
                },
            },
        ),
    ]
    args = {
        "tool_id": "kakao_coord_to_region",
        "params": {"lat": 35, "lon": 129},
    }

    normalized = _normalize_reverse_geocode_args_from_prior_locate("locate", args, msgs)

    assert normalized["params"] == {
        "lat": 35.0591517638253,
        "lon": 128.971316010861,
    }


def test_reverse_geocode_args_reuse_exact_prior_concrete_locate_coords() -> None:
    """TUI history stores concrete adapter names, not only root primitive names."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id in {"kakao_address_search", "kakao_coord_to_region"}:
                return SimpleNamespace(primitive="locate")
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 사하구 다대1동 근처 야간 응급실"),
        _msg_assistant_tool_call("kakao_address_search", {"query": "부산 사하구 다대1동"}),
        _msg_tool_result(
            "kakao_address_search",
            {
                "ok": True,
                "result": {
                    "kind": "bundle",
                    "coords": {
                        "kind": "coords",
                        "lat": 35.0591517638253,
                        "lon": 128.971316010861,
                    },
                },
            },
        ),
    ]
    args = {
        "tool_id": "kakao_coord_to_region",
        "params": {"lat": 35, "lon": 128},
    }

    normalized = _normalize_reverse_geocode_args_from_prior_locate(
        "locate",
        args,
        msgs,
        registry=Registry(),
    )

    assert normalized["params"] == {
        "lat": 35.0591517638253,
        "lon": 128.971316010861,
    }


def test_reverse_geocode_direct_call_reuses_exact_prior_concrete_locate_coords() -> None:
    """Concrete reverse-geocode calls must also repair rounded lat/lon arguments."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id in {"kakao_address_search", "kakao_coord_to_region"}:
                return SimpleNamespace(primitive="locate")
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산 사하구 다대1동 근처 야간 응급실"),
        _msg_assistant_tool_call("kakao_address_search", {"query": "부산 사하구 다대1동"}),
        _msg_tool_result(
            "kakao_address_search",
            {
                "ok": True,
                "result": {
                    "kind": "bundle",
                    "coords": {
                        "kind": "coords",
                        "lat": 35.0591517638253,
                        "lon": 128.971316010861,
                    },
                },
            },
        ),
    ]

    normalized = _normalize_reverse_geocode_args_from_prior_locate(
        "kakao_coord_to_region",
        {"lat": 35, "lon": 128},
        msgs,
        registry=Registry(),
    )

    assert normalized == {
        "lat": 35.0591517638253,
        "lon": 128.971316010861,
    }


def test_hira_lookup_args_are_derived_from_prior_concrete_locate_result() -> None:
    """HIRA needs exact xPos/yPos, but the model often calls it with empty params."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id == "kakao_keyword_search":
                return SimpleNamespace(primitive="locate")
            if tool_id == "hira_hospital_search":
                return SimpleNamespace(primitive="find")
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="다대포해수욕장 근처 오늘 진료하는 소아청소년과"),
        _msg_assistant_tool_call("kakao_keyword_search", {"query": "다대포해수욕장"}),
        _msg_tool_result(
            "kakao_keyword_search",
            {
                "ok": True,
                "result": {
                    "kind": "poi",
                    "name": "다대포해수욕장",
                    "lat": 35.0483022960665,
                    "lon": 128.966674959454,
                    "address_name": "부산 사하구 다대동",
                },
            },
        ),
    ]

    normalized = _normalize_hira_lookup_args_from_prior_locate(
        "find",
        {"tool_id": "hira_hospital_search", "params": {}},
        msgs,
        "다대포해수욕장 근처 오늘 진료하는 소아청소년과 찾아줘",
        registry=Registry(),
    )

    assert normalized["params"] == {
        "xPos": 128.966674959454,
        "yPos": 35.0483022960665,
        "radius": 2000,
        "dgsbjt": "소아청소년과",
    }
    assert (
        _check_chain_prerequisite(
            "find",
            normalized,
            msgs,
            registry=Registry(),
        )
        is None
    )


def test_cached_locate_result_normalizes_inbound_concrete_hira_call() -> None:
    """TUI-side concrete tool execution bypasses chat_request normalization."""
    normalized = _normalize_lookup_args_from_cached_locate_result(
        "find",
        {"tool_id": "hira_hospital_search", "params": {"xPos": 128, "yPos": 35}},
        {
            "kind": "poi",
            "lat": 35.0465263488422,
            "lon": 128.962741189119,
        },
    )

    assert normalized["params"] == {
        "xPos": 128.962741189119,
        "yPos": 35.0465263488422,
        "radius": 2000,
    }


def test_cached_locate_result_normalizes_inbound_concrete_nmc_call() -> None:
    """Concrete NMC tool execution also needs cached locate-derived region params."""
    normalized = _normalize_lookup_args_from_cached_locate_result(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "coordinate",
                "lat": 35,
                "origin_lat": 35,
                "origin_lon": 129,
                "qn": "응급실",
            },
        },
        {
            "kind": "poi",
            "name": "하단역 부산1호선",
            "lat": 35.1062385683347,
            "lon": 128.966786546793,
            "address_name": "부산 사하구 하단동 491",
        },
    )

    assert normalized["params"] == {
        "mode": "region",
        "origin_lat": 35.1062385683347,
        "origin_lon": 128.966786546793,
        "q0": "부산광역시",
        "q1": "사하구",
        "limit": 5,
    }


def test_cached_locate_result_normalizes_inbound_nmc_after_reverse_geocode() -> None:
    """Inbound dispatch must preserve the original POI origin after region lookup."""
    normalized = _normalize_lookup_args_from_cached_locate_result(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "region",
                "q0": "부산광역시",
                "q1": "동구",
                "limit": 5,
            },
        },
        {
            "kind": "region",
            "region_1depth_name": "부산광역시",
            "region_2depth_name": "동구",
            "x": 129.03358644975884,
            "y": 35.12133551971654,
        },
        coordinate_locate_result={
            "kind": "poi",
            "name": "부산역",
            "lat": 35.11520340622514,
            "lon": 129.04154985192403,
            "address_name": "부산 동구 초량동 1187-1",
        },
    )

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "동구",
        "origin_lat": 35.11520340622514,
        "origin_lon": 129.04154985192403,
        "limit": 5,
    }


def test_cached_locate_result_normalizes_inbound_aed_after_reverse_geocode() -> None:
    """AED dispatch should get origin coords for official-coordinate distance sorting."""
    normalized = _normalize_lookup_args_from_cached_locate_result(
        "find",
        {
            "tool_id": "nmc_aed_site_locate",
            "params": {
                "q0": "부산광역시",
                "q1": "동구",
                "page_no": 1,
                "num_of_rows": 10,
            },
        },
        {
            "kind": "region",
            "region_1depth_name": "부산광역시",
            "region_2depth_name": "동구",
            "x": 129.03358644975884,
            "y": 35.12133551971654,
        },
        coordinate_locate_result={
            "kind": "poi",
            "name": "부산역",
            "lat": 35.11520340622514,
            "lon": 129.04154985192403,
            "address_name": "부산 동구 초량동 1187-1",
        },
    )

    assert normalized["params"] == {
        "q0": "부산광역시",
        "q1": "동구",
        "page_no": 1,
        "num_of_rows": 10,
        "origin_lat": 35.11520340622514,
        "origin_lon": 129.04154985192403,
    }


def test_cached_locate_result_normalizes_inbound_concrete_reverse_geocode_call() -> None:
    """TUI Tool.call dispatch must repair rounded reverse-geocode coordinates."""
    normalized = _normalize_lookup_args_from_cached_locate_result(
        "locate",
        {"tool_id": "kakao_coord_to_region", "params": {"lat": 35, "lon": 129}},
        {
            "kind": "poi",
            "name": "부산역",
            "lat": 35.11520340622514,
            "lon": 129.04154985192403,
        },
    )

    assert normalized["params"] == {
        "lat": 35.11520340622514,
        "lon": 129.04154985192403,
    }


def test_koroad_lookup_args_are_derived_from_prior_concrete_locate_result() -> None:
    """Traffic-risk searches need the locate adm_cd copied into KOROAD params."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id == "kakao_address_search":
                return SimpleNamespace(primitive="locate")
            if tool_id == "koroad_accident_hazard_search":
                return SimpleNamespace(primitive="find")
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="강남역 주변 어린이보호구역 사고 위험 구간"),
        _msg_assistant_tool_call("kakao_address_search", {"query": "서울 강남구 역삼동"}),
        _msg_tool_result(
            "kakao_address_search",
            {
                "ok": True,
                "result": {
                    "kind": "bundle",
                    "coords": {
                        "kind": "coords",
                        "lat": 37.498095,
                        "lon": 127.02761,
                    },
                    "adm_cd": {
                        "kind": "adm_cd",
                        "code": "1168010100",
                        "name": "서울 강남구 역삼동",
                        "level": "eupmyeondong",
                    },
                },
            },
        ),
    ]

    normalized = _normalize_koroad_lookup_args_from_prior_locate(
        "find",
        {"tool_id": "koroad_accident_hazard_search", "params": {}},
        msgs,
        registry=Registry(),
    )

    assert normalized["params"] == {
        "adm_cd": "1168010100",
        "year": 2024,
    }
    assert (
        _check_chain_prerequisite(
            "find",
            normalized,
            msgs,
            registry=Registry(),
        )
        is None
    )


def test_nmc_lookup_args_keep_region_and_default_limit() -> None:
    """The normalizer only fills the missing limit when q0/q1 are already present."""
    normalized = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {"mode": "region", "q0": "부산광역시", "q1": "사하구"},
        },
        [],
    )

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "사하구",
        "limit": 5,
    }


def test_nmc_lookup_args_repair_rounded_origin_when_region_is_present() -> None:
    """Region-mode NMC params still need exact locate-derived origin coords."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id == "kakao_keyword_search":
                return SimpleNamespace(primitive="locate")
            if tool_id == "nmc_emergency_search":
                return SimpleNamespace(primitive="find")
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"),
        _msg_assistant_tool_call("kakao_keyword_search", {"query": "부산역"}),
        _msg_tool_result(
            "kakao_keyword_search",
            {
                "ok": True,
                "result": {
                    "kind": "poi",
                    "name": "부산역",
                    "lat": 35.11520340622514,
                    "lon": 129.04154985192403,
                    "address_name": "부산 동구 초량동 1187-1",
                },
            },
        ),
    ]

    normalized = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "region",
                "q0": "부산광역시",
                "q1": "동구",
                "origin_lat": 35,
                "origin_lon": 129,
                "limit": 5,
            },
        },
        msgs,
        registry=Registry(),
    )

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "동구",
        "origin_lat": 35.11520340622514,
        "origin_lon": 129.04154985192403,
        "limit": 5,
    }


def test_nmc_lookup_args_repair_rounded_origin_after_reverse_geocode() -> None:
    """Latest region result supplies q0/q1; earlier POI still supplies origin coords."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id in {"kakao_keyword_search", "kakao_coord_to_region"}:
                return SimpleNamespace(primitive="locate")
            if tool_id == "nmc_emergency_search":
                return SimpleNamespace(primitive="find")
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"),
        _msg_assistant_tool_call("kakao_keyword_search", {"query": "부산역"}),
        _msg_tool_result(
            "kakao_keyword_search",
            {
                "ok": True,
                "result": {
                    "kind": "poi",
                    "name": "부산역",
                    "lat": 35.11520340622514,
                    "lon": 129.04154985192403,
                    "address_name": "부산 동구 초량동 1187-1",
                },
            },
        ),
        _msg_assistant_tool_call("kakao_coord_to_region", {"lat": 35, "lon": 129}),
        _msg_tool_result(
            "kakao_coord_to_region",
            {
                "ok": True,
                "result": {
                    "kind": "region",
                    "region_1depth_name": "부산광역시",
                    "region_2depth_name": "동구",
                    "x": 129.03358644975884,
                    "y": 35.12133551971654,
                },
            },
        ),
    ]

    normalized = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "region",
                "q0": "부산광역시",
                "q1": "동구",
                "origin_lat": 35,
                "origin_lon": 129,
                "limit": 10,
            },
        },
        msgs,
        registry=Registry(),
    )

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "동구",
        "origin_lat": 35.11520340622514,
        "origin_lon": 129.04154985192403,
        "limit": 10,
    }


def test_nmc_lookup_args_fill_missing_origin_after_reverse_geocode() -> None:
    """Region-mode NMC calls should keep distance sorting when origin coords exist."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id in {"kakao_keyword_search", "kakao_coord_to_region"}:
                return SimpleNamespace(primitive="locate")
            if tool_id == "nmc_emergency_search":
                return SimpleNamespace(primitive="find")
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"),
        _msg_assistant_tool_call("kakao_keyword_search", {"query": "부산역"}),
        _msg_tool_result(
            "kakao_keyword_search",
            {
                "ok": True,
                "result": {
                    "kind": "poi",
                    "name": "부산역",
                    "lat": 35.11520340622514,
                    "lon": 129.04154985192403,
                    "address_name": "부산 동구 초량동 1187-1",
                },
            },
        ),
        _msg_assistant_tool_call("kakao_coord_to_region", {"lat": 35, "lon": 129}),
        _msg_tool_result(
            "kakao_coord_to_region",
            {
                "ok": True,
                "result": {
                    "kind": "region",
                    "region_1depth_name": "부산광역시",
                    "region_2depth_name": "동구",
                    "x": 129.03358644975884,
                    "y": 35.12133551971654,
                },
            },
        ),
    ]

    normalized = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "region",
                "q0": "부산광역시",
                "q1": "동구",
                "limit": 10,
            },
        },
        msgs,
        registry=Registry(),
    )

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "동구",
        "origin_lat": 35.11520340622514,
        "origin_lon": 129.04154985192403,
        "limit": 10,
    }


def test_nmc_lookup_args_drop_generic_qn_filter() -> None:
    """NMC QN is an institution-name filter, not the emergency-room intent."""
    normalized = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "region",
                "q0": "부산광역시",
                "q1": "사하구",
                "qn": "응급실",
                "limit": 5,
            },
        },
        [],
    )

    assert normalized["params"] == {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "사하구",
        "limit": 5,
    }


def test_nmc_lookup_args_drop_blank_and_keyword_list_qn_filters() -> None:
    """K-EXAONE may emit blank or comma-list QN values; both are not institution names."""
    blank = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "region",
                "q0": "부산광역시",
                "q1": "사하구",
                "qn": "",
                "limit": 5,
            },
        },
        [],
    )
    keyword_list = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        {
            "tool_id": "nmc_emergency_search",
            "params": {
                "mode": "region",
                "q0": "부산광역시",
                "q1": "사하구",
                "qn": "응급실,24시간,야간,병원",
                "limit": 5,
            },
        },
        [],
    )

    expected = {
        "mode": "region",
        "q0": "부산광역시",
        "q1": "사하구",
        "limit": 5,
    }
    assert blank["params"] == expected
    assert keyword_list["params"] == expected


def test_nmc_lookup_args_normalize_first_poi_to_region_search() -> None:
    """The first Hadan live failure rounded a POI result into coordinate mode."""

    class Registry:
        def find(self, tool_id: str) -> object:
            if tool_id == "kakao_keyword_search":
                return SimpleNamespace(primitive="locate")
            if tool_id == "nmc_emergency_search":
                return SimpleNamespace(primitive="find")
            raise KeyError(tool_id)

    msgs: list[Any] = [
        LLMChatMessage(role="user", content="하단역 근처 야간 응급실"),
        _msg_assistant_tool_call("kakao_keyword_search", {"query": "하단역"}),
        _msg_tool_result(
            "kakao_keyword_search",
            {
                "ok": True,
                "result": {
                    "kind": "poi",
                    "name": "하단역 부산1호선",
                    "lat": 35.1062385683347,
                    "lon": 128.966786546793,
                    "address_name": "부산 사하구 하단동 491",
                },
            },
        ),
    ]
    args = {
        "tool_id": "nmc_emergency_search",
        "params": {
            "mode": "coordinate",
            "lat": 35,
            "origin_lat": 35,
            "origin_lon": 128,
            "q0": "",
            "q1": "",
            "qn": "",
        },
    }

    normalized = _normalize_nmc_lookup_args_from_prior_locate(
        "find",
        args,
        msgs,
        registry=Registry(),
    )

    assert normalized["params"] == {
        "mode": "region",
        "origin_lat": 35.1062385683347,
        "origin_lon": 128.966786546793,
        "q0": "부산광역시",
        "q1": "사하구",
        "limit": 5,
    }


def test_nmc_region_mode_after_resolve_is_allowed() -> None:
    """Region-mode NMC lookup may proceed after resolve_location."""
    msgs: list[Any] = [
        LLMChatMessage(role="user", content="하단역 근처 응급실"),
        _msg_assistant_tool_call("locate", {"query": "하단역", "want": "all"}),
        _msg_tool_result(
            "locate",
            {
                "coords": {"lat": 35.1062, "lon": 128.9668},
                "region": {"region_1depth_name": "부산광역시", "region_2depth_name": "사하구"},
            },
        ),
    ]

    err = _check_chain_prerequisite(
        "find",
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
