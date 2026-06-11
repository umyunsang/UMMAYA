# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentAuthoringScenarioClass = Literal[
    "public_form_completion",
    "narrative_authoring",
    "unsupported_plausible_writing",
    "protected_field",
    "direct_hwp_path",
    "render_comparison",
]
DocumentAuthoringStatus = Literal["ready_for_review", "needs_input", "blocked"]
DocumentHwpDirectWriteState = Literal["blocked", "promoted", "not_applicable"]


class DocumentAuthoringCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    scenario_class: DocumentAuthoringScenarioClass
    correlation_id: str
    expected_status: DocumentAuthoringStatus
    requires_socratic_loop: bool
    requires_user_approval: bool
    mutation_allowed: bool
    render_comparison_required: bool
    hwp_direct_write_state: DocumentHwpDirectWriteState = "not_applicable"
    fixture_id: str | None = None
    evidence_ref: str
