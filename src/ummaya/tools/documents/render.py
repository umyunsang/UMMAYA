# SPDX-License-Identifier: Apache-2.0
"""Renderer facade for local document evidence artifacts."""

from __future__ import annotations

import hashlib
import html
import re
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.artifact_store import (
    ArtifactStoreConflictError,
    DocumentArtifactStore,
)
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
    DocumentChange,
    DocumentChangedViewport,
    DocumentClipRect,
    DocumentDiff,
    DocumentFormat,
    DocumentViewportCamera,
    PromotionCapability,
    PromotionChecklistItem,
    PromotionChecklistStatus,
    PromotionGateResult,
    PromotionState,
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
    baseline_records: tuple[RenderArtifactRecord, ...] = ()
    changed_viewports: tuple[DocumentChangedViewport, ...] = ()
    viewport_cameras: tuple[DocumentViewportCamera, ...] = ()
    artifact_refs: list[str] = Field(default_factory=list)
    render_passed: bool
    blocked_reason: BlockedReason | None = None
    promotion_gate_result: PromotionGateResult | None = None
    text_summary: str


def _write_or_reuse_derivative(
    parent: DocumentArtifact,
    store: DocumentArtifactStore,
    *,
    artifact_id: str,
    lineage: ArtifactLineage,
    destination_name: str,
    payload: bytes,
    document_format: DocumentFormat | None = None,
    mime_type: str | None = None,
    expanded_byte_size: int | None = None,
) -> DocumentArtifact:
    """Write a deterministic render artifact, or reuse an identical existing one."""

    try:
        return store.write_derivative(
            parent,
            artifact_id=artifact_id,
            lineage=lineage,
            destination_name=destination_name,
            payload=payload,
            document_format=document_format,
            mime_type=mime_type,
            expanded_byte_size=expanded_byte_size,
        )
    except ArtifactStoreConflictError as err:
        existing = store.load_artifact(artifact_id)
        if existing is None:
            raise
        mismatches = _derivative_metadata_mismatches(
            existing,
            parent,
            payload=payload,
            lineage=lineage,
            document_format=document_format,
            mime_type=mime_type,
            expanded_byte_size=expanded_byte_size,
        )
        if mismatches:
            mismatch_list = ", ".join(mismatches)
            raise ArtifactStoreConflictError(
                f"artifact already exists with divergent render metadata: "
                f"{artifact_id} ({mismatch_list})"
            ) from err
        return existing


def _derivative_metadata_mismatches(
    existing: DocumentArtifact,
    parent: DocumentArtifact,
    *,
    payload: bytes,
    lineage: ArtifactLineage,
    document_format: DocumentFormat | None,
    mime_type: str | None,
    expanded_byte_size: int | None,
) -> list[str]:
    expected_expanded_byte_size = (
        expanded_byte_size if expanded_byte_size is not None else len(payload)
    )
    expected = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_size": len(payload),
        "expanded_byte_size": expected_expanded_byte_size,
        "format": document_format or parent.format,
        "mime_type": mime_type or parent.mime_type,
        "lineage": lineage,
        "parent_artifact_id": parent.artifact_id,
    }
    actual = {
        "sha256": existing.sha256,
        "byte_size": existing.byte_size,
        "expanded_byte_size": existing.expanded_byte_size,
        "format": existing.format,
        "mime_type": existing.mime_type,
        "lineage": existing.lineage,
        "parent_artifact_id": existing.parent_artifact_id,
    }
    return [field for field, expected_value in expected.items() if actual[field] != expected_value]


