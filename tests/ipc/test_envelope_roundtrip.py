# SPDX-License-Identifier: Apache-2.0
"""Envelope round-trip tests for all 20 IPC frame kinds (Spec 032 T019 + Epic #1636 P5).

Tests:
1. Serialize via Pydantic model_dump_json, parse back via TypeAdapter — byte-equal.
2. emit_ndjson + parse_ndjson_line round-trip for every arm.
3. Invariants E1-E6 reject bad inputs.
4. Frame discriminator correctly routes to the right Pydantic model.
"""

from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from ummaya.ipc.envelope import emit_ndjson, parse_ndjson_line
from ummaya.ipc.frame_schema import (
    AssistantChunkFrame,
    BackpressureSignalFrame,
    ChatMessage,
    ChatRequestFrame,
    CoordinatorPhaseFrame,
    ErrorFrame,
    FrameTrailer,
    HeartbeatFrame,
    IPCFrame,
    NotificationPushFrame,
    PayloadDeltaFrame,
    PayloadEndFrame,
    PayloadStartFrame,
    PermissionRequestFrame,
    PermissionResponseFrame,
    PluginOpFrame,
    ResumeRejectedFrame,
    ResumeRequestFrame,
    ResumeResponseFrame,
    SessionEventFrame,
    ToolCallFrame,
    ToolResultEnvelope,
    ToolResultFrame,
    UserInputFrame,
    WorkerStatusFrame,
    ipc_frame_json_schema,
)

# ---------------------------------------------------------------------------
# Test fixture: one canonical example per frame kind
# ---------------------------------------------------------------------------

_BASE = {
    "session_id": "sess-0001",
    "correlation_id": "019da5b0-e60d-71a0-a393-000000000001",
    "ts": "2026-04-19T12:00:00.000Z",
    "frame_seq": 0,
    "transaction_id": None,
    "trailer": None,
}

ALL_FRAMES: list[IPCFrame] = [
    # 1. user_input
    UserInputFrame(**_BASE, role="tui", kind="user_input", text="서울 강남구 응급실 병상"),
    # 2a. chat_request (Spec 1978 ADR-0001)
    ChatRequestFrame(
        **_BASE,
        role="tui",
        kind="chat_request",
        messages=[ChatMessage(role="user", content="서울 강남구 응급실 병상")],
        tools=[],
    ),
    # 2. assistant_chunk
    AssistantChunkFrame(
        **_BASE,
        role="backend",
        kind="assistant_chunk",
        message_id="msg-001",
        delta="안녕하세요",
        done=False,
    ),
    # 3. tool_call
    ToolCallFrame(
        **_BASE,
        role="backend",
        kind="tool_call",
        call_id="call-001",
        name="find",
        arguments={"mode": "fetch", "tool_id": "kma_forecast"},
    ),
    # 4. tool_result
    ToolResultFrame(
        **{**_BASE, "trailer": FrameTrailer(final=True)},
        role="backend",
        kind="tool_result",
        call_id="call-001",
        envelope=ToolResultEnvelope(kind="find", data=[]),
    ),
    # 5. coordinator_phase
    CoordinatorPhaseFrame(**_BASE, role="backend", kind="coordinator_phase", phase="Research"),
    # 6. worker_status
    WorkerStatusFrame(
        **_BASE,
        role="backend",
        kind="worker_status",
        worker_id="w1",
        role_id="transport-specialist",
        current_primitive="find",
        status="running",
    ),
    # 7. permission_request
    PermissionRequestFrame(
        **_BASE,
        role="backend",
        kind="permission_request",
        request_id="req-001",
        worker_id="w1",
        primitive_kind="send",
        description_ko="민원 제출 허가 요청",
        description_en="Permission to submit civil petition",
        risk_level="high",
    ),
    # 8. permission_response
    PermissionResponseFrame(
        **_BASE, role="tui", kind="permission_response", request_id="req-001", decision="granted"
    ),
    # 9. session_event
    SessionEventFrame(**_BASE, role="tui", kind="session_event", event="new", payload={}),
    # 10. error
    ErrorFrame(
        **{**_BASE, "trailer": FrameTrailer(final=True)},
        role="backend",
        kind="error",
        code="backend_crash",
        message="Internal error",
        details={},
    ),
    # 11. payload_start
    PayloadStartFrame(
        **_BASE,
        role="backend",
        kind="payload_start",
        content_type="text/markdown",
        estimated_bytes=None,
    ),
    # 12. payload_delta
    PayloadDeltaFrame(
        **_BASE, role="backend", kind="payload_delta", delta_seq=0, payload="서울 강남구"
    ),
    # 13. payload_end
    PayloadEndFrame(
        **{**_BASE, "trailer": FrameTrailer(final=True)},
        role="backend",
        kind="payload_end",
        delta_count=1,
        status="ok",
    ),
    # 14. backpressure
    BackpressureSignalFrame(
        **_BASE,
        role="backend",
        kind="backpressure",
        signal="pause",
        source="backend_writer",
        queue_depth=64,
        hwm=64,
        hud_copy_ko="서비스 조절 중입니다",
        hud_copy_en="Service is throttled",
    ),
    # 15. resume_request
    ResumeRequestFrame(
        **_BASE,
        role="tui",
        kind="resume_request",
        last_seen_correlation_id=None,
        last_seen_frame_seq=None,
        tui_session_token="tok-abc",
    ),
    # 16. resume_response
    ResumeResponseFrame(
        **{**_BASE, "trailer": FrameTrailer(final=True)},
        role="backend",
        kind="resume_response",
        resumed_from_frame_seq=0,
        replay_count=0,
        server_session_id="sess-0001",
        heartbeat_interval_ms=30000,
    ),
    # 17. resume_rejected
    ResumeRejectedFrame(
        **{**_BASE, "trailer": FrameTrailer(final=True)},
        role="backend",
        kind="resume_rejected",
        reason="session_unknown",
        detail="세션을 찾을 수 없습니다. 새 세션을 시작해 주세요.",
    ),
    # 18. heartbeat
    HeartbeatFrame(**_BASE, role="backend", kind="heartbeat", direction="ping", peer_frame_seq=42),
    # 19. notification_push
    NotificationPushFrame(
        **_BASE,
        role="notification",
        kind="notification_push",
        subscription_id="sub-001",
        adapter_id="disaster_alert_cbs_push",
        event_guid="event-guid-001",
        payload_content_type="text/plain",
        payload="재난 경보: 서울시 강남구 폭우 경보",
    ),
    # 20. plugin_op (Epic #1636 P5)
    PluginOpFrame(
        **_BASE,
        role="tui",
        kind="plugin_op",
        op="request",
        request_op="install",
        name="seoul-subway",
    ),
]

