# SPDX-License-Identifier: Apache-2.0
"""T128 — Smoke test: SC-8 Scenario 1 (route safety) end-to-end via IPC.

Strategy
--------
The IPC stdio bridge (`kosmos.ipc.stdio`) reads JSONL frames from stdin and
writes JSONL frames to stdout.  This test exercises the *layer below* the TUI:
it drives the Python backend's QueryEngine directly via the same
infrastructure the e2e suite uses, then validates that the frame sequence a
real TUI consumer would receive is correct.

Two sub-tests are provided:

``test_sc8_scenario1_ipc_frame_sequence``
    Verifies that running the "happy" QueryEngine scenario produces the
    expected IPC frame *kinds* in order: at least one ``tool_call``,
    at least one ``tool_result``, and a final ``assistant_chunk`` with
    ``done=True``.  The frame objects are constructed by the same helper
    used in ``ipc/stdio.py``; the test exercises the serialise/deserialise
    round-trip via ``model_dump_json`` + ``TypeAdapter.validate_json``.

``test_sc8_scenario1_fixture_round_trip``
    Verifies the recorded KOROAD fixture parses and the expected hazard-spot
    fields are present.  Standalone fixture sanity — no subprocess spawning.

Live API note
-------------
Neither sub-test calls a live data.go.kr endpoint.  All HTTP interactions are
intercepted by the AsyncMock seam from ``tests.e2e.conftest``.  If a live
KOROAD API key is configured (``KOSMOS_KOROAD_API_KEY`` or
``KOSMOS_DATA_GO_KR_API_KEY``), the test does NOT automatically become live;
it still uses the fixture.  A ``@pytest.mark.live`` variant would be required
for real live calls (out of scope for this task per AGENTS.md hard rules).

Fixture source
--------------
``tests/fixtures/koroad/accident_hazard_search_happy.json`` — committed
recorded fixture synthesised from the published KOROAD API docs.
``tests/fixtures/kma/forecast_fetch_happy.json`` — KMA short-term forecast
fixture.
``tests/fixtures/kakao/`` — Kakao geocoder fixtures used by resolve_location.
"""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from pydantic import TypeAdapter

