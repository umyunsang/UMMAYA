# SPDX-License-Identifier: Apache-2.0
"""Dependency and license gate tests for document candidate promotion."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ummaya.tools.documents.evaluation import (
    CandidateProfile,
    evaluate_candidate_profiles,
    load_candidate_profiles,
)

_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "documents"


def test_dependency_and_license_gates_block_runtime_promotion() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    run = evaluate_candidate_profiles(profiles)

    pyhwp = _find(run.decisions, engine_id="pyhwp-read-only", operation="read")
    rhwp = _find(run.decisions, engine_id="rhwp", operation="write")

    assert pyhwp.promoted is False
    assert "license_gate_failed" in pyhwp.reasons
    assert pyhwp.license_gate_passed is False
    assert pyhwp.dependency_gate_passed is True

    assert rhwp.promoted is False
    assert "dependency_gate_failed" in rhwp.reasons
    assert rhwp.dependency_gate_passed is False
    assert rhwp.license_gate_passed is True


def test_candidate_profile_requires_fixture_evidence_for_supported_operations() -> None:
    raw = {
        "format": "pdf",
        "engine_id": "pypdf",
        "supported_operations": ["read"],
        "evaluate_operations": ["read"],
        "license": {
            "spdx": "BSD-3-Clause",
            "gate": "pass",
            "notes": "Permissive license.",
        },
        "dependency": {
            "runtime_dependency": False,
            "gate": "pass",
            "notes": "Already available as a candidate only.",
        },
        "scorecard": {
            "extraction_fidelity": 20,
            "write_fidelity": 0,
            "style_layout_control": 10,
            "deterministic_round_trip": 15,
            "public_form_validation": 15,
            "security_privacy": 10,
            "license_maintenance_tool_usability": 5,
        },
        "evidence_refs": [],
        "decision_note": "Missing evidence should fail closed.",
    }

    with pytest.raises(ValidationError, match="evidence_refs must not be empty"):
        CandidateProfile.model_validate(raw)


def test_candidate_profile_rejects_live_network_dependency_evidence() -> None:
    raw = {
        "format": "docx",
        "engine_id": "python-docx",
        "supported_operations": ["read"],
        "evaluate_operations": ["read"],
        "license": {
            "spdx": "MIT",
            "gate": "pass",
            "notes": "Permissive license.",
        },
        "dependency": {
            "runtime_dependency": False,
            "gate": "pass",
            "notes": "Candidate only.",
        },
        "scorecard": {
            "extraction_fidelity": 20,
            "write_fidelity": 0,
            "style_layout_control": 10,
            "deterministic_round_trip": 15,
            "public_form_validation": 15,
            "security_privacy": 10,
            "license_maintenance_tool_usability": 5,
        },
        "evidence_refs": ["live:data.go.kr:15000591"],
        "decision_note": "Live evidence is not allowed in CI.",
    }

    with pytest.raises(ValidationError, match="live evidence refs are forbidden"):
        CandidateProfile.model_validate(raw)


def _find(decisions, *, engine_id: str, operation: str):
    matches = [
        decision
        for decision in decisions
        if decision.engine_id == engine_id and decision.operation == operation
    ]
    assert len(matches) == 1
    return matches[0]
