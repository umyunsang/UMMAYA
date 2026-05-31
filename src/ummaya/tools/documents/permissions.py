# SPDX-License-Identifier: Apache-2.0
"""Document artifact permission payloads for local harness operations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentToolResult,
    ToolResultStatus,
)


class DocumentArtifactPermissionKind(StrEnum):
    """Permission boundary for one document harness tool call."""

    read_local_artifact = "read_local_artifact"
    write_derivative_artifact = "write_derivative_artifact"
    validate_local_artifact = "validate_local_artifact"


class DocumentArtifactPermissionPayload(BaseModel):
    """Minimal PermissionRequest payload for document artifacts.

    The payload intentionally carries artifact/report identifiers only. It does
    not expose source paths or inline bytes to the model-facing permission layer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: DocumentArtifactPermissionKind
    tool_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    derivative_artifact_id: str | None = Field(default=None, min_length=1)
    validation_report_id: str | None = Field(default=None, min_length=1)
    intended_change_class: str | None = Field(default=None, min_length=1, max_length=80)
    validation_status: str | None = Field(default=None, min_length=1, max_length=80)
    requires_approval: bool

    @model_validator(mode="after")
    def _enforce_approval_boundary(self) -> DocumentArtifactPermissionPayload:
        if (
            self.kind is DocumentArtifactPermissionKind.write_derivative_artifact
            and not self.requires_approval
        ):
            raise ValueError("write_derivative_artifact permission requires approval")
        if (
            self.kind is not DocumentArtifactPermissionKind.write_derivative_artifact
            and self.requires_approval
        ):
            raise ValueError("read and validation document permissions do not require approval")
        return self


def build_document_artifact_permission(
    *,
    kind: DocumentArtifactPermissionKind,
    tool_id: str,
    correlation_id: str,
    artifact_id: str,
    derivative_artifact_id: str | None = None,
    validation_report_id: str | None = None,
    intended_change_class: str | None = None,
    validation_status: str | None = None,
) -> DocumentArtifactPermissionPayload:
    """Build the identifier-only permission payload for a document tool call."""
    return DocumentArtifactPermissionPayload(
        kind=kind,
        tool_id=tool_id,
        correlation_id=correlation_id,
        artifact_id=artifact_id,
        derivative_artifact_id=derivative_artifact_id,
        validation_report_id=validation_report_id,
        intended_change_class=intended_change_class,
        validation_status=validation_status,
        requires_approval=kind is DocumentArtifactPermissionKind.write_derivative_artifact,
    )


def document_permission_denied_result(
    *,
    tool_id: str,
    correlation_id: str,
    artifact_id: str,
    derivative_artifact_id: str | None = None,
) -> DocumentToolResult:
    """Return a typed blocked result when the user denies a document write."""
    artifact_refs = [artifact_id]
    if derivative_artifact_id is not None:
        artifact_refs.append(derivative_artifact_id)
    return DocumentToolResult(
        tool_id=tool_id,
        correlation_id=correlation_id,
        status=ToolResultStatus.blocked,
        artifact_refs=artifact_refs,
        text_summary="Document write permission was denied by the user.",
        blocked_reason=BlockedReason.permission_denied,
    )


__all__ = [
    "DocumentArtifactPermissionKind",
    "DocumentArtifactPermissionPayload",
    "build_document_artifact_permission",
    "document_permission_denied_result",
]
