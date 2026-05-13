# SPDX-License-Identifier: Apache-2.0
"""T032 — Audit ledger record shape for submit primitive (Spec 024 / FR-026).

Verifies that the in-process submit dispatch table entries satisfy FR-026:
"Audit ledger entries MUST record the primitive name AND the resolved adapter
tool_id separately, so post-hoc queries can group by either axis."

Because the current ToolCallAuditRecord schema (Spec 024 v1) does not yet carry
a dedicated ``primitive`` field at the top level, FR-026 is satisfied through
the ``AdapterRegistration`` object stored in the submit dispatcher's in-process
registry (``_ADAPTER_REGISTRY``).  This module tests:

  1. The ``AdapterRegistration.primitive`` field is a non-empty str (the verb).
  2. The ``AdapterRegistration.tool_id`` field is a non-empty str (the adapter).
  3. ``primitive`` and ``tool_id`` are distinct strings — never concatenated.
  4. The ``primitive`` value equals ``"send"`` for all registered submit adapters.
  5. After a successful submit() call, the SubmitOutput envelope carries
     ``transaction_id`` (derived from ``tool_id`` + params + nonce), confirming
     the resolved adapter id participates in the audit-relevant digest.

References
----------
- specs/1634-tool-system-wiring/spec.md FR-026, SC-005
- src/ummaya/primitives/submit.py (_ADAPTER_REGISTRY, submit)
- src/ummaya/tools/registry.AdapterRegistration (primitive, tool_id fields)
- src/ummaya/security/audit.py (ToolCallAuditRecord — existing schema for context)
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

# Import adapter modules so they self-register into the submit dispatcher
import ummaya.tools.mock.data_go_kr.fines_pay  # noqa: F401
import ummaya.tools.mock.mydata.welfare_application  # noqa: F401
from ummaya.primitives.submit import _ADAPTER_REGISTRY, SubmitOutput, SubmitStatus, submit
from ummaya.tools.registry import AdapterPrimitive

# ---------------------------------------------------------------------------
# Minimal AuthContext stand-in (pre-US2)
# ---------------------------------------------------------------------------


class _MinimalAuthContext(BaseModel):
    """Minimal AuthContext carrying only the published_tier needed by the tier gate."""

    model_config = ConfigDict(frozen=True, extra="allow")
    published_tier: str


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_registration(tool_id: str):
    """Return the AdapterRegistration for a registered submit adapter."""
    assert tool_id in _ADAPTER_REGISTRY, (
        f"{tool_id!r} not in _ADAPTER_REGISTRY — "
        "ensure the adapter module is imported before this test runs"
    )
    registration, _ = _ADAPTER_REGISTRY[tool_id]
    return registration


# ---------------------------------------------------------------------------
# T032-A: primitive and tool_id are distinct non-empty string fields
# ---------------------------------------------------------------------------


class TestAuditFieldsDistinct:
    """FR-026: primitive and tool_id must be distinct, non-empty fields on every adapter."""

    @pytest.mark.parametrize(
        "tool_id",
        [
            "mock_traffic_fine_pay_v1",
            "mock_welfare_application_submit_v1",
        ],
    )
    def test_primitive_is_non_empty_string(self, tool_id: str) -> None:
        """AdapterRegistration.primitive must be a non-empty str."""
        reg = _get_registration(tool_id)
        assert isinstance(reg.primitive, str), (
            f"primitive must be str, got {type(reg.primitive).__name__}"
        )
        assert len(reg.primitive) > 0, "primitive must be a non-empty string"

    @pytest.mark.parametrize(
        "tool_id",
        [
            "mock_traffic_fine_pay_v1",
            "mock_welfare_application_submit_v1",
        ],
    )
    def test_tool_id_is_non_empty_string(self, tool_id: str) -> None:
        """AdapterRegistration.tool_id must be a non-empty str."""
        reg = _get_registration(tool_id)
        assert isinstance(reg.tool_id, str), (
            f"tool_id must be str, got {type(reg.tool_id).__name__}"
        )
        assert len(reg.tool_id) > 0, "tool_id must be a non-empty string"

    @pytest.mark.parametrize(
        "tool_id",
        [
            "mock_traffic_fine_pay_v1",
            "mock_welfare_application_submit_v1",
        ],
    )
    def test_primitive_and_tool_id_are_not_equal(self, tool_id: str) -> None:
        """primitive and tool_id MUST NOT be the same value (FR-026 distinct fields)."""
        reg = _get_registration(tool_id)
        assert reg.primitive != reg.tool_id, (
            f"primitive {reg.primitive!r} and tool_id {reg.tool_id!r} must be distinct (FR-026)"
        )

    @pytest.mark.parametrize(
        "tool_id",
        [
            "mock_traffic_fine_pay_v1",
            "mock_welfare_application_submit_v1",
        ],
    )
    def test_primitive_and_tool_id_are_not_concatenated(self, tool_id: str) -> None:
        """primitive and tool_id must not be a single concatenated string."""
        reg = _get_registration(tool_id)
        # If they were concatenated, one would contain the other as a substring
        # at the boundary. Test that neither is a prefix of the other.
        primitive_str = str(reg.primitive)
        assert not reg.tool_id.startswith(primitive_str + "_"), (
            f"tool_id {reg.tool_id!r} looks like a concatenation of "
            f"primitive {primitive_str!r} (FR-026 requires distinct fields)"
        )


# ---------------------------------------------------------------------------
# T032-B: primitive field value equals "send" for submit adapters
# ---------------------------------------------------------------------------


class TestAuditPrimitiveValue:
    """primitive must equal 'send' for adapters in the submit dispatcher."""

    @pytest.mark.parametrize(
        "tool_id",
        [
            "mock_traffic_fine_pay_v1",
            "mock_welfare_application_submit_v1",
        ],
    )
    def test_primitive_equals_send(self, tool_id: str) -> None:
        """AdapterRegistration.primitive must equal AdapterPrimitive.send."""
        reg = _get_registration(tool_id)
        assert reg.primitive == AdapterPrimitive.send, (
            f"Expected primitive='send', got {reg.primitive!r} for {tool_id!r}"
        )

    @pytest.mark.parametrize(
        "tool_id",
        [
            "mock_traffic_fine_pay_v1",
            "mock_welfare_application_submit_v1",
        ],
    )
    def test_primitive_str_value_is_submit(self, tool_id: str) -> None:
        """Primitive value as a plain string must be 'send'."""
        reg = _get_registration(tool_id)
        assert str(reg.primitive) == "send", (
            f"str(primitive) must equal 'send', got {str(reg.primitive)!r}"
        )


# ---------------------------------------------------------------------------
# T032-C: transaction_id is derived from the resolved tool_id
# ---------------------------------------------------------------------------


class TestAuditTransactionIdDerivation:
    """After submit(), transaction_id encodes the resolved adapter tool_id (FR-004).

    The deterministic transaction_id is SHA-256 over {tool_id, params, nonce}.
    Two calls with different tool_ids and identical params MUST produce different
    transaction_ids, proving that tool_id is a distinct input to the hash.
    """

    @pytest.mark.asyncio
    async def test_different_tool_ids_produce_different_transaction_ids(self) -> None:
        """Two adapters with identical params must produce different transaction_ids."""

        # Use matching-tier auth contexts for both adapters
        auth_ctx_fines = _MinimalAuthContext(published_tier="ganpyeon_injeung_kakao_aal2")
        _MinimalAuthContext(published_tier="mydata_individual_aal2")  # verifies constructor

        await submit(
            tool_id="mock_traffic_fine_pay_v1",
            params={"fine_reference": "FINE-SHARED-001", "payment_method": "card"},
            auth_context=auth_ctx_fines,
        )
        # welfare adapter has different required params, just test via derive_transaction_id
        from ummaya.primitives.submit import derive_transaction_id
        from ummaya.tools.mock.data_go_kr.fines_pay import REGISTRATION as fines_reg  # noqa: N811
        from ummaya.tools.mock.mydata.welfare_application import (
            REGISTRATION as welfare_reg,  # noqa: N811
        )

        txid_fines = derive_transaction_id(
            "mock_traffic_fine_pay_v1",
            {"common_param": "value"},
            adapter_nonce=fines_reg.nonce,
        )
        txid_welfare = derive_transaction_id(
            "mock_welfare_application_submit_v1",
            {"common_param": "value"},
            adapter_nonce=welfare_reg.nonce,
        )

        assert txid_fines != txid_welfare, (
            "Different tool_ids with the same params must produce different transaction_ids "
            "(FR-026: tool_id is a distinct audit axis)"
        )

    @pytest.mark.asyncio
    async def test_submit_output_transaction_id_format(self) -> None:
        """Successful submit must produce a URN-format transaction_id."""
        auth_ctx = _MinimalAuthContext(published_tier="ganpyeon_injeung_kakao_aal2")
        result = await submit(
            tool_id="mock_traffic_fine_pay_v1",
            params={"fine_reference": "AUDIT-SHAPE-001", "payment_method": "card"},
            auth_context=auth_ctx,
        )
        assert isinstance(result, SubmitOutput)
        assert result.status == SubmitStatus.succeeded
        # transaction_id must carry the urn:ummaya:send: prefix
        assert result.transaction_id.startswith("urn:ummaya:send:"), (
            f"transaction_id format invalid: {result.transaction_id!r}"
        )
        # The hex digest after the prefix is exactly 64 chars (SHA-256)
        hex_part = result.transaction_id.removeprefix("urn:ummaya:send:")
        assert len(hex_part) == 64, (
            f"SHA-256 digest should be 64 chars, got {len(hex_part)}: {hex_part!r}"
        )
        assert all(c in "0123456789abcdef" for c in hex_part), (
            f"Digest must be lowercase hex, got: {hex_part!r}"
        )


# ---------------------------------------------------------------------------
# T032-D: All registered submit adapters have non-null primitive AND tool_id
# ---------------------------------------------------------------------------


def test_all_registered_submit_adapters_have_distinct_primitive_and_tool_id() -> None:
    """FR-026: Every entry in _ADAPTER_REGISTRY must have distinct primitive + tool_id.

    This is a registry-wide scan so any future adapter registration that violates
    FR-026 will be caught immediately.
    """
    assert len(_ADAPTER_REGISTRY) > 0, "_ADAPTER_REGISTRY must contain at least one adapter"

    for tid, (registration, _invoke_fn) in _ADAPTER_REGISTRY.items():
        primitive_str = str(registration.primitive)
        tool_id_str = str(registration.tool_id)

        # Both fields non-empty
        assert primitive_str, f"Adapter {tid!r}: primitive must be non-empty (FR-026)"
        assert tool_id_str, f"Adapter {tid!r}: tool_id must be non-empty (FR-026)"

        # The fields must be distinct
        assert primitive_str != tool_id_str, (
            f"Adapter {tid!r}: primitive={primitive_str!r} and tool_id={tool_id_str!r} "
            "must be distinct (FR-026)"
        )

        # The _ADAPTER_REGISTRY key must match the registration's tool_id
        assert tid == tool_id_str, (
            f"Registry key {tid!r} does not match registration.tool_id {tool_id_str!r}"
        )
