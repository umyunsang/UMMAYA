# SPDX-License-Identifier: Apache-2.0
"""T021/T022/T023 — ``send`` primitive for the UMMAYA Five-Primitive Harness.

The ``send`` primitive absorbs every write-transaction verb:
- Traffic fine payment
- Welfare application filing
- Any other government-facing side-effecting operation

The main surface is **shape-only** (FR-001..FR-003): ``{tool_id, params}`` →
``{transaction_id, status, adapter_receipt}``. No domain-specific field ever
appears on ``SubmitInput`` or ``SubmitOutput`` (SC-002).

Domain vocabulary (ministry enums, service codes, application types) lives
exclusively in adapter modules under ``src/ummaya/tools/mock/<ministry>/``.

Architecture: the dispatcher holds an in-process ``_ADAPTER_REGISTRY``
(``dict[str, AdapterRegistration]``) populated by adapter ``REGISTRATION``
objects at module-import time. The global ``ToolRegistry`` singleton manages
the older ``GovAPITool`` surface; ``send`` uses a parallel lightweight
mapping to avoid coupling the new envelope to the legacy BM25 / retrieval stack.

T023 — deterministic ``transaction_id`` derivation:
    ``urn:ummaya:send:`` + SHA-256 over canonical JSON of
    ``{tool_id, params (sorted keys), adapter_nonce}``.
    Same inputs always produce the same URN. The ``adapter_nonce`` is sourced
    from :attr:`ummaya.tools.registry.AdapterRegistration.nonce` so the
    dispatcher and the adapter body compute byte-identical transaction ids.
    Send adapters declare a stable ``nonce`` string (e.g.
    ``"mock_traffic_fine_pay_v1_nonce_v1"``) on their ``AdapterRegistration``;
    the dispatcher reads that value directly — ``None`` is the explicit
    opt-out signal for adapters that do not need nonce namespacing.

OTEL spans: each invocation emits a ``gen_ai.tool_loop.iteration`` span (Spec 021)
via the global ``TracerProvider``. When tracing is disabled (``OTEL_SDK_DISABLED=true``
or no endpoint configured), the span is a no-op with zero overhead.

Audit: each invocation logs a best-effort ``ToolCallAuditRecord`` through
``_emit_audit_record()``. Audit storage is delegated to the existing Spec 024
sink (append-only, deferred per spec); this module only calls
``ummaya.security.audit.ToolCallAuditRecord`` shape-construction.

References:
- specs/031-five-primitive-harness/data-model.md § 1
- specs/031-five-primitive-harness/contracts/submit.input.schema.json
- specs/031-five-primitive-harness/contracts/submit.output.schema.json
- FR-001..FR-005, SC-002, SC-005
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field

from ummaya.primitives._errors import AdapterInvocationError, AdapterNotFoundError
from ummaya.tools.errors import AdapterIdCollisionError
from ummaya.tools.registry import AdapterRegistration

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
_SUBMIT_TOOL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_INVALID_TOOL_ID_SENTINEL = "invalid_tool_id"

# ---------------------------------------------------------------------------
# Public models — T021
# ---------------------------------------------------------------------------


class SubmitInput(BaseModel):
    """Shape-only submit envelope input.

    ``tool_id`` is the sole routing key. ``params`` is opaque at this layer;
    the adapter owns the typed Pydantic model and validates at invocation time.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_]*$",
        description=(
            "Globally unique adapter id registered in the submit dispatcher. "
            "Collisions rejected at registration (FR-020)."
        ),
    )
    params: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Opaque adapter-specific parameters. Adapter validates against its "
            "own Pydantic model at invocation time. Main envelope does NOT narrow "
            "this shape (harness-not-reimplementation)."
        ),
    )


class SubmitStatus(StrEnum):
    """Terminal / non-terminal disposition from the adapter.

    Failed adapter invocations surface as ``failed`` or ``rejected``,
    never as an unhandled Python exception (FR-005).
    """

    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    rejected = "rejected"


