# SPDX-License-Identifier: Apache-2.0
"""Evidence Fabric v2 dataset runner.

The runner is intentionally local and deterministic. It validates scenario
contracts and emits a typed RunEvidence document without calling live public
service channels, LLM providers, or observability backends.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ummaya.evidence.document_viewer_ux import DocumentViewerUxArtifact
from ummaya.evidence.models import (
    EvidenceGate,
    RouteAdapterFamily,
    RouteArgumentFeasibility,
    RouteFailureRecovery,
    RouteSelectionAssertion,
    RouteTraceRecord,
    RunEvidence,
)
from ummaya.evidence.task_registry import EvidenceDatasetRef, load_task_registry
from ummaya.tools.documents.models import KnownDocumentFormat
from ummaya.tools.routing.decision_types import RouteStopReason
from ummaya.tools.routing.schema import sha256, unique

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SCENARIO_PATH = _REPO_ROOT / "evidence/scenarios/national_ax_citizen_requests_v1.yaml"
_DEFAULT_TASK_REGISTRY_PATH = _REPO_ROOT / "evidence/registry.yaml"
_DEFAULT_DATASET_REF = "ummaya/national-ax-core@local"
_BANNED_MODEL_VISIBLE_KEYS = frozenset(
    {
        "adapter_id",
        "adapter_ids",
        "adapter_family",
        "expected_adapter_id",
        "tool_id",
        "tool_ids",
        "expected_tool_id",
        "expected_tool_ids",
        "expected_adapter_family",
        "expected_route_trace",
        "route_trace",
        "route_selection_assertion",
        "route_selection_assertions",
        "route_adapter_family",
        "selected_adapter_family",
        "selected_adapter_id",
        "selected_tool",
        "selected_tool_id",
        "selected_tool_ids",
        "selected_tools",
        "fixture_refs",
        "fixture_ref",
        "current_adapter_id",
        "assertion_events",
        "assertion_kind",
        "argument_feasibility",
        "clarification_expected",
        "clarification_reason",
        "correlation_id",
        "coverage_tags",
        "evidence_events",
        "expected_domain",
        "expected_primitives",
        "failure_recovery",
        "manifest_hash",
        "prompt_manifest_hash",
        "query_hash",
        "route_source",
        "selected_domain",
        "selected_primitives",
        "status",
        "stop_reason",
        "tool_catalog_hash",
        "trace_id",
        "trace_kind",
    }
)
_REQUIRED_DOMAINS = frozenset(
    {
        "tax",
        "civil_affairs",
        "payments",
        "utilities",
        "identity",
        "welfare",
        "healthcare",
        "housing",
        "mobility",
        "business",
        "labor",
        "education",
        "safety",
        "immigration",
        "legal",
        "personal_data",
        "public_data",
    }
)


class EvidenceContractError(ValueError):
    """Raised when a scenario dataset violates the Evidence Fabric contract."""


class ExpectedStep(BaseModel):
    """One expected public-service loop step in a scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primitive: str
    purpose: str


class PermissionRequirements(BaseModel):
    """Permission requirements attached to a citizen scenario."""

    model_config = ConfigDict(frozen=True, extra="allow")

    identity_assurance: str
    user_confirmations: tuple[str, ...] = Field(default_factory=tuple)
    sensitive_data: tuple[str, ...] = Field(default_factory=tuple)


class Scenario(BaseModel):
    """Minimum scenario shape needed by Evidence Fabric v2."""

    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    priority: str = "P2"
    lifecycle_domain: str
    request_ko: str
    request_en: str | None = None
    agencies_or_infrastructure: tuple[str, ...] = Field(default_factory=tuple)
    citizen_intent_verbs: tuple[str, ...] = Field(default_factory=tuple)
    expected_ax_chain: tuple[ExpectedStep, ...]
    permission_requirements: PermissionRequirements
    expected_system_behavior: tuple[str, ...] = Field(default_factory=tuple)
    evaluation_focus: tuple[str, ...] = Field(default_factory=tuple)


class ScenarioDataset(BaseModel):
    """Versioned citizen-demand scenario dataset."""

    model_config = ConfigDict(frozen=True, extra="allow")

    version: int
    dataset_id: str
    source_basis: str | None = None
    target_system: str | None = None
    allowed_primitives: tuple[str, ...] = Field(default_factory=tuple)
    coverage_domains: tuple[str, ...]
    scenarios: tuple[Scenario, ...]


