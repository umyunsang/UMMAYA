# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from ummaya.tools.errors import ToolNotFoundError
from ummaya.tools.routing.cards import build_adapter_card
from ummaya.tools.routing.decision_types import (
    RouteCandidate,
    RouteDecision,
    SchemaProjectionLevel,
)
from ummaya.tools.routing.feasibility import (
    DEFAULT_SOURCE_MODES,
    hard_exclusion_reasons,
    requires_permission_gate,
    score_breakdown,
    soft_filter_reasons,
)
from ummaya.tools.routing.intent import (
    ToolSelectionIntent,
    extract_tool_selection_intent,
)
from ummaya.tools.routing.retrieval_policy import (
    expand_query_for_intent,
    filter_special_case_scores,
)
from ummaya.tools.routing.schema import sha256
from ummaya.tools.routing.types import AdapterCard, PrimitiveFamily, SourceMode

if TYPE_CHECKING:
    from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class RouteDecisionService:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def decide(
        self,
        query: str,
        *,
        top_k: int = 15,
        max_selected: int = 5,
        initial_scores: Iterable[tuple[str, float]] | None = None,
    ) -> RouteDecision:
        return self.select_adapters(
            query,
            top_k=top_k,
            max_selected=max_selected,
            initial_scores=initial_scores,
            include_infeasible=True,
        )

    def select_adapters(
        self,
        query: str,
        *,
        top_k: int = 5,
        max_selected: int | None = None,
        intent: ToolSelectionIntent | None = None,
        session_identity: object | None = None,
        allowed_source_modes: Sequence[SourceMode] = DEFAULT_SOURCE_MODES,
        allowed_credentials: Sequence[str] | None = None,
        include_infeasible: bool = False,
        initial_scores: Iterable[tuple[str, float]] | None = None,
    ) -> RouteDecision:
        registry_size = len(self._registry)
        effective_top_k = max(1, min(top_k, registry_size, 20)) if registry_size else 0
        route_intent = intent or extract_tool_selection_intent(
            query, known_tool_ids=self._registry._tools.keys()
        )
        if registry_size == 0:
            return self._empty_decision(query, route_intent)

        if initial_scores is None:
            scored, backend_label, degradation_reason = self._score(query, route_intent)
        else:
            scored = sorted(
                filter_special_case_scores(route_intent, list(initial_scores)),
                key=lambda pair: (-pair[1], pair[0]),
            )
            backend_label = "injected"
            degradation_reason = None

        active_cards, card_events = self._active_cards()
        active_tool_ids = frozenset(card.tool_id for card in active_cards)
        active_primitives = frozenset(card.primitive_family for card in active_cards)
        candidates, candidate_events = self._candidate_set(
            scored,
            route_intent=route_intent,
            session_identity=session_identity,
            active_tool_ids=active_tool_ids,
            active_primitives=active_primitives,
            allowed_source_modes=frozenset(allowed_source_modes),
            allowed_credentials=(
                None if allowed_credentials is None else frozenset(allowed_credentials)
            ),
        )
        ranked_candidates = tuple(sorted(candidates, key=_candidate_sort_key))
        selected_candidates = tuple(
            candidate for candidate in ranked_candidates if candidate.feasible
        )
        selection_limit = max_selected if max_selected is not None else effective_top_k
        selected_route_candidates = selected_candidates[:selection_limit]
        selected_tools = tuple(candidate.tool_id for candidate in selected_route_candidates)
        visible_candidates = (ranked_candidates if include_infeasible else selected_candidates)[
            :effective_top_k
        ]

        return RouteDecision(
            decision_id=sha256(
                {
                    "query": query,
                    "selected_tools": selected_tools,
                    "backend_label": backend_label,
                    "degradation_reason": degradation_reason,
                }
            )[:16],
            query_hash=sha256(query),
            manifest_hash=sha256(
                [candidate.card.manifest_hash for candidate in visible_candidates]
            ),
            intent=route_intent,
            candidate_set=visible_candidates,
            selected_tools=selected_tools,
            schema_projection_level=_schema_projection_level(selected_tools),
            backend_label=backend_label,
            effective_top_k=effective_top_k,
            clarification_question=_clarification_question(ranked_candidates, selected_tools),
            permission_gate=any(
                requires_permission_gate(candidate.card, feasible=candidate.feasible)
                for candidate in selected_route_candidates
            ),
            stop_reason=None if selected_tools else "no_feasible_candidate",
            degradation_reason=degradation_reason,
            score_breakdown=_aggregate_score_breakdown(ranked_candidates),
            evidence_events=(*card_events, *candidate_events),
        )

    def _empty_decision(
        self, query: str, intent: ToolSelectionIntent, *, backend_label: str = "retrieval"
    ) -> RouteDecision:
        return RouteDecision(
            decision_id=sha256({"query": query, "selected_tools": ()})[:16],
            query_hash=sha256(query),
            manifest_hash=sha256([]),
            intent=intent,
            candidate_set=(),
            selected_tools=(),
            schema_projection_level="none",
            backend_label=backend_label,
            effective_top_k=0,
            clarification_question=None,
            permission_gate=False,
            stop_reason="no_feasible_candidate",
            degradation_reason=None,
            score_breakdown={"candidate_count": 0.0, "feasible_count": 0.0},
            evidence_events=(),
        )

    def _score(
        self, query: str, intent: ToolSelectionIntent
    ) -> tuple[list[tuple[str, float]], str, str | None]:
        expanded_query = expand_query_for_intent(query, intent)
        retriever = self._registry._retriever
        backend_label = _backend_label(retriever)
        try:
            scored = retriever.score(expanded_query)
            return (
                sorted(
                    filter_special_case_scores(intent, scored), key=lambda pair: (-pair[1], pair[0])
                ),
                backend_label,
                None,
            )
        except Exception as exc:
            logger.warning(
                "route decision: retriever.score failed (%s: %s); "
                "attempting BM25 companion fallback",
                type(exc).__name__,
                exc,
            )
            bm25_companion = getattr(retriever, "_bm25", None)
            if bm25_companion is None:
                return [], backend_label, f"{backend_label}_score_failed_no_bm25"
            try:
                scored = bm25_companion.score(expanded_query)
            except Exception as bm25_exc:
                logger.warning(
                    "route decision: BM25 companion failed (%s: %s); returning empty ranking",
                    type(bm25_exc).__name__,
                    bm25_exc,
                )
                return [], backend_label, "bm25_companion_failed"
            return (
                sorted(
                    filter_special_case_scores(intent, scored), key=lambda pair: (-pair[1], pair[0])
                ),
                "bm25",
                f"{backend_label}_score_failed",
            )

    def _active_cards(self) -> tuple[tuple[AdapterCard, ...], tuple[str, ...]]:
        cards: list[AdapterCard] = []
        events: list[str] = []
        for tool in self._registry.all_tools():
            try:
                cards.append(build_adapter_card(tool))
            except Exception as exc:
                events.append(f"active_card_build_failed:{tool.id}:{type(exc).__name__}")
        return tuple(cards), tuple(events)

    def _candidate_set(
        self,
        scored: Iterable[tuple[str, float]],
        *,
        route_intent: ToolSelectionIntent,
        session_identity: object | None,
        active_tool_ids: frozenset[str],
        active_primitives: frozenset[PrimitiveFamily],
        allowed_source_modes: frozenset[SourceMode],
        allowed_credentials: frozenset[str] | None,
    ) -> tuple[tuple[RouteCandidate, ...], tuple[str, ...]]:
        candidates: list[RouteCandidate] = []
        evidence_events: list[str] = []
        for tool_id, raw_score in scored:
            try:
                card = build_adapter_card(self._registry.find(tool_id))
            except ToolNotFoundError:
                evidence_events.append(f"hard_excluded:missing_registered_tool:{tool_id}")
                continue
            except Exception as exc:
                evidence_events.append(
                    f"hard_excluded:card_build_failed:{tool_id}:{type(exc).__name__}"
                )
                continue

            hard_reasons = hard_exclusion_reasons(
                card,
                active_tool_ids=active_tool_ids,
                allowed_source_modes=allowed_source_modes,
                allowed_credentials=allowed_credentials,
            )
            if hard_reasons:
                for reason in hard_reasons:
                    evidence_events.append(f"hard_excluded:{reason}:{tool_id}")
                continue

            retrieval_score = max(0.0, float(raw_score))
            filter_reasons = soft_filter_reasons(
                card,
                route_intent=route_intent,
                session_identity=session_identity,
                active_tool_ids=active_tool_ids,
                active_primitives=active_primitives,
            )
            candidates.append(
                RouteCandidate(
                    tool_id=tool_id,
                    retrieval_score=retrieval_score,
                    card=card,
                    status="feasible" if not filter_reasons else "infeasible",
                    feasible=not filter_reasons,
                    filter_reasons=filter_reasons,
                    score_breakdown=score_breakdown(card, retrieval_score, filter_reasons),
                )
            )
        return tuple(candidates), tuple(evidence_events)


