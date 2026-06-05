# SPDX-License-Identifier: Apache-2.0
"""Deterministic autonomous-fill planning over document IR."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from ummaya.tools.documents.models import (
    AutonomousFillPlan,
    AutonomousSaveIntent,
    AutonomousStyleIntent,
    DocumentIntent,
    DocumentIR,
    DocumentProtectedRange,
    FormSlot,
    StyleAlignment,
    StyleDescriptor,
)

_WEEK_LABEL_RE = re.compile(r"(?P<week>[0-9]{1,3})\s*주\s*차")
_DATE_RANGE_RE = re.compile(
    r"(?P<start>[0-9]{4}\.[0-9]{2}\.[0-9]{2})\s*(?:~|〜|-)\s*"
    r"(?P<end>[0-9]{4}\.[0-9]{2}\.[0-9]{2})"
)
_SAVE_CLAUSE_RE = re.compile(
    r"\s*,?\s*(?:저장|내보내|export|save)\s*(?:은|는|:|=)?.*$",
    re.IGNORECASE,
)
_SAVE_PATH_RE = re.compile(
    r"(?:저장|내보내|export|save)\s*(?:은|는|:|=)?\s*"
    r"(?P<path>(?:~|/|[A-Za-z]:)[^\s,;]+?\.(?:docx|hwpx|hwp|pdf|xlsx|pptx))",
    re.IGNORECASE,
)
_UPDATE_TAIL_RE = re.compile(
    r"\s+(?:로|으로)\s*(?:갱신|변경|수정|작성|입력|채우|해줘).*$",
    re.IGNORECASE,
)
_HEX_COLOR_RE = re.compile(r"\b(?P<hex>[0-9A-Fa-f]{6})\b")
_FONT_SIZE_RE = re.compile(r"(?P<size>[0-9]{1,2}(?:\.[0-9]+)?)\s*(?:pt|포인트)", re.IGNORECASE)
_PROTECTED_TERMS = (
    "서명",
    "signature",
    "동의",
    "consent",
    "주민등록",
    "성명",
    "이름",
    "신청인",
    "applicant",
    "계좌",
    "전화",
    "주소",
    "인감",
    "날인",
)
_LEGAL_ACTION_TERMS = (
    "서명",
    "signature",
    "동의",
    "consent",
    "인감",
    "날인",
)


def plan_autonomous_fill(
    document_ir: DocumentIR,
    *,
    instruction: str,
    session_context: Mapping[str, object] | None = None,
) -> AutonomousFillPlan:
    """Build a deterministic fill plan from document IR and user intent."""
    intent = DocumentIntent(
        intent_id=f"intent-{document_ir.artifact_id}",
        operation="fill",
        instruction=instruction,
        confidence=_intent_confidence(instruction),
    )
    planned_slots = _planned_slots(
        document_ir,
        instruction=instruction,
        session_context=session_context or {},
    )
    blocked_slot_ids = tuple(
        slot.slot_id
        for slot in planned_slots
        if slot.protected or _missing_required_slot(slot, instruction)
    )
    style_intents = _style_intents_from_instruction(
        instruction,
        planned_slots=planned_slots,
        blocked_slot_ids=blocked_slot_ids,
    )
    return AutonomousFillPlan(
        plan_id=f"plan-{document_ir.artifact_id}",
        artifact_id=document_ir.artifact_id,
        intent=intent,
        slots=planned_slots,
        style_intents=style_intents,
        save_intent=_save_intent_from_instruction(instruction),
        blocked_slot_ids=blocked_slot_ids,
        requires_human_review=bool(blocked_slot_ids),
        confidence=_plan_confidence(planned_slots, intent.confidence),
    )


def public_document_writing_profile() -> tuple[str, ...]:
    """Return public-form writing constraints used by autonomous fill planning."""
    return (
        "clear_subject_predicate",
        "plain_public_korean",
        "standard_numbering_ladder",
        "simple_tables_no_complex_merges",
        "protected_legal_text_preserved",
    )


def _planned_slots(
    document_ir: DocumentIR,
    *,
    instruction: str,
    session_context: Mapping[str, object],
) -> tuple[FormSlot, ...]:
    slots: list[FormSlot] = []
    seen_slot_ids: set[str] = set()
    seen_slot_paths: set[str] = set()
    seen_explicit_label_keys: set[str] = set()
    for slot in document_ir.form_slots:
        protected_range = _protected_range_for_slot(document_ir, slot)
        protected_slot_requested = _protected_slot_requested(slot, instruction)
        broad_autonomous_fill = _instruction_requests_broad_autonomous_fill(instruction)
        planned_slot = _planned_slot(
            slot,
            instruction=instruction,
            session_context=session_context,
            protected_range=protected_range,
        )
        protected_requested = (
            protected_range is not None
            and (broad_autonomous_fill or protected_slot_requested)
        )
        missing_required = _missing_required_slot(planned_slot, instruction)
        slot_is_protected_context = (
            slot.protected or protected_range is not None or _slot_has_protected_semantics(slot)
        )
        if (
            slot_is_protected_context
            and not broad_autonomous_fill
            and not protected_slot_requested
            and planned_slot.candidate_value is None
        ):
            missing_required = False
        explicit_label_key = (
            _explicit_slot_label_key(slot, instruction)
            if planned_slot.candidate_value is not None
            else None
        )
        if explicit_label_key is not None:
            if explicit_label_key in seen_explicit_label_keys:
                continue
            seen_explicit_label_keys.add(explicit_label_key)
        if (
            planned_slot.candidate_value is not None
            or protected_slot_requested
            or protected_requested
            or missing_required
        ):
            _append_planned_slot(
                slots,
                planned_slot,
                seen_slot_ids=seen_slot_ids,
                seen_slot_paths=seen_slot_paths,
            )
    return tuple(slots)


def _append_planned_slot(
    slots: list[FormSlot],
    planned_slot: FormSlot,
    *,
    seen_slot_ids: set[str],
    seen_slot_paths: set[str],
) -> None:
    source_path = planned_slot.source_anchor.format_path
    if source_path in seen_slot_paths:
        return
    unique_slot = planned_slot
    if planned_slot.slot_id in seen_slot_ids:
        unique_slot = planned_slot.model_copy(
            update={
                "slot_id": _unique_planned_slot_id(
                    planned_slot.slot_id,
                    source_path=source_path,
                    seen_slot_ids=seen_slot_ids,
                )
            }
        )
    seen_slot_ids.add(unique_slot.slot_id)
    seen_slot_paths.add(source_path)
    slots.append(unique_slot)


def _unique_planned_slot_id(
    slot_id: str,
    *,
    source_path: str,
    seen_slot_ids: set[str],
) -> str:
    suffix = sha256(source_path.encode("utf-8")).hexdigest()[:8]
    candidate = f"{slot_id}__{suffix}"
    counter = 2
    while candidate in seen_slot_ids:
        candidate = f"{slot_id}__{suffix}_{counter}"
        counter += 1
    return candidate


def _planned_slot(
    slot: FormSlot,
    *,
    instruction: str,
    session_context: Mapping[str, object],
    protected_range: DocumentProtectedRange | None,
) -> FormSlot:
    if slot.protected or protected_range is not None or _slot_has_protected_semantics(slot):
        explicit_value = _explicit_keyed_value(slot, instruction)
        if explicit_value is not None and not _slot_has_legal_action_semantics(slot):
            return slot.model_copy(
                update={
                    "candidate_value": explicit_value,
                    "protected": False,
                    "evidence_text": "user_provided_explicit_value",
                }
            )
        return slot.model_copy(
            update={
                "candidate_value": _protected_candidate(slot, instruction),
                "protected": True,
                "evidence_text": protected_range.reason if protected_range is not None else None,
            }
        )
    candidate = _candidate_value_for_slot(
        slot,
        instruction=instruction,
        session_context=session_context,
    )
    return slot.model_copy(update={"candidate_value": candidate})


def _protected_range_for_slot(
    document_ir: DocumentIR,
    slot: FormSlot,
) -> DocumentProtectedRange | None:
    for protected_range in document_ir.protected_ranges:
        if "autonomous_fill" not in protected_range.blocked_operations:
            continue
        if protected_range.source_anchor.format_path == slot.source_anchor.format_path:
            return protected_range
    return None


def _candidate_value_for_slot(
    slot: FormSlot,
    *,
    instruction: str,
    session_context: Mapping[str, object],
) -> object:
    slot_key = _slot_key(slot)
    if _is_week_slot(slot_key):
        return _explicit_week_value(instruction) or _next_week_value(slot.current_value)
    if _is_activity_period_slot(slot_key):
        return _explicit_date_range(instruction) or _next_date_range(slot.current_value)
    explicit_value = _explicit_keyed_value(slot, instruction)
    if explicit_value is not None:
        return explicit_value
    context_value = _session_context_value(slot, session_context)
    if context_value is not None:
        return context_value
    return None


def _protected_candidate(slot: FormSlot, instruction: str) -> object:
    if not _protected_slot_requested(slot, instruction):
        return None
    return None


def _protected_slot_requested(slot: FormSlot, instruction: str) -> bool:
    instruction_key = _normalize_key(instruction)
    return _slot_has_protected_semantics(slot) and (
        _instruction_requests_broad_autonomous_fill(instruction)
        or any(term in instruction_key for term in _PROTECTED_TERMS)
    )


def _slot_has_protected_semantics(slot: FormSlot) -> bool:
    slot_key = _slot_key(slot)
    return any(term in slot_key for term in _PROTECTED_TERMS)


def _slot_has_legal_action_semantics(slot: FormSlot) -> bool:
    slot_key = _slot_key(slot)
    return any(term in slot_key for term in _LEGAL_ACTION_TERMS)


def _explicit_keyed_value(slot: FormSlot, instruction: str) -> str | None:
    labels = (slot.label, slot.slot_id)
    for label in labels:
        value = _explicit_keyed_value_for_label(label, instruction)
        if value is not None:
            return value
    return None


def _explicit_slot_label_key(slot: FormSlot, instruction: str) -> str | None:
    for label in (slot.label, slot.slot_id):
        if _explicit_keyed_value_for_label(label, instruction) is not None:
            return _normalize_key(label)
    return None


def _explicit_keyed_value_for_label(label: str, instruction: str) -> str | None:
    if not _is_meaningful_explicit_label(label):
        return None
    adjacent_blank_match = re.search(
        rf"{re.escape(label)}\s*"
        r"(?:옆|다음|우측|오른쪽)?\s*"
        r"(?:빈\s*칸|칸|필드|항목)?\s*"
        r"(?:에는|엔|에)\s*"
        r"(?P<value>[^.!?。\n]+?)\s*(?:을|를)?\s*"
        r"(?:넣|입력|작성|채우|수정|변경|갱신)",
        instruction,
        flags=re.IGNORECASE,
    )
    if adjacent_blank_match is not None:
        value = _clean_explicit_keyed_value(adjacent_blank_match.group("value"))
        return value or None
    field_word_match = re.search(
        rf"{re.escape(label)}\s*(?:은|는|이|가)?\s*(?:필드|칸|항목)?\s*"
        r"(?:은|는|이|가|을|를)?\s*"
        r"(?P<value>[^.!?。\n]+?)\s*(?:로|으로)\s*"
        r"(?:작성|입력|채우|수정|변경|갱신)",
        instruction,
        flags=re.IGNORECASE,
    )
    if field_word_match is not None:
        value = _clean_explicit_keyed_value(field_word_match.group("value"))
        return value or None
    match = re.search(
        rf"{re.escape(label)}\s*(?:은|는|:|=)\s*(?P<value>[^.!?。\n]+[.!?。]?)",
        instruction,
        flags=re.IGNORECASE,
    )
    if match is not None:
        value = _clean_explicit_keyed_value(match.group("value"))
        return value or None
    return None


def _is_meaningful_explicit_label(label: str) -> bool:
    label_key = _normalize_key(label)
    if len(label_key) < 2:
        return False
    return any("a" <= char <= "z" or "가" <= char <= "힣" for char in label_key)


def _clean_explicit_keyed_value(value: str) -> str:
    cleaned = _SAVE_CLAUSE_RE.sub("", value).strip()
    cleaned = _UPDATE_TAIL_RE.sub("", cleaned).strip()
    return cleaned.strip(" ,;:)]}）")


def _style_intents_from_instruction(
    instruction: str,
    *,
    planned_slots: tuple[FormSlot, ...],
    blocked_slot_ids: tuple[str, ...],
) -> tuple[AutonomousStyleIntent, ...]:
    blocked = set(blocked_slot_ids)
    style_intents: list[AutonomousStyleIntent] = []
    for slot in planned_slots:
        if slot.slot_id in blocked or slot.protected or slot.candidate_value is None:
            continue
        style = _style_descriptor_from_instruction(
            instruction,
            target_path=slot.source_anchor.format_path,
        )
        if style is None:
            continue
        style_intents.append(
            AutonomousStyleIntent(
                intent_id=f"style-{slot.slot_id}",
                source_slot_id=slot.slot_id,
                target_path=slot.source_anchor.format_path,
                style=style,
                confidence=Decimal("0.70"),
            )
        )
    return tuple(style_intents)


def _style_descriptor_from_instruction(
    instruction: str,
    *,
    target_path: str,
) -> StyleDescriptor | None:
    font_family = _font_family_from_instruction(instruction)
    font_size_pt = _font_size_from_instruction(instruction)
    bold = _bold_from_instruction(instruction)
    font_color_rgb = _hex_after_terms(instruction, ("글자색", "font color", "text color"))
    fill_color_rgb = _hex_after_terms(instruction, ("배경색", "채우기", "fill"))
    alignment = _alignment_from_instruction(instruction)
    if all(
        value is None
        for value in (
            font_family,
            font_size_pt,
            bold,
            font_color_rgb,
            fill_color_rgb,
            alignment,
        )
    ):
        return None
    return StyleDescriptor(
        style_id=f"style-{sha256(target_path.encode('utf-8')).hexdigest()[:8]}",
        target_path=target_path,
        font_family=font_family,
        font_size_pt=font_size_pt,
        bold=bold,
        font_color_rgb=font_color_rgb,
        fill_color_rgb=fill_color_rgb,
        alignment=alignment,
    )


def _font_family_from_instruction(instruction: str) -> str | None:
    if re.search(r"malgun\s*gothic|맑은\s*고딕", instruction, flags=re.IGNORECASE):
        return "Malgun Gothic"
    return None


def _font_size_from_instruction(instruction: str) -> Decimal | None:
    match = _FONT_SIZE_RE.search(instruction)
    if match is None:
        return None
    return Decimal(match.group("size"))


def _bold_from_instruction(instruction: str) -> bool | None:
    instruction_key = _normalize_key(instruction)
    if "bold" in instruction.casefold() or "굵게" in instruction_key or "진하게" in instruction_key:
        return True
    return None


def _hex_after_terms(instruction: str, terms: tuple[str, ...]) -> str | None:
    for term in terms:
        match = re.search(
            rf"{re.escape(term)}\s*(?P<hex>[0-9A-Fa-f]{{6}})",
            instruction,
            flags=re.IGNORECASE,
        )
        if match is not None:
            return match.group("hex").upper()
    if len(terms) == 1:
        match = _HEX_COLOR_RE.search(instruction)
        if match is not None:
            return match.group("hex").upper()
    return None


def _alignment_from_instruction(instruction: str) -> StyleAlignment | None:
    instruction_key = _normalize_key(instruction)
    instruction_casefold = instruction.casefold()
    if (
        "center" in instruction_casefold
        or "가운데" in instruction_key
        or "중앙" in instruction_key
    ):
        return "center"
    if (
        "right" in instruction_casefold
        or "오른쪽정렬" in instruction_key
        or "우측정렬" in instruction_key
    ):
        return "right"
    if (
        "left" in instruction_casefold
        or "왼쪽정렬" in instruction_key
        or "좌측정렬" in instruction_key
    ):
        return "left"
    return None


def _save_intent_from_instruction(instruction: str) -> AutonomousSaveIntent | None:
    match = _SAVE_PATH_RE.search(instruction)
    if match is None:
        return None
    destination_path = match.group("path")
    return AutonomousSaveIntent(
        destination_path=destination_path,
        destination_display_name=Path(destination_path).name,
        confidence=Decimal("0.75"),
    )


def _session_context_value(
    slot: FormSlot,
    session_context: Mapping[str, object],
) -> object:
    slot_keys = {
        _normalize_key(slot.slot_id),
        _normalize_key(slot.label),
        _normalize_key(slot.source_anchor.format_path),
    }
    for key, value in session_context.items():
        normalized_key = _normalize_key(str(key))
        if normalized_key not in slot_keys:
            continue
        return _scalar_context_value(value)
    return None


def _scalar_context_value(value: object) -> object:
    if value is None or isinstance(value, str | int | Decimal | bool | date | datetime):
        return value
    return str(value)


def _missing_required_slot(slot: FormSlot, instruction: str) -> bool:
    return (
        slot.required
        and slot.candidate_value is None
        and (_instruction_requests_broad_autonomous_fill(instruction) or slot.protected)
    )


def _explicit_week_value(instruction: str) -> str | None:
    match = _WEEK_LABEL_RE.search(instruction)
    if match is None:
        return None
    return f"{int(match.group('week'))}주차"


def _next_week_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = _WEEK_LABEL_RE.search(value)
    if match is None:
        return None
    return f"{int(match.group('week')) + 1}주차"


def _explicit_date_range(instruction: str) -> str | None:
    match = _DATE_RANGE_RE.search(instruction)
    if match is None:
        return None
    return f"{match.group('start')}~{match.group('end')}"


def _next_date_range(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = _DATE_RANGE_RE.search(value)
    if match is None:
        return None
    start = datetime.strptime(match.group("start"), "%Y.%m.%d").date()
    end = datetime.strptime(match.group("end"), "%Y.%m.%d").date()
    return f"{start + timedelta(days=7):%Y.%m.%d}~{end + timedelta(days=7):%Y.%m.%d}"


def _slot_key(slot: FormSlot) -> str:
    return _normalize_key(f"{slot.slot_id} {slot.label} {slot.source_anchor.format_path}")


def _normalize_key(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())


def _is_week_slot(slot_key: str) -> bool:
    return "주차" in slot_key or "week" in slot_key


def _is_activity_period_slot(slot_key: str) -> bool:
    return "활동기간" in slot_key or "활동일시" in slot_key or "period" in slot_key


def _intent_confidence(instruction: str) -> Decimal:
    if _is_autonomous_instruction(instruction):
        return Decimal("0.70")
    return Decimal("0.60")


def _is_autonomous_instruction(instruction: str) -> bool:
    instruction_key = _normalize_key(instruction)
    return "알아서" in instruction_key or "파악" in instruction_key


def _instruction_requests_broad_autonomous_fill(instruction: str) -> bool:
    instruction_key = _normalize_key(instruction)
    return any(
        term in instruction_key
        for term in (
            "알아서",
            "자동작성",
            "자동으로작성",
            "전체작성",
            "전체를작성",
            "모든빈칸",
            "빈칸모두",
            "빈칸전체",
            "비어있는칸모두",
            "비어있는항목모두",
        )
    )


def _plan_confidence(slots: tuple[FormSlot, ...], intent_confidence: Decimal) -> Decimal:
    if not slots:
        return Decimal("0")
    slot_confidence = min(slot.confidence for slot in slots)
    return min(intent_confidence, slot_confidence)
