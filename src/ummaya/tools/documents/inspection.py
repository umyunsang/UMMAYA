# SPDX-License-Identifier: Apache-2.0
"""Inspection orchestration for engine-backed local document artifacts."""

from __future__ import annotations

import logging
from pathlib import Path

from ummaya.tools.documents.adapter_registry import (
    DocumentAdapterRegistry,
    UnsupportedDocumentAdapterError,
    build_document_adapter_registry_from_engine_registry,
)
from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
)
from ummaya.tools.documents.intake import DocumentIntakePolicy, inspect_document_intake
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentExtraction,
    DocumentFormat,
    DocumentFormatFamily,
    DocumentIntakeResult,
    DocumentSecurityFinding,
    DocumentToolResult,
    ToolResultStatus,
)

logger = logging.getLogger(__name__)
_PASSIVE_READ_FAMILIES = frozenset(
    {
        DocumentFormatFamily.odf,
        DocumentFormatFamily.text_web_export,
        DocumentFormatFamily.data_file,
        DocumentFormatFamily.image_scan,
        DocumentFormatFamily.legacy_office,
        DocumentFormatFamily.geospatial_data,
        DocumentFormatFamily.media_asset,
        DocumentFormatFamily.code_file,
        DocumentFormatFamily.archive,
    }
)


def inspect_document(
    source_path: str | Path,
    *,
    expected_format: str | object | None = None,
    declared_mime_type: str | None = None,
    policy: DocumentIntakePolicy | None = None,
    engine_registry: DocumentEngineRegistry | None = None,
    adapter_registry: DocumentAdapterRegistry | None = None,
) -> DocumentToolResult:
    """Inspect a document through intake, promoted engine delegation, and typed result."""
    intake_result = inspect_document_intake(
        source_path,
        expected_format=expected_format,
        declared_mime_type=declared_mime_type,
        policy=policy,
    )
    if intake_result.status is not ToolResultStatus.ok:
        passive_result = _inspect_passive_known_only_document(
            intake_result,
            source_path=Path(source_path),
            adapter_registry=adapter_registry,
            engine_registry=engine_registry,
        )
        if passive_result is not None:
            return passive_result
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

    registry = _adapter_registry_for(
        adapter_registry=adapter_registry,
        engine_registry=engine_registry,
    )
    try:
        adapter = registry.require_promoted(intake_result.detected_format)
    except UnsupportedDocumentAdapterError:
        text_summary = (
            _hwp_unsupported_summary()
            if intake_result.detected_format is DocumentFormat.hwp
            else (
                "Document inspection blocked: no promoted adapter is registered "
                f"for {intake_result.detected_format.value}."
            )
        )
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
                        "Document inspection requires a promoted adapter for "
                        f"{intake_result.detected_format.value}."
                    ),
                )
            ],
            text_summary=text_summary,
            blocked_reason=BlockedReason.unsupported_operation,
        )

    try:
        extraction = adapter.inspect(Path(source_path), artifact_id=intake_result.correlation_id)
    except Exception as exc:  # noqa: BLE001
        adapter_label = _adapter_label(adapter)
        logger.warning(
            "document inspection adapter %s failed for %s: %s",
            adapter_label,
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
                        f"Document inspection adapter {adapter_label} could not parse "
                        f"the {intake_result.detected_format.value} artifact."
                    ),
                )
            ],
            text_summary=(
                f"Document inspection blocked: {adapter_label} could not parse "
                f"the {intake_result.detected_format.value} artifact."
            ),
            blocked_reason=BlockedReason.corrupt,
        )
    adapter_label = _adapter_label(adapter)
    return DocumentToolResult(
        tool_id="document_inspect",
        correlation_id=intake_result.correlation_id,
        status=ToolResultStatus.ok,
        artifact_refs=intake_result.artifact_refs,
        extraction=extraction,
        findings=[],
        text_summary=(
            f"Document inspection via {adapter_label} extracted "
            f"{len(extraction.paragraphs)} paragraph blocks, "
            f"{len(extraction.tables)} tables, and {len(extraction.fields)} fields."
        ),
    )


