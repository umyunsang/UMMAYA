# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Sequence

from ummaya.tools.routing.intent import ACTIVE_PRIMITIVES, ToolSelectionIntent
from ummaya.tools.routing.lint import lint_adapter_card
from ummaya.tools.routing.types import AdapterCard, PrimitiveFamily, SourceMode

DEFAULT_SOURCE_MODES: tuple[SourceMode, ...] = ("live", "mock")
SIDE_EFFECT_LEVELS = frozenset({"login", "action", "sign", "send", "verify"})
PERMISSION_CONTEXT_LEVELS = frozenset({"action", "sign", "send", "verify"})


def hard_exclusion_reasons(
    card: AdapterCard,
    *,
    active_tool_ids: frozenset[str],
    allowed_source_modes: frozenset[SourceMode],
    allowed_credentials: frozenset[str] | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if card.tool_id not in active_tool_ids:
        reasons.append("inactive_adapter")
    if card.source_mode not in allowed_source_modes:
        reasons.append(f"disallowed_source_mode:{card.source_mode}")
    if allowed_credentials is not None:
        missing_credentials = [
            requirement
            for requirement in card.credential_requirements
            if requirement not in allowed_credentials
        ]
        reasons.extend(f"disallowed_credential:{credential}" for credential in missing_credentials)
    return tuple(dict.fromkeys(reasons))


def soft_filter_reasons(
    card: AdapterCard,
    *,
    route_intent: ToolSelectionIntent,
    session_identity: object | None,
    active_tool_ids: frozenset[str],
    active_primitives: frozenset[PrimitiveFamily],
) -> tuple[str, ...]:
    reasons: list[str] = []
    reasons.extend(
        f"adapter_card_quality:{violation.code}" for violation in lint_adapter_card(card)
    )
    reasons.extend(_missing_slot_reasons(card.required_slots, route_intent.missing_slots))
    reasons.extend(_permission_reasons(card, route_intent, session_identity))
    reasons.extend(_prerequisite_reasons(card, active_tool_ids, active_primitives))
    return tuple(dict.fromkeys(reasons))


def score_breakdown(
    card: AdapterCard,
    retrieval_score: float,
    filter_reasons: tuple[str, ...],
) -> dict[str, float]:
    return {
        "retrieval": retrieval_score,
        "feasibility": 1.0 if not filter_reasons else 0.0,
        "source_mode": 1.0 if card.source_mode in {"live", "mock"} else 0.0,
        "permission": 0.0 if any("permission" in reason for reason in filter_reasons) else 1.0,
        "prerequisite": 0.0 if any("prerequisite" in reason for reason in filter_reasons) else 1.0,
        "quality": 0.0
        if any("adapter_card_quality" in reason for reason in filter_reasons)
        else 1.0,
    }


def requires_permission_gate(card: AdapterCard, *, feasible: bool) -> bool:
    return feasible and card.side_effect_level in SIDE_EFFECT_LEVELS


def source_modes(value: Sequence[SourceMode]) -> frozenset[SourceMode]:
    return frozenset(value)


def _missing_slot_reasons(
    required_slots: tuple[str, ...],
    intent_missing_slots: tuple[str, ...],
) -> tuple[str, ...]:
    missing = frozenset(intent_missing_slots)
    return tuple(f"missing_slot:{slot}" for slot in required_slots if slot in missing)


def _permission_reasons(
    card: AdapterCard,
    intent: ToolSelectionIntent,
    session_identity: object | None,
) -> tuple[str, ...]:
    if card.side_effect_level not in SIDE_EFFECT_LEVELS:
        return ()
    reasons: list[str] = []
    if card.policy_authority_url is None:
        reasons.append("missing_policy_citation")
    if (
        card.side_effect_level in PERMISSION_CONTEXT_LEVELS
        and not intent.requires_permission
        and session_identity is None
    ):
        reasons.append("permission_context_missing")
    return tuple(reasons)


def _prerequisite_reasons(
    card: AdapterCard,
    active_tool_ids: frozenset[str],
    active_primitives: frozenset[PrimitiveFamily],
) -> tuple[str, ...]:
    reasons: list[str] = []
    primitive_names = frozenset((*ACTIVE_PRIMITIVES, "document"))
    for prerequisite in card.prerequisite_tools:
        if prerequisite in primitive_names:
            if prerequisite not in active_primitives:
                reasons.append(f"missing_prerequisite_primitive:{prerequisite}")
            continue
        if prerequisite not in active_tool_ids:
            reasons.append(f"missing_prerequisite_tool:{prerequisite}")
    return tuple(reasons)
