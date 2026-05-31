# SPDX-License-Identifier: Apache-2.0
"""Engine-backed document patch harness."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.diff import DocumentDiff, diff_from_patch
from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
    UnsupportedDocumentEngineError,
)
from ummaya.tools.documents.models import (
    ArtifactLineage,
    BlockedReason,
    DocumentArtifact,
    DocumentPatch,
    ToolResultStatus,
)
from ummaya.tools.documents.style import DocumentPatchValidationError, validate_document_patch


class DocumentPatchResult(BaseModel):
    """Result of a copy or patch operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ToolResultStatus
    source_artifact: DocumentArtifact
    derivative_artifact: DocumentArtifact | None = None
    diff: DocumentDiff | None = None
    blocked_reason: BlockedReason | None = None
    text_summary: str


def copy_for_edit(
    store: DocumentArtifactStore,
    source: DocumentArtifact,
    *,
    artifact_id: str,
    destination_name: str,
) -> DocumentArtifact:
    """Create a working copy without mutating the source artifact."""
    payload = Path(source.source_path).read_bytes()
    return store.write_derivative(
        source,
        artifact_id=artifact_id,
        lineage=ArtifactLineage.working_copy,
        destination_name=destination_name,
        payload=payload,
    )


def apply_document_patch(
    store: DocumentArtifactStore,
    working_artifact: DocumentArtifact,
    patch: DocumentPatch,
    *,
    engine_registry: DocumentEngineRegistry,
    artifact_id: str,
    destination_name: str,
) -> DocumentPatchResult:
    """Apply an ordered patch through a promoted mutation engine."""
    if patch.target_artifact_id != working_artifact.artifact_id:
        return _blocked(
            working_artifact,
            BlockedReason.validation_failed,
            "Document patch target does not match the working artifact.",
        )
    if patch.expected_format is not working_artifact.format:
        return _blocked(
            working_artifact,
            BlockedReason.validation_failed,
            "Document patch expected_format does not match the working artifact.",
        )

    try:
        validate_document_patch(patch)
        engine = engine_registry.require_mutation(working_artifact.format)
    except DocumentPatchValidationError as exc:
        return _blocked(working_artifact, BlockedReason.validation_failed, str(exc))
    except UnsupportedDocumentEngineError:
        return _blocked(
            working_artifact,
            BlockedReason.unsupported_operation,
            f"No mutation-capable engine is registered for {working_artifact.format.value}.",
        )

    try:
        payload = engine.apply_patch(Path(working_artifact.source_path), patch)
    except ValueError as exc:
        return _blocked(working_artifact, BlockedReason.validation_failed, str(exc))
    derivative = store.write_derivative(
        working_artifact,
        artifact_id=artifact_id,
        lineage=ArtifactLineage.working_copy,
        destination_name=destination_name,
        payload=payload,
    )
    return DocumentPatchResult(
        status=ToolResultStatus.ok,
        source_artifact=working_artifact,
        derivative_artifact=derivative,
        diff=diff_from_patch(
            patch,
            source_artifact_id=working_artifact.artifact_id,
            derivative_artifact_id=derivative.artifact_id,
        ),
        text_summary=(
            f"Applied {len(patch.operations)} document patch operation(s) "
            f"through {engine.engine_id}."
        ),
    )


def _blocked(
    source: DocumentArtifact,
    reason: BlockedReason,
    message: str,
) -> DocumentPatchResult:
    return DocumentPatchResult(
        status=ToolResultStatus.blocked,
        source_artifact=source,
        blocked_reason=reason,
        text_summary=message,
    )
