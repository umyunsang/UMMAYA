# SPDX-License-Identifier: Apache-2.0
"""Typed Evidence Fabric v2 models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ummaya.tools.routing.decision_types import RouteStopReason

EvidenceStatus = Literal["pass", "fail", "skip"]
RouteTraceKind = Literal["scenario_route", "negative_control"]
RouteTraceSource = Literal["expected_route_contract", "route_decision"]
RouteAssertionStatus = Literal["pass", "fail"]
RouteAdapterFamily = Literal[
    "public_service_channel",
    "location_channel",
    "weather_channel",
    "safety_channel",
    "procurement_channel",
    "public_data_channel",
    "document_harness",
    "no_tool",
]
RouteArgumentFeasibility = Literal["sufficient", "needs_clarification", "blocked"]
RouteFailureRecovery = Literal[
    "not_required",
    "permission_gate",
    "clarification",
    "handoff",
    "blocked",
]
EvidenceGateName = Literal[
    "contract",
    "scenario",
    "observability",
    "adversarial",
    "ux",
    "live_canary",
]


class EvidenceGate(BaseModel):
    """One scored verification gate in a run evidence document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: EvidenceGateName
    status: EvidenceStatus
    summary: str
    check_ids: tuple[str, ...] = Field(default_factory=tuple)


class RouteTraceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_kind: RouteTraceKind = "scenario_route"
    route_source: RouteTraceSource = "expected_route_contract"
    scenario_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    query_hash: str = Field(min_length=64, max_length=64)
    manifest_hash: str = Field(min_length=64, max_length=64)
    prompt_manifest_hash: str = Field(min_length=64, max_length=64)
    tool_catalog_hash: str = Field(min_length=64, max_length=64)
    selected_domain: str = Field(min_length=1)
    selected_primitives: tuple[str, ...] = Field(default_factory=tuple)
    selected_tools: tuple[str, ...] = Field(default_factory=tuple)
    clarification_reason: str | None = None
    stop_reason: RouteStopReason
    evidence_events: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("query_hash", "manifest_hash", "prompt_manifest_hash", "tool_catalog_hash")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("hash fields must be lowercase SHA-256 hex")
        return value


class RouteSelectionAssertion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assertion_kind: RouteTraceKind = "scenario_route"
    route_source: RouteTraceSource = "expected_route_contract"
    status: RouteAssertionStatus
    scenario_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    prompt_manifest_hash: str = Field(min_length=64, max_length=64)
    tool_catalog_hash: str = Field(min_length=64, max_length=64)
    expected_domain: str = Field(min_length=1)
    selected_domain: str = Field(min_length=1)
    expected_primitives: tuple[str, ...] = Field(default_factory=tuple)
    selected_primitives: tuple[str, ...] = Field(default_factory=tuple)
    adapter_family: RouteAdapterFamily
    argument_feasibility: RouteArgumentFeasibility
    clarification_expected: bool
    clarification_reason: str | None
    stop_reason: RouteStopReason
    failure_recovery: RouteFailureRecovery
    coverage_tags: tuple[str, ...] = Field(default_factory=tuple)
    selected_tool_ids: tuple[str, ...] = Field(default_factory=tuple)
    assertion_events: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("prompt_manifest_hash", "tool_catalog_hash")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("hash fields must be lowercase SHA-256 hex")
        return value


class RunEvidence(BaseModel):
    """Top-level immutable evidence document emitted by the v2 runner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["evidence.v2"] = "evidence.v2"
    run_id: str = Field(default_factory=lambda: f"ev-{uuid4()}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_ref: str
    dataset_id: str
    task_registry_id: str | None = None
    dataset_ref: str | None = None
    task_count: int = 0
    task_ids: tuple[str, ...] = Field(default_factory=tuple)
    scenario_count: int
    scenario_ids: tuple[str, ...]
    route_trace_records: tuple[RouteTraceRecord, ...] = Field(default_factory=tuple)
    route_selection_assertions: tuple[RouteSelectionAssertion, ...] = Field(default_factory=tuple)
    gates: tuple[EvidenceGate, ...]
    trace_join_keys: tuple[str, ...] = (
        "scenario_id",
        "trace_id",
        "correlation_id",
        "prompt_manifest_hash",
        "tool_catalog_hash",
        "frame_hash",
    )
