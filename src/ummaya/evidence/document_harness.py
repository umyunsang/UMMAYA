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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ummaya.evidence.document_authoring_cases import DocumentAuthoringCase
from ummaya.evidence.models import RunEvidence
from ummaya.tools.documents.models import DocumentFormatFamily, KnownDocumentFormat

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DOCUMENT_SCENARIO_PATH = _REPO_ROOT / "evidence/scenarios/document_harness_v1.yaml"

DocumentHarnessReadiness = Literal[
    "ready_for_review",
    "not_ready",
    "blocked",
    "unsupported",
]
DocumentHarnessFormat = Literal["hwpx", "docx", "xlsx", "pdf", "pptx"]
DocumentHarnessLifecycleStage = Literal[
    "intake",
    "classification",
    "capability",
    "adapter_selection",
    "permission",
    "mutation",
    "render",
    "reread",
    "validation",
    "diff",
    "tui_frame",
]
DocumentHarnessLifecycleStatus = Literal[
    "pass",
    "blocked",
    "needs_input",
    "unsupported",
    "ready_for_review",
]
DocumentHarnessBetaDomain = Literal[
    "weekly_log",
    "contest_proposal",
    "consent",
    "pledge",
    "spreadsheet",
    "pdf_form",
    "presentation",
    "public_data_csv_json",
    "static_pdf",
    "scanned_image",
    "archive_bundle",
]
DocumentHarnessBetaOutcome = Literal[
    "ready_for_review",
    "read_only",
    "blocked",
    "needs_input",
    "unsupported",
]
DocumentHarnessNegativeTrigger = Literal[
    "missing_file",
    "ambiguous_file_candidates",
    "unsupported_known_format",
    "blocked_hwp_write",
    "static_pdf_fill",
    "macro_active_content",
    "path_traversal",
    "oversized_archive",
    "external_link",
]


class DocumentHarnessEvidenceError(ValueError):
    """Raised when document harness evidence metadata is invalid."""


class DocumentEvidenceRecord(BaseModel):
    """Joinable evidence record for one generated document derivative."""

    model_config = ConfigDict(frozen=True, extra="forbid")

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


class DocumentLifecycleEvidenceRecord(BaseModel):
    """Join-only evidence for one document workflow stage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str
    scenario_id: str
    correlation_id: str
    stage: DocumentHarnessLifecycleStage
    status: DocumentHarnessLifecycleStatus
    known_format: KnownDocumentFormat
    format_family: DocumentFormatFamily
    adapter_id: str | None = None
    artifact_id: str | None = None
    artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    document_diff_id: str | None = None
    frame_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    evidence_ref: str

    @model_validator(mode="after")
    def _tui_frame_requires_frame_hash(self) -> DocumentLifecycleEvidenceRecord:
        if self.stage == "tui_frame" and self.frame_hash is None:
            raise ValueError("tui_frame lifecycle evidence requires frame_hash")
        return self


class DocumentBetaCase(BaseModel):
    """Representative beta scenario for one Public AX document domain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    domain: DocumentHarnessBetaDomain
    known_format: KnownDocumentFormat
    format_family: DocumentFormatFamily
    expected_outcome: DocumentHarnessBetaOutcome
    expected_operation: str
    fixture_id: str | None = None
    evidence_ref: str


class DocumentNegativeCase(BaseModel):
    """Negative beta scenario that must fail closed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    trigger: DocumentHarnessNegativeTrigger
    expected_status: Literal["blocked", "needs_input"]
    expected_reason: str
    derivative_save: Literal["forbidden"]
    evidence_ref: str


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
    source_basis: Literal["document_production_hardening_spec"]
    target_system: str
    network_policy: Literal["offline_only"]
    required_sequence: tuple[Literal["document"], ...]
    acceptance_gates: DocumentHarnessAcceptanceGates
    fixtures: tuple[DocumentHarnessFixture, ...] = Field(min_length=1)
    lifecycle_records: tuple[DocumentLifecycleEvidenceRecord, ...] = Field(min_length=1)
    beta_cases: tuple[DocumentBetaCase, ...] = Field(min_length=1)
    negative_cases: tuple[DocumentNegativeCase, ...] = Field(min_length=1)
    authoring_cases: tuple[DocumentAuthoringCase, ...] = Field(min_length=1)


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


def lifecycle_records_from_scenario(
    scenario: DocumentHarnessScenario,
) -> tuple[DocumentLifecycleEvidenceRecord, ...]:
    """Return workflow lifecycle records from scenario metadata."""

    return scenario.lifecycle_records


def beta_cases_from_scenario(
    scenario: DocumentHarnessScenario,
) -> tuple[DocumentBetaCase, ...]:
    """Return beta-matrix cases from scenario metadata."""

    return scenario.beta_cases


def negative_cases_from_scenario(
    scenario: DocumentHarnessScenario,
) -> tuple[DocumentNegativeCase, ...]:
    """Return fail-closed beta-matrix cases from scenario metadata."""

    return scenario.negative_cases


def authoring_cases_from_scenario(
    scenario: DocumentHarnessScenario,
) -> tuple[DocumentAuthoringCase, ...]:
    return scenario.authoring_cases


def _load_yaml_mapping(path: Path) -> Mapping[str, object]:
    resolved = path if path.is_absolute() else _REPO_ROOT / path
    if not resolved.exists():
        raise DocumentHarnessEvidenceError(f"document harness scenario not found: {path}")
    loaded = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise DocumentHarnessEvidenceError(f"document harness scenario must be a mapping: {path}")
    return cast(Mapping[str, object], loaded)