def render_document_evidence(
    store: DocumentArtifactStore,
    artifact: DocumentArtifact,
    *,
    engine_registry: DocumentEngineRegistry,
    correlation_id: str,
    artifact_id_prefix: str,
    diff: DocumentDiff | None = None,
    baseline_artifact: DocumentArtifact | None = None,
) -> DocumentRenderResult:
    """Render a derivative through the promoted format engine and store artifacts."""
    try:
        engine = _require_render_engine(engine_registry, artifact)
    except UnsupportedDocumentEngineError:
        promotion_gate_result = _blocked_render_promotion_gate(artifact)
        return DocumentRenderResult(
            status=ToolResultStatus.blocked,
            correlation_id=correlation_id,
            source_artifact_id=artifact.artifact_id,
            source_sha256=artifact.sha256,
            render_passed=False,
            blocked_reason=BlockedReason.unsupported_operation,
            promotion_gate_result=promotion_gate_result,
            text_summary=_unsupported_render_summary(artifact),
        )

    output_dir = store.session_root / "renders" / artifact_id_prefix
    try:
        payloads = engine.render(
            Path(artifact.source_path),
            artifact_id=artifact.artifact_id,
            output_dir=output_dir,
        )
        baseline_payloads: tuple[bytes, ...] = ()
        if diff is not None and baseline_artifact is not None:
            baseline_payloads = engine.render(
                Path(baseline_artifact.source_path),
                artifact_id=baseline_artifact.artifact_id,
                output_dir=output_dir / "baseline",
            )
    except Exception as exc:  # noqa: BLE001 - native render bridges fail as runtime exceptions.
        return _render_engine_failure_result(
            artifact,
            correlation_id=correlation_id,
            engine=engine,
            exc=exc,
        )
    artifact_path = Path(artifact.source_path)
    render_extension = _render_artifact_extension(engine, artifact_path=artifact_path)
    render_mime_type = _render_mime_type(
        engine,
        extension=render_extension,
        artifact_path=artifact_path,
    )
    records: list[RenderArtifactRecord] = []
    baseline_records: list[RenderArtifactRecord] = []
    changed_viewports: list[DocumentChangedViewport] = []
    viewport_cameras: list[DocumentViewportCamera] = []
    changed_viewport_anchored = False
    for index, payload in enumerate(payloads, start=1):
        render_artifact_id = f"{artifact_id_prefix}-{index:03d}"
        render_payload, viewport_anchored, page_viewports = _detect_changed_viewports(
            payload,
            diff=diff,
            mime_type=render_mime_type,
            page_number=index,
            render_artifact_id=render_artifact_id,
        )
        changed_viewport_anchored = changed_viewport_anchored or viewport_anchored
        render_artifact = _write_or_reuse_derivative(
            artifact,
            store,
            artifact_id=render_artifact_id,
            lineage=ArtifactLineage.render,
            destination_name=f"{render_artifact_id}.{render_extension}",
            payload=render_payload,
            document_format=artifact.format,
            mime_type=render_mime_type,
        )
        raster_update = (
            _optional_png_render_update(
                store,
                artifact,
                render_artifact_id=render_artifact.artifact_id,
                render_path=Path(render_artifact.source_path),
            )
            if render_mime_type == "image/svg+xml"
            else {}
        )
        raster_artifact_ref = cast(str | None, raster_update.get("raster_artifact_ref"))
        raster_artifact_path = cast(Path | None, raster_update.get("raster_artifact_path"))
        raster_mime_type = cast(str | None, raster_update.get("raster_mime_type"))
        records.append(
            _render_artifact_record(
                artifact=artifact,
                render_artifact=render_artifact,
                render_mime_type=render_mime_type,
                raster_artifact_ref=raster_artifact_ref,
                raster_artifact_path=raster_artifact_path,
                raster_mime_type=raster_mime_type,
                page_number=index,
                correlation_id=correlation_id,
                engine=engine,
                artifact_path=artifact_path,
            )
        )
        baseline_record: RenderArtifactRecord | None = None
        baseline_payload = baseline_payloads[index - 1] if index <= len(baseline_payloads) else None
        if baseline_artifact is not None and baseline_payload is not None:
            baseline_record = _write_full_page_render_record(
                store,
                baseline_artifact,
                render_artifact_id=f"{artifact_id_prefix}-baseline-{index:03d}",
                render_payload=baseline_payload,
                render_extension=render_extension,
                render_mime_type=render_mime_type,
                page_number=index,
                correlation_id=correlation_id,
                engine=engine,
                artifact_path=Path(baseline_artifact.source_path),
            )
            baseline_records.append(baseline_record)
        if render_mime_type == "image/svg+xml":
            page_changed_viewports = _write_changed_viewport_artifacts(
                store,
                artifact,
                after_render_payload=render_payload,
                before_artifact=baseline_artifact,
                before_render_payload=baseline_payload,
                viewports=page_viewports,
            )
            changed_viewports.extend(page_changed_viewports)
            if baseline_record is not None:
                viewport_cameras.extend(
                    _viewport_cameras_for_page(
                        page_changed_viewports,
                        source_render_artifact_id=render_artifact.artifact_id,
                        baseline_render_artifact_id=baseline_record.render_artifact_id,
                        page_index=index - 1,
                    )
                )
        else:
            changed_viewports.extend(page_viewports)

    render_passed = len(records) > 0
    return DocumentRenderResult(
        status=ToolResultStatus.ok if render_passed else ToolResultStatus.blocked,
        correlation_id=correlation_id,
        source_artifact_id=artifact.artifact_id,
        source_sha256=artifact.sha256,
        records=tuple(records),
        baseline_records=tuple(baseline_records),
        changed_viewports=tuple(changed_viewports),
        viewport_cameras=tuple(viewport_cameras),
        artifact_refs=[record.render_artifact_id for record in records],
        render_passed=render_passed,
        blocked_reason=None if render_passed else BlockedReason.validation_failed,
        text_summary=_render_text_summary(
            record_count=len(records),
            engine=engine,
            render_passed=render_passed,
            visual_diff_requested=diff is not None,
            changed_viewport_anchored=changed_viewport_anchored,
            artifact_path=artifact_path,
        ),
    )


