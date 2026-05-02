# SPDX-License-Identifier: Apache-2.0
"""T014 — Agentic-loop integration scenarios for Epic #2077 K-EXAONE tool wiring.

Two scenarios:

(a) test_single_tool_call_closure — Single tool-call round-trip (US1 acceptance
    scenarios 1+3, SC-001, FR-010).
    Verifies that:
    - A citizen prompt "강남구 24시간 응급실 알려주세요" triggers a lookup tool_call frame.
    - A tool_result frame follows the tool_call frame.
    - A final assistant_chunk with the Turn-2 text is emitted.
    - SC-001: Zero references to CC-era tools (Read/Glob/Bash/Write/Edit/Grep/
      NotebookEdit/Task) appear anywhere in the emitted frame stream.

(b) test_five_turn_agentic_loop — Multi-turn loop within RPM budget (SC-004, FR-012).
    Verifies that:
    - 5 sequential tool_call frames are emitted (each with a distinct call_id).
    - 5 matching tool_result frames are emitted.
    - A terminal assistant_chunk(done=True) is emitted at the end.
    - No error frame with code="rate_limit" (or containing "rate_limit") is present.
    - Total wall-clock duration is under 30 seconds (no real network involved).

Strategy: in-process harness reused from tests/ipc/test_stdio.py (_run_with_frame
at line 197, _BaseFakeLLMClient at line 150, helper infrastructure at lines 74-105).
The helpers cannot be imported directly (they are module-level privates in test_stdio),
so we replicate the minimal fixture code here. Structural parity is maintained so
reviewers can verify the approach at a glance.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import os
import re
import sys
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

from kosmos.ipc.frame_schema import (
    ChatMessage as IPCChatMessage,
)
from kosmos.ipc.frame_schema import (
    ChatRequestFrame,
    ToolDefinition,
)
from kosmos.llm.models import StreamEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared fixture infrastructure (mirrors tests/ipc/test_stdio.py lines 74-105,
# 112-144, 150-162, 194-374)
# ---------------------------------------------------------------------------


def _ts() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _make_chat_request(
    *,
    session_id: str | None = None,
    tools: list[ToolDefinition] | None = None,
    system: str | None = None,
    prompt: str = "강남구 24시간 응급실 알려주세요",
) -> ChatRequestFrame:
    """Build a minimal ChatRequestFrame for testing."""
    return ChatRequestFrame(
        session_id=session_id or str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_ts(),
        kind="chat_request",
        messages=[IPCChatMessage(role="user", content=prompt)],
        tools=tools if tools is not None else [],
        system=system,
    )


def _encode_frame(frame: ChatRequestFrame) -> bytes:
    return (frame.model_dump_json() + "\n").encode("utf-8")


class _CaptureBuf:
    """Bytes capture buffer mimicking sys.stdout.buffer."""

    def __init__(self) -> None:
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    def flush(self) -> None:
        pass

    def as_frames(self) -> list[dict[str, Any]]:
        self._buf.seek(0)
        frames = []
        for line in self._buf:
            stripped = line.strip()
            if stripped:
                with contextlib.suppress(json.JSONDecodeError):
                    frames.append(json.loads(stripped))
        return frames


class _FakeStdout:
    def __init__(self) -> None:
        self.buffer = _CaptureBuf()


# ---------------------------------------------------------------------------
# Minimal fake LLM client base
# ---------------------------------------------------------------------------


class _BaseFakeLLMClient:
    """Records stream() calls via class-level list (instance-agnostic)."""

    recorded_calls: list[dict[str, Any]] = []

    def __init__(self, config: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Minimal test tools returned by mock ToolRegistry.export_core_tools_openai
# ---------------------------------------------------------------------------

_MINIMAL_TEST_TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Search or fetch government API data",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_location",
            "description": "Resolve a Korean address or location",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit",
            "description": "Submit a government service transaction",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subscribe",
            "description": "Subscribe to government service events",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify",
            "description": "Verify identity or delegate",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

_RUNNER_TIMEOUT = 20.0  # seconds


async def _run_with_frame(  # noqa: C901 — test harness deliberately covers many branches
    frame: ChatRequestFrame,
    fake_client_cls: type,
    *,
    monkeypatch: pytest.MonkeyPatch,
    env_overrides: dict[str, str] | None = None,
) -> tuple[_CaptureBuf, type]:
    """Pipe one ChatRequestFrame through run() and return (stdout_buf, fake_client_cls).

    Replicates the harness from tests/ipc/test_stdio.py lines 197-374 with
    minimal variation.  Key steps:
    - Monkeypatch sys.stdout to capture NDJSON output.
    - Monkeypatch LLMClient + LLMClientConfig.
    - Monkeypatch ToolRegistry.export_core_tools_openai.
    - Monkeypatch PromptLoader for fast system-prompt resolution.
    - Create an OS pipe for stdin; write frame + exit sentinel; pass read-end
      to run() via sys.stdin.buffer.
    """
    from kosmos.ipc import stdio as stdio_mod
    from kosmos.ipc.frame_schema import SessionEventFrame

    # Reset stdout lock so a fresh asyncio.Lock is created for this run.
    monkeypatch.setattr(stdio_mod, "_stdout_lock", None)

    # Capture stdout.
    fake_stdout = _FakeStdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    # Reset class-level state.
    fake_client_cls.recorded_calls = []  # type: ignore[attr-defined]
    for attr in ("turn_count", "_class_turn"):
        if hasattr(fake_client_cls, attr):
            setattr(fake_client_cls, attr, 0)  # type: ignore[attr-defined]

    class _FakeLLMClientConfig:
        pass

    import kosmos.llm.client as llm_client_mod
    import kosmos.llm.config as llm_config_mod

    monkeypatch.setattr(llm_client_mod, "LLMClient", fake_client_cls)
    monkeypatch.setattr(llm_config_mod, "LLMClientConfig", _FakeLLMClientConfig)

    # Monkeypatch ToolRegistry.export_core_tools_openai.
    import kosmos.tools.registry as registry_mod

    def _fake_export(self: Any) -> list[dict[str, object]]:
        return _MINIMAL_TEST_TOOLS

    monkeypatch.setattr(registry_mod.ToolRegistry, "export_core_tools_openai", _fake_export)

    # Monkeypatch PromptLoader for fast resolution.
    try:
        import kosmos.context.prompt_loader as pl_mod

        class _FakePromptLoader:
            def __init__(self, *, manifest_path: Any) -> None:
                pass

            def load(self, name: str) -> str:
                return f"System prompt ({name})"

        monkeypatch.setattr(pl_mod, "PromptLoader", _FakePromptLoader)
    except ImportError:
        pass

    # Apply env overrides.
    for k, v in (env_overrides or {}).items():
        monkeypatch.setenv(k, v)

    # Build stdin payload: chat_request + session_event{exit}.
    session_id = frame.session_id
    exit_frame = SessionEventFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_ts(),
        kind="session_event",
        event="exit",
        payload={},
    )
    payload = _encode_frame(frame) + (exit_frame.model_dump_json() + "\n").encode("utf-8")

    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    r_file = os.fdopen(r_fd, "rb")

    class _FakeStdinWrapper:
        buffer = r_file

    monkeypatch.setattr(sys, "stdin", _FakeStdinWrapper())

    from kosmos.ipc.stdio import run as ipc_run

    try:
        await asyncio.wait_for(ipc_run(session_id=session_id), timeout=_RUNNER_TIMEOUT)
    except TimeoutError:
        pass
    except Exception:  # noqa: BLE001, S110 — test inspects captured state regardless of how the loop exited
        pass

    try:
        if not r_file.closed:
            r_file.close()
    except OSError:
        pass

    return fake_stdout.buffer, fake_client_cls


# ---------------------------------------------------------------------------
# Scenario (a) helpers — Single tool-call closure
# ---------------------------------------------------------------------------

# CC-era tool names that MUST NOT appear in KOSMOS output (SC-001 whitelist).
_CC_TOOL_NAMES = re.compile(
    r'<tool_call>\s*\{[^}]*"name"\s*:\s*"'
    r'(Read|Glob|Bash|Write|Edit|Grep|NotebookEdit|Task)"',
    re.IGNORECASE,
)


class _SingleLookupThenAnswerLLMClient(_BaseFakeLLMClient):
    """LLM that calls lookup once on Turn 1, then answers on Turn 2.

    Turn 1: tool_call_delta(name='lookup', args='{"mode":"search","query":"강남구 응급실"}') + done.
    Turn 2: emits content_delta('강남구 응급실은 강남세브란스병원입니다.') + done.
    """

    recorded_calls: list[dict[str, Any]] = []
    _class_turn: int = 0

    def __init__(self, config: Any) -> None:
        super().__init__(config)

    async def stream(
        self,
        messages: list[Any],
        *,
        tools: list[Any] | None = None,
        tool_choice: Any = None,
        temperature: float = 1.0,
        top_p: float = 0.95,
        presence_penalty: float = 0.0,
        max_tokens: int = 1024,
        stop: Any = None,
    ) -> AsyncIterator[StreamEvent]:
        type(self)._class_turn += 1
        turn = type(self)._class_turn
        type(self).recorded_calls.append({"messages": messages, "tools": tools})

        if turn == 1:
            # Tool invocation turn.
            yield StreamEvent(
                type="tool_call_delta",
                tool_call_index=0,
                tool_call_id=f"call-{uuid.uuid4().hex[:12]}",
                function_name="lookup",
                function_args_delta='{"mode":"search","query":"강남구 응급실"}',
            )
            yield StreamEvent(type="done")
        else:
            # Final answer turn (after tool_result injected into context — FR-010).
            yield StreamEvent(
                type="content_delta",
                content="강남구 응급실은 강남세브란스병원입니다.",
            )
            yield StreamEvent(type="done")


# ---------------------------------------------------------------------------
# Scenario (a) test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_tool_call_closure(monkeypatch: pytest.MonkeyPatch) -> None:
    """US1 acceptance scenarios 1+3, SC-001, FR-010.

    A citizen prompt triggers exactly one lookup tool call.  After the tool
    result is fed back (FR-010), the model emits a final answer.  The entire
    frame stream contains zero references to CC-era developer tools (SC-001).
    """
    frame = _make_chat_request(
        prompt="강남구 24시간 응급실 알려주세요",
        tools=[],
    )

    # Monkeypatch kosmos.tools.lookup.lookup to resolve immediately with a
    # synthetic envelope (bypasses BM25 + real adapters, no live network).
    import kosmos.tools.lookup as lookup_mod
    from kosmos.tools.models import AdapterCandidate, LookupSearchResult

    async def _fake_lookup(
        inp: Any,
        *,
        registry: Any = None,
        executor: Any = None,
        session_identity: Any = None,
    ) -> LookupSearchResult:
        return LookupSearchResult(
            kind="search",
            candidates=[
                AdapterCandidate(
                    tool_id="nmc_emergency_search",
                    score=0.95,
                    required_params=["query"],
                    search_hint="강남 응급실",
                    why_matched="query matches emergency room context",
                    requires_auth=False,
                    is_personal_data=False,
                )
            ],
            total_registry_size=5,
            effective_top_k=5,
            reason="ok",
        )

    monkeypatch.setattr(lookup_mod, "lookup", _fake_lookup)

    buf, _ = await _run_with_frame(
        frame,
        _SingleLookupThenAnswerLLMClient,
        monkeypatch=monkeypatch,
        env_overrides={
            "KOSMOS_TOOL_RESULT_TIMEOUT_SECONDS": "10",
            "KOSMOS_AGENTIC_LOOP_MAX_TURNS": "8",
        },
    )

    emitted = buf.as_frames()
    assert emitted, "No IPC frames were emitted — harness or handler may have failed"

    # --- Assert: at least one tool_call frame for 'lookup' ---
    tool_call_frames = [f for f in emitted if f.get("kind") == "tool_call"]
    assert tool_call_frames, (
        "No tool_call frame emitted. Expected at least one tool_call for 'lookup'. "
        f"Emitted kinds: {[f.get('kind') for f in emitted]}"
    )
    lookup_calls = [f for f in tool_call_frames if f.get("name") == "lookup"]
    assert lookup_calls, (
        f"tool_call frames present but none for name='lookup'. "
        f"tool_call names: {[f.get('name') for f in tool_call_frames]}"
    )

    # --- Assert: at least one tool_result frame ---
    tool_result_frames = [f for f in emitted if f.get("kind") == "tool_result"]
    assert tool_result_frames, (
        "No tool_result frame emitted after tool_call. "
        "FR-010 requires the tool result to be fed back into the next LLM turn."
    )

    # --- Assert: final assistant_chunk with Turn-2 text ---
    assistant_chunks = [f for f in emitted if f.get("kind") == "assistant_chunk"]
    assert assistant_chunks, (
        "No assistant_chunk frames emitted. Expected a final answer from Turn 2."
    )
    all_delta_text = "".join(str(f.get("delta", "")) for f in assistant_chunks if f.get("delta"))
    assert "강남세브란스" in all_delta_text or "강남구 응급실" in all_delta_text, (
        f"Final answer text not found in assistant_chunk deltas. "
        f"Concatenated deltas: {all_delta_text!r}"
    )

    # --- SC-001: NO references to CC-era tools anywhere in emitted stream ---
    full_stream_text = json.dumps(emitted, ensure_ascii=False)
    assert not _CC_TOOL_NAMES.search(full_stream_text), (
        "SC-001 violation: CC-era tool reference (Read/Glob/Bash/Write/Edit/Grep/"
        "NotebookEdit/Task) found in emitted IPC frame stream. "
        f"Frames (truncated): {full_stream_text[:500]!r}"
    )


# ---------------------------------------------------------------------------
# Scenario (b) helpers — 5-turn agentic loop
# ---------------------------------------------------------------------------


class _FiveTurnToolCallLLMClient(_BaseFakeLLMClient):
    """LLM that emits one tool_call_delta for each of the first 5 turns,
    then emits a final content_delta + done on Turn 6.

    Uses class-level counters so the instance created by _ensure_llm_client()
    inside run() shares state with the test's observation point.
    """

    recorded_calls: list[dict[str, Any]] = []
    _class_turn: int = 0

    def __init__(self, config: Any) -> None:
        super().__init__(config)

    async def stream(
        self,
        messages: list[Any],
        *,
        tools: list[Any] | None = None,
        tool_choice: Any = None,
        temperature: float = 1.0,
        top_p: float = 0.95,
        presence_penalty: float = 0.0,
        max_tokens: int = 1024,
        stop: Any = None,
    ) -> AsyncIterator[StreamEvent]:
        type(self)._class_turn += 1
        turn = type(self)._class_turn
        type(self).recorded_calls.append({"messages": messages, "tools": tools})

        if turn <= 5:
            # Tool invocation turns 1-5: each with a unique call_id.
            yield StreamEvent(
                type="tool_call_delta",
                tool_call_index=0,
                tool_call_id=f"call-turn{turn}-{uuid.uuid4().hex[:8]}",
                function_name="lookup",
                function_args_delta=f'{{"mode":"search","query":"응급실 검색 {turn}"}}',
            )
            yield StreamEvent(type="done")
        else:
            # Turn 6+: final answer.
            yield StreamEvent(
                type="content_delta",
                content="5번의 조회 후 최종 답변드립니다.",
            )
            yield StreamEvent(type="done")


# ---------------------------------------------------------------------------
# Scenario (b) test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_five_turn_agentic_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-004, FR-012 — 5-turn multi-tool agentic loop.

    Five sequential lookup calls complete, each generating a tool_call +
    tool_result pair, followed by a terminal assistant_chunk(done=True).
    Wall-clock duration stays under 30 seconds (no real network).
    No rate-limit error frame appears (FR-012).
    """
    frame = _make_chat_request(
        prompt="강남구 응급실 5군데 알려주세요",
        tools=[],
    )

    # Monkeypatch lookup to resolve immediately.
    import kosmos.tools.lookup as lookup_mod
    from kosmos.tools.models import AdapterCandidate, LookupSearchResult

    call_counter = {"n": 0}

    async def _fast_lookup(
        inp: Any,
        *,
        registry: Any = None,
        executor: Any = None,
        session_identity: Any = None,
    ) -> LookupSearchResult:
        call_counter["n"] += 1
        return LookupSearchResult(
            kind="search",
            candidates=[
                AdapterCandidate(
                    tool_id="nmc_emergency_search",
                    score=0.9,
                    required_params=["query"],
                    search_hint=f"응급실 call {call_counter['n']}",
                    why_matched="emergency room match",
                    requires_auth=False,
                    is_personal_data=False,
                )
            ],
            total_registry_size=5,
            effective_top_k=5,
            reason="ok",
        )

    monkeypatch.setattr(lookup_mod, "lookup", _fast_lookup)

    start = time.perf_counter()
    buf, _ = await _run_with_frame(
        frame,
        _FiveTurnToolCallLLMClient,
        monkeypatch=monkeypatch,
        env_overrides={
            "KOSMOS_TOOL_RESULT_TIMEOUT_SECONDS": "10",
            "KOSMOS_AGENTIC_LOOP_MAX_TURNS": "8",
        },
    )
    elapsed = time.perf_counter() - start

    emitted = buf.as_frames()
    assert emitted, "No IPC frames were emitted — harness or handler may have failed"

    # --- Assert: 5 distinct tool_call frames (SC-004) ---
    tool_call_frames = [f for f in emitted if f.get("kind") == "tool_call"]
    call_ids_seen: set[str] = {str(f.get("call_id", "")) for f in tool_call_frames}
    # Filter out any empty-string call_ids from malformed frames.
    call_ids_seen.discard("")
    assert len(call_ids_seen) >= 5, (
        f"Expected at least 5 distinct tool_call frames (SC-004). "
        f"Found {len(call_ids_seen)} distinct call_ids: {sorted(call_ids_seen)}. "
        f"Total tool_call frames: {len(tool_call_frames)}."
    )

    # --- Assert: 5 distinct tool_result frames ---
    tool_result_frames = [f for f in emitted if f.get("kind") == "tool_result"]
    result_call_ids: set[str] = {str(f.get("call_id", "")) for f in tool_result_frames}
    result_call_ids.discard("")
    assert len(result_call_ids) >= 5, (
        f"Expected at least 5 distinct tool_result frames. "
        f"Found {len(result_call_ids)} distinct call_ids: {sorted(result_call_ids)}. "
        f"Total tool_result frames: {len(tool_result_frames)}."
    )

    # --- Assert: terminal assistant_chunk(done=True) at the end ---
    terminal_chunks = [
        f for f in emitted if f.get("kind") == "assistant_chunk" and f.get("done") is True
    ]
    assert terminal_chunks, (
        "No terminal assistant_chunk(done=True) frame found in emitted frames. "
        "The agentic loop must emit a final done=True chunk after the last turn."
    )

    # --- Assert: NO rate_limit error frame (FR-012) ---
    error_frames = [f for f in emitted if f.get("kind") == "error"]
    rate_limit_errors = [
        f
        for f in error_frames
        if "rate_limit" in str(f.get("code", "")).lower()
        or "rate_limit" in str(f.get("message", "")).lower()
    ]
    assert not rate_limit_errors, (
        f"FR-012 violation: rate_limit error frame(s) found in multi-turn loop. "
        f"Frames: {rate_limit_errors}"
    )

    # --- Assert: wall-clock duration < 30 seconds (SC-004 loose bound) ---
    assert elapsed < 30.0, (
        f"Multi-turn agentic loop took {elapsed:.2f}s which exceeds the 30-second "
        "budget (SC-004). The fixture has no real network — check for blocking I/O."
    )


