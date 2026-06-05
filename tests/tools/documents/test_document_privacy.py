# SPDX-License-Identifier: Apache-2.0
"""T073 privacy tests for document permission, result, and evidence JSON."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64
_RAW_SOURCE_PATH = "/Users/example/private/civil-form.pdf"
_RAW_BYTES_MARKER = "%PDF-1.7 raw document bytes"
_FORBIDDEN_KEYS = frozenset(
    {
        "document_bytes",
        "raw_bytes",
        "source_bytes",
        "source_path",
    }
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
    encoded = _json_dict(payload.model_dump_json())

    assert encoded["correlation_id"] == "corr-doc-privacy-001"
    assert encoded["artifact_id"] == "artifact-source-001"
    assert encoded["derivative_artifact_id"] == "artifact-derivative-001"
    assert encoded["validation_report_id"] == "validation-report-001"
    _assert_identifier_scoped(encoded)


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
                    source_path=_RAW_SOURCE_PATH,
                )
            ],
            warnings=[_RAW_BYTES_MARKER],
        ),
        text_summary="Document extraction completed without exposing raw inputs.",
    )

    encoded = _json_dict(result.model_dump_json())

    assert encoded["correlation_id"] == "corr-doc-privacy-002"
    assert encoded["artifact_refs"] == ["artifact-source-002"]
    _assert_identifier_scoped(encoded)


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
        source_sha256=_HASH_A,
        derivative_artifact_id="artifact-derivative-003",
        derivative_sha256=_HASH_B,
        structured_diff_id="structured-diff-003",
        structured_diff_sha256=_HASH_C,
        render_artifact_ids=("render-page-003",),
        validation_report_id="validation-report-003",
        validation_report_sha256=_HASH_D,
        readiness="ready_for_review",
    )

    encoded = _json_dict(record.model_dump_json())

    assert encoded["correlation_id"] == "corr-doc-privacy-003"
    assert encoded["source_artifact_id"] == "artifact-source-003"
    assert encoded["source_sha256"] == _HASH_A
    assert encoded["derivative_artifact_id"] == "artifact-derivative-003"
    assert encoded["derivative_sha256"] == _HASH_B
    assert encoded["validation_report_id"] == "validation-report-003"
    assert encoded["validation_report_sha256"] == _HASH_D
    _assert_identifier_scoped(encoded)


def _json_dict(payload: str) -> dict[str, Any]:
    decoded = json.loads(payload)
    assert isinstance(decoded, dict)
    return decoded


def _assert_identifier_scoped(payload: Mapping[str, Any]) -> None:
    forbidden_key_paths = _find_forbidden_key_paths(payload)
    assert forbidden_key_paths == []
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert _RAW_SOURCE_PATH not in encoded
    assert _RAW_BYTES_MARKER not in encoded


def _find_forbidden_key_paths(value: object, prefix: str = "$") -> list[str]:
    if isinstance(value, Mapping):
        matches: list[str] = []
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if key in _FORBIDDEN_KEYS:
                matches.append(path)
            matches.extend(_find_forbidden_key_paths(item, path))
        return matches
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        matches = []
        for index, item in enumerate(value):
            matches.extend(_find_forbidden_key_paths(item, f"{prefix}[{index}]"))
        return matches
    return []