def _write_full_page_render_record(
    store: DocumentArtifactStore,
    artifact: DocumentArtifact,
    *,
    render_artifact_id: str,
    render_payload: bytes,
    render_extension: str,
    render_mime_type: str,
    page_number: int,
    correlation_id: str,
    engine: DocumentRenderEngine,
    artifact_path: Path,
) -> RenderArtifactRecord:
    render_artifact = _write_or_reuse_derivative(
        artifact,
        store,
        artifact_id=render_artifact_id,
        lineage=ArtifactLineage.render,
        destination_name=f"{render_artifact_id}.{render_extension}",
        payload=render_payload,
        document_format=artifact.format,
        mime_type=render_mime_type,
    )
    raster_update = (
        _optional_png_render_update(
            store,
            artifact,
            render_artifact_id=render_artifact.artifact_id,
            render_path=Path(render_artifact.source_path),
        )
        if render_mime_type == "image/svg+xml"
        else {}
    )
    return _render_artifact_record(
        artifact=artifact,
        render_artifact=render_artifact,
        render_mime_type=render_mime_type,
        raster_artifact_ref=cast(str | None, raster_update.get("raster_artifact_ref")),
        raster_artifact_path=cast(Path | None, raster_update.get("raster_artifact_path")),
        raster_mime_type=cast(str | None, raster_update.get("raster_mime_type")),
        page_number=page_number,
        correlation_id=correlation_id,
        engine=engine,
        artifact_path=artifact_path,
    )


def _render_artifact_record(
    *,
    artifact: DocumentArtifact,
    render_artifact: DocumentArtifact,
    render_mime_type: str,
    raster_artifact_ref: str | None,
    raster_artifact_path: Path | None,
    raster_mime_type: str | None,
    page_number: int,
    correlation_id: str,
    engine: DocumentRenderEngine,
    artifact_path: Path,
) -> RenderArtifactRecord:
    return RenderArtifactRecord(
        render_artifact_id=render_artifact.artifact_id,
        source_artifact_id=artifact.artifact_id,
        source_sha256=artifact.sha256,
        render_sha256=render_artifact.sha256,
        render_path=render_artifact.source_path,
        render_mime_type=render_mime_type,
        raster_artifact_ref=raster_artifact_ref,
        raster_artifact_path=raster_artifact_path,
        raster_mime_type=raster_mime_type,
        page_number=page_number,
        correlation_id=correlation_id,
        engine_id=_render_engine_id(engine, artifact_path=artifact_path),
    )


