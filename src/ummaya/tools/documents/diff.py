# SPDX-License-Identifier: Apache-2.0
"""Structured derivative diff generation for document patches."""

from __future__ import annotations

import hashlib
import json

from ummaya.tools.documents.models import (
    DocumentChange,
    DocumentChangeType,
    DocumentDiff,
    DocumentExtraction,
    DocumentPatch,
    DocumentViewportCamera,
    MetadataValue,
    OperationType,
    RenderArtifactRecord,
    TableCell,
)

__all__ = [
    "DocumentChange",
    "DocumentChangeType",
    "DocumentDiff",
    "DocumentViewportCamera",
    "RenderArtifactRecord",
    "diff_from_patch",
]


def diff_from_patch(
    patch: DocumentPatch,
    *,
    source_artifact_id: str,
    derivative_artifact_id: str,
    render_artifacts: tuple[RenderArtifactRecord, ...] = (),
    before_extraction: DocumentExtraction | None = None,
    after_extraction: DocumentExtraction | None = None,
) -> DocumentDiff:
    """Build a structured diff from an ordered patch request."""
    changes = tuple(
        DocumentChange(
            change_id=f"change-{index:03d}",
            operation_id=operation.operation_id,
            change_type=_change_type(operation.operation_type),
            target_path=operation.target_path,
            display_label=_display_label_for_target(
                before_extraction or after_extraction,
                operation.target_path,
            ),
            before_value=_value_for_target(before_extraction, operation.target_path),
            after_value=_after_value(
                operation.value,
                after_extraction,
                operation.target_path,
            ),
        )
        for index, operation in enumerate(patch.operations, start=1)
    )
    diff_sha256 = _diff_sha256(
        source_artifact_id=source_artifact_id,
        derivative_artifact_id=derivative_artifact_id,
        changes=changes,
        render_artifacts=render_artifacts,
    )
    diff_id = f"diff-{diff_sha256[:16]}"
    return DocumentDiff(
        diff_id=diff_id,
        diff_sha256=diff_sha256,
        resource_ref=f"document-diff://{diff_id}",
        source_artifact_id=source_artifact_id,
        derivative_artifact_id=derivative_artifact_id,
        changes=changes,
        render_artifacts=render_artifacts,
    )


def _diff_sha256(
    *,
    source_artifact_id: str,
    derivative_artifact_id: str,
    changes: tuple[DocumentChange, ...],
    render_artifacts: tuple[RenderArtifactRecord, ...],
) -> str:
    payload = {
        "changes": [change.model_dump(mode="json") for change in changes],
        "derivative_artifact_id": derivative_artifact_id,
        "render_artifacts": [record.model_dump(mode="json") for record in render_artifacts],
        "source_artifact_id": source_artifact_id,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _change_type(operation_type: OperationType) -> DocumentChangeType:
    if operation_type is OperationType.set_field_value:
        return "field"
    if operation_type is OperationType.set_table_cell:
        return "table_cell"
    if operation_type is OperationType.replace_text:
        return "text"
    if operation_type in {
        OperationType.set_paragraph_style,
        OperationType.set_run_style,
        OperationType.set_cell_style,
    }:
        return "style"
    if operation_type is OperationType.set_document_metadata:
        return "metadata"
    return "copy"


def _value_for_target(
    extraction: DocumentExtraction | None,
    target_path: str,
) -> str | None:
    if extraction is None:
        return None
    value = _field_value_for_target(extraction, target_path)
    if value is not None:
        return value
    value = _paragraph_value_for_target(extraction, target_path)
    if value is not None:
        return value
    value = _table_value_for_target(extraction, target_path)
    if value is not None:
        return value
    return _metadata_value_for_target(extraction, target_path)


def _display_label_for_target(
    extraction: DocumentExtraction | None,
    target_path: str,
) -> str | None:
    if extraction is None:
        return None
    for field in extraction.fields:
        if field.path == target_path:
            return field.label
    for table in extraction.tables:
        matching_cell = _table_cell_for_target(table.cells, target_path)
        if matching_cell is None:
            continue
        return _left_neighbor_label(table.cells, matching_cell)
    return None


def _after_value(
    operation_value: MetadataValue,
    after_extraction: DocumentExtraction | None,
    target_path: str,
) -> str | None:
    if operation_value is not None:
        return str(operation_value)
    return _value_for_target(after_extraction, target_path)


def _metadata_value_to_str(value: MetadataValue) -> str | None:
    if value is None:
        return None
    return str(value)


def _field_value_for_target(
    extraction: DocumentExtraction,
    target_path: str,
) -> str | None:
    for field in extraction.fields:
        if field.path == target_path:
            return _metadata_value_to_str(field.current_value)
    return None


def _paragraph_value_for_target(
    extraction: DocumentExtraction,
    target_path: str,
) -> str | None:
    if target_path in {"/text/body", "/data/body", "/code/body"}:
        return "\n".join(paragraph.text for paragraph in extraction.paragraphs)
    for paragraph in extraction.paragraphs:
        if (
            _target_path_matches(paragraph.source_path, target_path)
            or paragraph.block_id == target_path
        ):
            return paragraph.text
    return None


def _table_value_for_target(
    extraction: DocumentExtraction,
    target_path: str,
) -> str | None:
    for table in extraction.tables:
        if _target_path_matches(table.source_path, target_path) or table.block_id == target_path:
            return _table_text(table.cells)
        for cell in table.cells:
            if _target_path_matches(cell.source_path, target_path):
                return cell.text
    return None


def _table_cell_for_target(
    cells: list[TableCell],
    target_path: str,
) -> TableCell | None:
    for cell in cells:
        if _target_path_matches(cell.source_path, target_path):
            return cell
    return None


def _left_neighbor_label(
    cells: list[TableCell],
    target_cell: TableCell,
) -> str | None:
    candidates = [
        cell
        for cell in cells
        if cell.row_index == target_cell.row_index
        and cell.column_index < target_cell.column_index
        and cell.text.strip()
    ]
    if not candidates:
        return None
    label_cell = max(candidates, key=lambda cell: cell.column_index)
    return label_cell.text.strip()


def _target_path_matches(extracted_path: str, target_path: str) -> bool:
    if extracted_path == target_path:
        return True
    extracted_tail = _engine_path_tail(extracted_path)
    target_tail = _engine_path_tail(target_path)
    if extracted_tail is not None and extracted_tail == target_tail:
        return True
    if extracted_tail is not None:
        return extracted_tail == target_path.lstrip("/")
    return False


def _engine_path_tail(path: str) -> str | None:
    prefix = "engine://"
    if not path.startswith(prefix):
        return None
    parts = path[len(prefix) :].split("/")
    if len(parts) < 3:
        return None
    return "/".join(parts[2:])


def _metadata_value_for_target(
    extraction: DocumentExtraction,
    target_path: str,
) -> str | None:
    metadata_key = _metadata_key_from_target(target_path)
    if metadata_key is None or metadata_key not in extraction.metadata:
        return None
    return _metadata_value_to_str(extraction.metadata[metadata_key])


def _metadata_key_from_target(target_path: str) -> str | None:
    prefix = "/metadata/"
    if target_path.startswith(prefix) and len(target_path) > len(prefix):
        return target_path[len(prefix) :]
    return None


def _table_text(cells: list[TableCell]) -> str:
    return "\n".join(cell.text for cell in cells if cell.text)
