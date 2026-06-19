# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

RedactionCategory = Literal[
    "auth_header",
    "cookie",
    "service_key",
    "token",
    "pii",
    "private_document",
]
PromptInjectionState = Literal["detected", "not_detected"]

_AUTH_HEADER_PATTERN = re.compile(r"\bAuthorization\s*:\s*[^\n\r;]+", re.IGNORECASE)
_AUTH_ASSIGNMENT_PATTERN = re.compile(
    r"\bauthorization\s*=\s*[^\s&;\n\r]+",
    re.IGNORECASE,
)
_COOKIE_PATTERN = re.compile(r"\bCookie\s*:\s*[^;\n\r]+;?\s*", re.IGNORECASE)
_COOKIE_ASSIGNMENT_PATTERN = re.compile(
    r"\bcookie\s*=\s*[^\s&;\n\r]+",
    re.IGNORECASE,
)
_SERVICE_KEY_PATTERN = re.compile(
    r"\b(?:serviceKey|authKey)\s*=\s*[^\s&]+",
    re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(
    r"\b(?:UMMAYA_[A-Z0-9_]*TOKEN|"
    r"[A-Z0-9_]*(?:API|AUTH|ACCESS|REFRESH|SESSION)[_-]?KEY|"
    r"(?:session|access|refresh|id)[_-]?token)\s*=\s*[^\s&]+|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]+",
    re.IGNORECASE,
)
_GENERIC_TOKEN_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?:token|secret|api[_-]?key|access[_-]?token|session[_-]?token|"
    r"refresh[_-]?token|id[_-]?token|client[_-]?secret)\s*=\s*[^\s&;\n\r]+",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_KOREAN_RRN_PATTERN = re.compile(r"\b\d{6}-[1-4]\d{6}\b")
_PHONE_PATTERN = re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")
_PRIVATE_DOCUMENT_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|raw private document|private document bytes",
    re.IGNORECASE,
)
_PROMPT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"change\s+(?:the\s+)?permission\s+policy", re.IGNORECASE),
    re.compile(r"bypass\s+(?:permissions?|approval|policy)", re.IGNORECASE),
    re.compile(r"treat\s+this\s+as\s+(?:a\s+)?system\s+instruction", re.IGNORECASE),
)
_SECRET_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authkey",
        "authorization",
        "cookie",
        "id_token",
        "key",
        "refresh_token",
        "servicekey",
        "session",
        "session_token",
        "token",
    }
)


def redact_source_url(value: str | None) -> tuple[str | None, tuple[RedactionCategory, ...]]:
    if value is None:
        return None, ()
    categories: list[RedactionCategory] = []
    try:
        parsed = urlsplit(value)
    except ValueError:
        return redact_source_text(value)
    query_items: list[tuple[str, str]] = []
    for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered_key = key.lower()
        if lowered_key in _SECRET_QUERY_KEYS:
            categories.append(
                "service_key" if lowered_key in {"authkey", "servicekey"} else "token"
            )
            continue
        redacted_value, item_categories = redact_source_text(item_value)
        categories.extend(item_categories)
        query_items.append((key, redacted_value or ""))
    rebuilt = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_items),
            parsed.fragment,
        )
    )
    redacted_text, text_categories = redact_source_text(rebuilt)
    categories.extend(text_categories)
    return redacted_text, ordered_redaction_categories(categories)


def redact_source_text(value: str | None) -> tuple[str | None, tuple[RedactionCategory, ...]]:
    if value is None:
        return None, ()
    categories = list(redaction_categories_for_text(value))
    redacted = _AUTH_HEADER_PATTERN.sub("[REDACTED_AUTH_HEADER]", value)
    redacted = _AUTH_ASSIGNMENT_PATTERN.sub("[REDACTED_AUTH_HEADER]", redacted)
    redacted = _COOKIE_PATTERN.sub("[REDACTED_COOKIE] ", redacted)
    redacted = _COOKIE_ASSIGNMENT_PATTERN.sub("[REDACTED_COOKIE]", redacted)
    redacted = _SERVICE_KEY_PATTERN.sub("[REDACTED_SERVICE_KEY]", redacted)
    redacted = _TOKEN_PATTERN.sub("[REDACTED_TOKEN]", redacted)
    redacted = _GENERIC_TOKEN_ASSIGNMENT_PATTERN.sub("[REDACTED_TOKEN]", redacted)
    redacted = _EMAIL_PATTERN.sub("[REDACTED_PII]", redacted)
    redacted = _KOREAN_RRN_PATTERN.sub("[REDACTED_PII]", redacted)
    redacted = _PHONE_PATTERN.sub("[REDACTED_PII]", redacted)
    redacted = _PRIVATE_DOCUMENT_PATTERN.sub("[REDACTED_PRIVATE_DOCUMENT]", redacted)
    return re.sub(r"[ \t]{2,}", " ", redacted).strip(), ordered_redaction_categories(categories)


def detect_prompt_injection(value: str) -> PromptInjectionState:
    return (
        "detected"
        if any(pattern.search(value) for pattern in _PROMPT_INJECTION_PATTERNS)
        else "not_detected"
    )


def redaction_categories_for_text(value: str) -> tuple[RedactionCategory, ...]:
    categories: list[RedactionCategory] = []
    if _AUTH_HEADER_PATTERN.search(value):
        categories.append("auth_header")
    if _AUTH_ASSIGNMENT_PATTERN.search(value):
        categories.append("auth_header")
    if _COOKIE_PATTERN.search(value):
        categories.append("cookie")
    if _COOKIE_ASSIGNMENT_PATTERN.search(value):
        categories.append("cookie")
    if _SERVICE_KEY_PATTERN.search(value):
        categories.append("service_key")
    if _TOKEN_PATTERN.search(value):
        categories.append("token")
    if _GENERIC_TOKEN_ASSIGNMENT_PATTERN.search(value):
        categories.append("token")
    if (
        _EMAIL_PATTERN.search(value)
        or _KOREAN_RRN_PATTERN.search(value)
        or _PHONE_PATTERN.search(value)
    ):
        categories.append("pii")
    if _PRIVATE_DOCUMENT_PATTERN.search(value):
        categories.append("private_document")
    return ordered_redaction_categories(categories)


def ordered_redaction_categories(
    categories: Iterable[RedactionCategory],
) -> tuple[RedactionCategory, ...]:
    order: tuple[RedactionCategory, ...] = (
        "auth_header",
        "cookie",
        "service_key",
        "token",
        "pii",
        "private_document",
    )
    present = set(categories)
    return tuple(category for category in order if category in present)
