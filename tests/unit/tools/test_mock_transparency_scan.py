# SPDX-License-Identifier: Apache-2.0
"""T034 — Registry-wide transparency scan (FR-006 / SC-005).

Parameterised over active mock adapter IDs:
  - 10 verify families  (kosmos.primitives.verify._VERIFY_ADAPTERS)
  - 5  submit adapters  (kosmos.primitives.submit._ADAPTER_REGISTRY)
  - 2  lookup tools     (main ToolRegistry, adapter_mode='mock')

Each adapter is invoked with minimal synthetic input and the six transparency
fields are asserted present and non-empty.

ONE adapter, ONE omission → CI red.

Contract: specs/2296-ax-mock-adapters/contracts/mock-adapter-response-shape.md § 5
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Six transparency fields that every Mock adapter response must carry
# ---------------------------------------------------------------------------

_SIX_FIELDS = (
    "_mode",
    "_reference_implementation",
    "_actual_endpoint_when_live",
    "_security_wrapping_pattern",
    "_policy_authority",
    "_international_reference",
)


# ---------------------------------------------------------------------------
# Helpers — synthetic inputs per surface
# ---------------------------------------------------------------------------


def _make_delegation_context(scope: str) -> Any:
    """Build a minimal valid DelegationContext for testing."""
    from kosmos.primitives.delegation import DelegationContext, DelegationToken

    token = DelegationToken(
        vp_jwt=(
            "eyJhbGciOiJub25lIiwidHlwIjoidnArand0In0"
            ".eyJzdWIiOiJtb2NrIn0"
            ".mock-signature-not-cryptographic"
        ),
        delegation_token="del_" + "x" * 24,
        scope=scope,
        issuer_did="did:web:mobileid.go.kr",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        **{"_mode": "mock"},
    )
    return DelegationContext(
        token=token,
        purpose_ko="테스트",
        purpose_en="Test",
    )


# ---------------------------------------------------------------------------
# Verify surface — 10 families
# ---------------------------------------------------------------------------

# Families whose invoke() returns a dict directly (stamped via stamp_mock_response)
_VERIFY_DICT_FAMILIES = [
    "any_id_sso",
    "geumyung_module",
    "kec",
    "modid",
    "simple_auth_module",
]

# Families whose invoke() returns a Pydantic context object (model_dump needed)
_VERIFY_MODEL_FAMILIES = [
    "ganpyeon_injeung",
    "geumyung_injeungseo",
    "gongdong_injeungseo",
    "mobile_id",
    "mydata",
]

_ALL_VERIFY_FAMILIES = _VERIFY_DICT_FAMILIES + _VERIFY_MODEL_FAMILIES

_VERIFY_SYNTHETIC_INPUT: dict[str, Any] = {
    "scope_list": ["verify:simple_auth.identity"],
    "session_id": "transparency-scan-session",
}


def _invoke_verify_adapter(family: str) -> dict[str, Any]:
    """Invoke a verify adapter with synthetic input; normalise result to dict."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.verify import _VERIFY_ADAPTERS

    adapter = _VERIFY_ADAPTERS[family]
    result = adapter(_VERIFY_SYNTHETIC_INPUT)

    if isinstance(result, dict):
        return result
    # Pydantic model — dump to dict with alias so underscore-prefixed fields appear
    return result.model_dump(by_alias=True)


@pytest.mark.parametrize("family", _ALL_VERIFY_FAMILIES)
def test_verify_adapter_carries_six_transparency_fields(family: str) -> None:
    """Each verify adapter response carries all six transparency fields non-empty."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration

    result = _invoke_verify_adapter(family)

    assert result.get("_mode") == "mock", (
        f"verify/{family}: _mode must be 'mock', got {result.get('_mode')!r}"
    )
    for field in _SIX_FIELDS[1:]:  # skip _mode (already asserted above)
        value = result.get(field)
        assert value is not None and isinstance(value, str) and value.strip(), (
            f"verify/{family}: transparency field {field!r} is missing or empty. Got: {value!r}"
        )


# ---------------------------------------------------------------------------
# Submit surface — 5 adapters
# ---------------------------------------------------------------------------

# Adapters that require a DelegationContext in params (new delegation-aware mocks)
_DELEGATION_SUBMIT_CASES: list[tuple[str, str, dict[str, Any]]] = [
    (
        "mock_submit_module_hometax_taxreturn",
        "submit:hometax.tax-return",
        {
            "tax_year": 2024,
            "income_type": "근로소득",
            "total_income_krw": 50_000_000,
            "session_id": "transparency-scan-hometax",
            # delegation_context injected below
        },
    ),
    (
        "mock_submit_module_gov24_minwon",
        "submit:gov24.minwon",
        {
            "minwon_type": "주민등록등본",
            "applicant_name": "김테스트",
            "delivery_method": "online",
            "session_id": "transparency-scan-gov24",
            # delegation_context injected below
        },
    ),
    (
        "mock_submit_module_public_mydata_action",
        "submit:public_mydata.action",
        {
            "action_type": "transfer_consent",
            "target_institution_code": "KSB001",
            "applicant_di": "di-scan-transparency-001",
            "session_id": "transparency-scan-mydata",
            # delegation_context injected below
        },
    ),
]

# Adapters that do NOT require a DelegationContext (existing pre-delegation mocks)
_NODELEGATION_SUBMIT_CASES: list[tuple[str, dict[str, Any]]] = [
    (
        "mock_traffic_fine_pay_v1",
        {"fine_reference": "FINE-SCAN-001", "payment_method": "card"},
    ),
    (
        "mock_welfare_application_submit_v1",
        {
            "applicant_id": "di-scan-001",
            "benefit_code": "기초생활수급",
            "application_type": "new",
            "household_size": 3,
        },
    ),
]

_ALL_SUBMIT_IDS = [case[0] for case in _DELEGATION_SUBMIT_CASES] + [
    case[0] for case in _NODELEGATION_SUBMIT_CASES
]


async def _get_submit_receipt(adapter_id: str) -> dict[str, Any]:
    """Invoke a submit adapter with synthetic input; return adapter_receipt dict."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.submit import _ADAPTER_REGISTRY

    _reg, invoke_fn = _ADAPTER_REGISTRY[adapter_id]

    # Identify which param set to use
    for aid, scope, base_params in _DELEGATION_SUBMIT_CASES:
        if aid == adapter_id:
            params = {**base_params, "delegation_context": _make_delegation_context(scope)}
            result = await invoke_fn(params)
            return result.adapter_receipt

    for aid, params in _NODELEGATION_SUBMIT_CASES:
        if aid == adapter_id:
            result = await invoke_fn(params)
            return result.adapter_receipt

    raise KeyError(f"No synthetic input defined for submit adapter {adapter_id!r}")


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_id", _ALL_SUBMIT_IDS)
async def test_submit_adapter_receipt_carries_six_transparency_fields(adapter_id: str) -> None:
    """Each submit adapter's adapter_receipt carries all six transparency fields."""
    receipt = await _get_submit_receipt(adapter_id)

    assert receipt.get("_mode") == "mock", (
        f"submit/{adapter_id}: _mode must be 'mock', got {receipt.get('_mode')!r}"
    )
    for field in _SIX_FIELDS[1:]:
        value = receipt.get(field)
        assert value is not None and isinstance(value, str) and value.strip(), (
            f"submit/{adapter_id}: transparency field {field!r} is missing or empty. Got: {value!r}"
        )