def _load_yaml_mapping(path: Path) -> Mapping[str, object]:
    if not path.exists():
        raise EvidenceContractError(f"scenario dataset not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise EvidenceContractError(f"scenario dataset must be a mapping: {path}")
    return cast(Mapping[str, object], loaded)


def _find_banned_keys(value: object, path: str = "$") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        hits: list[str] = []
        for key, nested in value.items():
            key_text = str(key)
            nested_path = f"{path}.{key_text}"
            if key_text in _BANNED_MODEL_VISIBLE_KEYS:
                hits.append(nested_path)
            hits.extend(_find_banned_keys(nested, nested_path))
        return tuple(hits)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        hits = []
        for index, nested in enumerate(value):
            hits.extend(_find_banned_keys(nested, f"{path}[{index}]"))
        return tuple(hits)
    return ()


def _parse_dataset(path: Path) -> ScenarioDataset:
    raw = _load_yaml_mapping(path)
    banned = _find_banned_keys(raw)
    if banned:
        raise EvidenceContractError(
            "model-visible scenario dataset contains banned implementation keys: "
            + ", ".join(banned)
        )
    try:
        return ScenarioDataset.model_validate(raw)
    except ValidationError as exc:
        raise EvidenceContractError(str(exc)) from exc


def _gate(
    name: Literal["contract", "scenario", "observability", "adversarial", "ux", "live_canary"],
    status: Literal["pass", "fail", "skip"],
    summary: str,
    check_ids: tuple[str, ...],
) -> EvidenceGate:
    return EvidenceGate(name=name, status=status, summary=summary, check_ids=check_ids)


def _build_gates(dataset: ScenarioDataset) -> tuple[EvidenceGate, ...]:
    covered_domains = set(dataset.coverage_domains)
    missing_domains = tuple(sorted(_REQUIRED_DOMAINS - covered_domains))
    scenario_domains = {scenario.lifecycle_domain for scenario in dataset.scenarios}
    uncovered_scenario_domains = tuple(sorted(scenario_domains - covered_domains))

    scenario_status: Literal["pass", "fail"] = (
        "pass" if not missing_domains and not uncovered_scenario_domains else "fail"
    )
    scenario_summary = (
        "all required citizen infrastructure domains are covered"
        if scenario_status == "pass"
        else "missing coverage: " + ", ".join(missing_domains + uncovered_scenario_domains)
    )

    return (
        _gate(
            "contract",
            "pass",
            "dataset is versioned, typed, and free of model-visible route-cheat keys",
            ("dataset-schema", "task-registry", "no-adapter-leakage", "no-route-cheat-keys"),
        ),
        _gate(
            "scenario",
            scenario_status,
            scenario_summary,
            ("coverage-domains", "scenario-shape"),
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


def _route_trace_records(dataset: ScenarioDataset) -> tuple[RouteTraceRecord, ...]:
    records: list[RouteTraceRecord] = []
    prompt_manifest_hash = _prompt_manifest_hash(dataset)
    tool_catalog_hash = _tool_catalog_hash(dataset)
    for scenario in dataset.scenarios:
        selected_primitives = tuple(step.primitive for step in scenario.expected_ax_chain)
        stop_reason = _stop_reason_for_scenario(scenario)
        trace_id = f"route-{scenario.id.lower()}"
        correlation_id = _correlation_id(trace_id)
        records.append(
            RouteTraceRecord(
                trace_kind="scenario_route",
                route_source="expected_route_contract",
                scenario_id=scenario.id,
                trace_id=trace_id,
                correlation_id=correlation_id,
                query_hash=sha256(scenario.request_ko),
                manifest_hash=sha256(
                    {
                        "correlation_id": correlation_id,
                        "scenario_id": scenario.id,
                        "selected_domain": scenario.lifecycle_domain,
                        "selected_primitives": selected_primitives,
                        "stop_reason": stop_reason,
                        "trace_kind": "scenario_route",
                        "route_source": "expected_route_contract",
                    }
                ),
                prompt_manifest_hash=prompt_manifest_hash,
                tool_catalog_hash=tool_catalog_hash,
                selected_domain=scenario.lifecycle_domain,
                selected_primitives=selected_primitives,
                clarification_reason=None,
                stop_reason=stop_reason,
                evidence_events=(
                    "evidence_fabric.route_trace.contract",
                    f"route_stop:{stop_reason}",
                ),
            )
        )
    records.extend(_negative_control_route_records(prompt_manifest_hash, tool_catalog_hash))
    return tuple(records)


def _route_selection_assertions(
    dataset: ScenarioDataset,
    records: Sequence[RouteTraceRecord],
) -> tuple[RouteSelectionAssertion, ...]:
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
        assertions.append(
            RouteSelectionAssertion(
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
                adapter_family=_adapter_family_for_scenario(scenario, record.selected_primitives),
                argument_feasibility=_argument_feasibility_for_scenario(scenario),
                clarification_expected=record.stop_reason == "needs_input",
                clarification_reason=record.clarification_reason,
                stop_reason=record.stop_reason,
                failure_recovery=_failure_recovery_for_stop_reason(record.stop_reason),
                coverage_tags=_coverage_tags_for_scenario(scenario, record.selected_primitives),
                selected_tool_ids=(),
                assertion_events=(
                    "route_assertion:domain_match",
                    "route_assertion:primitive_match",
                    "route_assertion:no_internal_tool_id",
                ),
            )
        )
    return tuple(assertions)


def _negative_control_route_records(
    prompt_manifest_hash: str,
    tool_catalog_hash: str,
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
    records: list[RouteTraceRecord] = []
    for scenario_id, query, stop_reason, event in controls:
        trace_id = f"route-{scenario_id.lower()}"
        correlation_id = _correlation_id(trace_id)
        records.append(
            RouteTraceRecord(
                trace_kind="negative_control",
                route_source="expected_route_contract",
                scenario_id=scenario_id,
                trace_id=trace_id,
                correlation_id=correlation_id,
                query_hash=sha256(query),
                manifest_hash=sha256(
                    {
                        "correlation_id": correlation_id,
                        "scenario_id": scenario_id,
                        "selected_domain": "general_information",
                        "selected_primitives": (),
                        "stop_reason": stop_reason,
                        "trace_kind": "negative_control",
                        "route_source": "expected_route_contract",
                    }
                ),
                prompt_manifest_hash=prompt_manifest_hash,
                tool_catalog_hash=tool_catalog_hash,
                selected_domain="general_information",
                selected_primitives=(),
                selected_tools=(),
                clarification_reason=None,
                stop_reason=stop_reason,
                evidence_events=(event, f"route_stop:{stop_reason}"),
            )
        )
    return tuple(records)


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
        failure_recovery=_failure_recovery_for_stop_reason(record.stop_reason),
        coverage_tags=("negative_control",),
        selected_tool_ids=(),
        assertion_events=(
            "route_assertion:negative_control",
            "route_assertion:no_internal_tool_id",
        ),
    )


def _stop_reason_for_scenario(scenario: Scenario) -> RouteStopReason:
    return (
        "permission_required"
        if scenario.permission_requirements.user_confirmations
        else "answerable"
    )


def _argument_feasibility_for_scenario(scenario: Scenario) -> RouteArgumentFeasibility:
    if not scenario.request_ko.strip() or not scenario.expected_ax_chain:
        return "blocked"
    return "sufficient"


def _failure_recovery_for_stop_reason(stop_reason: RouteStopReason) -> RouteFailureRecovery:
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


def _adapter_family_for_scenario(
    scenario: Scenario,
    selected_primitives: Sequence[str],
) -> RouteAdapterFamily:
    text = _scenario_text(scenario)
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


def _coverage_tags_for_scenario(
    scenario: Scenario,
    selected_primitives: Sequence[str],
) -> tuple[str, ...]:
    text = _scenario_text(scenario)
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


def _scenario_text(scenario: Scenario) -> str:
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


def _prompt_manifest_hash(dataset: ScenarioDataset) -> str:
    return sha256(
        {
            "allowed_primitives": dataset.allowed_primitives,
            "dataset_id": dataset.dataset_id,
            "source_basis": dataset.source_basis,
            "target_system": dataset.target_system,
            "version": dataset.version,
        }
    )


def _tool_catalog_hash(dataset: ScenarioDataset) -> str:
    return sha256(
        {
            "adapter_families": tuple(
                sorted(
                    {
                        _adapter_family_for_scenario(
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


def _correlation_id(trace_id: str) -> str:
    return f"corr-route-{sha256(trace_id)[:16]}"


def _resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else _REPO_ROOT / path


def _resolve_task_dataset(
    *,
    dataset: ScenarioDataset,
    scenario_path: Path,
    task_registry_path: Path | None,
    dataset_ref: str,
) -> tuple[str | None, EvidenceDatasetRef | None]:
    if task_registry_path is None:
        return None, None
    registry = load_task_registry(task_registry_path)
    task_dataset = registry.resolve_dataset(dataset_ref)
    if task_dataset.dataset_id != dataset.dataset_id:
        raise EvidenceContractError(
            f"task registry dataset_id {task_dataset.dataset_id!r} does not match "
            f"scenario dataset_id {dataset.dataset_id!r}"
        )
    if _resolve_repo_path(task_dataset.scenario_path) != _resolve_repo_path(scenario_path):
        raise EvidenceContractError(
            f"task registry scenario_path {task_dataset.scenario_path} does not match "
            f"run scenario_path {scenario_path}"
        )
    return registry.registry_id, task_dataset


def run_dataset(
    *,
    scenario_path: Path = _DEFAULT_SCENARIO_PATH,
    source_ref: str = "local",
    task_registry_path: Path | None = _DEFAULT_TASK_REGISTRY_PATH,
    dataset_ref: str = _DEFAULT_DATASET_REF,
) -> RunEvidence:
    """Validate a scenario dataset and return a typed evidence document."""

    dataset = _parse_dataset(scenario_path)
    task_registry_id, task_dataset = _resolve_task_dataset(
        dataset=dataset,
        scenario_path=scenario_path,
        task_registry_path=task_registry_path,
        dataset_ref=dataset_ref,
    )
    route_trace_records = _route_trace_records(dataset)
    return RunEvidence(
        source_ref=source_ref,
        dataset_id=dataset.dataset_id,
        task_registry_id=task_registry_id,
        dataset_ref=task_dataset.ref if task_dataset else None,
        task_count=len(task_dataset.tasks) if task_dataset else 0,
        task_ids=tuple(task.task_id for task in task_dataset.tasks) if task_dataset else (),
        scenario_count=len(dataset.scenarios),
        scenario_ids=tuple(scenario.id for scenario in dataset.scenarios),
        route_trace_records=route_trace_records,
        route_selection_assertions=_route_selection_assertions(dataset, route_trace_records),
        gates=_build_gates(dataset),
    )


def build_evidence_output_payload(
    evidence: RunEvidence,
    *,
    include_document_harness: bool = True,
    document_viewer_ux_artifacts: Sequence[DocumentViewerUxArtifact] = (),
    hwp_bridge_probe_env: Mapping[str, str] | None = None,
    hwp_bridge_probe_search_path: Sequence[str] | None = None,
    odf_probe_env: Mapping[str, str] | None = None,
    odf_probe_search_path: Sequence[str] | None = None,
    odf_probe_importable_modules: frozenset[str] | None = None,
    pdfa_probe_env: Mapping[str, str] | None = None,
    pdfa_probe_search_path: Sequence[str] | None = None,
    archive_probe_env: Mapping[str, str] | None = None,
    archive_probe_search_path: Sequence[str] | None = None,
    passive_probe_env: Mapping[str, str] | None = None,
    passive_probe_search_path: Sequence[str] | None = None,
    passive_probe_importable_modules: frozenset[str] | None = None,
    legacy_office_probe_env: Mapping[str, str] | None = None,
    legacy_office_probe_search_path: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build the JSON payload emitted by the CLI."""
    payload = evidence.model_dump(mode="json")
    if document_viewer_ux_artifacts:
        payload["gates"] = _with_passed_ux_gate(payload["gates"])
        payload["ux_artifacts"] = [
            artifact.model_dump(mode="json") for artifact in document_viewer_ux_artifacts
        ]
    if include_document_harness:
        from ummaya.evidence.document_harness import (  # noqa: PLC0415
            beta_cases_from_scenario,
            lifecycle_records_from_scenario,
            load_document_harness_scenario,
            negative_cases_from_scenario,
            records_from_scenario,
        )

        scenario = load_document_harness_scenario()
        document_records = records_from_scenario(scenario)
        _validate_document_viewer_ux_joins(document_records, document_viewer_ux_artifacts)
        payload["document_evidence_records"] = [
            record.model_dump(mode="json") for record in document_records
        ]
        payload["document_lifecycle_records"] = [
            record.model_dump(mode="json") for record in lifecycle_records_from_scenario(scenario)
        ]
        payload["document_beta_cases"] = [
            case.model_dump(mode="json") for case in beta_cases_from_scenario(scenario)
        ]
        payload["document_negative_cases"] = [
            case.model_dump(mode="json") for case in negative_cases_from_scenario(scenario)
        ]
        from ummaya.tools.documents.hwp_conversion_probe import (  # noqa: PLC0415
            probe_hwp_to_hwpx_bridge,
        )

        bridge_probe = probe_hwp_to_hwpx_bridge(
            env=hwp_bridge_probe_env,
            search_path=_default_hwp_bridge_probe_search_path(
                env=hwp_bridge_probe_env,
                explicit_search_path=hwp_bridge_probe_search_path,
            ),
        )
        payload["document_bridge_probe_records"] = [bridge_probe.model_dump(mode="json")]
        from ummaya.tools.documents.odf_promotion_probe import (  # noqa: PLC0415
            probe_odf_promotion,
        )

        odf_probe_records = probe_odf_promotion(
            env=odf_probe_env,
            search_path=odf_probe_search_path,
            importable_modules=odf_probe_importable_modules,
        )
        payload["document_odf_probe_records"] = [
            record.model_dump(mode="json") for record in odf_probe_records
        ]
        from ummaya.tools.documents.pdfa_promotion_probe import (  # noqa: PLC0415
            probe_pdfa_promotion,
        )

        pdfa_probe_record = probe_pdfa_promotion(
            env=pdfa_probe_env,
            search_path=pdfa_probe_search_path,
        )
        payload["document_pdfa_probe_records"] = [pdfa_probe_record.model_dump(mode="json")]
        from ummaya.tools.documents.archive_container_probe import (  # noqa: PLC0415
            probe_archive_container_promotion,
        )

        archive_probe_records = probe_archive_container_promotion(
            env=archive_probe_env,
            search_path=archive_probe_search_path,
        )
        payload["document_archive_probe_records"] = [
            record.model_dump(mode="json") for record in archive_probe_records
        ]
        from ummaya.tools.documents.passive_capability_probe import (  # noqa: PLC0415
            probe_passive_capabilities,
        )

        passive_probe_records = probe_passive_capabilities(
            env=passive_probe_env,
            search_path=passive_probe_search_path,
            importable_modules=passive_probe_importable_modules,
        )
        payload["document_passive_probe_records"] = [
            record.model_dump(mode="json") for record in passive_probe_records
        ]
        from ummaya.tools.documents.legacy_office_promotion_probe import (  # noqa: PLC0415
            probe_legacy_office_promotion,
        )

        legacy_office_probe_records = probe_legacy_office_promotion(
            env=legacy_office_probe_env,
            search_path=legacy_office_probe_search_path,
        )
        payload["document_legacy_office_probe_records"] = [
            record.model_dump(mode="json") for record in legacy_office_probe_records
        ]
        from ummaya.tools.documents.format_completion_audit import (  # noqa: PLC0415
            audit_document_format_completion,
        )

        payload["document_format_completion_audit"] = audit_document_format_completion(
            derivative_promoted_formats=_derivative_promoted_formats_from_probe_records(
                bridge_probe=bridge_probe,
                legacy_office_probe_records=legacy_office_probe_records,
            ),
            pdfa_conformance_promoted=pdfa_probe_record.status == "candidate_available",
        ).model_dump(mode="json")
    return payload


def _derivative_promoted_formats_from_probe_records(
    *,
    bridge_probe: Any,
    legacy_office_probe_records: Sequence[Any],
) -> frozenset[KnownDocumentFormat]:
    from ummaya.tools.documents.hwp_conversion_probe import (  # noqa: PLC0415
        HWPXJS_CANDIDATE_ID,
    )

    promoted: set[KnownDocumentFormat] = set()
    if bridge_probe.status == "configured" or (
        bridge_probe.status == "available" and bridge_probe.candidate_id == HWPXJS_CANDIDATE_ID
    ):
        promoted.add(KnownDocumentFormat.hwp)
    for record in legacy_office_probe_records:
        if record.status == "candidate_available":
            promoted.add(record.known_format)
    return frozenset(promoted)


def _default_hwp_bridge_probe_search_path(
    *,
    env: Mapping[str, str] | None,
    explicit_search_path: Sequence[str] | None,
) -> Sequence[str] | None:
    if explicit_search_path is not None:
        return explicit_search_path
    if env is not None:
        return None

    paths: list[str] = []
    for root in (Path.cwd(), _REPO_ROOT):
        node_bin = root / "node_modules" / ".bin"
        node_bin_str = str(node_bin)
        if node_bin_str not in paths:
            paths.append(node_bin_str)

    process_path = os.environ.get("PATH", "")
    paths.extend(part for part in process_path.split(os.pathsep) if part)
    return tuple(paths) if paths else None


def _validate_document_viewer_ux_joins(
    document_records: Sequence[Any],
    document_viewer_ux_artifacts: Sequence[DocumentViewerUxArtifact],
) -> None:
    if not document_viewer_ux_artifacts:
        return
    from ummaya.evidence.document_harness import DocumentHarnessEvidenceError  # noqa: PLC0415

    valid_joins = {
        (record.structured_diff_id, record.correlation_id) for record in document_records
    }
    for artifact in document_viewer_ux_artifacts:
        if artifact.document_diff_id is None:
            raise DocumentHarnessEvidenceError(
                f"document viewer UX artifact does not carry a document_diff_id: "
                f"{artifact.artifact_id}"
            )
        join_key = (artifact.document_diff_id, artifact.correlation_id)
        if join_key not in valid_joins:
            raise DocumentHarnessEvidenceError(
                "document viewer UX artifact does not join a backend document diff "
                f"record by document_diff_id and correlation_id: {artifact.artifact_id}"
            )


def _with_passed_ux_gate(gates: object) -> list[object]:
    if not isinstance(gates, list):
        return []
    promoted: list[object] = []
    for gate in gates:
        if isinstance(gate, dict) and gate.get("name") == "ux":
            promoted.append(
                {
                    **gate,
                    "status": "pass",
                    "summary": "Playwright document viewer UX artifacts are attached",
                    "check_ids": ["document-viewer-playwright-png", "frame-hash"],
                }
            )
            continue
        promoted.append(gate)
    return promoted


def main() -> None:
    """CLI entrypoint for `python -m ummaya.evidence`."""

    parser = argparse.ArgumentParser(prog="python -m ummaya.evidence")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=_DEFAULT_SCENARIO_PATH,
        help="Path to the Evidence Fabric scenario dataset.",
    )
    parser.add_argument(
        "--source-ref",
        default="local",
        help="Source revision or label recorded in the evidence document.",
    )
    parser.add_argument(
        "--task-registry",
        type=Path,
        default=_DEFAULT_TASK_REGISTRY_PATH,
        help="Path to the Harbor-style Evidence Fabric task registry.",
    )
    parser.add_argument(
        "--dataset-ref",
        default=_DEFAULT_DATASET_REF,
        help="Harbor-style dataset ref to resolve from the task registry.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(".evidence/run.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--document-viewer-html",
        type=Path,
        action="append",
        default=None,
        help="Local document viewer HTML path to capture as a Playwright UX artifact.",
    )
    parser.add_argument(
        "--document-viewer-ux-out-dir",
        type=Path,
        default=None,
        help="Directory for Playwright document viewer PNG artifacts.",
    )
    parser.add_argument(
        "--document-viewer-correlation-id",
        default=None,
        help="Correlation ID to attach when the viewer manifest does not carry one.",
    )
    parser.add_argument(
        "--document-viewer-diff-id",
        default=None,
        help="Document diff ID to attach when the viewer manifest does not carry one.",
    )
    args = parser.parse_args()

    evidence = run_dataset(
        scenario_path=args.scenarios,
        source_ref=args.source_ref,
        task_registry_path=args.task_registry,
        dataset_ref=args.dataset_ref,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ux_out_dir = args.document_viewer_ux_out_dir or args.out.parent / "ux-artifacts"
    document_viewer_ux_artifacts: list[DocumentViewerUxArtifact] = []
    document_viewer_html_paths = tuple(args.document_viewer_html or ())
    if document_viewer_html_paths:
        from ummaya.evidence.document_viewer_ux import (  # noqa: PLC0415
            capture_document_viewer_ux_artifact,
        )

        for viewer_html_path in document_viewer_html_paths:
            document_viewer_ux_artifacts.append(
                capture_document_viewer_ux_artifact(
                    viewer_html_path=viewer_html_path,
                    output_dir=ux_out_dir,
                    source_ref=args.source_ref,
                    correlation_id=args.document_viewer_correlation_id,
                    document_diff_id=args.document_viewer_diff_id,
                )
            )
    payload = build_evidence_output_payload(
        evidence,
        document_viewer_ux_artifacts=tuple(document_viewer_ux_artifacts),
    )
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
