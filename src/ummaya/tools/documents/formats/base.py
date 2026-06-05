# SPDX-License-Identifier: Apache-2.0
"""Shared engine-backed adapter protocol for document formats."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ummaya.tools.documents.models import DocumentExtraction, DocumentFormat, KnownDocumentFormat

if TYPE_CHECKING:
    from ummaya.tools.documents.tool_defs import DocumentFieldPatch


class DocumentFormatAdapter(Protocol):
    """Format-scoped adapter boundary below the single document primitive."""

    adapter_id: str
    known_formats: tuple[KnownDocumentFormat, ...]
    promoted_formats: tuple[DocumentFormat, ...]

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Return LLM-readable document IR for a local artifact."""

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Normalize adapter-specific model-facing fill targets before mutation."""


class EngineBackedFormatAdapter(Protocol):
    """Thin wrapper around a promoted external or optional document engine."""

    document_format: DocumentFormat
    engine_id: str

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Delegate inspection to the selected engine."""
