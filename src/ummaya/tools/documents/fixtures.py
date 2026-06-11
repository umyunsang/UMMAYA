# SPDX-License-Identifier: Apache-2.0
"""Offline fixture manifest helpers for document harness tests."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SupportedFixtureFormat = Literal["hwpx", "hwp", "docx", "pdf", "xlsx", "pptx"]
FixtureAuthoringFlow = Literal[
    "read_only",
    "public_form_fill",
    "socratic_narrative",
    "blocked_hostile",
]
FixtureCoverageTag = Literal[
    "form_blanks",
    "self_introduction",
    "business_plan",
    "protected_fields",
    "missing_evidence",
    "approved_draft_mutation",
    "direct_hwp_blocked",
]
RedistributionStatus = Literal[
    "owned",
    "public_domain",
    "open_license",
    "metadata_only",
    "not_redistributable",
]

DEFAULT_FIXTURE_MANIFEST_PATH = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "documents"
    / "corpus_manifest.yaml"
)


class DocumentFixtureEntry(BaseModel):
    """One offline fixture declared in the document corpus manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fixture_id: str = Field(min_length=1)
    format: SupportedFixtureFormat
    path: str = Field(min_length=1)
    source: str = Field(min_length=1)
    redistribution_status: RedistributionStatus
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    authoring_flow: FixtureAuthoringFlow = "read_only"
    expected_authoring_flow: tuple[str, ...] = ()
    expected_fields: tuple[str, ...] = ()
    expected_narrative_prompts: tuple[str, ...] = ()
    expected_layout_anchors: tuple[str, ...] = ()
    protected_field_expectations: tuple[str, ...] = ()
    coverage_tags: tuple[FixtureCoverageTag, ...] = ()
    negative_case: str | None = None

    @field_validator(
        "expected_authoring_flow",
        "expected_fields",
        "expected_narrative_prompts",
        "expected_layout_anchors",
        "protected_field_expectations",
        "coverage_tags",
    )
    @classmethod
    def _tuple_values_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("fixture metadata tuple values must be unique")
        return values


class DocumentFixtureGroups(BaseModel):
    """Fixture groups separated by expected safety posture."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benign: tuple[DocumentFixtureEntry, ...] = ()
    public_forms: tuple[DocumentFixtureEntry, ...] = ()
    narrative_authoring: tuple[DocumentFixtureEntry, ...] = ()
    hostile: tuple[DocumentFixtureEntry, ...] = ()


class DocumentFixtureManifest(BaseModel):
    """Offline document fixture manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1]
    manifest_id: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    source_policy: Literal["offline_fixtures_only"]
    live_network_allowed: Literal[False]
    formats: tuple[SupportedFixtureFormat, ...] = Field(min_length=1)
    fixture_groups: DocumentFixtureGroups
    requirements: dict[str, str]

    @model_validator(mode="after")
    def _require_known_format_groups(self) -> DocumentFixtureManifest:
        declared = set(self.formats)
        for entry in (
            *self.fixture_groups.benign,
            *self.fixture_groups.public_forms,
            *self.fixture_groups.narrative_authoring,
            *self.fixture_groups.hostile,
        ):
            if entry.format not in declared:
                raise ValueError(
                    f"Fixture {entry.fixture_id!r} uses undeclared format {entry.format!r}"
                )
        return self

    @model_validator(mode="after")
    def _require_matrix_metadata(self) -> DocumentFixtureManifest:
        for entry in (
            *self.fixture_groups.public_forms,
            *self.fixture_groups.narrative_authoring,
        ):
            _require_common_matrix_metadata(entry)
        for entry in self.fixture_groups.public_forms:
            _require_public_form_matrix_metadata(entry)
        for entry in self.fixture_groups.narrative_authoring:
            _require_narrative_matrix_metadata(entry)
        return self


def load_fixture_manifest(
    path: Path = DEFAULT_FIXTURE_MANIFEST_PATH,
) -> DocumentFixtureManifest:
    """Load and validate the offline document fixture manifest."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Fixture manifest must be a YAML object: {path}")
    return DocumentFixtureManifest.model_validate(cast(dict[str, object], raw))


def _require_common_matrix_metadata(entry: DocumentFixtureEntry) -> None:
    if entry.size_bytes is None:
        raise ValueError(f"Fixture {entry.fixture_id!r} must declare size_bytes")
    if entry.sha256 is None:
        raise ValueError(f"Fixture {entry.fixture_id!r} must declare sha256")
    if not entry.expected_authoring_flow:
        raise ValueError(f"Fixture {entry.fixture_id!r} must declare expected_authoring_flow")
    if not entry.protected_field_expectations:
        raise ValueError(f"Fixture {entry.fixture_id!r} must declare protected_field_expectations")
    if not entry.coverage_tags:
        raise ValueError(f"Fixture {entry.fixture_id!r} must declare coverage_tags")


def _require_public_form_matrix_metadata(entry: DocumentFixtureEntry) -> None:
    if entry.authoring_flow != "public_form_fill":
        raise ValueError(f"Public form fixture {entry.fixture_id!r} has wrong flow")
    if not entry.expected_fields:
        raise ValueError(f"Public form fixture {entry.fixture_id!r} needs fields")


def _require_narrative_matrix_metadata(entry: DocumentFixtureEntry) -> None:
    if entry.authoring_flow != "socratic_narrative":
        raise ValueError(f"Narrative fixture {entry.fixture_id!r} has wrong flow")
    if not entry.expected_narrative_prompts:
        raise ValueError(f"Narrative fixture {entry.fixture_id!r} needs narrative prompts")
