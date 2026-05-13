# SPDX-License-Identifier: Apache-2.0
"""T030 — submit primitive end-to-end integration tests.

Verifies ``ummaya.primitives.submit.submit()`` end-to-end with:
  - Happy path: valid params → SubmitOutput with transaction_id, status, adapter_receipt.
  - Audit ledger emission: the AdapterRegistration captured in the dispatch table
    carries primitive="send" AND tool_id as distinct, non-empty string fields
    (FR-026 — audit must record both axes).
  - Cross-ministry shape parity: both mock_traffic_fine_pay_v1 (data_go_kr) and
    mock_welfare_application_submit_v1 (mydata) flow through the same envelope.

No live network calls are made.  Both adapters are shape-mirrored mocks (OOS).

References
----------
- specs/1634-tool-system-wiring/contracts/primitive-envelope.md § 3
- src/ummaya/primitives/submit.py
- src/ummaya/tools/mock/data_go_kr/fines_pay.py
- src/ummaya/tools/mock/mydata/welfare_application.py
"""

from __future__ import annotations

import pytest

# Import adapter modules so they self-register into the submit dispatcher
import ummaya.tools.mock.data_go_kr.fines_pay  # noqa: F401
import ummaya.tools.mock.mydata.welfare_application  # noqa: F401
from ummaya.primitives._errors import AdapterNotFoundError
from ummaya.primitives.submit import _ADAPTER_REGISTRY, SubmitOutput, SubmitStatus, submit
from ummaya.tools.registry import AdapterPrimitive

# ---------------------------------------------------------------------------
# T030-A: Happy path — mock_traffic_fine_pay_v1
# ---------------------------------------------------------------------------


class TestSubmitFinesPayHappyPath:
    """mock_traffic_fine_pay_v1 must succeed with valid params and correct envelope shape."""

    TOOL_ID = "mock_traffic_fine_pay_v1"
    VALID_PARAMS = {
        "fine_reference": "FINE-2026-001",
        "payment_method": "card",
    }

    @pytest.mark.asyncio
    async def test_submit_returns_submit_output(self) -> None:
        """submit(mock_traffic_fine_pay_v1, valid_params) returns SubmitOutput."""
        result = await submit(
            tool_id=self.TOOL_ID,
            params=self.VALID_PARAMS,
            auth_context=None,  # tier gate will reject due to AAL2 requirement
        )
        # The adapter requires AAL2 auth — without auth_context it returns status=rejected
        # This is the tier gate path: still a SubmitOutput, not an exception.
        assert isinstance(result, SubmitOutput), (
            f"Expected SubmitOutput (even rejected), got {type(result).__name__}"
        )

    @pytest.mark.asyncio
    async def test_submit_with_matching_tier_succeeds(self) -> None:
        """submit() with matching AAL2 tier → status=succeeded."""
        from pydantic import BaseModel, ConfigDict

        class _MinimalAuthContext(BaseModel):
            model_config = ConfigDict(frozen=True, extra="allow")
            published_tier: str

        auth_ctx = _MinimalAuthContext(published_tier="ganpyeon_injeung_kakao_aal2")
        result = await submit(
            tool_id=self.TOOL_ID,
            params=self.VALID_PARAMS,
            auth_context=auth_ctx,
        )
        assert isinstance(result, SubmitOutput)
        assert result.status == SubmitStatus.succeeded
        assert result.transaction_id.startswith("urn:ummaya:send:")
        assert isinstance(result.adapter_receipt, dict)
        assert len(result.adapter_receipt) > 0

    @pytest.mark.asyncio
    async def test_submit_output_has_correct_envelope_fields(self) -> None:
        """SubmitOutput must carry exactly {transaction_id, status, adapter_receipt}."""
        from pydantic import BaseModel, ConfigDict

        class _MinimalAuthContext(BaseModel):
            model_config = ConfigDict(frozen=True, extra="allow")
            published_tier: str

        auth_ctx = _MinimalAuthContext(published_tier="ganpyeon_injeung_kakao_aal2")
        result = await submit(
            tool_id=self.TOOL_ID,
            params=self.VALID_PARAMS,
            auth_context=auth_ctx,
        )
        assert isinstance(result, SubmitOutput)
        # FR-026 / SC-002: envelope is shape-only — no domain fields at top level
        envelope_keys = set(result.model_dump().keys())
        assert envelope_keys == {"transaction_id", "status", "adapter_receipt"}, (
            f"Unexpected envelope fields: {envelope_keys}"
        )

    @pytest.mark.asyncio
    async def test_submit_transaction_id_is_urn(self) -> None:
        """transaction_id must be a URN in urn:ummaya:send: format (FR-004)."""
        from pydantic import BaseModel, ConfigDict

        class _MinimalAuthContext(BaseModel):
            model_config = ConfigDict(frozen=True, extra="allow")
            published_tier: str

        auth_ctx = _MinimalAuthContext(published_tier="ganpyeon_injeung_kakao_aal2")
        result = await submit(
            tool_id=self.TOOL_ID,
            params=self.VALID_PARAMS,
            auth_context=auth_ctx,
        )
        assert isinstance(result, SubmitOutput)
        assert result.transaction_id.startswith("urn:ummaya:send:")
        # SHA-256 hex is 64 chars; total URN length tracks the active project prefix.
        assert len(result.transaction_id) == len("urn:ummaya:send:") + 64


