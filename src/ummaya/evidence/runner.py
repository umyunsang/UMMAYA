# SPDX-License-Identifier: Apache-2.0
"""Evidence Fabric v2 dataset runner.

The runner is intentionally local and deterministic. It validates scenario
contracts and emits a typed RunEvidence document without calling live public
service channels, LLM providers, or observability backends.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ummaya.evidence.models import EvidenceGate, RunEvidence
from ummaya.evidence.task_registry import EvidenceDatasetRef, load_task_registry

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
    args = parser.parse_args()

    evidence = run_dataset(
        scenario_path=args.scenarios,
        source_ref=args.source_ref,
        task_registry_path=args.task_registry,
        dataset_ref=args.dataset_ref,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(evidence.model_dump_json(indent=2), encoding="utf-8")
