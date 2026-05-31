# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the IPC frame schema (T014).

Covers:
- (a) Round-trip: model_validate_json → model_dump_json → model_validate_json
      for all 10 discriminated-union arms.
- (b) model_json_schema() contains all 10 discriminator kind values.
- (c) Invalid / missing required fields raise ValidationError.
- (d) Schema arms where per-file examples were absent: synthesised defaults are
      documented inline (see SYNTHESISED_ARMS).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from ummaya.ipc.frame_schema import (
    ChatRequestFrame,
    IPCFrame,
    ProgressEventFrame,
    ipc_frame_json_schema,
)


def _compute_manifest_hash_for_test() -> str:
    """Pre-compute the manifest_hash for the single-entry test frame."""
    entry = {
        "input_schema_json": {},
        "llm_description": None,
        "name": "Resolve Location",
        "output_schema_json": {},
        "policy_authority_url": None,
        "primitive": "locate",
        "search_hint": None,
        "source_mode": "internal",
        "tool_id": "locate",
    }
    canonical = json.dumps([entry], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONTRACTS_DIR = (
    Path(__file__).parent.parent.parent / "specs" / "287-tui-ink-react-bun" / "contracts"
)

# Arms whose per-arm JSON Schema files had no "examples" field; minimal valid
# payloads were synthesised from the schema's "required" properties and their
# stated types.
SYNTHESISED_ARMS: frozenset[str] = frozenset(
    {
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
    }
)

_TS = "2025-01-01T00:00:00Z"
_SESSION_ID = "01HNMJ1Z000000000000000000"  # valid ULID-format string
_CORR_ID = "01HNMJ0Z000000000000000000"  # Spec 032 required envelope field

# ---------------------------------------------------------------------------
# Minimal valid examples per arm
# ---------------------------------------------------------------------------

_MINIMAL_EXAMPLES: dict[str, dict[str, Any]] = {
    "user_input": {
        "kind": "user_input",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "tui",
        "frame_seq": 0,
        "ts": _TS,
        "text": "안녕하세요",
    },
    # Spec 1978 ADR-0001 — tools-aware chat from TUI
    "chat_request": {
        "kind": "chat_request",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "tui",
        "frame_seq": 0,
        "ts": _TS,
        "messages": [{"role": "user", "content": "안녕하세요"}],
        "tools": [],
    },
    "assistant_chunk": {
        "kind": "assistant_chunk",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 1,
        "ts": _TS,
        "message_id": "01HNMJ2Z000000000000000001",
        "delta": "안녕",
        "done": False,
    },
    "progress_event": {
        "kind": "progress_event",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 2,
        "ts": _TS,
        "phase": "tool_selection",
        "message_ko": "도구 후보를 정리하고 있습니다.",
        "message_en": "Selecting tool candidates.",
        "safe_to_persist": True,
    },
    "tool_call": {
        "kind": "tool_call",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 2,
        "ts": _TS,
        "call_id": "01HNMJ3Z000000000000000002",
        "name": "find",
        "arguments": {"mode": "search", "query": "서울 병원"},
    },
    "tool_result": {
        "kind": "tool_result",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 3,
        "ts": _TS,
        "call_id": "01HNMJ3Z000000000000000002",
        "envelope": {"kind": "find"},
    },
    "coordinator_phase": {
        "kind": "coordinator_phase",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 4,
        "ts": _TS,
        "phase": "Research",
    },
    "worker_status": {
        "kind": "worker_status",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 5,
        "ts": _TS,
        "worker_id": "worker-001",
        "role_id": "transport-specialist",
        "current_primitive": "find",
        "status": "running",
    },
    "permission_request": {
        "kind": "permission_request",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 6,
        "ts": _TS,
        "request_id": "01HNMJ4Z000000000000000003",
        "worker_id": "worker-001",
        "primitive_kind": "send",
        "description_ko": "제출 권한이 필요합니다",
        "description_en": "Permission to submit required",
        "risk_level": "medium",
    },
    "permission_response": {
        "kind": "permission_response",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "tui",
        "frame_seq": 7,
        "ts": _TS,
        "request_id": "01HNMJ4Z000000000000000003",
        "decision": "granted",
    },
    "session_event": {
        "kind": "session_event",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "tui",
        "frame_seq": 8,
        "ts": _TS,
        "event": "save",
        "payload": {},
    },
    "error": {
        "kind": "error",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 9,
        "ts": _TS,
        "code": "backend_crash",
        "message": "Unexpected backend error",
        "details": {},
    },
    # --- Spec 032 new arms (T005-T009) ---
    "payload_start": {
        "kind": "payload_start",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 10,
        "ts": _TS,
        "content_type": "text/plain",
    },
    "payload_delta": {
        "kind": "payload_delta",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 11,
        "ts": _TS,
        "delta_seq": 0,
        "payload": "hello",
    },
    "payload_end": {
        "kind": "payload_end",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 12,
        "ts": _TS,
        "delta_count": 1,
        "status": "ok",
        "trailer": {"final": True},
    },
    "backpressure": {
        "kind": "backpressure",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 13,
        "ts": _TS,
        "signal": "throttle",
        "source": "upstream_429",
        "queue_depth": 10,
        "hwm": 64,
        "retry_after_ms": 5000,
        "hud_copy_ko": "부처 API가 혼잡합니다.",
        "hud_copy_en": "Upstream API is congested.",
    },
    "resume_request": {
        "kind": "resume_request",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "tui",
        "frame_seq": 0,
        "ts": _TS,
        "tui_session_token": "test-token-001",
    },
    "resume_response": {
        "kind": "resume_response",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 14,
        "ts": _TS,
        "trailer": {"final": True},
        "resumed_from_frame_seq": 0,
        "replay_count": 0,
        "server_session_id": _SESSION_ID,
        "heartbeat_interval_ms": 30000,
    },
    "resume_rejected": {
        "kind": "resume_rejected",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 15,
        "ts": _TS,
        "trailer": {"final": True},
        "reason": "session_unknown",
        "detail": "Session not found",
    },
    "heartbeat": {
        "kind": "heartbeat",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 16,
        "ts": _TS,
        "direction": "ping",
        "peer_frame_seq": 5,
    },
    "notification_push": {
        "kind": "notification_push",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "notification",
        "frame_seq": 17,
        "ts": _TS,
        "subscription_id": "sub-001",
        "adapter_id": "disaster_alert_cbs_push",
        "event_guid": "guid-001",
        "payload_content_type": "text/plain",
        "payload": "재난 알림 테스트",
    },
    # --- Epic #1636 P5 plugin DX 5-tier ---
    "plugin_op": {
        "kind": "plugin_op",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "tui",
        "frame_seq": 18,
        "ts": _TS,
        "op": "request",
        "request_op": "install",
        "name": "seoul-subway",
    },
    # --- Epic ε #2296 adapter manifest sync ---
    # manifest_hash is the SHA-256 of canonical-JSON of the sorted single entry.
    "adapter_manifest_sync": {
        "kind": "adapter_manifest_sync",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 19,
        "ts": _TS,
        "entries": [
            {
                "tool_id": "locate",
                "name": "Resolve Location",
                "primitive": "locate",
                "policy_authority_url": None,
                "source_mode": "internal",
            }
        ],
        # Pre-computed SHA-256 of canonical JSON of the single entry above.
        # Recompute via: hashlib.sha256(json.dumps([{"name": "Resolve Location",
        #   "policy_authority_url": null, "primitive": "locate",
        #   "source_mode": "internal", "tool_id": "locate"}],
        #   sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        "manifest_hash": _compute_manifest_hash_for_test(),
        "emitter_pid": 47823,
    },
    # --- Epic 2 — consent revoke IPC (arms 22-23) ---
    "consent_revoke_request": {
        "kind": "consent_revoke_request",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "tui",
        "frame_seq": 20,
        "ts": _TS,
        "request_id": "req-test-001",
        "receipt_id": "rcpt-abcdefgh",
        "scope": "once",
    },
    "consent_revoke_response": {
        "kind": "consent_revoke_response",
        "version": "1.0",
        "session_id": _SESSION_ID,
        "correlation_id": _CORR_ID,
        "role": "backend",
        "frame_seq": 21,
        "ts": _TS,
        "request_id": "req-test-001",
        "ok": True,
        "revoked_at": _TS,
        "record_hash": "a" * 64,
    },
}


def test_chat_request_accepts_reasoning_mode() -> None:
    """ChatRequestFrame carries the TUI's K-EXAONE reasoning policy to backend."""
    frame = ChatRequestFrame(
        kind="chat_request",
        version="1.0",
        session_id=_SESSION_ID,
        correlation_id=_CORR_ID,
        role="tui",
        frame_seq=0,
        ts=_TS,
        messages=[{"role": "user", "content": "안녕하세요"}],
        reasoning_mode="deep",
    )

    assert frame.reasoning_mode == "deep"


def test_progress_event_is_backend_only_and_safe_by_default() -> None:
    """progress_event is the deterministic, safe query-loop painting channel."""
    frame = ProgressEventFrame(
        kind="progress_event",
        version="1.0",
        session_id=_SESSION_ID,
        correlation_id=_CORR_ID,
        role="backend",
        frame_seq=0,
        ts=_TS,
        phase="analysis",
        message_ko="요청을 분석하고 있습니다.",
        message_en="Analyzing the request.",
    )

    assert frame.safe_to_persist is True


_EXPECTED_ARMS = frozenset(_MINIMAL_EXAMPLES.keys())
_ADAPTER: TypeAdapter[Any] = TypeAdapter(IPCFrame)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _validate_roundtrip(example: dict[str, Any]) -> None:
    """Parse → dump → parse and assert structural equality."""
    raw = json.dumps(example)
    frame1 = _ADAPTER.validate_json(raw)
    dumped = _ADAPTER.dump_json(frame1)
    frame2 = _ADAPTER.validate_json(dumped)
    assert _ADAPTER.dump_python(frame1) == _ADAPTER.dump_python(frame2), (
        f"Round-trip failed for kind={example['kind']!r}"
    )


# ---------------------------------------------------------------------------
# Tests: one per arm
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("arm", sorted(_MINIMAL_EXAMPLES.keys()))
def test_arm_round_trip(arm: str) -> None:
    """Each arm validates and round-trips without data loss."""
    _validate_roundtrip(_MINIMAL_EXAMPLES[arm])


@pytest.mark.parametrize("arm", sorted(_MINIMAL_EXAMPLES.keys()))
def test_arm_kind_field(arm: str) -> None:
    """Parsed frame has correct kind field."""
    raw = json.dumps(_MINIMAL_EXAMPLES[arm])
    frame = _ADAPTER.validate_json(raw)
    assert _ADAPTER.dump_python(frame)["kind"] == arm


# ---------------------------------------------------------------------------
# Tests: union-level schema
# ---------------------------------------------------------------------------


def test_json_schema_contains_all_discriminators() -> None:
    """ipc_frame_json_schema() exposes all 22 discriminator values
    (10 baseline + 9 Spec 032 + 1 Epic #1636 + 1 Spec 1978 + 1 Epic ε #2296 = 22)."""
    schema = ipc_frame_json_schema()
    discriminator = schema.get("discriminator", {})
    mapping = discriminator.get("mapping", {})
    found = frozenset(mapping.keys())
    assert found == _EXPECTED_ARMS, (
        f"Missing arms: {_EXPECTED_ARMS - found}; unexpected: {found - _EXPECTED_ARMS}"
    )


def test_json_schema_is_serialisable() -> None:
    """ipc_frame_json_schema() output must be JSON-serialisable (no Python-only objects)."""
    schema = ipc_frame_json_schema()
    json.dumps(schema)  # raises TypeError on non-serialisable types


# ---------------------------------------------------------------------------
# Tests: contract files exist for all arms
# ---------------------------------------------------------------------------


def test_contract_files_present() -> None:
    """Each arm must have a corresponding *.schema.json file in contracts/."""
    arm_to_file = {
        "user_input": "user-input.schema.json",
        "assistant_chunk": "assistant-chunk.schema.json",
        "tool_call": "tool-call.schema.json",
        "tool_result": "tool-result.schema.json",
        "coordinator_phase": "coordinator-phase.schema.json",
        "worker_status": "worker-status.schema.json",
        "permission_request": "permission-request.schema.json",
        "permission_response": "permission-response.schema.json",
        "session_event": "session-event.schema.json",
        "error": "error.schema.json",
    }
    for arm, filename in arm_to_file.items():
        path = _CONTRACTS_DIR / filename
        assert path.exists(), f"Missing contract file for arm={arm!r}: {path}"


# ---------------------------------------------------------------------------
# Tests: invalid payloads are rejected
# ---------------------------------------------------------------------------


def test_missing_kind_rejected() -> None:
    """Payload without 'kind' must raise ValidationError."""
    payload = {"session_id": _SESSION_ID, "ts": _TS, "text": "hello"}
    with pytest.raises(ValidationError):
        _ADAPTER.validate_json(json.dumps(payload))


def test_unknown_kind_rejected() -> None:
    """Payload with unrecognised 'kind' must raise ValidationError."""
    payload = {"kind": "nonexistent_arm", "session_id": _SESSION_ID, "ts": _TS}
    with pytest.raises(ValidationError):
        _ADAPTER.validate_json(json.dumps(payload))


@pytest.mark.parametrize("arm", sorted(_MINIMAL_EXAMPLES.keys()))
def test_missing_required_field_rejected(arm: str) -> None:
    """Dropping correlation_id (required, no default) must raise ValidationError."""
    example = dict(_MINIMAL_EXAMPLES[arm])
    # correlation_id is required on _BaseFrame (no default) — dropping it must fail.
    del example["correlation_id"]
    with pytest.raises(ValidationError):
        _ADAPTER.validate_json(json.dumps(example))


def test_extra_field_rejected() -> None:
    """Extra fields on the union base are forbidden (extra='forbid')."""
    payload = dict(_MINIMAL_EXAMPLES["user_input"])
    payload["unknown_extra"] = "should_be_rejected"
    with pytest.raises(ValidationError):
        _ADAPTER.validate_json(json.dumps(payload))


# ---------------------------------------------------------------------------
# Tests: optional correlation_id
# ---------------------------------------------------------------------------


def test_correlation_id_null_rejected() -> None:
    """correlation_id=null is rejected — Spec 032 invariant E5 requires non-empty string."""
    payload = dict(_MINIMAL_EXAMPLES["assistant_chunk"])
    payload["correlation_id"] = None
    with pytest.raises(ValidationError):
        _ADAPTER.validate_json(json.dumps(payload))


def test_correlation_id_string_accepted() -> None:
    """correlation_id as a ULID string is accepted."""
    payload = dict(_MINIMAL_EXAMPLES["assistant_chunk"])
    payload["correlation_id"] = "01HNMJ5Z000000000000000099"
    _validate_roundtrip(payload)


# ---------------------------------------------------------------------------
# Lead-Diag-4 (2026-05-04, role='tool' wire conversion) — ChatMessage.tool_calls
# ---------------------------------------------------------------------------


def _make_chat_request(messages: list[dict[str, object]]) -> dict[str, object]:
    base = dict(_MINIMAL_EXAMPLES["chat_request"])
    base["messages"] = messages
    return base


def test_chat_message_tool_calls_accepted_on_assistant() -> None:
    """Assistant message carrying ``tool_calls`` round-trips cleanly."""
    payload = _make_chat_request(
        [
            {"role": "user", "content": "서울 날씨"},
            {
                "role": "assistant",
                "content": "잠시만요",
                "tool_calls": [
                    {
                        "id": "call_001",
                        "type": "function",
                        "function": {"name": "find", "arguments": '{"q":"서울"}'},
                    }
                ],
            },
            {
                "role": "tool",
                "content": '{"ok":true}',
                "name": "find",
                "tool_call_id": "call_001",
            },
        ]
    )
    _validate_roundtrip(payload)


def test_chat_message_tool_calls_rejected_on_user() -> None:
    """Wire validator rejects ``tool_calls`` on non-assistant roles (D4 ext.)."""
    payload = _make_chat_request(
        [
            {
                "role": "user",
                "content": "hi",
                "tool_calls": [
                    {
                        "id": "call_x",
                        "type": "function",
                        "function": {"name": "find", "arguments": "{}"},
                    }
                ],
            },
        ]
    )
    with pytest.raises(ValidationError, match="tool_calls is only valid"):
        _ADAPTER.validate_json(json.dumps(payload))


def test_chat_message_tool_calls_rejected_on_tool() -> None:
    """Wire validator rejects ``tool_calls`` on role='tool' messages."""
    payload = _make_chat_request(
        [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_x",
                        "type": "function",
                        "function": {"name": "find", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "content": "result",
                "name": "find",
                "tool_call_id": "call_x",
                "tool_calls": [
                    {
                        "id": "call_y",
                        "type": "function",
                        "function": {"name": "find", "arguments": "{}"},
                    }
                ],
            },
        ]
    )
    with pytest.raises(ValidationError, match="tool_calls is only valid"):
        _ADAPTER.validate_json(json.dumps(payload))


def test_chat_message_tool_calls_omitted_is_backward_compat() -> None:
    """Legacy senders that omit ``tool_calls`` continue to validate."""
    payload = _make_chat_request(
        [
            {"role": "user", "content": "안녕하세요"},
            {"role": "assistant", "content": "반갑습니다"},
        ]
    )
    _validate_roundtrip(payload)


def test_chat_message_tool_calls_arguments_must_be_string() -> None:
    """OpenAI spec — ``tool_calls[i].function.arguments`` is a JSON STRING."""
    # Pydantic v2 will accept dict-typed arguments only if we declare them
    # as dict. We declared ``arguments: str``, so a dict here MUST raise.
    payload = _make_chat_request(
        [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_x",
                        "type": "function",
                        "function": {"name": "find", "arguments": {"q": "obj"}},
                    }
                ],
            },
        ]
    )
    with pytest.raises(ValidationError):
        _ADAPTER.validate_json(json.dumps(payload))


def test_chat_message_role_tool_still_requires_name_and_call_id() -> None:
    """D4 invariant unchanged — role='tool' requires both name and tool_call_id."""
    # Missing name
    bad_no_name = _make_chat_request(
        [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_x",
                        "type": "function",
                        "function": {"name": "find", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "content": "r", "tool_call_id": "call_x"},
        ]
    )
    with pytest.raises(ValidationError, match="non-empty 'name'"):
        _ADAPTER.validate_json(json.dumps(bad_no_name))

    # Missing tool_call_id
    bad_no_id = _make_chat_request(
        [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_x",
                        "type": "function",
                        "function": {"name": "find", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "content": "r", "name": "find"},
        ]
    )
    with pytest.raises(ValidationError, match="non-empty 'tool_call_id'"):
        _ADAPTER.validate_json(json.dumps(bad_no_id))
