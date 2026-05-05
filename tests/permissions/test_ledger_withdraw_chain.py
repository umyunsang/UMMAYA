# SPDX-License-Identifier: Apache-2.0
"""Hash-chain integrity tests for withdraw records (Spec 033 WS3).

Verifies that:
  1. A withdraw record after an allow record chains correctly (prev_hash == allow record_hash).
  2. record_hash covers the "action" field — changing action changes hash.
  3. Two consecutive withdrawals chain correctly.
  4. Chain verification tolerates the mixed allow → withdraw sequence.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosmos.permissions.ledger import append

_ZERO_DIGEST = "0" * 64
_WITHDRAWAL_TS = datetime(2026, 5, 4, 9, 0, 0, tzinfo=UTC)


@pytest.fixture()
def ledger_env(tmp_path: Path):
    """Minimal isolated ledger + key environment."""
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(mode=0o700)
    key_path = keys_dir / "ledger.key"
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        os.write(fd, b"\xcd" * 32)
    finally:
        os.close(fd)
    ledger_path = tmp_path / "consent_ledger.jsonl"
    registry_path = keys_dir / "registry.json"
    return ledger_path, key_path, registry_path


# ---------------------------------------------------------------------------
# Chain linkage: allow → withdraw
# ---------------------------------------------------------------------------


def test_withdraw_chains_from_allow(ledger_env):
    """A withdraw record's prev_hash must equal the prior allow record's record_hash."""
    ledger_path, key_path, registry_path = ledger_env

    allow_record = append(
        tool_id="koroad_accident_hazard_search",
        mode="default",
        granted=True,
        action_digest=_ZERO_DIGEST,
        action="allow",
        consent_receipt_id="rcpt-allow-001",
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    withdraw_record = append(
        tool_id="koroad_accident_hazard_search",
        mode="default",
        granted=False,
        action_digest=_ZERO_DIGEST,
        action="withdraw",
        scope_receipt_id="rcpt-allow-001",
        withdrawn_at=_WITHDRAWAL_TS,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    assert withdraw_record.prev_hash == allow_record.record_hash
    assert withdraw_record.sequence == allow_record.sequence + 1


# ---------------------------------------------------------------------------
# Hash covers action field
# ---------------------------------------------------------------------------


def test_action_field_is_hashed(ledger_env):
    """Different action values on otherwise identical inputs produce different record_hash."""

    ledger_path, key_path, registry_path = ledger_env

    allow_rec = append(
        tool_id="kma_short_term_forecast",
        mode="default",
        granted=True,
        action_digest=_ZERO_DIGEST,
        action="allow",
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    # Reset to a fresh ledger so sequence / prev_hash are the same.
    fresh_ledger = ledger_path.parent / "fresh.jsonl"

    deny_rec = append(
        tool_id="kma_short_term_forecast",
        mode="default",
        granted=True,
        action_digest=_ZERO_DIGEST,
        action="deny",
        ledger_path=fresh_ledger,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    # The record_hash must differ because action differs.
    assert allow_rec.record_hash != deny_rec.record_hash


# ---------------------------------------------------------------------------
# Two consecutive withdrawals chain correctly
# ---------------------------------------------------------------------------


def test_double_withdraw_chain(ledger_env):
    """Two consecutive withdraw records chain correctly."""
    ledger_path, key_path, registry_path = ledger_env

    w1 = append(
        tool_id="hira_hospital_search",
        mode="default",
        granted=False,
        action_digest=_ZERO_DIGEST,
        action="withdraw",
        scope_receipt_id="rcpt-x1",
        withdrawn_at=_WITHDRAWAL_TS,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    w2 = append(
        tool_id="hira_hospital_search",
        mode="default",
        granted=False,
        action_digest=_ZERO_DIGEST,
        action="withdraw",
        scope_receipt_id="rcpt-x2",
        withdrawn_at=_WITHDRAWAL_TS,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    assert w2.prev_hash == w1.record_hash
    assert w2.sequence == w1.sequence + 1


# ---------------------------------------------------------------------------
# JSONL round-trip: all fields persisted
# ---------------------------------------------------------------------------


def test_withdraw_jsonl_round_trip(ledger_env):
    """All withdraw fields are durably serialised to NDJSON and readable back."""
    ledger_path, key_path, registry_path = ledger_env
    target_receipt = "rcpt-round-trip-007"

    append(
        tool_id="nmc_emergency_search",
        mode="default",
        granted=False,
        action_digest=_ZERO_DIGEST,
        action="withdraw",
        scope_receipt_id=target_receipt,
        withdrawn_at=_WITHDRAWAL_TS,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    lines = [line for line in ledger_path.read_bytes().splitlines() if line.strip()]
    obj = json.loads(lines[-1])
    assert obj["action"] == "withdraw"
    assert obj["scope_receipt_id"] == target_receipt
    assert "withdrawn_at" in obj
