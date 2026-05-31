# SPDX-License-Identifier: Apache-2.0
"""Deterministic performance budget tests for the local document harness."""

from __future__ import annotations

import math
import os
import time
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from ummaya.tools.documents.baselines import (
    BaselineField,
    BaselineTableGeometry,
    BaselineTextAnchor,
    ConformanceBaseline,
    ConformanceBaselineCatalog,
)
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FormField,
    ParagraphBlock,
    TableBlock,
    TableCell,
    ToolResultStatus,
)
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import (
    DocumentApplyFillRequest,
    DocumentApplyStyleRequest,
    DocumentCopyForEditRequest,
    DocumentExtractRequest,
    DocumentInspectRequest,
    DocumentLocator,
    DocumentSaveRequest,
    DocumentStylePatch,
    DocumentValidatePublicFormRequest,
)

pytestmark = pytest.mark.performance

_ITERATIONS = 20
_INSPECT_EXTRACT_P95_BUDGET_MS = 5_000.0
_FILL_STYLE_SAVE_VALIDATE_P95_BUDGET_MS = 15_000.0
_PERF_SKIP = pytest.mark.skipif(
    os.environ.get("UMMAYA_SKIP_PERF") == "1",
    reason="UMMAYA_SKIP_PERF=1 - performance gates disabled on constrained runners",
)


class BudgetDocxEngine:
    """Local inspection and mutation engine double for document perf gates."""

    document_format = DocumentFormat.docx
    engine_id = "budget-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        path.stat()
        return _budget_extraction(artifact_id)

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        operation_log = "\n".join(
            f"{operation.operation_id}:{operation.operation_type.value}:{operation.target_path}"
            for operation in patch.operations
        )
        return path.read_bytes() + f"\npatched:{patch.patch_id}\n{operation_log}".encode()


@_PERF_SKIP
def test_document_inspect_extract_p95_budget_uses_local_engine(tmp_path: Path) -> None:
    source = _write_minimal_docx(tmp_path / "budget-source.docx")
    runtime = _runtime(tmp_path / "inspect-artifacts")
    timings_ms: list[float] = []

    for index in range(_ITERATIONS):
        correlation_id = f"read-{index:03d}"
        started_ns = time.perf_counter_ns()
        inspect_result = runtime.inspect(
            DocumentInspectRequest(
                correlation_id=correlation_id,
                document=DocumentLocator(
                    path=str(source),
                    expected_format=DocumentFormat.docx,
                ),
            )
        )
        extract_result = runtime.extract(
            DocumentExtractRequest(
                correlation_id=f"extract-{index:03d}",
                document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
                include_tables=True,
                include_images=True,
                include_fields=True,
            )
        )
        timings_ms.append(_elapsed_ms(started_ns))

        assert inspect_result.status is ToolResultStatus.ok
        assert extract_result.status is ToolResultStatus.ok
        assert extract_result.extraction is not None
        assert extract_result.extraction.fields[0].field_id == "applicant_name"

    p95_ms = _p95(timings_ms)
    assert p95_ms <= _INSPECT_EXTRACT_P95_BUDGET_MS, (
        f"T079 inspect/extract p95 {p95_ms:.2f} ms exceeded "
        f"{_INSPECT_EXTRACT_P95_BUDGET_MS:.0f} ms over {_ITERATIONS} local runs"
    )