def _viewport_cameras_for_page(
    viewports: tuple[DocumentChangedViewport, ...],
    *,
    source_render_artifact_id: str,
    baseline_render_artifact_id: str,
    page_index: int,
) -> tuple[DocumentViewportCamera, ...]:
    return tuple(
        DocumentViewportCamera(
            source_render_artifact_id=source_render_artifact_id,
            baseline_render_artifact_id=baseline_render_artifact_id,
            page_index=page_index,
            viewport_rect=viewport.clip_rect,
            zoom=Decimal("1"),
            change_ids=viewport.change_ids,
        )
        for viewport in viewports
    )


def _write_changed_viewport_artifacts(
    store: DocumentArtifactStore,
    artifact: DocumentArtifact,
    *,
    after_render_payload: bytes,
    before_artifact: DocumentArtifact | None = None,
    before_render_payload: bytes | None = None,
    viewports: tuple[DocumentChangedViewport, ...],
) -> tuple[DocumentChangedViewport, ...]:
    updated: list[DocumentChangedViewport] = []
    for viewport in viewports:
        after_viewport_payload = _viewport_svg_payload(
            after_render_payload,
            viewport_id=viewport.viewport_id,
            clip_rect=viewport.clip_rect,
        )
        after_viewport_artifact = _write_or_reuse_derivative(
            artifact,
            store,
            artifact_id=viewport.viewport_id,
            lineage=ArtifactLineage.render,
            destination_name=f"{viewport.viewport_id}.svg",
            payload=after_viewport_payload,
            document_format=artifact.format,
            mime_type="image/svg+xml",
        )
        after_png_update = _optional_png_viewport_update(
            store,
            artifact,
            viewport_id=viewport.viewport_id,
            viewport_svg_path=Path(after_viewport_artifact.source_path),
        )
        update: dict[str, str | Path | None] = {
            "svg_artifact_ref": after_viewport_artifact.artifact_id,
            "svg_artifact_path": after_viewport_artifact.source_path,
            "after_svg_artifact_ref": after_viewport_artifact.artifact_id,
            "after_svg_artifact_path": after_viewport_artifact.source_path,
            **after_png_update,
            **_prefixed_png_update(after_png_update, prefix="after"),
        }
        if before_artifact is not None and before_render_payload is not None:
            before_viewport_id = f"{viewport.viewport_id}-before"
            before_viewport_payload = _viewport_svg_payload(
                before_render_payload,
                viewport_id=before_viewport_id,
                clip_rect=viewport.clip_rect,
            )
            before_viewport_artifact = _write_or_reuse_derivative(
                before_artifact,
                store,
                artifact_id=before_viewport_id,
                lineage=ArtifactLineage.render,
                destination_name=f"{before_viewport_id}.svg",
                payload=before_viewport_payload,
                document_format=before_artifact.format,
                mime_type="image/svg+xml",
            )
            before_png_update = _optional_png_viewport_update(
                store,
                before_artifact,
                viewport_id=before_viewport_id,
                viewport_svg_path=Path(before_viewport_artifact.source_path),
            )
            update.update(
                {
                    "before_svg_artifact_ref": before_viewport_artifact.artifact_id,
                    "before_svg_artifact_path": before_viewport_artifact.source_path,
                    **_prefixed_png_update(before_png_update, prefix="before"),
                }
            )
        updated.append(
            viewport.model_copy(
                update=update,
            )
        )
    return tuple(updated)


