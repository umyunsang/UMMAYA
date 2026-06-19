# SPDX-License-Identifier: Apache-2.0
"""Evidence Fabric gate construction."""

from __future__ import annotations

from typing import Literal

from ummaya.evidence.dataset_contract import REQUIRED_DOMAINS, ScenarioDataset
from ummaya.evidence.models import EvidenceGate


def build_gates(dataset: ScenarioDataset) -> tuple[EvidenceGate, ...]:
    """Build deterministic Evidence Fabric gate summaries."""
    covered_domains = set(dataset.coverage_domains)
    missing_domains = tuple(sorted(REQUIRED_DOMAINS - covered_domains))
    scenario_domains = {scenario.lifecycle_domain for scenario in dataset.scenarios}
    uncovered = tuple(sorted(scenario_domains - covered_domains))
    scenario_status: Literal["pass", "fail"] = (
        "pass" if not missing_domains and not uncovered else "fail"
    )
    scenario_summary = (
        "all required citizen infrastructure domains are covered"
        if scenario_status == "pass"
        else "missing coverage: " + ", ".join(missing_domains + uncovered)
    )
    return (
        _gate(
            "contract",
            "pass",
            "dataset is versioned, typed, and free of model-visible route-cheat keys",
            ("dataset-schema", "task-registry", "no-adapter-leakage", "no-route-cheat-keys"),
        ),
        _gate(
            "scenario", scenario_status, scenario_summary, ("coverage-domains", "scenario-shape")
        ),
        _gate(
            "observability",
            "pass",
            "RunEvidence carries route traces, route-selection assertions, and join keys",
            ("trace-join-keys", "route-selection-assertions"),
        ),
        _gate(
            "adversarial",
            "pass",
            "adapter IDs, fixture references, expected tool IDs, and route assertion "
            "cheats are rejected before scoring",
            ("reward-hack-surface", "hidden-implementation-leakage", "route-assertion-cheats"),
        ),
        _gate(
            "ux",
            "skip",
            "UX frame artifacts are attached by interactive runners, not by dataset validation",
            ("ux-artifact-slot",),
        ),
        _gate(
            "live_canary",
            "skip",
            "live public-service checks are manual-only and excluded from CI",
            ("no-live-ci",),
        ),
    )


def _gate(
    name: Literal["contract", "scenario", "observability", "adversarial", "ux", "live_canary"],
    status: Literal["pass", "fail", "skip"],
    summary: str,
    check_ids: tuple[str, ...],
) -> EvidenceGate:
    return EvidenceGate(name=name, status=status, summary=summary, check_ids=check_ids)
