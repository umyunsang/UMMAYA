# SPDX-License-Identifier: Apache-2.0
"""Evidence Fabric joins for Public AX document harness reports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64


def test_document_evidence_record_joins_reports_without_document_bytes() -> None:
    from ummaya.evidence.document_harness import DocumentEvidenceRecord

    record = DocumentEvidenceRecord(
        record_id="doc-ev-001",
        scenario_id="DOC-US4-001",
        correlation_id="corr-doc-001",
        source_artifact_id="artifact-source-001",
        source_sha256=_HASH_A,
        derivative_artifact_id="artifact-derivative-001",
        derivative_sha256=_HASH_B,
        structured_diff_id="diff-001",
        structured_diff_sha256=_HASH_C,
        render_artifact_ids=("render-page-001",),
        validation_report_id="validation-001",
        validation_report_sha256=_HASH_D,
        readiness="ready_for_review",
    )

    encoded = json.loads(record.model_dump_json())

    assert encoded["correlation_id"] == "corr-doc-001"
    assert encoded["source_sha256"] == _HASH_A
    assert encoded["derivative_sha256"] == _HASH_B
    assert encoded["render_artifact_ids"] == ["render-page-001"]
    assert "document_bytes" not in encoded
    assert "text" not in encoded
    assert "after_value" not in encoded


def test_document_evidence_record_rejects_inline_document_bytes() -> None:
    from ummaya.evidence.document_harness import DocumentEvidenceRecord

    with pytest.raises(ValidationError, match="document_bytes"):
        DocumentEvidenceRecord(
            record_id="doc-ev-001",
            scenario_id="DOC-US4-001",
            correlation_id="corr-doc-001",
            source_artifact_id="artifact-source-001",
            source_sha256=_HASH_A,
            derivative_artifact_id="artifact-derivative-001",
            derivative_sha256=_HASH_B,
            structured_diff_id="diff-001",
            structured_diff_sha256=_HASH_C,
            render_artifact_ids=("render-page-001",),
            validation_report_id="validation-001",
            validation_report_sha256=_HASH_D,
            readiness="ready_for_review",
            document_bytes=b"raw document payload",
        )


def test_document_harness_scenario_covers_us4_without_live_calls() -> None:
    from ummaya.evidence.document_harness import load_document_harness_scenario

    scenario = load_document_harness_scenario(Path("evidence/scenarios/document_harness_v1.yaml"))

    assert scenario.scenario_id == "document_harness_v1"
    assert scenario.network_policy == "offline_only"
    assert scenario.acceptance_gates.live_government_calls == "forbidden"
    assert scenario.acceptance_gates.render_reread_evidence == "required"
    assert scenario.required_sequence == (
        "document_inspect",
        "document_form_schema",
        "document_copy_for_edit",
        "document_apply_fill",
        "document_render",
        "document_validate_public_form",
        "document_save",
    )
    assert {fixture.format for fixture in scenario.fixtures} == {
        "hwpx",
        "docx",
        "xlsx",
        "pdf",
        "pptx",
    }
    assert all(fixture.expected_correlation_id for fixture in scenario.fixtures)
    assert all(fixture.source_sha256 and fixture.derivative_sha256 for fixture in scenario.fixtures)


def test_document_records_attach_to_evidence_runner_output() -> None:
    from ummaya.evidence.document_harness import (
        DocumentEvidenceRecord,
        attach_document_evidence_records,
    )
    from ummaya.evidence.runner import run_dataset

    run_evidence = run_dataset(
        scenario_path=Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml"),
        source_ref="test",
    )
    record = DocumentEvidenceRecord(
        record_id="doc-ev-001",
        scenario_id="DOC-US4-001",
        correlation_id="corr-doc-001",
        source_artifact_id="artifact-source-001",
        source_sha256=_HASH_A,
        derivative_artifact_id="artifact-derivative-001",
        derivative_sha256=_HASH_B,
        structured_diff_id="diff-001",
        structured_diff_sha256=_HASH_C,
        render_artifact_ids=("render-page-001",),
        validation_report_id="validation-001",
        validation_report_sha256=_HASH_D,
        readiness="ready_for_review",
    )

    envelope = attach_document_evidence_records(run_evidence, (record,))

    assert envelope.run_evidence.schema_version == "evidence.v2"
    assert envelope.document_evidence_records == (record,)
    assert "correlation_id" in envelope.run_evidence.trace_join_keys
    encoded = json.loads(envelope.model_dump_json())
    assert encoded["document_evidence_records"][0]["correlation_id"] == "corr-doc-001"


def test_evidence_cli_payload_includes_document_harness_records() -> None:
    from ummaya.evidence.runner import build_evidence_output_payload, run_dataset

    run_evidence = run_dataset(
        scenario_path=Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml"),
        source_ref="test",
    )

    payload = build_evidence_output_payload(run_evidence)

    assert payload["schema_version"] == "evidence.v2"
    records = payload["document_evidence_records"]
    assert isinstance(records, list)
    assert records
    assert {record["scenario_id"] for record in records} == {"document_harness_v1"}
    assert all(record["correlation_id"] for record in records)
