# SPDX-License-Identifier: Apache-2.0
"""T018 — verify_module_kec unit tests.

Covers:
- Happy path: invoke returns dict with six transparency fields + DelegationContext shape.
- Singapore APEX international reference.
- OAuth2.1 + mTLS security wrapping.
- Ledger append.
- Registration: 'kec' is registered in _VERIFY_ADAPTERS.

Contract: specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 1
"""

from __future__ import annotations

import json
from pathlib import Path


def test_kec_invoke_returns_transparency_fields(tmp_path: Path) -> None:
    """invoke() returns a dict with all six transparency fields non-empty."""
    from ummaya.tools.mock.verify_module_kec import invoke

    result = invoke(
        {
            "scope_list": ["send:hometax.tax-return"],
            "session_id": "sess-kec-001",
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
            f"transparency field {field!r} missing or empty in kec response"
        )


def test_kec_international_reference(tmp_path: Path) -> None:
    """_international_reference must be 'Singapore APEX'."""
    from ummaya.tools.mock.verify_module_kec import invoke

    result = invoke(
        {
            "scope_list": ["check:kec.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert result.transparency_international_reference == "Singapore APEX"


def test_kec_security_wrapping_pattern(tmp_path: Path) -> None:
    """_security_wrapping_pattern must contain OAuth2.1 and mTLS."""
    from ummaya.tools.mock.verify_module_kec import invoke

    result = invoke(
        {
            "scope_list": ["check:kec.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert "OAuth2.1" in result.transparency_security_wrapping_pattern
    assert "mTLS" in result.transparency_security_wrapping_pattern


def test_kec_issuer_did_in_vp_jwt(tmp_path: Path) -> None:
    """The token's vp_jwt contains the issuer DID 'did:web:kec.go.kr'."""
    import base64
    import json as json_module

    from ummaya.tools.mock.verify_module_kec import invoke

    result = invoke(
        {
            "scope_list": ["check:kec.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    vp_jwt = result.delegation_context.token.vp_jwt
    _header, payload_b64, _sig = vp_jwt.split(".")
    # Pad base64
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload = json_module.loads(base64.urlsafe_b64decode(padded))
    assert payload["iss"] == "did:web:kec.go.kr"


def test_kec_ledger_append(tmp_path: Path) -> None:
    """delegation_issued event written after invoke."""
    from ummaya.tools.mock.verify_module_kec import invoke

    ledger_dir = tmp_path / "ledger"
    invoke(
        {
            "scope_list": ["check:kec.identity"],
            "session_id": "sess-ledger-kec",
            "ledger_root": ledger_dir,
        }
    )
    jsonl_files = list(ledger_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    lines = [json.loads(line) for line in jsonl_files[0].read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    event = lines[0]
    assert event["kind"] == "delegation_issued"
    assert event["verify_tool_id"] == "mock_verify_module_kec"


def test_kec_is_registered() -> None:
    """Importing the module registers 'kec' in _VERIFY_ADAPTERS."""
    import ummaya.tools.mock.verify_module_kec  # noqa: F401
    from ummaya.primitives.verify import _VERIFY_ADAPTERS

    assert "kec" in _VERIFY_ADAPTERS
