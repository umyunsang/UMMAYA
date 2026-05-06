# SPDX-License-Identifier: Apache-2.0
"""T035 — 6-family coercion-free dispatch for the verify primitive.

Proves FR-010: family_hint mismatch returns VerifyMismatchError; the
dispatcher NEVER silently coerces one family's context into another.

Each test imports the mock verify adapters (which register themselves) and
drives the verify() coroutine directly.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest
import pytest_asyncio  # noqa: F401 — ensures asyncio mode is active

# Import mock adapters so they self-register; order-independent.
# NOTE: verify_digital_onepass DELETED — FR-004 (서비스 종료 2025-12-30, Epic ε #2296 T021).
import kosmos.tools.mock.verify_ganpyeon_injeung  # noqa: F401
import kosmos.tools.mock.verify_geumyung_injeungseo  # noqa: F401
import kosmos.tools.mock.verify_gongdong_injeungseo  # noqa: F401
import kosmos.tools.mock.verify_mobile_id  # noqa: F401
import kosmos.tools.mock.verify_mydata  # noqa: F401
from kosmos.memdir.consent_ledger import DelegationIssuedEvent, read_delegation_events
from kosmos.primitives.verify import (
    GanpyeonInjeungContext,
    GeumyungInjeungseoContext,
    GongdongInjeungseoContext,
    MobileIdContext,
    MyDataContext,
    VerifyMismatchError,
    verify,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Happy-path: each family_hint dispatches to the correct adapter
# ---------------------------------------------------------------------------


async def test_dispatch_gongdong_injeungseo() -> None:
    result = await verify("gongdong_injeungseo", {})
    assert isinstance(result, GongdongInjeungseoContext)
    assert result.family == "gongdong_injeungseo"


async def test_dispatch_geumyung_injeungseo() -> None:
    result = await verify("geumyung_injeungseo", {})
    assert isinstance(result, GeumyungInjeungseoContext)
    assert result.family == "geumyung_injeungseo"


async def test_dispatch_ganpyeon_injeung() -> None:
    result = await verify("ganpyeon_injeung", {})
    assert isinstance(result, GanpyeonInjeungContext)
    assert result.family == "ganpyeon_injeung"


async def test_dispatch_ganpyeon_injeung_issues_delegation_context() -> None:
    result = await verify(
        "ganpyeon_injeung",
        {
            "scope_list": ["lookup:gov24.movein", "submit:gov24.minwon"],
            "purpose_ko": "전입신고와 주소변경",
            "purpose_en": "Move-in report and linked address updates",
        },
    )

    assert isinstance(result, GanpyeonInjeungContext)
    assert result.delegation_context is not None
    assert result.delegation_context.token.scope == (
        "lookup:gov24.movein,submit:gov24.minwon"
    )


async def test_dispatch_ganpyeon_injeung_writes_delegation_issued_event(
    tmp_path: Path,
) -> None:
    session_id = "sess-ganpyeon-ledger"
    result = await verify(
        "ganpyeon_injeung",
        {
            "session_id": session_id,
            "scope_list": ["lookup:gov24.movein", "submit:gov24.minwon"],
            "purpose_ko": "전입신고와 주소변경",
            "purpose_en": "Move-in report and linked address updates",
            "ledger_root": tmp_path,
        },
    )

    assert isinstance(result, GanpyeonInjeungContext)
    assert result.delegation_context is not None
    token = result.delegation_context.token
    events = read_delegation_events(ledger_root=tmp_path)

    issued = [
        event
        for event in events
        if isinstance(event, DelegationIssuedEvent)
        and event.delegation_token == token.delegation_token
    ]
    assert len(issued) == 1
    assert issued[0].session_id == session_id
    assert issued[0].scope == "lookup:gov24.movein,submit:gov24.minwon"
    assert issued[0].verify_tool_id == "mock_verify_ganpyeon_injeung"


async def test_dispatch_digital_onepass_deleted() -> None:
    """digital_onepass adapter was deleted (FR-004, Epic ε #2296 T021).

    The adapter is no longer registered, so family_hint='digital_onepass' must
    return VerifyMismatchError (fail-closed, no adapter registered).
    """
    result = await verify("digital_onepass", {})
    assert isinstance(result, VerifyMismatchError)
    assert result.reason == "family_mismatch"
    assert result.expected_family == "digital_onepass"


async def test_dispatch_mobile_id() -> None:
    result = await verify("mobile_id", {})
    assert isinstance(result, MobileIdContext)
    assert result.family == "mobile_id"


async def test_dispatch_mydata() -> None:
    result = await verify("mydata", {})
    assert isinstance(result, MyDataContext)
    assert result.family == "mydata"


# ---------------------------------------------------------------------------
# Mismatch guard: unregistered family → VerifyMismatchError (no coercion)
# ---------------------------------------------------------------------------


async def test_unregistered_family_returns_mismatch() -> None:
    result = await verify("alien_cert", {})
    assert isinstance(result, VerifyMismatchError)
    assert result.reason == "family_mismatch"
    assert result.expected_family == "alien_cert"


# ---------------------------------------------------------------------------
# FR-010: adapter returning wrong family → VerifyMismatchError (no coercion)
# ---------------------------------------------------------------------------


async def test_cross_family_adapter_blocked() -> None:
    """Simulate an adapter that accidentally returns the wrong family context.

    The verify dispatcher must detect the mismatch and return VerifyMismatchError
    instead of silently passing a context whose .family disagrees with family_hint.
    """
    from kosmos.primitives.verify import (
        _VERIFY_ADAPTERS,
        register_verify_adapter,
    )

    # Register a rogue adapter under "mobile_id" that returns a gongdong context.
    original = _VERIFY_ADAPTERS.get("mobile_id")

    def _rogue_adapter(ctx: dict) -> GongdongInjeungseoContext:
        from datetime import datetime

        return GongdongInjeungseoContext(
            family="gongdong_injeungseo",
            published_tier="gongdong_injeungseo_personal_aal3",
            nist_aal_hint="AAL3",
            verified_at=datetime(2026, 4, 19, tzinfo=UTC),
            certificate_issuer="KICA",
        )

    register_verify_adapter("mobile_id", _rogue_adapter)
    try:
        result = await verify("mobile_id", {})
        assert isinstance(result, VerifyMismatchError), (
            f"Expected VerifyMismatchError but got {type(result).__name__}"
        )
        assert result.expected_family == "mobile_id"
        assert result.observed_family == "gongdong_injeungseo"
    finally:
        # Restore original adapter so other tests are unaffected.
        if original is not None:
            register_verify_adapter("mobile_id", original)
        else:
            _VERIFY_ADAPTERS.pop("mobile_id", None)


# ---------------------------------------------------------------------------
# VerifyMismatchError adapter: adapter explicitly returns mismatch passes through
# ---------------------------------------------------------------------------


async def test_adapter_returning_mismatch_is_propagated() -> None:
    """If an adapter explicitly returns VerifyMismatchError it is passed through."""
    from kosmos.primitives.verify import (
        _VERIFY_ADAPTERS,
        register_verify_adapter,
    )

    original = _VERIFY_ADAPTERS.get("mydata")

    def _mismatch_adapter(ctx: dict) -> VerifyMismatchError:
        return VerifyMismatchError(
            family="mismatch_error",
            reason="family_mismatch",
            expected_family="mydata",
            observed_family="unsupported",
            message="Test: adapter signals explicit mismatch.",
        )

    register_verify_adapter("mydata", _mismatch_adapter)
    try:
        result = await verify("mydata", {})
        assert isinstance(result, VerifyMismatchError)
        assert result.observed_family == "unsupported"
    finally:
        if original is not None:
            register_verify_adapter("mydata", original)
        else:
            _VERIFY_ADAPTERS.pop("mydata", None)
