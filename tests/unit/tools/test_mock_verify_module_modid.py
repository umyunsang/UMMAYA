# SPDX-License-Identifier: Apache-2.0
"""T017 — verify_module_modid unit tests.

Covers:
- Happy path: invoke returns dict with six transparency fields + DelegationContext shape.
- EU EUDI Wallet international reference.
- citizen_did is populated (modid DID issued during ceremony).
- Ledger append: delegation_issued event written.
- Registration: 'modid' is registered in _VERIFY_ADAPTERS.

Contract: specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 1
"""

from __future__ import annotations

import json
from pathlib import Path


def test_modid_invoke_returns_transparency_fields(tmp_path: Path) -> None:
    """invoke() returns a dict with all six transparency fields non-empty."""
    from kosmos.tools.mock.verify_module_modid import invoke

    result = invoke(
        {
            "scope_list": ["submit:hometax.tax-return"],
            "session_id": "sess-modid-001",
            "ledger_root": tmp_path / "ledger",
        }
    )

    assert hasattr(result, "transparency_mode")
    assert result.transparency_mode == "mock"
    for field in (
        "transparency_reference_implementation",
        "transparency_actual_endpoint_when_live",
        "transparency_security_wrapping_pattern",
        "transparency_policy_authority",
        "transparency_international_reference",
    ):
        value = getattr(result, field)
        assert value is not None and isinstance(value, str) and value.strip(), (
            f"transparency field {field!r} missing or empty in modid response"
        )


def test_modid_international_reference(tmp_path: Path) -> None:
    """_international_reference must be 'EU EUDI Wallet'."""
    from kosmos.tools.mock.verify_module_modid import invoke

    result = invoke(
        {
            "scope_list": ["verify:modid.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert result.transparency_international_reference == "EU EUDI Wallet"


def test_modid_security_wrapping(tmp_path: Path) -> None:
    """_security_wrapping_pattern must contain OID4VP."""
    from kosmos.tools.mock.verify_module_modid import invoke

    result = invoke(
        {
            "scope_list": ["verify:modid.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert "OID4VP" in result.transparency_security_wrapping_pattern


def test_modid_evidence_grade(tmp_path: Path) -> None:
    """Mobile ID module mock exposes official API evidence metadata."""
    from kosmos.tools.mock.verify_module_modid import invoke

    result = invoke(
        {
            "scope_list": ["verify:modid.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    dumped = result.model_dump(by_alias=True)
    assert dumped["_mock_fidelity_grade"] == "A-official-mobile-id-verifier-api-published"
    assert dumped["_mock_evidence"]["credential_status"] == "student_no_live_authority"
    assert "basis_urls" in dumped["_mock_evidence"]


def test_modid_citizen_did_is_set(tmp_path: Path) -> None:
    """citizen_did is populated (DID issued during Mobile-ID ceremony)."""
    from kosmos.tools.mock.verify_module_modid import invoke

    result = invoke(
        {
            "scope_list": ["verify:modid.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    citizen_did = result.delegation_context.citizen_did
    assert citizen_did is not None, "citizen_did should be set for Mobile-ID"
    assert citizen_did.startswith("did:web:mobileid.go.kr")


def test_modid_delegation_token_prefix(tmp_path: Path) -> None:
    """The delegation_token inside the returned DelegationContext starts with 'del_'."""
    from kosmos.tools.mock.verify_module_modid import invoke

    result = invoke(
        {
            "scope_list": ["submit:hometax.tax-return"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert result.delegation_context.token.delegation_token.startswith("del_")


def test_modid_ledger_append(tmp_path: Path) -> None:
    """After invoke, delegation_issued event is written to the ledger."""
    from kosmos.tools.mock.verify_module_modid import invoke

    ledger_dir = tmp_path / "ledger"
    invoke(
        {
            "scope_list": ["lookup:hometax.simplified,submit:hometax.tax-return"],
            "session_id": "sess-ledger-modid",
            "ledger_root": ledger_dir,
        }
    )

    jsonl_files = list(ledger_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    lines = [json.loads(line) for line in jsonl_files[0].read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    event = lines[0]
    assert event["kind"] == "delegation_issued"
    assert event["verify_tool_id"] == "mock_verify_module_modid"


def test_modid_is_registered() -> None:
    """Importing the module registers 'modid' in _VERIFY_ADAPTERS."""
    import kosmos.tools.mock.verify_module_modid  # noqa: F401
    from kosmos.primitives.verify import _VERIFY_ADAPTERS

    assert "modid" in _VERIFY_ADAPTERS
