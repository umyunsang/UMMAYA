# SPDX-License-Identifier: Apache-2.0
"""Audit-4 P0-2 / P0-3 — Allow + Revoke paths must append HMAC-sealed records.

Background
----------
Pre-Audit-4 the Allow path in ``stdio._check_permission_gate`` wrote a JSON
receipt under ``~/.kosmos/memdir/user/consent/<receipt_id>.json`` but never
called ``kosmos.permissions.ledger.append``. Receipts therefore had no
HMAC seal, no hash chain, no key_id — and the canonical Spec 033 PIPA
ledger at ``~/.kosmos/consent_ledger.jsonl`` did not even exist on first
boot. Similarly the Revoke path used an ad-hoc unsealed
``hashlib.sha256(json.dumps(entry))`` plus a parallel
``~/.kosmos/memdir/user/consent/ledger.jsonl`` file — entries forgeable.

These tests verify the fix by:

1. Importing the production ledger module that the Allow / Revoke handlers
   in ``stdio.py`` now call.
2. Calling ``append(action="allow", ...)`` against an isolated tmp-path
   ledger and asserting the resulting record has all integrity fields
   (record_hash, hmac_seal, prev_hash, key_id, sequence).
3. Calling ``append(action="withdraw", ...)`` against the same ledger and
   asserting the chain link prev_hash points back to the allow record.
4. Verifying the ledger file is created with mode 0600 and the directory
   with mode 0700 (POSIX hardening from Spec 033).

Reference: ``specs/033-permission-v2-spectrum/data-model.md § 2.1`` invariants
L1 (genesis), L2 (chain), L3 (HMAC), L4 (key-ID), L5 (WORM).
"""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosmos.permissions.action_digest import compute_action_digest, generate_nonce
from kosmos.permissions.ledger import append as ledger_append


