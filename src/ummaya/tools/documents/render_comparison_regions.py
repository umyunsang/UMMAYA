# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from decimal import Decimal

from ummaya.tools.documents.models import (
    DocumentArtifact,
    DocumentChangedViewport,
    DocumentDiff,
    RenderArtifactRecord,
)
from ummaya.tools.documents.render_comparison_models import (
    RenderChangedRegionEvidence,
    RenderComparisonStatus,
)


def changed_region_evidence(
    diff: DocumentDiff,
    *,
    source: DocumentArtifact,
    derivative: DocumentArtifact,
    threshold: Decimal,
) -> tuple[RenderChangedRegionEvidence, ...]:
    derivative_records = {record.render_artifact_id: record for record in diff.render_artifacts}
    baseline_by_page = {record.page_number: record for record in diff.baseline_render_artifacts}
    regions: list[RenderChangedRegionEvidence] = []
    for viewport in diff.changed_viewports:
        derivative_record = derivative_records.get(viewport.source_render_artifact_id)
        baseline_record = baseline_by_page.get(viewport.page_number)
        if derivative_record is None or baseline_record is None:
            continue
        regions.append(
            _changed_region(
                viewport,
                source=source,
                derivative=derivative,
                derivative_record=derivative_record,
                baseline_record=baseline_record,
                threshold=threshold,
            )
        )
    return tuple(regions)


def _changed_region(
    viewport: DocumentChangedViewport,
    *,
    source: DocumentArtifact,
    derivative: DocumentArtifact,
    derivative_record: RenderArtifactRecord,
    baseline_record: RenderArtifactRecord,
    threshold: Decimal,
) -> RenderChangedRegionEvidence:
    threshold_status: RenderComparisonStatus = (
        "pass" if viewport.confidence >= threshold else "failed"
    )
    return RenderChangedRegionEvidence(
        region_id=viewport.viewport_id,
        viewport_id=viewport.viewport_id,
        change_ids=viewport.change_ids,
        page_number=viewport.page_number,
        source_render_artifact_id=baseline_record.render_artifact_id,
        derivative_render_artifact_id=derivative_record.render_artifact_id,
        source_render_sha256=baseline_record.render_sha256,
        derivative_render_sha256=derivative_record.render_sha256,
        source_artifact_sha256=source.sha256,
        derivative_artifact_sha256=derivative.sha256,
        confidence=viewport.confidence,
        threshold=threshold,
        threshold_status=threshold_status,
    )
