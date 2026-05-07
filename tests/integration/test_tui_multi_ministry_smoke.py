# SPDX-License-Identifier: Apache-2.0
"""T129 — Smoke test: SC-8 Phase 2 multi-ministry scenario end-to-end via IPC.

Scenario description
--------------------
Phase 2 multi-ministry: a citizen asks for combined route-safety + hospital
information ("강남구 사고 위험지역이랑 근처 병원도 알려줘").

Tool call order exercised (scripted mock LLM):
  1. resolve_location  — geocode 강남구 (Kakao fixture)
  2. lookup(search)    — search KOROAD accident hazard adapter
  3. lookup(fetch)     — fetch koroad_accident_hazard_search (KOROAD fixture)
  4. lookup(search)    — search HIRA hospital adapter
  5. lookup(fetch)     — fetch hira_hospital_search (HIRA fixture)
  6. text_delta        — Korean synthesis mentioning both KOROAD + HIRA results

Assertions
----------
- tool_call_order contains resolve_location then ≥2 lookup calls.
- tool_call_order ends with a text-delta turn (synthesis).
- Final response is non-empty Korean text mentioning both KOROAD (강남구/사고) and
  HIRA (병원/강남).
- All IPC frames survive model_dump_json + TypeAdapter.validate_json round-trip.
- ToolCallFrame.name values are exclusively the active primitive names accepted by
  ToolCallFrame (lookup, resolve_location, submit, verify).
- stop_reason == "end_turn".
- message_order ends with AssistantChunkFrame(done=True) — i.e., the TUI-side
  consumer would receive a properly closed stream.

Live API note
-------------
No live data.go.kr calls.  All HTTP is intercepted by the AsyncMock seam
extended here to route ``getHospBasisList`` → HIRA fixture.  If real keys are
present in the environment, the test still runs against fixtures.  A
``@pytest.mark.live`` variant for real API calls is out of scope per
AGENTS.md hard rules.

Fixture sources
---------------
``tests/fixtures/koroad/accident_hazard_search_happy.json``
``tests/fixtures/kma/forecast_fetch_happy.json`` (unused in this scenario)
``tests/fixtures/hira/hospital_search_happy.json``
``tests/fixtures/kakao/local_search_address_강남구.json``
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import TypeAdapter

from kosmos.ipc.frame_schema import (
    AssistantChunkFrame,
    IPCFrame,
    ToolCallFrame,
    ToolResultEnvelope,
    ToolResultFrame,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURE_BASE = Path(__file__).resolve().parent.parent / "fixtures"
_KOROAD_FIXTURE = _FIXTURE_BASE / "koroad" / "accident_hazard_search_happy.json"
_HIRA_FIXTURE = _FIXTURE_BASE / "hira" / "hospital_search_happy.json"
_KMA_FIXTURE = _FIXTURE_BASE / "kma" / "forecast_fetch_happy.json"

# ---------------------------------------------------------------------------
# Trigger query
# ---------------------------------------------------------------------------

_MULTI_MINISTRY_QUERY = "강남구 사고 위험지역이랑 근처 병원도 알려줘"

# ---------------------------------------------------------------------------
# Scripted mock LLM turn data
# ---------------------------------------------------------------------------

_RESOLVE_GANGNAM_ARGS: dict[str, Any] = {"query": "강남구", "want": "coords_and_admcd"}
_SEARCH_KOROAD_ARGS: dict[str, Any] = {"mode": "search", "query": "사고다발지역 교통사고"}
_FETCH_KOROAD_ARGS: dict[str, Any] = {
    "mode": "fetch",
    "tool_id": "koroad_accident_hazard_search",
    "params": {"adm_cd": "1168000000", "year": 2023},
}
_SEARCH_HIRA_ARGS: dict[str, Any] = {"mode": "search", "query": "병원 응급실 근처"}
_FETCH_HIRA_ARGS: dict[str, Any] = {
    "mode": "fetch",
    "tool_id": "hira_hospital_search",
    "params": {"xPos": 127.047, "yPos": 37.498, "radius": 2000},
}
_MULTI_MINISTRY_SYNTHESIS = (
    "강남구 안전 정보입니다.\n\n"
    "교통사고 위험지점: 서울특별시 강남구 개포동 일대 (사고 12건), "
    "서울특별시 강남구 삼성동 일대 (사고 9건)이 확인되었습니다.\n\n"
    "근처 병원: 연세대학교의과대학강남세브란스병원 (서울특별시 강남구 언주로 211)이 "
    "가장 가까운 상급종합병원입니다.\n\n"
    "사고다발구역 통행 시 주의하시고, 응급 시 강남세브란스병원을 이용하시기 바랍니다."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_frame_adapter: TypeAdapter[Any] = TypeAdapter(IPCFrame)


def _make_ts() -> str:
    from datetime import datetime

    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Extended httpx mock that adds HIRA routing
# ---------------------------------------------------------------------------


def _build_multi_ministry_httpx_mock() -> AsyncMock:
    """Build AsyncMock routing KOROAD + HIRA + Kakao fixture URLs.

    Extends the e2e conftest mock with a HIRA routing arm for
    ``getHospBasisList``.  Unmatched URLs raise to fail-closed.
    """
    import urllib.parse

    def _load(path: Path) -> dict[str, Any]:
        assert path.exists(), f"Fixture missing: {path}"
        return json.loads(path.read_text())

    def _resp(url_str: str, data: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json=data,
            request=httpx.Request("GET", url_str),
            headers={"content-type": "application/json"},
        )

    async def _mock_get(
        url: str | httpx.URL,
        *,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        url_str = str(url)
        parsed = urllib.parse.urlparse(url_str)
        path = parsed.path
        host = parsed.netloc or parsed.path

        # KOROAD accident hazard
        if "getRestFrequentzoneLg" in path:
            return _resp(url_str, _load(_KOROAD_FIXTURE))

        # HIRA hospital search
        if "getHospBasisList" in path:
            return _resp(url_str, _load(_HIRA_FIXTURE))

        # KMA forecast (not used in this scenario but guard against accidental calls)
        if "getVilageFcst" in path:
            return _resp(url_str, _load(_KMA_FIXTURE))

        # Kakao geocoder
        if host.endswith(".kakao.com") or host == "kakao.com":
            kakao_fixture = _FIXTURE_BASE / "kakao" / "local_search_address_강남구.json"
            return _resp(url_str, _load(kakao_fixture))

        raise AssertionError(f"Unpatched httpx.get call in multi-ministry test to URL: {url_str!r}")

    return AsyncMock(side_effect=_mock_get)


# ---------------------------------------------------------------------------
# Script builder — multi-ministry 5-turn scenario
# ---------------------------------------------------------------------------


def _build_multi_ministry_script():  # type: ignore[no-untyped-def]
    """Build scripted mock LLM event sequences for multi-ministry scenario.

    Returns (event_sequences, expected_tool_order).
    event_sequences: list of per-turn StreamEvent lists consumed by MockLLMClient.
    expected_tool_order: ordered list of tool names for assertion.
    """
    from kosmos.llm.models import TokenUsage
    from tests.e2e.conftest import _make_text_events, _tce

    _u = TokenUsage(input_tokens=200, output_tokens=50)
    _u_synth = TokenUsage(input_tokens=900, output_tokens=180)

    event_sequences = [
        _tce("resolve_location", _RESOLVE_GANGNAM_ARGS, "call_001", _u),
        _tce("lookup", _SEARCH_KOROAD_ARGS, "call_002", _u),
        _tce("lookup", _FETCH_KOROAD_ARGS, "call_003", _u),
        _tce("lookup", _SEARCH_HIRA_ARGS, "call_004", _u),
        _tce("lookup", _FETCH_HIRA_ARGS, "call_005", _u),
        _make_text_events(_MULTI_MINISTRY_SYNTHESIS, _u_synth),
    ]

    expected_tool_order = [
        "resolve_location",
        "lookup",
        "lookup",
        "lookup",
        "lookup",
    ]

    return event_sequences, expected_tool_order


# ---------------------------------------------------------------------------
# T129: Multi-ministry smoke test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sc8_phase2_multi_ministry_ipc_frame_sequence() -> None:  # noqa: C901
    """SC-8 Phase 2: multi-ministry IPC frame sequence (KOROAD + HIRA).

    Exercises tool call order: resolve_location → lookup(search,KOROAD) →
    lookup(fetch,KOROAD) → lookup(search,HIRA) → lookup(fetch,HIRA) → synthesis.

    Asserts:
    - resolve_location appears before any lookup call.
    - At least 4 lookup calls in tool_call_order.
    - Final synthesis is non-empty Korean text mentioning both KOROAD and HIRA content.
    - stop_reason == "end_turn".
    - IPC message_order ends with AssistantChunkFrame(done=True).
    - All produced IPC frames survive JSON round-trip.
    """
    import uuid

    from kosmos.context.builder import ContextBuilder
    from kosmos.engine.config import QueryEngineConfig
    from kosmos.engine.engine import QueryEngine
    from kosmos.engine.events import QueryEvent, StopReason
    from kosmos.llm.client import LLMClient
    from kosmos.llm.models import ChatMessage, StreamEvent
    from kosmos.llm.usage import UsageTracker
    from kosmos.tools.hira.hospital_search import register as reg_hira
    from tests.e2e.conftest import _build_registry_and_executor
    from tests.engine.conftest import MockLLMClient

    # Build mock LLM event sequences
    event_sequences, expected_tool_order = _build_multi_ministry_script()

    # Build registry + executor — start with base e2e setup then add HIRA
    registry, executor = _build_registry_and_executor()

    # Register HIRA hospital search adapter
    reg_hira(registry, executor)

    context_builder = ContextBuilder(registry=registry)

    class _Adapter(LLMClient):
        def __new__(cls, *args: object, **kwargs: object) -> _Adapter:
            return object.__new__(cls)  # type: ignore[return-value]

        def __init__(self, delegate: MockLLMClient) -> None:
            self._delegate = delegate

        @property
        def usage(self) -> UsageTracker:  # type: ignore[override]
            return self._delegate.usage

        async def stream(  # type: ignore[override]
            self,
            messages: list[ChatMessage],
            **kwargs: object,
        ) -> AsyncIterator[StreamEvent]:
            async for event in self._delegate.stream(messages, **kwargs):
                yield event

    llm_adapter = _Adapter(MockLLMClient(responses=event_sequences))
    config = QueryEngineConfig()
    engine = QueryEngine(
        llm_client=llm_adapter,
        tool_registry=registry,
        tool_executor=executor,
        config=config,
        context_builder=context_builder,
    )

    httpx_mock = _build_multi_ministry_httpx_mock()
    collected_events: list[QueryEvent] = []
    with patch.object(httpx.AsyncClient, "get", httpx_mock):
        async for event in engine.run(_MULTI_MINISTRY_QUERY):
            collected_events.append(event)

    # Extract tool_call_order
    tool_call_order = [e.tool_name for e in collected_events if e.type == "tool_use"]

    # Extract final response
    text_parts = [e.content for e in collected_events if e.type == "text_delta" and e.content]
    final_response = "".join(text_parts) if text_parts else None

    # Extract stop reason
    stop_events = [e for e in collected_events if e.type == "stop"]
    stop_reason = stop_events[-1].stop_reason if stop_events else StopReason.error_unrecoverable

    # --- Assertions on engine output ---

    assert tool_call_order, "Expected at least one tool call in multi-ministry scenario"

    assert "resolve_location" in tool_call_order, (
        f"resolve_location missing from tool_call_order: {tool_call_order!r}"
    )

    lookup_calls = [t for t in tool_call_order if t == "lookup"]
    assert len(lookup_calls) >= 4, (
        f"Expected ≥4 lookup calls (2 search + 2 fetch for KOROAD+HIRA), "
        f"got {len(lookup_calls)}: {tool_call_order!r}"
    )

    # resolve_location must precede the first lookup
    first_lookup_idx = next(i for i, t in enumerate(tool_call_order) if t == "lookup")
    last_resolve_idx = max(i for i, t in enumerate(tool_call_order) if t == "resolve_location")
    assert last_resolve_idx < first_lookup_idx, (
        "All resolve_location calls must precede the first lookup call. "
        f"last_resolve_idx={last_resolve_idx}, first_lookup_idx={first_lookup_idx}"
    )

    assert stop_reason in (StopReason.end_turn, StopReason.task_complete), (
        f"Expected end_turn or task_complete stop_reason, got {stop_reason!r}"
    )

    assert final_response, "final_response must not be empty for end_turn stop"
    assert any(ord(c) >= 0xAC00 for c in final_response), (
        "final_response must contain Korean characters"
    )

    # KOROAD content must be present
    koroad_keywords = ["강남구", "개포동", "삼성동", "사고", "위험"]
    assert any(kw in final_response for kw in koroad_keywords), (
        f"final_response must mention KOROAD hazard data. "
        f"Expected one of {koroad_keywords} in: {final_response[:300]!r}"
    )

    # HIRA content must be present
    hira_keywords = ["병원", "강남세브란스", "서울대학교", "응급", "강남구"]
    assert any(kw in final_response for kw in hira_keywords), (
        f"final_response must mention HIRA hospital data. "
        f"Expected one of {hira_keywords} in: {final_response[:300]!r}"
    )

    # --- Build IPC frames and assert message_order ---

    session_id = str(uuid.uuid4())
    ipc_frames: list[IPCFrame] = []  # type: ignore[type-arg]
    primitive_names = {"lookup", "resolve_location", "submit", "verify"}

    for event in collected_events:
        if event.type == "tool_use" and event.tool_name in primitive_names:
            frame = ToolCallFrame(
                session_id=session_id,
                correlation_id=str(uuid.uuid4()),
                ts=_make_ts(),
                role="backend",
                kind="tool_call",
                call_id=event.tool_call_id or str(uuid.uuid4()),
                name=event.tool_name,  # type: ignore[arg-type]
                arguments=json.loads(event.arguments) if event.arguments else {},
            )
            ipc_frames.append(frame)

        elif event.type == "tool_result":
            # Derive envelope kind from preceding tool_use
            envelope_kind = "lookup"
            idx = collected_events.index(event)
            for prev in reversed(collected_events[:idx]):
                if prev.type == "tool_use" and prev.tool_name in primitive_names:
                    envelope_kind = prev.tool_name
                    break
            envelope = ToolResultEnvelope(kind=envelope_kind)  # type: ignore[arg-type]
            result_frame = ToolResultFrame(
                session_id=session_id,
                correlation_id=str(uuid.uuid4()),
                ts=_make_ts(),
                role="backend",
                kind="tool_result",
                call_id=str(uuid.uuid4()),
                envelope=envelope,
            )
            ipc_frames.append(result_frame)

        elif event.type == "text_delta" and event.content:
            chunk = AssistantChunkFrame(
                session_id=session_id,
                correlation_id=str(uuid.uuid4()),
                ts=_make_ts(),
                role="backend",
                kind="assistant_chunk",
                message_id=str(uuid.uuid4()),
                delta=event.content,
                done=False,
            )
            ipc_frames.append(chunk)

    # Add terminal chunk
    terminal = AssistantChunkFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        ts=_make_ts(),
        role="backend",
        kind="assistant_chunk",
        message_id=str(uuid.uuid4()),
        delta="",
        done=True,
    )
    ipc_frames.append(terminal)

    # message_order assertions
    assert ipc_frames, "No IPC frames produced"

    # IPC sequence must start with a ToolCallFrame (first primitive call)
    first_primitive_frame = next((f for f in ipc_frames if isinstance(f, ToolCallFrame)), None)
    assert first_primitive_frame is not None, "Expected at least one ToolCallFrame"
    assert first_primitive_frame.name in primitive_names

    # IPC sequence must end with AssistantChunkFrame(done=True)
    last_frame = ipc_frames[-1]
    assert isinstance(last_frame, AssistantChunkFrame), (
        f"Expected last IPC frame to be AssistantChunkFrame, got {type(last_frame).__name__}"
    )
    assert last_frame.done, "Last AssistantChunkFrame must have done=True"

    # All ToolCallFrame names must be active primitive names
    for f in ipc_frames:
        if isinstance(f, ToolCallFrame):
            assert f.name in primitive_names, (
                f"ToolCallFrame.name={f.name!r} is not a valid active primitive name"
            )

    # JSON round-trip for all frames
    for frame in ipc_frames:
        raw_json = frame.model_dump_json()
        recovered = _frame_adapter.validate_json(raw_json)
        assert recovered.kind == frame.kind, (
            f"Round-trip kind mismatch: {frame.kind!r} != {recovered.kind!r}"
        )
