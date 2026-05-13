# SPDX-License-Identifier: Apache-2.0
"""T003 — DelegationToken, DelegationContext, IdentityAssertion unit tests.

Covers:
- Construction (happy + 4 validator failure paths)
- _scope_matches (8 table-driven cases)
- validate_delegation (5 outcome paths)

Contract: specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 4, 8
Data model: specs/2296-ax-mock-adapters/data-model.md § 1-3
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from ummaya.primitives.delegation import (
    DelegationContext,
    DelegationToken,
    DelegationValidationOutcome,
    IdentityAssertion,
    _scope_matches,
    validate_delegation,
)

# ---------------------------------------------------------------------------
# Helpers for constructing valid fixtures
# ---------------------------------------------------------------------------


def _make_vp_jwt(payload: dict | None = None) -> str:
    """Produce a minimal dot-separated JWS string for testing."""
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "vp+jwt"}).encode())
        .decode()
        .rstrip("=")
    )
    pay = (
        base64.urlsafe_b64encode(json.dumps(payload or {"sub": "citizen-123"}).encode())
        .decode()
        .rstrip("=")
    )
    return f"{header}.{pay}.mock-signature-not-cryptographic"


_VALID_TOKEN_DATA = {
    "vp_jwt": _make_vp_jwt(),
    "delegation_token": "del_" + "a" * 24,  # exactly 24 chars after prefix
    "scope": "send:hometax.tax-return",
    "issuer_did": "did:web:mobileid.go.kr",
    # Anchor far enough in the future that natural calendar drift between
    # spec authoring and CI runs cannot expire the token (5 years buffer).
    "issued_at": datetime(2031, 1, 1, 10, 0, 0, tzinfo=UTC),
    "expires_at": datetime(2031, 1, 2, 10, 0, 0, tzinfo=UTC),  # +24h
}


def _valid_token() -> DelegationToken:
    return DelegationToken(**_VALID_TOKEN_DATA)


def _valid_context(scope: str | None = None) -> DelegationContext:
    token_data = {**_VALID_TOKEN_DATA}
    if scope is not None:
        token_data["scope"] = scope
    token = DelegationToken(**token_data)
    return DelegationContext(
        token=token,
        purpose_ko="2024년 귀속 종합소득세 신고",
        purpose_en="Filing 2024 comprehensive income tax return",
    )


# ---------------------------------------------------------------------------
# T003-A: DelegationToken construction (happy path)
# ---------------------------------------------------------------------------


def test_delegation_token_happy_path() -> None:
    """Valid DelegationToken constructs without error."""
    token = _valid_token()
    assert token.delegation_token.startswith("del_")
    assert token.scope == "send:hometax.tax-return"
    assert token.expires_at > token.issued_at


def test_delegation_token_multi_scope_happy_path() -> None:
    """Multi-scope (comma-joined) token is valid."""
    token = DelegationToken(
        **{
            **_VALID_TOKEN_DATA,
            "scope": "find:hometax.simplified,send:hometax.tax-return",
        }
    )
    assert "send:hometax.tax-return" in token.scope.split(",")
    assert "find:hometax.simplified" in token.scope.split(",")


# ---------------------------------------------------------------------------
# T003-B: DelegationToken validator failures (4 paths)
# ---------------------------------------------------------------------------


def test_delegation_token_validator_expiry_before_issued() -> None:
    """expires_at <= issued_at must raise ValueError."""
    with pytest.raises(ValidationError) as exc_info:
        DelegationToken(
            **{
                **_VALID_TOKEN_DATA,
                "expires_at": _VALID_TOKEN_DATA["issued_at"],  # equal, not greater
            }
        )
    assert "expires_at" in str(exc_info.value) or "strictly greater" in str(exc_info.value)


def test_delegation_token_validator_bad_scope() -> None:
    """Scope not matching grammar must raise ValueError."""
    with pytest.raises(ValidationError) as exc_info:
        DelegationToken(**{**_VALID_TOKEN_DATA, "scope": "bad-scope"})
    assert "scope" in str(exc_info.value).lower()


def test_delegation_token_validator_bad_token_prefix() -> None:
    """delegation_token not starting with 'del_' must raise ValueError."""
    with pytest.raises(ValidationError) as exc_info:
        DelegationToken(**{**_VALID_TOKEN_DATA, "delegation_token": "tok_" + "a" * 24})
    assert "del_" in str(exc_info.value) or "delegation_token" in str(exc_info.value)


def test_delegation_token_validator_token_too_short() -> None:
    """delegation_token with fewer than 24 chars after prefix must raise ValueError."""
    with pytest.raises(ValidationError) as exc_info:
        DelegationToken(**{**_VALID_TOKEN_DATA, "delegation_token": "del_short"})
    assert "24" in str(exc_info.value) or "delegation_token" in str(exc_info.value)


def test_delegation_token_validator_bad_jws_shape() -> None:
    """vp_jwt not having exactly 3 dot-separated parts must raise ValueError."""
    with pytest.raises(ValidationError) as exc_info:
        DelegationToken(**{**_VALID_TOKEN_DATA, "vp_jwt": "only-two.parts"})
    assert "JWS" in str(exc_info.value) or "vp_jwt" in str(exc_info.value)


# ---------------------------------------------------------------------------
# T003-C: _scope_matches — 8 table-driven cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token_scope, required, expected",
    [
        # 1. Single scope — exact match
        ("send:hometax.tax-return", "send:hometax.tax-return", True),
        # 2. Single scope — no match
        ("send:hometax.tax-return", "send:gov24.minwon", False),
        # 3. Multi-scope — required is first entry
        ("send:hometax.tax-return,find:hometax.simplified", "send:hometax.tax-return", True),
        # 4. Multi-scope — required is second entry
        ("find:hometax.simplified,send:hometax.tax-return", "send:hometax.tax-return", True),
        # 5. Multi-scope — required is NOT in any entry
        ("find:hometax.simplified,send:hometax.tax-return", "send:gov24.minwon", False),
        # 6. Prefix substring is NOT a match (scope must be an exact entry after split)
        ("send:hometax.tax-return", "send:hometax", False),
        # 7. Empty required never matches (empty string not in any comma list)
        ("send:hometax.tax-return", "", False),
        # 8. Three-scope token — middle match
        (
            "check:modid.ceremony,find:hometax.simplified,send:hometax.tax-return",
            "find:hometax.simplified",
            True,
        ),
    ],
)
def test_scope_matches_table_driven(token_scope: str, required: str, expected: bool) -> None:
    assert _scope_matches(token_scope, required) == expected, (
        f"_scope_matches({token_scope!r}, {required!r}) expected {expected}"
    )


# ---------------------------------------------------------------------------
# T003-D: validate_delegation — 5 outcome paths
# ---------------------------------------------------------------------------


def _make_ledger_reader(session_id: str | None) -> AsyncMock:
    """Return a mock ledger reader that reports a given issuance session_id."""
    reader = AsyncMock()
    reader.find_issuance_session = AsyncMock(return_value=session_id)
    return reader


@pytest.mark.asyncio
async def test_validate_delegation_ok() -> None:
    """All checks pass → DelegationValidationOutcome.OK."""
    context = _valid_context("send:hometax.tax-return")
    ledger = _make_ledger_reader(session_id="sess-abc")
    outcome = await validate_delegation(
        context,
        required_scope="send:hometax.tax-return",
        current_session_id="sess-abc",
        revoked_set=set(),
        ledger_reader=ledger,
    )
    assert outcome == DelegationValidationOutcome.OK


@pytest.mark.asyncio
async def test_validate_delegation_expired() -> None:
    """Token past expires_at → EXPIRED (checked first)."""
    past = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    token = DelegationToken(
        **{
            **_VALID_TOKEN_DATA,
            "issued_at": datetime(2024, 12, 31, 0, 0, 0, tzinfo=UTC),
            "expires_at": past,
        }
    )
    context = DelegationContext(
        token=token,
        purpose_ko="테스트",
        purpose_en="test",
    )
    ledger = _make_ledger_reader(session_id="sess-abc")
    outcome = await validate_delegation(
        context,
        required_scope="send:hometax.tax-return",
        current_session_id="sess-abc",
        revoked_set=set(),
        ledger_reader=ledger,
    )
    assert outcome == DelegationValidationOutcome.EXPIRED


@pytest.mark.asyncio
async def test_validate_delegation_scope_violation() -> None:
    """Token scope does not include required_scope → SCOPE_VIOLATION."""
    context = _valid_context("send:hometax.tax-return")
    ledger = _make_ledger_reader(session_id="sess-abc")
    outcome = await validate_delegation(
        context,
        required_scope="send:gov24.minwon",  # not in token scope
        current_session_id="sess-abc",
        revoked_set=set(),
        ledger_reader=ledger,
    )
    assert outcome == DelegationValidationOutcome.SCOPE_VIOLATION


@pytest.mark.asyncio
async def test_validate_delegation_session_violation() -> None:
    """Token issued in different session → SESSION_VIOLATION."""
    context = _valid_context("send:hometax.tax-return")
    ledger = _make_ledger_reader(session_id="sess-original")
    outcome = await validate_delegation(
        context,
        required_scope="send:hometax.tax-return",
        current_session_id="sess-different",
        revoked_set=set(),
        ledger_reader=ledger,
    )
    assert outcome == DelegationValidationOutcome.SESSION_VIOLATION


@pytest.mark.asyncio
async def test_validate_delegation_revoked() -> None:
    """Token in revoked_set → REVOKED (after scope + session pass)."""
    context = _valid_context("send:hometax.tax-return")
    token_value = context.token.delegation_token
    ledger = _make_ledger_reader(session_id="sess-abc")
    outcome = await validate_delegation(
        context,
        required_scope="send:hometax.tax-return",
        current_session_id="sess-abc",
        revoked_set={token_value},
        ledger_reader=ledger,
    )
    assert outcome == DelegationValidationOutcome.REVOKED


# ---------------------------------------------------------------------------
# IdentityAssertion — basic construction
# ---------------------------------------------------------------------------


def test_identity_assertion_happy_path() -> None:
    """IdentityAssertion constructs without error."""
    jwt = "header.payload.mock-signature"
    ia = IdentityAssertion(
        assertion_jwt=jwt,
        expires_at=datetime(2026, 4, 30, 10, 0, 0, tzinfo=UTC),
    )
    assert ia.assertion_jwt == jwt
    assert ia.citizen_did is None


def test_identity_assertion_bad_jws_shape() -> None:
    """assertion_jwt with wrong number of parts raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        IdentityAssertion(
            assertion_jwt="only.two",
            expires_at=datetime(2026, 4, 30, 10, 0, 0, tzinfo=UTC),
        )
    assert "JWS" in str(exc_info.value) or "assertion_jwt" in str(exc_info.value)
