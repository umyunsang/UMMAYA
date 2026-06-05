# SPDX-License-Identifier: Apache-2.0
"""Tests for format-scoped document adapter registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from ummaya.tools.documents.adapter_registry import (
    DocumentAdapterRegistry,
    UnsupportedDocumentAdapterError,
    build_default_document_adapter_registry,
)
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    KnownDocumentFormat,
)


class MinimalAdapter:
    """Minimal adapter test double."""

    def __init__(
        self,
        *,
        adapter_id: str,
        known_formats: tuple[KnownDocumentFormat, ...],
        promoted_formats: tuple[DocumentFormat, ...],
    ) -> None:
        self.adapter_id = adapter_id
        self.known_formats = known_formats
        self.promoted_formats = promoted_formats

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        path.stat()
        return DocumentExtraction(artifact_id=artifact_id)


def test_adapter_registry_returns_adapter_by_known_and_promoted_format() -> None:
    adapter = MinimalAdapter(
        adapter_id="hwpx-adapter",
        known_formats=(KnownDocumentFormat.hwpx, KnownDocumentFormat.owpml),
        promoted_formats=(DocumentFormat.hwpx,),
    )
    registry = DocumentAdapterRegistry()

    registry.register(adapter)

    assert registry.require_known(KnownDocumentFormat.hwpx) is adapter
    assert registry.require_known(KnownDocumentFormat.owpml) is adapter
    assert registry.require_promoted(DocumentFormat.hwpx) is adapter


def test_adapter_registry_rejects_duplicate_adapter_ids_and_known_formats() -> None:
    registry = DocumentAdapterRegistry()
    registry.register(
        MinimalAdapter(
            adapter_id="doc-adapter",
            known_formats=(KnownDocumentFormat.docx,),
            promoted_formats=(DocumentFormat.docx,),
        )
    )

    with pytest.raises(ValueError, match="adapter_id"):
        registry.register(
            MinimalAdapter(
                adapter_id="doc-adapter",
                known_formats=(KnownDocumentFormat.xlsx,),
                promoted_formats=(DocumentFormat.xlsx,),
            )
        )

    with pytest.raises(ValueError, match="known format"):
        registry.register(
            MinimalAdapter(
                adapter_id="other-docx-adapter",
                known_formats=(KnownDocumentFormat.docx,),
                promoted_formats=(),
            )
        )


def test_adapter_registry_rejects_promoted_format_not_declared_as_known() -> None:
    registry = DocumentAdapterRegistry()

    with pytest.raises(ValueError, match="promoted format"):
        registry.register(
            MinimalAdapter(
                adapter_id="bad-adapter",
                known_formats=(KnownDocumentFormat.odt,),
                promoted_formats=(DocumentFormat.docx,),
            )
        )


def test_adapter_registry_fails_closed_for_unregistered_formats() -> None:
    registry = DocumentAdapterRegistry()

    with pytest.raises(UnsupportedDocumentAdapterError):
        registry.require_known(KnownDocumentFormat.odt)

    with pytest.raises(UnsupportedDocumentAdapterError):
        registry.require_promoted(DocumentFormat.pdf)


def test_default_adapter_registry_exposes_current_promoted_engine_backed_adapters() -> None:
    registry = build_default_document_adapter_registry()

    hwpx_adapter = registry.require_promoted(DocumentFormat.hwpx)
    docx_adapter = registry.require_promoted(DocumentFormat.docx)
    pdf_adapter = registry.require_promoted(DocumentFormat.pdf)

    assert hwpx_adapter.adapter_id == "hwpx-package-text-adapter"
    assert docx_adapter.adapter_id == "python-docx-adapter"
    assert pdf_adapter.adapter_id == "pypdf-acroform-adapter"
    assert registry.require_known(KnownDocumentFormat.owpml) is hwpx_adapter
    assert registry.require_known(KnownDocumentFormat.pdf) is pdf_adapter
