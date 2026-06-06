# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.routing import RouteDecision, RouteStopReason, SchemaProjectionLevel


class RouteDecisionDiagnosticPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    turn_index: int = Field(ge=1)
    session_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    query_hash: str = Field(min_length=64, max_length=64)
    manifest_hash: str = Field(min_length=64, max_length=64)
    backend_label: str = Field(min_length=1)
    selected_tools: tuple[str, ...]
    candidate_count: int = Field(ge=0)
    effective_top_k: int = Field(ge=0)
    schema_projection_level: SchemaProjectionLevel
    stop_reason: RouteStopReason
    permission_gate: bool
    clarification_reason: (
        Literal[
            "missing_slots",
            "equal_candidates",
            "side_effect_confirmation",
            "execution_risk_input_fault",
        ]
        | None
    )
    evidence_events: tuple[str, ...]


def log_route_decision_diagnostic(
    *,
    logger: logging.Logger,
    turn_index: int,
    session_id: str,
    correlation_id: str,
    decision: RouteDecision | None,
) -> None:
    if decision is None:
        return
    clarification_reason = None if decision.clarification is None else decision.clarification.reason
    payload = RouteDecisionDiagnosticPayload(
        turn_index=turn_index,
        session_id=session_id,
        correlation_id=correlation_id,
        decision_id=decision.decision_id,
        query_hash=decision.query_hash,
        manifest_hash=decision.manifest_hash,
        backend_label=decision.backend_label,
        selected_tools=decision.selected_tools,
        candidate_count=len(decision.candidate_set),
        effective_top_k=decision.effective_top_k,
        schema_projection_level=decision.schema_projection_level,
        stop_reason=decision.stop_reason,
        permission_gate=decision.permission_gate,
        clarification_reason=clarification_reason,
        evidence_events=decision.evidence_events,
    )
    logger.info(
        "[ROUTE_DECISION] payload=%s",
        json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
    )
