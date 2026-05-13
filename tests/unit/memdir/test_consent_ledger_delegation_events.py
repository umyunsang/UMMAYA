# SPDX-License-Identifier: Apache-2.0
"""T006 — Delegation ledger event JSONL append + parse round-trip tests.

Covers:
- JSONL append + parse round-trip for all 3 event kinds.
- FileLedgerReader.find_issuance_session integration.

Contract: specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 5
Data model: specs/2296-ax-mock-adapters/data-model.md § 6
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ummaya.memdir.consent_ledger import (
    DelegationIssuedEvent,
    DelegationRevokedEvent,
    DelegationUsedEvent,
    FileLedgerReader,
    append_delegation_issued,
    append_delegation_revoked,
    append_delegation_used,
    read_delegation_events,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ledger_root(tmp_path: Path) -> Path:
    """Temporary ledger directory isolated per test."""
    return tmp_path / "consent"


def _issued_event(
    token: str = "del_" + "a" * 24, session: str = "sess-abc"
) -> DelegationIssuedEvent:  # noqa: E501
    return DelegationIssuedEvent(
        ts=datetime(2026, 4, 29, 10, 15, 23, tzinfo=UTC),
        session_id=session,
        delegation_token=token,
        scope="find:hometax.simplified,send:hometax.tax-return",
        expires_at=datetime(2026, 4, 30, 10, 15, 23, tzinfo=UTC),
        issuer_did="did:web:mobileid.go.kr",
        verify_tool_id="mock_verify_module_modid",
    )


def _used_event(token: str = "del_" + "a" * 24, session: str = "sess-abc") -> DelegationUsedEvent:
    return DelegationUsedEvent(
        ts=datetime(2026, 4, 29, 10, 15, 28, tzinfo=UTC),
        session_id=session,
        delegation_token=token,
        consumer_tool_id="mock_lookup_module_hometax_simplified",
        receipt_id=None,
        outcome="success",
    )


def _revoked_event(
    token: str = "del_" + "a" * 24, session: str = "sess-abc"
) -> DelegationRevokedEvent:  # noqa: E501
    return DelegationRevokedEvent(
        ts=datetime(2026, 4, 29, 10, 15, 35, tzinfo=UTC),
        session_id=session,
        delegation_token=token,
        reason="citizen_request",
    )


# ---------------------------------------------------------------------------
# Test 1: DelegationIssuedEvent round-trip
# ---------------------------------------------------------------------------


def test_delegation_issued_event_round_trip(ledger_root: Path) -> None:
    """DelegationIssuedEvent appends to JSONL and re-parses correctly."""
    event = _issued_event()
    path = append_delegation_issued(event, ledger_root=ledger_root)

    assert path.exists()
    events = read_delegation_events(ledger_root=ledger_root, date=event.ts)
    assert len(events) == 1

    parsed = events[0]
    assert isinstance(parsed, DelegationIssuedEvent)
    assert parsed.kind == "delegation_issued"
    assert parsed.delegation_token == event.delegation_token
    assert parsed.scope == event.scope
    assert parsed.session_id == event.session_id
    assert parsed.verify_tool_id == event.verify_tool_id
    assert parsed.issuer_did == event.issuer_did


# ---------------------------------------------------------------------------
# Test 2: DelegationUsedEvent round-trip
# ---------------------------------------------------------------------------


def test_delegation_used_event_round_trip(ledger_root: Path) -> None:
    """DelegationUsedEvent appends to JSONL and re-parses correctly."""
    event = _used_event()
    path = append_delegation_used(event, ledger_root=ledger_root)

    assert path.exists()
    events = read_delegation_events(ledger_root=ledger_root, date=event.ts)
    assert len(events) == 1

    parsed = events[0]
    assert isinstance(parsed, DelegationUsedEvent)
    assert parsed.kind == "delegation_used"
    assert parsed.delegation_token == event.delegation_token
    assert parsed.consumer_tool_id == event.consumer_tool_id
    assert parsed.outcome == "success"
    assert parsed.receipt_id is None


# ---------------------------------------------------------------------------
# Test 3: DelegationRevokedEvent round-trip
# ---------------------------------------------------------------------------


def test_delegation_revoked_event_round_trip(ledger_root: Path) -> None:
    """DelegationRevokedEvent appends to JSONL and re-parses correctly."""
    event = _revoked_event()
    path = append_delegation_revoked(event, ledger_root=ledger_root)

    assert path.exists()
    events = read_delegation_events(ledger_root=ledger_root, date=event.ts)
    assert len(events) == 1

    parsed = events[0]
    assert isinstance(parsed, DelegationRevokedEvent)
    assert parsed.kind == "delegation_revoked"
    assert parsed.delegation_token == event.delegation_token
    assert parsed.reason == "citizen_request"


# ---------------------------------------------------------------------------
# Test 4: Multiple events on the same day — JSONL ordering preserved
# ---------------------------------------------------------------------------


def test_multiple_events_same_day(ledger_root: Path) -> None:
    """Three events appended on the same day are read back in order."""
    token = "del_" + "b" * 24
    issued = _issued_event(token=token)
    used = _used_event(token=token)
    revoked = _revoked_event(token=token)

    append_delegation_issued(issued, ledger_root=ledger_root)
    append_delegation_used(used, ledger_root=ledger_root)
    append_delegation_revoked(revoked, ledger_root=ledger_root)

    events = read_delegation_events(ledger_root=ledger_root, date=issued.ts)
    assert len(events) == 3
    assert isinstance(events[0], DelegationIssuedEvent)
    assert isinstance(events[1], DelegationUsedEvent)
    assert isinstance(events[2], DelegationRevokedEvent)


# ---------------------------------------------------------------------------
# Test 5: DelegationUsedEvent with receipt_id (submit success)
# ---------------------------------------------------------------------------


def test_delegation_used_event_with_receipt_id(ledger_root: Path) -> None:
    """DelegationUsedEvent with a non-null receipt_id round-trips."""
    event = DelegationUsedEvent(
        ts=datetime(2026, 4, 29, 10, 15, 35, tzinfo=UTC),
        session_id="sess-abc",
        delegation_token="del_" + "c" * 24,
        consumer_tool_id="mock_submit_module_hometax_taxreturn",
        receipt_id="hometax-2026-04-29-RX-7K2J9",
        outcome="success",
    )
    append_delegation_used(event, ledger_root=ledger_root)
    events = read_delegation_events(ledger_root=ledger_root, date=event.ts)
    assert len(events) == 1
    parsed = events[0]
    assert isinstance(parsed, DelegationUsedEvent)
    assert parsed.receipt_id == "hometax-2026-04-29-RX-7K2J9"


# ---------------------------------------------------------------------------
# Test 6: FileLedgerReader.find_issuance_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_ledger_reader_finds_session(ledger_root: Path) -> None:
    """FileLedgerReader.find_issuance_session returns the correct session_id.

    Note: ``find_issuance_session`` scans **today's** ledger file only (per
    ``src/ummaya/memdir/consent_ledger.py:288`` docstring — full multi-day
    scan is deferred per data-model.md § 9.1 footnote). The fixture event's
    ``ts`` MUST therefore be today's date or the read will return None when
    the calendar rolls over (Epic ζ #2297 2026-04-30 CI fix).
    """
    token = "del_" + "d" * 24
    today = datetime.now(UTC)
    event = DelegationIssuedEvent(
        ts=today,
        session_id="sess-xyz",
        delegation_token=token,
        scope="find:hometax.simplified,send:hometax.tax-return",
        expires_at=today.replace(year=today.year + 1),
        issuer_did="did:web:mobileid.go.kr",
        verify_tool_id="mock_verify_module_modid",
    )
    append_delegation_issued(event, ledger_root=ledger_root)

    reader = FileLedgerReader(ledger_root=ledger_root)
    result = await reader.find_issuance_session(token)
    assert result == "sess-xyz"


@pytest.mark.asyncio
async def test_file_ledger_reader_returns_none_for_unknown(ledger_root: Path) -> None:
    """FileLedgerReader.find_issuance_session returns None for an unknown token."""
    reader = FileLedgerReader(ledger_root=ledger_root)
    result = await reader.find_issuance_session("del_" + "z" * 24)
    assert result is None
