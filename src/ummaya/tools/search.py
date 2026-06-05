# SPDX-License-Identifier: Apache-2.0
"""Retriever-based search for the UMMAYA Tool System.

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

from ummaya.tools.bm25_index import BM25Index
from ummaya.tools.models import (
    AdapterCandidate,
    GovAPITool,
    SearchToolsInput,
    SearchToolsOutput,
    ToolSearchResult,
)
from ummaya.tools.routing.intent import ToolSelectionIntent, extract_tool_selection_intent
from ummaya.tools.routing.retrieval_policy import (
    expand_query_for_adapter_retrieval as _policy_expand_query_for_adapter_retrieval,
)
from ummaya.tools.routing.retrieval_policy import (
    expand_query_for_intent as _policy_expand_query_for_intent,
)
from ummaya.tools.routing.retrieval_policy import (
    filter_special_case_scores as _policy_filter_special_case_scores,
)
from ummaya.tools.routing.retrieval_policy import (
    is_document_harness_query as _policy_is_document_harness_query,
)

if TYPE_CHECKING:
    from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def is_document_harness_query(query: str) -> bool:
    return _policy_is_document_harness_query(query)


def _expand_query_for_adapter_retrieval(query: str) -> str:
    return _policy_expand_query_for_adapter_retrieval(query)


def _expand_query_for_intent(query: str, intent: ToolSelectionIntent) -> str:
    return _policy_expand_query_for_intent(query, intent)


def _filter_special_case_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    return _policy_filter_special_case_scores(intent, scored)


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

    intent = extract_tool_selection_intent(query, known_tool_ids=registry._tools.keys())

    from ummaya.tools.routing.decision_service import RouteDecisionService

    decision = RouteDecisionService(registry).select_adapters(
        query,
        top_k=effective_top_k,
        max_selected=effective_top_k,
        intent=intent,
    )

    results: list[AdapterCandidate] = []
    for route_candidate in decision.candidate_set:
        tool_id = route_candidate.tool_id
        try:
            tool = registry.find(tool_id)
        except Exception:  # pragma: no cover
            logger.warning("search: tool %r in retriever but not in registry", tool_id)
            continue

        score = route_candidate.retrieval_score
        input_schema_json, required_params = _input_schema_export(tool)
        output_schema_json = _output_schema_export(tool)
        candidate = AdapterCandidate(
            tool_id=tool_id,
            score=max(0.0, float(score)),
            required_params=required_params,
            search_hint=tool.search_hint,
            why_matched=f"{decision.backend_label} score {score:.4f} on search_hint",
            input_schema_json=input_schema_json,
            output_schema_json=output_schema_json,
            llm_description=tool.llm_description,
            primitive=tool.primitive,
            real_classification_url=(
                tool.policy.real_classification_url if tool.policy is not None else None
            ),
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
        ministry="UMMAYA",
        category=["시스템", "검색"],
        endpoint="internal://search_tools",
        auth_type="public",
        input_schema=SearchToolsInput,
        output_schema=SearchToolsOutput,
        search_hint="도구 검색 찾기 search tools find discover 도구목록",
        # Meta-tool; internal UMMAYA harness surface.
        is_concurrency_safe=True,
        cache_ttl_seconds=0,
        rate_limit_per_minute=60,
        is_core=True,
    )
