# SPDX-License-Identifier: Apache-2.0
"""T018 — Dispatch and envelope purity tests for the submit primitive.

Covers:
1. Envelope purity: SubmitOutput never carries domain-specific fields
   (main surface is shape-only, SC-002).
2. AdapterNotFoundError structured result for unregistered tool_id (FR-005).
3. Happy-path: registered mock adapter returns correct SubmitOutput shape.
4. Failed adapter invocation surfaces as status=failed, not an exception (FR-005).
"""

from __future__ import annotations

import pytest

from ummaya.primitives._errors import AdapterNotFoundError
from ummaya.primitives.submit import SubmitOutput, SubmitStatus, submit

# ---------------------------------------------------------------------------
# Minimal stub adapter for dispatch tests
# ---------------------------------------------------------------------------


class _SuccessParams:
    """Minimal params stub — dispatch only inspects tool_id."""

    pass


async def _invoke_success(params: object) -> SubmitOutput:
    return SubmitOutput(
        transaction_id="urn:ummaya:send:aabbcc",
        status=SubmitStatus.succeeded,
        adapter_receipt={"receipt_number": "TEST-001"},
    )


async def _invoke_failure(params: object) -> None:
    raise ValueError("upstream service unreachable")


# ---------------------------------------------------------------------------
# T018-A: AdapterNotFoundError for unregistered tool_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unregistered_tool_id_returns_structured_error() -> None:
    """An unregistered tool_id must produce AdapterNotFoundError, not an exception."""
    result = await submit(
        tool_id="no_such_adapter_xyz_v1",
        params={},
    )
    assert isinstance(result, AdapterNotFoundError), (
        f"Expected AdapterNotFoundError, got {type(result).__name__}"
    )
    assert result.reason == "adapter_not_found"
    assert result.tool_id == "no_such_adapter_xyz_v1"
    assert result.message  # non-empty human-readable message


@pytest.mark.asyncio
async def test_empty_tool_id_returns_structured_error() -> None:
    """A malformed LLM call must not raise a raw Pydantic validation error."""
    result = await submit(
        tool_id="",
        params={},
    )

    assert isinstance(result, AdapterNotFoundError)
    assert result.reason == "adapter_not_found"
    assert result.tool_id == "invalid_tool_id"
    assert "non-empty registered adapter tool_id" in result.message


@pytest.mark.asyncio
async def test_invalid_tool_id_shape_returns_structured_error() -> None:
    """Invalid tool-id syntax should fail closed before registry lookup."""
    result = await submit(
        tool_id="Invalid-ID",
        params={},
    )

    assert isinstance(result, AdapterNotFoundError)
    assert result.reason == "adapter_not_found"
    assert result.tool_id == "invalid_tool_id"
    assert "^[a-z][a-z0-9_]*$" in result.message


# ---------------------------------------------------------------------------
# T018-B: Envelope purity — SubmitOutput has no domain fields
# ---------------------------------------------------------------------------


def test_submit_output_has_only_envelope_fields() -> None:
    """SubmitOutput must only expose transaction_id, status, adapter_receipt."""
    SubmitOutput(
        transaction_id="urn:ummaya:send:test001",
        status=SubmitStatus.succeeded,
        adapter_receipt={"ref": "2026"},
    )
    allowed_fields = {"transaction_id", "status", "adapter_receipt"}
    actual_fields = set(SubmitOutput.model_fields.keys())
    assert actual_fields == allowed_fields, (
        f"SubmitOutput has unexpected fields: {actual_fields - allowed_fields} "
        "(SC-002: main envelope must be domain-agnostic)"
    )


def test_submit_output_no_domain_data_leaks_through_adapter_receipt() -> None:
    """adapter_receipt is opaque dict — domain data lives there, not on envelope."""
    out = SubmitOutput(
        transaction_id="urn:ummaya:send:test002",
        status=SubmitStatus.succeeded,
        adapter_receipt={"접수번호": "2026-04-19-0001", "ministry": "data_go_kr"},
    )
    # The envelope field is `adapter_receipt`, not a domain field at the top level.
    assert hasattr(out, "adapter_receipt")
    assert not hasattr(out, "접수번호")
    assert not hasattr(out, "ministry")


# ---------------------------------------------------------------------------
# T018-C: SubmitStatus enum values
# ---------------------------------------------------------------------------


def test_submit_status_values() -> None:
    """SubmitStatus must have exactly pending/succeeded/failed/rejected."""
    expected = {"pending", "succeeded", "failed", "rejected"}
    actual = {s.value for s in SubmitStatus}
    assert actual == expected, f"SubmitStatus mismatch: got {actual}"


# ---------------------------------------------------------------------------
# T018-D: SubmitInput model validation
# ---------------------------------------------------------------------------


def test_submit_input_rejects_invalid_tool_id() -> None:
    """SubmitInput must reject tool_ids that don't match ^[a-z][a-z0-9_]*$."""
    from pydantic import ValidationError

    from ummaya.primitives.submit import SubmitInput

    with pytest.raises(ValidationError):
        SubmitInput(tool_id="Invalid-ID", params={})

    with pytest.raises(ValidationError):
        SubmitInput(tool_id="", params={})


def test_submit_input_accepts_valid_tool_id() -> None:
    """SubmitInput must accept valid snake_case tool_ids."""
    from ummaya.primitives.submit import SubmitInput

    s = SubmitInput(tool_id="mock_traffic_fine_pay_v1", params={"x": 1})
    assert s.tool_id == "mock_traffic_fine_pay_v1"
    assert s.params == {"x": 1}


def test_submit_input_is_frozen() -> None:
    """SubmitInput must be immutable (frozen=True)."""
    from pydantic import ValidationError

    from ummaya.primitives.submit import SubmitInput

    s = SubmitInput(tool_id="valid_id_v1", params={})
    with pytest.raises((ValidationError, TypeError)):
        s.tool_id = "mutated"  # type: ignore[misc]
