# SPDX-License-Identifier: Apache-2.0
"""HWPX engine-adapter boundary."""

from __future__ import annotations

from ummaya.tools.documents.engines import DocumentInspectionEngine, DocumentMutationEngine
from ummaya.tools.documents.models import DocumentFormat

HWPX_CANDIDATE_ENGINES: tuple[str, ...] = (
    "python-hwpx",
    "hwpx-mcp-server",
    "rhwp",
    "direct-owpml-oracle",
)


def validate_hwpx_engine(engine: DocumentInspectionEngine) -> DocumentInspectionEngine:
    """Validate that an injected engine is scoped to HWPX."""
    if engine.document_format is not DocumentFormat.hwpx:
        raise ValueError("HWPX adapter requires a hwpx engine")
    return engine


def validate_hwpx_mutation_engine(engine: DocumentInspectionEngine) -> DocumentMutationEngine:
    """Validate that an injected HWPX engine can safely mutate derivatives."""
    validate_hwpx_engine(engine)
    if not isinstance(engine, DocumentMutationEngine):
        raise ValueError("HWPX adapter requires a mutation-capable engine")
    return engine
