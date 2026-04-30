# SPDX-License-Identifier: Apache-2.0
"""Spec 2521 T006 — End-to-end thinking-channel plumbing test (FR-008).

Drives the FULL chain:
    simulated FriendliAI SSE (delta.reasoning_content)
        → LLMClient._stream_response (yields thinking_delta event)
        → backend stdio.py emits AssistantChunkFrame(thinking=...)
        → IPC bridge transports the frame
        → TUI llmClient.ts converts to content_block_delta { type: 'thinking_delta' }
        → assistant message content[] contains { type: 'thinking', thinking: <concatenated> }
        → Ink's AssistantThinkingMessage renders ∴ Thinking glyph

Scaffold (T006): in-process harness skeleton. Full implementation in T023.

CC reference chain:
  - services/api/claude.ts:2148 (thinking_delta content_block_delta)
  - services/api/claude.ts:2030 (thinking content_block_start)
  - components/messages/AssistantThinkingMessage.tsx (∴ Thinking render)
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import uuid
from datetime import UTC, datetime

import pytest


def _ts() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _make_thinking_only_llm_client():
    """Return a synthetic LLMClient class emitting thinking_delta events.

    Extracted to module level to keep the test function under C901 complexity.
    """
    from kosmos.llm.models import StreamEvent  # noqa: PLC0415

    class _ThinkingOnlyLLMClient:
        _class_turn = 0

        def __init__(self, config: object) -> None:  # noqa: D401
            pass

        async def stream(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            type(self)._class_turn += 1
            for chunk in ["사용자가 ", "부산 날씨를 ", "물어보고 있습니다."]:
                yield StreamEvent(type="thinking_delta", thinking=chunk)
            yield StreamEvent(type="content_delta", content="조회 완료.")
            yield StreamEvent(type="done")

    return _ThinkingOnlyLLMClient


def _stub_prompt_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub PromptLoader to avoid manifest disk I/O during the test."""
    with contextlib.suppress(ImportError):
        import kosmos.context.prompt_loader as pl_mod  # noqa: PLC0415

        class _FPL:
            def __init__(self, *, manifest_path: object) -> None:
                pass

            def load(self, name: str) -> str:
                return f"System prompt ({name})"

        monkeypatch.setattr(pl_mod, "PromptLoader", _FPL)


class _CaptureBuf:
    def __init__(self) -> None:
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    def flush(self) -> None:
        pass

    def as_frames(self) -> list[dict]:
        self._buf.seek(0)
        frames: list[dict] = []
        for line in self._buf:
            stripped = line.strip()
            if stripped:
                with contextlib.suppress(json.JSONDecodeError):
                    frames.append(json.loads(stripped))
        return frames


class _FakeStdout:
    def __init__(self) -> None:
        self.buffer = _CaptureBuf()


@pytest.mark.asyncio
async def test_thinking_channel_e2e_plumbing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T006 scaffold — verifies the FriendliAI → LLMClient → AssistantChunkFrame
    backend half of the chain. The TUI half (assistant message thinking content
    block + Ink render) is covered by T024 ink-testing-library snapshot.

    Full assertions populated in T023 once Procedure-A byte-copy is complete.
    """
    from kosmos.ipc.frame_schema import (
        ChatMessage as IPCChatMessage,
    )
    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
        ChatRequestFrame,
    )

    # ---- Stage 1: synthetic LLMClient that emits thinking_delta events ----
    class _FakeLLMConfig:
        pass

    import kosmos.llm.client as llm_client_mod  # noqa: PLC0415
    import kosmos.llm.config as llm_config_mod  # noqa: PLC0415

    monkeypatch.setattr(llm_client_mod, "LLMClient", _make_thinking_only_llm_client())
    monkeypatch.setattr(llm_config_mod, "LLMClientConfig", _FakeLLMConfig)

    _stub_prompt_loader(monkeypatch)

    # ---- Stage 2: run a single chat_request through stdio backend ----
    sid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    frame = ChatRequestFrame(
        session_id=sid,
        correlation_id=cid,
        role="tui",
        ts=_ts(),
        kind="chat_request",
        messages=[IPCChatMessage(role="user", content="오늘 부산 날씨")],
        tools=[],
        system=None,
    )
    exit_frame = {
        "version": "1.0",
        "kind": "session_event",
        "role": "tui",
        "session_id": sid,
        "correlation_id": str(uuid.uuid4()),
        "frame_seq": 2,
        "ts": _ts(),
        "event": "exit",
        "payload": {},
    }

    fake_stdout = _FakeStdout()
    import sys

    monkeypatch.setattr(sys, "stdout", fake_stdout)

    from kosmos.ipc import stdio as stdio_mod  # noqa: PLC0415

    monkeypatch.setattr(stdio_mod, "_stdout_lock", None)

    # Pipe stdin with the chat_request + exit frame
    import os

    payload = (frame.model_dump_json() + "\n").encode() + (json.dumps(exit_frame) + "\n").encode()
    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    r_file = os.fdopen(r_fd, "rb")

    class _FakeStdinWrapper:
        buffer = r_file

    monkeypatch.setattr(sys, "stdin", _FakeStdinWrapper())

    from kosmos.ipc.stdio import run as ipc_run  # noqa: PLC0415

    # Backend may exit early on stdin EOF — suppress so the assertion phase
    # can run on whatever frames were emitted before exit.
    with contextlib.suppress(Exception):
        await asyncio.wait_for(ipc_run(session_id=sid), timeout=15.0)
    if not r_file.closed:
        r_file.close()

    # ---- Stage 3: assert AssistantChunkFrame with thinking field emitted ----
    frames = fake_stdout.buffer.as_frames()
    thinking_chunks = [
        f
        for f in frames
        if f.get("kind") == "assistant_chunk" and f.get("thinking")
    ]
    assert thinking_chunks, (
        f"expected at least one AssistantChunkFrame with thinking field; "
        f"got kinds: {[f.get('kind') for f in frames]}"
    )

    concatenated = "".join(f.get("thinking", "") for f in thinking_chunks)
    assert "부산 날씨" in concatenated, (
        f"reasoning content not preserved verbatim through IPC: {concatenated!r}"
    )

    # Sanity: visible content channel separate from thinking
    content_chunks = [
        f for f in frames if f.get("kind") == "assistant_chunk" and f.get("delta")
    ]
    visible = "".join(f.get("delta", "") for f in content_chunks)
    assert "사용자가" not in visible, (
        f"thinking content leaked into delta channel: {visible!r}"
    )
