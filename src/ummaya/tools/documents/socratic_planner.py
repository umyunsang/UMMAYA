# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from ummaya.tools.documents.models import FormSlot, ScalarValue

_NEEDS_INPUT_PREFIX: Final[str] = "needs_input:"
_BLOCKED_MISSING_EVIDENCE_PREFIX: Final[str] = "blocked_missing_evidence:"
_DRAFT_REQUIRES_APPROVAL_PREFIX: Final[str] = "draft_requires_approval:"

_FABRICATION_TERMS: Final[tuple[str, ...]] = (
    "대충",
    "그럴듯",
    "그럴싸",
    "적당히",
    "임의로",
)
_AUTHORING_TERMS: Final[tuple[str, ...]] = (
    "작성",
    "써줘",
    "써",
    "완성",
    "채워",
    "기입",
    "해줘",
)
_NARRATIVE_TERMS: Final[tuple[str, ...]] = (
    "자기소개",
    "지원동기",
    "성장과정",
    "경험",
    "경력",
    "수상",
    "사업계획",
    "계획",
    "시장",
    "예산",
    "성과",
    "목표",
    "제안내용",
    "문항",
    "에세이",
)


def apply_socratic_fill_gate(
    slot: FormSlot,
    *,
    instruction: str,
    session_context: Mapping[str, ScalarValue],
    explicit_value_provided: bool,
    context_value_provided: bool,
    broad_autonomous_fill: bool,
) -> FormSlot:
    if explicit_value_provided:
        return _with_provenance(slot, "user_provided_explicit_value")
    if slot.protected:
        return slot
    if _is_document_derived_candidate(slot):
        return _with_provenance(slot, "document_derived")
    if _instruction_requests_fabrication(instruction) and _slot_is_empty(slot):
        return _with_socratic_evidence(
            slot,
            prefix=_BLOCKED_MISSING_EVIDENCE_PREFIX,
            candidate_value=None,
        )
    if _is_narrative_slot(slot) and _slot_is_empty(slot):
        return _gate_narrative_slot(
            slot,
            session_context=session_context,
            context_value_provided=context_value_provided,
        )
    if broad_autonomous_fill and _slot_is_empty(slot):
        if context_value_provided:
            return _with_provenance(slot, "user_provided_context")
        return _with_socratic_evidence(slot, prefix=_NEEDS_INPUT_PREFIX, candidate_value=None)
    return slot


def socratic_slot_requires_input(slot: FormSlot) -> bool:
    return slot.evidence_text is not None and slot.evidence_text.startswith(
        (
            _NEEDS_INPUT_PREFIX,
            _BLOCKED_MISSING_EVIDENCE_PREFIX,
            _DRAFT_REQUIRES_APPROVAL_PREFIX,
        )
    )


def _gate_narrative_slot(
    slot: FormSlot,
    *,
    session_context: Mapping[str, ScalarValue],
    context_value_provided: bool,
) -> FormSlot:
    if not context_value_provided:
        return _with_socratic_evidence(slot, prefix=_NEEDS_INPUT_PREFIX, candidate_value=None)
    if _context_has_approval(slot, session_context):
        return slot.model_copy(update={"evidence_text": "approved_user_draft"})
    return _with_socratic_evidence(
        slot,
        prefix=_DRAFT_REQUIRES_APPROVAL_PREFIX,
        candidate_value=None,
    )


def _with_socratic_evidence(
    slot: FormSlot,
    *,
    prefix: str,
    candidate_value: ScalarValue,
) -> FormSlot:
    return slot.model_copy(
        update={
            "candidate_value": candidate_value,
            "evidence_text": f"{prefix}{_question_for_slot(slot)}",
        }
    )


def _with_provenance(slot: FormSlot, evidence_text: str) -> FormSlot:
    if slot.candidate_value is None or slot.evidence_text is not None:
        return slot
    return slot.model_copy(update={"evidence_text": evidence_text})


def _question_for_slot(slot: FormSlot) -> str:
    return f"{slot.label} 항목을 작성할 사용자 제공 근거를 알려주세요."


def _is_document_derived_candidate(slot: FormSlot) -> bool:
    if slot.candidate_value is None:
        return False
    slot_key = _slot_key(slot)
    if ("주차" in slot_key or "week" in slot_key) and slot.current_value is not None:
        return True
    return (
        "활동기간" in slot_key or "활동일시" in slot_key or "period" in slot_key
    ) and slot.current_value is not None


def _is_narrative_slot(slot: FormSlot) -> bool:
    slot_key = _slot_key(slot)
    return any(term in slot_key for term in _NARRATIVE_TERMS)


def _instruction_requests_fabrication(instruction: str) -> bool:
    instruction_key = _normalize_key(instruction)
    return any(term in instruction_key for term in _FABRICATION_TERMS) and any(
        term in instruction_key for term in _AUTHORING_TERMS
    )


def _context_has_approval(
    slot: FormSlot,
    session_context: Mapping[str, ScalarValue],
) -> bool:
    approval_keys = _approval_keys_for_slot(slot)
    for key, value in session_context.items():
        if _normalize_key(key) not in approval_keys:
            continue
        if value is True:
            return True
        if isinstance(value, str) and _normalize_key(value) in {"승인", "approved", "approve"}:
            return True
    return False


def _approval_keys_for_slot(slot: FormSlot) -> set[str]:
    keys: set[str] = set()
    for label in (slot.slot_id, slot.label, slot.source_anchor.format_path):
        normalized = _normalize_key(label)
        keys.add(f"approved{normalized}")
        keys.add(f"approval{normalized}")
        keys.add(f"승인{normalized}")
    return keys


def _slot_is_empty(slot: FormSlot) -> bool:
    value = slot.current_value
    return value is None or (isinstance(value, str) and value.strip() == "")


def _slot_key(slot: FormSlot) -> str:
    return _normalize_key(f"{slot.slot_id} {slot.label} {slot.source_anchor.format_path}")


def _normalize_key(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())
