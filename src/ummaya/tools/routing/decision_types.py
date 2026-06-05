# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.routing.intent import ToolSelectionIntent
from ummaya.tools.routing.types import AdapterCard

SchemaProjectionLevel = Literal["none", "name_only", "summary", "full_schema"]
FeasibilityStatus = Literal["feasible", "infeasible"]
RouteStopReason = Literal[
    "answerable",
    "needs_input",
    "permission_required",
    "handoff_required",
    "blocked_no_adapter",
    "blocked_no_credential",
    "max_turns",
    "repeated_tool_mismatch",
    "no_new_evidence",
    "runtime_tool_failure_unrecovered",
]
RouteClarificationReason = Literal[
    "missing_slots",
    "equal_candidates",
    "side_effect_confirmation",
    "execution_risk_input_fault",
]


class RouteCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(min_length=1)
    retrieval_score: float = Field(ge=0)
    card: AdapterCard
    status: FeasibilityStatus
    feasible: bool
    filter_reasons: tuple[str, ...]
    score_breakdown: dict[str, float]


class RouteClarificationDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: RouteClarificationReason
    question: str = Field(min_length=1, max_length=240)
    missing_slots: tuple[str, ...] = Field(default_factory=tuple)
    candidate_tool_ids: tuple[str, ...] = Field(default_factory=tuple)
    evidence_events: tuple[str, ...] = Field(default_factory=tuple)


class RouteDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(min_length=1)
    query_hash: str = Field(min_length=64, max_length=64)
    manifest_hash: str = Field(min_length=64, max_length=64)
    intent: ToolSelectionIntent
    candidate_set: tuple[RouteCandidate, ...]
    selected_tools: tuple[str, ...]
    schema_projection_level: SchemaProjectionLevel
    backend_label: str = Field(min_length=1)
    effective_top_k: int = Field(ge=0, le=20)
    clarification: RouteClarificationDecision | None
    clarification_question: str | None
    permission_gate: bool
    stop_reason: RouteStopReason
    degradation_reason: str | None
    score_breakdown: dict[str, float]
    evidence_events: tuple[str, ...]
