# SPDX-License-Identifier: Apache-2.0
"""T005 — AdapterManifestEntry + AdapterManifestSyncFrame unit tests.

Covers:
1. Round-trip serialisation.
2. Discriminator validation (IPCFrame.model_validate routes to the correct type).
3. Hash mismatch handling (validator I3 detects mutation).
4. 21-arm union exhaustive count (regression guard).

Contract: specs/2296-ax-mock-adapters/contracts/ipc-adapter-manifest-frame.md § 3, 7
Data model: specs/2296-ax-mock-adapters/data-model.md § 4-5
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from ummaya.ipc.frame_schema import (
    AdapterManifestEntry,
    AdapterManifestSyncFrame,
    IPCFrame,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _make_entries() -> list[AdapterManifestEntry]:
    return [
        AdapterManifestEntry(
            tool_id="locate",
            name="Resolve Location",
            primitive="locate",
            policy_authority_url=None,
            source_mode="internal",
        ),
        AdapterManifestEntry(
            tool_id="nmc_emergency_search",
            name="NMC Emergency Bed Availability",
            primitive="find",
            policy_authority_url="https://www.e-gen.or.kr/nemc/main.do",
            source_mode="live",
        ),
        AdapterManifestEntry(
            tool_id="mock_submit_module_hometax_taxreturn",
            name="Mock — Hometax Tax Return Submission",
            primitive="send",
            policy_authority_url="https://www.hometax.go.kr/api-policy.do",
            source_mode="mock",
        ),
    ]


def _compute_hash(entries: list[AdapterManifestEntry]) -> str:
    sorted_entries = sorted(entries, key=lambda e: e.tool_id)
    dicts = [e.model_dump(mode="json", by_alias=False) for e in sorted_entries]
    canonical = _canonical_json(dicts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _make_frame(entries: list[AdapterManifestEntry] | None = None) -> AdapterManifestSyncFrame:
    es = entries or _make_entries()
    return AdapterManifestSyncFrame(
        kind="adapter_manifest_sync",
        role="backend",
        session_id="test-session",
        correlation_id="01HXKQ7Z3M1V8K2YQ8A6P4F9C1",
        ts=datetime.now(UTC).isoformat(),
        entries=es,
        manifest_hash=_compute_hash(es),
        emitter_pid=47823,
    )


# ---------------------------------------------------------------------------
# Test 1: Round-trip serialisation
# ---------------------------------------------------------------------------


def test_round_trip_serialisation() -> None:
    """Frame JSON-serialises and re-parses back to an identical object."""
    frame = _make_frame()
    json_str = frame.model_dump_json()
    parsed = AdapterManifestSyncFrame.model_validate_json(json_str)

    assert parsed.kind == "adapter_manifest_sync"
    assert parsed.manifest_hash == frame.manifest_hash
    assert parsed.emitter_pid == 47823
    assert len(parsed.entries) == len(frame.entries)
    # Check one entry round-trips correctly.
    tool_ids = {e.tool_id for e in parsed.entries}
    assert "nmc_emergency_search" in tool_ids
    assert "locate" in tool_ids


# ---------------------------------------------------------------------------
# Test 2: Discriminator validation via IPCFrame union
# ---------------------------------------------------------------------------


def test_ipc_frame_discriminates_to_adapter_manifest_sync() -> None:
    """IPCFrame.model_validate on adapter_manifest_sync returns AdapterManifestSyncFrame."""
    entries = _make_entries()
    raw = {
        "kind": "adapter_manifest_sync",
        "role": "backend",
        "session_id": "test-session",
        "correlation_id": "01HXKQ7Z3M1V8K2YQ8A6P4F9C1",
        "ts": datetime.now(UTC).isoformat(),
        "entries": [e.model_dump(mode="json") for e in entries],
        "manifest_hash": _compute_hash(entries),
        "emitter_pid": 47823,
    }
    adapter: TypeAdapter[IPCFrame] = TypeAdapter(IPCFrame)  # type: ignore[type-arg]
    frame = adapter.validate_python(raw)
    assert isinstance(frame, AdapterManifestSyncFrame)


# ---------------------------------------------------------------------------
# Test 3: Hash mismatch handling (I3)
# ---------------------------------------------------------------------------


def test_hash_mismatch_detected() -> None:
    """Providing a wrong manifest_hash must raise ValidationError (I3)."""
    entries = _make_entries()
    wrong_hash = "a" * 64  # not the correct SHA-256
    with pytest.raises(ValidationError) as exc_info:
        AdapterManifestSyncFrame(
            role="backend",
            session_id="test-session",
            correlation_id="01HXKQ7Z3M1V8K2YQ8A6P4F9C1",
            ts=datetime.now(UTC).isoformat(),
            entries=entries,
            manifest_hash=wrong_hash,
            emitter_pid=47823,
        )
    assert "manifest_hash" in str(exc_info.value) or "I3" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 4: Duplicate tool_id rejected (I2)
# ---------------------------------------------------------------------------


def test_duplicate_tool_id_rejected() -> None:
    """Two entries with the same tool_id must raise ValidationError (I2)."""
    entry = AdapterManifestEntry(
        tool_id="locate",
        name="Resolve Location A",
        primitive="locate",
        policy_authority_url=None,
        source_mode="internal",
    )
    entry_dup = AdapterManifestEntry(
        tool_id="locate",  # duplicate!
        name="Resolve Location B",
        primitive="locate",
        policy_authority_url=None,
        source_mode="internal",
    )
    entries = [entry, entry_dup]
    with pytest.raises(ValidationError) as exc_info:
        AdapterManifestSyncFrame(
            role="backend",
            session_id="test-session",
            correlation_id="01HXKQ7Z3M1V8K2YQ8A6P4F9C1",
            ts=datetime.now(UTC).isoformat(),
            entries=entries,
            manifest_hash=_compute_hash(entries),  # hash matches but I2 violation
            emitter_pid=47823,
        )
    assert "duplicate" in str(exc_info.value).lower() or "I2" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 5: AdapterManifestEntry validators (I4/I5/I7)
# ---------------------------------------------------------------------------


def test_entry_live_without_policy_url_rejected() -> None:
    """live entry with policy_authority_url=None must raise ValidationError (I4)."""
    with pytest.raises(ValidationError):
        AdapterManifestEntry(
            tool_id="nmc_emergency_search",
            name="NMC Emergency",
            primitive="find",
            policy_authority_url=None,  # missing for live
            source_mode="live",
        )


def test_entry_internal_with_policy_url_rejected() -> None:
    """internal entry with non-null policy_authority_url must raise ValidationError (I5)."""
    with pytest.raises(ValidationError):
        AdapterManifestEntry(
            tool_id="locate",
            name="Resolve Location",
            primitive="locate",
            policy_authority_url="https://example.gov.kr/policy.do",  # must be None
            source_mode="internal",
        )


def test_entry_tool_id_invalid_format() -> None:
    """tool_id not matching ^[a-z][a-z0-9_]*$ must raise ValidationError (I7)."""
    with pytest.raises(ValidationError):
        AdapterManifestEntry(
            tool_id="Invalid-ID",  # uppercase and hyphen — invalid
            name="Some Entry",
            primitive="find",
            policy_authority_url="https://example.gov.kr/",
            source_mode="live",
        )


# ---------------------------------------------------------------------------
# Test 6: 21-arm union exhaustive count (regression guard)
# ---------------------------------------------------------------------------


def test_ipc_frame_union_has_exactly_25_arms() -> None:
    """IPCFrame discriminated union must have exactly 25 arms.

    Arm counts by spec:
    - Spec 287 baseline: 10 arms (user_input .. error)
    - Spec 032 additions: 9 arms (payload_start .. notification_push)
    - Epic #1636 P5: plugin_op (1 arm)
    - Spec 1978 ADR-0001: chat_request (1 arm)
    - Epic ε #2296: adapter_manifest_sync (1 arm)
    - Spec 2767 consent revoke: consent_revoke_request + consent_revoke_response (2 arms)
    - K-EXAONE reasoning/progress painting: progress_event (1 arm)
    Total: 25

    This is a regression guard — any Epic that accidentally extends an existing
    arm or skips adding the new arm will fail this test.
    """
    # Get the Annotated args; the first is the Union of all frame types.
    annotated_args = get_args(IPCFrame)
    # annotated_args[0] is the Union type (the frame arms).
    union_type = annotated_args[0]
    arms = get_args(union_type)
    assert len(arms) == 25, (
        f"Expected 25 IPCFrame arms, got {len(arms)}. "
        "Did an Epic accidentally add or remove an arm?"
    )
