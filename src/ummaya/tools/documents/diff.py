# SPDX-License-Identifier: Apache-2.0
"""Structured derivative diff generation for document patches."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.models import DocumentPatch, OperationType

DocumentChangeType = Literal["field", "table_cell", "text", "style", "metadata", "copy"]


class DocumentChange(BaseModel):
    """One structured change derived from a document patch operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    change_id: str
    operation_id: str
    change_type: DocumentChangeType
    target_path: str
    before_value: str | None = None
    after_value: str | None = None


class RenderArtifactRecord(BaseModel):
    """One reviewer-readable render artifact tied to a derivative hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    render_artifact_id: str
    source_artifact_id: str
    source_sha256: str
    render_sha256: str
    render_path: Path
    page_number: int = Field(ge=1)
    correlation_id: str
    engine_id: str


class DocumentDiff(BaseModel):
    """Diff between one working artifact and its derivative."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_artifact_id: str
    derivative_artifact_id: str
    changes: tuple[DocumentChange, ...]
    render_artifacts: tuple[RenderArtifactRecord, ...] = ()


def diff_from_patch(
    patch: DocumentPatch,
    *,
    source_artifact_id: str,
    derivative_artifact_id: str,
    render_artifacts: tuple[RenderArtifactRecord, ...] = (),
) -> DocumentDiff:
    """Build a structured diff from an ordered patch request."""
    return DocumentDiff(
        source_artifact_id=source_artifact_id,
        derivative_artifact_id=derivative_artifact_id,
        changes=tuple(
            DocumentChange(
                change_id=f"change-{index:03d}",
                operation_id=operation.operation_id,
                change_type=_change_type(operation.operation_type),
                target_path=operation.target_path,
                after_value=str(operation.value) if operation.value is not None else None,
            )
            for index, operation in enumerate(patch.operations, start=1)
        ),
        render_artifacts=render_artifacts,
    )


def _change_type(operation_type: OperationType) -> DocumentChangeType:
    if operation_type is OperationType.set_field_value:
        return "field"
    if operation_type is OperationType.set_table_cell:
        return "table_cell"
    if operation_type is OperationType.replace_text:
        return "text"
    if operation_type in {
        OperationType.set_paragraph_style,
        OperationType.set_run_style,
        OperationType.set_cell_style,
    }:
        return "style"
    if operation_type is OperationType.set_document_metadata:
        return "metadata"
    return "copy"