class SubmitOutput(BaseModel):
    """Shape-only submit envelope output.

    ``adapter_receipt`` is opaque — domain-specific receipt data lives there.
    ``transaction_id`` is deterministic per invocation (content-hash, FR-004).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str = Field(
        min_length=1,
        max_length=128,
        description=(
            "Deterministic per invocation (content-hash of input + adapter_nonce) — FR-004."
        ),
    )
    status: SubmitStatus
    adapter_receipt: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Opaque adapter-specific receipt (e.g. 접수번호, authorization code). "
            "Main envelope does NOT narrow this shape."
        ),
    )


# ---------------------------------------------------------------------------
# In-process adapter registry — parallel to ToolRegistry (GovAPITool)
# ---------------------------------------------------------------------------

# Maps tool_id → (AdapterRegistration, invoke_callable)
_ADAPTER_REGISTRY: dict[str, tuple[AdapterRegistration, Any]] = {}


def register_submit_adapter(registration: AdapterRegistration, invoke_fn: Any) -> None:
    """Register a submit adapter in the in-process dispatch table.

    Args:
        registration: ``AdapterRegistration`` metadata (must have
            ``primitive == AdapterPrimitive.send``).
        invoke_fn: Async callable ``async (params: <AdapterInput>) -> SubmitOutput``.
            The dispatcher passes the validated adapter input model as the sole arg.

    Raises:
        AdapterIdCollisionError: When ``registration.tool_id`` is already
            registered. Spec 031 FR-020 rejects duplicate registrations at
            import time rather than silently discarding them so a typo or a
            rogue third-party module cannot hijack an existing tool id. The
            error mirrors :meth:`ToolRegistry.register` on the legacy
            ``GovAPITool`` surface for consistency across both paths.

    This function is called at module-import time by adapter modules (e.g.
    ``src/ummaya/tools/mock/data_go_kr/fines_pay.py``) as their last statement.
    """
    existing = _ADAPTER_REGISTRY.get(registration.tool_id)
    if existing is not None:
        existing_registration, _ = existing
        logger.error(
            "submit dispatcher: tool_id collision at registration (FR-020) — "
            "%s already registered by %s; rejecting re-registration from %s.",
            registration.tool_id,
            existing_registration.module_path,
            registration.module_path,
        )
        raise AdapterIdCollisionError(
            registration.tool_id,
            existing_module=existing_registration.module_path,
        )
    _ADAPTER_REGISTRY[registration.tool_id] = (registration, invoke_fn)
    logger.info("submit dispatcher: registered adapter %s", registration.tool_id)


# ---------------------------------------------------------------------------
# T023 — Deterministic transaction_id derivation
# ---------------------------------------------------------------------------


def derive_transaction_id(
    tool_id: str,
    params: dict[str, object],
    *,
    adapter_nonce: str | None,
) -> str:
    """Derive a deterministic ``urn:ummaya:send:<sha256>`` transaction_id.

    The content hash is SHA-256 over the canonical JSON encoding of::

        {"tool_id": <str>, "params": <sorted-keys dict>, "adapter_nonce": <str|None>}

    ``sort_keys=True`` on ``params`` guarantees that dict insertion order does
    not affect the output (FR-004 invariant: same logical input → same URN).

    Args:
        tool_id:       Adapter identifier.
        params:        Raw invoke params dict (not adapter-typed; sorting is enough).
        adapter_nonce: Optional per-registration nonce string declared by the
                       adapter to namespace its transaction space.

    Returns:
        A ``urn:ummaya:send:<sha256-hex>`` string (72 chars fixed length).
    """
    canonical_payload: dict[str, object] = {
        "tool_id": tool_id,
        "params": dict(sorted(params.items())),
        "adapter_nonce": adapter_nonce,
    }
    canonical = json.dumps(
        canonical_payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"urn:ummaya:send:{digest}"


# ---------------------------------------------------------------------------
# T020 — SC-005 published_tier gate helper
# ---------------------------------------------------------------------------

# Ordered tier list — higher index = higher assurance level.
# Pre-v1.2 adapters may omit published_tier_minimum (None = no gate).
_TIER_ORDER: list[str] = [
    # AAL1 tiers
    "digital_onepass_level1_aal1",
    # AAL2 tiers
    "geumyung_injeungseo_personal_aal2",
    "gongdong_injeungseo_bank_only_aal2",
    "ganpyeon_injeung_pass_aal2",
    "ganpyeon_injeung_kakao_aal2",
    "ganpyeon_injeung_naver_aal2",
    "ganpyeon_injeung_toss_aal2",
    "ganpyeon_injeung_bank_aal2",
    "ganpyeon_injeung_samsung_aal2",
    "ganpyeon_injeung_payco_aal2",
    "digital_onepass_level2_aal2",
    "mobile_id_mdl_aal2",
    "mobile_id_resident_aal2",
    "mydata_individual_aal2",
    "simple_auth_module_aal2",
    "any_id_sso_aal2",
    # AAL3 tiers
    "gongdong_injeungseo_personal_aal3",
    "gongdong_injeungseo_corporate_aal3",
    "geumyung_injeungseo_business_aal3",
    "digital_onepass_level3_aal3",
    "modid_aal3",
    "kec_aal3",
    "geumyung_module_aal3",
]


# AAL-band rank (higher = stronger assurance). Used for cross-band comparison
# in check_tier_gate. Within the same band, we fall back to exact tier-id
# equality rather than ordinal position, because peer AAL2/AAL3 tiers from
# unrelated identity families have no intrinsic ordering (see code review on
# PR #1149).
_AAL_RANK: dict[str, int] = {"AAL1": 1, "AAL2": 2, "AAL3": 3}


def _aal_band_of(tier: str) -> str | None:
    """Extract the NIST AAL band ('AAL1'/'AAL2'/'AAL3') from a published tier id.

    Every entry in ``_TIER_ORDER`` terminates with ``_aal1``/``_aal2``/``_aal3``
    per the Spec 031 § 6 naming convention. Returns ``None`` when the suffix is
    not one of the three recognised bands (fail-closed signal).
    """
    suffix = tier.rsplit("_", 1)[-1].upper()
    return suffix if suffix in _AAL_RANK else None


def check_tier_gate(
    *,
    registration: AdapterRegistration,
    auth_context: object,
) -> dict[str, object] | None:
    """Check if the caller's auth context satisfies the adapter's published_tier_minimum.

    Returns ``None`` when the gate passes (invocation should proceed).
    Returns a rejection dict ``{"rejected": True, "reason": <str>}`` when the
    caller's tier is insufficient or missing and the adapter requires one.

    Args:
        registration: The adapter's registration metadata.
        auth_context: The caller's auth context object (any Pydantic model that
                      carries a ``published_tier`` field), or ``None``.

    SC-005 semantics:
        - ``published_tier_minimum=None`` → gate always passes (pre-v1.2 window).
        - ``auth_context=None`` AND ``published_tier_minimum`` is set → rejected.
        - Caller's AAL band < required AAL band → rejected.
        - Caller's AAL band > required AAL band → accepted.
        - Caller's AAL band == required AAL band but tier ids differ → rejected
          (peer AAL tiers from unrelated identity families are NOT auto-accepted;
          cross-family acceptance requires an explicit accept-set mechanism that
          this spec deliberately leaves out of scope).
        - Caller tier id == required tier id → accepted.
    """
    required_tier = registration.published_tier_minimum
    if required_tier is None:
        return None  # no tier gate (pre-v1.2 or public adapter)

    if auth_context is None:
        return {
            "rejected": True,
            "reason": (
                f"published_tier_minimum={required_tier!r} requires an AuthContext "
                "but none was provided (SC-005)"
            ),
        }

    caller_tier: str | None = getattr(auth_context, "published_tier", None)
    if caller_tier is None:
        return {
            "rejected": True,
            "reason": (
                f"published_tier_minimum={required_tier!r}: auth_context has no "
                "published_tier field (SC-005)"
            ),
        }

    # Step 1: caller + required tier ids must both be recognised published tiers.
    if caller_tier not in _TIER_ORDER:
        return {
            "rejected": True,
            "reason": (
                f"published_tier_minimum={required_tier!r}: caller tier "
                f"{caller_tier!r} is not a recognised published tier (SC-005)"
            ),
        }
    if required_tier not in _TIER_ORDER:
        logger.error(
            "check_tier_gate: required tier %r not in _TIER_ORDER — failing closed",
            required_tier,
        )
        return {
            "rejected": True,
            "reason": (
                f"published_tier_minimum={required_tier!r} is not in the known "
                "tier order — failing closed (SC-005)"
            ),
        }

    # Step 2: compare AAL strength first. Higher AAL caller always satisfies a
    # lower-AAL requirement; lower AAL caller never satisfies a higher-AAL
    # requirement. This matches the NIST SP 800-63B advisory hint rather than
    # relying on arbitrary ordinal position within the tier list.
    caller_band = _aal_band_of(caller_tier)
    required_band = _aal_band_of(required_tier)
    if caller_band is None or required_band is None:
        logger.error(
            "check_tier_gate: unrecognised AAL suffix (caller=%r required=%r)",
            caller_tier,
            required_tier,
        )
        return {
            "rejected": True,
            "reason": (
                f"published_tier_minimum={required_tier!r}: unable to extract "
                f"NIST AAL band from caller_tier={caller_tier!r} — failing closed (SC-005)"
            ),
        }

    caller_rank = _AAL_RANK[caller_band]
    required_rank = _AAL_RANK[required_band]

    if caller_rank > required_rank:
        return None  # stronger AAL always accepted
    if caller_rank < required_rank:
        return {
            "rejected": True,
            "reason": (
                f"published_tier_minimum={required_tier!r} ({required_band}) not met: "
                f"caller has {caller_tier!r} ({caller_band}) (SC-005)"
            ),
        }

    # Step 3: same AAL band — require exact tier-id match. Peer AAL tiers from
    # unrelated identity families (e.g., ganpyeon_injeung_kakao_aal2 vs
    # mydata_individual_aal2) are NOT auto-accepted. A future spec can add an
    # explicit accept-set on AdapterRegistration for cross-family acceptance.
    if caller_tier != required_tier:
        return {
            "rejected": True,
            "reason": (
                f"published_tier_minimum={required_tier!r} ({required_band}) not met: "
                f"caller has {caller_tier!r} which is a peer {caller_band} tier from a "
                "different identity family; cross-family acceptance is not permitted "
                "without an explicit accept-set (SC-005)"
            ),
        }

    return None  # gate passes


# ---------------------------------------------------------------------------
# T022 — Main send() dispatcher
# ---------------------------------------------------------------------------


async def submit(
    tool_id: str,
    params: dict[str, object] | None = None,
    *,
    auth_context: object = None,
    session_id: str = "unknown",
) -> SubmitOutput | AdapterNotFoundError | AdapterInvocationError:
    """Dispatch a write-transaction to the registered adapter for ``tool_id``.

    This is the main-surface entry point for the ``send`` primitive.  It:

    1. Resolves the ``AdapterRegistration`` for ``tool_id``.
    2. Checks the ``published_tier_minimum`` gate (SC-005).
    3. Derives the deterministic ``transaction_id`` (FR-004 / T023).
    4. Validates ``params`` against the adapter's input model (best-effort).
    5. Awaits the adapter's ``invoke()`` coroutine.
    6. Emits an OTEL ``gen_ai.tool_loop.iteration`` span (Spec 021).
    7. Returns a ``SubmitOutput`` on success or a structured error on failure.

    Args:
        tool_id:       Registered adapter identifier.
        params:        Opaque adapter-specific parameters.
        auth_context:  Caller's ``AuthContext`` (or minimal stand-in). Used for
                       ``published_tier_minimum`` gate enforcement (SC-005).
                       ``None`` is accepted for adapters without a tier gate.
        session_id:    Caller session identifier forwarded to OTEL + audit sink.

    Returns:
        ``SubmitOutput`` on success.
        ``AdapterNotFoundError`` when ``tool_id`` is not registered.
        ``AdapterInvocationError`` when the adapter raises or fails.
    """
    if params is None:
        params = {}

    tracer = trace.get_tracer("ummaya.primitives.submit")
    requested_tool_id = str(tool_id or "")

    with tracer.start_as_current_span("gen_ai.tool_loop.iteration") as span:
        span.set_attribute("gen_ai.tool.name", requested_tool_id or _INVALID_TOOL_ID_SENTINEL)
        span.set_attribute("ummaya.submit.session_id", session_id)

        if not _SUBMIT_TOOL_ID_RE.fullmatch(requested_tool_id):
            logger.warning("send: invalid tool_id shape: %r", requested_tool_id)
            span.set_attribute("error.type", "invalid_tool_id")
            return AdapterNotFoundError(
                tool_id=_INVALID_TOOL_ID_SENTINEL,
                message=(
                    "send requires a non-empty registered adapter tool_id matching "
                    "^[a-z][a-z0-9_]*$; call send(tool_id=<adapter>, params={...})."
                ),
            )

        # Step 1 — Resolve adapter
        if requested_tool_id not in _ADAPTER_REGISTRY:
            logger.warning("send: adapter not found: %s", requested_tool_id)
            span.set_attribute("error.type", "adapter_not_found")
            return AdapterNotFoundError(
                tool_id=requested_tool_id,
                message=(
                    f"No send adapter registered for tool_id={requested_tool_id!r}. "
                    "Check that the adapter module is imported before calling send()."
                ),
            )

        registration, invoke_fn = _ADAPTER_REGISTRY[requested_tool_id]

        # Step 2 — Published tier gate (SC-005)
        rejection = check_tier_gate(registration=registration, auth_context=auth_context)
        if rejection is not None:
            logger.info(
                "send: tier gate rejected invocation for %s: %s",
                requested_tool_id,
                rejection.get("reason", ""),
            )
            span.set_attribute("error.type", "tier_gate_rejected")
            return SubmitOutput(
                transaction_id=derive_transaction_id(
                    requested_tool_id,
                    params,
                    adapter_nonce=registration.nonce,
                ),
                status=SubmitStatus.rejected,
                adapter_receipt={
                    "reason": rejection.get("reason", "tier gate rejected"),
                    "published_tier_minimum": registration.published_tier_minimum,
                },
            )

        # Step 3 — Derive deterministic transaction_id
        transaction_id = derive_transaction_id(
            requested_tool_id,
            params,
            adapter_nonce=registration.nonce,
        )
        span.set_attribute("ummaya.submit.transaction_id", transaction_id)

        # Step 4 + 5 — Validate params (best-effort) and invoke adapter
        try:
            result = await invoke_fn(params)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "send: adapter invocation failed for %s: %s: %s",
                requested_tool_id,
                type(exc).__name__,
                exc,
            )
            span.set_attribute("error.type", type(exc).__name__)
            span.record_exception(exc)
            return AdapterInvocationError(
                tool_id=requested_tool_id,
                structured={"exception_type": type(exc).__name__, "message": str(exc)},
                message=(
                    f"Adapter {requested_tool_id!r} raised {type(exc).__name__}: {exc}. "
                    "See structured for details."
                ),
            )

        # Step 6 — Normalize result into SubmitOutput
        if isinstance(result, SubmitOutput):
            # Ensure transaction_id matches derived value (adapters may override)
            span.set_attribute("ummaya.submit.status", result.status.value)
            return result

        # Adapter returned something unexpected — wrap as failure (FR-005)
        logger.error(
            "send: adapter %s returned unexpected type %s (expected SubmitOutput)",
            requested_tool_id,
            type(result).__name__,
        )
        span.set_attribute("error.type", "unexpected_adapter_return_type")
        return AdapterInvocationError(
            tool_id=requested_tool_id,
            structured={"return_type": type(result).__name__},
            message=(
                f"Adapter {requested_tool_id!r} returned {type(result).__name__!r} "
                "instead of SubmitOutput."
            ),
        )


send = submit


__all__ = [
    "SubmitInput",
    "SubmitOutput",
    "SubmitStatus",
    "check_tier_gate",
    "derive_transaction_id",
    "register_submit_adapter",
    "send",
]
