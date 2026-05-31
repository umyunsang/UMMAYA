# SPDX-License-Identifier: Apache-2.0
"""Artifact store security and lineage tests for the document harness."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ummaya.tools.documents.artifact_store import (
    ArtifactStoreConflictError,
    ArtifactStoreSecurityError,
    DocumentArtifactStore,
)
from ummaya.tools.documents.models import (
    ArtifactLineage,
    DocumentArtifact,
    DocumentFormat,
    SecurityState,
)


def _model_value(model: object, raw: str) -> object:
    for attr in (raw.upper(), raw.lower()):
        if hasattr(model, attr):
            return getattr(model, attr)
    try:
        return model(raw)  # type: ignore[operator]
    except TypeError:
        return raw


def _raw_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_store_source_copies_bytes_immutably_and_records_checksum_lineage(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    original_path = incoming / "민원서식.docx"
    original_bytes = b"original docx bytes"
    original_path.write_bytes(original_bytes)

    store = DocumentArtifactStore(root=tmp_path / "store", session_id="session-001")
    artifact = store.store_source(
        original_path,
        artifact_id="source-001",
        document_format=_model_value(DocumentFormat, "docx"),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    stored_path = Path(artifact.source_path)
    assert isinstance(artifact, DocumentArtifact)
    assert stored_path.read_bytes() == original_bytes
    assert stored_path != original_path
    assert original_path.read_bytes() == original_bytes
    assert stored_path.is_relative_to((tmp_path / "store" / "session-001").resolve())
    assert artifact.sha256 == _sha256(original_bytes)
    assert artifact.byte_size == len(original_bytes)
    assert _raw_value(artifact.lineage) == _raw_value(_model_value(ArtifactLineage, "source"))
    assert artifact.parent_artifact_id is None
    assert _raw_value(artifact.security_state) == _raw_value(
        _model_value(SecurityState, "accepted")
    )

    original_path.write_bytes(b"mutated caller file")
    with pytest.raises(ArtifactStoreConflictError):
        store.store_source(
            original_path,
            artifact_id="source-001",
            document_format=_model_value(DocumentFormat, "docx"),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    assert stored_path.read_bytes() == original_bytes


def test_write_derivative_stays_under_session_root_and_records_parent_lineage(
    tmp_path: Path,
) -> None:
    original_path = tmp_path / "template.pdf"
    source_bytes = b"%PDF-1.7 source"
    original_path.write_bytes(source_bytes)
    store = DocumentArtifactStore(root=tmp_path / "store", session_id="session-002")
    source = store.store_source(
        original_path,
        artifact_id="source-pdf",
        document_format=_model_value(DocumentFormat, "pdf"),
        mime_type="application/pdf",
    )

    derivative_bytes = b"%PDF-1.7 filled derivative"
    derivative = store.write_derivative(
        source,
        artifact_id="working-pdf",
        lineage=_model_value(ArtifactLineage, "working_copy"),
        destination_name="filled.pdf",
        payload=derivative_bytes,
    )

    derivative_path = Path(derivative.source_path)
    assert derivative_path.read_bytes() == derivative_bytes
    assert derivative_path.is_relative_to((tmp_path / "store" / "session-002").resolve())
    assert derivative_path.name == "filled.pdf"
    assert source.sha256 == _sha256(source_bytes)
    assert derivative.sha256 == _sha256(derivative_bytes)
    assert derivative.parent_artifact_id == source.artifact_id
    assert _raw_value(derivative.lineage) == _raw_value(
        _model_value(ArtifactLineage, "working_copy")
    )
    assert Path(source.source_path).read_bytes() == source_bytes


@pytest.mark.parametrize(
    "destination_name",
    [
        ".hidden.pdf",
        "../escape.pdf",
        "nested/escape.pdf",
        "/public-root.pdf",
        "~/public-root.pdf",
        "C:\\public-root.pdf",
    ],
)
def test_write_derivative_rejects_hidden_traversal_and_public_root_destinations(
    tmp_path: Path,
    destination_name: str,
) -> None:
    original_path = tmp_path / "template.xlsx"
    original_path.write_bytes(b"xlsx source")
    store = DocumentArtifactStore(root=tmp_path / "store", session_id="session-003")
    source = store.store_source(
        original_path,
        artifact_id="source-xlsx",
        document_format=_model_value(DocumentFormat, "xlsx"),
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    with pytest.raises(ArtifactStoreSecurityError):
        store.write_derivative(
            source,
            artifact_id="bad-derivative",
            lineage=_model_value(ArtifactLineage, "export"),
            destination_name=destination_name,
            payload=b"bad",
        )


@pytest.mark.parametrize(
    "session_id",
    ["", ".", "..", ".hidden", "nested/session", "/public-session", "~/session"],
)
def test_store_rejects_unsafe_session_id(tmp_path: Path, session_id: str) -> None:
    with pytest.raises(ArtifactStoreSecurityError):
        DocumentArtifactStore(root=tmp_path / "store", session_id=session_id)
