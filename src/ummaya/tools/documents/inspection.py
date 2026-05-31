# SPDX-License-Identifier: Apache-2.0
"""Inspection orchestration for engine-backed local document artifacts."""

from __future__ import annotations

import logging
from pathlib import Path

from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
    UnsupportedDocumentEngineError,
)
from ummaya.tools.documents.intake import DocumentIntakePolicy, inspect_document_intake
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentExtraction,
    DocumentSecurityFinding,
    DocumentToolResult,
    ToolResultStatus,
)

logger = logging.getLogger(__name__)


def inspect_document(
    source_path: str | Path,
    *,
    expected_format: str | object | None = None,
    declared_mime_type: str | None = None,
    policy: DocumentIntakePolicy | None = None,
    engine_registry: DocumentEngineRegistry | None = None,
) -> DocumentToolResult:
    """Inspect a document through intake, promoted engine delegation, and typed result."""
    intake_result = inspect_document_intake(
        source_path,
        expected_format=expected_format,
        declared_mime_type=declared_mime_type,
        policy=policy,
    )
    if intake_result.status is not ToolResultStatus.ok:
        return DocumentToolResult(
            tool_id="document_inspect",
            correlation_id=intake_result.correlation_id,
            status=ToolResultStatus.blocked,
            artifact_refs=intake_result.artifact_refs,
            findings=list(intake_result.findings),
            text_summary=intake_result.text_summary,
            blocked_reason=intake_result.blocked_reason or BlockedReason.unsupported_format,
        )

    if intake_result.detected_format is None:
        return DocumentToolResult(
            tool_id="document_inspect",
            correlation_id=intake_result.correlation_id,
            status=ToolResultStatus.blocked,
            artifact_refs=intake_result.artifact_refs,
            findings=list(intake_result.findings),
            text_summary="Document inspection blocked: detected format is unavailable.",
            blocked_reason=BlockedReason.signature_mismatch,
        )

    registry = engine_registry or DocumentEngineRegistry()
    try:
        engine = registry.require(intake_result.detected_format)
    except UnsupportedDocumentEngineError:
        return DocumentToolResult(
            tool_id="document_inspect",
            correlation_id=intake_result.correlation_id,
            status=ToolResultStatus.blocked,
            artifact_refs=intake_result.artifact_refs,
            findings=[
                DocumentSecurityFinding(
                    finding_id="inspection-unsupported-engine",
                    severity="blocked",
                    code=BlockedReason.unsupported_operation,
                    message=(
                        "Document inspection requires a promoted engine for "
                        f"{intake_result.detected_format.value}."
                    ),
                )
            ],
            text_summary=(
                "Document inspection blocked: no promoted engine is registered "
                f"for {intake_result.detected_format.value}."
            ),
            blocked_reason=BlockedReason.unsupported_operation,
        )

    try:
        extraction = engine.inspect(Path(source_path), artifact_id=intake_result.correlation_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "document inspection engine %s failed for %s: %s",
            engine.engine_id,
            intake_result.detected_format.value,
            exc,
        )
        return DocumentToolResult(
            tool_id="document_inspect",
            correlation_id=intake_result.correlation_id,
            status=ToolResultStatus.blocked,
            artifact_refs=intake_result.artifact_refs,
            findings=[
                DocumentSecurityFinding(
                    finding_id="inspection-engine-parse-error",
                    severity="blocked",
                    code=BlockedReason.corrupt,
                    message=(
                        f"Document inspection engine {engine.engine_id} could not parse "
                        f"the {intake_result.detected_format.value} artifact."
                    ),
                )
            ],
            text_summary=(
                f"Document inspection blocked: {engine.engine_id} could not parse "
                f"the {intake_result.detected_format.value} artifact."
            ),
            blocked_reason=BlockedReason.corrupt,
        )
    return DocumentToolResult(
        tool_id="document_inspect",
        correlation_id=intake_result.correlation_id,
        status=ToolResultStatus.ok,
        artifact_refs=intake_result.artifact_refs,
        extraction=extraction,
        findings=[],
        text_summary=(
            f"Document inspection via {engine.engine_id} extracted "
            f"{len(extraction.paragraphs)} paragraph blocks, "
            f"{len(extraction.tables)} tables, and {len(extraction.fields)} fields."
        ),
    )


def empty_extraction(artifact_id: str, *, warning: str | None = None) -> DocumentExtraction:
    """Build an empty extraction with an optional warning."""
    return DocumentExtraction(
        artifact_id=artifact_id,
        warnings=[warning] if warning is not None else [],
    )
