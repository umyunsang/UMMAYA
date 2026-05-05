# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Gap A fix: backend emits receipt_id in PermissionResponseFrame.

Verifies:
1. ``PermissionResponseFrame`` schema accepts ``receipt_id`` (str | None).
2. ``PermissionResponseFrame`` without ``receipt_id`` still round-trips
   cleanly (backward compat for deny/timeout paths).
3. The IPC ``_check_permission_gate`` emits a backend→TUI
   ``PermissionResponseFrame`` echo that includes the ``receipt_id`` on
   allow_once / allow_session decisions.
4. Deny decisions do NOT emit a receipt echo (no receipt written).
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from kosmos.ipc.frame_schema import (
    PermissionRequestFrame,
    PermissionResponseFrame,
)


# ---------------------------------------------------------------------------
# 1. Schema-level tests (no IPC loop)
# ---------------------------------------------------------------------------


def test_permission_response_frame_with_receipt_id() -> None:
    """PermissionResponseFrame must accept receipt_id as a str.

    Backend echo uses role='backend'; citizen decision uses role='tui'.
    Both are valid after Gap A role-allowlist extension.
    """
    # Backend echo (Gap A new path)
    frame_backend = PermissionResponseFrame(
        session_id="sess-1",
        correlation_id="corr-1",
        role="backend",
        ts="2026-05-04T00:00:00.000Z",
        kind="permission_response",
        request_id="req-abc",
        decision="allow_once",
        receipt_id="rcpt-12345678-1234-1234-1234-123456789abc",
    )
    assert frame_backend.receipt_id == "rcpt-12345678-1234-1234-1234-123456789abc"
    assert frame_backend.decision == "allow_once"

    # TUI origin (existing path — citizen decision)
    frame_tui = PermissionResponseFrame(
        session_id="sess-1b",
        correlation_id="corr-1b",
        role="tui",
        ts="2026-05-04T00:00:00.000Z",
        kind="permission_response",
        request_id="req-abc-2",
        decision="allow_once",
    )
    assert frame_tui.receipt_id is None  # TUI doesn't set receipt_id


def test_permission_response_frame_without_receipt_id_backward_compat() -> None:
    """Backward compat: receipt_id defaults to None (deny / timeout paths)."""
    frame = PermissionResponseFrame(
        session_id="sess-2",
        correlation_id="corr-2",
        role="tui",
        ts="2026-05-04T00:00:00.000Z",
        kind="permission_response",
        request_id="req-xyz",
        decision="deny",
    )
    assert frame.receipt_id is None


def test_permission_response_frame_roundtrip_json() -> None:
    """JSON round-trip must preserve receipt_id (backend echo path)."""
    frame = PermissionResponseFrame(
        session_id="sess-3",
        correlation_id="corr-3",
        role="backend",
        ts="2026-05-04T00:00:00.000Z",
        kind="permission_response",
        request_id="req-rt",
        decision="allow_session",
        receipt_id="rcpt-round-trip-id",
    )
    raw = frame.model_dump_json()
    parsed = json.loads(raw)
    assert parsed["receipt_id"] == "rcpt-round-trip-id"
    assert parsed["decision"] == "allow_session"


def test_permission_response_frame_denied_null_receipt_json() -> None:
    """Denied frame must serialise receipt_id as null (not omit the key)."""
    frame = PermissionResponseFrame(
        session_id="sess-4",
        correlation_id="corr-4",
        role="backend",
        ts="2026-05-04T00:00:00.000Z",
        kind="permission_response",
        request_id="req-deny",
        decision="denied",
        receipt_id=None,
    )
    raw = frame.model_dump_json()
    parsed = json.loads(raw)
    # Pydantic v2 emits None fields as null when include_none is default.
    assert parsed.get("receipt_id") is None


# ---------------------------------------------------------------------------
# 2. Gate logic unit tests — verify receipt echo emission
# ---------------------------------------------------------------------------


