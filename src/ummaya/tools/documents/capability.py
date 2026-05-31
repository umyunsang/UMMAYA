# SPDX-License-Identifier: Apache-2.0
"""Capability promotion gates for Public AX document format engines."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ummaya.tools.documents.scorecard import CapabilityScorecard

DocumentFormat = Literal["hwpx", "hwp", "docx", "xlsx", "pptx", "pdf"]
CapabilityOperation = Literal["read", "write", "style", "render", "validate"]
PromotionOperation = Literal["read", "write"]
PromotionDecisionState = Literal["promoted", "deferred", "rejected"]
PromotionReason = Literal[
    "read_threshold_met",
    "write_threshold_met",
    "unsupported_operation",
    "critical_security_finding",
    "security_gates_failed",
    "score_below_read_threshold",
    "score_below_write_threshold",
    "write_hard_gates_failed",
    "hwp_write_blocked",
]

READ_PROMOTION_THRESHOLD: Final[int] = 75
WRITE_PROMOTION_THRESHOLD: Final[int] = 85


class FormatCapabilityProfile(BaseModel):
    """Declared capability surface for one candidate document engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: DocumentFormat
    engine_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    supported_operations: tuple[CapabilityOperation, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("supported_operations")
    @classmethod
    def _supported_operations_are_unique(
        cls,
        operations: tuple[CapabilityOperation, ...],
    ) -> tuple[CapabilityOperation, ...]:
        if len(set(operations)) != len(operations):
            raise ValueError("supported_operations must be unique")
        return operations


class PromotionDecision(BaseModel):
    """Machine-readable decision returned by the capability promotion loop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: DocumentFormat
    engine_id: str
    operation: PromotionOperation
    score: int
    required_score: int
    promoted: bool
    reasons: tuple[PromotionReason, ...]


class PromotionDecisionRecord(BaseModel):
    """Persisted promotion, deferral, or rejection decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: DocumentFormat
    engine_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    operation: PromotionOperation
    decision_state: PromotionDecisionState
    score: int = Field(ge=0, le=100)
    required_score: int = Field(ge=0, le=100)
    reasons: tuple[str, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    decision_note: str = Field(min_length=1)


class PromotionDecisionManifest(BaseModel):
    """Persistent manifest of candidate promotion decisions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1]
    run_id: str = Field(min_length=1)
    source_policy: Literal["offline_fixtures_only"]
    live_network_allowed: Literal[False]
    decisions: tuple[PromotionDecisionRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_unique_decisions(self) -> PromotionDecisionManifest:
        keys = [
            (decision.format, decision.engine_id, decision.operation) for decision in self.decisions
        ]
        if len(set(keys)) != len(keys):
            raise ValueError(
                "promotion decision records must be unique per format/engine/operation"
            )
        return self


def build_inspection_read_profile(
    *,
    document_format: DocumentFormat,
    engine_id: str,
    evidence_ref: str,
) -> FormatCapabilityProfile:
    """Build the read-only profile emitted after inspection fixture evidence."""
    return FormatCapabilityProfile(
        format=document_format,
        engine_id=engine_id,
        supported_operations=("read",),
        evidence_refs=(evidence_ref,),
    )


def persist_promotion_decision_manifest(
    manifest: PromotionDecisionManifest,
    path: Path,
) -> None:
    """Persist promotion decisions as deterministic local JSON."""
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def load_promotion_decision_manifest(path: Path) -> PromotionDecisionManifest:
    """Load persisted promotion decisions from deterministic local JSON."""
    return PromotionDecisionManifest.model_validate_json(
        path.expanduser().resolve().read_text(encoding="utf-8")
    )


def evaluate_capability_promotion(
    profile: FormatCapabilityProfile,
    operation: PromotionOperation,
    scorecard: CapabilityScorecard,
) -> PromotionDecision:
    """Apply score thresholds and hard gates before exposing a capability."""
    required_score = READ_PROMOTION_THRESHOLD if operation == "read" else WRITE_PROMOTION_THRESHOLD

    blocked = _global_blocker(profile, operation, scorecard, required_score)
    if blocked is not None:
        return blocked

    reasons = (
        _read_blocking_reasons(scorecard)
        if operation == "read"
        else _write_blocking_reasons(scorecard)
    )
    if reasons:
        return _decision(
            profile=profile,
            operation=operation,
            score=scorecard.total_score,
            required_score=required_score,
            promoted=False,
            reasons=reasons,
        )

    success_reason: PromotionReason = (
        "read_threshold_met" if operation == "read" else "write_threshold_met"
    )
    return _decision(
        profile=profile,
        operation=operation,
        score=scorecard.total_score,
        required_score=required_score,
        promoted=True,
        reasons=(success_reason,),
    )


def _global_blocker(
    profile: FormatCapabilityProfile,
    operation: PromotionOperation,
    scorecard: CapabilityScorecard,
    required_score: int,
) -> PromotionDecision | None:
    if scorecard.critical_security_findings:
        reasons: tuple[PromotionReason, ...] = ("critical_security_finding",)
    elif operation == "write" and profile.format == "hwp":
        reasons = ("hwp_write_blocked",)
    elif operation not in profile.supported_operations:
        reasons = ("unsupported_operation",)
    else:
        return None

    return _decision(
        profile=profile,
        operation=operation,
        score=scorecard.total_score,
        required_score=required_score,
        promoted=False,
        reasons=reasons,
    )


def _read_blocking_reasons(scorecard: CapabilityScorecard) -> tuple[PromotionReason, ...]:
    reasons: list[PromotionReason] = []
    if not scorecard.security_gate_passed:
        reasons.append("security_gates_failed")
    if scorecard.total_score < READ_PROMOTION_THRESHOLD:
        reasons.append("score_below_read_threshold")
    return tuple(reasons)


def _write_blocking_reasons(scorecard: CapabilityScorecard) -> tuple[PromotionReason, ...]:
    reasons: list[PromotionReason] = []
    if not scorecard.security_gate_passed:
        reasons.append("security_gates_failed")
    if not scorecard.write_hard_gates_passed:
        reasons.append("write_hard_gates_failed")
    if scorecard.total_score < WRITE_PROMOTION_THRESHOLD:
        reasons.append("score_below_write_threshold")
    return tuple(reasons)


def _decision(
    *,
    profile: FormatCapabilityProfile,
    operation: PromotionOperation,
    score: int,
    required_score: int,
    promoted: bool,
    reasons: tuple[PromotionReason, ...],
) -> PromotionDecision:
    return PromotionDecision(
        format=profile.format,
        engine_id=profile.engine_id,
        operation=operation,
        score=score,
        required_score=required_score,
        promoted=promoted,
        reasons=reasons,
    )
