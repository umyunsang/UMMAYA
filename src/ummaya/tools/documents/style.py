# SPDX-License-Identifier: Apache-2.0
"""Bounded style and target validation for document patches."""

from __future__ import annotations

from ummaya.tools.documents.models import DocumentPatch, OperationType


class DocumentPatchValidationError(ValueError):
    """Raised when a patch targets protected or unsupported document regions."""


def validate_document_patch(patch: DocumentPatch) -> None:
    """Validate patch targets before any mutation engine is called."""
    for operation in patch.operations:
        target = operation.target_path.lower()
        if "/protected/" in target or target.startswith("/protected"):
            raise DocumentPatchValidationError(
                f"protected template target cannot be edited: {operation.target_path}"
            )
        if "/formulas/" in target or target.endswith("/formula"):
            raise DocumentPatchValidationError(
                f"formula-backed spreadsheet target cannot be edited: {operation.target_path}"
            )
        if "/merged_regions/" in target or "/merged_cells/" in target:
            raise DocumentPatchValidationError(
                f"merged spreadsheet regions cannot be structurally edited: {operation.target_path}"
            )
        if target.endswith("/print_area") or "/print_areas/" in target:
            raise DocumentPatchValidationError(
                f"spreadsheet print areas cannot be edited by fill patches: {operation.target_path}"
            )
        if operation.operation_type in {
            OperationType.set_paragraph_style,
            OperationType.set_run_style,
            OperationType.set_cell_style,
        }:
            if operation.style is None:
                raise DocumentPatchValidationError("style operation requires a style payload")
            if operation.style.target_path != operation.target_path:
                raise DocumentPatchValidationError(
                    "style target_path must match the patch operation target_path"
                )
