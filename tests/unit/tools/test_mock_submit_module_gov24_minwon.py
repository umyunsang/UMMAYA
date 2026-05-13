# SPDX-License-Identifier: Apache-2.0
"""T024 — Unit tests for mock_submit_module_gov24_minwon.

Covers:
1. Happy path: success with valid DelegationContext (scope validated via mock).
2. Scope violation: wrong scope → rejected with scope_violation.
3. Expired token: → rejected with expired.
4. Session violation: cross-session → rejected with session_violation.
5. Transparency fields: adapter_receipt carries all six fields on success and failure.
6. Ledger assertion: delegation_used event appended with correct consumer_tool_id.

Contract: specs/2296-ax-mock-adapters/tasks.md T024
"""

from __future__ import annotations

import unittest.mock as mock
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel, ConfigDict

from ummaya.primitives.delegation import (
    DelegationContext,
    DelegationToken,
    DelegationValidationOutcome,
)
from ummaya.primitives.submit import SubmitStatus

# ---------------------------------------------------------------------------
# Transparency fields list
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
    scope: str = "send:gov24.minwon",
    expires_in: timedelta = timedelta(hours=1),
    issued_before: timedelta = timedelta(minutes=5),
) -> DelegationContext:
    now = datetime.now(UTC)
    token = DelegationToken(
        vp_jwt=_VP_JWT,
        delegation_token="del_" + "b" * 24,
        scope=scope,
        issuer_did="did:web:mobileid.go.kr",
        issued_at=now - issued_before,
        expires_at=now + expires_in,
        **{"_mode": "mock"},
    )
    return DelegationContext(
        token=token,
        purpose_ko="정부24 주민등록등본 신청",
        purpose_en="Requesting resident registration certificate via Government24",
    )


def _make_params(
    session_id: str = "sess-gov24-001",
    scope: str = "send:gov24.minwon",
) -> dict:
    ctx = _make_context(scope=scope)
    return {
        "minwon_type": "주민등록등본",
        "applicant_name": "홍길동",
        "delivery_method": "online",
        "session_id": session_id,
        "delegation_context": ctx,
    }


class _AuthForTierGate(BaseModel):
    model_config = ConfigDict(frozen=True)

    published_tier: str


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_gov24_registration_accepts_simple_auth_tier() -> None:
    """Gov24 minwon submit tier gate matches the canonical simple-auth verify mapping."""
    from ummaya.primitives.submit import check_tier_gate
    from ummaya.tools.mock.submit_module_gov24_minwon import REGISTRATION

    assert REGISTRATION.published_tier_minimum == "simple_auth_module_aal2"
    assert (
        check_tier_gate(
            registration=REGISTRATION,
            auth_context=_AuthForTierGate(published_tier="simple_auth_module_aal2"),
        )
        is None
    )


@pytest.mark.asyncio
async def test_gov24_happy_path_returns_succeeded() -> None:
    """Valid scope + session → SubmitStatus.succeeded with receipt_id starting 'gov24-'."""
    from ummaya.tools.mock.submit_module_gov24_minwon import invoke

    params = _make_params()

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.validate_delegation",
            return_value=DelegationValidationOutcome.OK,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.succeeded
    receipt = result.adapter_receipt
    assert str(receipt.get("receipt_id", "")).startswith("gov24-")
    assert receipt.get("mock") is True

    mock_append.assert_called_once()
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "success"
    assert call_event.receipt_id is not None
    assert call_event.consumer_tool_id == "mock_submit_module_gov24_minwon"


@pytest.mark.asyncio
async def test_gov24_transparency_fields_present() -> None:
    """All six transparency fields are present in adapter_receipt."""
    from ummaya.tools.mock.submit_module_gov24_minwon import invoke

    params = _make_params()

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.validate_delegation",
            return_value=DelegationValidationOutcome.OK,
        ),
        mock.patch("ummaya.tools.mock.submit_module_gov24_minwon.append_delegation_used"),
    ):
        result = await invoke(params)

    receipt = result.adapter_receipt
    for field in _TRANSPARENCY_FIELDS:
        val = receipt.get(field)
        assert val is not None and isinstance(val, str) and val.strip(), (
            f"Missing or empty {field!r} in adapter_receipt"
        )
    assert receipt["_mode"] == "mock"
    assert receipt["_international_reference"] == "Singapore APEX"
    assert receipt["_reference_implementation"] == "ax-infrastructure-callable-channel"


@pytest.mark.asyncio
async def test_gov24_scope_violation_returns_rejected() -> None:
    """Wrong scope token → rejected with scope_violation."""
    from ummaya.tools.mock.submit_module_gov24_minwon import invoke

    params = _make_params()

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.validate_delegation",
            return_value=DelegationValidationOutcome.SCOPE_VIOLATION,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "scope_violation"
    assert call_event.receipt_id is None

    # Transparency fields still present on rejection
    receipt = result.adapter_receipt
    for field in _TRANSPARENCY_FIELDS:
        assert field in receipt


@pytest.mark.asyncio
async def test_gov24_expired_token_returns_rejected() -> None:
    """Expired outcome → rejected with expired outcome."""
    from ummaya.tools.mock.submit_module_gov24_minwon import invoke

    params = _make_params()

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.validate_delegation",
            return_value=DelegationValidationOutcome.EXPIRED,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "expired"


@pytest.mark.asyncio
async def test_gov24_session_violation_returns_rejected() -> None:
    """Session violation outcome → rejected."""
    from ummaya.tools.mock.submit_module_gov24_minwon import invoke

    params = _make_params(session_id="sess-B")

    with (
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.validate_delegation",
            return_value=DelegationValidationOutcome.SESSION_VIOLATION,
        ),
        mock.patch(
            "ummaya.tools.mock.submit_module_gov24_minwon.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "session_violation"
