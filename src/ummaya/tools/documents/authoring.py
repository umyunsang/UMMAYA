# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from enum import StrEnum
from hashlib import sha256
from typing import Final, assert_never

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from ummaya.tools.documents.models import DocumentToolResult, ToolResultStatus

_SHA256_PATTERN: Final[str] = r"^[a-f0-9]{64}$"
_REDACTED_DOCUMENT_CONTENT: Final[str] = "[redacted-document-content]"
_RAW_DOCUMENT_MARKERS: Final[tuple[str, ...]] = (
    "%pdf",
    "raw document bytes",
    "/users/",
    "\\users\\",
)
_COMMON_PII_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"\b\d{6}-\d{7}\b"), "[redacted-rrn]"),
    (re.compile(r"\b01[016789]-\d{3,4}-\d{4}\b"), "[redacted-phone]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[redacted-email]"),
)


class StrictAuthoringModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class EvidenceSourceKind(StrEnum):
    user_provided = "user_provided"
    document_derived = "document_derived"
    policy_derived = "policy_derived"


class ApprovalDecisionKind(StrEnum):
    approved = "approved"
    edited = "edited"
    leave_blank = "leave_blank"
    cancel = "cancel"


class AuthoringState(StrEnum):
    needs_input = "needs_input"
    draft_ready_for_approval = "draft_ready_for_approval"
    approved_for_mutation = "approved_for_mutation"
    blocked_missing_evidence = "blocked_missing_evidence"


class AmbiguityClassification(StrEnum):
    blocking = "blocking"
    non_blocking_engineering = "non_blocking_engineering"


class AuthoringEvidenceItem(StrictAuthoringModel):
    evidence_id: str = Field(min_length=1)
    source_kind: EvidenceSourceKind
    summary: str = Field(min_length=1, max_length=1200)
    source_ref: str | None = Field(default=None, min_length=1, max_length=300)
    redacted_excerpt: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_serializer("summary", "source_ref", "redacted_excerpt", when_used="json")
    def _serialize_redacted_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        return redact_authoring_text(value)


class SocraticQuestion(StrictAuthoringModel):
    question_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=800)
    required: bool


class UserAnswer(StrictAuthoringModel):
    answer_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    response_summary: str = Field(min_length=1, max_length=1200)
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @field_serializer("response_summary", when_used="json")
    def _serialize_response_summary(self, value: str) -> str:
        return redact_authoring_text(value)


class DraftClaim(StrictAuthoringModel):
    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=2000)
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @field_serializer("text", when_used="json")
    def _serialize_text(self, value: str) -> str:
        return redact_authoring_text(value)


class DraftCandidate(StrictAuthoringModel):
    draft_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    draft_text: str = Field(min_length=1, max_length=8000)
    draft_sha256: str = Field(pattern=_SHA256_PATTERN)
    claims: tuple[DraftClaim, ...] = Field(min_length=1)
    evidence_items: tuple[AuthoringEvidenceItem, ...] = ()

    @field_serializer("draft_text", when_used="json")
    def _serialize_draft_text(self, value: str) -> str:
        return redact_authoring_text(value)

    @model_validator(mode="after")
    def _validate_draft_hash_and_claim_refs(self) -> DraftCandidate:
        if self.draft_sha256 != hash_authoring_text(self.draft_text):
            raise ValueError("draft_sha256 must match draft_text")
        if self.evidence_items:
            _require_known_evidence_refs(self.claims, self.evidence_items)
        return self


class ApprovalDecision(StrictAuthoringModel):
    approval_id: str = Field(min_length=1)
    draft_id: str = Field(min_length=1)
    decision: ApprovalDecisionKind
    draft_sha256: str = Field(pattern=_SHA256_PATTERN)
    approved_text_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _validate_approved_text_hash(self) -> ApprovalDecision:
        match self.decision:
            case ApprovalDecisionKind.approved | ApprovalDecisionKind.edited:
                if self.approved_text_sha256 is None:
                    raise ValueError("approved decisions require approved_text_sha256")
            case ApprovalDecisionKind.leave_blank | ApprovalDecisionKind.cancel:
                if self.approved_text_sha256 is not None:
                    raise ValueError("blank or cancel decisions cannot carry approved_text_sha256")
            case unreachable:
                assert_never(unreachable)
        return self


class AmbiguityRecord(StrictAuthoringModel):
    ambiguity_id: str = Field(min_length=1)
    classification: AmbiguityClassification
    evidence_path: str | None = Field(default=None, min_length=1)
    reviewer_verdict_id: str | None = Field(default=None, min_length=1)
    required_next_question: str | None = Field(default=None, min_length=1, max_length=800)

    @field_serializer("evidence_path", "required_next_question", when_used="json")
    def _serialize_redacted_metadata(self, value: str | None) -> str | None:
        if value is None:
            return None
        return redact_authoring_text(value)


