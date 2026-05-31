# SPDX-License-Identifier: Apache-2.0
"""PDF engine-adapter boundary."""

from __future__ import annotations

from ummaya.tools.documents.engines import DocumentInspectionEngine, DocumentMutationEngine
from ummaya.tools.documents.models import DocumentFormat

PDF_CANDIDATE_ENGINES: tuple[str, ...] = (
    "pypdf-acroform",
    "poppler-render-oracle",
    "qpdf-structure-oracle",
)


def validate_pdf_engine(engine: DocumentInspectionEngine) -> DocumentInspectionEngine:
    """Validate that an injected engine is scoped to PDF."""
    if engine.document_format is not DocumentFormat.pdf:
        raise ValueError("PDF adapter requires a pdf engine")
    return engine


def validate_pdf_mutation_engine(engine: DocumentInspectionEngine) -> DocumentMutationEngine:
    """Validate that an injected PDF engine can mutate fillable derivatives."""
    validate_pdf_engine(engine)
    if not isinstance(engine, DocumentMutationEngine):
        raise ValueError("PDF adapter requires a mutation-capable engine")
    return engine
