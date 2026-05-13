# SPDX-License-Identifier: Apache-2.0
"""T023 — Unit tests for mock_submit_module_hometax_taxreturn.

Covers:
1. Happy path: success with valid DelegationContext (scope validated via mock).
2. Scope violation: token with wrong scope returns rejected outcome.
3. Expired token: expired token returns rejected outcome.
4. Session violation: token cross-session returns rejected outcome.
5. Transparency fields: adapter_receipt carries all six fields on success.
6. Transparency fields on failure: all six fields present even on rejection.
7. Ledger assertions: delegation_used event appended for both success and failure.

Contract: specs/2296-ax-mock-adapters/tasks.md T023
"""

from __future__ import annotations

import unittest.mock as mock
from datetime import UTC, datetime, timedelta

import pytest

from ummaya.primitives.delegation import (
    DelegationContext,
    DelegationToken,
    DelegationValidationOutcome,
)
from ummaya.primitives.submit import SubmitStatus

# ---------------------------------------------------------------------------
# Shared transparency field list
# ---------------------------------------------------------------------------

_TRANSPARENCY_FIELDS = (
    "_mode",
    "_reference_implementation",
    "_actual_endpoint_when_live",
    "_security_wrapping_pattern",
    "_policy_authority",
    "_international_reference",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VP_JWT = (
    "eyJhbGciOiJub25lIiwidHlwIjoidnArand0In0.eyJzdWIiOiJtb2NrIn0.mock-signature-not-cryptographic"
)


def _make_context(
    scope: str = "send:hometax.tax-return",
    expires_in: timedelta = timedelta(hours=1),
    issued_before: timedelta = timedelta(minutes=5),
) -> DelegationContext:
    """Build a DelegationContext wrapping a DelegationToken."""
    now = datetime.now(UTC)
    token = DelegationToken(
        vp_jwt=_VP_JWT,
        delegation_token="del_" + "a" * 24,
        scope=scope,
        issuer_did="did:web:mobileid.go.kr",
        issued_at=now - issued_before,
        expires_at=now + expires_in,
        **{"_mode": "mock"},
    )
    return DelegationContext(
        token=token,
        purpose_ko="2024년 귀속 종합소득세 신고",
        purpose_en="Filing 2024 comprehensive income tax return",
    )


def _make_params(
    session_id: str = "sess-test-001",
    scope: str = "send:hometax.tax-return",
    expires_in: timedelta = timedelta(hours=1),
) -> dict:
    """Build valid params dict for invoke()."""
    ctx = _make_context(scope=scope, expires_in=expires_in)
    return {
        "tax_year": 2024,
        "income_type": "종합소득",
        "total_income_krw": 45_000_000,
        "session_id": session_id,
        "delegation_context": ctx,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_returns_succeeded() -> None:
    """Success path: validate_delegation returns OK → SubmitStatus.succeeded."""
    from ummaya.tools.mock.submit_module_hometax_taxreturn import invoke

    params = _make_params()

    # Mock validate_delegation to return OK (bypasses session/ledger checks)
    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.validate_delegation",
            return_value=DelegationValidationOutcome.OK,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.succeeded
    receipt = result.adapter_receipt
    assert "receipt_id" in receipt
    assert str(receipt["receipt_id"]).startswith("hometax-")
    assert receipt.get("mock") is True

    # Ledger event appended
    mock_append.assert_called_once()
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "success"
    assert call_event.receipt_id is not None
    assert call_event.receipt_id.startswith("hometax-")
    assert call_event.consumer_tool_id == "mock_submit_module_hometax_taxreturn"


@pytest.mark.asyncio
async def test_transparency_fields_present_on_success() -> None:
    """All six transparency fields must appear in adapter_receipt on success."""
    from ummaya.tools.mock.submit_module_hometax_taxreturn import invoke

    params = _make_params()

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.validate_delegation",
            return_value=DelegationValidationOutcome.OK,
        ),
        mock.patch("ummaya.tools.mock.submit_module_hometax_taxreturn.append_delegation_used"),
    ):
        result = await invoke(params)

    receipt = result.adapter_receipt
    for field in _TRANSPARENCY_FIELDS:
        value = receipt.get(field)
        assert value is not None and isinstance(value, str) and value.strip(), (
            f"adapter_receipt missing or empty transparency field {field!r}"
        )
    assert receipt["_mode"] == "mock"
    assert receipt["_international_reference"] == "UK HMRC Making Tax Digital"
    assert receipt["_reference_implementation"] == "ax-infrastructure-callable-channel"


@pytest.mark.asyncio
async def test_scope_violation_returns_rejected() -> None:
    """Scope violation → rejected with scope_violation outcome."""
    from ummaya.tools.mock.submit_module_hometax_taxreturn import invoke

    params = _make_params(scope="send:gov24.minwon")  # wrong scope

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.validate_delegation",
            return_value=DelegationValidationOutcome.SCOPE_VIOLATION,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    receipt = result.adapter_receipt
    assert receipt.get("error") == "scope_violation"

    # Ledger event appended with scope_violation outcome
    mock_append.assert_called_once()
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "scope_violation"
    assert call_event.receipt_id is None

    # Transparency fields still present on rejection
    for field in _TRANSPARENCY_FIELDS:
        assert field in receipt, f"Missing {field} on rejection receipt"


@pytest.mark.asyncio
async def test_expired_token_returns_rejected() -> None:
    """Expired outcome → SubmitStatus.rejected."""
    from ummaya.tools.mock.submit_module_hometax_taxreturn import invoke

    params = _make_params()

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.validate_delegation",
            return_value=DelegationValidationOutcome.EXPIRED,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "expired"


@pytest.mark.asyncio
async def test_session_violation_returns_rejected() -> None:
    """Session violation → SubmitStatus.rejected."""
    from ummaya.tools.mock.submit_module_hometax_taxreturn import invoke

    params = _make_params(session_id="sess-B")

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.validate_delegation",
            return_value=DelegationValidationOutcome.SESSION_VIOLATION,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "session_violation"


@pytest.mark.asyncio
async def test_ledger_event_consumer_tool_id() -> None:
    """delegation_used event must identify the consuming adapter correctly."""
    from ummaya.tools.mock.submit_module_hometax_taxreturn import invoke

    params = _make_params()

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.validate_delegation",
            return_value=DelegationValidationOutcome.SCOPE_VIOLATION,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.append_delegation_used"
        ) as mock_append,
    ):
        await invoke(params)

    call_event = mock_append.call_args[0][0]
    assert call_event.consumer_tool_id == "mock_submit_module_hometax_taxreturn"


@pytest.mark.asyncio
async def test_receipt_id_starts_with_hometax() -> None:
    """On success, receipt_id must start with 'hometax-' as per task spec."""
    from ummaya.tools.mock.submit_module_hometax_taxreturn import invoke

    params = _make_params()

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_hometax_taxreturn.validate_delegation",
            return_value=DelegationValidationOutcome.OK,
        ),
        mock.patch("ummaya.tools.mock.submit_module_hometax_taxreturn.append_delegation_used"),
    ):
        result = await invoke(params)

    receipt = result.adapter_receipt
    assert str(receipt["receipt_id"]).startswith("hometax-"), (
        f"receipt_id must start with 'hometax-', got {receipt['receipt_id']!r}"
    )
