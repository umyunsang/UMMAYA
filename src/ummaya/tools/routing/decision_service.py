# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from ummaya.tools.errors import ToolNotFoundError
from ummaya.tools.routing.cards import build_adapter_card
from ummaya.tools.routing.decision_types import (
    RouteCandidate,
    RouteClarificationDecision,
    RouteDecision,
    RouteStopReason,
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
        session_identity: object | None = None,
        initial_scores: Iterable[tuple[str, float]] | None = None,
        validation_events: Sequence[str] = (),
    ) -> RouteDecision:
        return self.select_adapters(
            query,
            top_k=top_k,
            max_selected=max_selected,
            session_identity=session_identity,
            initial_scores=initial_scores,
            validation_events=validation_events,
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
        validation_events: Sequence[str] = (),
        drop_zero_score_candidates: bool | None = None,
    ) -> RouteDecision:
        registry_size = len(self._registry)
        effective_top_k = max(1, min(top_k, registry_size, 20)) if registry_size else 0
        route_intent = intent or extract_tool_selection_intent(
            query, known_tool_ids=self._registry._tools.keys()
        )
        if _has_repeated_tool_mismatch(validation_events):
            return self._terminal_decision(
                query,
                route_intent,
                backend_label="validation",
                stop_reason="repeated_tool_mismatch",
                degradation_reason="repeated_tool_mismatch",
                evidence_events=(
                    "termination:repeated_tool_mismatch",
                    *_route_validation_events(validation_events),
                ),
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

        should_drop_zero_score_candidates = (
            _should_drop_zero_score_candidates(scored, route_intent=route_intent)
            if drop_zero_score_candidates is None
            else drop_zero_score_candidates
        )
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
            drop_zero_score_candidates=should_drop_zero_score_candidates,
        )
        ranked_candidates = tuple(sorted(candidates, key=_candidate_sort_key))
        selected_candidates = tuple(
            candidate for candidate in ranked_candidates if candidate.feasible
        )
        selection_limit = max_selected if max_selected is not None else effective_top_k
        selected_slice = selected_candidates[:selection_limit]
        clarification = _clarification_decision(
            ranked_candidates,
            selected_candidates=selected_candidates,
            selected_slice=selected_slice,
            selection_limit=selection_limit,
            session_identity=session_identity,
        )
        selected_route_candidates = () if clarification is not None else selected_slice
        selected_tools = tuple(candidate.tool_id for candidate in selected_route_candidates)
        visible_candidates = (ranked_candidates if include_infeasible else selected_candidates)[
            :effective_top_k
        ]
        permission_gate = any(
            requires_permission_gate(candidate.card, feasible=candidate.feasible)
            for candidate in selected_route_candidates
        )
        stop_reason = _stop_reason(
            selected_route_candidates=selected_route_candidates,
            clarification=clarification,
            permission_gate=permission_gate,
            evidence_events=candidate_events,
        )

        clarification_events = () if clarification is None else clarification.evidence_events

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
            clarification=clarification,
            clarification_question=None if clarification is None else clarification.question,
            permission_gate=permission_gate,
            stop_reason=stop_reason,
            degradation_reason=degradation_reason,
            score_breakdown=_aggregate_score_breakdown(ranked_candidates),
            evidence_events=(*card_events, *candidate_events, *clarification_events),
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
            clarification=None,
            clarification_question=None,
            permission_gate=False,
            stop_reason="blocked_no_adapter",
            degradation_reason=None,
            score_breakdown={"candidate_count": 0.0, "feasible_count": 0.0},
            evidence_events=(),
        )

    def _terminal_decision(
        self,
        query: str,
        intent: ToolSelectionIntent,
        *,
        backend_label: str,
        stop_reason: RouteStopReason,
        degradation_reason: str | None,
        evidence_events: tuple[str, ...],
    ) -> RouteDecision:
        return RouteDecision(
            decision_id=sha256(
                {
                    "query": query,
                    "selected_tools": (),
                    "stop_reason": stop_reason,
                    "backend_label": backend_label,
                }
            )[:16],
            query_hash=sha256(query),
            manifest_hash=sha256([]),
            intent=intent,
            candidate_set=(),
            selected_tools=(),
            schema_projection_level="none",
            backend_label=backend_label,
            effective_top_k=0,
            clarification=None,
            clarification_question=None,
            permission_gate=False,
            stop_reason=stop_reason,
            degradation_reason=degradation_reason,
            score_breakdown={"candidate_count": 0.0, "feasible_count": 0.0},
            evidence_events=evidence_events,
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
        drop_zero_score_candidates: bool,
    ) -> tuple[tuple[RouteCandidate, ...], tuple[str, ...]]:
        candidates: list[RouteCandidate] = []
        evidence_events: list[str] = []
        for tool_id, raw_score in scored:
            retrieval_score = max(0.0, float(raw_score))
            if (
                drop_zero_score_candidates
                and retrieval_score <= 0.0
                and tool_id not in route_intent.explicit_tool_ids
            ):
                evidence_events.append(f"soft_excluded:zero_retrieval_score:{tool_id}")
                continue
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


