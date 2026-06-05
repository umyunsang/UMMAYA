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
from ummaya.evidence.models import EvidenceGate, RunEvidence
from ummaya.evidence.task_registry import EvidenceDatasetRef, load_task_registry
from ummaya.tools.documents.models import KnownDocumentFormat

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SCENARIO_PATH = _REPO_ROOT / "evidence/scenarios/national_ax_citizen_requests_v1.yaml"
_DEFAULT_TASK_REGISTRY_PATH = _REPO_ROOT / "evidence/registry.yaml"
_DEFAULT_DATASET_REF = "ummaya/national-ax-core@local"
_BANNED_MODEL_VISIBLE_KEYS = frozenset(
    {
        "adapter_id",
        "tool_id",
        "expected_tool_id",
        "fixture_refs",
        "fixture_ref",
        "current_adapter_id",
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
    expected_ax_chain: tuple[ExpectedStep, ...]
    permission_requirements: PermissionRequirements


class ScenarioDataset(BaseModel):
    """Versioned citizen-demand scenario dataset."""

    model_config = ConfigDict(frozen=True, extra="allow")

    version: int
    dataset_id: str
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
            "dataset is versioned, typed, and free of model-visible implementation keys",
            ("dataset-schema", "task-registry", "no-adapter-leakage"),
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
            "RunEvidence carries trace join keys for OTEL/Langfuse correlation",
            ("trace-join-keys",),
        ),
        _gate(
            "adversarial",
            "pass",
            "adapter IDs, fixture references, and expected tool IDs are rejected before scoring",
            ("reward-hack-surface", "hidden-implementation-leakage"),
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
    return RunEvidence(
        source_ref=source_ref,
        dataset_id=dataset.dataset_id,
        task_registry_id=task_registry_id,
        dataset_ref=task_dataset.ref if task_dataset else None,
        task_count=len(task_dataset.tasks) if task_dataset else 0,
        task_ids=tuple(task.task_id for task in task_dataset.tasks) if task_dataset else (),
        scenario_count=len(dataset.scenarios),
        scenario_ids=tuple(scenario.id for scenario in dataset.scenarios),
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
