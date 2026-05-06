# SPDX-License-Identifier: Apache-2.0
"""T025 — Unit tests for mock_submit_module_public_mydata_action.

Covers:
1. Happy path: success with valid DelegationContext (mocked validate_delegation).
2. Scope violation: wrong scope → rejected with scope_violation.
3. Expired token: → rejected with expired.
4. Session violation: → rejected with session_violation.
5. Transparency fields: all six present in adapter_receipt on success and failure.
6. Ledger assertions: delegation_used event has correct consumer_tool_id.

Contract: specs/2296-ax-mock-adapters/tasks.md T025
"""

from __future__ import annotations

import unittest.mock as mock
from datetime import UTC, datetime, timedelta

import pytest

from kosmos.primitives.delegation import (
    DelegationContext,
    DelegationToken,
    DelegationValidationOutcome,
)
from kosmos.primitives.submit import SubmitStatus

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
    scope: str = "submit:public_mydata.action",
    expires_in: timedelta = timedelta(hours=1),
    issued_before: timedelta = timedelta(minutes=5),
) -> DelegationContext:
    now = datetime.now(UTC)
    token = DelegationToken(
        vp_jwt=_VP_JWT,
        delegation_token="del_" + "c" * 24,
        scope=scope,
        issuer_did="did:web:mobileid.go.kr",
        issued_at=now - issued_before,
        expires_at=now + expires_in,
        **{"_mode": "mock"},
    )
    return DelegationContext(
        token=token,
        purpose_ko="마이데이터 동의 범위 업데이트",
        purpose_en="Updating MyData consent scope",
    )


def _make_params(
    session_id: str = "sess-mydata-001",
    scope: str = "submit:public_mydata.action",
) -> dict:
    ctx = _make_context(scope=scope)
    return {
        "action_type": "update_scope",
        "target_institution_code": "KSB001",
        "applicant_di": "di-test-user-001",
        "session_id": session_id,
        "delegation_context": ctx,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mydata_action_happy_path_returns_succeeded() -> None:
    """Valid delegation → SubmitStatus.succeeded with receipt_id starting 'mydata-'."""
    from kosmos.tools.mock.submit_module_public_mydata_action import invoke

    params = _make_params()

    with (
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.validate_delegation",
            return_value=DelegationValidationOutcome.OK,
        ),
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.succeeded
    receipt = result.adapter_receipt
    assert str(receipt.get("receipt_id", "")).startswith("mydata-")
    assert receipt.get("mock") is True
    assert receipt.get("action_type") == "update_scope"
    assert receipt["consent_action"]["bundle_policy"] == "minimum_items_for_declared_purpose"
    assert "distribution_trace_ref" in receipt["audit_refs"]

    mock_append.assert_called_once()
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "success"
    assert call_event.receipt_id is not None
    assert call_event.consumer_tool_id == "mock_submit_module_public_mydata_action"


@pytest.mark.asyncio
async def test_mydata_action_transparency_fields_present() -> None:
    """All six transparency fields are present in adapter_receipt on success."""
    from kosmos.tools.mock.submit_module_public_mydata_action import invoke

    params = _make_params()

    with (
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.validate_delegation",
            return_value=DelegationValidationOutcome.OK,
        ),
        mock.patch("kosmos.tools.mock.submit_module_public_mydata_action.append_delegation_used"),
    ):
        result = await invoke(params)

    receipt = result.adapter_receipt
    for field in _TRANSPARENCY_FIELDS:
        val = receipt.get(field)
        assert val is not None and isinstance(val, str) and val.strip(), (
            f"Missing or empty {field!r} in adapter_receipt"
        )
    assert receipt["_mode"] == "mock"
    assert receipt["_international_reference"] == "Estonia X-Road"
    assert receipt["_reference_implementation"] == "public-mydata-action-extension"
    assert receipt["_mock_fidelity_grade"] == (
        "B-official-public-mydata-flow-action-extension-inferred"
    )
    assert receipt["_mock_evidence"]["credential_status"] == "student_no_live_authority"


@pytest.mark.asyncio
async def test_mydata_action_scope_violation_returns_rejected() -> None:
    """Wrong scope → rejected with scope_violation outcome."""
    from kosmos.tools.mock.submit_module_public_mydata_action import invoke

    params = _make_params()

    with (
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.validate_delegation",
            return_value=DelegationValidationOutcome.SCOPE_VIOLATION,
        ),
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "scope_violation"

    # Transparency fields still present on rejection
    receipt = result.adapter_receipt
    for field in _TRANSPARENCY_FIELDS:
        assert field in receipt


@pytest.mark.asyncio
async def test_mydata_action_expired_token_returns_rejected() -> None:
    """Expired outcome → rejected."""
    from kosmos.tools.mock.submit_module_public_mydata_action import invoke

    params = _make_params()

    with (
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.validate_delegation",
            return_value=DelegationValidationOutcome.EXPIRED,
        ),
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "expired"


@pytest.mark.asyncio
async def test_mydata_action_session_violation_returns_rejected() -> None:
    """Session violation outcome → rejected."""
    from kosmos.tools.mock.submit_module_public_mydata_action import invoke

    params = _make_params(session_id="sess-B")

    with (
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.validate_delegation",
            return_value=DelegationValidationOutcome.SESSION_VIOLATION,
        ),
        mock.patch(
            "kosmos.tools.mock.submit_module_public_mydata_action.append_delegation_used"
        ) as mock_append,
    ):
        result = await invoke(params)

    assert result.status == SubmitStatus.rejected
    call_event = mock_append.call_args[0][0]
    assert call_event.outcome == "session_violation"