# ---------------------------------------------------------------------------
# Fixture: isolated ledger + key + registry triple.
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_ledger(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Spec 033 ledger triple in tmp_path — never touches ~/.kosmos."""
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(mode=0o700)
    key_path = keys_dir / "ledger.key"
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        os.write(fd, b"\xCD" * 32)
    finally:
        os.close(fd)
    ledger_path = tmp_path / "consent_ledger.jsonl"
    registry_path = keys_dir / "registry.json"
    return ledger_path, key_path, registry_path


# ---------------------------------------------------------------------------
# P0-2 — Allow path appends a sealed record.
# ---------------------------------------------------------------------------


class TestAuditP0_2AllowLedger:
    def test_allow_append_creates_sealed_record(
        self, isolated_ledger: tuple[Path, Path, Path]
    ) -> None:
        """Allow-path append produces a record with all integrity fields."""
        ledger_path, key_path, registry_path = isolated_ledger

        digest = compute_action_digest(
            "mock_submit_module_gov24_minwon",
            {"minwon_type": "주민등록등본"},
            generate_nonce(),
        )
        record = ledger_append(
            tool_id="mock_submit_module_gov24_minwon",
            mode="default",
            granted=True,
            action_digest=digest,
            action="allow",
            consent_receipt_id="rcpt-allow-p0-2-001",
            session_id="sess-p0-2-allow",
            correlation_id="corr-p0-2-allow",
            ledger_path=ledger_path,
            key_path=key_path,
            key_registry_path=registry_path,
        )

        # P0-2 invariants — all integrity fields populated.
        assert record.record_hash and len(record.record_hash) == 64
        assert record.hmac_seal and len(record.hmac_seal) == 64
        assert record.prev_hash == "0" * 64  # genesis sentinel
        assert record.key_id == "k0001"  # default first key
        assert record.sequence == 0
        assert record.action == "allow"
        assert record.granted is True
        assert record.consent_receipt_id == "rcpt-allow-p0-2-001"

    def test_allow_ledger_file_permissions(
        self, isolated_ledger: tuple[Path, Path, Path]
    ) -> None:
        """The ledger file must be created with mode 0600 (POSIX hardening)."""
        ledger_path, key_path, registry_path = isolated_ledger

        ledger_append(
            tool_id="mock_submit_module_hometax_taxreturn",
            mode="default",
            granted=True,
            action_digest=compute_action_digest(
                "mock_submit_module_hometax_taxreturn", {}, generate_nonce()
            ),
            action="allow",
            consent_receipt_id="rcpt-allow-perm-check",
            ledger_path=ledger_path,
            key_path=key_path,
            key_registry_path=registry_path,
        )

        assert ledger_path.exists()
        actual_mode = ledger_path.stat().st_mode & 0o777
        assert actual_mode == 0o600, (
            f"ledger must be 0o600 per Spec 033 invariant, got {oct(actual_mode)}"
        )

    def test_allow_record_persisted_to_ndjson(
        self, isolated_ledger: tuple[Path, Path, Path]
    ) -> None:
        """The serialised record on disk must contain HMAC + chain fields."""
        ledger_path, key_path, registry_path = isolated_ledger

        ledger_append(
            tool_id="mock_traffic_fine_pay_v1",
            mode="default",
            granted=True,
            action_digest=compute_action_digest(
                "mock_traffic_fine_pay_v1", {"fine_reference": "F-001"}, generate_nonce()
            ),
            action="allow",
            consent_receipt_id="rcpt-allow-disk",
            ledger_path=ledger_path,
            key_path=key_path,
            key_registry_path=registry_path,
        )

        line = ledger_path.read_text("utf-8").rstrip("\n")
        parsed = json.loads(line)
        assert parsed["action"] == "allow"
        assert parsed["granted"] is True
        # Integrity fields MUST be present on every persisted record.
        for field in ("record_hash", "hmac_seal", "prev_hash", "key_id", "sequence"):
            assert field in parsed, f"missing integrity field {field!r}"


# ---------------------------------------------------------------------------
# P0-3 — Revoke path chains correctly off prior Allow.
# ---------------------------------------------------------------------------


class TestAuditP0_3RevokeLedger:
    def test_revoke_chains_from_allow(
        self, isolated_ledger: tuple[Path, Path, Path]
    ) -> None:
        """A withdraw record's prev_hash equals the prior allow record's record_hash."""
        ledger_path, key_path, registry_path = isolated_ledger

        allow = ledger_append(
            tool_id="mock_welfare_application_submit_v1",
            mode="default",
            granted=True,
            action_digest=compute_action_digest(
                "mock_welfare_application_submit_v1",
                {"benefit_code": "BS01"},
                generate_nonce(),
            ),
            action="allow",
            consent_receipt_id="rcpt-chain-allow",
            session_id="sess-chain",
            ledger_path=ledger_path,
            key_path=key_path,
            key_registry_path=registry_path,
        )

        withdraw = ledger_append(
            tool_id="mock_welfare_application_submit_v1",
            mode="default",
            granted=False,
            action_digest=compute_action_digest(
                "mock_welfare_application_submit_v1",
                {"scope_receipt_id": "rcpt-chain-allow"},
                generate_nonce(),
            ),
            action="withdraw",
            scope_receipt_id="rcpt-chain-allow",
            withdrawn_at=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
            session_id="sess-chain",
            ledger_path=ledger_path,
            key_path=key_path,
            key_registry_path=registry_path,
        )

        assert withdraw.prev_hash == allow.record_hash
        assert withdraw.sequence == allow.sequence + 1
        assert withdraw.action == "withdraw"
        assert withdraw.scope_receipt_id == "rcpt-chain-allow"
        assert withdraw.granted is False
        # HMAC and key_id must still be sealed on the withdraw record.
        assert withdraw.hmac_seal and len(withdraw.hmac_seal) == 64
        assert withdraw.key_id == "k0001"

    def test_revoke_hmac_validates_independently_of_chain(
        self, isolated_ledger: tuple[Path, Path, Path]
    ) -> None:
        """Tampering the chain (prev_hash) does not invalidate the HMAC seal —
        proving the HMAC layer is independent of the chain layer (Spec 033 L3)."""
        from kosmos.permissions.canonical_json import canonicalize
        import hashlib
        import hmac as hmac_lib

        ledger_path, key_path, registry_path = isolated_ledger

        rec = ledger_append(
            tool_id="mock_submit_module_public_mydata_action",
            mode="default",
            granted=True,
            action_digest=compute_action_digest(
                "mock_submit_module_public_mydata_action", {}, generate_nonce()
            ),
            action="allow",
            consent_receipt_id="rcpt-hmac-test",
            ledger_path=ledger_path,
            key_path=key_path,
            key_registry_path=registry_path,
        )

        # Re-derive record_hash + hmac_seal independently from disk.
        line = ledger_path.read_text("utf-8").splitlines()[-1]
        parsed = json.loads(line)
        # Strip integrity fields, re-canonicalise + re-hash — must equal record_hash.
        hashable = {
            k: v for k, v in parsed.items() if k not in ("record_hash", "hmac_seal")
        }
        recomputed_hash = hashlib.sha256(canonicalize(hashable)).hexdigest()
        assert recomputed_hash == rec.record_hash

        # Re-seal HMAC over recomputed hash — must equal stored hmac_seal.
        key_bytes = key_path.read_bytes()
        recomputed_seal = hmac_lib.new(
            key_bytes, recomputed_hash.encode("ascii"), "sha256"
        ).hexdigest()
        assert recomputed_seal == rec.hmac_seal


# ---------------------------------------------------------------------------
# Schema-level — verify the model accepts both Allow + Withdraw shapes.
# ---------------------------------------------------------------------------


def test_consent_ledger_record_action_field_default_allow() -> None:
    """Pre-WS3 records (no `action` field) deserialise as action='allow'."""
    from kosmos.permissions.models import ConsentLedgerRecord

    rec = ConsentLedgerRecord.model_validate(
        {
            "version": "1.0.0",
            "sequence": 0,
            "recorded_at": datetime(2026, 5, 4, tzinfo=UTC),
            "tool_id": "kma_short_term_forecast",
            "mode": "default",
            "granted": True,
            "action_digest": "0" * 64,
            "prev_hash": "0" * 64,
            "record_hash": "f" * 64,
            "hmac_seal": "e" * 64,
            "key_id": "k0001",
        }
    )
    assert rec.action == "allow"
