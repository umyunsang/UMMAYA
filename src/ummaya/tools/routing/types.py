# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ummaya.tools.models import MockFidelityGrade

PrimitiveFamily = Literal["find", "locate", "send", "check", "document"]
SourceMode = Literal["live", "mock", "internal"]
SideEffectLevel = Literal["read_only", "login", "action", "sign", "send", "verify"]

LEGACY_ALIASES: Final[dict[PrimitiveFamily, tuple[str, ...]]] = {
    "find": ("lookup",),
    "locate": ("resolve_location",),
    "send": ("submit",),
    "check": ("verify",),
    "document": (),
}

INTENT_VERBS: Final[dict[PrimitiveFamily, tuple[str, ...]]] = {
    "find": ("find", "search", "lookup"),
    "locate": ("locate", "geocode", "resolve_location"),
    "send": ("send", "submit"),
    "check": ("check", "verify"),
    "document": ("inspect", "fill", "validate"),
}

RAW_SCHEMA_MARKERS: Final[tuple[str, ...]] = (
    "{",
    "$defs",
    '"properties"',
    "'properties'",
    "input_schema_json",
    "output_schema_json",
)


class AdapterCardError(ValueError):
    pass


class SchemaFieldSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    required: bool
    description: str | None = None


class AdapterCard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(min_length=1)
    primitive_family: PrimitiveFamily
    legacy_primitive_aliases: tuple[str, ...]
    domain: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    source_mode: SourceMode
    capabilities: tuple[str, ...]
    intent_verbs: tuple[str, ...]
    entity_types: tuple[str, ...]
    required_slots: tuple[str, ...]
    optional_slots: tuple[str, ...]
    prerequisite_tools: tuple[str, ...]
    input_schema_hash: str
    input_schema_summary: tuple[SchemaFieldSummary, ...]
    output_schema_summary: tuple[SchemaFieldSummary, ...]
    policy_authority_url: str | None
    safety_annotations: tuple[str, ...]
    side_effect_level: SideEffectLevel
    credential_requirements: tuple[str, ...]
    mock_fidelity_grade: MockFidelityGrade
    examples_ko: tuple[str, ...]
    examples_en: tuple[str, ...]
    negative_examples: tuple[str, ...]
    limitations: tuple[str, ...]
    manifest_hash: str
    routing_text: str = Field(min_length=1, max_length=4096)

    @field_validator("input_schema_hash", "manifest_hash")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("hash fields must be lowercase SHA-256 hex")
        return value


class AdapterCardQualityViolation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