# ---------------------------------------------------------------------------
# T030-B: Happy path — mock_welfare_application_submit_v1
# ---------------------------------------------------------------------------


class TestSubmitWelfareApplicationHappyPath:
    """mock_welfare_application_submit_v1 must return correct envelope shape."""

    TOOL_ID = "mock_welfare_application_submit_v1"
    VALID_PARAMS = {
        "applicant_id": "citizen-DI-abc123",
        "benefit_code": "기초생활수급",
        "application_type": "new",
        "household_size": 3,
    }

    @pytest.mark.asyncio
    async def test_submit_welfare_with_matching_tier_succeeds(self) -> None:
        """mock_welfare_application_submit_v1 with mydata AAL2 tier → succeeded."""
        from pydantic import BaseModel, ConfigDict

        class _MinimalAuthContext(BaseModel):
            model_config = ConfigDict(frozen=True, extra="allow")
            published_tier: str

        auth_ctx = _MinimalAuthContext(published_tier="mydata_individual_aal2")
        result = await submit(
            tool_id=self.TOOL_ID,
            params=self.VALID_PARAMS,
            auth_context=auth_ctx,
        )
        assert isinstance(result, SubmitOutput)
        assert result.status == SubmitStatus.succeeded
        assert result.transaction_id.startswith("urn:ummaya:send:")

    @pytest.mark.asyncio
    async def test_submit_welfare_adapter_receipt_contains_benefit_code(self) -> None:
        """adapter_receipt must carry benefit_code from the typed adapter params."""
        from pydantic import BaseModel, ConfigDict

        class _MinimalAuthContext(BaseModel):
            model_config = ConfigDict(frozen=True, extra="allow")
            published_tier: str

        auth_ctx = _MinimalAuthContext(published_tier="mydata_individual_aal2")
        result = await submit(
            tool_id=self.TOOL_ID,
            params=self.VALID_PARAMS,
            auth_context=auth_ctx,
        )
        assert isinstance(result, SubmitOutput)
        assert "benefit_code" in result.adapter_receipt
        assert result.adapter_receipt["benefit_code"] == "기초생활수급"


# ---------------------------------------------------------------------------
# T030-C: Unregistered tool_id returns structured AdapterNotFoundError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_unregistered_tool_id_returns_structured_error() -> None:
    """Unregistered tool_id must return AdapterNotFoundError, not raise (FR-005)."""
    result = await submit(
        tool_id="nonexistent_adapter_xyz_v1",
        params={},
    )
    assert isinstance(result, AdapterNotFoundError), (
        f"Expected AdapterNotFoundError, got {type(result).__name__}"
    )
    assert result.tool_id == "nonexistent_adapter_xyz_v1"
    assert result.reason == "adapter_not_found"


# ---------------------------------------------------------------------------
# T030-D: FR-026 — registered adapter carries primitive + tool_id as distinct fields
# ---------------------------------------------------------------------------


def test_adapter_registry_carries_primitive_and_tool_id_separately() -> None:
    """FR-026: dispatch table entry carries primitive AND tool_id as distinct str fields.

    This verifies the audit axis precondition: the AdapterRegistration stored in
    the in-process submit registry has both ``primitive`` (the verb) and ``tool_id``
    (the adapter id) as separate, non-empty strings that are NOT concatenated.
    """
    assert "mock_traffic_fine_pay_v1" in _ADAPTER_REGISTRY, (
        "mock_traffic_fine_pay_v1 must be registered by module import"
    )
    registration, _ = _ADAPTER_REGISTRY["mock_traffic_fine_pay_v1"]

    # Both fields must be non-empty strings
    assert isinstance(registration.primitive, str) and len(registration.primitive) > 0
    assert isinstance(registration.tool_id, str) and len(registration.tool_id) > 0

    # They must NOT be the same value
    assert registration.primitive != registration.tool_id, (
        "primitive and tool_id must be distinct (FR-026)"
    )

    # The primitive field must identify the verb, not the adapter
    assert registration.primitive == AdapterPrimitive.send, (
        f"Expected primitive='send', got {registration.primitive!r}"
    )

    # The tool_id field must identify the specific adapter
    assert registration.tool_id == "mock_traffic_fine_pay_v1"
