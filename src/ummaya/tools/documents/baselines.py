# SPDX-License-Identifier: Apache-2.0
"""Public-form conformance baseline models and fixture loader."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ummaya.tools.documents.models import DocumentFormat, MetadataValue

CONFORMANCE_BASELINE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "documents"
    / "public_forms"
    / "baselines.yaml"
)


class BaselineField(BaseModel):
    """Required field declared by a public-form conformance baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    path: str = Field(min_length=1)


class BaselineTextAnchor(BaseModel):
    """Protected text or label that must remain present at a known anchor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    anchor: str = Field(min_length=1)


class BaselineTableGeometry(BaseModel):
    """Expected row and column geometry for a protected public-form table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table_id: str = Field(min_length=1)
    anchor: str = Field(min_length=1)
    rows: int = Field(ge=1)
    columns: int = Field(ge=1)


class ConformanceBaseline(BaseModel):
    """Format-specific public-form conformance rule set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str = Field(min_length=1)
    schema_id: str = Field(min_length=1)
    format: DocumentFormat
    authoritative_standard: str = Field(min_length=1)
    authority_refs: tuple[str, ...] = Field(min_length=1)
    supports_conformance: bool
    unsupported_reason: str | None = None
    expected_page_count: int | None = Field(default=None, ge=1)
    required_fields: tuple[BaselineField, ...] = ()
    protected_text: tuple[BaselineTextAnchor, ...] = ()
    required_labels: tuple[BaselineTextAnchor, ...] = ()
    table_geometries: tuple[BaselineTableGeometry, ...] = ()
    signature_regions: tuple[BaselineTextAnchor, ...] = ()
    metadata_exact_matches: dict[str, MetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_unsupported_reason(self) -> ConformanceBaseline:
        if not self.supports_conformance and not self.unsupported_reason:
            raise ValueError("unsupported conformance baselines require unsupported_reason")
        return self


class ConformanceBaselineCatalog(BaseModel):
    """Offline catalog of public-form conformance baselines."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1]
    catalog_id: str = Field(min_length=1)
    source_policy: Literal["offline_fixtures_only"]
    live_network_allowed: Literal[False]
    baselines: tuple[ConformanceBaseline, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_unique_template_ids(self) -> ConformanceBaselineCatalog:
        template_ids = [baseline.template_id for baseline in self.baselines]
        if len(set(template_ids)) != len(template_ids):
            raise ValueError("template_id values must be unique")
        return self

    def by_template_id(self, template_id: str) -> ConformanceBaseline:
        """Return one baseline by stable template ID."""
        for baseline in self.baselines:
            if baseline.template_id == template_id:
                return baseline
        raise KeyError(f"Unknown public-form conformance baseline: {template_id}")


def load_conformance_baselines(
    path: Path = CONFORMANCE_BASELINE_FIXTURE_PATH,
) -> ConformanceBaselineCatalog:
    """Load checked-in public-form conformance baselines from YAML."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Conformance baseline manifest must be a YAML object: {path}")
    return ConformanceBaselineCatalog.model_validate(cast(dict[str, object], raw))
