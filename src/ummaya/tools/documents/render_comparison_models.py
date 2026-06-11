# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type RenderComparisonStatus = Literal["pass", "failed", "blocked"]
type StylePropertyName = Literal[
    "font_family",
    "font_size_pt",
    "bold",
    "italic",
    "underline",
    "font_color_rgb",
    "fill_color_rgb",
    "alignment",
    "line_spacing",
    "border",
    "number_format",
]


class StrictRenderComparisonModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StyleDeltaEvidence(StrictRenderComparisonModel):
    operation_id: str
    target_path: str
    property_name: StylePropertyName
    before_value: str | None = None
    after_value: str | None = None


class TableGeometryDeltaEvidence(StrictRenderComparisonModel):
    target_path: str
    before_row_span: int
    after_row_span: int
    before_column_span: int
    after_column_span: int


class RenderChangedRegionEvidence(StrictRenderComparisonModel):
    region_id: str
    viewport_id: str
    change_ids: tuple[str, ...] = Field(min_length=1)
    page_number: int = Field(ge=1)
    source_render_artifact_id: str
    derivative_render_artifact_id: str
    source_render_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_render_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    confidence: Decimal = Field(ge=0, le=1)
    threshold: Decimal = Field(ge=0, le=1)
    threshold_status: RenderComparisonStatus


class RenderComparisonEvidence(StrictRenderComparisonModel):
    comparison_id: str
    source_artifact_id: str
    derivative_artifact_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: RenderComparisonStatus
    threshold: Decimal = Field(ge=0, le=1)
    threshold_status: RenderComparisonStatus
    changed_regions: tuple[RenderChangedRegionEvidence, ...] = ()
    style_deltas: tuple[StyleDeltaEvidence, ...] = ()
    table_geometry_deltas: tuple[TableGeometryDeltaEvidence, ...] = ()
    failure_reason: str | None = None
