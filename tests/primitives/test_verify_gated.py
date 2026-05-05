# SPDX-License-Identifier: Apache-2.0
"""Tests for verify primitive gating (Gap B fix).

Verifies that:
1. ``GATED_PRIMITIVES`` includes ``verify``.
2. ``LIGHT_GATE_PRIMITIVES`` is a subset of ``GATED_PRIMITIVES`` containing
   only ``verify``.
3. ``HEAVY_GATE_PRIMITIVES`` contains ``submit`` and ``subscribe`` but NOT
   ``verify``.
4. The gate partition is exhaustive: every primitive is either gated or
   fully auto-allowed (lookup / resolve_location).
5. The IPC stdio ``_check_permission_gate`` emits a ``PermissionRequestFrame``
   for a ``verify`` call (i.e. verify now enters the bridge, not the
   auto-allow shortcut).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

import kosmos.tools.mock  # noqa: F401  — registers all mock adapters
from kosmos.ipc.frame_schema import (
    ChatMessage as IPCChatMessage,
)
from kosmos.ipc.frame_schema import (
    ChatRequestFrame,
    PermissionRequestFrame,
)
from kosmos.llm.models import StreamEvent
from kosmos.primitives import (
    GATED_PRIMITIVES,
    HEAVY_GATE_PRIMITIVES,
    LIGHT_GATE_PRIMITIVES,
    PRIMITIVE_REGISTRY,
)

_RUNNER_TIMEOUT = 20.0


# ---------------------------------------------------------------------------
# 1. Pure constant assertions
# ---------------------------------------------------------------------------


def test_gated_primitives_includes_verify() -> None:
    """Gap B invariant: verify must be in GATED_PRIMITIVES."""
    assert "verify" in GATED_PRIMITIVES, (
        f"'verify' missing from GATED_PRIMITIVES={GATED_PRIMITIVES!r}"
    )


def test_light_gate_contains_only_verify() -> None:
    """LIGHT_GATE_PRIMITIVES must be exactly {verify}."""
    assert LIGHT_GATE_PRIMITIVES == frozenset({"verify"}), (
        f"LIGHT_GATE_PRIMITIVES={LIGHT_GATE_PRIMITIVES!r}, expected {{'verify'}}"
    )


def test_heavy_gate_does_not_contain_verify() -> None:
    """verify is light-gate; it must NOT appear in HEAVY_GATE_PRIMITIVES."""
    assert "verify" not in HEAVY_GATE_PRIMITIVES, (
        f"'verify' must not be in HEAVY_GATE_PRIMITIVES={HEAVY_GATE_PRIMITIVES!r}"
    )


def test_heavy_gate_contains_submit_and_subscribe() -> None:
    """submit and subscribe are side-effecting — must be in HEAVY_GATE_PRIMITIVES."""
    assert "submit" in HEAVY_GATE_PRIMITIVES
    assert "subscribe" in HEAVY_GATE_PRIMITIVES


def test_light_heavy_partition_is_disjoint() -> None:
    """Light and heavy gates must be disjoint."""
    overlap = LIGHT_GATE_PRIMITIVES & HEAVY_GATE_PRIMITIVES
    assert overlap == frozenset(), f"Overlap between light/heavy gates: {overlap!r}"


def test_gated_equals_light_union_heavy() -> None:
    """GATED_PRIMITIVES must equal LIGHT_GATE_PRIMITIVES | HEAVY_GATE_PRIMITIVES."""
    assert GATED_PRIMITIVES == LIGHT_GATE_PRIMITIVES | HEAVY_GATE_PRIMITIVES, (
        f"GATED={GATED_PRIMITIVES!r} != LIGHT|HEAVY="
        f"{LIGHT_GATE_PRIMITIVES | HEAVY_GATE_PRIMITIVES!r}"
    )


def test_auto_allowed_primitives_are_lookup_and_resolve_location() -> None:
    """lookup and resolve_location must NOT be gated (fully auto-allowed)."""
    all_primitives = frozenset(PRIMITIVE_REGISTRY.keys())
    auto_allowed = all_primitives - GATED_PRIMITIVES
    assert auto_allowed == frozenset({"lookup", "resolve_location"}), (
        f"Auto-allowed set={auto_allowed!r}, expected {{'lookup', 'resolve_location'}}"
    )


# ---------------------------------------------------------------------------
# 2. IPC integration — verify enters permission bridge
# ---------------------------------------------------------------------------


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
                try:
                    frames.append(json.loads(stripped))
                except json.JSONDecodeError:
                    pass
        return frames


class _FakeStdout:
    def __init__(self) -> None:
        self.buffer = _CaptureBuf()

    def write(self, data: str) -> None:
        """Direct write path used by emit_manifest (writes str, not bytes)."""
        self.buffer.write(data.encode())

    def flush(self) -> None:
        pass


class _VerifyOnceLLMClient:
    """Fake LLM that emits exactly one verify tool_call then finishes."""

    _class_turn: int = 0
    _args_json: str = "{}"

    def __init__(self, config: Any) -> None:
        pass

    async def stream(  # noqa: PLR0913
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
            call_id = f"call-verify-{uuid.uuid4().hex[:8]}"
            yield StreamEvent(
                type="tool_call_delta",
                tool_call_index=0,
                tool_call_id=call_id,
                function_name="verify",
                function_args_delta=type(self)._args_json,
            )
            yield StreamEvent(type="done")
        else:
            yield StreamEvent(type="content_delta", content="검증 완료.")
            yield StreamEvent(type="done")


@pytest.mark.asyncio
async def test_verify_call_emits_permission_request_frame(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """When the LLM emits a verify() call, the IPC dispatcher must emit a
    PermissionRequestFrame to the TUI — i.e. verify now enters the
    _check_permission_gate bridge, not the auto-allow shortcut.

    The test times out the permission bridge (no TUI responds) and checks
    that a ``permission_request`` frame was emitted before the timeout.
    """
    from kosmos.ipc import stdio as stdio_mod
    from kosmos.ipc.frame_schema import SessionEventFrame

    monkeypatch.setattr(stdio_mod, "_stdout_lock", None)

    # Redirect consent writes to tmp_path so we don't pollute ~/.kosmos
    import pathlib

    monkeypatch.setattr(
        pathlib.Path,
        "home",
        classmethod(lambda cls: tmp_path),  # type: ignore[arg-type]
    )

    fake_stdout = _FakeStdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    _VerifyOnceLLMClient._class_turn = 0
    _VerifyOnceLLMClient._args_json = json.dumps(
        {
            "tool_id": "mock_verify_module_modid",
            "params": {
                "scope_list": ["lookup:test"],
                "purpose_ko": "테스트",
                "purpose_en": "test",
            },
        }
    )

    class _FakeLLMConfig:
        pass

    import kosmos.llm.client as llm_client_mod
    import kosmos.llm.config as llm_config_mod

    monkeypatch.setattr(llm_client_mod, "LLMClient", _VerifyOnceLLMClient)
    monkeypatch.setattr(llm_config_mod, "LLMClientConfig", _FakeLLMConfig)

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

    frame = _make_chat_request("verify modid")
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
            "test_verify_gated: IPC loop exited: %s", exc
        )
    finally:
        if not r_file.closed:
            r_file.close()

    frames = fake_stdout.buffer.as_frames()
    kinds = [f.get("kind") for f in frames]

    # The key assertion: a permission_request must have been emitted.
    assert "permission_request" in kinds, (
        f"Expected permission_request frame for verify call, got kinds={kinds!r}"
    )

    perm_frames = [f for f in frames if f.get("kind") == "permission_request"]
    assert len(perm_frames) >= 1
    pf = perm_frames[0]
    assert pf.get("primitive_kind") == "verify", (
        f"permission_request.primitive_kind must be 'verify', got {pf.get('primitive_kind')!r}"
    )
    # verify is LIGHT_GATE → risk_level must be "low"
    assert pf.get("risk_level") == "low", (
        f"verify permission_request.risk_level must be 'low', got {pf.get('risk_level')!r}"
    )
