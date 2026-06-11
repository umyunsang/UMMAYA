# SPDX-License-Identifier: Apache-2.0
"""T073 privacy tests for document permission, result, and evidence JSON."""

from __future__ import annotations

import json

import pytest

from tests.tools.documents.document_privacy_helpers import (
    HASH_A,
    HASH_B,
    HASH_C,
    HASH_D,
    RAW_BYTES_MARKER,
    RAW_SOURCE_PATH,
    assert_identifier_scoped,
    fixture_privacy_payloads,
    json_dict,
    raw_pii_found,
)


def test_document_permission_payload_json_is_identifier_scoped() -> None:
    try:
        from ummaya.tools.documents.permissions import (
            DocumentArtifactPermissionKind,
            DocumentArtifactPermissionPayload,
            build_document_artifact_permission,
        )
    except ImportError as exc:
        pytest.fail(f"Document artifact permission API is missing: {exc}")

    payload = build_document_artifact_permission(
        kind=DocumentArtifactPermissionKind.write_derivative_artifact,
        tool_id="document_apply_fill",
        correlation_id="corr-doc-privacy-001",
        artifact_id="artifact-source-001",
        derivative_artifact_id="artifact-derivative-001",
        validation_report_id="validation-report-001",
        intended_change_class="fill_fields",
        validation_status="not_validated",
    )

    assert isinstance(payload, DocumentArtifactPermissionPayload)
    encoded = json_dict(payload.model_dump_json())

    assert encoded["correlation_id"] == "corr-doc-privacy-001"
    assert encoded["artifact_id"] == "artifact-source-001"
    assert encoded["derivative_artifact_id"] == "artifact-derivative-001"
    assert encoded["validation_report_id"] == "validation-report-001"
    assert_identifier_scoped(encoded)


def test_document_tool_result_json_redacts_raw_document_inputs() -> None:
    try:
        from ummaya.tools.documents.models import (
            DocumentExtraction,
            DocumentToolResult,
            ParagraphBlock,
            ToolResultStatus,
        )
    except ImportError as exc:
        pytest.fail(f"Document tool result API is missing: {exc}")

    result = DocumentToolResult(
        tool_id="document_extract",
        correlation_id="corr-doc-privacy-002",
        status=ToolResultStatus.ok,
        artifact_refs=["artifact-source-002"],
        extraction=DocumentExtraction(
            artifact_id="artifact-source-002",
            paragraphs=[
                ParagraphBlock(
                    block_id="paragraph-001",
                    text="Extracted visible form text.",
                    source_path=RAW_SOURCE_PATH,
                )
            ],
            warnings=[RAW_BYTES_MARKER],
        ),
        text_summary="Document extraction completed without exposing raw inputs.",
    )

    encoded = json_dict(result.model_dump_json())

    assert encoded["correlation_id"] == "corr-doc-privacy-002"
    assert encoded["artifact_refs"] == ["artifact-source-002"]
    assert_identifier_scoped(encoded)


def test_document_evidence_record_json_is_hash_and_id_scoped() -> None:
    try:
        from ummaya.evidence.document_harness import DocumentEvidenceRecord
    except ImportError as exc:
        pytest.fail(f"Document evidence record API is missing: {exc}")

    record = DocumentEvidenceRecord(
        record_id="doc-evidence-privacy-001",
        scenario_id="document_harness_v1",
        correlation_id="corr-doc-privacy-003",
        source_artifact_id="artifact-source-003",
        source_sha256=HASH_A,
        derivative_artifact_id="artifact-derivative-003",
        derivative_sha256=HASH_B,
        structured_diff_id="structured-diff-003",
        structured_diff_sha256=HASH_C,
        render_artifact_ids=("render-page-003",),
        validation_report_id="validation-report-003",
        validation_report_sha256=HASH_D,
        readiness="ready_for_review",
    )

    encoded = json_dict(record.model_dump_json())

    assert encoded["correlation_id"] == "corr-doc-privacy-003"
    assert encoded["source_artifact_id"] == "artifact-source-003"
    assert encoded["source_sha256"] == HASH_A
    assert encoded["derivative_artifact_id"] == "artifact-derivative-003"
    assert encoded["derivative_sha256"] == HASH_B
    assert encoded["validation_report_id"] == "validation-report-003"
    assert encoded["validation_report_sha256"] == HASH_D
    assert_identifier_scoped(encoded)


