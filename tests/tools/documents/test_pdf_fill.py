# SPDX-License-Identifier: Apache-2.0
"""Engine-backed PDF fill tests."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.artifact_store import DocumentArtifactStore
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.formats.pdf import validate_pdf_mutation_engine
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    OperationType,
)
from ummaya.tools.documents.patch import apply_document_patch, copy_for_edit


class PdfReadOnlyEngine:
    """Read-only PDF engine that cannot mutate static PDFs."""

    document_format = DocumentFormat.pdf
    engine_id = "pdf-read-only"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        path.stat()
        return DocumentExtraction(artifact_id=artifact_id)


class PdfAcroFormEngine(PdfReadOnlyEngine):
    """Mutation engine test double for AcroForm PDF fills."""

    engine_id = "pdf-acroform-engine"

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        return path.read_bytes() + b"\nACROFORM-FILLED"


def _working_pdf(tmp_path: Path):
    original = tmp_path / "form.pdf"
    original.write_bytes(b"%PDF-1.7\n")
    store = DocumentArtifactStore(root=tmp_path / "store", session_id="session-pdf")
    source = store.store_source(
        original,
        artifact_id="source-pdf",
        document_format=DocumentFormat.pdf,
        mime_type="application/pdf",
    )
    return store, copy_for_edit(
        store,
        source,
        artifact_id="working-pdf",
        destination_name="working.pdf",
    )


def _pdf_patch(target_artifact_id: str) -> DocumentPatch:
    return DocumentPatch(
        patch_id="patch-pdf",
        target_artifact_id=target_artifact_id,
        operations=[
            DocumentPatchOperation(
                operation_id="fill-pdf-name",
                operation_type=OperationType.set_field_value,
                target_path="/acroform/fields/applicant_name",
                value="Hong Gil Dong",
            )
        ],
        dry_run=False,
        expected_format=DocumentFormat.pdf,
        destination_policy="working_copy",
    )


def test_pdf_acroform_fill_requires_mutation_engine(tmp_path: Path) -> None:
    store, working = _working_pdf(tmp_path)
    registry = DocumentEngineRegistry()
    registry.register(PdfAcroFormEngine())

    result = apply_document_patch(
        store,
        working,
        _pdf_patch(working.artifact_id),
        engine_registry=registry,
        artifact_id="filled-pdf",
        destination_name="filled.pdf",
    )

    assert result.status.value == "ok"
    assert result.derivative_artifact is not None
    assert Path(result.derivative_artifact.source_path).read_bytes().endswith(b"ACROFORM-FILLED")


def test_static_pdf_without_mutation_engine_is_blocked(tmp_path: Path) -> None:
    store, working = _working_pdf(tmp_path)
    registry = DocumentEngineRegistry()
    registry.register(PdfReadOnlyEngine())

    result = apply_document_patch(
        store,
        working,
        _pdf_patch(working.artifact_id),
        engine_registry=registry,
        artifact_id="filled-static-pdf",
        destination_name="filled.pdf",
    )

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "unsupported_operation"
    assert result.derivative_artifact is None


def test_pdf_mutation_boundary_rejects_read_only_static_pdf_engine() -> None:
    acroform_engine = PdfAcroFormEngine()
    read_only_engine = PdfReadOnlyEngine()

    assert validate_pdf_mutation_engine(acroform_engine) is acroform_engine
    try:
        validate_pdf_mutation_engine(read_only_engine)
    except ValueError as exc:
        assert "mutation" in str(exc)
    else:
        raise AssertionError("read-only PDF engine should be rejected")
