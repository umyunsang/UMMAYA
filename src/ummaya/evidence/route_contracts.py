# SPDX-License-Identifier: Apache-2.0
"""Route trace and route-selection contract builders."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from ummaya.evidence.dataset_contract import Scenario, ScenarioDataset
from ummaya.evidence.models import RouteSelectionAssertion, RouteTraceRecord
from ummaya.evidence.route_helpers import (
    adapter_family_for_scenario,
    argument_feasibility_for_scenario,
    correlation_id,
    coverage_tags_for_scenario,
    failure_recovery_for_stop_reason,
    prompt_manifest_hash,
    stop_reason_for_scenario,
    tool_catalog_hash,
)
from ummaya.tools.routing.decision_types import RouteStopReason
from ummaya.tools.routing.schema import sha256


def route_trace_records(dataset: ScenarioDataset) -> tuple[RouteTraceRecord, ...]:
    """Build route traces from scenario contracts without selecting concrete tools."""
    records: list[RouteTraceRecord] = []
    prompt_hash = prompt_manifest_hash(dataset)
    catalog_hash = tool_catalog_hash(dataset)
    for scenario in dataset.scenarios:
        records.append(_scenario_route_trace(scenario, prompt_hash, catalog_hash))
    records.extend(_negative_control_route_records(prompt_hash, catalog_hash))
    return tuple(records)


def route_selection_assertions(
    dataset: ScenarioDataset,
    records: Sequence[RouteTraceRecord],
) -> tuple[RouteSelectionAssertion, ...]:
    """Build route-selection assertions from trace records."""
    scenarios_by_id = {scenario.id: scenario for scenario in dataset.scenarios}
    assertions: list[RouteSelectionAssertion] = []
    for record in records:
        if record.trace_kind == "negative_control":
            assertions.append(_negative_control_assertion(record))
            continue
        scenario = scenarios_by_id[record.scenario_id]
        expected_primitives = tuple(step.primitive for step in scenario.expected_ax_chain)
        status: Literal["pass", "fail"] = (
            "pass"
            if scenario.lifecycle_domain == record.selected_domain
            and expected_primitives == record.selected_primitives
            and not record.selected_tools
            else "fail"
        )
        assertions.append(_route_assertion(scenario, record, expected_primitives, status))
    return tuple(assertions)


def _scenario_route_trace(
    scenario: Scenario,
    prompt_hash: str,
    catalog_hash: str,
) -> RouteTraceRecord:
    selected_primitives = tuple(step.primitive for step in scenario.expected_ax_chain)
    stop_reason = stop_reason_for_scenario(scenario)
    trace_id = f"route-{scenario.id.lower()}"
    corr_id = correlation_id(trace_id)
    return RouteTraceRecord(
        trace_kind="scenario_route",
        route_source="expected_route_contract",
        scenario_id=scenario.id,
        trace_id=trace_id,
        correlation_id=corr_id,
        query_hash=sha256(scenario.request_ko),
        manifest_hash=sha256(
            {
                "correlation_id": corr_id,
                "scenario_id": scenario.id,
                "selected_domain": scenario.lifecycle_domain,
                "selected_primitives": selected_primitives,
                "stop_reason": stop_reason,
                "trace_kind": "scenario_route",
                "route_source": "expected_route_contract",
            }
        ),
        prompt_manifest_hash=prompt_hash,
        tool_catalog_hash=catalog_hash,
        selected_domain=scenario.lifecycle_domain,
        selected_primitives=selected_primitives,
        clarification_reason=None,
        stop_reason=stop_reason,
        evidence_events=("evidence_fabric.route_trace.contract", f"route_stop:{stop_reason}"),
    )


def _negative_control_route_records(
    prompt_hash: str,
    catalog_hash: str,
) -> tuple[RouteTraceRecord, ...]:
    controls: tuple[tuple[str, str, RouteStopReason, str], ...] = (
        (
            "NEG-DIRECT-ANSWER-001",
            "Explain the difference between a public notice and a civil petition "
            "without taking action.",
            "answerable",
            "negative_control:direct_answer",
        ),
        (
            "NEG-NO-ADAPTER-001",
            "Change a closed internal agency review score that has no public callable channel.",
            "blocked_no_adapter",
            "negative_control:no_adapter",
        ),
    )
    return tuple(
        _negative_control_route_trace(
            scenario_id, query, stop_reason, event, prompt_hash, catalog_hash
        )
        for scenario_id, query, stop_reason, event in controls
    )


def _negative_control_route_trace(
    scenario_id: str,
    query: str,
    stop_reason: RouteStopReason,
    event: str,
    prompt_hash: str,
    catalog_hash: str,
) -> RouteTraceRecord:
    trace_id = f"route-{scenario_id.lower()}"
    corr_id = correlation_id(trace_id)
    return RouteTraceRecord(
        trace_kind="negative_control",
        route_source="expected_route_contract",
        scenario_id=scenario_id,
        trace_id=trace_id,
        correlation_id=corr_id,
        query_hash=sha256(query),
        manifest_hash=sha256(
            {
                "correlation_id": corr_id,
                "scenario_id": scenario_id,
                "selected_domain": "general_information",
                "selected_primitives": (),
                "stop_reason": stop_reason,
                "trace_kind": "negative_control",
                "route_source": "expected_route_contract",
            }
        ),
        prompt_manifest_hash=prompt_hash,
        tool_catalog_hash=catalog_hash,
        selected_domain="general_information",
        selected_primitives=(),
        selected_tools=(),
        clarification_reason=None,
        stop_reason=stop_reason,
        evidence_events=(event, f"route_stop:{stop_reason}"),
    )


def _negative_control_assertion(record: RouteTraceRecord) -> RouteSelectionAssertion:
    return RouteSelectionAssertion(
        assertion_kind="negative_control",
        route_source=record.route_source,
        status="pass",
        scenario_id=record.scenario_id,
        trace_id=record.trace_id,
        correlation_id=record.correlation_id,
        prompt_manifest_hash=record.prompt_manifest_hash,
        tool_catalog_hash=record.tool_catalog_hash,
        expected_domain="general_information",
        selected_domain="general_information",
        expected_primitives=(),
        selected_primitives=(),
        adapter_family="no_tool",
        argument_feasibility="sufficient" if record.stop_reason == "answerable" else "blocked",
        clarification_expected=False,
        clarification_reason=None,
        stop_reason=record.stop_reason,
        failure_recovery=failure_recovery_for_stop_reason(record.stop_reason),
        coverage_tags=("negative_control",),
        selected_tool_ids=(),
        assertion_events=(
            "route_assertion:negative_control",
            "route_assertion:no_internal_tool_id",
        ),
    )


def _route_assertion(
    scenario: Scenario,
    record: RouteTraceRecord,
    expected_primitives: tuple[str, ...],
    status: Literal["pass", "fail"],
) -> RouteSelectionAssertion:
    return RouteSelectionAssertion(
        assertion_kind="scenario_route",
        route_source=record.route_source,
        status=status,
        scenario_id=scenario.id,
        trace_id=record.trace_id,
        correlation_id=record.correlation_id,
        prompt_manifest_hash=record.prompt_manifest_hash,
        tool_catalog_hash=record.tool_catalog_hash,
        expected_domain=scenario.lifecycle_domain,
        selected_domain=record.selected_domain,
        expected_primitives=expected_primitives,
        selected_primitives=record.selected_primitives,
        adapter_family=adapter_family_for_scenario(scenario, record.selected_primitives),
        argument_feasibility=argument_feasibility_for_scenario(scenario),
        clarification_expected=record.stop_reason == "needs_input",
        clarification_reason=record.clarification_reason,
        stop_reason=record.stop_reason,
        failure_recovery=failure_recovery_for_stop_reason(record.stop_reason),
        coverage_tags=coverage_tags_for_scenario(scenario, record.selected_primitives),
        selected_tool_ids=(),
        assertion_events=(
            "route_assertion:domain_match",
            "route_assertion:primitive_match",
            "route_assertion:no_internal_tool_id",
        ),
    )
