# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

ActivePrimitive = Literal["find", "locate", "send", "check"]

ACTIVE_PRIMITIVES: Final[tuple[ActivePrimitive, ...]] = ("find", "locate", "send", "check")
LEGACY_PRIMITIVE_ALIASES: Final[dict[str, ActivePrimitive]] = {
    "lookup": "find",
    "resolve_location": "locate",
    "submit": "send",
    "verify": "check",
}


class ToolSelectionIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_query: str
    normalized_query: str
    intent_verbs: tuple[ActivePrimitive, ...]
    entities: tuple[str, ...]
    document_refs: tuple[str, ...]
    location_refs: tuple[str, ...]
    time_refs: tuple[str, ...]
    public_data_refs: tuple[str, ...]
    credential_refs: tuple[str, ...]
    side_effect_markers: tuple[str, ...]
    explicit_tool_ids: tuple[str, ...]
    explicit_artifact_ids: tuple[str, ...]
    candidate_primitives: tuple[ActivePrimitive, ...]
    missing_slots: tuple[str, ...]
    unsafe_assumptions: tuple[str, ...]
    requires_clarification: bool
    requires_permission: bool

    def has_location_ref(self, value: str) -> bool:
        return value in self.location_refs

    def has_public_data_ref(self, value: str) -> bool:
        return value in self.public_data_refs

    def has_document_ref(self, value: str) -> bool:
        return value in self.document_refs
