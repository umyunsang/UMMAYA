# SPDX-License-Identifier: Apache-2.0
"""Shared engine-backed adapter protocol for document formats."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ummaya.tools.documents.models import DocumentExtraction, DocumentFormat


class EngineBackedFormatAdapter(Protocol):
    """Thin wrapper around a promoted external or optional document engine."""

    document_format: DocumentFormat
    engine_id: str

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Delegate inspection to the selected engine."""
