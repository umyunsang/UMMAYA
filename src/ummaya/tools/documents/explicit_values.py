# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re

_SAVE_CLAUSE_RE = re.compile(
    r"\s*,?\s*(?:저장|내보내|export|save)\s*(?:은|는|:|=)?.*$",
    re.IGNORECASE,
)
_UPDATE_TAIL_RE = re.compile(
    r"\s*(?:로|으로)\s*(?:(?:알아서|내용에\s*맞게)\s*)?"
    r"(?:갱신|변경|수정|작성|입력|채우|해줘).*$",
    re.IGNORECASE,
)
_NEXT_LABEL_BOUNDARY_RE = r"(?=,\s*[^,.\n]{2,80}?(?:에는|엔|에|은|는|:|=)\s*[\"'“”‘’]?)"
_COMMAND_BOUNDARY_RE = r"(?=\s*(?:만\s*)?(?:넣|입력|작성|채우|수정|변경|갱신))"
_VALUE_END_RE = rf"(?:{_NEXT_LABEL_BOUNDARY_RE}|{_COMMAND_BOUNDARY_RE}|[.!?。\n]|$)"
_LABEL_PART_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_LABEL_PART_SEPARATOR_RE = r"[\s·ㆍ‧\-_]*"
_LABEL_VALUE_SUFFIX_RE = r"(?:값|내용|value)?\s*"


def explicit_keyed_value_for_label(label: str, instruction: str) -> str | None:
    if not _is_meaningful_explicit_label(label):
        return None
    label_pattern = _explicit_label_pattern(label)
    quoted_value = _quoted_keyed_value_for_label(label, instruction)
    if quoted_value is not None:
        return quoted_value
    adjacent_blank_match = re.search(
        rf"{label_pattern}\s*"
        r"(?:옆|다음|우측|오른쪽)?\s*"
        r"(?:빈\s*칸|칸|필드|항목)?\s*"
        r"(?:에는|엔|에)\s*"
        rf"(?P<value>.+?){_VALUE_END_RE}",
        instruction,
        flags=re.IGNORECASE,
    )
    if adjacent_blank_match is not None:
        value = _clean_explicit_keyed_value(adjacent_blank_match.group("value"))
        return value or None
    field_word_match = re.search(
        rf"{label_pattern}\s*(?:은|는|이|가)?\s*(?:필드|칸|항목)?\s*"
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
        rf"{label_pattern}\s*(?:은|는|:|=)\s*(?P<value>[^.!?。\n]+[.!?。]?)",
        instruction,
        flags=re.IGNORECASE,
    )
    if match is not None:
        value = _clean_explicit_keyed_value(match.group("value"))
        return value or None
    return None


def _quoted_keyed_value_for_label(label: str, instruction: str) -> str | None:
    label_pattern = _explicit_label_pattern(label)
    match = re.search(
        rf"{label_pattern}\s*"
        r"(?:옆|다음|우측|오른쪽)?\s*"
        r"(?:빈\s*칸|칸|필드|항목)?\s*"
        rf"{_LABEL_VALUE_SUFFIX_RE}"
        r"(?:에는|엔|에|은|는|:|=)\s*"
        r"(?P<quote>[\"'“”‘’])(?P<value>.*?)(?P=quote)",
        instruction,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    value = _clean_quoted_keyed_value(match.group("value"))
    return value or None


def _explicit_label_pattern(label: str) -> str:
    parts = _LABEL_PART_RE.findall(label)
    if not parts:
        return re.escape(label)
    return _LABEL_PART_SEPARATOR_RE.join(re.escape(part) for part in parts)


def _is_meaningful_explicit_label(label: str) -> bool:
    label_key = _normalize_key(label)
    if len(label_key) < 2:
        return False
    return any("a" <= char <= "z" or "가" <= char <= "힣" for char in label_key)


def _clean_explicit_keyed_value(value: str) -> str:
    cleaned = _SAVE_CLAUSE_RE.sub("", value).strip()
    cleaned = _UPDATE_TAIL_RE.sub("", cleaned).strip()
    cleaned = re.sub(r"\s*(?:을|를)$", "", cleaned).strip()
    return cleaned.strip(" ,;:)]}）\"'“”‘’")


def _clean_quoted_keyed_value(value: str) -> str:
    return value.strip().strip(" ,;:)]}）\"'“”‘’")


def _normalize_key(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())
