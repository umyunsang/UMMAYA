# SPDX-License-Identifier: Apache-2.0
"""Public-form semantic scorecard tests for offline corpus evaluation."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ummaya.tools.documents.baselines import load_conformance_baselines
from ummaya.tools.documents.evaluation import load_data_go_kr_metadata_snapshot
from ummaya.tools.documents.models import (
    DocumentExtraction,
    FormField,
    ParagraphBlock,
    TableBlock,
    TableCell,
)
from ummaya.tools.documents.scorecard import compute_public_form_metrics

_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "documents"


def test_data_go_kr_semantic_metric_snapshot_sets_aggregate_threshold() -> None:
    snapshot = load_data_go_kr_metadata_snapshot(
        _FIXTURE_ROOT / "public_forms" / "data_go_kr_metadata.yaml"
    )
    baseline = load_conformance_baselines().by_template_id("birth-benefit-application-hwpx")

    metrics = compute_public_form_metrics(_matching_birth_benefit_extraction(), baseline)

    assert snapshot.authoritative_layout_oracle is False
    assert snapshot.metric_components == (
        "paragraph_block_f1",
        "table_cell_f1",
        "image_reference_f1",
        "metadata_exact_match",
    )
    assert metrics.paragraph_block_f1 == Decimal("1")
    assert metrics.table_cell_f1 == Decimal("1")
    assert metrics.image_reference_f1 == Decimal("1")
    assert metrics.metadata_exact_match == Decimal("1")
    assert metrics.aggregate_score >= Decimal(str(snapshot.aggregate_threshold))


def test_public_form_metrics_drop_below_threshold_for_structural_drift() -> None:
    snapshot = load_data_go_kr_metadata_snapshot(
        _FIXTURE_ROOT / "public_forms" / "data_go_kr_metadata.yaml"
    )
    baseline = load_conformance_baselines().by_template_id("birth-benefit-application-hwpx")

    metrics = compute_public_form_metrics(
        DocumentExtraction(
            artifact_id="artifact-drifted",
            paragraphs=[
                ParagraphBlock(
                    block_id="p-001",
                    text="Birth benefit application",
                    source_path="/body/section[1]/p[1]",
                )
            ],
            tables=[
                TableBlock(
                    block_id="applicant-table",
                    source_path="/body/section[1]/table[1]",
                    cells=[
                        TableCell(
                            row_index=0,
                            column_index=0,
                            text="Applicant",
                            source_path="/body/section[1]/table[1]/cell[1,1]",
                        )
                    ],
                )
            ],
            fields=[
                FormField(
                    field_id="applicant_name",
                    label="Applicant name",
                    path="/body/section[1]/field[applicant_name]",
                    field_type="text",
                    required=True,
                    current_value="Hong Gil-dong",
                    source_confidence=Decimal("1"),
                )
            ],
            metadata={"page_count": 1},
        ),
        baseline,
    )

    assert metrics.aggregate_score < Decimal(str(snapshot.aggregate_threshold))


def _matching_birth_benefit_extraction() -> DocumentExtraction:
    return DocumentExtraction(
        artifact_id="artifact-good",
        paragraphs=[
            ParagraphBlock(
                block_id="p-001",
                text="Birth benefit application",
                source_path="/body/section[1]/p[1]",
            ),
            ParagraphBlock(
                block_id="p-002",
                text="Applicant signature or seal",
                source_path="/body/section[1]/p[2]",
            ),
            ParagraphBlock(
                block_id="p-003",
                text="Required attachments",
                source_path="/body/section[2]/p[1]",
            ),
        ],
        tables=[
            TableBlock(
                block_id="applicant-table",
                source_path="/body/section[1]/table[1]",
                cells=[
                    TableCell(
                        row_index=0,
                        column_index=0,
                        text="Applicant",
                        source_path="/body/section[1]/table[1]/cell[1,1]",
                    ),
                    TableCell(
                        row_index=0,
                        column_index=1,
                        text="Name",
                        source_path="/body/section[1]/table[1]/cell[1,2]",
                    ),
                    TableCell(
                        row_index=1,
                        column_index=0,
                        text="Child",
                        source_path="/body/section[1]/table[1]/cell[2,1]",
                    ),
                    TableCell(
                        row_index=1,
                        column_index=1,
                        text="Date of birth",
                        source_path="/body/section[1]/table[1]/cell[2,2]",
                    ),
                ],
            )
        ],
        fields=[
            FormField(
                field_id="applicant_name",
                label="Applicant name",
                path="/body/section[1]/field[applicant_name]",
                field_type="text",
                required=True,
                current_value="Hong Gil-dong",
                source_confidence=Decimal("1"),
            ),
            FormField(
                field_id="child_birth_date",
                label="Child birth date",
                path="/body/section[1]/field[child_birth_date]",
                field_type="date",
                required=True,
                current_value="2026-05-01",
                source_confidence=Decimal("1"),
            ),
        ],
        metadata={
            "page_count": 2,
            "margin_top_mm": Decimal("20"),
            "margin_bottom_mm": Decimal("15"),
        },
    )
