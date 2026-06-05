# SPDX-License-Identifier: Apache-2.0
"""Tests for document harness engine registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from ummaya.tools.documents.engines import (
    DocumentEngineRegistry,
    UnsupportedDocumentEngineError,
)
from ummaya.tools.documents.models import DocumentExtraction, DocumentFormat


class MinimalEngine:
    """Minimal engine test double."""

    def __init__(self, *, document_format: DocumentFormat, engine_id: str) -> None:
        self.document_format = document_format
        self.engine_id = engine_id

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        path.stat()
        return DocumentExtraction(artifact_id=artifact_id)


def test_engine_registry_returns_registered_engine_by_format() -> None:
    engine = MinimalEngine(document_format=DocumentFormat.hwpx, engine_id="python-hwpx")
    registry = DocumentEngineRegistry()

    registry.register(engine)

    assert registry.require(DocumentFormat.hwpx) is engine


def test_engine_registry_rejects_duplicate_format_registration() -> None:
    registry = DocumentEngineRegistry()
    registry.register(MinimalEngine(document_format=DocumentFormat.docx, engine_id="engine-a"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(MinimalEngine(document_format=DocumentFormat.docx, engine_id="engine-b"))


def test_engine_registry_fails_closed_for_unpromoted_format() -> None:
    registry = DocumentEngineRegistry()

    with pytest.raises(UnsupportedDocumentEngineError):
        registry.require(DocumentFormat.pdf)
