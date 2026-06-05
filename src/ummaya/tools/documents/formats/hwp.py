# SPDX-License-Identifier: Apache-2.0
"""Legacy HWP engine-adapter boundary."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from html import unescape
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

from ummaya.tools.documents.engines import DocumentInspectionEngine
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    FormField,
    KnownDocumentFormat,
    ParagraphBlock,
    TableBlock,
    TableCell,
)

if TYPE_CHECKING:
    from ummaya.tools.documents.tool_defs import DocumentFieldPatch

HWP_CANDIDATE_ENGINES: tuple[str, ...] = (
    "pyhwp-read-only",
    "OpenHWP-read-only",
    "hwp.js-read-only",
    "unhwp-read-only",
)


def validate_hwp_engine(engine: DocumentInspectionEngine) -> DocumentInspectionEngine:
    """Validate that an injected engine is scoped to HWP read/extract only."""
    if engine.document_format is not DocumentFormat.hwp:
        raise ValueError("HWP adapter requires a hwp engine")
    return engine


class HwpDocumentAdapter:
    """Known-only legacy HWP adapter boundary.

    Binary HWP direct writing is blocked in this epic. The adapter is registered
    for classification and explicit unsupported-operation behavior only until a
    read engine passes the promotion gates.
    """

    adapter_id = "hwp-known-read-blocked-adapter"
    engine_id = "hwp-known-read-blocked"
    known_formats: tuple[KnownDocumentFormat, ...] = (KnownDocumentFormat.hwp,)
    promoted_formats: tuple[DocumentFormat, ...] = ()

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Fail closed if called before a promoted HWP read engine exists."""
        _ = path
        return DocumentExtraction(
            artifact_id=artifact_id,
            metadata={
                "format": DocumentFormat.hwp.value,
                "adapter_id": self.adapter_id,
                "promotion_state": "known_only",
            },
            warnings=[
                "Legacy HWP binary inspection is known but not promoted; direct "
                "HWP authoring remains blocked in this epic."
            ],
        )

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Return patches unchanged; HWP mutation is blocked before execution."""
        _ = extraction
        return patches


class UnhwpReadOnlyInspectionEngine:
    """Read-only HWP inspection engine backed by the promoted unhwp dependency."""

    document_format = DocumentFormat.hwp
    engine_id = "unhwp-read-only"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract HWP text as normalized read-only paragraph blocks."""
        try:
            import unhwp  # type: ignore[import-untyped]  # noqa: PLC0415
        except ImportError as exc:
            raise ValueError("unhwp dependency is unavailable for HWP inspection") from exc

        try:
            parsed = unhwp.parse(str(path))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"unhwp could not parse HWP artifact: {path.name}") from exc
        if hasattr(parsed, "__enter__"):
            with parsed as result:
                return self._extraction_from_parse_result(
                    result,
                    artifact_id=artifact_id,
                )
        return self._extraction_from_parse_result(parsed, artifact_id=artifact_id)

    def _extraction_from_parse_result(
        self,
        result: object,
        *,
        artifact_id: str,
    ) -> DocumentExtraction:
        text = str(getattr(result, "text", "") or "")
        markdown = str(getattr(result, "markdown", "") or "")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        tables = _table_blocks_from_markdown(markdown)
        fields = _field_candidates_from_tables(tables)
        paragraphs = [
            ParagraphBlock(
                block_id=f"hwp-unhwp-text-{index:03d}",
                text=line,
                source_path=f"/hwp/unhwp/text[{index}]",
            )
            for index, line in enumerate(lines, start=1)
        ]
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            tables=tables,
            fields=fields,
            metadata={
                "engine_id": self.engine_id,
                "format": DocumentFormat.hwp.value,
                "unhwp_version": _unhwp_distribution_version(),
                "section_count": int(getattr(result, "section_count", 0) or 0),
                "paragraph_count": int(getattr(result, "paragraph_count", 0) or 0),
                "image_count": len(getattr(result, "images", ()) or ()),
                "table_count": len(tables),
                "field_candidate_count": len(fields),
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
            },
            warnings=[
                "Legacy HWP binary inspection is read-only. Direct HWP authoring "
                "remains blocked; use a promoted HWPX derivative bridge for edits."
            ],
        )


