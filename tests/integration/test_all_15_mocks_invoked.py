# SPDX-License-Identifier: Apache-2.0
"""T034 — US2: all 15 mock adapters invoked at least once (FR-020 / SC-004).

Drives each of the 10 verify families directly through the backend dispatcher
(no subprocess), then exercises the 2 lookup, 2 submit, and 1 subscribe
adapters via their respective primitive invocation paths.

Mock surface (15 adapters):
  Verify (10):
    modid, kec, geumyung_module, simple_auth_module, any_id_sso,
    gongdong_injeungseo, geumyung_injeungseo, ganpyeon_injeung,
    mobile_id, mydata
  Lookup (2):
    mock_lookup_module_hometax_simplified, mock_lookup_module_gov24_certificate
  Submit (2):
    mock_submit_module_hometax_taxreturn, mock_submit_module_gov24_minwon
  Subscribe (1):
    mock_cbs_disaster_v1

SC-004 acceptance criterion: each of the 15 adapters logs ≥1 invocation in
the aggregate across this test module.

Strategy: backend-direct (in-process) for speed; no TUI subprocess required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Ensure all mock adapters are registered at import time.
import kosmos.tools.mock  # noqa: F401

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "citizen_chains"

_ALL_FIXTURE_NAMES = [
    "modid",
    "kec",
    "geumyung_module",
    "simple_auth_module",
    "any_id_sso",
    "gongdong_injeungseo",
    "geumyung_injeungseo",
    "ganpyeon_injeung",
    "mobile_id",
    "mydata",
]


def _load_fixture(name: str) -> dict[str, object]:
    path = _FIXTURES_DIR / f"{name}.json"
    assert path.exists(), f"Fixture missing: {path}"
    result: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return result


_EXPECTED_VERIFY = {
    "modid",
    "kec",
    "geumyung_module",
    "simple_auth_module",
    "any_id_sso",
    "gongdong_injeungseo",
    "geumyung_injeungseo",
    "ganpyeon_injeung",
    "mobile_id",
    "mydata",
}

_EXPECTED_LOOKUP = {
    "mock_lookup_module_hometax_simplified",
    "mock_lookup_module_gov24_certificate",
}

_EXPECTED_SUBMIT = {
    "mock_submit_module_hometax_taxreturn",
    "mock_submit_module_gov24_minwon",
}

_EXPECTED_SUBSCRIBE = {"mock_cbs_disaster_v1"}


# ---------------------------------------------------------------------------
# T034a — all 10 verify families invoked
# ---------------------------------------------------------------------------


async def _invoke_verify_family(fixture_name: str) -> str:
    """Each verify family mock must return a non-error AuthContext variant.

    Confirms SC-004 (10 verify adapters) and that fixture schema is consistent
    with the canonical map (family_hint matches the loaded mapping).
    """
    from kosmos.primitives.verify import VerifyMismatchError, verify
    from kosmos.tools.verify_canonical_map import get_canonical_map

    fixture = _load_fixture(fixture_name)
    tool_id = fixture["tool_id"]
    expected_family = fixture["family_hint"]

    # Confirm fixture tool_id maps to expected family via canonical map.
    canonical_map = get_canonical_map()
    assert tool_id in canonical_map, (
        f"Fixture tool_id {tool_id!r} not in canonical map. "
        f"Map keys: {sorted(canonical_map.keys())}"
    )
    assert canonical_map[tool_id] == expected_family, (
        f"Canonical map maps {tool_id!r} to {canonical_map[tool_id]!r}, "
        f"fixture expects {expected_family!r}"
    )

    # Extract scope_list from fixture (type-safe via cast).
    first_call = fixture.get("expected_first_tool_call", {})
    first_call_dict: dict[str, object] = first_call if isinstance(first_call, dict) else {}
    args_obj = first_call_dict.get("arguments", {})
    args_dict: dict[str, object] = args_obj if isinstance(args_obj, dict) else {}
    params_obj = args_dict.get("params", {})
    params_dict: dict[str, object] = params_obj if isinstance(params_obj, dict) else {}
    scope_list_raw = params_dict.get("scope_list", [])
    scope_list: list[str] = list(scope_list_raw) if isinstance(scope_list_raw, list) else []

    # Invoke via backend verify() dispatcher using family_hint directly.
    result = await verify(
        family_hint=str(expected_family),
        session_context={
            "scope_list": scope_list,
            "session_id": f"test-{fixture_name}",
        },
    )

    assert not isinstance(result, VerifyMismatchError), (
        f"verify({expected_family!r}) returned VerifyMismatchError: {result!r}. "
        "Check that the mock adapter is registered."
    )

    return str(expected_family)


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", _ALL_FIXTURE_NAMES)
async def test_verify_family_invoked(fixture_name: str) -> None:
    invoked_family = await _invoke_verify_family(fixture_name)
    assert invoked_family in _EXPECTED_VERIFY


# ---------------------------------------------------------------------------
# T034b — 2 lookup mocks invoked
# ---------------------------------------------------------------------------


async def _invoke_lookup_hometax_simplified() -> str:
    """mock_lookup_module_hometax_simplified invoked ≥1 time."""
    from kosmos.tools.mock.lookup_module_hometax_simplified import (
        HometaxSimplifiedInput,
        handle,
    )

    inp = HometaxSimplifiedInput(year=2024, resident_id_prefix="900101")
    result = await handle(inp, delegation_context=None)

    assert isinstance(result, dict), (
        f"Expected dict from hometax lookup, got {type(result).__name__}"
    )
    return "mock_lookup_module_hometax_simplified"


@pytest.mark.asyncio
async def test_lookup_hometax_simplified_invoked() -> None:
    invoked_adapter = await _invoke_lookup_hometax_simplified()
    assert invoked_adapter in _EXPECTED_LOOKUP


async def _invoke_lookup_gov24_certificate() -> str:
    """mock_lookup_module_gov24_certificate invoked ≥1 time."""
    from kosmos.tools.mock.lookup_module_gov24_certificate import (
        Gov24CertificateInput,
        handle,
    )

    inp = Gov24CertificateInput(
        certificate_type="family_relations",
        purpose="테스트 조회",
    )
    result = await handle(inp, delegation_context=None)
    assert result is not None, "gov24_certificate lookup returned None"
    return "mock_lookup_module_gov24_certificate"


@pytest.mark.asyncio
async def test_lookup_gov24_certificate_invoked() -> None:
    invoked_adapter = await _invoke_lookup_gov24_certificate()
    assert invoked_adapter in _EXPECTED_LOOKUP


# ---------------------------------------------------------------------------
# T034c — 2 submit mocks invoked (with valid delegation context)
# ---------------------------------------------------------------------------


async def _invoke_submit_hometax_taxreturn(tmp_path: Path) -> str:
    """mock_submit_module_hometax_taxreturn invoked ≥1 time; receipt present."""
    import uuid
    from unittest.mock import patch

    import kosmos.tools.mock.submit_module_hometax_taxreturn as _smod
    from kosmos.memdir.consent_ledger import DelegationUsedEvent, append_delegation_used
    from kosmos.primitives.verify import ModidContext
    from kosmos.tools.mock.submit_module_hometax_taxreturn import invoke
    from kosmos.tools.mock.verify_module_modid import invoke as verify_invoke

    ledger_root = tmp_path / "consent"
    session_id = str(uuid.uuid4())

    # Issue delegation via modid verify.
    verify_result = verify_invoke(
        {
            "scope_list": ["submit:hometax.tax-return"],
            "session_id": session_id,
            "purpose_ko": "종합소득세 신고",
            "purpose_en": "Filing comprehensive income tax",
            "ledger_root": ledger_root,
        }
    )
    assert isinstance(verify_result, ModidContext)
    delegation_ctx = verify_result.delegation_context

    original_append = append_delegation_used

    def _patched_append(event: DelegationUsedEvent, **kwargs: object) -> Path:
        result_path: Path = original_append(event, ledger_root=ledger_root)
        return result_path

    from kosmos.memdir.consent_ledger import FileLedgerReader

    patched_reader = FileLedgerReader(ledger_root=ledger_root)
    with (
        patch.object(_smod, "append_delegation_used", side_effect=_patched_append),
        patch("kosmos.memdir.consent_ledger.FileLedgerReader", return_value=patched_reader),
    ):
        result = await invoke(
            {
                "tax_year": 2024,
                "income_type": "종합소득",
                "total_income_krw": 35_000_000,
                "session_id": session_id,
                "delegation_context": delegation_ctx,
            }
        )

    from kosmos.primitives.submit import SubmitOutput, SubmitStatus

    assert isinstance(result, SubmitOutput)
    assert result.status == SubmitStatus.succeeded
    receipt_id = result.adapter_receipt.get("receipt_id", "")
    assert isinstance(receipt_id, str) and receipt_id.startswith("hometax-"), (
        f"Expected hometax- receipt, got {receipt_id!r}"
    )
    return "mock_submit_module_hometax_taxreturn"


@pytest.mark.asyncio
async def test_submit_hometax_taxreturn_invoked(tmp_path: Path) -> None:
    invoked_adapter = await _invoke_submit_hometax_taxreturn(tmp_path)
    assert invoked_adapter in _EXPECTED_SUBMIT


async def _invoke_submit_gov24_minwon(tmp_path: Path) -> str:
    """mock_submit_module_gov24_minwon invoked ≥1 time."""
    import uuid
    from unittest.mock import patch

    import kosmos.tools.mock.submit_module_gov24_minwon as _smod
    from kosmos.memdir.consent_ledger import DelegationUsedEvent, append_delegation_used
    from kosmos.primitives.verify import ModidContext
    from kosmos.tools.mock.submit_module_gov24_minwon import invoke
    from kosmos.tools.mock.verify_module_modid import invoke as verify_invoke

    ledger_root = tmp_path / "consent"
    session_id = str(uuid.uuid4())

    verify_result = verify_invoke(
        {
            "scope_list": ["submit:gov24.minwon"],
            "session_id": session_id,
            "purpose_ko": "정부24 민원 신청",
            "purpose_en": "Gov24 civil petition submission",
            "ledger_root": ledger_root,
        }
    )
    assert isinstance(verify_result, ModidContext)
    delegation_ctx = verify_result.delegation_context

    original_append = append_delegation_used

    def _patched_append(event: DelegationUsedEvent, **kwargs: object) -> Path:
        result_path: Path = original_append(event, ledger_root=ledger_root)
        return result_path

    from kosmos.memdir.consent_ledger import FileLedgerReader

    patched_reader = FileLedgerReader(ledger_root=ledger_root)
    with (
        patch.object(_smod, "append_delegation_used", side_effect=_patched_append),
        patch("kosmos.memdir.consent_ledger.FileLedgerReader", return_value=patched_reader),
    ):
        result = await invoke(
            {
                "minwon_type": "주민등록등본",
                "applicant_name": "홍길동",
                "delivery_method": "online",
                "session_id": session_id,
                "delegation_context": delegation_ctx,
            }
        )

    from kosmos.primitives.submit import SubmitOutput

    assert isinstance(result, SubmitOutput), (
        f"Expected SubmitOutput from gov24 minwon, got {type(result).__name__}"
    )
    return "mock_submit_module_gov24_minwon"


@pytest.mark.asyncio
async def test_submit_gov24_minwon_invoked(tmp_path: Path) -> None:
    invoked_adapter = await _invoke_submit_gov24_minwon(tmp_path)
    assert invoked_adapter in _EXPECTED_SUBMIT


# ---------------------------------------------------------------------------
# T034d — 1 subscribe mock invoked (CBS disaster)
# ---------------------------------------------------------------------------


async def _invoke_subscribe_cbs_disaster() -> str:
    """mock_cbs_disaster_v1 invoked ≥1 time via subscribe() primitive."""
    from kosmos.primitives.subscribe import AdapterNotFoundError, SubscribeInput, subscribe

    inp = SubscribeInput(
        tool_id="mock_cbs_disaster_v1",
        params={"area_code": "11"},
        lifetime_seconds=10,
    )
    result = subscribe(inp)

    assert not isinstance(result, AdapterNotFoundError), (
        f"subscribe(mock_cbs_disaster_v1) returned AdapterNotFoundError: {result!r}"
    )
    # Consume one event to confirm the iterator is live.
    event_received = False
    async for _ in result:
        event_received = True
        break

    assert event_received, "CBS disaster subscribe iterator produced no events"
    return "mock_cbs_disaster_v1"


@pytest.mark.asyncio
async def test_subscribe_cbs_disaster_invoked() -> None:
    invoked_adapter = await _invoke_subscribe_cbs_disaster()
    assert invoked_adapter in _EXPECTED_SUBSCRIBE


# ---------------------------------------------------------------------------
# T034e — Aggregate SC-004 assertion (all 15 mocks present)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sc004_all_15_mocks_invoked(tmp_path: Path) -> None:
    """SC-004: assert all 15 mock adapters can be invoked in one battery.

    The aggregate check cannot depend on module globals populated by sibling
    tests because CI runs this file under pytest-xdist (`pytest -n auto`), where
    each worker has a separate Python process.
    """
    invoked_verify: set[str] = set()
    for fixture_name in _ALL_FIXTURE_NAMES:
        invoked_verify.add(await _invoke_verify_family(fixture_name))

    invoked_lookup = {
        await _invoke_lookup_hometax_simplified(),
        await _invoke_lookup_gov24_certificate(),
    }
    invoked_submit = {
        await _invoke_submit_hometax_taxreturn(tmp_path / "hometax"),
        await _invoke_submit_gov24_minwon(tmp_path / "gov24"),
    }
    invoked_subscribe = {await _invoke_subscribe_cbs_disaster()}

    missing_verify = _EXPECTED_VERIFY - invoked_verify
    missing_lookup = _EXPECTED_LOOKUP - invoked_lookup
    missing_submit = _EXPECTED_SUBMIT - invoked_submit
    missing_subscribe = _EXPECTED_SUBSCRIBE - invoked_subscribe

    assert not missing_verify, f"SC-004: verify families not invoked: {missing_verify}"
    assert not missing_lookup, f"SC-004: lookup adapters not invoked: {missing_lookup}"
    assert not missing_submit, f"SC-004: submit adapters not invoked: {missing_submit}"
    assert not missing_subscribe, f"SC-004: subscribe adapters not invoked: {missing_subscribe}"
