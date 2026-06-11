# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Final

from ummaya.tools.documents.models import (
    BorderDescriptor,
    DocumentDiff,
    DocumentExtraction,
    StyleDescriptor,
    TableCell,
)
from ummaya.tools.documents.render_comparison_models import (
    StyleDeltaEvidence,
    StylePropertyName,
    TableGeometryDeltaEvidence,
)

_STYLE_PROPERTIES: Final[tuple[StylePropertyName, ...]] = (
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
)
_STYLE_VALUE_READERS: Final[dict[StylePropertyName, Callable[[StyleDescriptor], str | None]]] = {
    "font_family": lambda style: style.font_family,
    "font_size_pt": lambda style: _decimal_value(style.font_size_pt),
    "bold": lambda style: _bool_value(style.bold),
    "italic": lambda style: _bool_value(style.italic),
    "underline": lambda style: _bool_value(style.underline),
    "font_color_rgb": lambda style: style.font_color_rgb,
    "fill_color_rgb": lambda style: style.fill_color_rgb,
    "alignment": lambda style: style.alignment,
    "line_spacing": lambda style: _decimal_value(style.line_spacing),
    "border": lambda style: _border_value(style.border),
    "number_format": lambda style: style.number_format,
}


def style_deltas(
    diff: DocumentDiff,
    *,
    before_extraction: DocumentExtraction,
    after_extraction: DocumentExtraction,
) -> tuple[StyleDeltaEvidence, ...]:
    operation_ids_by_target = {
        change.target_path: change.operation_id
        for change in diff.changes
        if change.change_type == "style"
    }
    deltas: list[StyleDeltaEvidence] = []
    for target_path, operation_id in operation_ids_by_target.items():
        before_style = _style_for_target(before_extraction, target_path)
        after_style = _style_for_target(after_extraction, target_path)
        if before_style is None and after_style is None:
            continue
        deltas.extend(_style_delta(operation_id, target_path, before_style, after_style))
    return tuple(deltas)


def table_geometry_deltas(
    before_extraction: DocumentExtraction,
    after_extraction: DocumentExtraction,
) -> tuple[TableGeometryDeltaEvidence, ...]:
    before_cells = _table_cells_by_path(before_extraction)
    after_cells = _table_cells_by_path(after_extraction)
    deltas: list[TableGeometryDeltaEvidence] = []
    for target_path, after_cell in after_cells.items():
        before_cell = before_cells.get(target_path)
        if before_cell is None:
            continue
        if (
            before_cell.row_span == after_cell.row_span
            and before_cell.column_span == after_cell.column_span
        ):
            continue
        deltas.append(
            TableGeometryDeltaEvidence(
                target_path=target_path,
                before_row_span=before_cell.row_span,
                after_row_span=after_cell.row_span,
                before_column_span=before_cell.column_span,
                after_column_span=after_cell.column_span,
            )
        )
    return tuple(deltas)


def _style_delta(
    operation_id: str,
    target_path: str,
    before_style: StyleDescriptor | None,
    after_style: StyleDescriptor | None,
) -> tuple[StyleDeltaEvidence, ...]:
    deltas: list[StyleDeltaEvidence] = []
    for property_name in _STYLE_PROPERTIES:
        before_value = _style_value(before_style, property_name)
        after_value = _style_value(after_style, property_name)
        if before_value == after_value:
            continue
        deltas.append(
            StyleDeltaEvidence(
                operation_id=operation_id,
                target_path=target_path,
                property_name=property_name,
                before_value=before_value,
                after_value=after_value,
            )
        )
    return tuple(deltas)


def _style_for_target(
    extraction: DocumentExtraction,
    target_path: str,
) -> StyleDescriptor | None:
    for style in extraction.style_map:
        if style.target_path == target_path:
            return style
    return None


def _style_value(
    style: StyleDescriptor | None,
    property_name: StylePropertyName,
) -> str | None:
    if style is None:
        return None
    return _STYLE_VALUE_READERS[property_name](style)


def _table_cells_by_path(extraction: DocumentExtraction) -> dict[str, TableCell]:
    return {cell.source_path: cell for table in extraction.tables for cell in table.cells}


def _bool_value(value: bool | None) -> str | None:
    if value is None:
        return None
    return "true" if value else "false"


def _decimal_value(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _border_value(value: BorderDescriptor | None) -> str | None:
    if value is None:
        return None
    return value.model_dump_json()