@_PERF_SKIP
def test_document_fill_style_save_validate_p95_budget_uses_local_engine(tmp_path: Path) -> None:
    source = _write_minimal_docx(tmp_path / "budget-write-source.docx")
    runtime = _runtime(tmp_path / "write-artifacts")
    timings_ms: list[float] = []

    for index in range(_ITERATIONS):
        working_artifact_id = _working_artifact_id(
            runtime,
            source=source,
            index=index,
        )

        started_ns = time.perf_counter_ns()
        fill_result = runtime.apply_fill(
            DocumentApplyFillRequest(
                correlation_id=f"fill-{index:03d}",
                document=DocumentLocator(artifact_id=working_artifact_id),
                patches=(
                    {
                        "target_path": "/body/section[1]/field[applicant_name]",
                        "value": "Hong Gil-dong",
                    },
                ),
            )
        )
        style_result = runtime.apply_style(
            DocumentApplyStyleRequest(
                correlation_id=f"style-{index:03d}",
                document=DocumentLocator(artifact_id=fill_result.artifact_refs[-1]),
                styles=(
                    DocumentStylePatch(
                        target_path="/body/section[1]/p[1]",
                        font_family="Noto Sans CJK KR",
                        font_size_pt=Decimal("10"),
                        bold=True,
                    ),
                ),
            )
        )
        save_result = runtime.save(
            DocumentSaveRequest(
                correlation_id=f"save-{index:03d}",
                document=DocumentLocator(artifact_id=style_result.artifact_refs[-1]),
                destination_display_name=f"budget-final-{index:03d}.docx",
            )
        )
        validate_result = runtime.validate_public_form(
            DocumentValidatePublicFormRequest(
                correlation_id=f"validate-{index:03d}",
                document=DocumentLocator(artifact_id=save_result.artifact_refs[-1]),
                template_id="budget-docx",
            )
        )
        timings_ms.append(_elapsed_ms(started_ns))

        assert fill_result.status is ToolResultStatus.ok
        assert style_result.status is ToolResultStatus.ok
        assert save_result.status is ToolResultStatus.ok
        assert validate_result.status is ToolResultStatus.ok
        assert validate_result.validation_report is not None
        assert validate_result.validation_report.readiness.value == "ready_for_review"

    p95_ms = _p95(timings_ms)
    assert p95_ms <= _FILL_STYLE_SAVE_VALIDATE_P95_BUDGET_MS, (
        f"T079 fill/style/save/validate p95 {p95_ms:.2f} ms exceeded "
        f"{_FILL_STYLE_SAVE_VALIDATE_P95_BUDGET_MS:.0f} ms over {_ITERATIONS} local runs"
    )


def _runtime(artifact_root: Path) -> DocumentToolRuntime:
    registry = DocumentEngineRegistry()
    registry.register(BudgetDocxEngine())
    return DocumentToolRuntime(
        session_id="session-document-budget",
        artifact_root=artifact_root,
        engine_registry=registry,
        baseline_catalog=_baseline_catalog(),
    )


def _working_artifact_id(runtime: DocumentToolRuntime, *, source: Path, index: int) -> str:
    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id=f"write-read-{index:03d}",
            document=DocumentLocator(
                path=str(source),
                expected_format=DocumentFormat.docx,
            ),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id=f"copy-{index:03d}",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )
    assert copy_result.status is ToolResultStatus.ok
    return copy_result.artifact_refs[-1]


def _write_minimal_docx(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")
    return path


def _budget_extraction(artifact_id: str) -> DocumentExtraction:
    return DocumentExtraction(
        artifact_id=artifact_id,
        paragraphs=[
            ParagraphBlock(
                block_id="p-001",
                text="Budget application",
                source_path="/body/section[1]/p[1]",
            )
        ],
        tables=[
            TableBlock(
                block_id="budget-table",
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
    )


def _baseline_catalog() -> ConformanceBaselineCatalog:
    return ConformanceBaselineCatalog(
        version=1,
        catalog_id="document-budget-baseline",
        source_policy="offline_fixtures_only",
        live_network_allowed=False,
        baselines=(
            ConformanceBaseline(
                template_id="budget-docx",
                schema_id="budget-docx-v1",
                format=DocumentFormat.docx,
                authoritative_standard="offline local test double",
                authority_refs=("tests/tools/documents/test_document_performance_budget.py",),
                supports_conformance=True,
                required_fields=(
                    BaselineField(
                        field_id="applicant_name",
                        label="Applicant name",
                        path="/body/section[1]/field[applicant_name]",
                    ),
                ),
                protected_text=(
                    BaselineTextAnchor(
                        text="Budget application",
                        anchor="/body/section[1]/p[1]",
                    ),
                ),
                table_geometries=(
                    BaselineTableGeometry(
                        table_id="budget-table",
                        anchor="/body/section[1]/table[1]",
                        rows=1,
                        columns=1,
                    ),
                ),
            ),
        ),
    )


def _elapsed_ms(started_ns: int) -> float:
    return (time.perf_counter_ns() - started_ns) / 1_000_000


def _p95(samples_ms: list[float]) -> float:
    assert samples_ms
    index = min(math.ceil(len(samples_ms) * 0.95) - 1, len(samples_ms) - 1)
    return sorted(samples_ms)[index]
