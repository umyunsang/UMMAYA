# SPDX-License-Identifier: Apache-2.0
"""Document harness evidence records for Evidence Fabric v2.

This module stores only join metadata for document reports. Document bytes,
extracted text, and filled field values stay in the local artifact/report store
and are referenced here by opaque IDs plus SHA-256 hashes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ummaya.evidence.models import RunEvidence

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DOCUMENT_SCENARIO_PATH = _REPO_ROOT / "evidence/scenarios/document_harness_v1.yaml"

DocumentHarnessReadiness = Literal[
    "ready_for_review",
    "not_ready",
    "blocked",
    "unsupported",
]
DocumentHarnessFormat = Literal["hwpx", "docx", "xlsx", "pdf", "pptx"]


class DocumentHarnessEvidenceError(ValueError):
    """Raised when document harness evidence metadata is invalid."""


class DocumentEvidenceRecord(BaseModel):
    """Joinable evidence record for one generated document derivative."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    record_id: str
    scenario_id: str
    correlation_id: str
    source_artifact_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_artifact_id: str
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_diff_id: str
    structured_diff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    render_artifact_ids: tuple[str, ...] = Field(min_length=1)
    validation_report_id: str
    validation_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    readiness: DocumentHarnessReadiness


class DocumentHarnessEvidenceEnvelope(BaseModel):
    """Evidence Fabric runner output plus document-specific evidence records."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    run_evidence: RunEvidence
    document_evidence_records: tuple[DocumentEvidenceRecord, ...]


class DocumentHarnessAcceptanceGates(BaseModel):
    """US4 acceptance gates for the document harness scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    original_mutation: Literal["blocked"]
    derivative_lineage: Literal["required"]
    structured_result_schema: Literal["required"]
    render_reread_evidence: Literal["required"]
    live_government_calls: Literal["forbidden"]


class DocumentHarnessFixture(BaseModel):
    """Offline fixture metadata used to prove document evidence joins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fixture_id: str
    format: DocumentHarnessFormat
    source_artifact_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_artifact_id: str
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_diff_id: str
    structured_diff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    render_artifact_ids: tuple[str, ...] = Field(min_length=1)
    validation_report_id: str
    validation_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_correlation_id: str


class DocumentHarnessScenario(BaseModel):
    """Dedicated US4 scenario metadata for document harness evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    scenario_id: Literal["document_harness_v1"]
    created_at: str
    source_basis: Literal["public_ax_document_harness_spec"]
    target_system: str
    network_policy: Literal["offline_only"]
    required_sequence: tuple[
        Literal[
            "document_inspect",
            "document_form_schema",
            "document_copy_for_edit",
            "document_apply_fill",
            "document_render",
            "document_validate_public_form",
            "document_save",
        ],
        ...,
    ]
    acceptance_gates: DocumentHarnessAcceptanceGates
    fixtures: tuple[DocumentHarnessFixture, ...] = Field(min_length=1)


def load_document_harness_scenario(
    path: Path = _DEFAULT_DOCUMENT_SCENARIO_PATH,
) -> DocumentHarnessScenario:
    """Load the offline document harness Evidence Fabric scenario."""

    raw = _load_yaml_mapping(path)
    try:
        return DocumentHarnessScenario.model_validate(raw)
    except ValidationError as exc:
        raise DocumentHarnessEvidenceError(str(exc)) from exc


def attach_document_evidence_records(
    run_evidence: RunEvidence,
    records: Sequence[DocumentEvidenceRecord],
) -> DocumentHarnessEvidenceEnvelope:
    """Attach document records to an Evidence Fabric runner result."""

    return DocumentHarnessEvidenceEnvelope(
        run_evidence=run_evidence,
        document_evidence_records=tuple(records),
    )


def records_from_scenario(
    scenario: DocumentHarnessScenario,
) -> tuple[DocumentEvidenceRecord, ...]:
    """Build join-only document evidence records from scenario fixture metadata."""

    return tuple(
        DocumentEvidenceRecord(
            record_id=f"doc-evidence-{fixture.fixture_id}",
            scenario_id=scenario.scenario_id,
            correlation_id=fixture.expected_correlation_id,
            source_artifact_id=fixture.source_artifact_id,
            source_sha256=fixture.source_sha256,
            derivative_artifact_id=fixture.derivative_artifact_id,
            derivative_sha256=fixture.derivative_sha256,
            structured_diff_id=fixture.structured_diff_id,
            structured_diff_sha256=fixture.structured_diff_sha256,
            render_artifact_ids=fixture.render_artifact_ids,
            validation_report_id=fixture.validation_report_id,
            validation_report_sha256=fixture.validation_report_sha256,
            readiness="ready_for_review",
        )
        for fixture in scenario.fixtures
    )


def _load_yaml_mapping(path: Path) -> Mapping[str, object]:
    resolved = path if path.is_absolute() else _REPO_ROOT / path
    if not resolved.exists():
        raise DocumentHarnessEvidenceError(f"document harness scenario not found: {path}")
    loaded = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise DocumentHarnessEvidenceError(f"document harness scenario must be a mapping: {path}")
    return cast(Mapping[str, object], loaded)