def _unhwp_distribution_version() -> str:
    try:
        return version("unhwp")
    except PackageNotFoundError:
        return "unknown"


def _table_blocks_from_markdown(markdown: str) -> list[TableBlock]:
    tables: list[TableBlock] = []
    current_lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            current_lines.append(stripped)
            continue
        if current_lines:
            table = _table_block_from_markdown_lines(
                current_lines,
                table_index=len(tables) + 1,
            )
            if table is not None:
                tables.append(table)
            current_lines = []
    if current_lines:
        table = _table_block_from_markdown_lines(
            current_lines,
            table_index=len(tables) + 1,
        )
        if table is not None:
            tables.append(table)
    return tables


def _table_block_from_markdown_lines(
    lines: list[str],
    *,
    table_index: int,
) -> TableBlock | None:
    rows: list[list[str]] = []
    for line in lines:
        cells = [_clean_markdown_cell(cell) for cell in _split_markdown_table_row(line)]
        if not cells or all(_is_markdown_separator_cell(cell) for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return None

    block_id = f"hwp-unhwp-table-{table_index:03d}"
    source_path = f"/hwp/unhwp/table[{table_index}]"
    table_cells: list[TableCell] = []
    for row_index, row in enumerate(rows):
        for column_index, text in enumerate(row):
            cell_path = f"{source_path}/row[{row_index}]/cell[{column_index}]"
            table_cells.append(
                TableCell(
                    row_index=row_index,
                    column_index=column_index,
                    text=text,
                    source_path=cell_path,
                    field_path=cell_path if text else None,
                )
            )
    return TableBlock(block_id=block_id, source_path=source_path, cells=table_cells)


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return stripped.split("|")


def _clean_markdown_cell(value: str) -> str:
    cleaned = unescape(value)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</?u>", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("\\_", "_")
    for marker in ("**", "__", "~~", "`", "*"):
        cleaned = cleaned.replace(marker, "")
    cleaned = "\n".join(" ".join(part.split()) for part in cleaned.splitlines())
    return cleaned.strip()


def _is_markdown_separator_cell(value: str) -> bool:
    return bool(re.fullmatch(r":?-{3,}:?", value.strip()))


def _field_candidates_from_tables(tables: list[TableBlock]) -> list[FormField]:
    fields: list[FormField] = []
    for table_index, table in enumerate(tables, start=1):
        rows: dict[int, list[TableCell]] = {}
        for cell in table.cells:
            rows.setdefault(cell.row_index, []).append(cell)
        for row_index, row_cells in sorted(rows.items()):
            non_empty_cells = [
                cell
                for cell in sorted(row_cells, key=lambda candidate: candidate.column_index)
                if cell.text.strip()
            ]
            if len(non_empty_cells) < 2:
                continue
            label_cells = non_empty_cells[:-1]
            value_cell = non_empty_cells[-1]
            label = _field_label_from_cells(label_cells)
            if not label or _is_probably_header_row(label, value_cell.text):
                continue
            fields.append(
                FormField(
                    field_id=f"hwp-table-{table_index:03d}-row-{row_index + 1:03d}",
                    label=label,
                    path=value_cell.field_path or value_cell.source_path,
                    field_type="text",
                    required=False,
                    current_value=value_cell.text,
                    source_confidence=Decimal("0.80"),
                )
            )
    return fields


def _field_label_from_cells(cells: list[TableCell]) -> str:
    labels = [cell.text.strip() for cell in cells if cell.text.strip()]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return " / ".join(labels)


def _is_probably_header_row(label: str, value: str) -> bool:
    header_tokens = {"연 번", "제출 목록", "제출 방식", "제출"}
    return label in header_tokens and value in header_tokens