_ADAPTER: TypeAdapter[IPCFrame] = TypeAdapter(IPCFrame)


# ---------------------------------------------------------------------------
# Test 1: All 21 kinds serialize and round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("frame", ALL_FRAMES, ids=lambda f: f.kind)
def test_pydantic_roundtrip_all_21_kinds(frame: IPCFrame) -> None:
    """Serialize via model_dump_json, validate back — byte-equal round-trip."""
    serialized = frame.model_dump_json()
    parsed = _ADAPTER.validate_json(serialized)

    # Re-serialize the parsed frame and compare
    re_serialized = parsed.model_dump_json()
    assert serialized == re_serialized, (
        f"Round-trip not byte-equal for kind={frame.kind!r}\n"
        f"  original:  {serialized}\n"
        f"  roundtrip: {re_serialized}"
    )


@pytest.mark.parametrize("frame", ALL_FRAMES, ids=lambda f: f.kind)
def test_ndjson_emit_parse_roundtrip(frame: IPCFrame) -> None:
    """emit_ndjson -> parse_ndjson_line round-trip — parsed frame equals original."""
    ndjson_line = emit_ndjson(frame)

    # Must end with exactly one newline
    assert ndjson_line.endswith("\n"), f"NDJSON line missing trailing newline for kind={frame.kind}"
    assert "\n" not in ndjson_line[:-1], (
        f"NDJSON line has internal bare newline for kind={frame.kind}"
    )

    parsed = parse_ndjson_line(ndjson_line)
    assert parsed is not None, f"parse_ndjson_line returned None for kind={frame.kind}"
    assert parsed.kind == frame.kind
    assert parsed.session_id == frame.session_id
    assert parsed.correlation_id == frame.correlation_id


# ---------------------------------------------------------------------------
# Test 2: Schema has all discriminator values
# ---------------------------------------------------------------------------


