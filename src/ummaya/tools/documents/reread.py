# SPDX-License-Identifier: Apache-2.0
"""Derivative re-read comparison against intended document patches."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
    UnsupportedDocumentEngineError,
)
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentArtifact,
    DocumentExtraction,
    DocumentPatch,
    DocumentPatchOperation,
    OperationType,
    ScalarValue,
    ToolResultStatus,
)


class ReReadMismatch(BaseModel):
    """One intended value that was not observed after saving and re-reading."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: str
    target_path: str
    expected_value: str
    observed_value: str | None = None


class DocumentReReadResult(BaseModel):
    """Result of re-reading a saved derivative artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ToolResultStatus
    correlation_id: str
    artifact_id: str
    extraction: DocumentExtraction
    mismatches: tuple[ReReadMismatch, ...] = ()
    round_trip_passed: bool
    blocked_reason: BlockedReason | None = None
    text_summary: str


def reread_derivative(
    artifact: DocumentArtifact,
    patch: DocumentPatch,
    *,
    engine_registry: DocumentEngineRegistry,
    correlation_id: str,
) -> DocumentReReadResult:
    """Re-read a derivative and compare observed values with the patch intent."""
    if patch.target_artifact_id != artifact.artifact_id:
        extraction = DocumentExtraction(artifact_id=artifact.artifact_id)
        return DocumentReReadResult(
            status=ToolResultStatus.blocked,
            correlation_id=correlation_id,
            artifact_id=artifact.artifact_id,
            extraction=extraction,
            round_trip_passed=False,
            blocked_reason=BlockedReason.validation_failed,
            text_summary="Patch target does not match the derivative artifact.",
        )
    try:
        engine = engine_registry.require(artifact.format)
    except UnsupportedDocumentEngineError:
        extraction = DocumentExtraction(artifact_id=artifact.artifact_id)
        return DocumentReReadResult(
            status=ToolResultStatus.blocked,
            correlation_id=correlation_id,
            artifact_id=artifact.artifact_id,
            extraction=extraction,
            round_trip_passed=False,
            blocked_reason=BlockedReason.unsupported_operation,
            text_summary=f"No inspection engine is registered for {artifact.format.value}.",
        )

    extraction = engine.inspect(Path(artifact.source_path), artifact_id=artifact.artifact_id)
    mismatches = tuple(
        mismatch
        for operation in patch.operations
        if (mismatch := _operation_mismatch(operation, extraction)) is not None
    )
    passed = len(mismatches) == 0
    return DocumentReReadResult(
        status=ToolResultStatus.ok if passed else ToolResultStatus.blocked,
        correlation_id=correlation_id,
        artifact_id=artifact.artifact_id,
        extraction=extraction,
        mismatches=mismatches,
        round_trip_passed=passed,
        blocked_reason=None if passed else BlockedReason.validation_failed,
        text_summary=(
            "Derivative re-read matched all intended patch values."
            if passed
            else f"Derivative re-read found {len(mismatches)} mismatched intended value(s)."
        ),
    )


def _operation_mismatch(
    operation: DocumentPatchOperation,
    extraction: DocumentExtraction,
) -> ReReadMismatch | None:
    if operation.operation_type not in {
        OperationType.set_field_value,
        OperationType.set_table_cell,
        OperationType.replace_text,
        OperationType.insert_paragraph,
        OperationType.set_document_metadata,
    }:
        return None
    expected = _string_value(operation.value)
    observed = _observed_value(operation, extraction)
    if observed == expected:
        return None
    return ReReadMismatch(
        operation_id=operation.operation_id,
        target_path=operation.target_path,
        expected_value=expected,
        observed_value=observed,
    )


def _observed_value(
    operation: DocumentPatchOperation,
    extraction: DocumentExtraction,
) -> str | None:
    if operation.operation_type is OperationType.set_field_value:
        for field in extraction.fields:
            if field.path == operation.target_path:
                return _string_value(field.current_value)
        return None
    if operation.operation_type is OperationType.set_table_cell:
        for table in extraction.tables:
            for cell in table.cells:
                if cell.source_path == operation.target_path:
                    return cell.text
        return None
    if operation.operation_type is OperationType.set_document_metadata:
        return _string_value(extraction.metadata.get(operation.target_path))
    expected = _string_value(operation.value)
    text_parts = [paragraph.text for paragraph in extraction.paragraphs]
    text_parts.extend(cell.text for table in extraction.tables for cell in table.cells)
    observed_text = "\n".join(text_parts)
    return expected if expected in observed_text else None


def _string_value(value: ScalarValue) -> str:
    return "" if value is None else str(value)