def _inspect_passive_known_only_document(
    intake_result: DocumentIntakeResult,
    *,
    source_path: Path,
    adapter_registry: DocumentAdapterRegistry | None,
    engine_registry: DocumentEngineRegistry | None,
) -> DocumentToolResult | None:
    known_format = getattr(intake_result, "known_format", None)
    format_family = getattr(intake_result, "format_family", None)
    blocked_reason = getattr(intake_result, "blocked_reason", None)
    if (
        blocked_reason is not BlockedReason.unsupported_operation
        or known_format is None
        or format_family not in _PASSIVE_READ_FAMILIES
    ):
        return None

    registry = _adapter_registry_for(
        adapter_registry=adapter_registry,
        engine_registry=engine_registry,
    )
    try:
        adapter = registry.require_known(known_format)
    except UnsupportedDocumentAdapterError:
        return None
    if getattr(adapter, "promoted_formats", ()):
        return None

    try:
        extraction = adapter.inspect(source_path, artifact_id=intake_result.correlation_id)
    except Exception as exc:  # noqa: BLE001
        adapter_label = _adapter_label(adapter)
        logger.warning(
            "passive document inspection adapter %s failed for %s: %s",
            adapter_label,
            known_format.value,
            exc,
        )
        return DocumentToolResult(
            tool_id="document_inspect",
            correlation_id=intake_result.correlation_id,
            status=ToolResultStatus.blocked,
            artifact_refs=[],
            findings=[
                DocumentSecurityFinding(
                    finding_id="passive-inspection-parse-error",
                    severity="blocked",
                    code=BlockedReason.corrupt,
                    message=(
                        f"Document known-only adapter {adapter_label} could not parse "
                        f"the {known_format.value} artifact."
                    ),
                )
            ],
            text_summary=(
                f"Document known-only inspection blocked: {adapter_label} could not parse "
                f"the {known_format.value} artifact."
            ),
            blocked_reason=BlockedReason.corrupt,
        )

    adapter_label = _adapter_label(adapter)
    return DocumentToolResult(
        tool_id="document_inspect",
        correlation_id=intake_result.correlation_id,
        status=ToolResultStatus.ok,
        artifact_refs=[],
        extraction=extraction,
        findings=[],
        text_summary=(
            f"Document known-only inspection via {adapter_label} extracted "
            f"{len(extraction.paragraphs)} paragraph blocks, "
            f"{len(extraction.tables)} tables, {len(extraction.images)} images, "
            f"and {len(extraction.fields)} fields. This format remains known-only "
            "and read-only; mutation, render, and save are not promoted."
        ),
    )


def _adapter_registry_for(
    *,
    adapter_registry: DocumentAdapterRegistry | None,
    engine_registry: DocumentEngineRegistry | None,
) -> DocumentAdapterRegistry:
    if adapter_registry is not None:
        return adapter_registry
    if engine_registry is not None:
        return build_document_adapter_registry_from_engine_registry(engine_registry)
    return DocumentAdapterRegistry()


def _adapter_label(adapter: object) -> str:
    engine_id = getattr(adapter, "engine_id", None)
    if isinstance(engine_id, str) and engine_id:
        return engine_id
    adapter_id = getattr(adapter, "adapter_id", None)
    if isinstance(adapter_id, str) and adapter_id:
        return adapter_id
    return "unknown-document-adapter"


def _hwp_unsupported_summary() -> str:
    return (
        "HWP binary direct writing is blocked for this document harness. "
        "Use a HWPX or DOCX editable template for safe fill/save work, or keep "
        "this HWP file as classification/read-only evidence until a promoted HWP "
        "read adapter passes fixture and license gates."
    )


def empty_extraction(artifact_id: str, *, warning: str | None = None) -> DocumentExtraction:
    """Build an empty extraction with an optional warning."""
    return DocumentExtraction(
        artifact_id=artifact_id,
        warnings=[warning] if warning is not None else [],
    )
