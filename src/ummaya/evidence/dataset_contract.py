# SPDX-License-Identifier: Apache-2.0
"""Scenario dataset parsing for Evidence Fabric v2."""

from __future__ import annotations

from pathlib import Path
from typing import assert_never

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ummaya.evidence.json_types import JsonObject, JsonValue, parse_json_object

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCENARIO_PATH = _REPO_ROOT / "evidence/scenarios/national_ax_citizen_requests_v1.yaml"
DEFAULT_TASK_REGISTRY_PATH = _REPO_ROOT / "evidence/registry.yaml"
DEFAULT_DATASET_REF = "ummaya/national-ax-core@local"
BANNED_MODEL_VISIBLE_KEYS = frozenset(
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
REQUIRED_DOMAINS = frozenset(
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


def parse_dataset(path: Path) -> ScenarioDataset:
    """Parse and validate a scenario dataset file."""
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


def resolve_repo_path(path: Path) -> Path:
    """Resolve a repository-relative path from the Evidence Fabric root."""
    return path if path.is_absolute() else _REPO_ROOT / path


def _load_yaml_mapping(path: Path) -> JsonObject:
    if not path.exists():
        raise EvidenceContractError(f"scenario dataset not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        return parse_json_object(loaded)
    except ValidationError as exc:
        raise EvidenceContractError(f"scenario dataset must be a JSON mapping: {path}") from exc


def _find_banned_keys(value: JsonValue, path: str = "$") -> tuple[str, ...]:
    match value:
        case dict():
            hits: list[str] = []
            for key, nested in value.items():
                nested_path = f"{path}.{key}"
                if key in BANNED_MODEL_VISIBLE_KEYS:
                    hits.append(nested_path)
                hits.extend(_find_banned_keys(nested, nested_path))
            return tuple(hits)
        case list():
            hits = []
            for index, nested in enumerate(value):
                hits.extend(_find_banned_keys(nested, f"{path}[{index}]"))
            return tuple(hits)
        case str() | int() | float() | bool() | None:
            return ()
        case unreachable:
            assert_never(unreachable)