# ---------------------------------------------------------------------------
# T017 follow-up — multi-call LLM turn coerced to one visible dispatch
# ---------------------------------------------------------------------------


class _ThreeToolsInOneTurnLLMClient(_BaseFakeLLMClient):
    """LLM that emits 3 simultaneous tool calls, then a follow-up single call.

    Turn 1: three tool_call_delta events at index 0, 1, 2 — each for name='lookup'
            with a distinct query argument. Then done.
    Turn 2: one follow-up tool_call_delta after observing the first result.
    Turn 3: one content_delta carrying the final answer text. Then done.

    The backend must expose only the first Turn-1 call to the TUI/context so
    results paint before any additional tool request.
    """

    recorded_calls: list[dict[str, Any]] = []
    _class_turn: int = 0

    # Pre-generate stable IDs so the test can compare them after the run.
    _call_ids: list[str] = [
        f"call-t17-{uuid.uuid4().hex[:12]}",
        f"call-t17-{uuid.uuid4().hex[:12]}",
        f"call-t17-{uuid.uuid4().hex[:12]}",
    ]
    _followup_call_id: str = f"call-t17-followup-{uuid.uuid4().hex[:12]}"

    def __init__(self, config: Any) -> None:
        super().__init__(config)

    async def stream(
        self,
        messages: list[Any],
        *,
        tools: list[Any] | None = None,
        tool_choice: Any = None,
        temperature: float = 1.0,
        top_p: float = 0.95,
        presence_penalty: float = 0.0,
        max_tokens: int = 1024,
        stop: Any = None,
    ) -> AsyncIterator[StreamEvent]:
        type(self)._class_turn += 1
        turn = type(self)._class_turn
        type(self).recorded_calls.append({"messages": messages, "tools": tools})

        if turn == 1:
            # Emit three parallel tool_call_deltas with indices 0, 1, 2.
            queries = ["응급실 강남", "응급실 서초", "응급실 송파"]
            for idx, (call_id, query) in enumerate(zip(type(self)._call_ids, queries, strict=True)):
                yield StreamEvent(
                    type="tool_call_delta",
                    tool_call_index=idx,
                    tool_call_id=call_id,
                    function_name="lookup",
                    function_args_delta=json.dumps(
                        {
                            "mode": "fetch",
                            "tool_id": "nmc_emergency_search",
                            "params": {"query": query},
                        },
                        ensure_ascii=False,
                    ),
                )
            yield StreamEvent(type="done")
        elif turn == 2:
            yield StreamEvent(
                type="tool_call_delta",
                tool_call_index=0,
                tool_call_id=type(self)._followup_call_id,
                function_name="lookup",
                function_args_delta=json.dumps(
                    {
                        "mode": "fetch",
                        "tool_id": "nmc_emergency_search",
                        "params": {"query": "응급실 서초"},
                    },
                    ensure_ascii=False,
                ),
            )
            yield StreamEvent(type="done")
        else:
            # Turn 3+: emit the final answer after sequential tool_results.
            yield StreamEvent(
                type="content_delta",
                content="순차 조회 결과로 근처 응급실 정보를 확인했습니다.",
            )
            yield StreamEvent(type="done")


