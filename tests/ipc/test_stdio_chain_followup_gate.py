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
from typing import Any

from kosmos.ipc.stdio import (
    _check_chain_prerequisite,
    _check_resolve_terminated_without_followup,
    _query_implies_followup_lookup,
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
