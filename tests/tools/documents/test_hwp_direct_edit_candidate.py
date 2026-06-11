# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ummaya.tools.documents.hwp_direct_candidate import (
    RhwpCandidateEvidence,
    build_hwp_direct_write_candidate_result,
    evaluate_rhwp_candidate,
)


def test_rhwp_candidate_scorecard_requires_license_api_size_and_local_execution() -> None:
    evaluation = evaluate_rhwp_candidate(
        RhwpCandidateEvidence(
            version="0.7.15",
            license_spdx=None,
            package_ref="github-release:v0.7.15",
            artifact_size_bytes=None,
            local_only_execution=None,
            api_surface_refs=(),
            source_refs=("https://github.com/edwardkim/rhwp",),
            known_risk_refs=(),
        )
    )

    assert evaluation.write_enabled is False
    assert evaluation.hard_gate_failures == (
        "license_unverified",
        "api_surface_unverified",
        "artifact_size_unverified",
        "local_only_execution_unverified",
        "sanitized_hwp_round_trip_missing",
        "render_comparison_missing",
    )
    assert evaluation.promotion_state == "blocked"


def test_hwp_direct_write_stays_blocked_when_rhwp_scorecard_fails() -> None:
    result = build_hwp_direct_write_candidate_result(
        RhwpCandidateEvidence(
            version="0.7.15",
            license_spdx="MIT",
            package_ref="github-release:v0.7.15",
            artifact_size_bytes=4_570_493,
            local_only_execution=True,
            api_surface_refs=(
                "https://github.com/edwardkim/rhwp/blob/main/README_EN.md#npm-packages--use-in-your-web-project",
                "https://github.com/edwardkim/rhwp/blob/main/Cargo.toml",
            ),
            source_refs=(
                "https://github.com/edwardkim/rhwp/blob/main/README_EN.md",
                "https://chromewebstore.google.com/detail/rhwp-hwp-%EB%AC%B8%EC%84%9C-%EB%B7%B0%EC%96%B4-%EC%97%90%EB%94%94%ED%84%B0/pgakpjflombjmehnebnbpnalhegaanag?hl=en",
            ),
            known_risk_refs=(
                "https://github.com/edwardkim/rhwp/issues/1328",
                "https://github.com/edwardkim/rhwp/issues/1370",
            ),
        )
    )

    assert result.write_enabled is False
    assert result.promotion_state == "blocked"
    assert "Direct HWP binary writing remains blocked" in result.user_facing_summary
    assert "sanitized HWP round-trip fixture evidence is missing" in result.user_facing_summary
    assert "render comparison evidence is missing" in result.user_facing_summary
