# SPDX-License-Identifier: Apache-2.0
"""T065 — Verify primitive family-mismatch dispatcher test.

Asserts that:
- (happy path) a known family_hint routes to its adapter and returns a valid
  AuthContext variant.
- (mismatch path) an unregistered family_hint causes the dispatcher to return
  a VerifyMismatchError without raising an exception.
"""

from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime

import pytest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_gongdong_injeungseo() -> None:
    """Calling verify() with a registered family returns a valid AuthContext."""
    import ummaya.tools.mock  # noqa: F401 — registers all 6 adapters
    from ummaya.primitives.verify import GongdongInjeungseoContext, verify

    result = await verify("gongdong_injeungseo", {})

    assert isinstance(result, GongdongInjeungseoContext), (
        f"Expected GongdongInjeungseoContext, got {type(result).__name__!r}"
    )
    assert result.family == "gongdong_injeungseo"
    assert result.published_tier == "gongdong_injeungseo_personal_aal3"
    assert result.nist_aal_hint == "AAL3"
    logger.debug("happy path result: %s", result)


# ---------------------------------------------------------------------------
# Mismatch path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unregistered_family_returns_mismatch_error() -> None:
    """verify() with an unknown family must return VerifyMismatchError, not raise."""
    import ummaya.tools.mock  # noqa: F401
    from ummaya.primitives.verify import VerifyMismatchError, verify

    result = await verify("nonexistent_cert_family", {})

    assert isinstance(result, VerifyMismatchError), (
        f"Expected VerifyMismatchError, got {type(result).__name__!r}"
    )
    assert result.family == "mismatch_error"
    assert result.reason == "family_mismatch"
    assert result.expected_family == "nonexistent_cert_family"
    assert result.observed_family == "<no_adapter>"
    logger.debug("mismatch result: %s", result)


@pytest.mark.asyncio
async def test_tool_id_specific_verify_adapter_does_not_override_family_adapter() -> None:
    """A live MobileID tool adapter must be selectable without replacing the mock family."""
    from ummaya.primitives.verify import (
        MobileIdContext,
        register_verify_adapter,
        verify,
    )

    verify_mod = importlib.import_module("ummaya.primitives.verify")
    original_adapters = dict(verify_mod._VERIFY_ADAPTERS)
    original_families = dict(getattr(verify_mod, "_VERIFY_ADAPTER_FAMILIES", {}))

    def family_adapter(session_context: dict[str, object]) -> MobileIdContext:
        return MobileIdContext(
            published_tier="mobile_id_mdl_aal2",
            nist_aal_hint="AAL2",
            verified_at=datetime(2026, 5, 18, tzinfo=UTC),
            external_session_ref="mock-family-ref",
            id_type="mdl",
        )

    def live_adapter(session_context: dict[str, object]) -> MobileIdContext:
        return MobileIdContext(
            published_tier="mobile_id_mdl_aal2",
            nist_aal_hint="AAL2",
            verified_at=datetime(2026, 5, 18, tzinfo=UTC),
            external_session_ref="live-tool-ref",
            id_type="mdl",
        )

    try:
        register_verify_adapter("mobile_id", family_adapter)
        register_verify_adapter("mobile_id", live_adapter, tool_id="live_verify_mobile_id")

        default_result = await verify("mobile_id", {})
        selected_result = await verify(
            "mobile_id",
            {"_verify_tool_id": "live_verify_mobile_id"},
        )

        assert isinstance(default_result, MobileIdContext)
        assert default_result.external_session_ref == "mock-family-ref"
        assert isinstance(selected_result, MobileIdContext)
        assert selected_result.external_session_ref == "live-tool-ref"
    finally:
        verify_mod._VERIFY_ADAPTERS.clear()
        verify_mod._VERIFY_ADAPTERS.update(original_adapters)
        if hasattr(verify_mod, "_VERIFY_ADAPTER_FAMILIES"):
            verify_mod._VERIFY_ADAPTER_FAMILIES.clear()
            verify_mod._VERIFY_ADAPTER_FAMILIES.update(original_families)


@pytest.mark.asyncio
async def test_selected_unknown_tool_id_does_not_fall_back_to_family_adapter() -> None:
    """Explicit live selection must not be satisfied by the family mock on lookup miss."""
    from ummaya.primitives.verify import (
        MobileIdContext,
        VerifyMismatchError,
        register_verify_adapter,
        verify,
    )

    verify_mod = importlib.import_module("ummaya.primitives.verify")
    original_adapters = dict(verify_mod._VERIFY_ADAPTERS)
    original_families = dict(getattr(verify_mod, "_VERIFY_ADAPTER_FAMILIES", {}))

    def family_adapter(session_context: dict[str, object]) -> MobileIdContext:
        return MobileIdContext(
            published_tier="mobile_id_mdl_aal2",
            nist_aal_hint="AAL2",
            verified_at=datetime(2026, 5, 18, tzinfo=UTC),
            external_session_ref="mock-family-ref",
            id_type="mdl",
        )

    try:
        register_verify_adapter("mobile_id", family_adapter)
        result = await verify("mobile_id", {"_verify_tool_id": "missing_live_mobileid"})

        assert isinstance(result, VerifyMismatchError)
        assert result.expected_family == "mobile_id"
        assert result.observed_family == "<no_adapter>"
        assert "missing_live_mobileid" in result.message
    finally:
        verify_mod._VERIFY_ADAPTERS.clear()
        verify_mod._VERIFY_ADAPTERS.update(original_adapters)
        if hasattr(verify_mod, "_VERIFY_ADAPTER_FAMILIES"):
            verify_mod._VERIFY_ADAPTER_FAMILIES.clear()
            verify_mod._VERIFY_ADAPTER_FAMILIES.update(original_families)
