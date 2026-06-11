# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

RhwpHardGateFailure = Literal[
    "license_unverified",
    "api_surface_unverified",
    "artifact_size_unverified",
    "local_only_execution_unverified",
    "hwp_write_capability_unverified",
    "sanitized_hwp_round_trip_missing",
    "render_comparison_missing",
]
RhwpPromotionState = Literal["blocked", "ready_for_fixture_round_trip"]

_PERMISSIVE_LICENSES: Final[frozenset[str]] = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "MIT OR Apache-2.0",
        "Apache-2.0 OR MIT",
    }
)
_MAX_REVIEWED_ARTIFACT_SIZE_BYTES: Final[int] = 25 * 1024 * 1024
_GATE_SCORES: Final[dict[RhwpHardGateFailure, int]] = {
    "license_unverified": 10,
    "api_surface_unverified": 15,
    "artifact_size_unverified": 10,
    "local_only_execution_unverified": 20,
    "hwp_write_capability_unverified": 15,
    "sanitized_hwp_round_trip_missing": 20,
    "render_comparison_missing": 10,
}
_GATE_MESSAGES: Final[dict[RhwpHardGateFailure, str]] = {
    "license_unverified": "license evidence is missing or not permissive",
    "api_surface_unverified": "local API surface evidence is missing",
    "artifact_size_unverified": "reviewed artifact size evidence is missing",
    "local_only_execution_unverified": "local-only execution evidence is missing",
    "hwp_write_capability_unverified": "HWP write capability evidence is missing",
    "sanitized_hwp_round_trip_missing": "sanitized HWP round-trip fixture evidence is missing",
    "render_comparison_missing": "render comparison evidence is missing",
}


class RhwpCandidateEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    license_spdx: str | None = None
    package_ref: str | None = Field(default=None, min_length=1)
    artifact_size_bytes: int | None = Field(default=None, ge=1)
    local_only_execution: bool | None = None
    api_surface_refs: tuple[str, ...] = Field(default_factory=tuple)
    supports_hwp_read: bool = True
    supports_hwp_write: bool = True
    supports_hwpx_read: bool = True
    supports_hwpx_write: bool = True
    sanitized_hwp_round_trip_fixture_refs: tuple[str, ...] = Field(default_factory=tuple)
    render_comparison_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_refs: tuple[str, ...] = Field(min_length=1)
    known_risk_refs: tuple[str, ...] = Field(default_factory=tuple)


class RhwpCandidateEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    engine_id: Literal["rhwp-direct-hwp"]
    version: str
    promotion_state: RhwpPromotionState
    write_enabled: bool
    total_score: int = Field(ge=0, le=100)
    required_score: Literal[100]
    hard_gate_failures: tuple[RhwpHardGateFailure, ...]
    user_facing_summary: str
    source_refs: tuple[str, ...]
    known_risk_refs: tuple[str, ...]


def evaluate_rhwp_candidate(evidence: RhwpCandidateEvidence) -> RhwpCandidateEvaluation:
    failures = _hard_gate_failures(evidence)
    total_score = 100 - sum(_GATE_SCORES[failure] for failure in failures)
    write_enabled = not failures
    promotion_state: RhwpPromotionState = (
        "ready_for_fixture_round_trip" if write_enabled else "blocked"
    )
    return RhwpCandidateEvaluation(
        engine_id="rhwp-direct-hwp",
        version=evidence.version,
        promotion_state=promotion_state,
        write_enabled=write_enabled,
        total_score=total_score,
        required_score=100,
        hard_gate_failures=failures,
        user_facing_summary=_user_facing_summary(failures),
        source_refs=evidence.source_refs,
        known_risk_refs=evidence.known_risk_refs,
    )


def build_hwp_direct_write_candidate_result(
    evidence: RhwpCandidateEvidence,
) -> RhwpCandidateEvaluation:
    return evaluate_rhwp_candidate(evidence)


def _hard_gate_failures(
    evidence: RhwpCandidateEvidence,
) -> tuple[RhwpHardGateFailure, ...]:
    failures: list[RhwpHardGateFailure] = []
    if evidence.license_spdx not in _PERMISSIVE_LICENSES:
        failures.append("license_unverified")
    if not evidence.api_surface_refs:
        failures.append("api_surface_unverified")
    if not _artifact_size_is_reviewed(evidence.artifact_size_bytes):
        failures.append("artifact_size_unverified")
    if evidence.local_only_execution is not True:
        failures.append("local_only_execution_unverified")
    if not (evidence.supports_hwp_read and evidence.supports_hwp_write):
        failures.append("hwp_write_capability_unverified")
    if not evidence.sanitized_hwp_round_trip_fixture_refs:
        failures.append("sanitized_hwp_round_trip_missing")
    if not evidence.render_comparison_refs:
        failures.append("render_comparison_missing")
    return tuple(failures)


def _artifact_size_is_reviewed(size: int | None) -> bool:
    return size is not None and 0 < size <= _MAX_REVIEWED_ARTIFACT_SIZE_BYTES


def _user_facing_summary(failures: tuple[RhwpHardGateFailure, ...]) -> str:
    if not failures:
        return (
            "Direct HWP binary writing is ready for promotion evidence review; "
            "the candidate must still run through the document primitive fixture suite."
        )
    reasons = "; ".join(_GATE_MESSAGES[failure] for failure in failures)
    return f"Direct HWP binary writing remains blocked because {reasons}."
