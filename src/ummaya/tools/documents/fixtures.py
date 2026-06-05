# SPDX-License-Identifier: Apache-2.0
"""Offline fixture manifest helpers for document harness tests."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SupportedFixtureFormat = Literal["hwpx", "hwp", "docx", "pdf", "xlsx", "pptx"]
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
    expected_fields: tuple[str, ...] = ()
    expected_layout_anchors: tuple[str, ...] = ()
    negative_case: str | None = None


class DocumentFixtureGroups(BaseModel):
    """Fixture groups separated by expected safety posture."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benign: tuple[DocumentFixtureEntry, ...] = ()
    public_forms: tuple[DocumentFixtureEntry, ...] = ()
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
            *self.fixture_groups.hostile,
        ):
            if entry.format not in declared:
                raise ValueError(
                    f"Fixture {entry.fixture_id!r} uses undeclared format {entry.format!r}"
                )
        return self


def load_fixture_manifest(
    path: Path = DEFAULT_FIXTURE_MANIFEST_PATH,
) -> DocumentFixtureManifest:
    """Load and validate the offline document fixture manifest."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Fixture manifest must be a YAML object: {path}")
    return DocumentFixtureManifest.model_validate(cast(dict[str, object], raw))