# ---------------------------------------------------------------------------
# T017 test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_tool_turn_is_coerced_to_one_visible_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend exposes one tool call per LLM turn even if the model emits many."""
    # Reset class-level state before test so call_ids are fresh.
    _ThreeToolsInOneTurnLLMClient._class_turn = 0
    _ThreeToolsInOneTurnLLMClient._call_ids = [
        f"call-t17-{uuid.uuid4().hex[:12]}",
        f"call-t17-{uuid.uuid4().hex[:12]}",
        f"call-t17-{uuid.uuid4().hex[:12]}",
    ]
    _ThreeToolsInOneTurnLLMClient._followup_call_id = f"call-t17-followup-{uuid.uuid4().hex[:12]}"

    frame = _make_chat_request(
        prompt="강남, 서초, 송파 응급실 각각 알려주세요",
        tools=[],
    )

    # Monkeypatch kosmos.tools.lookup.lookup to return a different result per
    # call (identified by a sequential counter) so pairing can be verified.
    import kosmos.tools.lookup as lookup_mod
    from kosmos.tools.models import AdapterCandidate, LookupSearchResult

    call_counter: dict[str, int] = {"n": 0}
    district_names = ["강남", "서초", "송파"]

    async def _multi_lookup(
        inp: Any,
        *,
        registry: Any = None,
        executor: Any = None,
        session_identity: Any = None,
    ) -> LookupSearchResult:
        n = call_counter["n"]
        call_counter["n"] += 1
        district = district_names[n % len(district_names)]
        return LookupSearchResult(
            kind="search",
            candidates=[
                AdapterCandidate(
                    tool_id="nmc_emergency_search",
                    score=0.95 - n * 0.01,
                    required_params=["query"],
                    search_hint=f"{district} 응급실",
                    why_matched=f"query matches {district} emergency room context",
                    requires_auth=False,
                    is_personal_data=False,
                )
            ],
            total_registry_size=5,
            effective_top_k=5,
            reason="ok",
        )

    monkeypatch.setattr(lookup_mod, "lookup", _multi_lookup)

    buf, _ = await _run_with_frame(
        frame,
        _ThreeToolsInOneTurnLLMClient,
        monkeypatch=monkeypatch,
        env_overrides={
            "KOSMOS_TOOL_RESULT_TIMEOUT_SECONDS": "10",
            "KOSMOS_AGENTIC_LOOP_MAX_TURNS": "8",
        },
    )

    emitted = buf.as_frames()
    assert emitted, "No IPC frames were emitted — harness or handler may have failed"

    tool_call_frames = [f for f in emitted if f.get("kind") == "tool_call"]
    tool_call_ids: list[str] = [
        str(f.get("call_id", "")) for f in tool_call_frames if f.get("call_id")
    ]
    tool_result_frames = [f for f in emitted if f.get("kind") == "tool_result"]
    result_call_ids: list[str] = [
        str(f.get("call_id", "")) for f in tool_result_frames if f.get("call_id")
    ]
    expected_call_ids = [
        _ThreeToolsInOneTurnLLMClient._call_ids[0],
        _ThreeToolsInOneTurnLLMClient._followup_call_id,
    ]
    assert tool_call_ids == expected_call_ids
    assert result_call_ids == expected_call_ids
    assert _ThreeToolsInOneTurnLLMClient._call_ids[1] not in tool_call_ids
    assert _ThreeToolsInOneTurnLLMClient._call_ids[2] not in tool_call_ids
    assert call_counter["n"] == 2

    frame_kinds = [f.get("kind") for f in emitted]
    first_call_idx = frame_kinds.index("tool_call")
    first_result_idx = frame_kinds.index("tool_result")
    second_call_idx = frame_kinds.index("tool_call", first_call_idx + 1)
    second_result_idx = frame_kinds.index("tool_result", first_result_idx + 1)
    assert first_call_idx < first_result_idx < second_call_idx < second_result_idx

    assistant_chunks = [f for f in emitted if f.get("kind") == "assistant_chunk"]
    assert assistant_chunks, (
        "No assistant_chunk frames emitted after sequential tool_results. "
        "The agentic loop must emit a final answer."
    )
    all_delta_text = "".join(str(f.get("delta", "")) for f in assistant_chunks if f.get("delta"))
    assert "순차 조회" in all_delta_text or "응급실" in all_delta_text, (
        f"Final answer text not found in assistant_chunk deltas. "
        f"Concatenated deltas: {all_delta_text!r}"
    )
