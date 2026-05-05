# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ConsentLedgerRecord action-field extension (Spec 033 WS3).

Tests:
  - "allow" action (default / backward-compat)
  - "deny" action
  - "withdraw" action with scope_receipt_id + withdrawn_at
  - Backward-compat: JSON without "action" field parses as "allow"
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosmos.permissions.ledger import append
from kosmos.permissions.models import ConsentLedgerRecord

# Deterministic sentinel digest (64 hex zeros) used for action_digest in tests.
_ZERO_DIGEST = "0" * 64


@pytest.fixture()
def ledger_env(tmp_path: Path):
    """Minimal isolated ledger + key environment."""
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(mode=0o700)
    key_path = keys_dir / "ledger.key"
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        os.write(fd, b"\xAB" * 32)
    finally:
        os.close(fd)
    ledger_path = tmp_path / "consent_ledger.jsonl"
    registry_path = keys_dir / "registry.json"
    return ledger_path, key_path, registry_path


# ---------------------------------------------------------------------------
# Happy-path: action == "allow" (default)
# ---------------------------------------------------------------------------


def test_action_allow_default(ledger_env):
    """Appending without specifying action stores action='allow' (default)."""
    ledger_path, key_path, registry_path = ledger_env

    record = append(
        tool_id="koroad_accident_hazard_search",
        mode="default",
        granted=True,
        action_digest=_ZERO_DIGEST,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    assert record.action == "allow"
    assert record.scope_receipt_id is None
    assert record.withdrawn_at is None


def test_action_allow_explicit(ledger_env):
    """Explicitly passing action='allow' stores action='allow'."""
    ledger_path, key_path, registry_path = ledger_env

    record = append(
        tool_id="koroad_accident_hazard_search",
        mode="default",
        granted=True,
        action_digest=_ZERO_DIGEST,
        action="allow",
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    assert record.action == "allow"


# ---------------------------------------------------------------------------
# Happy-path: action == "deny"
# ---------------------------------------------------------------------------


def test_action_deny(ledger_env):
    """Appending with action='deny' stores action='deny' and granted=False."""
    ledger_path, key_path, registry_path = ledger_env

    record = append(
        tool_id="kma_short_term_forecast",
        mode="default",
        granted=False,
        action_digest=_ZERO_DIGEST,
        action="deny",
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    assert record.action == "deny"
    assert record.granted is False
    assert record.scope_receipt_id is None
    assert record.withdrawn_at is None


# ---------------------------------------------------------------------------
# Happy-path: action == "withdraw"
# ---------------------------------------------------------------------------


def test_action_withdraw(ledger_env):
    """Appending with action='withdraw' stores scope_receipt_id + withdrawn_at."""
    ledger_path, key_path, registry_path = ledger_env
    target_receipt = "rcpt-abc-123"
    withdrawal_ts = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)

    record = append(
        tool_id="koroad_accident_hazard_search",
        mode="default",
        granted=False,
        action_digest=_ZERO_DIGEST,
        action="withdraw",
        scope_receipt_id=target_receipt,
        withdrawn_at=withdrawal_ts,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    assert record.action == "withdraw"
    assert record.scope_receipt_id == target_receipt
    assert record.withdrawn_at == withdrawal_ts


# ---------------------------------------------------------------------------
# Backward-compat: JSON missing "action" field → default "allow"
# ---------------------------------------------------------------------------


def test_backward_compat_no_action_field(ledger_env):
    """Legacy ledger records without 'action' key deserialise as action='allow'."""
    ledger_path, key_path, registry_path = ledger_env

    # First, append a real record to seed the chain hashes.
    record = append(
        tool_id="koroad_accident_hazard_search",
        mode="default",
        granted=True,
        action_digest=_ZERO_DIGEST,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    # Read back the raw JSON and strip "action" to simulate a pre-WS3 record.
    raw = json.loads(ledger_path.read_bytes().splitlines()[-1])
    assert "action" in raw  # WS3 records have it
    del raw["action"]

    # Re-serialise and parse via model_validate_json so datetime strings are
    # handled correctly by Pydantic's strict mode JSON parser.
    stripped_json = json.dumps(raw, ensure_ascii=False)
    parsed = ConsentLedgerRecord.model_validate_json(stripped_json)
    assert parsed.action == "allow"


# ---------------------------------------------------------------------------
# Persistence: verify action is durable in the JSONL file
# ---------------------------------------------------------------------------


def test_action_persisted_in_jsonl(ledger_env):
    """The 'action' field is written to the NDJSON line and readable back."""
    ledger_path, key_path, registry_path = ledger_env

    append(
        tool_id="hira_hospital_search",
        mode="default",
        granted=False,
        action_digest=_ZERO_DIGEST,
        action="deny",
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=registry_path,
    )

    raw_line = ledger_path.read_bytes().rstrip(b"\n")
    obj = json.loads(raw_line)
    assert obj["action"] == "deny"