# ---------------------------------------------------------------------------
# Lookup surface — 2 adapters in main ToolRegistry
# ---------------------------------------------------------------------------

_LOOKUP_ADAPTER_CASES: list[tuple[str, Any, dict[str, Any]]] = []

# Populated lazily in the test body to avoid import-time side effects


@pytest.mark.parametrize(
    "adapter_id,input_obj",
    [
        (
            "mock_lookup_module_hometax_simplified",
            None,  # populated inside test
        ),
        (
            "mock_lookup_module_gov24_certificate",
            None,  # populated inside test
        ),
    ],
    ids=[
        "mock_lookup_module_hometax_simplified",
        "mock_lookup_module_gov24_certificate",
    ],
)
@pytest.mark.asyncio
async def test_lookup_adapter_response_carries_six_transparency_fields(
    adapter_id: str,
    input_obj: object,
) -> None:
    """Each lookup mock's handle() returns a dict with all six transparency fields."""
    if adapter_id == "mock_lookup_module_hometax_simplified":
        from kosmos.tools.mock.lookup_module_hometax_simplified import (
            HometaxSimplifiedInput,
            handle,
        )

        inp = HometaxSimplifiedInput(year=2024, resident_id_prefix="851201")
        result = await handle(inp)

    elif adapter_id == "mock_lookup_module_gov24_certificate":
        from kosmos.tools.mock.lookup_module_gov24_certificate import (
            Gov24CertificateInput,
            handle,
        )

        inp = Gov24CertificateInput(
            certificate_type="resident_registration",
            purpose="transparency-scan-test-purpose",
        )
        result = await handle(inp)

    else:
        raise ValueError(f"Unknown lookup adapter: {adapter_id!r}")

    # B1 envelope-contract fix: lookup mocks now return a LookupOutput
    # ``{"kind": "record", "item": {...}}`` envelope. The six transparency
    # fields are stamped onto ``item`` (LookupRecord.item is dict[str, object]),
    # not the outer envelope (LookupRecord uses extra='forbid').
    assert result.get("kind") == "record", (
        f"lookup/{adapter_id}: handle() must return a LookupRecord envelope "
        f"({{'kind': 'record', 'item': ...}}), got kind={result.get('kind')!r}"
    )
    item = result.get("item")
    assert isinstance(item, dict), (
        f"lookup/{adapter_id}: envelope 'item' must be a dict, got {type(item).__name__}"
    )

    assert item.get("_mode") == "mock", (
        f"lookup/{adapter_id}: _mode must be 'mock' (inside envelope.item), "
        f"got {item.get('_mode')!r}"
    )
    for field in _SIX_FIELDS[1:]:
        value = item.get(field)
        assert value is not None and isinstance(value, str) and value.strip(), (
            f"lookup/{adapter_id}: transparency field {field!r} is missing or empty "
            f"(checked inside envelope.item). Got: {value!r}"
        )


# ---------------------------------------------------------------------------
# Coverage guard — enumerates all active mock IDs explicitly
# ---------------------------------------------------------------------------


def _all_mock_adapter_ids() -> list[str]:
    """Return the canonical list of active Mock adapter IDs."""
    return (
        _ALL_VERIFY_FAMILIES
        + _ALL_SUBMIT_IDS
        + [
            "mock_lookup_module_hometax_simplified",
            "mock_lookup_module_gov24_certificate",
        ]
    )


def test_canonical_mock_adapter_count_is_17() -> None:
    """Guard: canonical active mock adapter list must total exactly 17 entries."""
    ids = _all_mock_adapter_ids()
    assert len(ids) == 17, f"Expected 17 canonical Mock adapter IDs, got {len(ids)}. IDs: {ids}"
    assert len(set(ids)) == len(ids), (
        "Duplicate adapter IDs detected in canonical list — each adapter must "
        f"appear exactly once. Duplicates: "
        f"{[x for x in ids if ids.count(x) > 1]}"
    )