def _prefixed_png_update(
    png_update: dict[str, str | Path],
    *,
    prefix: str,
) -> dict[str, str | Path]:
    prefixed: dict[str, str | Path] = {}
    if "png_artifact_ref" in png_update:
        prefixed[f"{prefix}_png_artifact_ref"] = png_update["png_artifact_ref"]
    if "png_artifact_path" in png_update:
        prefixed[f"{prefix}_png_artifact_path"] = png_update["png_artifact_path"]
    return prefixed


def _optional_png_viewport_update(
    store: DocumentArtifactStore,
    artifact: DocumentArtifact,
    *,
    viewport_id: str,
    viewport_svg_path: Path,
) -> dict[str, str | Path]:
    return _optional_svg_to_png_update(
        store,
        artifact,
        png_artifact_id=f"{viewport_id}-png",
        svg_path=viewport_svg_path,
    )


def _optional_svg_to_png_update(
    store: DocumentArtifactStore,
    artifact: DocumentArtifact,
    *,
    png_artifact_id: str,
    svg_path: Path,
) -> dict[str, str | Path]:
    rasterizer = shutil.which("rsvg-convert")
    if rasterizer is None:
        return {}

    png_path = (
        store.session_root / "render" / f"{png_artifact_id}-raster-tmp" / f"{png_artifact_id}.png"
    )
    png_path.parent.mkdir(parents=True, exist_ok=True)
    # Local rasterizer only, no shell: fixed executable plus local artifact paths.
    completed = subprocess.run(  # noqa: S603
        [rasterizer, str(svg_path), "-o", str(png_path)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0 or not png_path.is_file():
        return {}

    png_payload = png_path.read_bytes()
    png_artifact = _write_or_reuse_derivative(
        artifact,
        store,
        artifact_id=png_artifact_id,
        lineage=ArtifactLineage.render,
        destination_name=f"{png_artifact_id}.png",
        payload=png_payload,
        document_format=artifact.format,
        mime_type="image/png",
    )
    return {
        "png_artifact_ref": png_artifact.artifact_id,
        "png_artifact_path": png_artifact.source_path,
    }


def _optional_png_render_update(
    store: DocumentArtifactStore,
    artifact: DocumentArtifact,
    *,
    render_artifact_id: str,
    render_path: Path,
) -> dict[str, str | Path]:
    png_update = _optional_svg_to_png_update(
        store,
        artifact,
        png_artifact_id=f"{render_artifact_id}-png",
        svg_path=render_path,
    )
    if not png_update:
        return {}
    return {
        "raster_artifact_ref": png_update["png_artifact_ref"],
        "raster_artifact_path": png_update["png_artifact_path"],
        "raster_mime_type": "image/png",
    }


def _viewport_svg_payload(
    render_payload: bytes,
    *,
    viewport_id: str,
    clip_rect: DocumentClipRect,
) -> bytes:
    svg = render_payload.decode("utf-8")
    clip_x = float(clip_rect.x)
    clip_y = float(clip_rect.y)
    clip_width = max(float(clip_rect.width), 1.0)
    clip_height = max(float(clip_rect.height), 1.0)
    escaped_viewport_id = html.escape(viewport_id, quote=True)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{clip_width:.2f}" height="{clip_height:.2f}" '
        f'viewBox="{clip_x:.2f} {clip_y:.2f} {clip_width:.2f} {clip_height:.2f}" '
        'preserveAspectRatio="xMinYMin meet" overflow="hidden" '
        f'data-ummaya-viewport-id="{escaped_viewport_id}">'
        "<title>UMMAYA changed document viewport</title>"
        f"{_svg_inner_markup(svg)}</svg>"
    ).encode()


def _svg_inner_markup(svg: str) -> str:
    match = re.search(r"<svg\b[^>]*>(?P<body>.*)</svg>", svg, re.DOTALL)
    if match is None:
        return html.escape(svg)
    return match.group("body")


def _render_artifact_extension(
    engine: DocumentRenderEngine,
    *,
    artifact_path: Path | None = None,
) -> str:
    dynamic_extension = getattr(engine, "render_artifact_extension_for", None)
    if dynamic_extension is not None and artifact_path is not None:
        extension = str(dynamic_extension(artifact_path)).lstrip(".").lower()
    else:
        extension = str(getattr(engine, "render_artifact_extension", "txt")).lstrip(".").lower()
    supported_extensions = {"txt", "svg", "png", "pdf", "html"}
    if extension not in supported_extensions:
        raise ValueError(f"Unsupported render artifact extension: {extension}")
    return extension


def _render_mime_type(
    engine: DocumentRenderEngine,
    *,
    extension: str,
    artifact_path: Path | None = None,
) -> str:
    dynamic_mime_type = getattr(engine, "render_mime_type_for", None)
    if dynamic_mime_type is not None and artifact_path is not None:
        return str(dynamic_mime_type(artifact_path))
    explicit_mime_type = getattr(engine, "render_mime_type", None)
    if explicit_mime_type is not None:
        return str(explicit_mime_type)
    return {
        "html": "text/html",
        "pdf": "application/pdf",
        "png": "image/png",
        "svg": "image/svg+xml",
        "txt": "text/plain",
    }[extension]


def _render_engine_id(
    engine: DocumentRenderEngine,
    *,
    artifact_path: Path | None = None,
) -> str:
    dynamic_engine_id = getattr(engine, "render_engine_id_for", None)
    if dynamic_engine_id is not None and artifact_path is not None:
        return str(dynamic_engine_id(artifact_path))
    return str(getattr(engine, "render_engine_id", engine.engine_id))


def _render_text_summary(
    *,
    record_count: int,
    engine: DocumentRenderEngine,
    render_passed: bool,
    visual_diff_requested: bool,
    changed_viewport_anchored: bool,
    artifact_path: Path | None = None,
) -> str:
    if not render_passed:
        return "Renderer produced no reviewer evidence artifacts."
    engine_id = _render_engine_id(engine, artifact_path=artifact_path)
    if changed_viewport_anchored:
        return (
            f"Rendered {record_count} reviewer evidence artifact(s) through {engine_id} "
            "with changed viewport evidence."
        )
    if visual_diff_requested:
        return (
            f"Rendered {record_count} reviewer evidence artifact(s) through {engine_id}; "
            "no changed viewport anchors matched the rendered page."
        )
    return f"Rendered {record_count} reviewer evidence artifact(s) through {engine_id}."


def _render_engine_failure_result(
    artifact: DocumentArtifact,
    *,
    correlation_id: str,
    engine: DocumentRenderEngine,
    exc: Exception,
) -> DocumentRenderResult:
    return DocumentRenderResult(
        status=ToolResultStatus.blocked,
        correlation_id=correlation_id,
        source_artifact_id=artifact.artifact_id,
        source_sha256=artifact.sha256,
        render_passed=False,
        blocked_reason=BlockedReason.validation_failed,
        text_summary=_render_engine_failure_summary(engine=engine, exc=exc),
    )


def _render_engine_failure_summary(
    *,
    engine: DocumentRenderEngine,
    exc: Exception,
) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    if len(message) > 300:
        message = f"{message[:300]}..."
    return f"Document render failed through {_render_engine_id(engine)}: {message}"


def _require_render_engine(
    engine_registry: DocumentEngineRegistry,
    artifact: DocumentArtifact,
) -> DocumentRenderEngine:
    engine = engine_registry.require(artifact.format)
    if not isinstance(engine, DocumentRenderEngine):
        raise UnsupportedDocumentEngineError(artifact.format)
    return engine


def _blocked_render_promotion_gate(artifact: DocumentArtifact) -> PromotionGateResult:
    failure_id = (
        "hwpx_render_engine_unpromoted"
        if artifact.format is DocumentFormat.hwpx
        else f"{artifact.format.value}_render_engine_unavailable"
    )
    return PromotionGateResult(
        gate_id=f"gate-{artifact.artifact_id}-render",
        profile_id=f"profile-{artifact.format.value}",
        capability=PromotionCapability.render,
        score_total=0,
        extraction_fidelity=0,
        write_fidelity=0,
        style_layout_control=0,
        deterministic_round_trip=0,
        public_form_validation=0,
        security_privacy=0,
        license_maintenance_tool_usability=0,
        hard_gates_passed=False,
        hard_gate_failures=[failure_id],
        promotion_state=PromotionState.blocked,
        promotion_checklist=_promotion_checklist_for_render(artifact),
        evidence_record_ids=[],
    )


def _promotion_checklist_for_render(artifact: DocumentArtifact) -> list[PromotionChecklistItem]:
    if artifact.format is not DocumentFormat.hwpx:
        return []
    evidence_items = {
        "page_geometry": "Rendered pages preserve paper size, margins, and page breaks.",
        "table_spans": "Rendered tables preserve row spans, column spans, borders, and cell text.",
        "font_fallback": (
            "Korean fonts resolve deterministically without missing-glyph fallback drift."
        ),
        "korean_line_breaks": "Korean line breaks and paragraph spacing match the source fixture.",
        "visible_field_values": (
            "Filled values are visible at the expected anchors in the rendered output."
        ),
        "package_integrity": "The HWPX package remains valid after render preparation.",
        "no_external_egress": (
            "Rendering uses only local files and performs no external network egress."
        ),
    }
    return [
        PromotionChecklistItem(
            check_id=check_id,
            capability=PromotionCapability.render,
            status=PromotionChecklistStatus.required,
            evidence_required=evidence_required,
        )
        for check_id, evidence_required in evidence_items.items()
    ]


def _unsupported_render_summary(artifact: DocumentArtifact) -> str:
    if artifact.format is DocumentFormat.hwpx:
        return (
            "HWPX visual render is not promoted for the hwpx-package-text engine. "
            "Use extraction, structured diff, and public-form validation evidence "
            "until an HWPX renderer passes the visual fixture gate."
        )
    return f"No render-capable engine is registered for {artifact.format.value}."


_TEXT_ELEMENT_RE = re.compile(r"<text\b(?P<attrs>[^>]*)>(?P<text>.*?)</text>", re.DOTALL)
_NUMBER_ATTR_RE = re.compile(r'\b(?P<name>x|y|font-size|textLength)="(?P<value>-?\d+(?:\.\d+)?)"')
_MIN_CHANGED_VIEWPORT_WIDTH = 240.0
_MIN_CHANGED_VIEWPORT_HEIGHT = 140.0


class _SvgTextRun(BaseModel):
    """One positioned SVG text run extracted from renderer output."""

    model_config = ConfigDict(frozen=True)

    index: int
    x: float
    y: float
    width: float
    height: float
    text: str


class _SvgViewportMatch(BaseModel):
    """Matched SVG visual change location plus its page crop rectangle."""

    model_config = ConfigDict(frozen=True)

    clip_x: float
    clip_y: float
    clip_width: float
    clip_height: float
    text_fallback: tuple[str, ...]


def _detect_changed_viewports(
    payload: bytes,
    *,
    diff: DocumentDiff | None,
    mime_type: str,
    page_number: int,
    render_artifact_id: str,
) -> tuple[bytes, bool, tuple[DocumentChangedViewport, ...]]:
    if diff is None or mime_type != "image/svg+xml":
        return payload, False, ()

    svg = payload.decode("utf-8")
    runs = _svg_text_runs(svg)
    changed_viewports: list[DocumentChangedViewport] = []
    for change in diff.changes:
        viewport = _svg_viewport_for_change(change, runs=runs, page_number=page_number)
        if viewport is None:
            continue
        changed_viewports.append(
            DocumentChangedViewport(
                viewport_id=f"viewport-{render_artifact_id}-{change.change_id}",
                change_ids=(change.change_id,),
                page_number=page_number,
                source_render_artifact_id=render_artifact_id,
                clip_rect=DocumentClipRect(
                    x=_decimal(viewport.clip_x),
                    y=_decimal(viewport.clip_y),
                    width=_decimal(viewport.clip_width),
                    height=_decimal(viewport.clip_height),
                ),
                svg_artifact_ref=render_artifact_id,
                text_fallback=viewport.text_fallback,
                anchor_strategy="exact_text_run",
                confidence=Decimal("0.90"),
            )
        )
    if not changed_viewports:
        return payload, False, ()

    return payload, True, tuple(changed_viewports)


def _svg_text_runs(svg: str) -> list[_SvgTextRun]:
    runs: list[_SvgTextRun] = []
    for index, match in enumerate(_TEXT_ELEMENT_RE.finditer(svg)):
        attrs = _number_attrs(match.group("attrs"))
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group("text")))
        if not text:
            continue
        x = attrs.get("x")
        y = attrs.get("y")
        font_size = attrs.get("font-size", 12.0)
        if x is None or y is None:
            continue
        width = attrs.get("textLength", _estimated_text_width(text, font_size))
        runs.append(
            _SvgTextRun(
                index=index,
                x=x,
                y=y,
                width=width,
                height=max(font_size, 8.0),
                text=text,
            )
        )
    return runs


