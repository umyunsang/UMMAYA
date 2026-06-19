# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from ummaya.evidence.source_provenance_redaction import (
    PromptInjectionState,
    RedactionCategory,
    detect_prompt_injection,
    ordered_redaction_categories,
    redact_source_text,
    redact_source_url,
    redaction_categories_for_text,
)
from ummaya.tools.routing.schema import sha256, unique

SourceKind = Literal["web", "mcp", "agent", "file"]
SourceUseState = Literal["used", "blocked"]
SourceTrust = Literal["trusted", "untrusted"]
SynthesisState = Literal[
    "eligible_for_synthesis",
    "blocked_pending_user_approval",
    "blocked_untrusted",
    "blocked_missing_source",
]
DocumentAuthoringState = Literal[
    "approved_for_document",
    "blocked_pending_user_approval",
    "blocked_untrusted",
    "blocked_missing_source",
]


class SourceRedactionMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    redacted: bool
    categories: tuple[RedactionCategory, ...] = Field(default_factory=tuple)
    raw_private_document_stored: Literal[False] = False
    secret_values_stored: Literal[False] = False
    pii_values_stored: Literal[False] = False

    @model_validator(mode="after")
    def _categories_match_redacted_flag(self) -> Self:
        if self.redacted and not self.categories:
            raise PydanticCustomError(
                "source_provenance_missing_redaction_categories",
                "redacted provenance requires redaction categories",
            )
        if not self.redacted and self.categories:
            raise PydanticCustomError(
                "source_provenance_unexpected_redaction_categories",
                "unredacted provenance cannot carry redaction categories",
            )
        return self


class SourceProvenanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_kind: SourceKind
    source_url: str | None
    local_evidence_handle: str | None
    title: str | None
    description: str | None
    tool_id: str = Field(min_length=1)
    observed_at: datetime
    state: SourceUseState
    citation_id: str = Field(min_length=1)
    provenance_id: str = Field(min_length=1)
    trust: SourceTrust
    prompt_injection: PromptInjectionState = "not_detected"
    redaction: SourceRedactionMetadata

    @field_validator(
        "source_url",
        "local_evidence_handle",
        "title",
        "description",
        "tool_id",
        "citation_id",
        "provenance_id",
    )
    @classmethod
    def _reject_unredacted_sensitive_value(cls, value: str | None) -> str | None:
        if value is not None and redaction_categories_for_text(value):
            raise PydanticCustomError(
                "source_provenance_unredacted_sensitive_value",
                "source provenance contains unredacted sensitive value",
            )
        return value

    @model_validator(mode="after")
    def _requires_source_handle_and_label(self) -> Self:
        if self.source_url is None and self.local_evidence_handle is None:
            raise PydanticCustomError(
                "source_provenance_missing_source",
                "source provenance requires source_url or local_evidence_handle",
            )
        if self.title is None and self.description is None:
            raise PydanticCustomError(
                "source_provenance_missing_label",
                "source provenance requires title or description when available",
            )
        return self


class SourceProvenanceDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(min_length=1)
    provenance_ids: tuple[str, ...] = Field(min_length=1)
    synthesis_state: SynthesisState
    document_authoring_state: DocumentAuthoringState
    requires_user_approval: bool
    approved_by_user: bool
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def _document_approval_requires_user_approval(self) -> Self:
        if self.document_authoring_state == "approved_for_document" and (
            self.requires_user_approval or not self.approved_by_user
        ):
            raise PydanticCustomError(
                "source_provenance_document_approval_missing_user_approval",
                "approved document authoring requires completed user approval",
            )
        return self


class SourceProvenanceLedger(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["source_provenance_ledger.v1"] = "source_provenance_ledger.v1"
    ledger_id: str = Field(min_length=1)
    records: tuple[SourceProvenanceRecord, ...] = Field(min_length=1)
    decisions: tuple[SourceProvenanceDecision, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _decisions_reference_known_provenance_ids(self) -> Self:
        known_ids = {record.provenance_id for record in self.records}
        if len(known_ids) != len(self.records):
            raise PydanticCustomError(
                "source_provenance_duplicate_ids",
                "source provenance ledger contains duplicate provenance ids",
            )
        unknown_ids = tuple(
            unique(
                provenance_id
                for decision in self.decisions
                for provenance_id in decision.provenance_ids
                if provenance_id not in known_ids
            )
        )
        if unknown_ids:
            raise PydanticCustomError(
                "source_provenance_unknown_ids",
                "unknown provenance ids: " + ", ".join(unknown_ids),
            )
        return self


def build_source_provenance_record(
    *,
    source_kind: SourceKind,
    tool_id: str,
    source_url: str | None,
    local_evidence_handle: str | None,
    title: str | None,
    description: str | None,
    observed_at: datetime,
    state: SourceUseState,
    trust: SourceTrust,
    citation_id: str,
) -> SourceProvenanceRecord:
    redacted_url, url_categories = redact_source_url(source_url)
    redacted_handle, handle_categories = redact_source_text(local_evidence_handle)
    redacted_title, title_categories = redact_source_text(title)
    redacted_description, description_categories = redact_source_text(description)
    categories = ordered_redaction_categories(
        (
            *url_categories,
            *handle_categories,
            *title_categories,
            *description_categories,
        )
    )
    prompt_injection_text_parts = (
        title or "",
        description or "",
        source_url or "",
        local_evidence_handle or "",
    )
    return SourceProvenanceRecord(
        source_kind=source_kind,
        source_url=redacted_url,
        local_evidence_handle=redacted_handle,
        title=redacted_title,
        description=redacted_description,
        tool_id=tool_id,
        observed_at=observed_at,
        state=state,
        citation_id=citation_id,
        provenance_id=stable_source_provenance_id(
            source_kind=source_kind,
            tool_id=tool_id,
            source_url=redacted_url,
            local_evidence_handle=redacted_handle,
            citation_id=citation_id,
        ),
        trust=trust,
        prompt_injection=detect_prompt_injection(
            "\n".join(part for part in prompt_injection_text_parts if part)
        ),
        redaction=SourceRedactionMetadata(
            redacted=bool(categories),
            categories=categories,
            raw_private_document_stored=False,
            secret_values_stored=False,
            pii_values_stored=False,
        ),
    )


def stable_source_provenance_id(
    *,
    source_kind: SourceKind,
    tool_id: str,
    source_url: str | None,
    local_evidence_handle: str | None,
    citation_id: str,
) -> str:
    digest = sha256(
        {
            "citation_id": citation_id,
            "local_evidence_handle": local_evidence_handle,
            "source_kind": source_kind,
            "source_url": source_url,
            "tool_id": tool_id,
        }
    )
    return f"prov-{digest[:24]}"
