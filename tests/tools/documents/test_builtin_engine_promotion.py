# SPDX-License-Identifier: Apache-2.0
"""Runtime promotion coverage for built-in document harness engines."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.evaluation import evaluate_candidate_profiles, load_candidate_profiles

_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "documents"


def test_python_docx_read_profile_is_promoted_for_default_runtime() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    run = evaluate_candidate_profiles(profiles)

    docx_read = next(
        decision
        for decision in run.decisions
        if decision.format == "docx"
        and decision.engine_id == "python-docx"
        and decision.operation == "read"
    )
    assert docx_read.promoted is True
    assert docx_read.license_gate_passed is True
    assert docx_read.dependency_gate_passed is True


def test_hwpx_package_text_profile_is_promoted_for_default_runtime() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    run = evaluate_candidate_profiles(profiles)

    hwpx_write = next(
        decision
        for decision in run.decisions
        if decision.format == "hwpx"
        and decision.engine_id == "hwpx-package-text"
        and decision.operation == "write"
    )
    assert hwpx_write.promoted is True
    assert hwpx_write.license_gate_passed is True
    assert hwpx_write.dependency_gate_passed is True
