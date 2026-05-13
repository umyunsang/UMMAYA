# SPDX-License-Identifier: Apache-2.0
"""T016 — verify_module_simple_auth unit tests.

Covers:
- Happy path: invoke returns dict with six transparency fields + DelegationContext shape.
- Scope validation failure: missing / empty scope_list raises ValueError.
- Ledger append: delegation_issued event is written to a temp ledger directory.
- Registration: 'simple_auth_module' is registered in _VERIFY_ADAPTERS after import.

Contract: specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 1
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------


def test_simple_auth_invoke_returns_transparency_fields(tmp_path: Path) -> None:
    """invoke() returns a dict with all six transparency fields non-empty."""
    from ummaya.tools.mock.verify_module_simple_auth import invoke

    result = invoke(
        {
            "scope_list": ["send:hometax.tax-return"],
            "session_id": "test-sess-001",
            "ledger_root": tmp_path / "ledger",
        }
    )

    assert hasattr(result, "transparency_mode"), "Expected a dict from invoke()"
    assert result.transparency_mode == "mock", "_mode must be 'mock'"
    for field in (
        "transparency_reference_implementation",
        "transparency_actual_endpoint_when_live",
        "transparency_security_wrapping_pattern",
        "transparency_policy_authority",
        "transparency_international_reference",
    ):
        value = getattr(result, field)
        assert value is not None and isinstance(value, str) and value.strip(), (
            f"transparency field {field!r} is missing or empty in simple_auth response"
        )


def test_simple_auth_international_reference(tmp_path: Path) -> None:
    """_international_reference must be 'Japan マイナポータル API'."""
    from ummaya.tools.mock.verify_module_simple_auth import invoke

    result = invoke(
        {
            "scope_list": ["check:simple_auth.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert result.transparency_international_reference == "Japan マイナポータル API"


def test_simple_auth_reference_impl(tmp_path: Path) -> None:
    """_reference_implementation must be 'ax-infrastructure-callable-channel'."""
    from ummaya.tools.mock.verify_module_simple_auth import invoke

    result = invoke(
        {
            "scope_list": ["check:simple_auth.identity"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert result.transparency_reference_implementation == "ax-infrastructure-callable-channel"


def test_simple_auth_delegation_context_shape(tmp_path: Path) -> None:
    """invoke() result carries 'token' dict (DelegationContext payload)."""
    from ummaya.tools.mock.verify_module_simple_auth import invoke

    result = invoke(
        {
            "scope_list": ["send:hometax.tax-return"],
            "session_id": "s1",
            "ledger_root": tmp_path / "ledger",
        }
    )
    assert hasattr(result, "delegation_context"), (
        "Expected delegation_context on the typed AuthContext result"
    )
    token = result.delegation_context.token
    assert token.delegation_token.startswith("del_")
    assert token.scope == "send:hometax.tax-return"


def test_simple_auth_multi_scope(tmp_path: Path) -> None:
    """Comma-joined multi-scope list is embedded in the token scope field."""
    from ummaya.tools.mock.verify_module_simple_auth import invoke

    result = invoke(
        {
            "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
            "session_id": "s-multi",
            "ledger_root": tmp_path / "ledger",
        }
    )
    scope = result.delegation_context.token.scope
    assert "find:hometax.simplified" in scope.split(",")
    assert "send:hometax.tax-return" in scope.split(",")


# ---------------------------------------------------------------------------
# Scope validation failure
# ---------------------------------------------------------------------------


def test_simple_auth_scope_grammar_enforced(tmp_path: Path) -> None:
    """Invalid scope string causes DelegationToken validator to raise ValueError."""
    from pydantic import ValidationError

    from ummaya.tools.mock.verify_module_simple_auth import invoke

    with pytest.raises(ValidationError):
        invoke(
            {
                "scope_list": ["BAD_SCOPE_NO_COLON"],
                "session_id": "s-bad",
                "ledger_root": tmp_path / "ledger",
            }
        )


# ---------------------------------------------------------------------------
# Ledger append
# ---------------------------------------------------------------------------


def test_simple_auth_ledger_append(tmp_path: Path) -> None:
    """After invoke, a delegation_issued event is appended to the ledger."""
    from ummaya.tools.mock.verify_module_simple_auth import invoke

    ledger_dir = tmp_path / "ledger"
    invoke(
        {
            "scope_list": ["send:hometax.tax-return"],
            "session_id": "sess-ledger-test",
            "ledger_root": ledger_dir,
        }
    )

    # Find the jsonl file
    jsonl_files = list(ledger_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1, f"Expected 1 JSONL ledger file, found {len(jsonl_files)}"
    lines = [json.loads(line) for line in jsonl_files[0].read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    event = lines[0]
    assert event["kind"] == "delegation_issued"
    assert event["session_id"] == "sess-ledger-test"
    assert event["delegation_token"].startswith("del_")
    assert event["scope"] == "send:hometax.tax-return"
    assert event["verify_tool_id"] == "mock_verify_module_simple_auth"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_simple_auth_is_registered() -> None:
    """Importing the module registers 'simple_auth_module' in _VERIFY_ADAPTERS."""
    import ummaya.tools.mock.verify_module_simple_auth  # noqa: F401 — side-effect
    from ummaya.primitives.verify import _VERIFY_ADAPTERS

    assert "simple_auth_module" in _VERIFY_ADAPTERS, (
        "simple_auth_module not found in _VERIFY_ADAPTERS after import"
    )
