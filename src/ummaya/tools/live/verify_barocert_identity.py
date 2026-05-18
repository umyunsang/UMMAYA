# SPDX-License-Identifier: Apache-2.0
"""Live BaroCert identity check adapter for the ganpyeon_injeung family."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable

import ummaya.tools.mock.verify_ganpyeon_injeung  # noqa: F401
from ummaya.primitives.verify import (
    _VERIFY_ADAPTERS,
    GanpyeonInjeungContext,
    VerifyMismatchError,
    register_verify_adapter,
)
from ummaya.tools.live.barocert_identity_client import (
    BarocertIdentityClient,
    BarocertIdentityStatus,
    BarocertIdentityVerification,
    BarocertProviderError,
    parse_identity_status,
    parse_identity_verification,
)

logger = logging.getLogger(__name__)

LIVE_TOOL_ID = "live_verify_ganpyeon_injeung"
FAMILY = "ganpyeon_injeung"

Adapter = Callable[[dict[str, object]], object]


def _current_previous_adapter() -> Adapter | None:
    current = _VERIFY_ADAPTERS.get(FAMILY)
    if getattr(current, "_barocert_live_adapter", False):
        previous = getattr(current, "_previous_adapter", None)
        return previous if callable(previous) else None
    return current if callable(current) else None


_PREVIOUS_ADAPTER = _current_previous_adapter()


def _selected_tool_id(session_context: dict[str, object]) -> str:
    tool_id = session_context.get("_tool_id") or session_context.get("tool_id")
    return str(tool_id or "")


def _is_live_selection(session_context: dict[str, object]) -> bool:
    return _selected_tool_id(session_context) == LIVE_TOOL_ID


def _call_previous_adapter(session_context: dict[str, object]) -> object:
    if _PREVIOUS_ADAPTER is None:
        return VerifyMismatchError(
            expected_family=FAMILY,
            observed_family="barocert_identity:no_previous_adapter",
            message="No previous ganpyeon_injeung adapter is registered.",
        )
    result = _PREVIOUS_ADAPTER(session_context)
    if inspect.isawaitable(result):
        return _fail("async_previous_adapter", "previous ganpyeon adapter returned awaitable")
    return result


def _fail(reason: str, message: str) -> VerifyMismatchError:
    return VerifyMismatchError(
        expected_family=FAMILY,
        observed_family=f"barocert_identity:{reason}",
        message=f"BaroCert identity check failed ({reason}): {message}",
    )


def _receipt_id(session_context: dict[str, object]) -> str:
    raw = (
        session_context.get("receiptID")
        or session_context.get("receipt_id")
        or session_context.get("external_session_ref")
    )
    if isinstance(raw, str) and raw.startswith("barocert:"):
        parts = raw.split(":", 2)
        raw = parts[-1] if len(parts) == 3 else raw
    if not isinstance(raw, str) or not raw.strip():
        raise BarocertProviderError("missing_receipt_id", "receiptID is required")
    return raw.strip()


def _parse_or_call_live(
    provider: str,
    receipt_id: str,
    session_context: dict[str, object],
) -> tuple[BarocertIdentityStatus, BarocertIdentityVerification]:
    status_fixture = session_context.get("_fixture_status")
    verify_fixture = session_context.get("_fixture_verify")
    if isinstance(status_fixture, dict) and isinstance(verify_fixture, dict):
        status = parse_identity_status(provider, receipt_id, status_fixture)
        verification = parse_identity_verification(provider, receipt_id, verify_fixture)
        return status, verification

    client = BarocertIdentityClient.from_env(provider)
    status = client.get_status(receipt_id)
    verification = client.verify_identity(receipt_id)
    return status, verification


def invoke(
    session_context: dict[str, object],
) -> GanpyeonInjeungContext | VerifyMismatchError:
    """Route explicit live selection to BaroCert; otherwise preserve the mock adapter."""

    if not _is_live_selection(session_context):
        return _call_previous_adapter(session_context)  # type: ignore[return-value]

    provider = str(session_context.get("provider") or "toss").strip().lower()
    try:
        receipt_id = _receipt_id(session_context)
        status, verification = _parse_or_call_live(provider, receipt_id, session_context)
        if not status.is_complete:
            return _fail("status_not_complete", f"status={status.state}")
        if not verification.identity_evidence_present or not verification.signed_data_present:
            return _fail("missing_identity_evidence", "identity evidence or signedData missing")
    except BarocertProviderError as exc:
        logger.info("BaroCert identity check failed closed: %s", exc.reason)
        return _fail(exc.reason, exc.message)

    return GanpyeonInjeungContext.model_validate(
        {
            "family": FAMILY,
            "published_tier": f"ganpyeon_injeung_{provider}_aal2",
            "nist_aal_hint": "AAL2",
            "verified_at": verification.verified_at,
            "external_session_ref": f"barocert:{provider}:{receipt_id}",
            "provider": provider,
        }
    )


invoke._barocert_live_adapter = True  # type: ignore[attr-defined]
invoke._previous_adapter = _PREVIOUS_ADAPTER  # type: ignore[attr-defined]
register_verify_adapter(FAMILY, invoke)

__all__ = ["FAMILY", "LIVE_TOOL_ID", "invoke"]
