# SPDX-License-Identifier: Apache-2.0
"""Regression test for stdio.py:_dispatch_primitive lookup branch.

Bug (citizen "오늘 부산 날씨 어땠어?" report, 2026-05-01):
    The IPC stdio dispatcher's lookup branch instantiated a fresh empty
    ``ToolRegistry`` + ``ToolExecutor`` on every call, so every
    ``lookup(mode="search", query=...)`` returned ``reason="empty_registry"``
    and the LLM concluded that no adapters were registered. Live API keys
    and the agentic loop were both fine — only the wiring was broken.

Fix:
    ``_ensure_tool_registry`` (and a paired ``_ensure_tool_executor``) now
    invoke ``register_all_tools(registry, executor)`` exactly once per
    session, and ``_dispatch_primitive`` reuses those singletons.

This test exercises the full IPC harness (no monkey-patch on ``lookup``)
and asserts that a citizen weather query surfaces KMA adapters via BM25,
proving the dispatcher is wired to the populated registry.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

from kosmos.ipc.frame_schema import (
    ChatMessage as IPCChatMessage,
)
from kosmos.ipc.frame_schema import ChatRequestFrame
from kosmos.llm.models import StreamEvent

_RUNNER_TIMEOUT = 30.0


def _ts() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _make_chat_request(prompt: str) -> ChatRequestFrame:
    return ChatRequestFrame(
        session_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_ts(),
        kind="chat_request",
        messages=[IPCChatMessage(role="user", content=prompt)],
        tools=[],
        system=None,
    )


class _CaptureBuf:
    def __init__(self) -> None:
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    def flush(self) -> None:
        pass

    def as_frames(self) -> list[dict[str, Any]]:
        self._buf.seek(0)
        frames: list[dict[str, Any]] = []
        for line in self._buf:
            stripped = line.strip()
            if stripped:
                with contextlib.suppress(json.JSONDecodeError):
                    frames.append(json.loads(stripped))
        return frames


class _FakeStdout:
    def __init__(self) -> None:
        self.buffer = _CaptureBuf()


class _LookupSearchOnceLLMClient:
    """Fake LLM that emits exactly one ``lookup(mode="search")`` call.

    Turn 1: ``lookup(mode="search", query="부산 날씨", top_k=5)``.
    Turn 2: short content delta so the agentic loop terminates cleanly.
    """

    _class_turn: int = 0

    def __init__(self, config: Any) -> None:  # noqa: D401
        pass

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

        if turn == 1:
            call_id = f"call-{uuid.uuid4().hex[:12]}"
            args = json.dumps(
                {
                    "mode": "search",
                    "query": "부산 날씨",
                    "top_k": 5,
                }
            )
            yield StreamEvent(
                type="tool_call_delta",
                tool_call_index=0,
                tool_call_id=call_id,
                function_name="lookup",
                function_args_delta=args,
            )
            yield StreamEvent(type="done")
        else:
            yield StreamEvent(type="content_delta", content="조회 완료.")
            yield StreamEvent(type="done")


async def _run_lookup_search(
    frame: ChatRequestFrame, monkeypatch: pytest.MonkeyPatch
) -> _CaptureBuf:
    from kosmos.ipc import stdio as stdio_mod
    from kosmos.ipc.frame_schema import SessionEventFrame

    monkeypatch.setattr(stdio_mod, "_stdout_lock", None)

    fake_stdout = _FakeStdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    _LookupSearchOnceLLMClient._class_turn = 0

    class _FakeLLMConfig:
        pass

    import kosmos.llm.client as llm_client_mod
    import kosmos.llm.config as llm_config_mod

    monkeypatch.setattr(llm_client_mod, "LLMClient", _LookupSearchOnceLLMClient)
    monkeypatch.setattr(llm_config_mod, "LLMClientConfig", _FakeLLMConfig)

    # Stub the prompt loader so the test doesn't hit the manifest on disk.
    try:
        import kosmos.context.prompt_loader as pl_mod

        class _FPL:
            def __init__(self, *, manifest_path: Any) -> None:
                pass

            def load(self, name: str) -> str:
                return f"System prompt ({name})"

        monkeypatch.setattr(pl_mod, "PromptLoader", _FPL)
    except ImportError:
        pass

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
    payload = (frame.model_dump_json() + "\n").encode() + (
        exit_frame.model_dump_json() + "\n"
    ).encode()

    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    r_file = os.fdopen(r_fd, "rb")

    class _FakeStdinWrapper:
        buffer = r_file

    monkeypatch.setattr(sys, "stdin", _FakeStdinWrapper())

    import logging as _logging

    from kosmos.ipc.stdio import run as ipc_run

    try:
        await asyncio.wait_for(ipc_run(session_id=session_id), timeout=_RUNNER_TIMEOUT)
    except (TimeoutError, Exception) as exc:  # noqa: BLE001
        _logging.getLogger(__name__).debug(
            "_run_lookup_search: IPC loop exited early: %s", exc
        )
    finally:
        if not r_file.closed:
            r_file.close()

    return fake_stdout.buffer


@pytest.mark.asyncio
async def test_dispatch_primitive_lookup_uses_populated_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: ``_dispatch_primitive`` lookup branch must hit the
    register_all_tools-populated singleton registry, not a fresh empty one.

    The fake LLM emits ``lookup(mode="search", query="부산 날씨")``. After the
    fix, the dispatcher routes this through the same ToolRegistry that
    ``register_all_tools`` initialised, so BM25 surfaces KMA forecast
    adapters with reason="ok". Before the fix the envelope contained
    reason="empty_registry" and an empty candidate list.
    """
    frame = _make_chat_request("부산 날씨 알려줘")
    buf = await _run_lookup_search(frame, monkeypatch)

    frames = buf.as_frames()
    assert frames, "No IPC frames emitted"

    tool_results = [f for f in frames if f.get("kind") == "tool_result"]
    lookup_results = [
        f for f in tool_results if f.get("envelope", {}).get("kind") == "lookup"
    ]
    assert lookup_results, (
        f"expected at least one lookup tool_result frame; got kinds="
        f"{[f.get('envelope', {}).get('kind') for f in tool_results]}"
    )

    envelope = lookup_results[0]["envelope"]
    inner = envelope.get("result")
    assert isinstance(inner, dict), f"envelope.result must be a dict, got {type(inner)}"
    assert inner.get("kind") == "search", (
        f"expected result.kind='search', got {inner.get('kind')!r}; "
        f"full inner={inner!r}"
    )
    assert inner.get("reason") == "ok", (
        f"REGRESSION: dispatcher returned reason={inner.get('reason')!r}. "
        f"This means _dispatch_primitive is using an empty ToolRegistry "
        f"(stdio.py bug fixed 2026-05-01)."
    )

    candidates = inner.get("candidates") or []
    assert candidates, (
        f"BM25 returned no candidates for '부산 날씨' query. "
        f"Either the registry is still empty, or BM25 indexing broke. "
        f"total_registry_size={inner.get('total_registry_size')}"
    )

    candidate_ids = [c.get("tool_id") for c in candidates]
    assert any("kma" in (cid or "") for cid in candidate_ids), (
        f"expected at least one KMA adapter for weather query, got "
        f"candidate_ids={candidate_ids}"
    )
