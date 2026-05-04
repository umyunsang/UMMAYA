# SPDX-License-Identifier: Apache-2.0
"""lookup facade coroutine — T024.

Single entry point for adapter discovery (search) and invocation (fetch).

FR-004: Dispatches on ``LookupInput.mode`` discriminator.
FR-005: search → BM25 retrieval gate via ``kosmos.tools.search.search()``.
FR-006: fetch → typed adapter invocation via ``executor.invoke()``.
FR-009: top_k adaptive clamp [1, 20], default from KOSMOS_LOOKUP_TOPK.
"""

from __future__ import annotations

import logging
import uuid

from opentelemetry import trace

from kosmos.tools.errors import LookupErrorReason
from kosmos.tools.models import (
    LookupCollection,
    LookupError,  # noqa: A004
    LookupFetchInput,
    LookupRecord,
    LookupSearchInput,
    LookupSearchResult,
    LookupTimeseries,
)

logger = logging.getLogger(__name__)


async def lookup(
    inp: LookupSearchInput | LookupFetchInput,
    *,
    registry: object | None = None,
    executor: object | None = None,
    session_identity: str | None = None,
) -> LookupSearchResult | LookupRecord | LookupCollection | LookupTimeseries | LookupError:
    """Dispatch a lookup call by mode.

    Args:
        inp: Validated LookupSearchInput or LookupFetchInput.
        registry: ToolRegistry instance (required for search mode).
        executor: ToolExecutor instance (required for fetch mode).
        session_identity: Caller identity token.  None = unauthenticated.
            Forwarded to executor.invoke() to enable the Layer 3 auth gate.

    Returns:
        One of the 5 LookupOutput variants.
    """
    if isinstance(inp, LookupSearchInput):
        return await _lookup_search(inp, registry=registry)
    else:
        return await _lookup_fetch(inp, executor=executor, session_identity=session_identity)


async def _lookup_search(
    inp: LookupSearchInput,
    *,
    registry: object | None = None,
) -> LookupSearchResult:
    """Handle search mode: BM25 retrieval gate over adapter registry.

    FR-005, FR-009.
    """
    from kosmos.tools.registry import ToolRegistry
    from kosmos.tools.search import search

    if registry is None or not isinstance(registry, ToolRegistry):
        logger.warning("lookup search: no valid registry provided, returning empty")
        return LookupSearchResult(
            kind="search",
            candidates=[],
            total_registry_size=0,
            effective_top_k=0,
            reason="empty_registry",
        )

    registry_size = len(registry)

    if registry_size == 0:
        return LookupSearchResult(
            kind="search",
            candidates=[],
            total_registry_size=0,
            effective_top_k=0,
            reason="empty_registry",
        )

    # Compute effective top_k with adaptive clamp (FR-009)
    from kosmos.settings import settings

    default_k = settings.lookup_topk  # from KOSMOS_LOOKUP_TOPK
    raw_k = inp.top_k if inp.top_k is not None else default_k
    effective_top_k = max(1, min(raw_k, registry_size, 20))

    candidates = search(
        query=inp.query,
        bm25_index=registry.bm25_index,
        registry=registry,
        top_k=effective_top_k,
    )

    # Optional domain filter: filter candidates by category tag
    if inp.domain is not None:
        domain_lower = inp.domain.lower()
        filtered = []
        for candidate in candidates:
            try:
                tool = registry.lookup(candidate.tool_id)
                if any(domain_lower in cat.lower() for cat in tool.category):
                    filtered.append(candidate)
            except Exception:
                filtered.append(candidate)
        candidates = filtered

    return LookupSearchResult(
        kind="search",
        candidates=candidates,
        total_registry_size=registry_size,
        effective_top_k=effective_top_k,
        reason="ok",
    )


