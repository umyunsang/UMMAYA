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


def test_openpyxl_write_profile_is_promoted_for_default_runtime() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    run = evaluate_candidate_profiles(profiles)

    xlsx_write = next(
        decision
        for decision in run.decisions
        if decision.format == "xlsx"
        and decision.engine_id == "openpyxl"
        and decision.operation == "write"
    )
    assert xlsx_write.promoted is True
    assert xlsx_write.score >= xlsx_write.required_score
    assert xlsx_write.license_gate_passed is True
    assert xlsx_write.dependency_gate_passed is True


def test_python_pptx_write_profile_is_promoted_for_default_runtime() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    run = evaluate_candidate_profiles(profiles)

    pptx_write = next(
        decision
        for decision in run.decisions
        if decision.format == "pptx"
        and decision.engine_id == "python-pptx"
        and decision.operation == "write"
    )
    assert pptx_write.promoted is True
    assert pptx_write.score >= pptx_write.required_score
    assert pptx_write.license_gate_passed is True
    assert pptx_write.dependency_gate_passed is True


def test_pypdf_acroform_write_profile_is_promoted_for_default_runtime() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    run = evaluate_candidate_profiles(profiles)

    pdf_write = next(
        decision
        for decision in run.decisions
        if decision.format == "pdf"
        and decision.engine_id == "pypdf-acroform"
        and decision.operation == "write"
    )
    assert pdf_write.promoted is True
    assert pdf_write.score >= pdf_write.required_score
    assert pdf_write.license_gate_passed is True
    assert pdf_write.dependency_gate_passed is True
