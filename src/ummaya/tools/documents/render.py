# SPDX-License-Identifier: Apache-2.0
"""Renderer facade for local document evidence artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.diff import RenderArtifactRecord
from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
    DocumentInspectionEngine,
    UnsupportedDocumentEngineError,
)
from ummaya.tools.documents.models import (
    ArtifactLineage,
    BlockedReason,
    DocumentArtifact,
    ToolResultStatus,
)


@runtime_checkable
class DocumentRenderEngine(DocumentInspectionEngine, Protocol):
    """Promoted engine that can render reviewer-readable evidence."""

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Return one or more page, sheet, or slide render payloads."""


class DocumentRenderResult(BaseModel):
    """Result of rendering one derivative artifact for review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ToolResultStatus
    correlation_id: str
    source_artifact_id: str
    source_sha256: str
    records: tuple[RenderArtifactRecord, ...] = ()
    artifact_refs: list[str] = Field(default_factory=list)
    render_passed: bool
    blocked_reason: BlockedReason | None = None
    text_summary: str


def render_document_evidence(
    store: DocumentArtifactStore,
    artifact: DocumentArtifact,
    *,
    engine_registry: DocumentEngineRegistry,
    correlation_id: str,
    artifact_id_prefix: str,
) -> DocumentRenderResult:
    """Render a derivative through the promoted format engine and store artifacts."""
    try:
        engine = _require_render_engine(engine_registry, artifact)
    except UnsupportedDocumentEngineError:
        return DocumentRenderResult(
            status=ToolResultStatus.blocked,
            correlation_id=correlation_id,
            source_artifact_id=artifact.artifact_id,
            source_sha256=artifact.sha256,
            render_passed=False,
            blocked_reason=BlockedReason.unsupported_operation,
            text_summary=f"No render-capable engine is registered for {artifact.format.value}.",
        )

    output_dir = store.session_root / "renders" / artifact_id_prefix
    payloads = engine.render(
        Path(artifact.source_path),
        artifact_id=artifact.artifact_id,
        output_dir=output_dir,
    )
    records: list[RenderArtifactRecord] = []
    for index, payload in enumerate(payloads, start=1):
        render_artifact_id = f"{artifact_id_prefix}-{index:03d}"
        render_artifact = store.write_derivative(
            artifact,
            artifact_id=render_artifact_id,
            lineage=ArtifactLineage.render,
            destination_name=f"{render_artifact_id}.txt",
            payload=payload,
            document_format=artifact.format,
            mime_type="text/plain",
        )
        records.append(
            RenderArtifactRecord(
                render_artifact_id=render_artifact.artifact_id,
                source_artifact_id=artifact.artifact_id,
                source_sha256=artifact.sha256,
                render_sha256=render_artifact.sha256,
                render_path=render_artifact.source_path,
                page_number=index,
                correlation_id=correlation_id,
                engine_id=engine.engine_id,
            )
        )

    render_passed = len(records) > 0
    return DocumentRenderResult(
        status=ToolResultStatus.ok if render_passed else ToolResultStatus.blocked,
        correlation_id=correlation_id,
        source_artifact_id=artifact.artifact_id,
        source_sha256=artifact.sha256,
        records=tuple(records),
        artifact_refs=[record.render_artifact_id for record in records],
        render_passed=render_passed,
        blocked_reason=None if render_passed else BlockedReason.validation_failed,
        text_summary=(
            f"Rendered {len(records)} reviewer evidence artifact(s) through {engine.engine_id}."
            if render_passed
            else "Renderer produced no reviewer evidence artifacts."
        ),
    )


def _require_render_engine(
    engine_registry: DocumentEngineRegistry,
    artifact: DocumentArtifact,
) -> DocumentRenderEngine:
    engine = engine_registry.require(artifact.format)
    if not isinstance(engine, DocumentRenderEngine):
        raise UnsupportedDocumentEngineError(artifact.format)
    return engine
