# SPDX-License-Identifier: Apache-2.0
"""Retriever-based search for the KOSMOS Tool System.

Public API (for external callers):
- ``search(query, bm25_index, registry, top_k)`` — retrieval facade returning
  ``AdapterCandidate`` objects. The ``bm25_index`` parameter is kept for
  backward-compatible signatures (FR-009); the scoring call is routed through
  ``registry._retriever`` (spec 026) so Dense / Hybrid backends are honoured
  without any caller-side change.
- ``search_tools(tools, query, max_results)`` — legacy token-overlap function kept for
  backward compatibility with ``ToolRegistry.search()``; will be removed in a follow-on epic.
- ``create_search_meta_tool()`` — factory for the ``search_tools`` meta-tool definition.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kosmos.tools.bm25_index import BM25Index
from kosmos.tools.models import (
    AdapterCandidate,
    GovAPITool,
    SearchToolsInput,
    SearchToolsOutput,
    ToolSearchResult,
)

if TYPE_CHECKING:
    from kosmos.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def search(
    query: str,
    bm25_index: BM25Index,
    registry: ToolRegistry,
    top_k: int | None = None,
) -> list[AdapterCandidate]:
    """Retrieval-backend-ranked adapter search over the tool registry.

    Spec 026 rewires scoring through ``registry._retriever`` so the active
    backend (bm25 | dense | hybrid) determines the ranking. The
    ``bm25_index`` parameter is kept in the signature for FR-009
    backward compatibility — when the active backend is BM25 it points
    at the same index the retriever wraps; when the backend is Dense or
    Hybrid it is ignored. External signature and contract are unchanged.

    Adaptive top_k clamp (FR-009):
        effective_top_k = max(1, min(top_k if top_k else 5, len(registry), 20))

    Args:
        query: Free-text query in Korean or English.
        bm25_index: Compatibility parameter retained per FR-009; not
            consulted when the registry's active backend is non-BM25.
        registry: The live ToolRegistry to search.
        top_k: Per-call override.  None → use default (5).

    Returns:
        Ranked list of AdapterCandidate entries.
    """
    del bm25_index  # retained for FR-009 signature compat; routing happens via registry._retriever

    registry_size = len(registry)
    default_k = 5
    raw_k = top_k if top_k is not None else default_k
    effective_top_k = max(1, min(raw_k, registry_size, 20))

    if registry_size == 0:
        return []

    retriever = registry._retriever
    try:
        scored = retriever.score(query)
    except Exception as exc:
        # FR-002 fail-open: a mid-session retriever failure (dense OOM,
        # tokenizer crash, encoder corruption) must not surface as a 5xx
        # on the citizen path. The Retriever protocol does not forbid
        # score() from raising, so this is the last defensive boundary
        # before the public ``lookup`` contract. Try the retriever's BM25
        # companion (present on ``_DenseFailOpenWrapper`` and
        # ``HybridBackend``) before falling back to an empty ranking so
        # citizens still see lexical matches when the dense path crashes
        # outside its own catch-blocks.
        logger.warning(
            "search: retriever.score failed (%s: %s) — attempting BM25 companion fallback",
            type(exc).__name__,
            exc,
        )
        bm25_companion = getattr(retriever, "_bm25", None)
        if bm25_companion is None:
            logger.warning(
                "search: no BM25 companion on retriever %s — returning empty ranking",
                type(retriever).__name__,
            )
            return []
        try:
            scored = bm25_companion.score(query)
        except Exception as bm25_exc:
            logger.warning(
                "search: BM25 companion also failed (%s: %s) — returning empty ranking",
                type(bm25_exc).__name__,
                bm25_exc,
            )
            return []

    # Enforce the deterministic tie-break once, here. Backend-internal
    # orderings are not trusted (HybridBackend returns unordered union).
    scored = sorted(scored, key=lambda pair: (-pair[1], pair[0]))

    # Derive the backend label from the active retriever. Prefer the
    # explicit ``_requested_backend_label`` attribute (set on wrappers
    # like ``_DenseFailOpenWrapper`` that report a logical backend name
    # distinct from their Python class name) so ``why_matched`` reflects
    # the operator's configured backend, not an internal wrapper type.
    backend_label = getattr(
        retriever,
        "_requested_backend_label",
        type(retriever).__name__.removesuffix("Backend").lower() or "retrieval",
    )

    results: list[AdapterCandidate] = []
    for tool_id, score in scored[:effective_top_k]:
        try:
            tool = registry.lookup(tool_id)
        except Exception:  # pragma: no cover
            logger.warning("search: tool %r in retriever but not in registry", tool_id)
            continue

        input_schema_json, required_params = _input_schema_export(tool)
        output_schema_json = _output_schema_export(tool)
        candidate = AdapterCandidate(
            tool_id=tool_id,
            score=max(0.0, float(score)),
            required_params=required_params,
            search_hint=tool.search_hint,
            why_matched=f"{backend_label} score {score:.4f} on search_hint",
            input_schema_json=input_schema_json,
            output_schema_json=output_schema_json,
            llm_description=tool.llm_description,
            primitive=tool.primitive,
            real_classification_url=(
                tool.policy.real_classification_url if tool.policy is not None else None
            ),
            adapter_mode=tool.adapter_mode,
            citizen_facing_gate=(
                tool.policy.citizen_facing_gate if tool.policy is not None else None
            ),
            delegation_source_tool_id=tool.delegation_source_tool_id,
        )
        results.append(candidate)

    return results


def _input_schema_export(tool: GovAPITool) -> tuple[dict[str, object], list[str]]:
    """Export the tool's input_schema as a JSON Schema dict + required-fields list.

    Epic ζ #2297 path B — exposes full per-field description / type / pattern /
    examples / ge-le constraints so the LLM can fill params per domain.
    Returns ``({}, [])`` on schema export failure (pure best-effort path).
    """
    try:
        schema = tool.input_schema.model_json_schema()
    except Exception:  # pragma: no cover
        return ({}, [])
    required = list(schema.get("required", []))
    return (schema, required)


def _output_schema_export(tool: GovAPITool) -> dict[str, object]:
    """Export the tool's output_schema as a JSON Schema dict (best-effort)."""
    try:
        return tool.output_schema.model_json_schema()
    except Exception:  # pragma: no cover
        return {}