def _candidate_sort_key(candidate: RouteCandidate) -> tuple[int, float, str]:
    penalty = len(candidate.filter_reasons) * 1000.0
    score = candidate.retrieval_score + candidate.score_breakdown["feasibility"] * 100.0 - penalty
    return (0 if candidate.feasible else 1, -score, candidate.tool_id)


def _schema_projection_level(selected_tools: tuple[str, ...]) -> SchemaProjectionLevel:
    return "summary" if selected_tools else "none"


def _clarification_question(
    candidates: tuple[RouteCandidate, ...], selected_tools: tuple[str, ...]
) -> str | None:
    if not candidates or selected_tools:
        return None
    missing_slots = sorted(
        {
            reason.removeprefix("missing_slot:")
            for candidate in candidates
            for reason in candidate.filter_reasons
            if reason.startswith("missing_slot:")
        }
    )
    if missing_slots:
        return f"Required slot missing: {', '.join(missing_slots)}."
    return None


def _aggregate_score_breakdown(candidates: tuple[RouteCandidate, ...]) -> dict[str, float]:
    if not candidates:
        return {"candidate_count": 0.0, "feasible_count": 0.0}
    feasible_count = sum(1 for candidate in candidates if candidate.feasible)
    return {
        "candidate_count": float(len(candidates)),
        "feasible_count": float(feasible_count),
        "top_retrieval": max(candidate.retrieval_score for candidate in candidates),
    }


def _backend_label(retriever: object) -> str:
    return str(
        getattr(
            retriever,
            "_requested_backend_label",
            type(retriever).__name__.removesuffix("Backend").lower() or "retrieval",
        )
    )
