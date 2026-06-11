# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
from decimal import Decimal

from ummaya.tools.documents.models import (
    DocumentArtifact,
    DocumentDiff,
    DocumentExtraction,
)
from ummaya.tools.documents.render_comparison_models import (
    RenderComparisonEvidence,
    RenderComparisonStatus,
    StyleDeltaEvidence,
    TableGeometryDeltaEvidence,
)
from ummaya.tools.documents.render_comparison_regions import changed_region_evidence
from ummaya.tools.documents.render_comparison_style import (
    style_deltas,
    table_geometry_deltas,
)

__all__ = [
    "RenderComparisonEvidence",
    "RenderComparisonStatus",
    "build_render_comparison_evidence",
]


def build_render_comparison_evidence(
    source: DocumentArtifact,
    derivative: DocumentArtifact,
    *,
    diff: DocumentDiff,
    before_extraction: DocumentExtraction,
    after_extraction: DocumentExtraction,
    confidence_threshold: Decimal,
) -> RenderComparisonEvidence:
    changed_regions = changed_region_evidence(
        diff,
        source=source,
        derivative=derivative,
        threshold=confidence_threshold,
    )
    deltas = style_deltas(
        diff,
        before_extraction=before_extraction,
        after_extraction=after_extraction,
    )
    geometry_deltas = table_geometry_deltas(before_extraction, after_extraction)
    if not changed_regions:
        return _blocked_comparison(
            source,
            derivative,
            threshold=confidence_threshold,
            failure_reason="source-to-derivative render comparison is missing",
            style_deltas=deltas,
            table_geometry_deltas=geometry_deltas,
        )
    status: RenderComparisonStatus = (
        "pass" if all(region.threshold_status == "pass" for region in changed_regions) else "failed"
    )
    failure_reason = None if status == "pass" else "changed region confidence below threshold"
    return RenderComparisonEvidence(
        comparison_id=_comparison_id(source, derivative, diff),
        source_artifact_id=source.artifact_id,
        derivative_artifact_id=derivative.artifact_id,
        source_sha256=source.sha256,
        derivative_sha256=derivative.sha256,
        status=status,
        threshold=confidence_threshold,
        threshold_status=status,
        changed_regions=changed_regions,
        style_deltas=deltas,
        table_geometry_deltas=geometry_deltas,
        failure_reason=failure_reason,
    )


def _blocked_comparison(
    source: DocumentArtifact,
    derivative: DocumentArtifact,
    *,
    threshold: Decimal,
    failure_reason: str,
    style_deltas: tuple[StyleDeltaEvidence, ...],
    table_geometry_deltas: tuple[TableGeometryDeltaEvidence, ...],
) -> RenderComparisonEvidence:
    return RenderComparisonEvidence(
        comparison_id=_comparison_id(source, derivative, None),
        source_artifact_id=source.artifact_id,
        derivative_artifact_id=derivative.artifact_id,
        source_sha256=source.sha256,
        derivative_sha256=derivative.sha256,
        status="blocked",
        threshold=threshold,
        threshold_status="blocked",
        style_deltas=style_deltas,
        table_geometry_deltas=table_geometry_deltas,
        failure_reason=failure_reason,
    )


def _comparison_id(
    source: DocumentArtifact,
    derivative: DocumentArtifact,
    diff: DocumentDiff | None,
) -> str:
    diff_id = "no-diff" if diff is None else diff.diff_id
    payload = f"{source.artifact_id}:{derivative.artifact_id}:{diff_id}".encode()
    return f"render-comparison-{hashlib.sha256(payload).hexdigest()[:16]}"