def _required_params(tool: GovAPITool) -> list[str]:
    """Backward-compatible thin wrapper. Prefer ``_input_schema_export`` when both
    the schema dict and the required list are needed."""
    return _input_schema_export(tool)[1]


# ---------------------------------------------------------------------------
# Legacy token-overlap function — kept for ToolRegistry.search() backward compat
# ---------------------------------------------------------------------------


def search_tools(
    tools: list[GovAPITool],
    query: str,
    max_results: int = 5,
) -> list[ToolSearchResult]:
    """Search tools by Korean or English keywords in search_hint.

    Legacy token-overlap algorithm retained for ToolRegistry.search() backward
    compatibility.  New code should use ``search()`` instead.

    Algorithm:
    1. Tokenize query into lowercase tokens (split by whitespace).
    2. If query is empty or only whitespace, return empty list.
    3. For each tool, tokenize its search_hint into lowercase tokens.
    4. Score = number of query tokens that are bidirectionally substring-matched
       against any search_hint token (case-insensitive, either token may contain
       the other).
    5. If score > 0, include in results.
    6. Sort by score descending.
    7. Return top max_results.

    Args:
        tools: All registered tool definitions to search over.
        query: Freeform Korean or English search string.
        max_results: Maximum number of results to return.

    Returns:
        Ranked list of :class:`ToolSearchResult` with score > 0,
        capped at *max_results* entries.
    """
    if max_results <= 0:
        return []

    query_stripped = query.strip()
    if not query_stripped:
        return []

    query_tokens = query_stripped.lower().split()
    total_query_tokens = len(query_tokens)

    results: list[ToolSearchResult] = []

    for tool in tools:
        hint_tokens = tool.search_hint.lower().split()

        matched: list[str] = []
        for q_token in query_tokens:
            # Bidirectional substring match: either token contains the other.
            if any(q_token in h_token or h_token in q_token for h_token in hint_tokens):
                matched.append(q_token)

        if matched:
            score = len(matched) / total_query_tokens
            results.append(
                ToolSearchResult(
                    tool=tool,
                    score=score,
                    matched_tokens=matched,
                )
            )

    results.sort(key=lambda r: (-r.score, r.tool.id))
    return results[:max_results]


def create_search_meta_tool() -> GovAPITool:
    """Create the search_tools meta-tool for LLM discovery.

    This tool is registered in the ToolRegistry so the LLM can discover
    other tools via the search_tools function call.
    """
    return GovAPITool(
        id="search_tools",
        name_ko="도구검색",
        ministry="KOSMOS",
        category=["시스템", "검색"],
        endpoint="internal://search_tools",
        auth_type="public",
        input_schema=SearchToolsInput,
        output_schema=SearchToolsOutput,
        search_hint="도구 검색 찾기 search tools find discover 도구목록",
        # Meta-tool; internal KOSMOS harness surface.
        is_concurrency_safe=True,
        cache_ttl_seconds=0,
        rate_limit_per_minute=60,
        is_core=True,
    )
