# SPDX-License-Identifier: Apache-2.0
"""Spec 2296 Codex P1 #2446 fix verification — verify(family_hint=...) dispatch.

The 5 new mock_verify_module_* mocks (Phase 4A) originally returned stamped
dicts, which Spec 031's verify() dispatcher rejected with VerifyMismatchError
because the dispatcher only accepts known AuthContext typed variants. This
broke the LLM-driven citizen chain in the TUI smoke (PR #2445 Codex P1 review).

This test asserts the post-#2446 fix: each of the 5 new families dispatches
through verify(family_hint=...) and returns the correct typed AuthContext
variant carrying the wrapped DelegationContext (4 families) or
IdentityAssertion (any_id_sso).

Reference:
- specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 1
- src/ummaya/primitives/verify.py — AuthContext discriminated union (11 variants
  after Spec 2296: original 6 + 5 new AX-channel variants)
"""

from __future__ import annotations

import pytest

import ummaya.tools.mock  # noqa: F401 — register all 5 new verify mocks at import time
from ummaya.primitives.delegation import DelegationContext, IdentityAssertion
from ummaya.primitives.verify import (
    AnyIdSsoContext,
    GeumyungModuleContext,
    KECContext,
    ModidContext,
    SimpleAuthModuleContext,
    VerifyMismatchError,
    verify,
)


@pytest.mark.asyncio
async def test_verify_modid_returns_typed_modid_context() -> None:
    """verify(family_hint='modid') returns ModidContext, not VerifyMismatchError."""
    result = await verify(
        family_hint="modid",
        session_context={
            "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
            "session_id": "test-modid",
        },
    )
    assert isinstance(result, ModidContext), (
        f"Expected ModidContext, got {type(result).__name__}: {result!r}"
    )
    assert result.family == "modid"
    assert result.published_tier == "modid_aal3"
    assert isinstance(result.delegation_context, DelegationContext)
    assert result.delegation_context.token.delegation_token.startswith("del_")
    assert result.transparency_mode == "mock"


@pytest.mark.asyncio
async def test_verify_simple_auth_module_returns_typed_context() -> None:
    """verify(family_hint='simple_auth_module') returns SimpleAuthModuleContext."""
    result = await verify(
        family_hint="simple_auth_module",
        session_context={
            "scope_list": ["check:simple_auth.identity"],
            "session_id": "test-sa",
        },
    )
    assert isinstance(result, SimpleAuthModuleContext)
    assert result.family == "simple_auth_module"
    assert result.delegation_context.token.delegation_token.startswith("del_")


@pytest.mark.asyncio
async def test_verify_kec_returns_typed_context() -> None:
    """verify(family_hint='kec') returns KECContext."""
    result = await verify(
        family_hint="kec",
        session_context={
            "scope_list": ["check:kec.identity"],
            "session_id": "test-kec",
        },
    )
    assert isinstance(result, KECContext)
    assert result.family == "kec"
    assert result.published_tier == "kec_aal3"


@pytest.mark.asyncio
async def test_verify_geumyung_module_returns_typed_context() -> None:
    """verify(family_hint='geumyung_module') returns GeumyungModuleContext."""
    result = await verify(
        family_hint="geumyung_module",
        session_context={
            "scope_list": ["check:geumyung.identity"],
            "session_id": "test-geumyung",
        },
    )
    assert isinstance(result, GeumyungModuleContext)
    assert result.family == "geumyung_module"
    assert result.published_tier == "geumyung_module_aal3"


@pytest.mark.asyncio
async def test_verify_any_id_sso_returns_typed_context_with_identity_assertion() -> None:
    """verify(family_hint='any_id_sso') returns AnyIdSsoContext wrapping IdentityAssertion.

    Per delegation-flow-design.md § 2.2, Any-ID is identity-SSO only — no
    DelegationContext. The wrapped envelope is IdentityAssertion; downstream
    submit/lookup adapters must reject it with DelegationGrantMissing.
    """
    result = await verify(
        family_hint="any_id_sso",
        session_context={"session_id": "test-sso"},
    )
    assert isinstance(result, AnyIdSsoContext), (
        f"Expected AnyIdSsoContext, got {type(result).__name__}"
    )
    assert result.family == "any_id_sso"
    assert isinstance(result.identity_assertion, IdentityAssertion)
    # Critically: AnyIdSsoContext does NOT have a delegation_context field.
    assert not hasattr(result, "delegation_context"), (
        "AnyIdSsoContext must NOT carry a delegation_context — identity-SSO only "
        "per delegation-flow-design.md § 2.2"
    )


@pytest.mark.asyncio
async def test_verify_unknown_family_returns_mismatch() -> None:
    """verify(family_hint='unknown_family') still produces VerifyMismatchError.

    Confirms the dispatcher's family-not-registered path still works after the
    AuthContext union was extended with 5 new variants.
    """
    result = await verify(
        family_hint="unknown_family_xyz",
        session_context={},
    )
    assert isinstance(result, VerifyMismatchError)