def test_authoring_evidence_json_redacts_raw_document_inputs() -> None:
    from ummaya.tools.documents.authoring import AuthoringEvidenceItem, EvidenceSourceKind

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-privacy-001",
        source_kind=EvidenceSourceKind.user_provided,
        summary=f"사용자가 {RAW_SOURCE_PATH} 파일과 {RAW_BYTES_MARKER} 값을 언급했다.",
        source_ref="turn-privacy.answer-1",
        redacted_excerpt=f"{RAW_SOURCE_PATH}\n{RAW_BYTES_MARKER}",
    )

    encoded = json_dict(evidence.model_dump_json())

    assert encoded["evidence_id"] == "evidence-privacy-001"
    assert_identifier_scoped(encoded)


def test_authoring_evidence_json_redacts_common_pii_patterns() -> None:
    from ummaya.tools.documents.authoring import AuthoringEvidenceItem, EvidenceSourceKind

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-privacy-pii-001",
        source_kind=EvidenceSourceKind.user_provided,
        summary="연락처 010-1234-5678, 이메일 citizen@example.kr, 주민번호 900101-1234567",
        source_ref="turn-privacy.answer-2",
        redacted_excerpt="citizen@example.kr / 010-1234-5678 / 900101-1234567",
    )

    encoded = json_dict(evidence.model_dump_json())
    payload = json.dumps(encoded, ensure_ascii=False, sort_keys=True)

    assert "010-1234-5678" not in payload
    assert "citizen@example.kr" not in payload
    assert "900101-1234567" not in payload
    assert not raw_pii_found(payload)


def test_authoring_metadata_json_redacts_local_paths() -> None:
    from ummaya.tools.documents.authoring import (
        AmbiguityClassification,
        AmbiguityRecord,
        AuthoringEvidenceItem,
        EvidenceSourceKind,
    )

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-privacy-source-ref",
        source_kind=EvidenceSourceKind.document_derived,
        summary="Source reference must stay identifier scoped.",
        source_ref=RAW_SOURCE_PATH,
    )
    ambiguity = AmbiguityRecord(
        ambiguity_id="ambiguity-privacy-path",
        classification=AmbiguityClassification.blocking,
        evidence_path=RAW_SOURCE_PATH,
        required_next_question="근거 파일 경로 대신 안전한 증거 식별자를 제공해야 합니다.",
    )

    encoded = json_dict(evidence.model_dump_json())
    ambiguity_encoded = json_dict(ambiguity.model_dump_json())

    assert encoded["source_ref"] == "[redacted-document-content]"
    assert ambiguity_encoded["evidence_path"] == "[redacted-document-content]"
    assert_identifier_scoped(encoded)
    assert_identifier_scoped(ambiguity_encoded)


def test_authoring_answer_and_draft_json_redact_raw_document_inputs() -> None:
    from ummaya.tools.documents.authoring import (
        DraftCandidate,
        DraftClaim,
        UserAnswer,
        hash_authoring_text,
    )

    answer = UserAnswer(
        answer_id="answer-privacy-001",
        question_id="question-privacy-001",
        response_summary=f"사용자 답변에 {RAW_SOURCE_PATH} 경로가 포함되었다.",
        evidence_refs=("evidence-privacy-001",),
    )
    draft_text = f"초안에 {RAW_BYTES_MARKER} 값을 넣으면 안 됩니다."
    draft = DraftCandidate(
        draft_id="draft-privacy-001",
        target_id="self_intro.privacy",
        draft_text=draft_text,
        draft_sha256=hash_authoring_text(draft_text),
        claims=(
            DraftClaim(
                claim_id="claim-privacy-001",
                text=f"청구 문장에 {RAW_SOURCE_PATH} 경로가 포함되었다.",
                evidence_refs=("evidence-privacy-001",),
            ),
        ),
    )

    encoded_answer = json_dict(answer.model_dump_json())
    encoded_draft = json_dict(draft.model_dump_json())

    assert encoded_answer["response_summary"] == "[redacted-document-content]"
    assert encoded_draft["draft_text"] == "[redacted-document-content]"
    assert encoded_draft["claims"][0]["text"] == "[redacted-document-content]"
    assert_identifier_scoped(encoded_answer)
    assert_identifier_scoped(encoded_draft)


def test_document_fixtures_do_not_contain_raw_pii() -> None:
    from ummaya.tools.documents.fixtures import load_fixture_manifest

    manifest = load_fixture_manifest()
    for payload in fixture_privacy_payloads(manifest):
        assert RAW_SOURCE_PATH not in payload
        assert RAW_BYTES_MARKER not in payload
        assert not raw_pii_found(payload)