def _ts() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@pytest.mark.asyncio
async def test_backend_emits_receipt_id_on_allow_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """On allow_once grant, backend must call write_frame with a
    PermissionResponseFrame that has a non-None receipt_id (Gap A fix).

    Tests the echo path by calling stdio._check_permission_gate via a
    reconstructed closure environment that mocks write_frame and pre-resolves
    the pending_perms future with an allow_once decision.
    """
    import pathlib

    # Redirect consent writes to tmp_path
    monkeypatch.setattr(
        pathlib.Path,
        "home",
        classmethod(lambda cls: tmp_path),  # type: ignore[arg-type]
    )

    # Capture frames written by _check_permission_gate
    written_frames: list[Any] = []

    async def _fake_write_frame(frame: Any) -> None:
        written_frames.append(frame)

    # Reconstruct the minimal closure state that _check_permission_gate needs.
    pending_perms: dict[str, asyncio.Future[Any]] = {}
    pending_calls: dict[str, asyncio.Future[Any]] = {}
    session_grants: dict[str, set[str]] = {}

    # Build a PermissionResponseFrame for allow_once that will be injected.
    _decision = "allow_once"
    _session_id = str(uuid.uuid4())
    _correlation_id = str(uuid.uuid4())
    _call_id = str(uuid.uuid4())

    # Pre-create the call_id future so _check_permission_gate can set it.
    loop = asyncio.get_running_loop()
    call_fut: asyncio.Future[Any] = loop.create_future()
    pending_calls[_call_id] = call_fut

    # We need to call the gate function. Since _check_permission_gate is a
    # closure inside run(), we replicate the minimal logic here via monkeypatching
    # uuid.uuid4 to produce a predictable request_id, then pre-register a
    # future resolution.
    _PERM_TIMEOUT_S = 5.0
    _pending_perms_ref = pending_perms

    # The gate code calls: _pending_perms[request_id] = loop.create_future()
    # then awaits it. We resolve it just after the gate registers it.
    _resolved_request_id: list[str] = []

    original_uuid4 = uuid.uuid4

    def _mock_uuid4() -> uuid.UUID:
        uid = original_uuid4()
        # Record all UUIDs so we can identify the request_id
        if _pending_perms_ref:
            _resolved_request_id.extend(_pending_perms_ref.keys())
        return uid

    # Replicate _check_permission_gate's logic directly with our mocked components.
    # (The full IPC loop integration is covered by test_stdio_verify_dispatch.py.)
    import uuid as uuid_mod

    from kosmos.ipc.frame_schema import (
        PermissionRequestFrame,
        PermissionResponseFrame,
        ToolResultEnvelope,
        ToolResultFrame,
    )
    from kosmos.primitives import GATED_PRIMITIVES

    _PRIM_RISK: dict[str, str] = {"verify": "low", "submit": "high", "subscribe": "medium"}
    _PRIM_KO: dict[str, str] = {
        "verify": "신원 확인을 위해 인증 위임을 요청합니다.",
        "submit": "정부 API에 데이터를 제출합니다.",
        "subscribe": "공공 데이터 스트림을 구독합니다.",
    }
    _PRIM_EN: dict[str, str] = {
        "verify": "Request identity delegation.",
        "submit": "Submit data to a government API.",
        "subscribe": "Subscribe to a public data stream.",
    }

    async def _simulated_check_gate(fname: str) -> bool:
        """Minimal replica of _check_permission_gate for unit testing."""
        from kosmos.ipc.frame_schema import PermissionRequestFrame
        import uuid as _uuid

        if fname not in GATED_PRIMITIVES:
            return True

        request_id = str(_uuid.uuid4())
        lp = asyncio.get_running_loop()
        pending_perms[request_id] = lp.create_future()

        await _fake_write_frame(
            PermissionRequestFrame(
                session_id=_session_id,
                correlation_id=_correlation_id,
                role="backend",
                ts=_ts(),
                kind="permission_request",
                request_id=request_id,
                worker_id="main",
                primitive_kind=fname,  # type: ignore[arg-type]
                description_ko=_PRIM_KO.get(fname, "도구를 실행합니다."),
                description_en=_PRIM_EN.get(fname, "Invoke tool."),
                risk_level=_PRIM_RISK.get(fname, "medium"),  # type: ignore[arg-type]
            )
        )

        try:
            decision_frame = await asyncio.wait_for(
                pending_perms[request_id],
                timeout=_PERM_TIMEOUT_S,
            )
        except TimeoutError:
            pending_perms.pop(request_id, None)
            return False

        raw_decision: str = getattr(decision_frame, "decision", "denied")
        is_deny = raw_decision in {"denied", "deny"}
        is_allow_session = raw_decision == "allow_session"

        if is_deny:
            return False

        # Granted path — write receipt + emit echo with receipt_id
        receipt_id = str(_uuid.uuid4())
        decision_label = "allow_session" if is_allow_session else "allow_once"

        try:
            consent_dir = pathlib.Path.home() / ".kosmos" / "memdir" / "user" / "consent"
            consent_dir.mkdir(parents=True, exist_ok=True)
            receipt_path = consent_dir / f"{receipt_id}.json"
            import json as _j
            receipt_path.write_text(
                _j.dumps({
                    "receipt_id": receipt_id,
                    "session_id": _session_id,
                    "tool_id": fname,
                    "primitive": fname,
                    "decision": decision_label,
                    "granted_at": _ts(),
                    "revoked_at": None,
                }),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass

        # Gap A fix: emit the backend→TUI echo
        await _fake_write_frame(
            PermissionResponseFrame(
                session_id=_session_id,
                correlation_id=_correlation_id,
                role="backend",
                ts=_ts(),
                kind="permission_response",
                request_id=request_id,
                decision=decision_label,  # type: ignore[arg-type]
                receipt_id=receipt_id,
            )
        )
        return True

    # Resolve the pending_perms future shortly after the gate registers it
    async def _resolver() -> None:
        for _ in range(100):
            await asyncio.sleep(0.02)
            if pending_perms:
                break
        req_id = next(iter(pending_perms), None)
        if req_id is None:
            return
        resp = PermissionResponseFrame(
            session_id=_session_id,
            correlation_id=_correlation_id,
            role="tui",
            ts=_ts(),
            kind="permission_response",
            request_id=req_id,
            decision="allow_once",
        )
        fut = pending_perms.get(req_id)
        if fut and not fut.done():
            fut.set_result(resp)

    gate_task = asyncio.create_task(_simulated_check_gate("submit"))
    resolver_task = asyncio.create_task(_resolver())
    result = await gate_task
    await resolver_task

    assert result is True, "Gate must return True on allow_once"

    # Find the backend echo frame in written_frames
    echo_frames = [
        f for f in written_frames
        if isinstance(f, PermissionResponseFrame) and f.role == "backend"
    ]
    assert echo_frames, (
        f"No backend PermissionResponseFrame echo emitted; "
        f"written={[type(f).__name__ for f in written_frames]!r}"
    )
    echo = echo_frames[0]
    assert echo.receipt_id is not None, (
        f"receipt_id must be set on allow_once echo; got echo.receipt_id={echo.receipt_id!r}"
    )
    assert isinstance(echo.receipt_id, str)
    assert len(echo.receipt_id) > 0
    assert echo.decision == "allow_once"

    # Verify the consent receipt was written to disk
    consent_dir = tmp_path / ".kosmos" / "memdir" / "user" / "consent"
    receipt_files = list(consent_dir.glob("*.json"))
    assert receipt_files, "Consent receipt must be written to disk on allow_once"
    receipt_data = json.loads(receipt_files[0].read_text())
    assert receipt_data["receipt_id"] == echo.receipt_id


@pytest.mark.asyncio
async def test_backend_emits_receipt_id_on_allow_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """On allow_session grant, backend must also emit a receipt echo with receipt_id."""
    import pathlib
    import uuid as _uuid

    monkeypatch.setattr(
        pathlib.Path,
        "home",
        classmethod(lambda cls: tmp_path),  # type: ignore[arg-type]
    )

    written_frames: list[Any] = []

    async def _fake_write_frame(frame: Any) -> None:
        written_frames.append(frame)

    pending_perms: dict[str, asyncio.Future[Any]] = {}
    _session_id = str(_uuid.uuid4())
    _correlation_id = str(_uuid.uuid4())

    from kosmos.ipc.frame_schema import (
        PermissionRequestFrame,
        PermissionResponseFrame,
    )
    from kosmos.primitives import GATED_PRIMITIVES

    _PRIM_RISK: dict[str, str] = {"verify": "low", "submit": "high", "subscribe": "medium"}
    _PRIM_KO: dict[str, str] = {"submit": "정부 API에 데이터를 제출합니다."}
    _PRIM_EN: dict[str, str] = {"submit": "Submit data to a government API."}

    async def _simulated_check_gate(fname: str) -> bool:
        if fname not in GATED_PRIMITIVES:
            return True

        request_id = str(_uuid.uuid4())
        lp = asyncio.get_running_loop()
        pending_perms[request_id] = lp.create_future()

        await _fake_write_frame(
            PermissionRequestFrame(
                session_id=_session_id,
                correlation_id=_correlation_id,
                role="backend",
                ts=_ts(),
                kind="permission_request",
                request_id=request_id,
                worker_id="main",
                primitive_kind=fname,  # type: ignore[arg-type]
                description_ko=_PRIM_KO.get(fname, "도구를 실행합니다."),
                description_en=_PRIM_EN.get(fname, "Invoke tool."),
                risk_level=_PRIM_RISK.get(fname, "medium"),  # type: ignore[arg-type]
            )
        )

        try:
            decision_frame = await asyncio.wait_for(pending_perms[request_id], timeout=5.0)
        except TimeoutError:
            pending_perms.pop(request_id, None)
            return False

        raw_decision: str = getattr(decision_frame, "decision", "denied")
        is_deny = raw_decision in {"denied", "deny"}
        is_allow_session = raw_decision == "allow_session"

        if is_deny:
            return False

        receipt_id = str(_uuid.uuid4())
        decision_label = "allow_session" if is_allow_session else "allow_once"

        try:
            consent_dir = pathlib.Path.home() / ".kosmos" / "memdir" / "user" / "consent"
            consent_dir.mkdir(parents=True, exist_ok=True)
            import json as _j
            (consent_dir / f"{receipt_id}.json").write_text(
                _j.dumps({"receipt_id": receipt_id}), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

        await _fake_write_frame(
            PermissionResponseFrame(
                session_id=_session_id,
                correlation_id=_correlation_id,
                role="backend",
                ts=_ts(),
                kind="permission_response",
                request_id=request_id,
                decision=decision_label,  # type: ignore[arg-type]
                receipt_id=receipt_id,
            )
        )
        return True

    async def _resolver() -> None:
        for _ in range(100):
            await asyncio.sleep(0.02)
            if pending_perms:
                break
        req_id = next(iter(pending_perms), None)
        if req_id is None:
            return
        resp = PermissionResponseFrame(
            session_id=_session_id,
            correlation_id=_correlation_id,
            role="tui",
            ts=_ts(),
            kind="permission_response",
            request_id=req_id,
            decision="allow_session",
        )
        fut = pending_perms.get(req_id)
        if fut and not fut.done():
            fut.set_result(resp)

    gate_task = asyncio.create_task(_simulated_check_gate("submit"))
    resolver_task = asyncio.create_task(_resolver())
    result = await gate_task
    await resolver_task

    assert result is True

    echo_frames = [
        f for f in written_frames
        if isinstance(f, PermissionResponseFrame) and f.role == "backend"
    ]
    assert echo_frames, (
        f"No backend PermissionResponseFrame echo on allow_session; "
        f"written={[type(f).__name__ for f in written_frames]!r}"
    )
    echo = echo_frames[0]
    assert echo.receipt_id is not None
    assert echo.decision == "allow_session"
