# SPDX-License-Identifier: Apache-2.0
"""Candidate-engine evaluation loop for the Public AX document harness."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ummaya.tools.documents.capability import (
    CapabilityOperation,
    DocumentFormat,
    FormatCapabilityProfile,
    PromotionOperation,
    evaluate_capability_promotion,
)
from ummaya.tools.documents.scorecard import CapabilityScorecard

GateState = Literal["pass", "fail", "defer"]
DependencyReason = Literal[
    "dependency_gate_failed",
    "license_gate_failed",
]
CandidateDecisionReason = str
DataGoKrUsageScope = Literal[
    "semantic_structure_evaluation",
    "table_extraction_evaluation",
    "image_reference_evaluation",
    "summary_rewrite_evaluation",
]
SemanticMetricComponent = Literal[
    "paragraph_block_f1",
    "table_cell_f1",
    "image_reference_f1",
    "metadata_exact_match",
]


class CandidateLicenseGate(BaseModel):
    """License review gate for one candidate engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    spdx: str = Field(min_length=1)
    gate: GateState
    notes: str = Field(min_length=1)


class CandidateDependencyGate(BaseModel):
    """Runtime dependency review gate for one candidate engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime_dependency: bool
    gate: GateState
    notes: str = Field(min_length=1)


class CandidateProfile(BaseModel):
    """Fixture-backed candidate profile evaluated by the promotion loop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: DocumentFormat
    engine_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    supported_operations: tuple[CapabilityOperation, ...] = Field(min_length=1)
    evaluate_operations: tuple[PromotionOperation, ...] = Field(min_length=1)
    license: CandidateLicenseGate
    dependency: CandidateDependencyGate
    scorecard: CapabilityScorecard
    evidence_refs: tuple[str, ...]
    decision_note: str = Field(min_length=1)
    operation_notes: dict[PromotionOperation, str] = Field(default_factory=dict)

    @field_validator("supported_operations", "evaluate_operations")
    @classmethod
    def _operations_are_unique(cls, operations: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(operations)) != len(operations):
            raise ValueError("operations must be unique")
        return operations

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_is_offline(cls, evidence_refs: tuple[str, ...]) -> tuple[str, ...]:
        if not evidence_refs:
            raise ValueError("evidence_refs must not be empty")
        if any(ref.startswith("live:") for ref in evidence_refs):
            raise ValueError("live evidence refs are forbidden")
        return evidence_refs


class CandidateProfileManifest(BaseModel):
    """Offline manifest of candidate engine profiles."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1]
    run_id: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    source_policy: Literal["offline_fixtures_only"]
    live_network_allowed: Literal[False]
    profiles: tuple[CandidateProfile, ...] = Field(min_length=1)


class CandidateDecision(BaseModel):
    """One operation-level candidate evaluation decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: DocumentFormat
    engine_id: str
    operation: PromotionOperation
    promoted: bool
    score: int
    required_score: int
    reasons: tuple[CandidateDecisionReason, ...]
    dependency_gate_passed: bool
    license_gate_passed: bool
    decision_note: str
    evidence_refs: tuple[str, ...]


class CandidateEvaluationRun(BaseModel):
    """Result of evaluating every candidate operation in a manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    live_network_allowed: Literal[False]
    decisions: tuple[CandidateDecision, ...]


class DataGoKrMetadataRecord(BaseModel):
    """One offline metadata record for semantic public-document evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    expected_semantic_fields: tuple[str, ...] = Field(min_length=1)
    negative_assertion: str = Field(min_length=1)


class DataGoKrMetadataSnapshot(BaseModel):
    """Offline data.go.kr corpus metadata used as evaluation context only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1]
    snapshot_id: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    source_policy: Literal["offline_metadata_snapshot"]
    live_network_allowed: Literal[False]
    dataset_name: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    redistribution_status: Literal["metadata_only"]
    authoritative_layout_oracle: Literal[False]
    usage_scope: tuple[DataGoKrUsageScope, ...] = Field(min_length=1)
    metric_components: tuple[SemanticMetricComponent, ...] = Field(min_length=1)
    aggregate_threshold: float = Field(ge=0, le=1)
    records: tuple[DataGoKrMetadataRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_macro_average_components(self) -> DataGoKrMetadataSnapshot:
        required: tuple[SemanticMetricComponent, ...] = (
            "paragraph_block_f1",
            "table_cell_f1",
            "image_reference_f1",
            "metadata_exact_match",
        )
        if self.metric_components != required:
            raise ValueError("metric_components must match the FR-037 macro-average order")
        return self


def load_candidate_profiles(path: Path) -> CandidateProfileManifest:
    """Load candidate profiles from an offline YAML fixture."""
    raw = _load_yaml_mapping(path)
    return CandidateProfileManifest.model_validate(raw)


def evaluate_candidate_profiles(
    manifest: CandidateProfileManifest,
) -> CandidateEvaluationRun:
    """Evaluate profile operations through dependency, license, and score gates."""
    decisions: list[CandidateDecision] = []
    for profile in manifest.profiles:
        capability_profile = FormatCapabilityProfile(
            format=profile.format,
            engine_id=profile.engine_id,
            supported_operations=profile.supported_operations,
            evidence_refs=profile.evidence_refs,
        )
        for operation in profile.evaluate_operations:
            promotion = evaluate_capability_promotion(
                capability_profile,
                operation,
                profile.scorecard,
            )
            reasons: list[str] = list(promotion.reasons)
            dependency_gate_passed = profile.dependency.gate == "pass"
            license_gate_passed = profile.license.gate == "pass"
            if not dependency_gate_passed:
                reasons.append("dependency_gate_failed")
            if not license_gate_passed:
                reasons.append("license_gate_failed")

            decisions.append(
                CandidateDecision(
                    format=profile.format,
                    engine_id=profile.engine_id,
                    operation=operation,
                    promoted=promotion.promoted and dependency_gate_passed and license_gate_passed,
                    score=promotion.score,
                    required_score=promotion.required_score,
                    reasons=tuple(reasons),
                    dependency_gate_passed=dependency_gate_passed,
                    license_gate_passed=license_gate_passed,
                    decision_note=profile.operation_notes.get(operation, profile.decision_note),
                    evidence_refs=profile.evidence_refs,
                )
            )
    return CandidateEvaluationRun(
        run_id=manifest.run_id,
        live_network_allowed=manifest.live_network_allowed,
        decisions=tuple(decisions),
    )


def load_data_go_kr_metadata_snapshot(path: Path) -> DataGoKrMetadataSnapshot:
    """Load the offline data.go.kr semantic-evaluation metadata snapshot."""
    raw = _load_yaml_mapping(path)
    return DataGoKrMetadataSnapshot.model_validate(raw)


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML fixture must be an object: {path}")
    return cast(dict[str, object], loaded)