def _has_repeated_tool_mismatch(validation_events: Sequence[str]) -> bool:
    mismatch_count = sum(1 for event in validation_events if "tool_mismatch" in event)
    return mismatch_count >= 2


def _route_validation_events(validation_events: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"validation_event:{event}" for event in validation_events)


def _should_drop_zero_score_candidates(
    scored: Sequence[tuple[str, float]], *, route_intent: ToolSelectionIntent
) -> bool:
    if route_intent.explicit_tool_ids:
        return False
    if any(float(score) > 0.0 for _tool_id, score in scored):
        return True
    return len(scored) > 1


def _candidate_selection_score(candidate: RouteCandidate) -> float:
    penalty = len(candidate.filter_reasons) * 1000.0
    return candidate.retrieval_score + candidate.score_breakdown["feasibility"] * 100.0 - penalty


def _candidate_sort_key(candidate: RouteCandidate) -> tuple[int, float, str]:
    score = _candidate_selection_score(candidate)
    return (0 if candidate.feasible else 1, -score, candidate.tool_id)


def _schema_projection_level(selected_tools: tuple[str, ...]) -> SchemaProjectionLevel:
    return "summary" if selected_tools else "none"


def _clarification_decision(
    candidates: tuple[RouteCandidate, ...],
    *,
    selected_candidates: tuple[RouteCandidate, ...],
    selected_slice: tuple[RouteCandidate, ...],
    selection_limit: int,
    session_identity: object | None,
) -> RouteClarificationDecision | None:
    if not candidates:
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
        joined_slots = _join_human_readable(tuple(missing_slots))
        return RouteClarificationDecision(
            reason="missing_slots",
            question=f"Which values should I use for {joined_slots}?",
            missing_slots=tuple(missing_slots),
            evidence_events=("clarification:missing_slots",),
        )

    equal_candidates = _equal_top_candidates(selected_candidates, selection_limit)
    if equal_candidates:
        candidate_tool_ids = tuple(candidate.tool_id for candidate in equal_candidates)
        joined_tools = _join_candidate_choices(candidate_tool_ids)
        return RouteClarificationDecision(
            reason="equal_candidates",
            question=f"Which service should I use: {joined_tools}?",
            candidate_tool_ids=candidate_tool_ids,
            evidence_events=("clarification:equal_candidates",),
        )

    top_candidate = candidates[0]
    if "permission_context_missing" in top_candidate.filter_reasons:
        return RouteClarificationDecision(
            reason="side_effect_confirmation",
            question=f"Should I proceed with {top_candidate.tool_id}?",
            candidate_tool_ids=(top_candidate.tool_id,),
            evidence_events=("clarification:side_effect_confirmation",),
        )
    if session_identity is None:
        for candidate in selected_slice:
            if candidate.tool_id != "document" and candidate.card.side_effect_level in {
                "action",
                "sign",
                "send",
                "verify",
            }:
                return RouteClarificationDecision(
                    reason="side_effect_confirmation",
                    question=f"Should I proceed with {candidate.tool_id}?",
                    candidate_tool_ids=(candidate.tool_id,),
                    evidence_events=("clarification:side_effect_confirmation",),
                )

    return None


def _equal_top_candidates(
    selected_candidates: tuple[RouteCandidate, ...], selection_limit: int
) -> tuple[RouteCandidate, ...]:
    if selection_limit != 1 or len(selected_candidates) < 2:
        return ()
    top_score = _candidate_selection_score(selected_candidates[0])
    equal_candidates = tuple(
        candidate
        for candidate in selected_candidates
        if abs(_candidate_selection_score(candidate) - top_score) <= 1e-9
    )
    return equal_candidates if len(equal_candidates) >= 2 else ()


def _stop_reason(
    *,
    selected_route_candidates: tuple[RouteCandidate, ...],
    clarification: RouteClarificationDecision | None,
    permission_gate: bool,
    evidence_events: tuple[str, ...],
) -> RouteStopReason:
    if clarification is not None:
        return "needs_input"
    if permission_gate:
        return "permission_required"
    if selected_route_candidates:
        return "answerable"
    if any("disallowed_credential" in event for event in evidence_events):
        return "blocked_no_credential"
    if any("disallowed_source_mode:internal" in event for event in evidence_events):
        return "handoff_required"
    return "blocked_no_adapter"


def _join_human_readable(values: tuple[str, ...]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _join_candidate_choices(values: tuple[str, ...]) -> str:
    if len(values) <= 1:
        return _join_human_readable(values)
    if len(values) == 2:
        return f"{values[0]} or {values[1]}"
    return f"{', '.join(values[:-1])}, or {values[-1]}"


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
