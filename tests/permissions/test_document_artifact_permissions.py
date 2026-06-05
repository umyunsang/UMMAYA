# SPDX-License-Identifier: Apache-2.0
"""TDD coverage for Public AX document artifact permission payloads."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentToolResult,
    ToolResultStatus,
)
from ummaya.tools.documents.permissions import (
    DocumentArtifactPermissionKind,
    DocumentArtifactPermissionPayload,
    build_document_artifact_permission,
    document_permission_denied_result,
)


def test_read_local_artifact_permission_does_not_require_approval() -> None:
    payload = build_document_artifact_permission(
        kind=DocumentArtifactPermissionKind.read_local_artifact,
        tool_id="document_inspect",
        correlation_id="corr-doc-read-001",
        artifact_id="artifact-source-001",
    )

    assert isinstance(payload, DocumentArtifactPermissionPayload)
    assert payload.kind == DocumentArtifactPermissionKind.read_local_artifact
    assert payload.requires_approval is False
    assert payload.artifact_id == "artifact-source-001"


def test_write_derivative_artifact_permission_requires_approval() -> None:
    payload = build_document_artifact_permission(
        kind=DocumentArtifactPermissionKind.write_derivative_artifact,
        tool_id="document_apply_fill",
        correlation_id="corr-doc-write-001",
        artifact_id="artifact-source-001",
        derivative_artifact_id="artifact-derivative-001",
        intended_change_class="fill_fields",
        validation_status="not_validated",
    )

    assert payload.kind == DocumentArtifactPermissionKind.write_derivative_artifact
    assert payload.requires_approval is True
    assert payload.artifact_id == "artifact-source-001"
    assert payload.derivative_artifact_id == "artifact-derivative-001"
    assert payload.intended_change_class == "fill_fields"
    assert payload.validation_status == "not_validated"


def test_validate_local_artifact_payload_keeps_only_artifact_and_report_ids() -> None:
    payload = build_document_artifact_permission(
        kind=DocumentArtifactPermissionKind.validate_local_artifact,
        tool_id="document_validate_public_form",
        correlation_id="corr-doc-validate-001",
        artifact_id="artifact-derivative-001",
        validation_report_id="validation-report-001",
    )

    assert payload.model_dump(exclude_none=True) == {
        "kind": DocumentArtifactPermissionKind.validate_local_artifact,
        "tool_id": "document_validate_public_form",
        "correlation_id": "corr-doc-validate-001",
        "artifact_id": "artifact-derivative-001",
        "validation_report_id": "validation-report-001",
        "requires_approval": False,
    }


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("raw_bytes", b"%PDF-1.7 local document bytes"),
        ("source_path", "/Users/example/Documents/public-form.pdf"),
    ],
)
def test_permission_payload_forbids_raw_bytes_and_source_path(
    field_name: str,
    field_value: bytes | str,
) -> None:
    payload_data = {
        "kind": "read_local_artifact",
        "tool_id": "document_inspect",
        "correlation_id": "corr-doc-read-002",
        "artifact_id": "artifact-source-002",
        "requires_approval": False,
        field_name: field_value,
    }

    with pytest.raises(ValidationError):
        DocumentArtifactPermissionPayload.model_validate(payload_data)


def test_denied_write_returns_blocked_document_tool_result() -> None:
    result = document_permission_denied_result(
        tool_id="document_save",
        correlation_id="corr-doc-write-denied-001",
        artifact_id="artifact-source-001",
        derivative_artifact_id="artifact-derivative-001",
    )

    assert isinstance(result, DocumentToolResult)
    assert result.status == ToolResultStatus.blocked
    assert result.blocked_reason == BlockedReason.permission_denied