def _number_attrs(attrs: str) -> dict[str, float]:
    return {
        match.group("name"): float(match.group("value"))
        for match in _NUMBER_ATTR_RE.finditer(attrs)
    }


def _estimated_text_width(text: str, font_size: float) -> float:
    width = 0.0
    for character in text:
        width += font_size if ord(character) > 0x7F else font_size * 0.55
    return max(width, font_size * 0.55)


def _svg_viewport_for_change(
    change: DocumentChange,
    *,
    runs: list[_SvgTextRun],
    page_number: int,
) -> _SvgViewportMatch | None:
    if change.after_value is None:
        return None
    matched_runs = _match_text_runs(runs, change.after_value)
    if not matched_runs:
        return None

    x1 = min(run.x for run in matched_runs)
    y1 = min(run.y - run.height for run in matched_runs) - 3
    x2 = max(run.x + run.width for run in matched_runs)
    y2 = max(run.y + 3 for run in matched_runs)
    width = max(x2 - x1 + 6, 10)
    height = max(y2 - y1 + 6, 10)
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    clip_width = max(width + 96.0, _MIN_CHANGED_VIEWPORT_WIDTH)
    clip_height = max(height + 96.0, _MIN_CHANGED_VIEWPORT_HEIGHT)
    clip_x = max(0.0, center_x - (clip_width / 2))
    clip_y = max(0.0, center_y - (clip_height / 2))
    return _SvgViewportMatch(
        clip_x=clip_x,
        clip_y=clip_y,
        clip_width=clip_width,
        clip_height=clip_height,
        text_fallback=_change_text_fallback(change, page_number),
    )


def _match_text_runs(runs: list[_SvgTextRun], value: str) -> list[_SvgTextRun]:
    target = _normalize_match_text(value)
    if not target:
        return []

    for start_index in range(len(runs)):
        matched: list[_SvgTextRun] = []
        observed = ""
        for run in runs[start_index:]:
            normalized = _normalize_match_text(run.text)
            if not normalized:
                continue
            observed += normalized
            matched.append(run)
            if target.startswith(observed):
                if observed == target:
                    return matched
                continue
            break
    return []


def _normalize_match_text(value: str) -> str:
    return "".join(value.split())


def _change_text_fallback(change: DocumentChange, page_number: int) -> tuple[str, ...]:
    lines = [f"Page {page_number} · {change.change_id} · {change.target_path}"]
    if change.before_value is not None:
        lines.append(f"- {change.before_value}")
    if change.after_value is not None:
        lines.append(f"+ {change.after_value}")
    return tuple(lines)


def _decimal(value: float) -> Decimal:
    return Decimal(f"{value:.2f}")