class AuthoringClosureVerdict(StrictAuthoringModel):
    state: AuthoringState
    target_id: str = Field(min_length=1)
    evidence_items: tuple[AuthoringEvidenceItem, ...] = ()
    questions: tuple[SocraticQuestion, ...] = ()
    answers: tuple[UserAnswer, ...] = ()
    draft: DraftCandidate | None = None
    approval: ApprovalDecision | None = None
    ambiguities: tuple[AmbiguityRecord, ...] = ()

    @model_validator(mode="after")
    def _validate_state_contract(self) -> AuthoringClosureVerdict:
        _validate_answer_refs(self.answers, self.questions, self.evidence_items)
        if self.draft is not None:
            _require_known_evidence_refs(self.draft.claims, self.evidence_items)
        _validate_closure_state(self)
        return self


class DocumentAuthoringResult(DocumentToolResult):
    authoring: AuthoringClosureVerdict

    @model_validator(mode="after")
    def _validate_authoring_status(self) -> DocumentAuthoringResult:
        match self.authoring.state:
            case AuthoringState.needs_input | AuthoringState.draft_ready_for_approval:
                if self.status is not ToolResultStatus.needs_input:
                    raise ValueError(
                        f"{self.authoring.state.value} authoring results require status needs_input"
                    )
            case AuthoringState.approved_for_mutation:
                if self.status is not ToolResultStatus.ok:
                    raise ValueError("approved_for_mutation authoring results require status ok")
            case AuthoringState.blocked_missing_evidence:
                if self.status is not ToolResultStatus.blocked:
                    raise ValueError(
                        "blocked_missing_evidence authoring results require status blocked"
                    )
            case unreachable:
                assert_never(unreachable)
        return self


def hash_authoring_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def redact_authoring_text(value: str) -> str:
    lowered = value.lower()
    if any(marker in lowered for marker in _RAW_DOCUMENT_MARKERS):
        return _REDACTED_DOCUMENT_CONTENT
    redacted = value
    for pattern, replacement in _COMMON_PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _require_known_evidence_refs(
    claims: tuple[DraftClaim, ...],
    evidence_items: tuple[AuthoringEvidenceItem, ...],
) -> None:
    known_ids = {item.evidence_id for item in evidence_items}
    for claim in claims:
        unknown_refs = tuple(ref for ref in claim.evidence_refs if ref not in known_ids)
        if unknown_refs:
            raise ValueError(f"unknown evidence reference: {unknown_refs[0]}")


def _validate_answer_refs(
    answers: tuple[UserAnswer, ...],
    questions: tuple[SocraticQuestion, ...],
    evidence_items: tuple[AuthoringEvidenceItem, ...],
) -> None:
    known_questions = {question.question_id for question in questions}
    known_evidence = {item.evidence_id for item in evidence_items}
    for answer in answers:
        if answer.question_id not in known_questions:
            raise ValueError("answers must reference known questions")
        if known_evidence:
            unknown_refs = tuple(ref for ref in answer.evidence_refs if ref not in known_evidence)
            if unknown_refs:
                raise ValueError(f"unknown answer evidence reference: {unknown_refs[0]}")


def _validate_closure_state(verdict: AuthoringClosureVerdict) -> None:
    match verdict.state:
        case AuthoringState.needs_input | AuthoringState.blocked_missing_evidence:
            _validate_question_waiting_state(verdict)
        case AuthoringState.draft_ready_for_approval:
            _validate_draft_ready_state(verdict)
        case AuthoringState.approved_for_mutation:
            _validate_approved_state(verdict)
        case unreachable:
            assert_never(unreachable)


def _validate_question_waiting_state(verdict: AuthoringClosureVerdict) -> None:
    if not verdict.questions:
        raise ValueError(f"{verdict.state.value} requires questions")
    if verdict.draft is not None:
        raise ValueError(f"{verdict.state.value} cannot carry draft")
    if verdict.approval is not None:
        raise ValueError(f"{verdict.state.value} cannot carry approval")


def _validate_draft_ready_state(verdict: AuthoringClosureVerdict) -> None:
    if verdict.draft is None:
        raise ValueError("draft_ready_for_approval requires draft")
    if verdict.approval is not None:
        raise ValueError("draft_ready_for_approval cannot carry approval")


def _validate_approved_state(verdict: AuthoringClosureVerdict) -> None:
    if verdict.draft is None:
        raise ValueError("approved_for_mutation requires draft")
    if verdict.approval is None:
        raise ValueError("approved_for_mutation requires approval")
    match verdict.approval.decision:
        case ApprovalDecisionKind.approved | ApprovalDecisionKind.edited:
            pass
        case ApprovalDecisionKind.leave_blank | ApprovalDecisionKind.cancel:
            raise ValueError("approved_for_mutation requires an approval decision")
        case unreachable:
            assert_never(unreachable)
    if verdict.approval.draft_id != verdict.draft.draft_id:
        raise ValueError("approval draft_id must match draft")
    if verdict.approval.draft_sha256 != verdict.draft.draft_sha256:
        raise ValueError("approval draft_sha256 must match draft")