async def _lookup_fetch(
    inp: LookupFetchInput,
    *,
    executor: object | None = None,
    session_identity: str | None = None,
) -> LookupRecord | LookupCollection | LookupTimeseries | LookupError:
    """Handle fetch mode: typed adapter invocation via executor.

    FR-006, FR-017. Unknown tool_id → LookupError(reason="unknown_tool").
    Layer 3 gate and envelope normalization are handled inside executor.invoke().
    """
    from kosmos.tools.executor import ToolExecutor

    if executor is None or not isinstance(executor, ToolExecutor):
        return LookupError(
            kind="error",
            reason=LookupErrorReason.unknown_tool,
            message=f"No executor available to invoke tool {inp.tool_id!r}.",
            retryable=False,
        )

    # SWAP/llm-provider(2521): resolve_location bypass.
    # resolve_location's 6-variant ResolveLocationOutput union (CoordResult /
    # AdmCodeResult / AddressResult / POIResult / ResolveBundle / ResolveError)
    # does NOT match ToolExecutor.invoke()'s 5-variant LookupOutput envelope
    # contract — handing it to executor.invoke() makes envelope.normalize()
    # raise EnvelopeNormalizationError → "Response processing failed". The
    # mvp_surface.py docstring already declared this: "These tools are NOT
    # bound to executor adapters — their invocation is handled directly by
    # the KOSMOS orchestrator loop". Citizen-visible symptom without this
    # bypass: 7-turn lookup() spam ending in two unrelated upstream errors
    # because the LLM never gets a usable lat/lon back (probe-traced
    # 2026-05-01). Returning a LookupRecord wraps the bundle so the existing
    # LookupOutput consumers stay unchanged; the bundle's typed fields
    # (coords.lat / coords.lon / adm_cd) are preserved inside record.fields.
    if inp.tool_id == "resolve_location":
        from datetime import datetime  # noqa: PLC0415
        from zoneinfo import ZoneInfo  # noqa: PLC0415

        # KOSMOS canonical citizen-facing timezone (Asia/Seoul). Internal
        # OTEL/audit/IPC paths keep UTC; only envelope-visible stamps switch.
        seoul_tz = ZoneInfo("Asia/Seoul")

        from kosmos.tools.models import (
            LookupMeta,
            LookupRecord,
            ResolveError,
        )
        from kosmos.tools.models import (
            ResolveLocationInput as _ResolveLocationInput,
        )
        from kosmos.tools.resolve_location import resolve_location as _resolve_fn

        try:
            resolve_inp = _ResolveLocationInput.model_validate(inp.params or {})
        except Exception as exc:
            return LookupError(
                kind="error",
                reason=LookupErrorReason.invalid_params,
                message=f"resolve_location: input validation failed: {exc}",
                retryable=False,
            )
        try:
            resolve_result = await _resolve_fn(resolve_inp)
        except Exception as exc:
            return LookupError(
                kind="error",
                reason=LookupErrorReason.upstream_unavailable,
                message=f"resolve_location: {type(exc).__name__}: {exc}",
                retryable=False,
            )

        if isinstance(resolve_result, ResolveError):
            return LookupError(
                kind="error",
                reason=LookupErrorReason.upstream_unavailable,
                message=f"resolve_location: {resolve_result.message}",
                retryable=False,
            )

        # Wrap the typed ResolveLocationOutput into a LookupRecord so the
        # downstream agentic-loop code path (which expects a LookupOutput
        # variant) keeps working. The original bundle is in record.fields.
        return LookupRecord(
            kind="record",
            item=resolve_result.model_dump(),
            meta=LookupMeta(
                source="resolve_location",
                fetched_at=datetime.now(tz=seoul_tz),
                request_id=str(uuid.uuid4()),
                elapsed_ms=0,
            ),
        )

    request_id = str(uuid.uuid4())

    # FR-018: annotate the current execute_tool span with kosmos.tool.adapter
    # for fetch mode only.  search mode and resolve_location MUST NOT carry this
    # attribute.  Use get_current_span() — no new span is created.
    current_span = trace.get_current_span()
    current_span.set_attribute("kosmos.tool.adapter", inp.tool_id)

    result = await executor.invoke(
        tool_id=inp.tool_id,
        params=inp.params,
        request_id=request_id,
        session_identity=session_identity,
    )

    # executor.invoke() always returns a LookupOutput variant — pass through
    return result  # type: ignore[return-value]
