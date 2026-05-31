# SPDX-License-Identifier: Apache-2.0
"""Capability promotion scorecard tests for the Public AX document harness."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ummaya.tools.documents.capability import (
    FormatCapabilityProfile,
    build_inspection_read_profile,
    evaluate_capability_promotion,
)
from ummaya.tools.documents.scorecard import (
    SCORECARD_WEIGHTS,
    CapabilityScorecard,
)


def _perfect_scorecard() -> CapabilityScorecard:
    return CapabilityScorecard(
        extraction_fidelity=20,
        write_fidelity=20,
        style_layout_control=15,
        deterministic_round_trip=15,
        public_form_validation=15,
        security_privacy=10,
        license_maintenance_tool_usability=5,
    )


def test_scorecard_weights_match_public_ax_research_loop() -> None:
    assert SCORECARD_WEIGHTS == {
        "extraction_fidelity": 20,
        "write_fidelity": 20,
        "style_layout_control": 15,
        "deterministic_round_trip": 15,
        "public_form_validation": 15,
        "security_privacy": 10,
        "license_maintenance_tool_usability": 5,
    }
    assert sum(SCORECARD_WEIGHTS.values()) == 100


def test_scorecard_is_closed_and_bounded_by_dimension_weights() -> None:
    assert CapabilityScorecard.model_json_schema()["additionalProperties"] is False
    assert _perfect_scorecard().total_score == 100

    with pytest.raises(ValidationError):
        CapabilityScorecard(
            extraction_fidelity=21,
            write_fidelity=20,
            style_layout_control=15,
            deterministic_round_trip=15,
            public_form_validation=15,
            security_privacy=10,
            license_maintenance_tool_usability=5,
        )


def test_read_promotion_requires_threshold_and_security_hard_gates() -> None:
    profile = FormatCapabilityProfile(
        format="pdf",
        engine_id="pypdf",
        supported_operations=("read",),
    )
    passing_read_score = CapabilityScorecard(
        extraction_fidelity=20,
        write_fidelity=0,
        style_layout_control=10,
        deterministic_round_trip=15,
        public_form_validation=15,
        security_privacy=10,
        license_maintenance_tool_usability=5,
    )

    promoted = evaluate_capability_promotion(profile, "read", passing_read_score)

    assert passing_read_score.total_score == 75
    assert promoted.promoted is True
    assert promoted.required_score == 75
    assert promoted.reasons == ("read_threshold_met",)

    blocked = evaluate_capability_promotion(
        profile,
        "read",
        passing_read_score.model_copy(update={"security_gate_passed": False}),
    )

    assert blocked.promoted is False
    assert "security_gates_failed" in blocked.reasons


def test_critical_security_finding_blocks_read_and_write_regardless_of_score() -> None:
    profile = FormatCapabilityProfile(
        format="docx",
        engine_id="python-docx",
        supported_operations=("read", "write"),
    )
    unsafe_score = _perfect_scorecard().model_copy(
        update={"critical_security_findings": ("active macro payload",)}
    )

    read_decision = evaluate_capability_promotion(profile, "read", unsafe_score)
    write_decision = evaluate_capability_promotion(profile, "write", unsafe_score)

    assert read_decision.promoted is False
    assert write_decision.promoted is False
    assert read_decision.reasons == ("critical_security_finding",)
    assert write_decision.reasons == ("critical_security_finding",)


def test_write_promotion_requires_85_points_and_write_hard_gates() -> None:
    profile = FormatCapabilityProfile(
        format="hwpx",
        engine_id="python-hwpx",
        supported_operations=("read", "write"),
    )
    passing_write_score = CapabilityScorecard(
        extraction_fidelity=20,
        write_fidelity=20,
        style_layout_control=15,
        deterministic_round_trip=15,
        public_form_validation=0,
        security_privacy=10,
        license_maintenance_tool_usability=5,
    )

    promoted = evaluate_capability_promotion(profile, "write", passing_write_score)

    assert passing_write_score.total_score == 85
    assert promoted.promoted is True
    assert promoted.required_score == 85
    assert promoted.reasons == ("write_threshold_met",)

    below_threshold = evaluate_capability_promotion(
        profile,
        "write",
        passing_write_score.model_copy(update={"license_maintenance_tool_usability": 4}),
    )
    missing_hard_gate = evaluate_capability_promotion(
        profile,
        "write",
        passing_write_score.model_copy(update={"write_hard_gates_passed": False}),
    )

    assert below_threshold.promoted is False
    assert "score_below_write_threshold" in below_threshold.reasons
    assert missing_hard_gate.promoted is False
    assert "write_hard_gates_failed" in missing_hard_gate.reasons


def test_hwp_binary_write_is_always_blocked() -> None:
    profile = FormatCapabilityProfile(
        format="hwp",
        engine_id="pyhwp",
        supported_operations=("read", "write"),
    )

    decision = evaluate_capability_promotion(profile, "write", _perfect_scorecard())

    assert decision.promoted is False
    assert decision.reasons == ("hwp_write_blocked",)


def test_inspection_read_profile_registers_engine_without_write_claims() -> None:
    profile = build_inspection_read_profile(
        document_format="hwpx",
        engine_id="python-hwpx",
        evidence_ref="fixture:public-form-hwpx",
    )

    assert profile.format == "hwpx"
    assert profile.engine_id == "python-hwpx"
    assert profile.supported_operations == ("read",)
    assert profile.evidence_refs == ("fixture:public-form-hwpx",)

    decision = evaluate_capability_promotion(
        profile,
        "write",
        _perfect_scorecard(),
    )

    assert decision.promoted is False
    assert decision.reasons == ("unsupported_operation",)
