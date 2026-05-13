# SPDX-License-Identifier: Apache-2.0
"""T019 — FR-004 deterministic transaction_id tests.

The transaction_id produced by the submit dispatcher must be:
1. Deterministic: same (tool_id, params, adapter_nonce) → same transaction_id.
2. Prefixed with 'urn:ummaya:send:'.
3. Based on SHA-256 over canonical_json(tool_id, params, adapter_nonce).

Reference: specs/031-five-primitive-harness/data-model.md § 1 + T023.
"""

from __future__ import annotations

import hashlib
import json

from ummaya.primitives.submit import derive_transaction_id

# ---------------------------------------------------------------------------
# T019-A: URN prefix
# ---------------------------------------------------------------------------


def test_transaction_id_has_urn_prefix() -> None:
    """transaction_id MUST start with 'urn:ummaya:send:'."""
    txid = derive_transaction_id("mock_tool_v1", {"x": 1}, adapter_nonce=None)
    assert txid.startswith("urn:ummaya:send:"), (
        f"transaction_id {txid!r} must start with 'urn:ummaya:send:'"
    )


# ---------------------------------------------------------------------------
# T019-B: Determinism
# ---------------------------------------------------------------------------


def test_same_inputs_produce_same_transaction_id() -> None:
    """FR-004: identical (tool_id, params, nonce) → identical transaction_id."""
    params = {"fine_reference": "2026-04-19-0001", "payment_method": "virtual_account"}
    txid1 = derive_transaction_id("mock_traffic_fine_pay_v1", params, adapter_nonce=None)
    txid2 = derive_transaction_id("mock_traffic_fine_pay_v1", params, adapter_nonce=None)
    assert txid1 == txid2, "transaction_id must be deterministic for same inputs"


def test_different_tool_id_produces_different_transaction_id() -> None:
    """Different tool_id with same params → different transaction_id."""
    params = {"x": 1}
    txid_a = derive_transaction_id("tool_a_v1", params, adapter_nonce=None)
    txid_b = derive_transaction_id("tool_b_v1", params, adapter_nonce=None)
    assert txid_a != txid_b


def test_different_params_produce_different_transaction_id() -> None:
    """Different params with same tool_id → different transaction_id."""
    txid_a = derive_transaction_id("mock_tool_v1", {"x": 1}, adapter_nonce=None)
    txid_b = derive_transaction_id("mock_tool_v1", {"x": 2}, adapter_nonce=None)
    assert txid_a != txid_b


def test_adapter_nonce_affects_transaction_id() -> None:
    """A non-None adapter_nonce changes the transaction_id."""
    params = {"x": 1}
    txid_no_nonce = derive_transaction_id("mock_tool_v1", params, adapter_nonce=None)
    txid_with_nonce = derive_transaction_id("mock_tool_v1", params, adapter_nonce="abc123")
    assert txid_no_nonce != txid_with_nonce


# ---------------------------------------------------------------------------
# T019-C: SHA-256 content hash verification
# ---------------------------------------------------------------------------


def test_transaction_id_is_sha256_based() -> None:
    """transaction_id suffix must be the SHA-256 of the canonical JSON payload."""
    tool_id = "mock_traffic_fine_pay_v1"
    params: dict[str, object] = {"payment_method": "card", "fine_reference": "123"}
    adapter_nonce = None

    txid = derive_transaction_id(tool_id, params, adapter_nonce=adapter_nonce)

    # Reconstruct the expected canonical JSON + SHA-256
    canonical_payload = {
        "tool_id": tool_id,
        "params": dict(sorted(params.items())),  # canonical: keys sorted
        "adapter_nonce": adapter_nonce,
    }
    canonical = json.dumps(
        canonical_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    expected_txid = f"urn:ummaya:send:{expected_hash}"

    assert txid == expected_txid, (
        f"transaction_id {txid!r} does not match expected SHA-256 derivation {expected_txid!r}"
    )


def test_transaction_id_with_nonce_is_sha256_based() -> None:
    """transaction_id with adapter_nonce must be the SHA-256 of nonce-augmented canonical JSON."""
    tool_id = "mock_welfare_application_submit_v1"
    params: dict[str, object] = {"applicant_id": "user42"}
    adapter_nonce = "welfare-nonce-v1"

    txid = derive_transaction_id(tool_id, params, adapter_nonce=adapter_nonce)

    canonical_payload = {
        "tool_id": tool_id,
        "params": dict(sorted(params.items())),
        "adapter_nonce": adapter_nonce,
    }
    canonical = json.dumps(
        canonical_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    expected_txid = f"urn:ummaya:send:{expected_hash}"

    assert txid == expected_txid


# ---------------------------------------------------------------------------
# T019-D: Param key ordering does not affect output (canonical form)
# ---------------------------------------------------------------------------


def test_param_key_order_invariance() -> None:
    """transaction_id must be the same regardless of dict iteration order."""
    params_ordered = {"a": 1, "b": 2, "c": 3}
    params_reversed = {"c": 3, "b": 2, "a": 1}
    txid_ordered = derive_transaction_id("mock_tool_v1", params_ordered, adapter_nonce=None)
    txid_reversed = derive_transaction_id("mock_tool_v1", params_reversed, adapter_nonce=None)
    assert txid_ordered == txid_reversed, (
        "transaction_id must be invariant to dict key insertion order (canonical JSON)"
    )