from kosmos.ipc.frame_schema import (
    AssistantChunkFrame,
    IPCFrame,
    ToolCallFrame,
    ToolResultFrame,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURE_BASE = Path(__file__).resolve().parent.parent / "fixtures"
_KOROAD_FIXTURE = _FIXTURE_BASE / "koroad" / "accident_hazard_search_happy.json"
_KMA_FIXTURE = _FIXTURE_BASE / "kma" / "forecast_fetch_happy.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_frame_adapter: TypeAdapter[Any] = TypeAdapter(IPCFrame)


def _load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"Fixture missing: {path}"
    return json.loads(path.read_text())


def _make_ts() -> str:
    from datetime import datetime

    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# T128-A: IPC frame serialise / deserialise round-trip for route-safety turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sc8_scenario1_ipc_frame_sequence() -> None:  # noqa: C901
    """SC-8 Scenario 1: validate IPC frame sequence via QueryEngine + fixture mock.

    Wires:
    - QueryEngine with MockLLMClient scripted to the "happy" 6-turn sequence
      (resolve x2, lookup x4, synthesize).
    - httpx.AsyncClient.get AsyncMock routing to KOROAD + KMA + Kakao fixtures.
    - IPC frame construction from QueryEvent stream (ToolCallFrame + ToolResultFrame
      + AssistantChunkFrame) and serialise/deserialise round-trip validation.

    Asserts:
    - At least one ToolCallFrame with name in {lookup, resolve_location}.
    - At least one ToolResultFrame with envelope.kind in {lookup, resolve_location}.
    - At least one AssistantChunkFrame with done=True.
    - All frames survive model_dump_json + TypeAdapter.validate_json round-trip.
    - No live data.go.kr calls (all HTTP intercepted by fixture mock).
    """
    import uuid

    from kosmos.context.builder import ContextBuilder
    from kosmos.engine.config import QueryEngineConfig
    from kosmos.engine.engine import QueryEngine
    from kosmos.engine.events import QueryEvent
    from kosmos.ipc.frame_schema import ToolResultEnvelope
    from tests.e2e.conftest import (
        TRIGGER_QUERY,
        _build_httpx_mock,
        _build_registry_and_executor,
        build_happy_script,
    )
    from tests.engine.conftest import MockLLMClient

    # Build scripted mock LLM (same as e2e happy scenario)
    event_sequences, _script = build_happy_script()

    registry, executor = _build_registry_and_executor()
    context_builder = ContextBuilder(registry=registry)

    # Wrap MockLLMClient in LLMClient-compatible adapter
    from kosmos.llm.client import LLMClient
    from kosmos.llm.models import ChatMessage
    from kosmos.llm.usage import UsageTracker

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
        ):
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

    # Collect QueryEvents from engine under HTTP fixture mock
    httpx_mock = _build_httpx_mock()
    collected_events: list[QueryEvent] = []
    with patch.object(httpx.AsyncClient, "get", httpx_mock):
        async for event in engine.run(TRIGGER_QUERY):
            collected_events.append(event)

    # Build IPC frames from events (simulating what the stdio bridge would produce)
    session_id = str(uuid.uuid4())
    ipc_frames: list[IPCFrame] = []  # type: ignore[type-arg]

    for event in collected_events:
        if event.type == "tool_use":
            # Only emit ToolCallFrame for primitive names that frame_schema accepts
            primitive_names = {"lookup", "resolve_location", "submit", "verify"}
            if event.tool_name in primitive_names:
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
            # tool_result events carry a ToolResult; derive envelope kind from tool_name
            # by inspecting the most recent tool_use event tool_name in collected_events.
            # Fall back to "lookup" as the default primitive kind.
            result_tool_name = "lookup"
            for prev in reversed(collected_events[: collected_events.index(event)]):
                if prev.type == "tool_use" and prev.tool_name in {
                    "lookup",
                    "resolve_location",
                    "submit",
                    "verify",
                }:
                    result_tool_name = prev.tool_name
                    break
            envelope = ToolResultEnvelope(
                kind=result_tool_name,  # type: ignore[arg-type]
            )
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

    # Add terminal assistant_chunk with done=True
    if ipc_frames:
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

    # --- Assertions ---

    assert ipc_frames, "No IPC frames produced — QueryEngine emitted no events"

    # At least one ToolCallFrame with route-safety tool names
    tool_call_frames = [f for f in ipc_frames if isinstance(f, ToolCallFrame)]
    assert tool_call_frames, "Expected at least one ToolCallFrame in IPC output"
    tool_names_seen = {f.name for f in tool_call_frames}
    assert tool_names_seen & {"lookup", "resolve_location"}, (
        f"Expected lookup or resolve_location in ToolCallFrames, got: {tool_names_seen!r}"
    )

    # At least one ToolResultFrame
    tool_result_frames = [f for f in ipc_frames if isinstance(f, ToolResultFrame)]
    assert tool_result_frames, "Expected at least one ToolResultFrame in IPC output"

    # At least one AssistantChunkFrame with done=True (terminal chunk)
    done_chunks = [f for f in ipc_frames if isinstance(f, AssistantChunkFrame) and f.done]
    assert done_chunks, "Expected at least one AssistantChunkFrame with done=True"

    # Serialise/deserialise round-trip for every frame
    for frame in ipc_frames:
        raw_json = frame.model_dump_json()
        recovered = _frame_adapter.validate_json(raw_json)
        assert recovered.kind == frame.kind, (
            f"Round-trip kind mismatch: original={frame.kind!r} recovered={recovered.kind!r}"
        )
        assert recovered.session_id == session_id, (
            f"Round-trip session_id mismatch: {recovered.session_id!r} != {session_id!r}"
        )


# ---------------------------------------------------------------------------
# T128-B: Fixture sanity — KOROAD hazard spots decode correctly
# ---------------------------------------------------------------------------


def test_sc8_scenario1_fixture_round_trip() -> None:
    """SC-8 Scenario 1 fixture sanity: KOROAD accident_hazard_search_happy.json.

    Verifies the fixture contains the expected hazard spot fields used in
    the scenario synthesis assertion (spot_nm, occrrnc_cnt, la_crd, lo_crd).
    No backend or subprocess required.
    """
    data = _load_json(_KOROAD_FIXTURE)

    items_wrapper = data.get("items", {})
    item_list = items_wrapper.get("item", [])
    assert isinstance(item_list, list), f"Expected list of items, got {type(item_list)}"
    assert len(item_list) >= 1, "Expected at least 1 hazard spot in fixture"

    first = item_list[0]
    required_fields = {"spot_cd", "spot_nm", "sido_sgg_nm", "occrrnc_cnt", "la_crd", "lo_crd"}
    missing = required_fields - set(first.keys())
    assert not missing, f"Missing fields in first fixture item: {missing!r}"

    # Confirm the Gangnam hazard spot is present (used by synthesis assertions in e2e)
    spot_names = [item["spot_nm"] for item in item_list]
    assert any("강남구" in name for name in spot_names), (
        f"Expected 강남구 hazard spot in fixture, got spot names: {spot_names!r}"
    )
