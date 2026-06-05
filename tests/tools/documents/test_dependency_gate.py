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


def test_hwp_bridge_candidates_require_adr_and_document_permission_boundary() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    hwp_read = next(
        profile for profile in profiles.profiles if profile.engine_id == "OpenHWP-read-only"
    )
    hwp_convert = next(
        profile for profile in profiles.profiles if profile.engine_id == "HwpForge-hwp5-to-hwpx"
    )

    for profile in (hwp_read, hwp_convert):
        assert profile.dependency.gate == "defer"
        assert profile.dependency.requires_adr is True
        assert profile.dependency.adr_ref == "docs/adr/ADR-011-hwp-conversion-bridge.md"
        assert profile.dependency.permission_boundary == "document_primitive_only"
        assert profile.dependency.local_only_execution is True
        assert profile.dependency.package_ref
        assert "adr:docs/adr/ADR-011-hwp-conversion-bridge.md" in profile.evidence_refs

    assert hwp_convert.dependency.package_ref == (
        "git:https://github.com/ai-screams/HwpForge.git#v0.6.0:crates/hwpforge-bindings-cli"
    )
    assert "upstream:hwpforge-cli-v0.6.0-convert-hwp5" in hwp_convert.evidence_refs


def test_promoted_hwp_read_dependency_stays_local_and_document_scoped() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    unhwp_read = next(
        profile for profile in profiles.profiles if profile.engine_id == "unhwp-read-only"
    )

    assert unhwp_read.dependency.gate == "pass"
    assert unhwp_read.dependency.requires_adr is True
    assert unhwp_read.dependency.adr_ref == "docs/adr/ADR-011-hwp-conversion-bridge.md"
    assert unhwp_read.dependency.permission_boundary == "document_primitive_only"
    assert unhwp_read.dependency.local_only_execution is True
    assert unhwp_read.dependency.package_ref == "pypi:unhwp>=0.5.0,<0.6"
    assert "adr:docs/adr/ADR-011-hwp-conversion-bridge.md" in unhwp_read.evidence_refs


def test_candidate_profile_requires_adr_for_passed_runtime_bridge_gate() -> None:
    raw = {
        "format": "hwp",
        "engine_id": "HwpForge-hwp5-to-hwpx",
        "supported_operations": ["read", "convert"],
        "evaluate_operations": ["convert"],
        "license": {
            "spdx": "MIT OR Apache-2.0",
            "gate": "pass",
            "notes": "Permissive license.",
        },
        "dependency": {
            "runtime_dependency": True,
            "gate": "pass",
            "notes": "Missing ADR must fail closed.",
            "requires_adr": True,
            "permission_boundary": "document_primitive_only",
            "local_only_execution": True,
            "package_ref": "npm:@hwpforge/mcp@0.5.2",
        },
        "scorecard": {
            "extraction_fidelity": 18,
            "write_fidelity": 18,
            "style_layout_control": 14,
            "deterministic_round_trip": 13,
            "public_form_validation": 14,
            "security_privacy": 10,
            "license_maintenance_tool_usability": 5,
        },
        "evidence_refs": ["fixture:hwp-to-hwpx-derivative-lineage"],
        "decision_note": "Missing ADR should fail closed.",
    }

    with pytest.raises(ValidationError, match="requires_adr dependency gates require adr_ref"):
        CandidateProfile.model_validate(raw)


def test_candidate_profile_rejects_remote_runtime_bridge_dependency() -> None:
    raw = {
        "format": "hwp",
        "engine_id": "RemoteHwpConverter",
        "supported_operations": ["read", "convert"],
        "evaluate_operations": ["convert"],
        "license": {
            "spdx": "MIT",
            "gate": "pass",
            "notes": "Permissive license.",
        },
        "dependency": {
            "runtime_dependency": True,
            "gate": "pass",
            "notes": "Remote conversion must fail closed.",
            "requires_adr": True,
            "adr_ref": "docs/adr/ADR-011-hwp-conversion-bridge.md",
            "permission_boundary": "document_primitive_only",
            "local_only_execution": False,
            "package_ref": "remote:https://converter.example",
        },
        "scorecard": {
            "extraction_fidelity": 18,
            "write_fidelity": 18,
            "style_layout_control": 14,
            "deterministic_round_trip": 13,
            "public_form_validation": 14,
            "security_privacy": 10,
            "license_maintenance_tool_usability": 5,
        },
        "evidence_refs": ["fixture:hwp-to-hwpx-derivative-lineage"],
        "decision_note": "Remote conversion should fail closed.",
    }

    with pytest.raises(ValidationError, match="local_only_execution must be true"):
        CandidateProfile.model_validate(raw)


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
