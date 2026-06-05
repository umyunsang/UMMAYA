# SPDX-License-Identifier: Apache-2.0
"""Promotion scorecards for Public AX document capabilities."""

from __future__ import annotations

from decimal import Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.baselines import ConformanceBaseline
from ummaya.tools.documents.models import DocumentExtraction, TableBlock

ScoreDimension = Literal[
    "extraction_fidelity",
    "write_fidelity",
    "style_layout_control",
    "deterministic_round_trip",
    "public_form_validation",
    "security_privacy",
    "license_maintenance_tool_usability",
]

SCORECARD_WEIGHTS: Final[dict[ScoreDimension, int]] = {
    "extraction_fidelity": 20,
    "write_fidelity": 20,
    "style_layout_control": 15,
    "deterministic_round_trip": 15,
    "public_form_validation": 15,
    "security_privacy": 10,
    "license_maintenance_tool_usability": 5,
}


class CapabilityScorecard(BaseModel):
    """Evidence-backed promotion score for one format engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    extraction_fidelity: int = Field(
        ge=0,
        le=SCORECARD_WEIGHTS["extraction_fidelity"],
    )
    write_fidelity: int = Field(
        ge=0,
        le=SCORECARD_WEIGHTS["write_fidelity"],
    )
    style_layout_control: int = Field(
        ge=0,
        le=SCORECARD_WEIGHTS["style_layout_control"],
    )
    deterministic_round_trip: int = Field(
        ge=0,
        le=SCORECARD_WEIGHTS["deterministic_round_trip"],
    )
    public_form_validation: int = Field(
        ge=0,
        le=SCORECARD_WEIGHTS["public_form_validation"],
    )
    security_privacy: int = Field(
        ge=0,
        le=SCORECARD_WEIGHTS["security_privacy"],
    )
    license_maintenance_tool_usability: int = Field(
        ge=0,
        le=SCORECARD_WEIGHTS["license_maintenance_tool_usability"],
    )

    security_gate_passed: bool = True
    write_hard_gates_passed: bool = True
    critical_security_findings: tuple[str, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def total_score(self) -> int:
        """Return the weighted 100-point total for this scorecard."""
        return (
            self.extraction_fidelity
            + self.write_fidelity
            + self.style_layout_control
            + self.deterministic_round_trip
            + self.public_form_validation
            + self.security_privacy
            + self.license_maintenance_tool_usability
        )


class PublicFormMetricScore(BaseModel):
    """Semantic and structural public-form metric bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    paragraph_block_f1: Decimal = Field(ge=0, le=1)
    table_cell_f1: Decimal = Field(ge=0, le=1)
    image_reference_f1: Decimal = Field(ge=0, le=1)
    metadata_exact_match: Decimal = Field(ge=0, le=1)
    aggregate_score: Decimal = Field(ge=0, le=1)


def compute_public_form_metrics(
    extraction: DocumentExtraction,
    baseline: ConformanceBaseline,
) -> PublicFormMetricScore:
    """Compute the offline semantic metrics used by public-form validation."""
    paragraph_f1 = _paragraph_f1(extraction, baseline)
    table_f1 = _table_cell_f1(extraction, baseline)
    image_f1 = Decimal("1")
    metadata_match = _metadata_exact_match(extraction, baseline)
    return PublicFormMetricScore(
        paragraph_block_f1=paragraph_f1,
        table_cell_f1=table_f1,
        image_reference_f1=image_f1,
        metadata_exact_match=metadata_match,
        aggregate_score=_macro_average((paragraph_f1, table_f1, image_f1, metadata_match)),
    )


def _paragraph_f1(extraction: DocumentExtraction, baseline: ConformanceBaseline) -> Decimal:
    expected = {
        item.text
        for item in (
            *baseline.protected_text,
            *baseline.required_labels,
            *baseline.signature_regions,
        )
    }
    observed = {paragraph.text for paragraph in extraction.paragraphs}
    observed.update(cell.text for table in extraction.tables for cell in table.cells)
    return _set_f1(expected, observed)


def _table_cell_f1(extraction: DocumentExtraction, baseline: ConformanceBaseline) -> Decimal:
    expected = {
        (geometry.table_id, row, column)
        for geometry in baseline.table_geometries
        for row in range(geometry.rows)
        for column in range(geometry.columns)
    }
    observed = {
        (table.block_id, cell.row_index, cell.column_index)
        for table in extraction.tables
        for cell in table.cells
    }
    return _set_f1(expected, observed)


def _metadata_exact_match(
    extraction: DocumentExtraction,
    baseline: ConformanceBaseline,
) -> Decimal:
    expected = dict(baseline.metadata_exact_matches)
    if baseline.expected_page_count is not None:
        expected["page_count"] = baseline.expected_page_count
    if not expected:
        return Decimal("1")
    matches = sum(1 for key, value in expected.items() if extraction.metadata.get(key) == value)
    return Decimal(matches) / Decimal(len(expected))


def _set_f1[F1Item](expected: set[F1Item], observed: set[F1Item]) -> Decimal:
    if not expected and not observed:
        return Decimal("1")
    if not expected or not observed:
        return Decimal("0")
    matches = len(expected & observed)
    if matches == 0:
        return Decimal("0")
    precision = Decimal(matches) / Decimal(len(observed))
    recall = Decimal(matches) / Decimal(len(expected))
    return (Decimal("2") * precision * recall) / (precision + recall)


def _macro_average(values: tuple[Decimal, Decimal, Decimal, Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def table_shape(table: TableBlock | None) -> tuple[int, int]:
    """Return the row and column shape for a normalized table block."""
    if table is None or not table.cells:
        return 0, 0
    return (
        max(cell.row_index + cell.row_span for cell in table.cells),
        max(cell.column_index + cell.column_span for cell in table.cells),
    )