def test_schema_has_all_kinds() -> None:
    """ipc_frame_json_schema() must enumerate all current IPC kind values."""
    schema = ipc_frame_json_schema()

    expected_kinds = {
        "user_input",
        "assistant_chunk",
        "tool_call",
        "tool_result",
        "coordinator_phase",
        "worker_status",
        "permission_request",
        "permission_response",
        "session_event",
        "error",
        "payload_start",
        "payload_delta",
        "payload_end",
        "backpressure",
        "resume_request",
        "resume_response",
        "resume_rejected",
        "heartbeat",
        "notification_push",
        # Epic #1636 P5
        "plugin_op",
        # Spec 1978 ADR-0001
        "chat_request",
        # Epic ε #2296
        "adapter_manifest_sync",
        # Spec 2767 consent revoke
        "consent_revoke_request",
        "consent_revoke_response",
        # K-EXAONE reasoning/progress painting
        "progress_event",
    }

    # Pydantic generates a oneOf + discriminator schema
    mapping = schema.get("discriminator", {}).get("mapping", {})
    found_kinds = set(mapping.keys())

    assert found_kinds == expected_kinds, (
        f"Schema kinds mismatch.\n"
        f"  Missing: {expected_kinds - found_kinds}\n"
        f"  Extra:   {found_kinds - expected_kinds}"
    )


# ---------------------------------------------------------------------------
# Test 3: Invariant E1 — version must be "1.0"
# ---------------------------------------------------------------------------


def test_e1_version_hard_fail() -> None:
    """version != '1.0' must be rejected (E1)."""
    raw = {
        "version": "2.0",  # invalid
        "session_id": "s1",
        "correlation_id": "c1",
        "ts": "2026-04-19T12:00:00Z",
        "role": "tui",
        "frame_seq": 0,
        "kind": "user_input",
        "text": "hi",
    }
    with pytest.raises(ValidationError, match="version"):
        _ADAPTER.validate_python(raw)


# ---------------------------------------------------------------------------
# Test 4: Invariant E3 — role <-> kind allow-list
# ---------------------------------------------------------------------------


def test_e3_role_kind_mismatch_rejected() -> None:
    """role not in the allow-list for a kind must raise ValidationError (E3)."""
    raw = {
        "version": "1.0",
        "session_id": "s1",
        "correlation_id": "c1",
        "ts": "2026-04-19T12:00:00Z",
        "frame_seq": 0,
        "role": "tool",  # invalid for resume_request (must be tui)
        "kind": "resume_request",
        "tui_session_token": "tok-1",
    }
    with pytest.raises(ValidationError, match="role"):
        _ADAPTER.validate_python(raw)


def test_e3_notification_push_requires_notification_role() -> None:
    """notification_push must have role='notification' (E3)."""
    raw = {
        "version": "1.0",
        "session_id": "s1",
        "correlation_id": "c1",
        "ts": "2026-04-19T12:00:00Z",
        "frame_seq": 0,
        "role": "backend",  # invalid — must be "notification"
        "kind": "notification_push",
        "subscription_id": "sub-1",
        "adapter_id": "a1",
        "event_guid": "guid-1",
        "payload_content_type": "text/plain",
        "payload": "test",
    }
    with pytest.raises(ValidationError, match="role"):
        _ADAPTER.validate_python(raw)


# ---------------------------------------------------------------------------
# Test 5: Invariant E5 — correlation_id must be non-empty
# ---------------------------------------------------------------------------


def test_e5_empty_correlation_id_rejected() -> None:
    """correlation_id='' must raise ValidationError (E5)."""
    raw = {
        "version": "1.0",
        "session_id": "s1",
        "correlation_id": "",  # empty — invalid
        "ts": "2026-04-19T12:00:00Z",
        "role": "tui",
        "frame_seq": 0,
        "kind": "user_input",
        "text": "hi",
    }
    with pytest.raises(ValidationError, match="correlation_id"):
        _ADAPTER.validate_python(raw)


# ---------------------------------------------------------------------------
# Test 6: Invariant E6 — trailer.final=True only on terminal kinds
# ---------------------------------------------------------------------------


def test_e6_trailer_final_on_non_terminal_kind_rejected() -> None:
    """trailer.final=True on a non-terminal kind (e.g., heartbeat) must fail (E6)."""
    raw = {
        "version": "1.0",
        "session_id": "s1",
        "correlation_id": "c1",
        "ts": "2026-04-19T12:00:00Z",
        "role": "backend",
        "frame_seq": 0,
        "kind": "heartbeat",
        "direction": "ping",
        "peer_frame_seq": 0,
        "trailer": {"final": True},  # invalid — heartbeat is not terminal
    }
    with pytest.raises(ValidationError, match="trailer"):
        _ADAPTER.validate_python(raw)


