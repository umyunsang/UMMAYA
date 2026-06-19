# SPDX-License-Identifier: Apache-2.0
"""Small route-classification helpers for Evidence Fabric contracts."""

from __future__ import annotations

from collections.abc import Sequence

from ummaya.evidence.dataset_contract import Scenario, ScenarioDataset
from ummaya.evidence.models import (
    RouteAdapterFamily,
    RouteArgumentFeasibility,
    RouteFailureRecovery,
)
from ummaya.tools.routing.decision_types import RouteStopReason
from ummaya.tools.routing.schema import sha256, unique


def stop_reason_for_scenario(scenario: Scenario) -> RouteStopReason:
    """Return the expected stop reason for a static scenario contract."""
    return (
        "permission_required"
        if scenario.permission_requirements.user_confirmations
        else "answerable"
    )


def argument_feasibility_for_scenario(scenario: Scenario) -> RouteArgumentFeasibility:
    """Classify whether the scenario carries enough arguments for dispatch."""
    if not scenario.request_ko.strip() or not scenario.expected_ax_chain:
        return "blocked"
    return "sufficient"


def failure_recovery_for_stop_reason(stop_reason: RouteStopReason) -> RouteFailureRecovery:
    """Map a route stop reason to the Evidence Fabric recovery family."""
    if stop_reason == "permission_required":
        return "permission_gate"
    if stop_reason == "needs_input":
        return "clarification"
    if stop_reason == "handoff_required":
        return "handoff"
    if stop_reason.startswith("blocked_") or stop_reason in {
        "max_turns",
        "repeated_tool_mismatch",
        "no_new_evidence",
        "runtime_tool_failure_unrecovered",
    }:
        return "blocked"
    return "not_required"


def adapter_family_for_scenario(
    scenario: Scenario,
    selected_primitives: Sequence[str],
) -> RouteAdapterFamily:
    """Classify the expected adapter family without exposing concrete tool IDs."""
    text = scenario_text(scenario)
    if "procurement" in text or "bid" in text or "나라장터" in text:
        return "procurement_channel"
    if scenario.lifecycle_domain == "public_data" or "public data" in text or "공공데이터" in text:
        return "public_data_channel"
    if "aed" in text or "defibrillator" in text or "automated external" in text:
        return "safety_channel"
    if "aviation" in text or "airport" in text or "flight" in text or "weather" in text:
        return "weather_channel"
    if scenario.lifecycle_domain == "safety":
        return "safety_channel"
    if "resolve_location" in selected_primitives:
        return "location_channel"
    return "public_service_channel"


def coverage_tags_for_scenario(
    scenario: Scenario,
    selected_primitives: Sequence[str],
) -> tuple[str, ...]:
    """Build Evidence Fabric coverage tags from scenario text and primitives."""
    text = scenario_text(scenario)
    tags = [f"domain:{scenario.lifecycle_domain}"]
    if "document" in text:
        tags.append("document_harness")
    if "aviation" in text or "airport" in text or "flight" in text:
        tags.append("aviation_weather")
    if "aed" in text or "defibrillator" in text or "automated external" in text:
        tags.append("aed_safety")
    if "procurement" in text or "bid" in text or "나라장터" in text:
        tags.append("procurement")
    if scenario.lifecycle_domain == "public_data" or "public data" in text or "공공데이터" in text:
        tags.append("public_data_search")
    if "resolve_location" in selected_primitives:
        tags.append("location")
    if {"verify", "submit", "subscribe"} & set(selected_primitives):
        tags.append("side_effecting_government_request")
    return tuple(unique(tags))


def scenario_text(scenario: Scenario) -> str:
    """Flatten scenario text fields for deterministic route-family classification."""
    parts = [
        scenario.lifecycle_domain,
        scenario.request_ko,
        scenario.request_en or "",
        *scenario.agencies_or_infrastructure,
        *scenario.citizen_intent_verbs,
        *scenario.expected_system_behavior,
        *scenario.evaluation_focus,
        *(step.primitive for step in scenario.expected_ax_chain),
        *(step.purpose for step in scenario.expected_ax_chain),
    ]
    return " ".join(parts).lower()


def prompt_manifest_hash(dataset: ScenarioDataset) -> str:
    """Hash prompt-facing dataset metadata."""
    return sha256(
        {
            "allowed_primitives": dataset.allowed_primitives,
            "dataset_id": dataset.dataset_id,
            "source_basis": dataset.source_basis,
            "target_system": dataset.target_system,
            "version": dataset.version,
        }
    )


def tool_catalog_hash(dataset: ScenarioDataset) -> str:
    """Hash the abstract adapter-family catalog implied by the dataset."""
    return sha256(
        {
            "adapter_families": tuple(
                sorted(
                    {
                        adapter_family_for_scenario(
                            scenario,
                            tuple(step.primitive for step in scenario.expected_ax_chain),
                        )
                        for scenario in dataset.scenarios
                    }
                )
            ),
            "coverage_domains": dataset.coverage_domains,
            "dataset_id": dataset.dataset_id,
            "scenario_count": len(dataset.scenarios),
        }
    )


def correlation_id(trace_id: str) -> str:
    """Build the deterministic route correlation id used by Evidence Fabric."""
    return f"corr-route-{sha256(trace_id)[:16]}"
