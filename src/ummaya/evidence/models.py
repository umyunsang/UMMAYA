# SPDX-License-Identifier: Apache-2.0
"""Typed Evidence Fabric v2 models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

EvidenceStatus = Literal["pass", "fail", "skip"]
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
    gates: tuple[EvidenceGate, ...]
    trace_join_keys: tuple[str, ...] = (
        "scenario_id",
        "trace_id",
        "correlation_id",
        "prompt_manifest_hash",
        "tool_catalog_hash",
        "frame_hash",
    )