def test_e6_trailer_final_on_terminal_kind_allowed() -> None:
    """trailer.final=True on payload_end is allowed (E6)."""
    raw = {
        "version": "1.0",
        "session_id": "s1",
        "correlation_id": "c1",
        "ts": "2026-04-19T12:00:00Z",
        "role": "backend",
        "frame_seq": 0,
        "kind": "payload_end",
        "delta_count": 3,
        "status": "ok",
        "trailer": {"final": True},
    }
    frame = _ADAPTER.validate_python(raw)
    assert frame.kind == "payload_end"
    assert frame.trailer is not None
    assert frame.trailer.final is True


# ---------------------------------------------------------------------------
# Test 7: Backpressure dual-locale requirement (FR-015)
# ---------------------------------------------------------------------------


def test_backpressure_empty_hud_copy_ko_rejected() -> None:
    """hud_copy_ko='' must fail (FR-015, min_length=1)."""
    raw = {
        "version": "1.0",
        "session_id": "s1",
        "correlation_id": "c1",
        "ts": "2026-04-19T12:00:00Z",
        "role": "backend",
        "frame_seq": 0,
        "kind": "backpressure",
        "signal": "pause",
        "source": "backend_writer",
        "queue_depth": 64,
        "hwm": 64,
        "hud_copy_ko": "",  # invalid
        "hud_copy_en": "congested",
    }
    with pytest.raises(ValidationError):
        _ADAPTER.validate_python(raw)


def test_backpressure_empty_hud_copy_en_rejected() -> None:
    """hud_copy_en='' must fail (FR-015, min_length=1)."""
    raw = {
        "version": "1.0",
        "session_id": "s1",
        "correlation_id": "c1",
        "ts": "2026-04-19T12:00:00Z",
        "role": "backend",
        "frame_seq": 0,
        "kind": "backpressure",
        "signal": "pause",
        "source": "backend_writer",
        "queue_depth": 64,
        "hwm": 64,
        "hud_copy_ko": "혼잡",
        "hud_copy_en": "",  # invalid
    }
    with pytest.raises(ValidationError):
        _ADAPTER.validate_python(raw)


# ---------------------------------------------------------------------------
# Test 8: NDJSON newline escape in payload
# ---------------------------------------------------------------------------


def test_ndjson_payload_newline_escape() -> None:
    """A payload containing a literal newline must round-trip as a real newline.

    ``json.dumps`` escapes ``\\n`` to the two-character JSON sequence ``\\n``
    so each frame occupies exactly one terminal-``\\n`` NDJSON line (FR-009),
    AND the receiver's ``parse_ndjson_line`` decodes it back to a real newline
    (no double-escape corruption).
    """
    frame = PayloadDeltaFrame(
        **_BASE, role="backend", kind="payload_delta", delta_seq=0, payload="line1\nline2"
    )
    ndjson_line = emit_ndjson(frame)

    # The emitted line must be a single NDJSON line terminated by a single "\n".
    assert ndjson_line.endswith("\n")
    assert ndjson_line.count("\n") == 1, (
        f"Expected exactly one terminal newline, got {ndjson_line.count(chr(10))}"
    )

    # Round-trip: the receiver sees the ORIGINAL newline, not a literal "\\n".
    decoded = parse_ndjson_line(ndjson_line)
    assert decoded is not None
    assert decoded.kind == "payload_delta"
    assert decoded.payload == "line1\nline2"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test 9: parse_ndjson_line fail-closed on malformed JSON
# ---------------------------------------------------------------------------


def test_parse_ndjson_fail_closed_on_bad_json() -> None:
    """parse_ndjson_line returns None (not raises) for malformed JSON (FR-035)."""
    result = parse_ndjson_line("this is not json{{{")
    assert result is None


def test_parse_ndjson_fail_closed_on_schema_violation() -> None:
    """parse_ndjson_line returns None on schema violation (FR-035)."""
    raw = json.dumps({"kind": "user_input", "session_id": "s1"})  # missing required fields
    result = parse_ndjson_line(raw)
    assert result is None


def test_parse_ndjson_empty_line_returns_none() -> None:
    """parse_ndjson_line returns None for empty/whitespace lines."""
    assert parse_ndjson_line("") is None
    assert parse_ndjson_line("   \n") is None
