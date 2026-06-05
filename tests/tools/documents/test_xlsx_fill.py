# SPDX-License-Identifier: Apache-2.0
"""Engine-backed XLSX fill tests."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.formats.ooxml import validate_ooxml_mutation_engine
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    OperationType,
    StyleDescriptor,
)
from ummaya.tools.documents.patch import apply_document_patch, copy_for_edit


class XlsxMutationEngine:
    """Mutation engine test double for XLSX operations."""

    document_format = DocumentFormat.xlsx
    engine_id = "xlsx-fill-engine"

    def __init__(self) -> None:
        self.received_targets: list[str] = []

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        path.stat()
        return DocumentExtraction(artifact_id=artifact_id)

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        self.received_targets = [operation.target_path for operation in patch.operations]
        return path.read_bytes() + b"\nFILLED:XLSX"


def _working_xlsx(tmp_path: Path):
    original = tmp_path / "sheet.xlsx"
    original.write_bytes(b"XLSX")
    store = DocumentArtifactStore(root=tmp_path / "store", session_id="session-xlsx")
    source = store.store_source(
        original,
        artifact_id="source-xlsx",
        document_format=DocumentFormat.xlsx,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    return store, copy_for_edit(
        store,
        source,
        artifact_id="working-xlsx",
        destination_name="working.xlsx",
    )


def test_xlsx_fill_passes_cell_and_style_patch_to_engine(tmp_path: Path) -> None:
    store, working = _working_xlsx(tmp_path)
    engine = XlsxMutationEngine()
    registry = DocumentEngineRegistry()
    registry.register(engine)
    patch = DocumentPatch(
        patch_id="patch-xlsx",
        target_artifact_id=working.artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="set-a1",
                operation_type=OperationType.set_table_cell,
                target_path="/sheets/Sheet1/cells/A1",
                value="123",
            ),
            DocumentPatchOperation(
                operation_id="style-a1",
                operation_type=OperationType.set_cell_style,
                target_path="/sheets/Sheet1/cells/A1",
                style=StyleDescriptor(
                    style_id="style-a1",
                    target_path="/sheets/Sheet1/cells/A1",
                    bold=True,
                ),
            ),
        ],
        dry_run=False,
        expected_format=DocumentFormat.xlsx,
        destination_policy="working_copy",
    )

    result = apply_document_patch(
        store,
        working,
        patch,
        engine_registry=registry,
        artifact_id="filled-xlsx",
        destination_name="filled.xlsx",
    )

    assert result.status.value == "ok"
    assert engine.received_targets == [
        "/sheets/Sheet1/cells/A1",
        "/sheets/Sheet1/cells/A1",
    ]
    assert result.derivative_artifact is not None
    assert Path(result.derivative_artifact.source_path).read_bytes().endswith(b"FILLED:XLSX")


def test_xlsx_fill_blocks_formula_cell_targets_before_engine_call(tmp_path: Path) -> None:
    store, working = _working_xlsx(tmp_path)
    engine = XlsxMutationEngine()
    registry = DocumentEngineRegistry()
    registry.register(engine)
    patch = DocumentPatch(
        patch_id="patch-formula",
        target_artifact_id=working.artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="set-formula",
                operation_type=OperationType.set_table_cell,
                target_path="/sheets/Sheet1/formulas/A1",
                value="123",
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.xlsx,
        destination_policy="working_copy",
    )

    result = apply_document_patch(
        store,
        working,
        patch,
        engine_registry=registry,
        artifact_id="filled-formula",
        destination_name="filled.xlsx",
    )

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "validation_failed"
    assert engine.received_targets == []


def test_xlsx_fill_blocks_merged_region_structure_edits(tmp_path: Path) -> None:
    store, working = _working_xlsx(tmp_path)
    engine = XlsxMutationEngine()
    registry = DocumentEngineRegistry()
    registry.register(engine)
    patch = DocumentPatch(
        patch_id="patch-merged-region",
        target_artifact_id=working.artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="rewrite-merged-region",
                operation_type=OperationType.replace_text,
                target_path="/sheets/Sheet1/merged_regions/A1:C1",
                value="rewritten",
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.xlsx,
        destination_policy="working_copy",
    )

    result = apply_document_patch(
        store,
        working,
        patch,
        engine_registry=registry,
        artifact_id="filled-merged",
        destination_name="filled.xlsx",
    )

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "validation_failed"
    assert engine.received_targets == []


def test_xlsx_fill_blocks_print_area_edits(tmp_path: Path) -> None:
    store, working = _working_xlsx(tmp_path)
    engine = XlsxMutationEngine()
    registry = DocumentEngineRegistry()
    registry.register(engine)
    patch = DocumentPatch(
        patch_id="patch-print-area",
        target_artifact_id=working.artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="rewrite-print-area",
                operation_type=OperationType.set_document_metadata,
                target_path="/sheets/Sheet1/print_area",
                value="A1:Z99",
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.xlsx,
        destination_policy="working_copy",
    )

    result = apply_document_patch(
        store,
        working,
        patch,
        engine_registry=registry,
        artifact_id="filled-print-area",
        destination_name="filled.xlsx",
    )

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "validation_failed"
    assert engine.received_targets == []


def test_xlsx_mutation_boundary_accepts_xlsx_engine() -> None:
    engine = XlsxMutationEngine()

    assert validate_ooxml_mutation_engine(engine) is engine
