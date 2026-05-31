# SPDX-License-Identifier: Apache-2.0
"""Candidate evaluation loop tests for the Public AX document harness."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.capability import (
    PromotionDecisionManifest,
    PromotionDecisionRecord,
    load_promotion_decision_manifest,
    persist_promotion_decision_manifest,
)
from ummaya.tools.documents.evaluation import (
    CandidateDecision,
    evaluate_candidate_profiles,
    load_candidate_profiles,
    load_data_go_kr_metadata_snapshot,
)

_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "documents"


def test_candidate_profiles_fixture_drives_promotions_and_rejections() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    run = evaluate_candidate_profiles(profiles)

    assert run.run_id == "public_doc_candidate_profiles_v1"
    assert run.live_network_allowed is False
    assert _decision(run.decisions, "hwpx", "python-hwpx", "write") == CandidateDecision(
        format="hwpx",
        engine_id="python-hwpx",
        operation="write",
        promoted=True,
        score=90,
        required_score=85,
        reasons=("write_threshold_met",),
        dependency_gate_passed=True,
        license_gate_passed=True,
        decision_note="Promote for HWPX derivative writes behind the harness.",
        evidence_refs=(
            "fixture:hwpx-public-form-baseline",
            "metadata:data-go-kr-public-doc-ai-corpus",
        ),
    )
    rejected = _decision(run.decisions, "hwpx", "direct-owpml-oracle", "write")
    assert rejected.promoted is False
    assert rejected.reasons == ("unsupported_operation",)
    assert rejected.decision_note == "Retain as a test oracle only, not a runtime engine."


def test_hwp_read_only_candidate_promotes_read_and_blocks_write() -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")

    run = evaluate_candidate_profiles(profiles)

    read_decision = _decision(run.decisions, "hwp", "OpenHWP-read-only", "read")
    write_decision = _decision(run.decisions, "hwp", "OpenHWP-read-only", "write")

    assert read_decision.promoted is True
    assert read_decision.reasons == ("read_threshold_met",)
    assert write_decision.promoted is False
    assert write_decision.reasons == ("hwp_write_blocked",)
    assert write_decision.decision_note == "Binary HWP direct write remains blocked in this epic."


def test_data_go_kr_metadata_snapshot_is_offline_evaluation_context_only() -> None:
    snapshot = load_data_go_kr_metadata_snapshot(
        _FIXTURE_ROOT / "public_forms" / "data_go_kr_metadata.yaml"
    )

    assert snapshot.live_network_allowed is False
    assert snapshot.authoritative_layout_oracle is False
    assert snapshot.metric_components == (
        "paragraph_block_f1",
        "table_cell_f1",
        "image_reference_f1",
        "metadata_exact_match",
    )
    assert snapshot.aggregate_threshold == 0.85


def test_candidate_promotion_and_deferral_decisions_are_persistable(tmp_path: Path) -> None:
    profiles = load_candidate_profiles(_FIXTURE_ROOT / "candidate_profiles.yaml")
    run = evaluate_candidate_profiles(profiles)
    promoted = _decision(run.decisions, "hwpx", "python-hwpx", "write")
    deferred = _decision(run.decisions, "hwpx", "rhwp", "write")
    manifest = PromotionDecisionManifest(
        version=1,
        run_id=run.run_id,
        source_policy="offline_fixtures_only",
        live_network_allowed=False,
        decisions=(
            PromotionDecisionRecord(
                format=promoted.format,
                engine_id=promoted.engine_id,
                operation=promoted.operation,
                decision_state="promoted",
                score=promoted.score,
                required_score=promoted.required_score,
                reasons=promoted.reasons,
                evidence_refs=promoted.evidence_refs,
                decision_note=promoted.decision_note,
            ),
            PromotionDecisionRecord(
                format=deferred.format,
                engine_id=deferred.engine_id,
                operation=deferred.operation,
                decision_state="deferred",
                score=deferred.score,
                required_score=deferred.required_score,
                reasons=deferred.reasons,
                evidence_refs=deferred.evidence_refs,
                decision_note=deferred.decision_note,
            ),
        ),
    )
    destination = tmp_path / "promotion-decisions.json"

    persist_promotion_decision_manifest(manifest, destination)

    loaded = load_promotion_decision_manifest(destination)
    assert loaded == manifest
    assert {decision.decision_state for decision in loaded.decisions} == {
        "promoted",
        "deferred",
    }


def _decision(
    decisions: tuple[CandidateDecision, ...],
    document_format: str,
    engine_id: str,
    operation: str,
) -> CandidateDecision:
    matches = [
        decision
        for decision in decisions
        if decision.format == document_format
        and decision.engine_id == engine_id
        and decision.operation == operation
    ]
    assert len(matches) == 1
    return matches[0]
