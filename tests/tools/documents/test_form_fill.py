# SPDX-License-Identifier: Apache-2.0
"""Engine-backed form fill tests for HWPX and DOCX."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.formats.hwpx import validate_hwpx_mutation_engine
from ummaya.tools.documents.formats.ooxml import validate_ooxml_mutation_engine
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    OperationType,
)
from ummaya.tools.documents.patch import apply_document_patch, copy_for_edit


class FillEngine:
    """Mutation engine test double that records ordered patches."""

    def __init__(self, *, document_format: DocumentFormat) -> None:
        self.document_format = document_format
        self.engine_id = f"fill-engine-{document_format.value}"
        self.received_operations: list[str] = []

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        path.stat()
        return DocumentExtraction(artifact_id=artifact_id)

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        self.received_operations = [operation.operation_id for operation in patch.operations]
        payload = path.read_bytes().decode("utf-8")
        for operation in patch.operations:
            payload += f"\n{operation.target_path}={operation.value}"
        return payload.encode("utf-8")


def _source_artifact(tmp_path: Path, *, filename: str, document_format: DocumentFormat):
    original = tmp_path / filename
    original.write_text("PROTECTED: official label\nFIELD: applicant_name\n", encoding="utf-8")
    store = DocumentArtifactStore(root=tmp_path / "store", session_id="session-us2")
    return store, store.store_source(
        original,
        artifact_id=f"source-{document_format.value}",
        document_format=document_format,
        mime_type="application/octet-stream",
    )


def test_hwpx_fill_uses_ordered_engine_patch_and_preserves_source(tmp_path: Path) -> None:
    store, source = _source_artifact(
        tmp_path,
        filename="form.hwpx",
        document_format=DocumentFormat.hwpx,
    )
    working = copy_for_edit(
        store,
        source,
        artifact_id="working-hwpx",
        destination_name="working.hwpx",
    )
    engine = FillEngine(document_format=DocumentFormat.hwpx)
    registry = DocumentEngineRegistry()
    registry.register(engine)
    patch = DocumentPatch(
        patch_id="patch-hwpx",
        target_artifact_id=working.artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="fill-name",
                operation_type=OperationType.set_field_value,
                target_path="/fields/applicant_name",
                value="Hong Gil Dong",
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.hwpx,
        destination_policy="working_copy",
    )

    result = apply_document_patch(
        store,
        working,
        patch,
        engine_registry=registry,
        artifact_id="filled-hwpx",
        destination_name="filled.hwpx",
    )

    assert result.status.value == "ok"
    assert result.derivative_artifact is not None
    assert result.derivative_artifact.parent_artifact_id == working.artifact_id
    assert engine.received_operations == ["fill-name"]
    assert "PROTECTED: official label" in Path(source.source_path).read_text(encoding="utf-8")
    assert "Hong Gil Dong" in Path(result.derivative_artifact.source_path).read_text(
        encoding="utf-8"
    )
    assert result.diff is not None
    assert [change.operation_id for change in result.diff.changes] == ["fill-name"]


def test_docx_fill_blocks_protected_template_target_before_engine_call(tmp_path: Path) -> None:
    store, source = _source_artifact(
        tmp_path,
        filename="form.docx",
        document_format=DocumentFormat.docx,
    )
    working = copy_for_edit(
        store,
        source,
        artifact_id="working-docx",
        destination_name="working.docx",
    )
    engine = FillEngine(document_format=DocumentFormat.docx)
    registry = DocumentEngineRegistry()
    registry.register(engine)
    patch = DocumentPatch(
        patch_id="patch-docx-protected",
        target_artifact_id=working.artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="rewrite-protected",
                operation_type=OperationType.replace_text,
                target_path="/protected/official_label",
                value="Changed",
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.docx,
        destination_policy="working_copy",
    )

    result = apply_document_patch(
        store,
        working,
        patch,
        engine_registry=registry,
        artifact_id="filled-docx",
        destination_name="filled.docx",
    )

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "validation_failed"
    assert result.derivative_artifact is None
    assert engine.received_operations == []


def test_hwpx_and_docx_mutation_boundaries_require_matching_mutation_engines() -> None:
    hwpx_engine = FillEngine(document_format=DocumentFormat.hwpx)
    docx_engine = FillEngine(document_format=DocumentFormat.docx)

    assert validate_hwpx_mutation_engine(hwpx_engine) is hwpx_engine
    assert validate_ooxml_mutation_engine(docx_engine) is docx_engine
