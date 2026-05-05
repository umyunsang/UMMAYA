# SPDX-License-Identifier: Apache-2.0
"""P1-2/P1-3 smoke test — HMAC key bootstrap + first ledger append + verify.

Audit-8 P1 fix validation:
- P1-2: ``~/.kosmos/keys/registry.json`` auto-bootstrap on first boot.
- P1-3: First consent receipt written via ``ledger.append()`` + ``verify_ledger``
        returns ``passed=True`` (HMAC chain valid from genesis).

Also validates idempotency: bootstrap called twice does not corrupt the key or
overwrite the registry.

References:
- Spec 033 §US1 FR-D01..FR-D05, Invariants L1–L5
- PIPA §22-2 audit trail integrity obligation
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kosmos.permissions.hmac_key import HMACKeyFileModeError, bootstrap_hmac_key
from kosmos.permissions.ledger import append as ledger_append
from kosmos.permissions.ledger_verify import verify_ledger

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def keys_dir(tmp_path: Path) -> Path:
    """Return a fresh keys directory under tmp_path."""
    d = tmp_path / "keys"
    d.mkdir(mode=0o700, parents=True)
    return d


@pytest.fixture()
def bootstrap_env(tmp_path: Path):
    """Complete fresh bootstrap environment (no pre-existing key or registry)."""
    key_path = tmp_path / "keys" / "ledger.key"
    key_registry_path = tmp_path / "keys" / "registry.json"
    ledger_path = tmp_path / "consent_ledger.jsonl"
    return {
        "key_path": key_path,
        "key_registry_path": key_registry_path,
        "ledger_path": ledger_path,
    }


# ---------------------------------------------------------------------------
# P1-2: HMAC key + registry auto-bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_creates_key_file(bootstrap_env):
    """bootstrap_hmac_key() creates ledger.key when it does not exist."""
    key_path = bootstrap_env["key_path"]
    key_registry_path = bootstrap_env["key_registry_path"]

    assert not key_path.exists(), "Pre-condition: key must not exist"

    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    assert key_path.exists(), "bootstrap_hmac_key must create the key file"


def test_bootstrap_key_mode_is_0400(bootstrap_env):
    """Auto-generated key file has mode 0o400 (owner-read only)."""
    key_path = bootstrap_env["key_path"]
    key_registry_path = bootstrap_env["key_registry_path"]

    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    actual_mode = os.stat(key_path).st_mode & 0o777
    assert actual_mode == 0o400, f"Expected 0o400 got {oct(actual_mode)}"


def test_bootstrap_key_dir_mode_is_0700(bootstrap_env):
    """Parent directory of key file is created with mode 0o700."""
    key_path = bootstrap_env["key_path"]
    key_registry_path = bootstrap_env["key_registry_path"]

    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    dir_mode = os.stat(key_path.parent).st_mode & 0o777
    assert dir_mode == 0o700, f"Expected 0o700 got {oct(dir_mode)}"


def test_bootstrap_creates_registry_json(bootstrap_env):
    """bootstrap_hmac_key() creates registry.json when it does not exist."""
    key_path = bootstrap_env["key_path"]
    key_registry_path = bootstrap_env["key_registry_path"]

    assert not key_registry_path.exists(), "Pre-condition: registry must not exist"

    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    assert key_registry_path.exists(), "bootstrap_hmac_key must create registry.json"


def test_bootstrap_registry_has_k0001_entry(bootstrap_env):
    """Auto-created registry.json contains a k0001 entry pointing to ledger.key."""
    key_path = bootstrap_env["key_path"]
    key_registry_path = bootstrap_env["key_registry_path"]

    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    entries = json.loads(key_registry_path.read_text("utf-8"))
    assert isinstance(entries, list), "Registry must be a JSON array"
    assert len(entries) >= 1, "Registry must have at least one entry"

    k0001 = next((e for e in entries if e.get("key_id") == "k0001"), None)
    assert k0001 is not None, "Registry must contain key_id='k0001'"
    assert k0001.get("retired_at") is None, "k0001 must be active (retired_at=null)"
    assert k0001.get("file_path") == key_path.name, (
        f"file_path must be '{key_path.name}', got {k0001.get('file_path')!r}"
    )


def test_bootstrap_is_idempotent(bootstrap_env):
    """Calling bootstrap_hmac_key() twice leaves key + registry unchanged."""
    key_path = bootstrap_env["key_path"]
    key_registry_path = bootstrap_env["key_registry_path"]

    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    # Read the key bytes and registry contents after first call.
    key_bytes_first = key_path.read_bytes()
    registry_text_first = key_registry_path.read_text("utf-8")

    # Second call — must be idempotent.
    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    assert key_path.read_bytes() == key_bytes_first, "Key bytes must not change on second call"
    assert key_registry_path.read_text("utf-8") == registry_text_first, (
        "Registry must not change on second call"
    )


def test_bootstrap_fails_closed_on_wrong_key_mode(tmp_path):
    """bootstrap_hmac_key() propagates HMACKeyFileModeError when key mode is wrong."""
    key_path = tmp_path / "keys" / "ledger.key"
    key_path.parent.mkdir(mode=0o700, parents=True)
    key_registry_path = tmp_path / "keys" / "registry.json"

    # Create key with wrong mode (0o644).
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, b"\xab" * 32)
    finally:
        os.close(fd)

    with pytest.raises(HMACKeyFileModeError) as exc_info:
        bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    assert exc_info.value.actual_mode == 0o644


# ---------------------------------------------------------------------------
# P1-3: First receipt append + verify_ledger PASS
# ---------------------------------------------------------------------------


def test_first_receipt_append_and_verify(bootstrap_env):
    """Smoke: bootstrap → append first receipt → verify_ledger passes (exit_code=0)."""
    key_path = bootstrap_env["key_path"]
    key_registry_path = bootstrap_env["key_registry_path"]
    ledger_path = bootstrap_env["ledger_path"]

    # Step 1: Bootstrap keys.
    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    # Step 2: Append a genesis consent record.
    record = ledger_append(
        tool_id="koroad_accident_hazard_search",
        mode="default",
        granted=True,
        action_digest="a" * 64,  # fake 64-char hex digest
        consent_receipt_id=None,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=key_registry_path,
    )

    # Basic sanity checks on returned record.
    assert record.sequence == 0, f"Genesis record must have sequence=0, got {record.sequence}"
    assert record.prev_hash == "0" * 64, "Genesis record must have prev_hash=genesis sentinel"
    assert len(record.record_hash) == 64, "record_hash must be 64-char hex"
    assert len(record.hmac_seal) == 64, "hmac_seal must be 64-char hex"
    assert record.key_id == "k0001"

    # Step 3: Verify the ledger — must return passed=True with exit_code=0.
    report = verify_ledger(ledger_path=ledger_path, key_registry_path=key_registry_path)

    assert report.passed is True, (
        f"verify_ledger must pass after genesis append. "
        f"Got passed={report.passed}, exit_code={report.exit_code}, "
        f"reason={report.broken_reason}"
    )
    assert report.exit_code == 0
    assert report.total_records == 1
    assert report.first_broken_index is None
    assert report.broken_reason is None


def test_second_receipt_extends_chain_and_verifies(bootstrap_env):
    """Two consecutive appends form a valid chain that verify_ledger confirms."""
    key_path = bootstrap_env["key_path"]
    key_registry_path = bootstrap_env["key_registry_path"]
    ledger_path = bootstrap_env["ledger_path"]

    bootstrap_hmac_key(key_path=key_path, key_registry_path=key_registry_path)

    # Append two records.
    first = ledger_append(
        tool_id="hira_hospital_search",
        mode="default",
        granted=True,
        action_digest="b" * 64,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=key_registry_path,
    )
    second = ledger_append(
        tool_id="kma_short_term_forecast",
        mode="default",
        granted=False,
        action_digest="c" * 64,
        ledger_path=ledger_path,
        key_path=key_path,
        key_registry_path=key_registry_path,
    )

    # Chain linkage: second.prev_hash == first.record_hash.
    assert second.prev_hash == first.record_hash, (
        "Second record's prev_hash must equal first record's record_hash"
    )
    assert second.sequence == 1

    report = verify_ledger(ledger_path=ledger_path, key_registry_path=key_registry_path)
    assert report.passed is True, (
        f"Chain of 2 records must verify. exit_code={report.exit_code} "
        f"reason={report.broken_reason}"
    )
    assert report.total_records == 2
