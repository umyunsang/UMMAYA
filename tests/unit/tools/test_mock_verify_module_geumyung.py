# SPDX-License-Identifier: Apache-2.0
"""T019 — verify_module_geumyung unit tests.

Covers:
- Happy path: invoke returns dict with six transparency fields + DelegationContext shape.
- Singapore Myinfo international reference.
- public-mydata-read-v240930 reference implementation.
- Ledger append.
- Registration: 'geumyung_module' is registered in _VERIFY_ADAPTERS.

Contract: specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 1
"""

from __future__ import annotations

import json
from pathlib import Path


def test_geumyung_invoke_returns_transparency_fields(tmp_path: Path) -> None:
    """invoke() returns a dict with all six transparency fields non-empty."""
    from ummaya.tools.mock.verify_module_geumyung import invoke

    result = invoke(
        {
            "scope_list": ["send:hometax.tax-return"],
            "session_id": "sess-geumyung-001",
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
            f"transparency field {field!r} missing or empty in geumyung response"
        )


def test_geumyung_international_reference(tmp_path: Path) -> None:
    """_international_reference must be 'Singapore Myinfo'."""
    from ummaya.tools.mock.verify_module_geumyung import invoke

    result = invoke(
        {
            "scope_list": ["check:geumyung.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert result.transparency_international_reference == "Singapore Myinfo"


def test_geumyung_reference_impl(tmp_path: Path) -> None:
    """_reference_implementation must be 'public-mydata-read-v240930'."""
    from ummaya.tools.mock.verify_module_geumyung import invoke

    result = invoke(
        {
            "scope_list": ["check:geumyung.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert result.transparency_reference_implementation == "public-mydata-read-v240930"


def test_geumyung_delegation_token_format(tmp_path: Path) -> None:
    """The delegation token starts with 'del_' and scope is embedded correctly."""
    from ummaya.tools.mock.verify_module_geumyung import invoke

    result = invoke(
        {
            "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert result.delegation_context.token.delegation_token.startswith("del_")
    scope = result.delegation_context.token.scope
    assert "find:hometax.simplified" in scope
    assert "send:hometax.tax-return" in scope


def test_geumyung_ledger_append(tmp_path: Path) -> None:
    """delegation_issued event written to ledger after invoke."""
    from ummaya.tools.mock.verify_module_geumyung import invoke

    ledger_dir = tmp_path / "ledger"
    invoke(
        {
            "scope_list": ["check:geumyung.identity"],
            "session_id": "sess-ledger-geumyung",
            "ledger_root": ledger_dir,
        }
    )
    jsonl_files = list(ledger_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    lines = [json.loads(line) for line in jsonl_files[0].read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    event = lines[0]
    assert event["kind"] == "delegation_issued"
    assert event["verify_tool_id"] == "mock_verify_module_geumyung"


def test_geumyung_is_registered() -> None:
    """Importing the module registers 'geumyung_module' in _VERIFY_ADAPTERS."""
    import ummaya.tools.mock.verify_module_geumyung  # noqa: F401
    from ummaya.primitives.verify import _VERIFY_ADAPTERS

    assert "geumyung_module" in _VERIFY_ADAPTERS
