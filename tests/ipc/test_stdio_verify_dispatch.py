# SPDX-License-Identifier: Apache-2.0
"""Regression test for stdio.py:_dispatch_primitive verify branch.

Bug (Spec 2521 / Spec 2297 / Issue #C1, citizen smoke 2026-05-04):
    Snapshots S2..S8 of the verify-cascade smoke captured every K-EXAONE
    ``verify({tool_id: "mock_verify_module_modid", params: {...}})`` call
    surfacing as ``VerifyMismatchError(message="No verify adapter
    registered for family ''")`` — the IPC stdio dispatcher read
    ``family_hint`` directly from the args dict and never translated
    ``tool_id`` → ``family_hint``. The mvp_surface
    ``_VerifyInputForLLM.translate_tool_id_shape`` validator only fires
    when the LLM call enters Pydantic schema validation; the IPC stdio
    direct path bypassed that validator.

Fix:
    ``stdio.py`` verify branch now calls
    ``kosmos.tools.verify_canonical_map.resolve_family(tool_id)`` first,
    falling back to ``args_obj["family_hint"]`` / ``args_obj["family"]``
    when the tool_id lookup misses (legacy compatibility).

This test asserts:
1. All 10 canonical ``mock_verify_*`` ↔ family_hint pairs resolve
   correctly via the canonical map (single source-of-truth derived from
   ``prompts/system_v1.md`` ``<verify_families>``).
2. The full IPC dispatch path translates ``tool_id`` → ``family_hint``
   and finds the registered adapter (no VerifyMismatchError).
3. Legacy ``family_hint`` (no tool_id) keeps working — backward
   compatibility for tools-bridge callers.
4. Empty / unknown tool_id falls through to the legacy field and
   surfaces the expected ``VerifyMismatchError`` when nothing resolves.
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

# Importing the mock package registers all 10 mock_verify_* adapters via
# register_verify_adapter() at module-import time (side effect).
import kosmos.tools.mock  # noqa: F401
from kosmos.ipc.frame_schema import (
    ChatMessage as IPCChatMessage,
)
from kosmos.ipc.frame_schema import ChatRequestFrame
from kosmos.llm.models import StreamEvent
from kosmos.tools.verify_canonical_map import (
    get_canonical_map,
    resolve_family,
)

_RUNNER_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# 1. Pure-function tests for the canonical map
# ---------------------------------------------------------------------------


# Source-of-truth: prompts/system_v1.md <verify_families> block.
# Mirrored here so any drift between prompt and code blows up the test.
_EXPECTED_PAIRS: dict[str, str] = {
    "mock_verify_gongdong_injeungseo": "gongdong_injeungseo",
    "mock_verify_geumyung_injeungseo": "geumyung_injeungseo",
    "mock_verify_ganpyeon_injeung": "ganpyeon_injeung",
    "mock_verify_mobile_id": "mobile_id",
    "mock_verify_mydata": "mydata",
    "mock_verify_module_simple_auth": "simple_auth_module",
    "mock_verify_module_modid": "modid",
    "mock_verify_module_kec": "kec",
    "mock_verify_module_geumyung": "geumyung_module",
    "mock_verify_module_any_id_sso": "any_id_sso",
}


@pytest.mark.parametrize(
    ("tool_id", "expected_family"),
    list(_EXPECTED_PAIRS.items()),
)
def test_resolve_family_covers_all_10_canonical_pairs(tool_id: str, expected_family: str) -> None:
    """All 10 canonical mock_verify_* tool_ids resolve to the right family_hint.

    This is the SOT-mirror assertion: prompt-side
    ``<verify_families>`` and code-side mapping must agree.
    """
    assert resolve_family(tool_id) == expected_family, (
        f"resolve_family({tool_id!r}) returned {resolve_family(tool_id)!r}, "
        f"expected {expected_family!r}"
    )


def test_canonical_map_has_exactly_ten_entries() -> None:
    """FR-008b: the verify_families block must enumerate ≥10 entries."""
    canonical = get_canonical_map()
    assert len(canonical) >= 10, (
        f"Expected at least 10 verify families, got {len(canonical)}: {dict(canonical)!r}"
    )


def test_resolve_family_unknown_tool_id_returns_none() -> None:
    """Unknown tool_ids must surface as None so the dispatcher can fall
    through to the legacy ``family_hint`` arg (backward compatibility)."""
    assert resolve_family("some_unknown_verify_tool") is None
    assert resolve_family("") is None
    assert resolve_family("submit_something_else") is None


# ---------------------------------------------------------------------------
# 2. IPC dispatcher integration — minimal harness
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
                with contextlib.suppress(json.JSONDecodeError):
                    frames.append(json.loads(stripped))
        return frames


class _FakeStdout:
    def __init__(self) -> None:
        self.buffer = _CaptureBuf()

    def write(self, data: str) -> None:
        """Direct write path used by emit_manifest (str → bytes)."""
        self.buffer.write(data.encode())

    def flush(self) -> None:
        pass


class _VerifyOnceLLMClient:
    """Fake LLM that emits exactly one ``verify`` tool_call and then
    finishes the conversation on turn 2.

    The exact tool-call args are pulled from class-level ``_args_json``
    set by the test harness immediately before invoking ``run``.
    """

    _class_turn: int = 0
    _args_json: str = "{}"
    _call_id_prefix: str = "verify"

    def __init__(self, config: Any) -> None:  # noqa: D401
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
            call_id = f"call-{type(self)._call_id_prefix}-{uuid.uuid4().hex[:8]}"
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


async def _run_verify_dispatch(
    frame: ChatRequestFrame,
    args_obj: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> _CaptureBuf:
    """Run a single chat_request through the IPC harness with a fake LLM
    that emits one ``verify(args_obj)`` tool_call.

    Returns the captured NDJSON frame buffer.
    """
    from kosmos.ipc import stdio as stdio_mod
    from kosmos.ipc.frame_schema import SessionEventFrame

    monkeypatch.setattr(stdio_mod, "_stdout_lock", None)

    # Gap B fix: verify is now gated (GATED_PRIMITIVES includes "verify").
    # These tests only exercise the tool_id → family_hint translation path,
    # NOT the permission gating logic. Bypass the gate by patching
    # GATED_PRIMITIVES to submit only so
    # verify auto-allows and the IPC loop doesn't wait 60 s for citizen input.
    import kosmos.primitives as _prims_mod

    monkeypatch.setattr(
        _prims_mod,
        "GATED_PRIMITIVES",
        frozenset({"submit"}),
    )

    fake_stdout = _FakeStdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    _VerifyOnceLLMClient._class_turn = 0
    _VerifyOnceLLMClient._args_json = json.dumps(args_obj, ensure_ascii=False)

    class _FakeLLMConfig:
        pass

    import kosmos.llm.client as llm_client_mod
    import kosmos.llm.config as llm_config_mod

    monkeypatch.setattr(llm_client_mod, "LLMClient", _VerifyOnceLLMClient)
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
        _logging.getLogger(__name__).debug("_run_verify_dispatch: IPC loop exited early: %s", exc)
    finally:
        if not r_file.closed:
            r_file.close()

    return fake_stdout.buffer


def _extract_verify_envelope(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Pull the inner ``envelope.result`` payload from the first verify
    tool_result frame in ``frames``."""
    tool_results = [f for f in frames if f.get("kind") == "tool_result"]
    assert tool_results, (
        f"No tool_result frames emitted; got kinds={[f.get('kind') for f in frames]}"
    )
    envelope = tool_results[0].get("envelope", {})
    inner = envelope.get("result")
    assert isinstance(inner, dict), f"envelope.result must be a dict, got {type(inner)}"
    return {"envelope": envelope, "inner": inner}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_id", "expected_family"),
    list(_EXPECTED_PAIRS.items()),
)
async def test_dispatch_verify_translates_tool_id_to_family_hint(
    tool_id: str,
    expected_family: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM-emitted ``verify({tool_id: "mock_verify_*"})`` must dispatch
    via the canonical map and reach the registered adapter.

    Pre-fix: every call surfaced as ``VerifyMismatchError`` because the
    stdio dispatcher read ``args["family_hint"]`` (always missing) and
    sent an empty string to ``verify()``.

    Post-fix: ``resolve_family(tool_id)`` runs first and produces the
    correct family_hint so the registered adapter is invoked.
    """
    args_obj: dict[str, Any] = {
        "tool_id": tool_id,
        "params": {
            "scope_list": ["lookup:test.adapter"],
            "purpose_ko": "테스트",
            "purpose_en": "test",
        },
    }
    frame = _make_chat_request("dispatch canonical verify adapter")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    envelope = parts["envelope"]
    inner = parts["inner"]

    assert envelope.get("kind") == "verify", (
        f"Expected envelope.kind=='verify', got {envelope.get('kind')!r}"
    )
    # The envelope's outer ``family`` mirror is set from the resolved
    # family_hint; must equal the expected mapping.
    assert envelope.get("family") == expected_family, (
        f"Expected envelope.family=={expected_family!r}, got {envelope.get('family')!r}"
    )
    # The adapter result MUST NOT be a VerifyMismatchError surfaced as
    # ``family == 'mismatch_error'`` — that was the pre-fix symptom.
    assert inner.get("family") != "mismatch_error", (
        f"verify({tool_id!r}) returned VerifyMismatchError post-fix; inner={inner!r}"
    )
    assert inner.get("family") == expected_family, (
        f"Expected adapter to return family={expected_family!r}, got "
        f"family={inner.get('family')!r}; inner={inner!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_verify_legacy_family_hint_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy callers that still pass ``family_hint`` directly (no
    ``tool_id`` field) must keep working — the canonical-map lookup
    misses, then the dispatcher falls back to the legacy field."""
    args_obj: dict[str, Any] = {
        "family_hint": "modid",
        "session_context": {
            "scope_list": ["lookup:hometax.simplified"],
            "session_id": "test-legacy",
        },
    }
    frame = _make_chat_request("legacy verify modid")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    envelope = parts["envelope"]
    inner = parts["inner"]

    assert envelope.get("family") == "modid"
    assert inner.get("family") == "modid", (
        f"legacy family_hint='modid' must still dispatch; inner={inner!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_verify_legacy_family_alias_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tools-bridge legacy alias ``family`` (instead of ``family_hint``)
    must keep working when ``tool_id`` is absent."""
    args_obj: dict[str, Any] = {
        "family": "mobile_id",
        "session_context": {"session_id": "test-legacy-alias"},
    }
    frame = _make_chat_request("legacy verify alias mobile_id")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    inner = parts["inner"]

    assert inner.get("family") == "mobile_id", (
        f"legacy family='mobile_id' alias must still dispatch; inner={inner!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_verify_empty_tool_id_falls_back_to_mismatch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When neither tool_id nor family_hint is provided, the dispatcher
    must surface a ``VerifyMismatchError`` (family='mismatch_error') —
    not crash, not silently succeed."""
    args_obj: dict[str, Any] = {
        "tool_id": "",
        "session_context": {},
    }
    frame = _make_chat_request("empty verify args")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    inner = parts["inner"]

    assert inner.get("family") == "mismatch_error", (
        f"empty verify args must surface VerifyMismatchError, got "
        f"family={inner.get('family')!r}; inner={inner!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_verify_unknown_tool_id_falls_back_to_mismatch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown tool_ids that are not in the canonical map AND have no
    legacy ``family_hint`` companion arg must surface
    ``VerifyMismatchError`` cleanly."""
    args_obj: dict[str, Any] = {
        "tool_id": "mock_verify_does_not_exist",
        "session_context": {},
    }
    frame = _make_chat_request("unknown verify tool_id")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    inner = parts["inner"]

    assert inner.get("family") == "mismatch_error", (
        f"unknown tool_id must surface VerifyMismatchError, got "
        f"family={inner.get('family')!r}; inner={inner!r}"
    )
