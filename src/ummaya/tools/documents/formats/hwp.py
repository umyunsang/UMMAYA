# SPDX-License-Identifier: Apache-2.0
"""Legacy HWP engine-adapter boundary."""

from __future__ import annotations

from ummaya.tools.documents.engines import DocumentInspectionEngine
from ummaya.tools.documents.models import DocumentFormat

HWP_CANDIDATE_ENGINES: tuple[str, ...] = (
    "pyhwp-read-only",
    "OpenHWP-read-only",
    "hwp.js-read-only",
    "unhwp-read-only",
)


def validate_hwp_engine(engine: DocumentInspectionEngine) -> DocumentInspectionEngine:
    """Validate that an injected engine is scoped to HWP read/extract only."""
    if engine.document_format is not DocumentFormat.hwp:
        raise ValueError("HWP adapter requires a hwp engine")
    return engine
