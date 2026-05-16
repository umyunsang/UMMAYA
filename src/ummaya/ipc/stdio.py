# SPDX-License-Identifier: Apache-2.0
"""Asyncio-based JSONL stdio reader/writer loop for the TUI ↔ backend IPC bridge.

Protocol
--------
* Every frame is a single line of JSON terminated by a newline (``\\n``).
* The backend reads frames from ``stdin`` and writes frames to ``stdout``.
* ``stderr`` is reserved for diagnostic / log output; TUI consumes it for crash notices.
* Graceful shutdown: ``SIGTERM`` / ``SIGINT`` → drain in-flight work → write
  ``session_event {event="exit"}`` → flush stdout → exit 0.
* ``stdout`` is flushed after every written frame (FR-005 ordering invariant).

Usage
-----
This module is invoked by the CLI when ``--ipc stdio`` is passed::

    uv run ummaya --ipc stdio

The ``run()`` coroutine is the public entry point; it blocks until the session
exits.  The ``write_frame()`` helper is available for code that needs to push
frames from outside this module.
"""

from __future__ import annotations

import asyncio
import contextlib
import json as _stdlib_json
import logging
import os
import re
import signal
import sys
import time
import uuid
from collections.abc import Callable, Collection
from datetime import UTC, datetime, timedelta
from types import FrameType
from typing import TYPE_CHECKING, Any, Final, Literal, cast

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import TypeAdapter, ValidationError

from ummaya.ipc.envelope import attach_envelope_span_attributes
from ummaya.ipc.frame_schema import (
    ErrorFrame,
    IPCFrame,
    SessionEventFrame,
)

if TYPE_CHECKING:
    from ummaya.session.manager import SessionManager
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Module-level tracer — follows the same pattern as ummaya.tools.executor and
# ummaya.engine.query (trace.get_tracer(__name__) at module load time).
_tracer = trace.get_tracer(__name__)

# Frames whose handlers can legitimately await follow-up frames from the same
# stdin stream. Running them inline deadlocks the reader: chat_request waits for
# permission_response while the reader is still awaiting chat_request.
_BACKGROUND_FRAME_KINDS: frozenset[str] = frozenset({"chat_request", "user_input", "plugin_op"})
_SCOPE_ENTRY_RE = re.compile(r"^(find|send|check):[a-z0-9_]+\.[a-z0-9_-]+$")
_TOOL_ID_SCOPE_RE = re.compile(r"^(?P<verb>find|send|check):(?P<tool_id>[a-z][a-z0-9_]*[a-z0-9])$")
_LEGACY_SCOPE_VERB_ALIASES: Final[dict[str, str]] = {
    "lookup": "find",
    "submit": "send",
    "verify": "check",
}
_CANONICAL_SCOPE_ALIASES: Final[dict[str, str]] = {
    "find:mock_lookup_module_hometax_simplified": "find:hometax.simplified",
    "find:mock.lookup_module_hometax_simplified": "find:hometax.simplified",
    "send:mock_submit_module_gov24_minwon": "send:gov24.minwon",
    "send:mock.submit_module_gov24_minwon": "send:gov24.minwon",
    "send:mock_submit_module_hometax_taxreturn": "send:hometax.tax-return",
    "send:mock.submit_module_hometax_taxreturn": "send:hometax.tax-return",
    "send:mock_welfare_application_submit_v1": "send:mydata.welfare_application",
    "send:mock.welfare_application_submit_v1": "send:mydata.welfare_application",
    "send:mohw.welfare_application": "send:mydata.welfare_application",
    "send:pub.mohw.welfare_application": "send:mydata.welfare_application",
    "send:mock_traffic_fine_pay_v1": "send:traffic.fine-pay",
    "send:mock.traffic_fine_pay_v1": "send:traffic.fine-pay",
    "send:traffic_fine.payment": "send:traffic.fine-pay",
    "send:traffic_fine.pay": "send:traffic.fine-pay",
    "send:traffic.fine.payment": "send:traffic.fine-pay",
    "send:traffic.fine.pay": "send:traffic.fine-pay",
    "send:traffic.fine_pay": "send:traffic.fine-pay",
}
_NON_DELEGATING_VERIFY_SCOPE_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "find:gov24.certificate",
        "find:gov24.resident_certificate",
        "find:gov24.simplified",
        "find:gov24_certificate.lookup",
        "find:mock_lookup_module_gov24_certificate",
        "find:mock.lookup_module_gov24_certificate",
        "find:mydata.welfare",
        "find:mydata.welfare_eligibility_search",
        "find:public_mydata.welfare_eligibility_search",
        "find:mohw.welfare_eligibility",
        "find:mohw_welfare_eligibility_search",
        "find:mohw.welfare_eligibility_search",
        "find:pub.mohw.welfare_eligibility",
        "find:pub.mohw.welfare_eligibility_search",
        "find:traffic_fine.check",
        "find:traffic.fine",
        "find:traffic.fine_check",
        "find:traffic.fine.check",
        "find:traffic_fine.inquiry",
        "find:traffic.fine_inquiry",
        "find:traffic.fine.inquiry",
        "find:traffic_fine.search",
        "find:traffic.fine_search",
        "find:traffic.fine.search",
    }
)
_PRUNABLE_OVERBROAD_VERIFY_SCOPES: Final[frozenset[str]] = frozenset(
    {
        "find:hometax.simplified",
        "send:hometax.tax-return",
    }
)
_QUERY_BOUND_NON_DELEGATING_SCOPE_PREFIXES: Final[dict[str, tuple[str, ...]]] = {
    "send:gov24.minwon": ("find:gov24.",),
}
_PRIMITIVE_TOOL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MOCK_DISCLOSURE_KO: Final = "이 결과는 실제 행정 영향이 없는 시연(모의) 결과입니다."
_MOCK_SUBMIT_RECEIPT_DISCLOSURE_KO: Final = (
    f"{_MOCK_DISCLOSURE_KO} 접수번호는 시연용이며 실제 기관 포털에서 조회되지 않습니다."
)
_GOV24_MINWON_RECEIPT_RE: Final = re.compile(r"gov24-\d{4}-\d{2}-\d{2}-MW-[A-Z0-9]+")
_HOMETAX_TAXRETURN_RECEIPT_RE: Final = re.compile(r"hometax-\d{4}-\d{2}-\d{2}-RX-[A-Z0-9]+")
_UMMAYA_SUBMIT_TX_RE: Final = re.compile(r"urn:ummaya:(?:send|submit):[a-f0-9]+")
_GOV24_MINWON_SESSION_RE: Final = re.compile(r"GOV24-[A-Z0-9-]+")
_INTERNAL_TOOL_ID_RE: Final = re.compile(r"\b[a-z]+_[a-z0-9_]*\b")
_DELEGATION_CONTEXT_SPREAD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "citizen_did",
        "delegation_token",
        "expires_at",
        "issued_at",
        "issuer_did",
        "mode",
        "_mode",
        "purpose_en",
        "purpose_ko",
        "scope",
        "token",
        "vp_jwt",
    }
)
_SENSITIVE_LOOKUP_AUTH_REQUIREMENTS: Final[dict[str, dict[str, str]]] = {
    "mock_lookup_module_hometax_simplified": {
        "verify_tool_id": "mock_verify_module_modid",
        "scope": "find:hometax.simplified",
        "purpose_ko": "연말정산 간소화 자료 조회",
        "purpose_en": "Hometax simplified year-end tax lookup",
    },
}
_FINAL_ANSWER_OBSERVATION_JSON_LIMIT: Final = 12_000
_FINAL_ANSWER_OBSERVATION_LIST_LIMIT: Final = 12
_FINAL_ANSWER_OBSERVATION_STR_LIMIT: Final = 2_000
_FINAL_ANSWER_OBSERVATION_OMIT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "outbound_traces",
    }
)
_PRIMITIVE_ERROR_REASONS: Final[frozenset[str]] = frozenset(
    {
        "adapter_invocation_failed",
        "adapter_not_found",
        "auth_required",
        "coercion_violation",
        "family_mismatch",
        "invalid_params",
        "scope_violation",
        "submit_already_succeeded",
        "verify_tool_choice_mismatch",
    }
)
_VERIFY_QUERY_REQUIREMENTS: Final[tuple[tuple[tuple[str, ...], dict[str, str]], ...]] = (
    (
        ("간편인증", "pass 인증", "kakao 인증", "naver 인증"),
        {
            "verify_tool_id": "mock_verify_ganpyeon_injeung",
            "allowed_tool_ids": "mock_verify_ganpyeon_injeung,mock_verify_module_simple_auth",
            "scope": "check:ganpyeon.identity",
            "allowed_scopes": "check:ganpyeon.identity",
            "purpose_ko": "간편인증 로그인",
            "purpose_en": "Simple authentication login",
        },
    ),
    (
        ("모바일신분증", "모바일id", "모바일 id", "mobile id"),
        {
            "verify_tool_id": "mock_verify_mobile_id",
            "allowed_tool_ids": "mock_verify_mobile_id",
            "scope": "check:mobile_id.identity",
            "allowed_scopes": "check:mobile_id.identity",
            "purpose_ko": "모바일 신분증 본인확인",
            "purpose_en": "Mobile ID identity verification",
        },
    ),
    (
        ("마이데이터", "mydata"),
        {
            "verify_tool_id": "mock_verify_mydata",
            "allowed_tool_ids": "mock_verify_mydata",
            "scope": "check:mydata.consent",
            "allowed_scopes": "check:mydata.consent,send:public_mydata.action",
            "purpose_ko": "마이데이터 인증",
            "purpose_en": "MyData authentication",
        },
    ),
    (
        ("홈택스", "연말정산", "간소화"),
        {
            "verify_tool_id": "mock_verify_module_modid",
            "allowed_tool_ids": "mock_verify_module_modid",
            "scope": "find:hometax.simplified",
            "allowed_scopes": "find:hometax.simplified",
            "purpose_ko": "연말정산 간소화 자료 조회",
            "purpose_en": "Hometax simplified year-end tax lookup",
        },
    ),
    (
        ("정부24", "주민등록등본", "등본", "민원"),
        {
            "verify_tool_id": "mock_verify_module_simple_auth",
            "allowed_tool_ids": "mock_verify_module_simple_auth",
            "scope": "send:gov24.minwon",
            "allowed_scopes": "send:gov24.minwon",
            "purpose_ko": "주민등록등본 발급 민원 신청",
            "purpose_en": "Gov24 resident registration certificate civil petition",
        },
    ),
    (
        ("복지 급여 신청", "한부모가족", "아동양육비"),
        {
            "verify_tool_id": "mock_verify_mydata",
            "allowed_tool_ids": "mock_verify_mydata",
            "scope": "send:mydata.welfare_application",
            "allowed_scopes": "send:mydata.welfare_application",
            "purpose_ko": "한부모가족 아동양육비 지원 신청",
            "purpose_en": "Single-parent family child support application",
        },
    ),
    (
        ("과태료", "교통범칙금", "범칙금"),
        {
            "verify_tool_id": "mock_verify_ganpyeon_injeung",
            "allowed_tool_ids": "mock_verify_ganpyeon_injeung",
            "scope": "send:traffic.fine-pay",
            "allowed_scopes": "send:traffic.fine-pay",
            "purpose_ko": "교통 과태료 납부",
            "purpose_en": "Traffic fine payment",
        },
    ),
)
_LOCATION_RESOLUTION_HINTS_KO: Final[frozenset[str]] = frozenset(
    {
        "근처",
        "주변",
        "주소",
        "위치",
        "역",
        "동네",
    }
)
_LOCATION_INDEPENDENT_WORKFLOW_HINTS_KO: Final[frozenset[str]] = frozenset(
    {
        "홈택스",
        "연말정산",
        "종합소득세",
        "정부24",
        "주민등록등본",
        "등본",
        "간편인증",
        "모바일신분증",
        "마이데이터",
        "공공마이데이터",
        "과태료",
        "교통범칙금",
        "범칙금",
        "한부모가족",
        "아동양육비",
    }
)
_NON_LOCATION_STATION_SUFFIX_WORDS_KO: Final[frozenset[str]] = frozenset(
    {
        "내역",
        "영역",
        "지역",
        "권역",
        "용역",
        "무역",
        "전역",
        "현역",
        "병역",
        "역",
    }
)
_DEFAULT_CHAT_MAX_TOKENS: Final[int] = 4096

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_frame_adapter: TypeAdapter[Any] = TypeAdapter(IPCFrame)


def _serialize_primitive_result(raw: object) -> dict[str, Any]:
    """Coerce a primitive return value to a JSON-serialisable dict.

    Pydantic models go through ``model_dump(mode="json")``; everything else
    falls back to ``{"raw": str(value)}`` so the envelope round-trip stays
    safe. Helper extracted from inline expressions to keep the dispatcher
    body under the line-length limit.
    """
    dump = getattr(raw, "model_dump", None)
    if callable(dump):
        result = dump(mode="json")
        if isinstance(result, dict):
            return result
        return {"raw": result}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {"items": raw}
    return {"raw": str(raw)}


def _invalid_gated_primitive_tool_id_result(
    primitive: str,
    args_obj: dict[str, object],
) -> dict[str, object] | None:
    """Return a structured non-throwing result for malformed gated calls."""
    raw_tool_id = args_obj.get("tool_id")
    tool_id = raw_tool_id if isinstance(raw_tool_id, str) else ""
    if _PRIMITIVE_TOOL_ID_RE.fullmatch(tool_id):
        return None

    return {
        "tool_id": "invalid_tool_id",
        "invalid_tool_id": True,
        "result": {
            "reason": "adapter_not_found",
            "tool_id": "invalid_tool_id",
            "message": (
                f"{primitive} requires a non-empty registered adapter tool_id; "
                f"call {primitive}(tool_id=<adapter>, params={{...}})."
            ),
        },
    }


def _contains_mock_marker(value: object) -> bool:
    """Return True when a tool result carries mock-mode transparency evidence."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"_mode", "transparency_mode"} and item == "mock":
                return True
            if key == "mock" and item is True:
                return True
            if _contains_mock_marker(item):
                return True
    elif isinstance(value, list):
        return any(_contains_mock_marker(item) for item in value)
    return False


def _ensure_mock_disclosure(text: str, *, mock_primitives: set[str] | None = None) -> str:
    """Append the mandatory citizen-facing mock disclosure when absent."""
    text = _normalize_gov24_mock_minwon_final_answer(text)
    text = _normalize_hometax_mock_taxreturn_final_answer(text)
    text = _remove_internal_tool_id_lines(text)
    if mock_primitives == {"check"}:
        text = _normalize_mock_check_final_answer(text)
    text = _remove_mock_conflicting_real_world_claims(text)
    if "실제 행정 영향" in text and ("시연" in text or "모의" in text):
        return text
    suffix = (
        _MOCK_SUBMIT_RECEIPT_DISCLOSURE_KO
        if (
            "접수번호" in text
            or _GOV24_MINWON_RECEIPT_RE.search(text)
            or _HOMETAX_TAXRETURN_RECEIPT_RE.search(text)
        )
        else _MOCK_DISCLOSURE_KO
    )
    if not text.strip():
        return suffix
    return f"{text.rstrip()}\n\n{suffix}"


def _remove_unneeded_mock_disclosure(text: str) -> str:
    """Strip mock disclosure text from live-tool final answers."""
    text = _remove_internal_tool_id_lines(text)
    if "실제 행정 영향" not in text and "시연(모의)" not in text:
        return text
    fragments = (
        _MOCK_SUBMIT_RECEIPT_DISCLOSURE_KO,
        _MOCK_DISCLOSURE_KO,
        "이 결과는 실제 행정 영향이 없는 시연(모의) 결과입니다.",
        "실제 행정 영향이 없는 시연(모의) 결과입니다.",
        "접수번호는 시연용이며 실제 기관 포털에서 조회되지 않습니다.",
    )
    cleaned = text
    for fragment in fragments:
        cleaned = cleaned.replace(fragment, "")
    lines = [
        line.rstrip()
        for line in cleaned.splitlines()
        if not ("실제 행정 영향" in line and ("시연" in line or "모의" in line))
    ]
    return "\n".join(lines).strip()


def _remove_unneeded_live_meta_disclosure(text: str) -> str:
    """Strip live-answer meta disclaimers that discuss the demo/runtime itself."""
    kept: list[str] = []
    for line in text.splitlines():
        normalized = " ".join(line.strip().split())
        is_runtime_meta = (
            "시각적 가상 시스템" in normalized
            or "가상 시스템" in normalized
            or "시연(모의)" in normalized
            or "모의 결과" in normalized
            or "시연 결과" in normalized
            or "virtual system" in normalized.lower()
            or "demo result" in normalized.lower()
            or ("이 결과는 실제" in normalized and "기반" in normalized and "시스템" in normalized)
            or ("실제 날씨 상황" in normalized and "다를 수" in normalized)
            or (
                "기상청 공식 채널" in normalized
                and "최신 정보" in normalized
                and "확인" in normalized
            )
        )
        if is_runtime_meta:
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


def _remove_internal_tool_id_lines(text: str) -> str:
    """Drop final prose lines that expose adapter ids as implementation detail."""
    kept: list[str] = []
    for line in text.splitlines():
        compact = line.lower()
        exposes_tool_id = _INTERNAL_TOOL_ID_RE.search(line) is not None and (
            "도구" in compact or "어댑터" in compact or "tool" in compact or "adapter" in compact
        )
        if exposes_tool_id:
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


def _normalize_mock_check_final_answer(text: str) -> str:
    """Keep mock check-only final answers as verification results, not lookups."""
    if (
        "접수번호" in text
        or _GOV24_MINWON_RECEIPT_RE.search(text)
        or _HOMETAX_TAXRETURN_RECEIPT_RE.search(text)
    ):
        return text
    if not any(marker in text for marker in ("본인확인", "인증", "검증")):
        return text
    if not any(marker in text for marker in ("완료", "성공", "verified", "인증 완료")):
        return text
    subject = "모바일 신분증 본인확인" if "모바일" in text else "본인확인"
    return f"{subject}이 완료되었습니다."


_KMA_FORECAST_BASE_HOURS: Final[tuple[int, ...]] = (2, 5, 8, 11, 14, 17, 20, 23)


def _kma_day_note(reference_kst: datetime, slot_kst: datetime) -> str:
    if slot_kst.date() == reference_kst.date():
        return "오늘"
    if slot_kst.date() == (reference_kst - timedelta(days=1)).date():
        return "어제"
    return slot_kst.strftime("%Y-%m-%d")


def _kma_forecast_base_slot_hint(now_kst: datetime) -> tuple[str, str, str]:
    """Return the latest KMA short-term forecast base_date/time before now."""
    previous_hour = max(
        (hour for hour in _KMA_FORECAST_BASE_HOURS if hour <= now_kst.hour),
        default=_KMA_FORECAST_BASE_HOURS[-1],
    )
    if now_kst.hour < _KMA_FORECAST_BASE_HOURS[0]:
        slot = (now_kst - timedelta(days=1)).replace(
            hour=_KMA_FORECAST_BASE_HOURS[-1],
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        slot = now_kst.replace(hour=previous_hour, minute=0, second=0, microsecond=0)
    return slot.strftime("%Y%m%d"), slot.strftime("%H00"), _kma_day_note(now_kst, slot)


def _kma_observation_base_slot_hint(now_kst: datetime) -> tuple[str, str, str]:
    """Return the stable KMA ultra-short current-observation base_date/time."""
    candidate_hour = now_kst.hour if now_kst.minute >= 40 else now_kst.hour - 1
    if candidate_hour < 0:
        slot = (now_kst - timedelta(days=1)).replace(
            hour=23,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        slot = now_kst.replace(hour=candidate_hour, minute=0, second=0, microsecond=0)
    return slot.strftime("%Y%m%d"), slot.strftime("%H00"), _kma_day_note(now_kst, slot)


def _final_answer_looks_like_pending_tool_plan(text: str) -> bool:
    """Return true when final prose says it will call tools after tools already ran."""
    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    pending_markers = (
        "호출하겠습니다",
        "조회하겠습니다",
        "찾아보겠습니다",
        "검색하겠습니다",
        "진행하겠습니다",
        "확인하겠습니다",
        "will call",
        "i'll call",
        "i will call",
        "will look up",
    )
    return any(marker in normalized.lower() for marker in pending_markers)


def _final_answer_looks_like_recursive_tool_message(text: str) -> bool:
    """Return true when final prose recursively quotes tool-result wrappers."""
    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    return normalized.count("도구가 반환한 메시지") >= 2


def _final_answer_looks_like_repeated_sections(text: str) -> bool:
    """Return true when final prose repeats the same answer sections."""
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.fullmatch(r"(?:#{1,6}\s*)?\*\*(?P<title>[^*\n]{2,90})\*\*", stripped)
        if match is None:
            continue
        title = re.sub(r"\s+", "", match.group("title")).lower()
        headings.append(title)

    seen_headings: set[str] = set()
    repeated_heading_count = 0
    for title in headings:
        if title in seen_headings:
            repeated_heading_count += 1
        else:
            seen_headings.add(title)
    if repeated_heading_count >= 2:
        return True

    paragraphs = [
        re.sub(r"\s+", " ", paragraph).strip().lower() for paragraph in re.split(r"\n{2,}", text)
    ]
    seen_paragraphs: set[str] = set()
    for paragraph in paragraphs:
        if len(paragraph) < 60:
            continue
        if paragraph in seen_paragraphs:
            return True
        seen_paragraphs.add(paragraph)
    return False


def _final_answer_looks_like_unclosed_markdown(text: str) -> bool:
    """Return true when final prose appears to end with an open Markdown span."""
    stripped = text.strip()
    if not stripped:
        return False
    return stripped.endswith("**") and stripped.count("**") % 2 == 1


def _final_answer_looks_like_incomplete_sentence(text: str) -> bool:
    """Return true when final prose ends with a dangling connective."""
    stripped = text.strip()
    if not stripped:
        return False
    normalized = re.sub(r"\s+", " ", stripped)
    dangling_suffixes = (
        ",",
        ":",
        "에 따르면",
        "에 따르면,",
        "기준으로",
        "기준으로,",
        "자료에 따르면",
        "자료에 따르면,",
    )
    return any(normalized.endswith(suffix) for suffix in dangling_suffixes)


def _final_answer_looks_like_tool_call_narration(text: str) -> bool:
    """Return true when final prose narrates internal tool calls to the citizen."""
    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    head = normalized[:700]
    if "도구" not in head:
        return False
    return any(
        marker in head
        for marker in (
            "도구를 호출",
            "도구를 사용",
            "검색 도구",
            "조회 도구",
            "도구로 조회",
        )
    )


def _final_answer_looks_like_generic_retry_after_success(text: str) -> bool:
    """Return true when final prose ignores successful data and asks to retry."""
    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    lowered = normalized.lower()
    retry_markers = (
        "다른 검색어로 재시도",
        "다른 검색어 / 다른 지역",
        "다른 지역으로 재시도",
        "재시도하시겠습니까",
        "다시 검색해",
        "try another search",
        "try a different search",
        "would you like me to retry",
    )
    if any(marker in lowered for marker in retry_markers):
        return True

    handoff_markers = (
        "정확한 정보는",
        "공식 홈페이지에서 확인",
        "공식 사이트에서 확인",
        "기관에 문의",
    )
    has_handoff = any(marker in normalized for marker in handoff_markers)
    if not has_handoff:
        return False
    # A source citation may be useful as a footer. It is only suspect when the
    # answer has no concrete returned values at all.
    return not bool(re.search(r"\d", normalized))


def _conversation_has_successful_any_primitive_result(llm_messages: list[Any]) -> bool:
    """Return True when the loop already has a successful primitive result."""
    return (
        _conversation_has_successful_primitive_any_tool(llm_messages, primitive="find")
        or _conversation_has_successful_primitive_any_tool(llm_messages, primitive="locate")
        or _conversation_has_successful_primitive_any_tool(llm_messages, primitive="check")
        or _conversation_has_successful_primitive_any_tool(llm_messages, primitive="send")
    )


def _normalize_gov24_mock_minwon_final_answer(text: str) -> str:
    """Replace Gov24 mock-submit prose with a receipt-only citizen summary."""
    if "gov24-" not in text or "주민등록등본" not in text:
        return text
    receipt = _first_match(_GOV24_MINWON_RECEIPT_RE, text)
    transaction_id = _first_match(_UMMAYA_SUBMIT_TX_RE, text)
    session_id = _first_match(_GOV24_MINWON_SESSION_RE, text)

    lines = ["정부24 주민등록등본 발급 민원 신청이 시연 환경에서 접수되었습니다."]
    if receipt is not None:
        lines.append(f"접수번호: {receipt} (시연용)")
    if transaction_id is not None:
        lines.append(f"거래 ID: {transaction_id}")
    if "홍길동" in text:
        lines.append("신청자: 홍길동")
    lines.append("문서 종류: 주민등록등본")
    if "온라인" in text:
        lines.append("수령 방법: 온라인 발급")
    if session_id is not None:
        lines.append(f"세션 ID: {session_id}")
    lines.append(_MOCK_SUBMIT_RECEIPT_DISCLOSURE_KO)
    return "\n".join(lines)


def _normalize_hometax_mock_taxreturn_final_answer(text: str) -> str:
    """Replace Hometax mock-submit prose with a receipt-only citizen summary."""
    if "hometax-" not in text or "종합소득세" not in text:
        return text
    receipt = _first_match(_HOMETAX_TAXRETURN_RECEIPT_RE, text)
    transaction_id = _first_match(_UMMAYA_SUBMIT_TX_RE, text)

    lines = ["홈택스 종합소득세 신고가 시연 환경에서 접수되었습니다."]
    if receipt is not None:
        lines.append(f"접수번호: {receipt} (시연용)")
    if transaction_id is not None:
        lines.append(f"거래 ID: {transaction_id}")
    if "42,000,000" in text or "42000000" in text:
        lines.append("총 신고 소득: 42,000,000원")
    lines.append("신고 상태: 신고완료")
    lines.append(_MOCK_SUBMIT_RECEIPT_DISCLOSURE_KO)
    return "\n".join(lines)


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(0)


def _remove_mock_conflicting_real_world_claims(text: str) -> str:
    """Strip final-answer lines that contradict the mandatory mock disclosure."""
    kept: list[str] = []
    for line in text.splitlines():
        compact = "".join(line.split())
        if (
            (
                ("정부24포털" in compact or "정부24홈페이지" in compact or "모바일앱" in compact)
                and ("조회" in compact or "발급" in compact)
            )
            or (
                "정부24홈페이지" in compact
                and (
                    "앱" in compact
                    or "진행" in compact
                    or "로그인" in compact
                    or "조회" in compact
                    or "발급" in compact
                )
            )
            or "해당접수번호로조회" in compact
            or ("접수번호" in compact and "조회" in compact and "조회되지않습니다" not in compact)
            or ("세션유효기간" in compact and "24시간" in compact)
            or "인증토큰발급일로부터24시간" in compact
            or "다음단계" in compact
            or "처리내역" in compact
            or "참고사항" in compact
            or "중요안내사항" in compact
            or "안내사항" in compact
            or "온라인발급안내" in compact
            or "온라인발급이완료" in compact
            or ("다음방법" in compact and "확인" in compact)
            or "확인하실수있습니다" in compact
            or "정부24시스템" in compact
            or "정식접수" in compact
            or "인증절차완료" in compact
            or "위임토큰발급" in compact
            or "민원신청완료" in compact
            or "신청ID" in compact
            or ("접수번호" in compact and "보관" in compact)
            or "조회시필요" in compact
            or "발급완료시" in compact
            or "등록된연락처" in compact
            or "알림이발송" in compact
            or "발급기한" in compact
            or ("일반적으로" in compact and ("즉시발급" in compact or "1~2일" in compact))
            or "발급된주민등록등본" in compact
            or "문서다운로드" in compact
            or "다운로드" in compact
            or "발급소요시간" in compact
            or "10-30분" in compact
            or "본인인증" in compact
            or ("해당접수번호" in compact and "온라인발급" in compact)
            or ("로그인후" in compact and ("민원신청" in compact or "발급" in compact))
            or "민원신청/발급" in compact
            or "발급신청내역조회" in compact
            or "접수후24시간" in compact
            or "취소신청" in compact
            or ("수정" in compact and "변경" in compact and "필요" in compact)
            or "접수번호는추후문의" in compact
            or ("추가문의사항" in compact and "민원접수번호" in compact)
            or ("인터넷연결" in compact and ("스마트폰" in compact or "컴퓨터" in compact))
            or "정부24고객센터" in compact
            or "고객센터(110)" in compact
            or "정부24콜센터" in compact
            or "콜센터(1588-2121)" in compact
            or "1588-2121" in compact
        ):
            continue
        kept.append(line)
    return "\n".join(kept)


# Module-level stdout lock — prevents interleaved JSON if multiple async tasks
# write simultaneously (guards the flush-after-every-frame invariant).
_stdout_lock: asyncio.Lock | None = None


# ---------------------------------------------------------------------------
# Spec spec-multi-turn-contamination — diagnostic instrumentation (DIAGNOSTIC
# ONLY, gated by UMMAYA_CHAT_REQUEST_DUMP=1; off by default — production
# behavior is unchanged when the env var is unset).
#
# Per-session turn counter; rebuilt at process boot, in-memory only.
# Increments at the entry of `_handle_chat_request` for every ChatRequestFrame
# whose session_id matches. Lets the diagnostic cross-correlate three layers
# (chat_messages_built / chat_request_dump / latest_user_utt / reasoning_preview)
# by `(session_id, turn_index)`.
# ---------------------------------------------------------------------------

_session_turn_counter: dict[str, int] = {}


def _diag_chat_request_enabled() -> bool:
    """Return True when UMMAYA_CHAT_REQUEST_DUMP env var is set to '1'.

    Helper exists so the env-var lookup is centralised and the call sites
    stay one-liners that are easy to grep / remove later.
    """
    return os.getenv("UMMAYA_CHAT_REQUEST_DUMP") == "1"


def _get_stdout_lock() -> asyncio.Lock:
    global _stdout_lock
    if _stdout_lock is None:
        _stdout_lock = asyncio.Lock()
    return _stdout_lock


# ---------------------------------------------------------------------------
# Frame I/O primitives
# ---------------------------------------------------------------------------


async def write_frame(
    frame: IPCFrame,
    *,
    _assembly_start_ns: int | None = None,
    tx_cache_state: Literal["miss", "hit", "stored"] | None = None,
) -> None:
    """Serialise *frame* to a single JSON line and write it to stdout.

    Flushes stdout immediately after every frame to preserve the FIFO ordering
    invariant required by the TUI (FR-005).

    Thread-safety: serialised by ``_stdout_lock`` so concurrent coroutines
    cannot interleave partial JSON.

    OTEL: emits a ``ummaya.ipc.frame`` child span (FR-053) with direction
    ``"outbound"``.  ``_assembly_start_ns`` is the ``time.monotonic_ns()``
    captured by the caller before building the frame payload; when absent,
    the span clock starts at the write call itself.  ``tx_cache_state`` is
    forwarded from the :class:`~ummaya.ipc.transaction_lru.TransactionLRU`
    path for irreversible-tool frames (Spec 032 T048 / FR-053).
    """
    t0_ns = _assembly_start_ns if _assembly_start_ns is not None else time.monotonic_ns()
    payload = frame.model_dump_json() + "\n"
    encoded = payload.encode("utf-8")
    lock = _get_stdout_lock()
    with _tracer.start_as_current_span("ummaya.ipc.frame") as span:
        try:
            async with lock:
                sys.stdout.buffer.write(encoded)
                sys.stdout.buffer.flush()
            latency_ms = (time.monotonic_ns() - t0_ns) / 1_000_000
            span.set_attribute("ummaya.session.id", frame.session_id)
            span.set_attribute("ummaya.frame.kind", frame.kind)
            span.set_attribute("ummaya.frame.direction", "outbound")
            span.set_attribute("ummaya.ipc.latency_ms", latency_ms)
            attach_envelope_span_attributes(frame, tx_cache_state=tx_cache_state)
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            raise


def _write_frame_sync(frame: IPCFrame) -> None:
    """Synchronous variant used in signal handlers (no event loop available)."""
    payload = frame.model_dump_json() + "\n"
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.flush()


# ---------------------------------------------------------------------------
# Reader loop
# ---------------------------------------------------------------------------


async def _dispatch_inbound_frame(
    frame: IPCFrame,
    on_frame: Callable[[IPCFrame], Any],
) -> None:
    """Dispatch one validated inbound frame with OTEL error accounting."""
    logger.debug("IPC frame received: kind=%s session=%s", frame.kind, frame.session_id)
    dispatch_start_ns = time.monotonic_ns()
    with _tracer.start_as_current_span("ummaya.ipc.frame") as span:
        try:
            result = on_frame(frame)
            if asyncio.iscoroutine(result):
                await result
            latency_ms = (time.monotonic_ns() - dispatch_start_ns) / 1_000_000
            span.set_attribute("ummaya.session.id", frame.session_id)
            span.set_attribute("ummaya.frame.kind", frame.kind)
            span.set_attribute("ummaya.frame.direction", "inbound")
            span.set_attribute("ummaya.ipc.latency_ms", latency_ms)
            attach_envelope_span_attributes(frame)
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            logger.exception("on_frame handler raised: %s", exc)


async def _write_decode_error(raw: str, session_id: str) -> None:
    """Surface malformed TUI input as an IPC error frame."""
    err_frame = ErrorFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="backend",
        ts=_utcnow(),
        kind="error",
        code="ipc_decode_error",
        message="Failed to decode IPC frame from TUI",
        details={"raw_preview": raw[:200]},
    )
    await write_frame(err_frame)


def _track_background_dispatch(
    frame: IPCFrame,
    on_frame: Callable[[IPCFrame], Any],
    background_tasks: set[asyncio.Task[None]],
) -> None:
    """Start and track a non-blocking frame dispatch task."""
    task = asyncio.create_task(
        _dispatch_inbound_frame(frame, on_frame),
        name=f"ipc-frame-{frame.kind}-{frame.correlation_id[:8]}",
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


async def _drain_background_tasks(
    background_tasks: set[asyncio.Task[None]],
    *,
    cancel: bool,
) -> None:
    """Drain or cancel in-flight background frame handlers."""
    if not background_tasks:
        return
    tasks = tuple(background_tasks)
    if cancel:
        for task in tasks:
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _build_verify_session_context(
    args_obj: dict[str, object],
    *,
    session_id: str,
) -> dict[str, object]:
    """Translate LLM citizen-shape check args into adapter session context.

    The OpenAI tool schema teaches ``check(tool_id, params={scope_list, ...})``.
    The primitive implementation consumes ``verify(family_hint, session_context)``.
    Keep this translation at the backend boundary so direct IPC dispatch follows
    the same contract as the Pydantic LLM-visible schema.
    """
    session_context: dict[str, object] = {}
    raw_context = args_obj.get("session_context")
    if isinstance(raw_context, dict):
        session_context.update({str(k): v for k, v in raw_context.items()})
    raw_params = args_obj.get("params")
    if isinstance(raw_params, dict):
        raw_nested_context = raw_params.get("session_context")
        if isinstance(raw_nested_context, dict):
            session_context.update({str(k): v for k, v in raw_nested_context.items()})
        session_context.update({str(k): v for k, v in raw_params.items() if k != "session_context"})
    raw_scope_list = session_context.get("scope_list")
    if isinstance(raw_scope_list, list):
        session_context["scope_list"] = _normalize_verify_scope_list(raw_scope_list)
    session_context.setdefault("session_id", session_id)
    return session_context


def _normalize_scope_entry(scope: str) -> str:
    """Normalize model-emitted ``verb:tool_id`` shorthand to scope grammar."""
    if ":" in scope:
        verb, rest = scope.split(":", 1)
        canonical_verb = _LEGACY_SCOPE_VERB_ALIASES.get(verb)
        if canonical_verb is not None:
            normalized_verb_scope = f"{canonical_verb}:{rest}"
            logger.debug(
                "check: normalized legacy scope verb %r -> %r",
                scope,
                normalized_verb_scope,
            )
            scope = normalized_verb_scope
    alias = _CANONICAL_SCOPE_ALIASES.get(scope)
    if alias is not None:
        logger.debug("check: normalized scope alias %r -> %r", scope, alias)
        return alias
    if _SCOPE_ENTRY_RE.match(scope):
        return scope
    match = _TOOL_ID_SCOPE_RE.match(scope)
    if match is None:
        return scope
    tool_id = match.group("tool_id")
    if "_" not in tool_id:
        return scope
    family, action = tool_id.split("_", 1)
    normalized = f"{match.group('verb')}:{family}.{action}"
    normalized = _CANONICAL_SCOPE_ALIASES.get(normalized, normalized)
    logger.debug("check: normalized scope entry %r -> %r", scope, normalized)
    return normalized


def _normalize_verify_scope_entry(scope: str) -> str | None:
    """Normalize a verify scope and drop public lookup aliases from delegation."""
    normalized = _normalize_scope_entry(scope)
    if normalized in _NON_DELEGATING_VERIFY_SCOPE_ALIASES:
        logger.debug("check: ignored non-delegating scope alias %r", scope)
        return None
    return normalized


def _normalize_verify_scope_list(entries: list[object]) -> list[object]:
    """Normalize model-emitted verify scope_list entries while preserving order."""
    normalized_entries: list[object] = []
    seen_strings: set[str] = set()
    for entry in entries:
        if not isinstance(entry, str):
            normalized_entries.append(entry)
            continue
        stripped = entry.strip()
        if not stripped:
            continue
        normalized = _normalize_verify_scope_entry(stripped)
        if normalized is None or normalized in seen_strings:
            continue
        normalized_entries.append(normalized)
        seen_strings.add(normalized)
    return normalized_entries


def _cacheable_auth_context(raw: object) -> bool:
    """Return True when a verify result can authorize later submit calls."""
    return (
        getattr(raw, "status", None) == "verified"
        and getattr(raw, "published_tier", None) is not None
    )


def _inject_delegation_context(
    params: dict[str, object],
    auth_context: object,
) -> dict[str, object]:
    """Attach the latest typed DelegationContext to submit params when present."""
    delegation_context = getattr(auth_context, "delegation_context", None)
    if delegation_context is None:
        return params
    merged = {
        key: value for key, value in params.items() if key not in _DELEGATION_CONTEXT_SPREAD_KEYS
    }
    removed_keys = sorted(set(params) - set(merged))
    if removed_keys:
        logger.info(
            "send: removed model-spread delegation fields before injecting "
            "backend-owned DelegationContext: %s",
            ",".join(removed_keys),
        )
    dump = getattr(delegation_context, "model_dump", None)
    if callable(dump):
        merged["delegation_context"] = dump(mode="json")
    else:
        merged["delegation_context"] = delegation_context
    return merged


def _bind_submit_session_id(
    params: dict[str, object],
    *,
    session_id: str,
) -> dict[str, object]:
    """Verified delegation session_id wins over model-emitted submit values."""
    if "session_id" not in params:
        return params
    merged = dict(params)
    if merged.get("session_id") != session_id:
        logger.info(
            "send: replacing model-emitted session_id with verified session_id "
            "for delegation session binding"
        )
    merged["session_id"] = session_id
    return merged


def _delegation_scope_entries(auth_context: object | None) -> set[str]:
    """Extract comma-joined delegation token scopes from a cached AuthContext."""
    if auth_context is None:
        return set()
    delegation_context = getattr(auth_context, "delegation_context", None)
    token = getattr(delegation_context, "token", None)
    scope = getattr(token, "scope", None)
    if not isinstance(scope, str):
        return set()
    return {_normalize_scope_entry(entry.strip()) for entry in scope.split(",") if entry.strip()}


def _sensitive_lookup_requirement(args_obj: dict[str, object]) -> dict[str, str] | None:
    """Return auth requirement metadata for personal-data lookup calls."""
    mode = args_obj.get("mode")
    if mode not in (None, "fetch"):
        return None
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str):
        return None
    return _SENSITIVE_LOOKUP_AUTH_REQUIREMENTS.get(tool_id)


def _check_sensitive_lookup_auth_prerequisite(
    fname: str,
    args_obj: dict[str, object],
    auth_context: object | None,
) -> str | None:
    """Return recovery text when a sensitive lookup lacks verified delegation.

    UMMAYA keeps read-only public-data lookups permissive, but citizen-specific
    tax records carry private financial/medical/education deduction fields. The
    gateway boundary therefore requires a prior verify result whose delegation
    token grants the exact lookup scope before the lookup dispatch can proceed.
    """
    if fname != "find":
        return None
    requirement = _sensitive_lookup_requirement(args_obj)
    if requirement is None:
        return None
    required_scope = requirement["scope"]
    scopes = _delegation_scope_entries(auth_context)
    if required_scope in scopes:
        return None
    tool_id = str(args_obj.get("tool_id") or "")
    verify_tool_id = requirement["verify_tool_id"]
    purpose_ko = requirement["purpose_ko"]
    purpose_en = requirement["purpose_en"]
    if not scopes:
        reason = "No verified delegation context is cached for this session."
    else:
        reason = f"Latest delegation scope(s) {sorted(scopes)!r} do not include {required_scope!r}."
    return (
        f"Sensitive lookup auth prerequisite missing: {tool_id} reads "
        "citizen-specific Hometax simplified tax data and MUST NOT run before "
        f"a verify turn grants {required_scope!r}. {reason} "
        "RECOVERY: in the next turn call "
        f"check(tool_id={verify_tool_id!r}, params={{"
        f'"scope_list": [{required_scope!r}], '
        f'"purpose_ko": {purpose_ko!r}, '
        f'"purpose_en": {purpose_en!r}'
        "}}). Do NOT answer from cached or synthetic tax data until that check "
        "tool_result succeeds; then retry the original find."
    )


def _sensitive_lookup_verify_redirect_for_query(
    fname: str,
    args_obj: dict[str, object],
    user_query: str,
    auth_context: object | None,
) -> dict[str, str] | None:
    """Return the verify requirement that should preempt a sensitive lookup.

    The citizen-visible flow must not render a red auth error for a predictable
    model ordering mistake when the latest citizen query already implies the
    required verify scope. In that case the API layer discards the premature
    find call and forces the next turn to the canonical check primitive.
    """
    if fname != "find":
        return None
    requirement = _sensitive_lookup_requirement(args_obj)
    if requirement is None:
        return None
    required_scope = requirement["scope"]
    if required_scope in _delegation_scope_entries(auth_context):
        return None
    verify_requirement = _verify_requirement_for_query(user_query)
    if verify_requirement is None:
        return None
    if verify_requirement["verify_tool_id"] != requirement["verify_tool_id"]:
        return None
    if required_scope not in _requirement_scope_entries(verify_requirement):
        return None
    return verify_requirement


def _sensitive_lookup_requirement_for_query(user_query: str) -> dict[str, str] | None:
    """Map a citizen query to the sensitive lookup that must follow verify."""
    verify_requirement = _verify_requirement_for_query(user_query)
    if verify_requirement is None:
        return None
    required_scope = verify_requirement["scope"]
    for tool_id, requirement in _SENSITIVE_LOOKUP_AUTH_REQUIREMENTS.items():
        if requirement["scope"] == required_scope:
            return {**requirement, "tool_id": tool_id}
    return None


def _tool_call_arguments_dict(tool_call: object) -> dict[str, object]:
    """Extract function-call arguments from SDK or dict tool-call shapes."""
    raw_args = getattr(getattr(tool_call, "function", None), "arguments", None) or (
        tool_call.get("function", {}).get("arguments") if isinstance(tool_call, dict) else None
    )
    if isinstance(raw_args, str):
        try:
            parsed: object = _stdlib_json.loads(raw_args)
        except _stdlib_json.JSONDecodeError:
            return {}
    else:
        parsed = raw_args
    if not isinstance(parsed, dict):
        return {}
    return {str(key): value for key, value in parsed.items()}


def _payload_dict_is_error_like(payload: dict[str, object]) -> bool:
    """Return True when a primitive payload is a structured failure."""
    if payload.get("kind") == "error" or payload.get("denied") is True:
        return True
    reason = payload.get("reason")
    if isinstance(reason, str) and reason in _PRIMITIVE_ERROR_REASONS:
        return True
    structured = payload.get("structured")
    if isinstance(structured, dict) and isinstance(structured.get("exception_type"), str):
        return True
    error = payload.get("error")
    return isinstance(error, str) and bool(error)


def _tool_result_payload_is_error(payload: object) -> bool:
    """Return True for structured tool-result payloads that are errors."""
    if not isinstance(payload, dict):
        return False
    if _payload_dict_is_error_like(payload):
        return True
    result = payload.get("result")
    return isinstance(result, dict) and _payload_dict_is_error_like(
        {str(key): value for key, value in result.items()}
    )


def _lookup_call_ids_for_tool(
    llm_messages: list[Any],
    *,
    tool_id: str,
) -> set[str]:
    """Collect assistant lookup call IDs that target a specific adapter."""
    matching_call_ids: set[str] = set()
    for msg in llm_messages:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role != "assistant":
            continue
        tool_calls = getattr(msg, "tool_calls", None) or (
            msg.get("tool_calls") if isinstance(msg, dict) else None
        )
        if not tool_calls:
            continue
        for tool_call in tool_calls:
            call_fn = getattr(getattr(tool_call, "function", None), "name", None) or (
                tool_call.get("function", {}).get("name") if isinstance(tool_call, dict) else None
            )
            if call_fn != "find":
                continue
            args = _tool_call_arguments_dict(tool_call)
            call_id = getattr(tool_call, "id", None) or (
                tool_call.get("id") if isinstance(tool_call, dict) else None
            )
            if args.get("tool_id") == tool_id and isinstance(call_id, str):
                matching_call_ids.add(call_id)
    return matching_call_ids


def _tool_result_payload_for_call(
    msg: Any,
    *,
    matching_call_ids: set[str],
) -> object | None:
    """Parse a lookup tool-result message when it matches one of call IDs."""
    role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
    if role != "tool":
        return None
    name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
    if name != "find":
        return None
    call_id = getattr(msg, "tool_call_id", None) or (
        msg.get("tool_call_id") if isinstance(msg, dict) else None
    )
    if not isinstance(call_id, str) or call_id not in matching_call_ids:
        return None
    content = getattr(msg, "content", None) or (
        msg.get("content") if isinstance(msg, dict) else None
    )
    if not isinstance(content, str):
        return None
    try:
        payload: object = _stdlib_json.loads(content)
        return payload
    except _stdlib_json.JSONDecodeError:
        return None


def _conversation_has_successful_lookup(
    llm_messages: list[Any],
    *,
    tool_id: str,
) -> bool:
    """Return True when a prior lookup call for tool_id produced a non-error result."""
    matching_call_ids = _lookup_call_ids_for_tool(llm_messages, tool_id=tool_id)
    if not matching_call_ids:
        return False
    for msg in llm_messages:
        payload = _tool_result_payload_for_call(msg, matching_call_ids=matching_call_ids)
        if payload is not None and not _tool_result_payload_is_error(payload):
            return True
    return False


def _primitive_call_ids_for_tool(
    llm_messages: list[Any],
    *,
    primitive: str,
    tool_id: str | None = None,
) -> set[str]:
    """Collect assistant primitive call IDs, optionally narrowed by adapter id."""
    matching_call_ids: set[str] = set()
    for msg in llm_messages:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role != "assistant":
            continue
        tool_calls = getattr(msg, "tool_calls", None) or (
            msg.get("tool_calls") if isinstance(msg, dict) else None
        )
        if not tool_calls:
            continue
        for tool_call in tool_calls:
            call_fn = getattr(getattr(tool_call, "function", None), "name", None) or (
                tool_call.get("function", {}).get("name") if isinstance(tool_call, dict) else None
            )
            if call_fn != primitive:
                continue
            args = _tool_call_arguments_dict(tool_call)
            if tool_id is not None and args.get("tool_id") != tool_id:
                continue
            call_id = getattr(tool_call, "id", None) or (
                tool_call.get("id") if isinstance(tool_call, dict) else None
            )
            if isinstance(call_id, str):
                matching_call_ids.add(call_id)
    return matching_call_ids


def _tool_result_payload_for_primitive_call(
    msg: Any,
    *,
    primitive: str,
    matching_call_ids: set[str],
) -> object | None:
    """Parse a primitive tool-result message when it matches one of call IDs."""
    role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
    if role != "tool":
        return None
    name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
    if name != primitive:
        return None
    call_id = getattr(msg, "tool_call_id", None) or (
        msg.get("tool_call_id") if isinstance(msg, dict) else None
    )
    if not isinstance(call_id, str) or call_id not in matching_call_ids:
        return None
    content = getattr(msg, "content", None) or (
        msg.get("content") if isinstance(msg, dict) else None
    )
    if not isinstance(content, str):
        return None
    try:
        payload: object = _stdlib_json.loads(content)
        return payload
    except _stdlib_json.JSONDecodeError:
        return None


def _tool_result_payload_for_primitive(
    msg: Any,
    *,
    primitive: str,
) -> object | None:
    """Parse a primitive tool-result payload from a tool message.

    Unlike ``_tool_result_payload_for_primitive_call``, this helper does not
    require matching call IDs. It is used for recovery gates that need the
    resolved state of the most recent primitive invocation, not a specific
    call handle.
    """
    role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
    if role != "tool":
        return None
    name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
    if name != primitive:
        return None
    content = getattr(msg, "content", None) or (
        msg.get("content") if isinstance(msg, dict) else None
    )
    if not isinstance(content, str):
        return None
    try:
        payload: object = _stdlib_json.loads(content)
        return payload
    except _stdlib_json.JSONDecodeError:
        return None


def _primitive_payload_is_success(payload: object, *, primitive: str) -> bool:
    """Return True when a primitive payload represents a completed operation."""
    if _tool_result_payload_is_error(payload):
        return False
    if not isinstance(payload, dict):
        return True
    result = payload.get("result")
    if primitive == "send":
        if isinstance(result, dict) and result.get("status") == "succeeded":
            return True
        return payload.get("status") == "succeeded"
    return True


def _canonical_primitive_args(args: dict[str, object]) -> str:
    """Stable signature for comparing repeated primitive calls."""
    try:
        return _stdlib_json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return repr(sorted(args.items()))


def _conversation_has_successful_identical_primitive_call(  # noqa: C901
    llm_messages: list[Any],
    *,
    primitive: str,
    args: dict[str, object],
) -> bool:
    """Return True when the exact primitive call already succeeded in this turn.

    This is a non-progress guard, not an alternate data path. If the model asks
    for the same primitive and the same schema-valid arguments after a successful
    result, dispatching it again can only burn quota and may push the loop into
    a blank max-turn termination.
    """
    target_signature = _canonical_primitive_args(args)
    matching_call_ids: set[str] = set()
    for msg in llm_messages:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role != "assistant":
            continue
        tool_calls = getattr(msg, "tool_calls", None) or (
            msg.get("tool_calls") if isinstance(msg, dict) else None
        )
        if not tool_calls:
            continue
        for tool_call in tool_calls:
            call_fn = getattr(getattr(tool_call, "function", None), "name", None) or (
                tool_call.get("function", {}).get("name") if isinstance(tool_call, dict) else None
            )
            if call_fn != primitive:
                continue
            call_id = getattr(tool_call, "id", None) or (
                tool_call.get("id") if isinstance(tool_call, dict) else None
            )
            if not isinstance(call_id, str):
                continue
            if _canonical_primitive_args(_tool_call_arguments_dict(tool_call)) == target_signature:
                matching_call_ids.add(call_id)

    if not matching_call_ids:
        return False

    for msg in llm_messages:
        payload = _tool_result_payload_for_primitive_call(
            msg,
            primitive=primitive,
            matching_call_ids=matching_call_ids,
        )
        if payload is not None and _primitive_payload_is_success(payload, primitive=primitive):
            return True
    return False


def _conversation_has_successful_primitive(
    llm_messages: list[Any],
    *,
    primitive: str,
    tool_id: str,
) -> bool:
    """Return True when a prior primitive call for tool_id completed successfully."""
    matching_call_ids = _primitive_call_ids_for_tool(
        llm_messages,
        primitive=primitive,
        tool_id=tool_id,
    )
    if not matching_call_ids:
        return False
    for msg in llm_messages:
        payload = _tool_result_payload_for_primitive_call(
            msg,
            primitive=primitive,
            matching_call_ids=matching_call_ids,
        )
        if payload is not None and _primitive_payload_is_success(payload, primitive=primitive):
            return True
    return False


def _conversation_has_primitive_call(
    llm_messages: list[Any],
    *,
    primitive: str,
    tool_id: str,
) -> bool:
    """Return True when a prior assistant turn called a specific adapter."""
    return bool(
        _primitive_call_ids_for_tool(
            llm_messages,
            primitive=primitive,
            tool_id=tool_id,
        )
    )


def _conversation_has_successful_primitive_any_tool(
    llm_messages: list[Any],
    *,
    primitive: str,
) -> bool:
    """Return True when any prior tool result for ``primitive`` succeeded."""
    for msg in llm_messages:
        payload = _tool_result_payload_for_primitive(msg, primitive=primitive)
        if payload is not None and _primitive_payload_is_success(payload, primitive=primitive):
            return True
    return False


def _latest_successful_primitive_result(
    llm_messages: list[Any],
    *,
    primitive: str,
) -> dict[str, object] | None:
    """Return the most recent successful primitive result payload."""
    for msg in reversed(llm_messages):
        payload = _tool_result_payload_for_primitive(msg, primitive=primitive)
        if payload is None or not _primitive_payload_is_success(payload, primitive=primitive):
            continue
        if not isinstance(payload, dict):
            continue
        result = payload.get("result")
        if isinstance(result, dict):
            return cast("dict[str, object]", result)
    return None


def _latest_successful_primitive_result_for_tool(
    llm_messages: list[Any],
    *,
    primitive: str,
    tool_id: str,
) -> dict[str, object] | None:
    """Return the most recent successful primitive result payload for tool_id."""
    matching_call_ids = _primitive_call_ids_for_tool(
        llm_messages,
        primitive=primitive,
        tool_id=tool_id,
    )
    if not matching_call_ids:
        return None
    for msg in reversed(llm_messages):
        payload = _tool_result_payload_for_primitive_call(
            msg,
            primitive=primitive,
            matching_call_ids=matching_call_ids,
        )
        if payload is None or not _primitive_payload_is_success(payload, primitive=primitive):
            continue
        if not isinstance(payload, dict):
            continue
        result = payload.get("result")
        if isinstance(result, dict):
            return cast("dict[str, object]", result)
    return None


def _scrub_tool_result_for_final_observation(value: object) -> object:
    """Return a prompt-safe, bounded copy of a tool result payload.

    This preserves the adapter-returned data shape for the next model turn
    without turning it into a domain-specific answer. Large transport traces are
    omitted because the model needs the observation, not HTTP debug evidence.
    """
    if isinstance(value, dict):
        scrubbed: dict[str, object] = {}
        for key, nested in value.items():
            key_str = str(key)
            if key_str in _FINAL_ANSWER_OBSERVATION_OMIT_KEYS:
                continue
            scrubbed[key_str] = _scrub_tool_result_for_final_observation(nested)
        return scrubbed
    if isinstance(value, list):
        visible = [
            _scrub_tool_result_for_final_observation(item)
            for item in value[:_FINAL_ANSWER_OBSERVATION_LIST_LIMIT]
        ]
        omitted = len(value) - len(visible)
        if omitted > 0:
            visible.append({"__omitted_items__": omitted})
        return visible
    if isinstance(value, str) and len(value) > _FINAL_ANSWER_OBSERVATION_STR_LIMIT:
        return value[:_FINAL_ANSWER_OBSERVATION_STR_LIMIT] + "...[truncated]"
    return value


def _latest_successful_primitive_observation(
    llm_messages: list[Any],
) -> dict[str, object] | None:
    """Return the most recent successful primitive tool_result for prompt repair."""
    for msg in reversed(llm_messages):
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role != "tool":
            continue
        primitive = getattr(msg, "name", None) or (
            msg.get("name") if isinstance(msg, dict) else None
        )
        if primitive not in {"find", "locate", "check", "send"}:
            continue
        payload = _tool_result_payload_for_primitive(msg, primitive=str(primitive))
        if payload is None or not _primitive_payload_is_success(payload, primitive=str(primitive)):
            continue
        tool_call_id = getattr(msg, "tool_call_id", None) or (
            msg.get("tool_call_id") if isinstance(msg, dict) else None
        )
        return {
            "primitive": str(primitive),
            "tool_call_id": str(tool_call_id) if isinstance(tool_call_id, str) else None,
            "payload": _scrub_tool_result_for_final_observation(payload),
        }
    return None


def _final_answer_observation_message(
    *,
    message: str,
    latest_user_utt: str,
    llm_messages: list[Any],
) -> str:
    """Build a generic final-answer repair prompt from observed tool data."""
    observation = _latest_successful_primitive_observation(llm_messages)
    observation_json = "{}"
    if observation is not None:
        observation_json = _stdlib_json.dumps(
            observation,
            ensure_ascii=False,
            default=str,
        )
        if len(observation_json) > _FINAL_ANSWER_OBSERVATION_JSON_LIMIT:
            observation_json = (
                observation_json[:_FINAL_ANSWER_OBSERVATION_JSON_LIMIT] + "...[truncated]"
            )

    return (
        "[UMMAYA FINAL ANSWER OBSERVATION]\n"
        f"{message}\n\n"
        "Citizen request:\n"
        f"{latest_user_utt}\n\n"
        "Latest successful primitive tool_result JSON:\n"
        f"{observation_json}\n\n"
        "Use only the observed tool_result data above and the prior tool_result "
        "messages. Do not call another tool. Do not invent names, addresses, "
        "phone numbers, timestamps, weather values, receipt IDs, or source "
        "metadata that are not present in the observed result. Answer the "
        "citizen directly in Korean."
    )


def _nonempty_str(value: object) -> str | None:
    """Return a stripped string when value is meaningful."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _region_pair_from_address_text(text: object) -> tuple[str, str] | None:
    """Derive NMC Q0/Q1 from a structured Korean address string.

    This is intentionally conservative: it only parses strings returned by
    locate's official geocoder payloads and only extracts 시도 + 시군구.
    """
    if not isinstance(text, str):
        return None
    parts = [part.strip() for part in text.split() if part.strip()]
    if len(parts) < 2:
        return None
    q0 = parts[0]
    if not q0.endswith(("특별시", "광역시", "특별자치시", "특별자치도", "도")):
        return None
    q1 = parts[1]
    if (
        len(parts) >= 3
        and q0.endswith(("도", "특별자치도"))
        and parts[1].endswith("시")
        and parts[2].endswith(("구", "군"))
    ):
        # Kakao region_2depth_name can be "성남시 분당구"; keep that shape
        # when the fallback source was a full adm_cd/address name.
        q1 = f"{parts[1]} {parts[2]}"
    if not q1.endswith(("시", "군", "구")):
        return None
    return q0, q1


def _locate_result_region_pair(result: dict[str, object]) -> tuple[str, str] | None:  # noqa: C901
    """Extract NMC region-mode q0/q1 from a locate result."""
    for key in ("region", "coords"):
        value = result.get(key)
        if not isinstance(value, dict):
            continue
        q0 = _nonempty_str(value.get("region_1depth_name"))
        q1 = _nonempty_str(value.get("region_2depth_name"))
        if q0 and q1:
            return q0, q1

    q0 = _nonempty_str(result.get("region_1depth_name"))
    q1 = _nonempty_str(result.get("region_2depth_name"))
    if q0 and q1:
        return q0, q1

    for key in ("adm_cd", "region", "address", "poi"):
        value = result.get(key)
        if isinstance(value, dict):
            for text_key in (
                "address_name",
                "name",
                "road_address",
                "jibun_address",
                "road_address_name",
            ):
                pair = _region_pair_from_address_text(value.get(text_key))
                if pair is not None:
                    return pair
    for text_key in ("address_name", "name", "road_address", "jibun_address"):
        pair = _region_pair_from_address_text(result.get(text_key))
        if pair is not None:
            return pair
    return None


def _locate_result_coords(result: dict[str, object]) -> tuple[float, float] | None:
    """Extract WGS-84 lat/lon from a locate result."""
    candidates: list[object] = [result.get("coords"), result.get("poi"), result]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        lat = candidate.get("lat")
        lon = candidate.get("lon")
        if isinstance(lat, int | float) and isinstance(lon, int | float):
            return float(lat), float(lon)
    return None


def _normalize_nmc_lookup_args_from_prior_locate(
    fname: str,
    args_obj: dict[str, object],
    llm_messages: list[Any],
) -> dict[str, object]:
    """Fill NMC region-mode params from the latest successful locate result.

    CC's equivalent control point is Tool.validateInput(input, context): tool
    definitions guide the call, and the executor can still inspect surrounding
    context before running the tool. UMMAYA keeps NMC's official operation
    semantics in the adapter description, then normalizes here when the model
    selected the right adapter but omitted the derived q0/q1 fields.
    """
    if fname != "find" or args_obj.get("tool_id") != "nmc_emergency_search":
        return args_obj

    raw_params = args_obj.get("params")
    params = dict(raw_params) if isinstance(raw_params, dict) else {}
    limit = params.get("limit")
    needs_default_limit = not isinstance(limit, int) or isinstance(limit, bool)

    has_region_params = (
        params.get("mode") == "region"
        and bool(_nonempty_str(params.get("q0")))
        and bool(_nonempty_str(params.get("q1")))
    )
    if has_region_params and not needs_default_limit:
        return args_obj

    locate_result = _latest_successful_primitive_result(llm_messages, primitive="locate")
    if locate_result is None:
        if has_region_params and needs_default_limit:
            normalized = dict(args_obj)
            next_params = dict(params)
            next_params["limit"] = 5
            normalized["params"] = next_params
            return normalized
        return args_obj

    region_pair = _locate_result_region_pair(locate_result)
    if region_pair is None:
        return args_obj
    origin_coords = _locate_result_coords(locate_result)

    next_params = dict(params)
    next_params["mode"] = "region"
    next_params["q0"], next_params["q1"] = region_pair
    next_params.pop("lat", None)
    next_params.pop("lon", None)
    if origin_coords is not None:
        next_params["origin_lat"] = origin_coords[0]
        next_params["origin_lon"] = origin_coords[1]
    if needs_default_limit:
        next_params["limit"] = 5

    if next_params == params and isinstance(raw_params, dict):
        return args_obj
    normalized = dict(args_obj)
    normalized["params"] = next_params
    logger.info(
        "find: normalized nmc_emergency_search params from prior locate q0=%s q1=%s origin=%s",
        next_params.get("q0"),
        next_params.get("q1"),
        origin_coords,
    )
    return normalized


def _check_sensitive_lookup_terminated_without_lookup(
    llm_messages: list[Any],
    user_query: str,
    auth_context: object | None,
) -> dict[str, str] | None:
    """Return recovery metadata when verify succeeded but the lookup never ran."""
    requirement = _sensitive_lookup_requirement_for_query(user_query)
    if requirement is None:
        return None
    required_scope = requirement["scope"]
    if required_scope not in _delegation_scope_entries(auth_context):
        return None
    tool_id = requirement["tool_id"]
    if _conversation_has_successful_lookup(llm_messages, tool_id=tool_id):
        return None
    return {
        **requirement,
        "message": (
            "Sensitive lookup follow-up missing: verify has already granted "
            f"{required_scope!r}, but the citizen's requested data has not been "
            f"retrieved from {tool_id!r}. RECOVERY: in the next turn call "
            f"find(tool_id={tool_id!r}, params={{}}). "
            "Do NOT answer from the verify result alone; summarize the requested "
            "medical and education deduction fields only after the find "
            "tool_result succeeds."
        ),
    }


def _conversation_has_tool_call(llm_messages: list[Any], tool_name: str) -> bool:
    """Return True when conversation history already contains a tool call/result."""
    for msg in llm_messages:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role == "tool":
            name = getattr(msg, "name", None) or (
                msg.get("name") if isinstance(msg, dict) else None
            )
            if name == tool_name:
                return True
            continue
        if role != "assistant":
            continue
        tool_calls = getattr(msg, "tool_calls", None) or (
            msg.get("tool_calls") if isinstance(msg, dict) else None
        )
        if tool_calls:
            for tool_call in tool_calls:
                call_fn = getattr(getattr(tool_call, "function", None), "name", None) or (
                    tool_call.get("function", {}).get("name")
                    if isinstance(tool_call, dict)
                    else None
                )
                if call_fn == tool_name:
                    return True
        content = getattr(msg, "content", None) or (
            msg.get("content") if isinstance(msg, dict) else None
        )
        if isinstance(content, str) and tool_name in content:
            return True
    return False


def _verify_requirement_for_query(user_query: str) -> dict[str, str] | None:  # noqa: C901
    """Map citizen auth wording to the verify tool/scope the next turn must call."""
    if not user_query:
        return None
    compact = re.sub(r"\s+", "", user_query).lower()
    lowered = user_query.lower()
    submit_requirement = _submit_requirement_for_query(user_query)
    if (
        submit_requirement is not None
        and submit_requirement["tool_id"] == "mock_submit_module_public_mydata_action"
    ):
        return {
            "verify_tool_id": "mock_verify_mydata",
            "allowed_tool_ids": "mock_verify_mydata",
            "scope": "send:public_mydata.action",
            "allowed_scopes": "send:public_mydata.action",
            "purpose_ko": "공공 마이데이터 제공 동의",
            "purpose_en": "Public MyData consent action",
        }
    if submit_requirement is not None:
        submit_tool_id = submit_requirement["tool_id"]
        if submit_tool_id == "mock_submit_module_hometax_taxreturn":
            return {
                "verify_tool_id": "mock_verify_module_modid",
                "allowed_tool_ids": "mock_verify_module_modid",
                "scope": "find:hometax.simplified",
                "required_scopes": "find:hometax.simplified,send:hometax.tax-return",
                "allowed_scopes": "find:hometax.simplified,send:hometax.tax-return",
                "purpose_ko": "종합소득세 신고",
                "purpose_en": "Comprehensive income tax filing",
            }
        if submit_tool_id == "mock_submit_module_gov24_minwon":
            wants_modid = (
                "mock_verify_module_modid" in lowered
                or "모바일id" in compact
                or "mobileid" in compact
            )
            return {
                "verify_tool_id": "mock_verify_module_modid"
                if wants_modid
                else "mock_verify_module_simple_auth",
                "allowed_tool_ids": "mock_verify_module_simple_auth,mock_verify_module_modid",
                "scope": "send:gov24.minwon",
                "allowed_scopes": "send:gov24.minwon",
                "purpose_ko": "주민등록등본 발급 민원 신청",
                "purpose_en": "Gov24 resident registration certificate civil petition",
            }
        if submit_tool_id == "mock_welfare_application_submit_v1":
            return {
                "verify_tool_id": "mock_verify_mydata",
                "allowed_tool_ids": "mock_verify_mydata",
                "scope": "send:mydata.welfare_application",
                "allowed_scopes": "send:mydata.welfare_application",
                "purpose_ko": "한부모가족 아동양육비 지원 신청",
                "purpose_en": "Single-parent family child support application",
            }
        if submit_tool_id == "mock_traffic_fine_pay_v1":
            return {
                "verify_tool_id": "mock_verify_ganpyeon_injeung",
                "allowed_tool_ids": "mock_verify_ganpyeon_injeung",
                "scope": "send:traffic.fine-pay",
                "allowed_scopes": "send:traffic.fine-pay",
                "purpose_ko": "교통 과태료 납부",
                "purpose_en": "Traffic fine payment",
            }
    for keywords, requirement in _VERIFY_QUERY_REQUIREMENTS:
        for keyword in keywords:
            needle = re.sub(r"\s+", "", keyword).lower()
            if needle in compact or keyword.lower() in lowered:
                return requirement
    return None


def _compact_query(user_query: str) -> str:
    return re.sub(r"\s+", "", user_query).lower()


def _query_contains_any(user_query: str, keywords: tuple[str, ...]) -> bool:
    compact = _compact_query(user_query)
    lowered = user_query.lower()
    for keyword in keywords:
        needle = _compact_query(keyword)
        if needle in compact or keyword.lower() in lowered:
            return True
    return False


def _extract_tax_year(user_query: str, fallback: int = 2025) -> int:
    """Return the tax year encoded by the citizen query or the mock fixture default."""
    match = re.search(r"(20[2-3]\d)\s*년", user_query)
    if match is None:
        return fallback
    return int(match.group(1))


def _query_uses_relative_previous_year(user_query: str) -> bool:
    return _query_contains_any(user_query, ("작년", "지난해", "전년도"))


def _extract_session_id(user_query: str, fallback: str) -> str:
    match = re.search(r"[A-Z][A-Z0-9]+(?:-[A-Z0-9]+){2,}", user_query)
    return match.group(0) if match else fallback


def _submit_requirement_for_query(user_query: str) -> dict[str, str] | None:
    """Map citizen write/payment wording to the submit adapter that must run."""
    if not user_query:
        return None
    compact = _compact_query(user_query)
    asks_submit = any(
        token in compact for token in ("신청", "발급", "납부", "결제", "신고", "동의")
    )

    asks_hometax_tax_return = _query_contains_any(
        user_query,
        ("종합소득세", "소득세 신고", "세금 신고", "세금신고", "홈택스 신고"),
    ) or (
        _query_contains_any(user_query, ("홈택스",))
        and _query_contains_any(user_query, ("신고", "신고서", "제출"))
    )
    if asks_submit and asks_hometax_tax_return:
        session_id = _extract_session_id(user_query, "HOMETAX-TAXRETURN-SESSION-001")
        params = {
            "tax_year": _extract_tax_year(user_query),
            "income_type": "종합소득",
            "total_income_krw": 42_000_000,
            "session_id": session_id,
        }
        return {
            "tool_id": "mock_submit_module_hometax_taxreturn",
            "verify_tool_id": "mock_verify_module_modid",
            "scope": "send:hometax.tax-return",
            "pre_submit_lookup_tool_id": "mock_lookup_module_hometax_simplified",
            "params_json": _stdlib_json.dumps(params, ensure_ascii=False),
        }

    if asks_submit and _query_contains_any(user_query, ("정부24", "주민등록등본", "등본", "민원")):
        session_id = _extract_session_id(user_query, "GOV24-MINWON-SESSION-001")
        params = {
            "minwon_type": "주민등록등본",
            "applicant_name": "홍길동" if "홍길동" in user_query else "MOCK_APPLICANT",
            "delivery_method": "online",
            "session_id": session_id,
        }
        return {
            "tool_id": "mock_submit_module_gov24_minwon",
            "verify_tool_id": "mock_verify_module_simple_auth",
            "scope": "send:gov24.minwon",
            "params_json": _stdlib_json.dumps(params, ensure_ascii=False),
        }

    if asks_submit and _query_contains_any(
        user_query,
        ("복지 급여", "복지신청", "한부모가족", "한부모", "아동양육비"),
    ):
        applicant_match = re.search(r"DI-[A-Z0-9-]+", user_query)
        household_match = re.search(r"(\d+)\s*명", user_query)
        params = {
            "applicant_id": applicant_match.group(0)
            if applicant_match
            else "DI-MOCK-WELFARE-APPLICANT",
            "benefit_code": "WLF00001068",
            "application_type": "new",
            "household_size": int(household_match.group(1)) if household_match else 1,
        }
        return {
            "tool_id": "mock_welfare_application_submit_v1",
            "verify_tool_id": "mock_verify_mydata",
            "scope": "send:mydata.welfare_application",
            "params_json": _stdlib_json.dumps(params, ensure_ascii=False),
        }

    if asks_submit and _query_contains_any(user_query, ("과태료", "교통범칙금", "범칙금")):
        params = {
            "fine_reference": "MOCK-FINE-2026-001",
            "payment_method": "virtual_account",
        }
        return {
            "tool_id": "mock_traffic_fine_pay_v1",
            "verify_tool_id": "mock_verify_ganpyeon_injeung",
            "scope": "send:traffic.fine-pay",
            "params_json": _stdlib_json.dumps(params, ensure_ascii=False),
        }

    if asks_submit and _query_contains_any(user_query, ("마이데이터", "공공마이데이터")):
        session_id = _extract_session_id(user_query, "MYDATA-ACTION-SESSION-001")
        params = {
            "action_type": "transfer_consent",
            "target_institution_code": "PUBLIC-MYDATA-MOCK",
            "applicant_di": "DI-MOCK-MYDATA-001",
            "session_id": session_id,
        }
        return {
            "tool_id": "mock_submit_module_public_mydata_action",
            "verify_tool_id": "mock_verify_mydata",
            "scope": "send:public_mydata.action",
            "params_json": _stdlib_json.dumps(params, ensure_ascii=False),
        }

    return None


def _check_submit_terminated_without_submit(
    llm_messages: list[Any],
    user_query: str,
    auth_context: object | None,
) -> dict[str, str] | None:
    """Return recovery metadata when a write request verified but never submitted."""
    requirement = _submit_requirement_for_query(user_query)
    if requirement is None:
        return None
    if _conversation_has_successful_primitive(
        llm_messages,
        primitive="send",
        tool_id=requirement["tool_id"],
    ):
        return None
    if auth_context is None or not _conversation_has_tool_call(llm_messages, "check"):
        return None
    pre_submit_lookup_tool_id = requirement.get("pre_submit_lookup_tool_id")
    if pre_submit_lookup_tool_id and not _conversation_has_successful_lookup(
        llm_messages,
        tool_id=pre_submit_lookup_tool_id,
    ):
        return None
    params_json = requirement["params_json"]
    tool_id = requirement["tool_id"]
    return {
        **requirement,
        "message": (
            "Send follow-up missing: the citizen asked to complete a write, "
            "payment, consent, or filing flow and verification has already run, "
            f"but {tool_id!r} has not succeeded. RECOVERY: in the next turn call "
            f"send(tool_id={tool_id!r}, params={params_json}). The backend will "
            "inject the cached DelegationContext. Do NOT ask for additional mock "
            "fields and do NOT end with guidance-only prose."
        ),
    }


def _check_duplicate_submit_prerequisite(
    fname: str,
    args_obj: dict[str, object],
    llm_messages: list[Any],
) -> str | None:
    """Reject repeat submit calls after the same adapter already succeeded."""
    if fname != "send":
        return None
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id:
        return None
    if not _conversation_has_successful_primitive(
        llm_messages,
        primitive="send",
        tool_id=tool_id,
    ):
        return None
    return (
        f"Submit already succeeded for {tool_id!r} in this conversation. "
        "RECOVERY: do NOT call send again and do NOT request another "
        "permission decision. Produce the final citizen-facing answer from the "
        "prior successful submit tool_result and include the mock disclosure."
    )


def _check_unrequested_verify_after_public_find(
    fname: str,
    llm_messages: list[Any],
    user_query: str,
) -> str | None:
    """Suppress identity checks that were not requested after public lookup.

    Public data ``find`` results are read-only.  If the citizen did not ask
    for authentication, submission, consent, or identity verification, a later
    ``check`` call can only create a spurious permission prompt.  Keep that
    recoverable routing error inside the agentic loop and ask the model to
    finish from the successful public-data result instead.
    """

    if fname != "check":
        return None
    if _verify_requirement_for_query(user_query) is not None:
        return None
    if not _conversation_has_successful_primitive_any_tool(llm_messages, primitive="find"):
        return None
    return (
        "The citizen request has a successful public-data find result and does "
        "not contain an authentication, identity, consent, submit, payment, or "
        "filing requirement. RECOVERY: do NOT call check and do NOT show a "
        "permission prompt. Produce the citizen-facing final answer from the "
        "latest successful find tool_result."
    )


def _submit_requirement_params(requirement: dict[str, str]) -> dict[str, object] | None:
    try:
        parsed = _stdlib_json.loads(requirement["params_json"])
    except _stdlib_json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(key): value for key, value in parsed.items()}


def _canonicalize_submit_tool_id(
    args_obj: dict[str, object],
    requirement: dict[str, str],
) -> dict[str, object]:
    required_tool_id = requirement["tool_id"]
    tool_id = args_obj.get("tool_id")
    if tool_id == required_tool_id:
        return args_obj
    if not isinstance(tool_id, str) or not tool_id:
        return {**args_obj, "tool_id": required_tool_id}
    emitted_scope = _normalize_scope_entry(f"send:{tool_id}")
    if tool_id != "send" and emitted_scope != requirement["scope"]:
        return args_obj
    logger.info(
        "send: normalized model-emitted tool_id %r -> %r for citizen request",
        tool_id,
        required_tool_id,
    )
    return {**args_obj, "tool_id": required_tool_id}


def _apply_submit_canonical_params(
    params: dict[str, object],
    canonical: dict[str, object],
    tool_id: str,
) -> bool:
    """Apply submit fixture defaults, overwriting Hometax mock guesses."""
    changed = False
    overwrite = tool_id == "mock_submit_module_hometax_taxreturn"
    for key, value in canonical.items():
        if overwrite:
            if params.get(key) != value:
                params[key] = value
                changed = True
            continue
        if key not in params or params.get(key) in (None, ""):
            params[key] = value
            changed = True
    return changed


def _normalize_submit_args_for_query(
    fname: str,
    args_obj: dict[str, object],
    user_query: str,
) -> dict[str, object]:
    """Fill submit adapter payload fields already present in the citizen request."""
    if fname != "send":
        return args_obj
    requirement = _submit_requirement_for_query(user_query)
    if requirement is None:
        return args_obj

    args_obj = _canonicalize_submit_tool_id(args_obj, requirement)
    if args_obj.get("tool_id") != requirement["tool_id"]:
        return args_obj

    canonical = _submit_requirement_params(requirement)
    if canonical is None:
        return args_obj

    raw_params = args_obj.get("params")
    params = dict(raw_params) if isinstance(raw_params, dict) else {}
    for key in canonical:
        top_level_value = args_obj.get(key)
        if key not in params and top_level_value not in (None, ""):
            params[key] = top_level_value
    changed = _apply_submit_canonical_params(params, canonical, requirement["tool_id"])
    if not changed and params is raw_params:
        return args_obj
    normalized = dict(args_obj)
    normalized["params"] = params
    return normalized


def _strip_hometax_lookup_context_noise(params: dict[str, object]) -> bool:
    """Remove model-invented lookup fields from delegation_context."""
    delegation_context = params.get("delegation_context")
    if not isinstance(delegation_context, dict):
        return False
    cleaned = dict(delegation_context)
    changed = False
    for key in ("year", "resident_id_prefix"):
        if key in cleaned:
            cleaned.pop(key, None)
            changed = True
    if changed:
        params["delegation_context"] = cleaned
    return changed


def _normalize_hometax_lookup_args_for_query(
    args_obj: dict[str, object],
    user_query: str,
) -> dict[str, object]:
    """Fill deterministic Hometax simplified lookup fields from mock context."""
    if args_obj.get("tool_id") != "mock_lookup_module_hometax_simplified":
        return args_obj
    if not _query_contains_any(
        user_query,
        ("홈택스", "연말정산", "간소화", "종합소득세", "소득세 신고", "세금 신고"),
    ):
        return args_obj
    canonical: dict[str, object] = {
        "year": _extract_tax_year(user_query),
        "resident_id_prefix": "000000",
    }
    raw_params = args_obj.get("params")
    params = dict(raw_params) if isinstance(raw_params, dict) else {}
    changed = not isinstance(raw_params, dict)
    changed = _strip_hometax_lookup_context_noise(params) or changed
    for key, value in canonical.items():
        if key == "year" and _query_uses_relative_previous_year(user_query):
            if params.get(key) != value:
                params[key] = value
                changed = True
            continue
        if params.get(key) in (None, ""):
            params[key] = value
            changed = True
    if not changed:
        return args_obj
    normalized = dict(args_obj)
    normalized["params"] = params
    return normalized


def _canonicalize_lookup_tool_id_for_query(
    args_obj: dict[str, object],
    user_query: str,
) -> dict[str, object]:
    """Fill unambiguous lookup adapter id when tool_choice forced lookup only."""
    tool_id = str(args_obj.get("tool_id") or "")
    if tool_id and tool_id != "find":
        return args_obj
    sensitive_lookup = _sensitive_lookup_requirement_for_query(user_query)
    if sensitive_lookup is None:
        return args_obj
    normalized = dict(args_obj)
    normalized["tool_id"] = sensitive_lookup["tool_id"]
    logger.info(
        "find: normalized model-emitted tool_id %r -> %r for citizen request",
        tool_id or "<missing>",
        sensitive_lookup["tool_id"],
    )
    return normalized


def _normalize_lookup_args_for_query(
    fname: str,
    args_obj: dict[str, object],
    user_query: str,
    *,
    adapter_param_names: Collection[str] | None = None,
) -> dict[str, object]:
    """Fill deterministic lookup filters already present in the citizen request."""
    if fname != "find":
        return args_obj
    args_obj = _canonicalize_lookup_tool_id_for_query(args_obj, user_query)
    args_obj = _normalize_hometax_lookup_args_for_query(args_obj, user_query)
    args_obj = _normalize_lookup_result_count_args(
        args_obj,
        user_query,
        adapter_param_names=adapter_param_names,
    )
    if args_obj.get("tool_id") != "mohw_welfare_eligibility_search":
        return args_obj
    if not _query_contains_any(user_query, ("한부모가족", "한부모", "아동양육비")):
        return args_obj

    canonical: dict[str, object] = {
        "search_wrd": "한부모가족 아동양육비",
        "trgter_indvdl_array": "060",
        "onap_psblt_yn": "Y",
    }
    raw_params = args_obj.get("params")
    params = dict(raw_params) if isinstance(raw_params, dict) else {}

    changed = not isinstance(raw_params, dict)
    if params.get("life_array") in ("002", 2):
        params.pop("life_array", None)
        changed = True
    for key, value in canonical.items():
        if params.get(key) in (None, ""):
            params[key] = value
            changed = True
    if not changed:
        return args_obj

    normalized = dict(args_obj)
    normalized["params"] = params
    return normalized


_KOREAN_COUNT_WORDS: Final[dict[str, int]] = {
    "한": 1,
    "두": 2,
    "세": 3,
    "네": 4,
    "다섯": 5,
    "여섯": 6,
    "일곱": 7,
    "여덟": 8,
    "아홉": 9,
    "열": 10,
}
_RESULT_COUNT_RE = re.compile(
    r"(?P<count>\d{1,3}|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*"
    r"(?:곳|개|건|명|가지|rows?|results?)\s*(?:만|정도)?",
    re.IGNORECASE,
)


def _explicit_result_count_from_query(user_query: str) -> int | None:
    """Extract a citizen-stated result count such as '3곳만' or 'top 5'."""
    match = _RESULT_COUNT_RE.search(user_query)
    if match is None:
        top_match = re.search(r"\btop\s+(?P<count>\d{1,3})\b", user_query, re.IGNORECASE)
        if top_match is None:
            return None
        raw = top_match.group("count")
    else:
        raw = match.group("count")
    if raw.isdigit():
        count = int(raw)
    else:
        word_count = _KOREAN_COUNT_WORDS.get(raw)
        if word_count is None:
            return None
        count = word_count
    if 1 <= count <= 100:
        return count
    return None


def _normalize_lookup_result_count_args(
    args_obj: dict[str, object],
    user_query: str,
    *,
    adapter_param_names: Collection[str] | None = None,
) -> dict[str, object]:
    """Preserve explicit citizen result counts using adapter schema field names."""
    requested_count = _explicit_result_count_from_query(user_query)
    if requested_count is None:
        return args_obj
    raw_params = args_obj.get("params")
    params = dict(raw_params) if isinstance(raw_params, dict) else {}
    field_names = set(adapter_param_names or ())
    row_field: str | None = None
    for candidate in ("numOfRows", "num_of_rows", "limit", "page_size", "pageSize"):
        if candidate in field_names or candidate in params:
            row_field = candidate
            break
    if row_field is None:
        return args_obj
    if params.get(row_field) == requested_count:
        return args_obj
    normalized = dict(args_obj)
    params[row_field] = requested_count
    normalized["params"] = params
    return normalized


def _check_verify_terminated_without_verify(
    llm_messages: list[Any],
    user_query: str,
) -> dict[str, str] | None:
    """Return verify recovery metadata when an auth request is about to end as prose."""
    requirement = _verify_requirement_for_query(user_query)
    if requirement is None:
        return None
    if _conversation_has_tool_call(llm_messages, "check"):
        return None
    verify_tool_id = requirement["verify_tool_id"]
    scope_entries = _requirement_scope_entries(requirement)
    purpose_ko = requirement["purpose_ko"]
    purpose_en = requirement["purpose_en"]
    return {
        **requirement,
        "message": (
            "Check prerequisite missing: the citizen asked for an authentication, "
            "login, consent, or identity flow, but this turn is about to answer "
            "without invoking check. RECOVERY: in the next turn call "
            f"check(tool_id={verify_tool_id!r}, params={{"
            f'"scope_list": {list(scope_entries)!r}, '
            f'"purpose_ko": {purpose_ko!r}, '
            f'"purpose_en": {purpose_en!r}'
            "}}). Do NOT ask the citizen which purpose/scope to use; the system "
            "prompt mapping already defines it."
        ),
    }


def _requirement_scope_entries(requirement: dict[str, str]) -> tuple[str, ...]:
    """Return the exact verify scope_list entries required by a query contract."""
    raw_scopes = requirement.get("required_scopes") or requirement["scope"]
    return tuple(item.strip() for item in raw_scopes.split(",") if item.strip())


def _verify_scope_entries(args_obj: dict[str, object]) -> set[str]:
    """Extract normalized scope_list entries from a verify tool call."""
    raw_params = args_obj.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    raw_scope_list = params.get("scope_list", args_obj.get("scope_list"))
    if raw_scope_list is None:
        raw_session_context = params.get(
            "session_context",
            args_obj.get("session_context"),
        )
        session_context = raw_session_context if isinstance(raw_session_context, dict) else {}
        raw_scope_list = session_context.get("scope_list")
    entries: list[object]
    if isinstance(raw_scope_list, list):
        entries = raw_scope_list
    elif isinstance(raw_scope_list, str):
        entries = [raw_scope_list]
    else:
        return set()
    return {
        normalized_entry
        for entry in entries
        if isinstance(entry, str) and entry.strip()
        for normalized_entry in (_normalize_verify_scope_entry(entry.strip()),)
        if normalized_entry is not None
    }


def _verify_tool_matches_requirement(
    args_obj: dict[str, object],
    *,
    allowed_tool_ids: set[str],
    expected_tool: str,
) -> bool:
    """Return true when a verify call selects the required adapter family."""
    tool_id = str(args_obj.get("tool_id") or "")
    if tool_id in allowed_tool_ids:
        return True

    raw_params = args_obj.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    family_hint = str(
        args_obj.get("family_hint")
        or args_obj.get("family")
        or params.get("family_hint")
        or params.get("family")
        or ""
    )
    if not family_hint:
        return False

    from ummaya.tools.verify_canonical_map import resolve_family  # noqa: PLC0415

    allowed_families = {
        family
        for allowed_tool_id in allowed_tool_ids | {expected_tool}
        for family in (resolve_family(allowed_tool_id),)
        if family
    }
    return family_hint in allowed_families


def _check_verify_tool_choice_prerequisite(
    fname: str,
    args_obj: dict[str, object],
    user_query: str,
) -> dict[str, str] | None:
    """Return recovery metadata when verify tool_id/scope contradicts the query."""
    requirement = _verify_requirement_for_query(user_query)
    if requirement is None:
        return None
    allowed_tool_ids = {
        item.strip()
        for item in requirement.get("allowed_tool_ids", requirement["verify_tool_id"]).split(",")
        if item.strip()
    }
    tool_id = str(args_obj.get("tool_id") or "")
    scopes = _verify_scope_entries(args_obj)
    allowed_scopes = {
        item.strip()
        for item in requirement.get("allowed_scopes", requirement["scope"]).split(",")
        if item.strip()
    }
    required_scopes = set(_requirement_scope_entries(requirement))
    expected_tool = requirement["verify_tool_id"]
    expected_scope_list = list(_requirement_scope_entries(requirement))
    purpose_ko = requirement["purpose_ko"]
    purpose_en = requirement["purpose_en"]
    if fname != "check":
        wrong_verify_tool = (
            tool_id == "check"
            or tool_id.startswith("mock_verify_")
            or tool_id in allowed_tool_ids
            or _verify_tool_matches_requirement(
                args_obj,
                allowed_tool_ids=allowed_tool_ids,
                expected_tool=expected_tool,
            )
        )
        if not wrong_verify_tool:
            return None
        return {
            **requirement,
            "message": (
                "Check primitive prerequisite mismatch: the citizen wording maps "
                f"to check tool(s) {sorted(allowed_tool_ids)!r} with scope(s) "
                f"{sorted(allowed_scopes)!r}, but the model emitted {fname}"
                f"(tool_id={tool_id!r}). RECOVERY: call "
                f"check(tool_id={expected_tool!r}, params={{"
                f'"scope_list": {expected_scope_list!r}, '
                f'"purpose_ko": {purpose_ko!r}, '
                f'"purpose_en": {purpose_en!r}'
                "}}). Do NOT call check adapters through find or another primitive."
            ),
        }
    if (
        _verify_tool_matches_requirement(
            args_obj,
            allowed_tool_ids=allowed_tool_ids,
            expected_tool=expected_tool,
        )
        and scopes <= allowed_scopes
        and (required_scopes <= scopes if "required_scopes" in requirement else bool(scopes))
    ):
        return None
    return {
        **requirement,
        "message": (
            "Check tool-choice prerequisite mismatch: the citizen wording maps "
            f"to check tool(s) {sorted(allowed_tool_ids)!r} with scope(s) "
            f"{sorted(allowed_scopes)!r}, but the model emitted tool_id={tool_id!r} "
            f"and scope_list={sorted(scopes)!r}. RECOVERY: call "
            f"check(tool_id={expected_tool!r}, params={{"
            f'"scope_list": {expected_scope_list!r}, '
            f'"purpose_ko": {purpose_ko!r}, '
            f'"purpose_en": {purpose_en!r}'
            "}}). Do NOT substitute another identity family or invent scope names."
        ),
    }


def _verify_scope_list_entries(args_obj: dict[str, object]) -> list[object] | None:
    raw_params = args_obj.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    raw_scope_list = params.get("scope_list", args_obj.get("scope_list"))
    if isinstance(raw_scope_list, list):
        return raw_scope_list
    if isinstance(raw_scope_list, str):
        return [raw_scope_list]
    return None


def _with_verify_scope_list(
    args_obj: dict[str, object],
    scope_list: list[object],
) -> dict[str, object]:
    normalized_args = dict(args_obj)
    raw_params = args_obj.get("params")
    if isinstance(raw_params, dict):
        normalized_params = dict(raw_params)
        normalized_params["scope_list"] = scope_list
        normalized_args["params"] = normalized_params
    else:
        normalized_args["scope_list"] = scope_list
    return normalized_args


def _is_query_bound_non_delegating_scope(
    scope: str,
    *,
    required_scopes: set[str],
) -> bool:
    for required_scope in required_scopes:
        prefixes = _QUERY_BOUND_NON_DELEGATING_SCOPE_PREFIXES.get(required_scope, ())
        if any(scope.startswith(prefix) for prefix in prefixes):
            return True
    return False


def _normalize_query_bound_verify_scope_entries(
    entries: list[object],
    *,
    allowed_scopes: set[str],
    required_scopes: set[str],
) -> tuple[list[object], set[str], list[str], bool]:
    normalized_entries: list[object] = []
    seen_strings: set[str] = set()
    dropped: list[str] = []
    changed = False
    for entry in entries:
        if not isinstance(entry, str):
            normalized_entries.append(entry)
            continue
        stripped = entry.strip()
        if not stripped:
            changed = True
            continue
        normalized = _normalize_verify_scope_entry(stripped)
        if normalized is None:
            dropped.append(stripped)
            changed = True
            continue
        if normalized not in allowed_scopes and (
            normalized in _PRUNABLE_OVERBROAD_VERIFY_SCOPES
            or _is_query_bound_non_delegating_scope(
                normalized,
                required_scopes=required_scopes,
            )
        ):
            dropped.append(normalized)
            changed = True
            continue
        if normalized in seen_strings:
            changed = True
            continue
        normalized_entries.append(normalized)
        seen_strings.add(normalized)
        changed = changed or normalized != stripped
    normalized_scopes = {entry for entry in normalized_entries if isinstance(entry, str)}
    return normalized_entries, normalized_scopes, dropped, changed


def _normalize_verify_args_for_query(
    fname: str,
    args_obj: dict[str, object],
    user_query: str,
) -> dict[str, object]:
    """Normalize known verify scope drift before it reaches citizen-visible UI."""
    if fname != "check":
        return args_obj
    requirement = _verify_requirement_for_query(user_query)
    if requirement is None:
        return args_obj

    entries = _verify_scope_list_entries(args_obj)
    if entries is None:
        if not requirement["scope"].startswith("check:"):
            return args_obj
        normalized = dict(args_obj)
        normalized["tool_id"] = str(normalized.get("tool_id") or requirement["verify_tool_id"])
        raw_params = normalized.get("params")
        params = dict(raw_params) if isinstance(raw_params, dict) else {}
        params["scope_list"] = list(_requirement_scope_entries(requirement))
        params.setdefault("purpose_ko", requirement["purpose_ko"])
        params.setdefault("purpose_en", requirement["purpose_en"])
        normalized["params"] = params
        logger.info(
            "check: filled missing identity scope_list for citizen request (%s)",
            requirement["verify_tool_id"],
        )
        return normalized

    allowed_scopes = {
        item.strip()
        for item in requirement.get("allowed_scopes", requirement["scope"]).split(",")
        if item.strip()
    }
    required_scopes = set(_requirement_scope_entries(requirement))
    normalized_entries, normalized_scopes, dropped, changed = (
        _normalize_query_bound_verify_scope_entries(
            entries,
            allowed_scopes=allowed_scopes,
            required_scopes=required_scopes,
        )
    )
    if not required_scopes <= normalized_scopes:
        return args_obj
    if not changed:
        return args_obj
    if dropped:
        logger.info(
            "check: normalized query-bound scope_list by dropping non-required scope(s): %s",
            ",".join(dropped),
        )
    return _with_verify_scope_list(args_obj, normalized_entries)


def _normalize_verify_tool_id_for_query(
    fname: str,
    args_obj: dict[str, object],
    user_query: str,
) -> dict[str, object]:
    """Canonicalize generic verify tool_id when scope already selects one adapter."""
    if fname != "check":
        return args_obj
    requirement = _verify_requirement_for_query(user_query)
    if requirement is None:
        return args_obj
    tool_id = str(args_obj.get("tool_id") or "")
    if tool_id and tool_id != "check":
        return args_obj
    scopes = _verify_scope_entries(args_obj)
    allowed_scopes = {
        item.strip()
        for item in requirement.get("allowed_scopes", requirement["scope"]).split(",")
        if item.strip()
    }
    required_scopes = set(_requirement_scope_entries(requirement))
    if not (
        scopes <= allowed_scopes
        and (required_scopes <= scopes if "required_scopes" in requirement else bool(scopes))
    ):
        return args_obj
    required_tool_id = requirement["verify_tool_id"]
    logger.info(
        "check: normalized model-emitted tool_id %r -> %r for citizen request",
        tool_id or "<missing>",
        required_tool_id,
    )
    return {**args_obj, "tool_id": required_tool_id}


def _query_implies_location_resolution(user_query: str) -> bool:
    """Return True when a citizen query must canonicalise a place string first."""
    if not user_query:
        return False
    station_tokens: list[str] = []
    for token in re.findall(r"[0-9A-Za-z가-힣]+", user_query):
        if token.endswith("역") and token not in _NON_LOCATION_STATION_SUFFIX_WORDS_KO:
            station_tokens.append(token)
    if station_tokens:
        return True
    location_hints = _LOCATION_RESOLUTION_HINTS_KO - {"역"}
    if any(keyword in user_query for keyword in location_hints):
        return True
    lowered = user_query.lower()
    return any(
        keyword in lowered
        for keyword in ("near", "nearby", "around", "address", "location", "station")
    )


def _maybe_reroute_locate_admin_keyword_args(
    fname: str,
    args_obj: dict[str, Any],
) -> dict[str, Any]:
    """Rewrite admin-area Kakao keyword calls to the documented address adapter."""

    if fname != "locate" or args_obj.get("tool_id") != "kakao_keyword_search":
        return args_obj
    params = args_obj.get("params")
    if not isinstance(params, dict):
        return args_obj
    query = params.get("query")
    if not isinstance(query, str):
        return args_obj

    from ummaya.tools.location_adapters import (  # noqa: PLC0415
        canonical_admin_area_query,
        should_route_keyword_query_to_address,
    )

    if not should_route_keyword_query_to_address(query):
        return args_obj

    next_params = {**params, "query": canonical_admin_area_query(query)}
    logger.info(
        "locate: rerouted Kakao keyword admin-area query to address search: %r",
        query,
    )
    return {**args_obj, "tool_id": "kakao_address_search", "params": next_params}


def _effective_chat_max_tokens(requested: int) -> int:
    """Clamp interactive chat completions so bad tool-routing loops fail fast."""
    raw = os.getenv("UMMAYA_CHAT_MAX_TOKENS")
    cap = _DEFAULT_CHAT_MAX_TOKENS
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            parsed = cap
        cap = min(32000, max(512, parsed))
    return min(requested, cap)


def _location_independent_resolve_redirect_for_query(
    fname: str,
    user_query: str,
) -> dict[str, str] | None:
    """Return the next primitive when locate is irrelevant."""
    if fname != "locate":
        return None
    if _query_implies_location_resolution(user_query):
        return None
    if not _query_contains_any(user_query, tuple(_LOCATION_INDEPENDENT_WORKFLOW_HINTS_KO)):
        return None

    if _query_contains_any(
        user_query,
        ("증명서 목록", "발급 가능한 증명서", "발급가능한 증명서"),
    ):
        return {"primitive": "free", "tool_id": ""}

    submit_requirement = _submit_requirement_for_query(user_query)
    if submit_requirement is not None:
        return {
            "primitive": "check",
            "tool_id": submit_requirement["verify_tool_id"],
        }

    sensitive_lookup = _sensitive_lookup_requirement_for_query(user_query)
    if sensitive_lookup is not None:
        return {
            "primitive": "check",
            "tool_id": sensitive_lookup["verify_tool_id"],
        }

    if _query_contains_any(
        user_query,
        ("간편인증", "모바일신분증", "모바일 id", "mobile id", "마이데이터"),
    ):
        verify_requirement = _verify_requirement_for_query(user_query)
        if verify_requirement is not None:
            return {
                "primitive": "check",
                "tool_id": verify_requirement["verify_tool_id"],
            }

    return {"primitive": "free", "tool_id": ""}


def _check_location_terminated_without_resolve(
    llm_messages: list[Any],
    user_query: str,
) -> str | None:
    """Return recovery text when a location-like request would end without resolve."""
    if not _query_implies_location_resolution(user_query):
        return None
    if _conversation_has_tool_call(llm_messages, "locate"):
        return None
    return (
        "Location resolution prerequisite missing: the citizen supplied a place, "
        "address, station, or nearby-search request, but this turn is about to "
        "answer without invoking locate. RECOVERY: in the next turn call "
        "locate(tool_id='kakao_keyword_search', params={'query': "
        "<citizen supplied place/address text>}) for a place/POI/station, or "
        "locate(tool_id='kakao_address_search', params={'query': "
        "<citizen supplied address text>}) for a structured road/jibun address, "
        "even when the text looks fake or incomplete. "
        "Only report not_found / 유효한 위치 없음 after the resolver returns it; "
        "do NOT invent coordinates."
    )


async def _reader_loop(
    stream: asyncio.StreamReader,
    on_frame: Callable[[IPCFrame], Any],
    session_id: str,
) -> None:
    """Read newline-delimited JSON frames from *stream* and dispatch them.

    Malformed lines are logged at ERROR and an ``error`` frame is sent back
    rather than crashing the loop (data-model.md § 1.4).
    """
    background_tasks: set[asyncio.Task[None]] = set()
    cancelled = False
    try:
        while True:
            try:
                line = await stream.readline()
            except (asyncio.IncompleteReadError, ConnectionResetError):
                logger.debug("stdin EOF or connection reset — stopping reader loop")
                break

            if not line:
                logger.debug("stdin EOF — stopping reader loop")
                break

            raw = line.decode("utf-8", errors="replace").strip()
            if not raw:
                continue  # skip blank lines

            try:
                frame = _frame_adapter.validate_json(raw)
            except (ValidationError, ValueError) as exc:
                logger.error("IPC decode error: %s | raw=%r", exc, raw[:200])
                await _write_decode_error(raw, session_id)
                continue

            if frame.kind in _BACKGROUND_FRAME_KINDS:
                _track_background_dispatch(frame, on_frame, background_tasks)
            else:
                await _dispatch_inbound_frame(frame, on_frame)
    except asyncio.CancelledError:
        cancelled = True
        await _drain_background_tasks(background_tasks, cancel=True)
        raise
    finally:
        if not cancelled:
            await _drain_background_tasks(background_tasks, cancel=False)


# ---------------------------------------------------------------------------
# Shutdown helpers
# ---------------------------------------------------------------------------


# Coordinate / admin-code field names that signal a downstream tool needs
# locate to have run first (Epic #2766 chain prerequisite gate).
# The literal field set is intentionally broader than what any single
# adapter accepts so the gate catches every variant the LLM might pick.
_COORD_INPUT_FIELDS: frozenset[str] = frozenset(
    {
        "xPos",
        "yPos",
        "lat",
        "lon",
        "latitude",
        "longitude",
        "origin_lat",
        "origin_lon",
        "nx",
        "ny",
        "x",
        "y",
    }
)
_ADMCD_INPUT_FIELDS: frozenset[str] = frozenset(
    {
        "adm_cd",
        "siGunGuCd",
        "sgg_cd",
        "h_code",
        "b_code",
    }
)


def _check_chain_prerequisite(  # noqa: C901
    fname: str,
    args_obj: dict[str, object],
    llm_messages: list[Any],
    registry: Any = None,
) -> str | None:
    """Return chain-recovery error message when a prerequisite is missing.

    CC reference: ``Tool.validateInput?(input, context)`` in
    ``.references/claude-code-sourcemap/restored-src/src/Tool.ts:489``.
    The CC hook is tool-scoped; UMMAYA centralises the equivalent
    pre-dispatch check here because every coord-input adapter has the
    identical prerequisite (locate must have been called in
    a prior turn of the same conversation). Adapter-scoped overrides can
    be added later by extending this function to dispatch on tool_id.

    Returns ``None`` when the call is allowed; returns a descriptive
    error message when the call should be rejected. The caller emits
    that message verbatim to the LLM via a tool_result envelope so the
    next agentic-loop turn can recover.
    """
    # Only the `find` primitive carries adapter calls (fetch-only
    # routes to a registered GovAPITool). All other primitives are
    # either coord-free (verify) or carry their own param schema
    # (submit, locate).
    if fname != "find":
        return None
    if not isinstance(args_obj, dict):
        return None
    # Accept both shapes the LLM emits: full {mode:'fetch', tool_id, params}
    # AND the abbreviated {tool_id, params} where mode is implicit. K-EXAONE
    # frequently omits mode when tool_id is set; treating those as fetch
    # closes the bypass that lets a tool_id=hira_* call slip past the gate
    # just because mode was unset.
    mode = args_obj.get("mode")
    tool_id = args_obj.get("tool_id")
    if mode not in (None, "fetch"):
        return None
    if not isinstance(tool_id, str) or not tool_id:
        return None
    params_obj = args_obj.get("params")
    params: dict[str, object] = params_obj if isinstance(params_obj, dict) else {}

    # Recognise coord-input adapter calls only when the model actually
    # supplied coordinate/admcd fields. Empty or coord-free params are left
    # to the adapter-level schema/validator so the primitive does not
    # pre-interpret arbitrary tool_ids before dispatch.
    has_coord = any(k in params for k in _COORD_INPUT_FIELDS)
    has_admcd = any(k in params for k in _ADMCD_INPUT_FIELDS)
    schema_coord_fields: set[str] = set()
    schema_admcd_fields: set[str] = set()
    schema_required_fields: set[str] = set()
    if registry is not None:
        try:
            tool = registry.find(tool_id)
            schema = tool.input_schema.model_json_schema()
            props = schema.get("properties", {})
            schema_coord_fields = set(props) & _COORD_INPUT_FIELDS
            schema_admcd_fields = set(props) & _ADMCD_INPUT_FIELDS
            required = schema.get("required", [])
            if isinstance(required, list):
                schema_required_fields = {str(field) for field in required}
        except Exception as exc:  # noqa: BLE001
            # Unknown tool / registry not booted — let the dispatcher
            # produce its own unknown_tool error instead of guessing.
            logger.debug("find prerequisite schema lookup skipped for %s: %s", tool_id, exc)
    if not (has_coord or has_admcd):
        return None

    has_prior_resolve = _conversation_has_successful_primitive_any_tool(
        llm_messages,
        primitive="locate",
    )
    if tool_id == "nmc_emergency_search":
        has_region_params = (
            params.get("mode") == "region"
            and isinstance(params.get("q0"), str)
            and bool(str(params.get("q0")).strip())
            and isinstance(params.get("q1"), str)
            and bool(str(params.get("q1")).strip())
        )
        if has_prior_resolve and has_region_params:
            return None
        if has_prior_resolve:
            return (
                "NMC operation prerequisite missing: citizen place-name ER search must use "
                "the official getEgytListInfoInqire region operation, not the coordinate "
                "operation. The prior locate call did not provide the q0/q1 "
                "region-mode parameters used by NMC. RECOVERY: call "
                "locate(tool_id='kakao_coord_to_region', "
                "params={lat:<prior_lat>, lon:<prior_lon>}), then call "
                "find(tool_id='nmc_emergency_search', "
                "params={mode:'region', q0:region.region_1depth_name, "
                "q1:region.region_2depth_name, origin_lat:coords.lat, "
                "origin_lon:coords.lon, limit:<N>}). Do NOT retry coordinate mode for "
                "station/neighborhood ER search and do NOT invent NMC filters such as QZ."
            )

    # Require a successful prior locate for this context. If resolve
    # fails (e.g. ``not_found``), find still requires recovery and should not
    # be treated as fulfilled chain state.
    if _conversation_has_successful_primitive_any_tool(
        llm_messages,
        primitive="locate",
    ):
        missing_required_fields = sorted(
            field for field in schema_required_fields if params.get(field) in (None, "")
        )
        if missing_required_fields:
            return (
                "Chain parameter transfer missing: a prior locate call succeeded, "
                "but the current find call omitted required adapter params "
                f"{missing_required_fields!r}. RECOVERY: re-invoke "
                f"find(tool_id={tool_id!r}) with params copied from the latest locate "
                "tool_result. For KMA adapters, use the displayed KMA grid nx/ny "
                "values exactly and fill base_date/base_time from the current KST "
                "context in the tool schema. Do NOT call the adapter with empty params "
                "and do NOT guess location values from prior knowledge."
            )
        return None

    # Field naming: prefer the actually-supplied params (the LLM tipped its
    # hand on which fields it tried to fill), otherwise fall back to the
    # schema-introspected field set so the recovery message names something
    # the LLM can actually produce.
    missing_coord = (set(params.keys()) & _COORD_INPUT_FIELDS) or schema_coord_fields
    missing_admcd = (set(params.keys()) & _ADMCD_INPUT_FIELDS) or schema_admcd_fields
    missing_fields = sorted(missing_coord | missing_admcd)
    if tool_id == "nmc_emergency_search":
        return (
            "Chain prerequisite missing: nmc_emergency_search models two official NMC "
            "operations and must receive location fields from locate in the "
            "same conversation. No locate turn precedes the current call. "
            "RECOVERY: in the next turn call a coordinate-producing locate adapter "
            "such as locate(tool_id='kakao_keyword_search', params={query:'<지역명>'}), "
            "then locate(tool_id='kakao_coord_to_region', params={lat:<lat>, lon:<lon>}), "
            "then call find(tool_id='nmc_emergency_search', "
            "params={mode:'region', q0:region.region_1depth_name, "
            "q1:region.region_2depth_name, origin_lat:coords.lat, origin_lon:coords.lon, "
            "limit:<N>}). Do NOT guess coordinates or set NMC filters such as QZ unless "
            "the citizen explicitly supplied them."
        )
    if has_coord or schema_coord_fields:
        field_kind = "coordinates"
    elif has_admcd or schema_admcd_fields:
        field_kind = "administrative code"
    else:
        field_kind = "location parameters"
    return (
        f"Chain prerequisite missing: this tool requires {field_kind} "
        f"({', '.join(missing_fields) if missing_fields else 'see input schema'}) "
        f"that MUST come from a prior locate call in the same "
        f"conversation. No locate turn precedes the current call — "
        f"that means the values would be guessed from prior knowledge instead "
        f"of being resolved against Kakao Local API. "
        f"RECOVERY: in the next turn call a coordinate-producing locate adapter "
        f"such as locate(tool_id='kakao_keyword_search', params={{query:'<지역명>'}}) "
        f"to obtain the canonical lat/lon for the citizen's location, then "
        f"re-invoke this tool with the returned values. Do NOT "
        f"guess coordinates."
    )


_CURRENT_WEATHER_KEYWORDS_KO: frozenset[str] = frozenset(
    {"날씨", "기온", "온도", "습도", "강수", "바람", "풍속"}
)
_CURRENT_WEATHER_PRECIP_KO_RE: Final = re.compile(
    r"(?<![가-힣])(?:비|눈)(?:\s*(?:가|는|도|와|오|올|오는|올지|올까|내리|내릴|예보|소식)|$)"
)
_CURRENT_WEATHER_KEYWORDS_EN: frozenset[str] = frozenset(
    {"weather", "temperature", "humidity", "rainfall", "rain", "snow", "wind"}
)
_CURRENT_TIME_HINTS_KO: frozenset[str] = frozenset(
    {"오늘", "현재", "지금", "실시간", "현시각", "요즘"}
)
_CURRENT_TIME_HINTS_EN: frozenset[str] = frozenset({"today", "current", "now", "live"})
_FUTURE_TIME_HINTS_KO: frozenset[str] = frozenset(
    {"내일", "모레", "글피", "주말", "다음주", "다음 주", "이번 주말"}
)
_FUTURE_TIME_HINTS_EN: frozenset[str] = frozenset({"tomorrow", "weekend", "next week", "forecast"})

_AVAILABLE_ADAPTER_FIND_LINE_RE: Final = re.compile(
    r"^\s*-\s+[A-Za-z0-9_.:-]+\s+\(primitive=find\)",
    re.MULTILINE,
)


def _latest_available_adapters_block(llm_messages: list[Any]) -> str:
    """Return the latest dynamic ``<available_adapters>`` block in context."""
    for message in reversed(llm_messages):
        role = getattr(message, "role", None) or (
            message.get("role") if isinstance(message, dict) else None
        )
        if role != "system":
            continue
        content = getattr(message, "content", None) or (
            message.get("content") if isinstance(message, dict) else None
        )
        if not isinstance(content, str) or "<available_adapters" not in content:
            continue
        start = content.rfind("<available_adapters")
        end = content.find("</available_adapters>", start)
        if start >= 0 and end >= 0:
            return content[start : end + len("</available_adapters>")]
    return ""


def _available_adapters_block_has_find_candidate(block: str) -> bool:
    """Return True when retrieval surfaced a non-locate follow-up adapter."""
    return bool(block and _AVAILABLE_ADAPTER_FIND_LINE_RE.search(block))


def _query_implies_current_weather_observation(user_query: str) -> bool:
    """Return True when final weather prose should include current observation."""
    if not user_query:
        return False
    q = user_query.lower()
    has_weather = (
        any(kw in user_query for kw in _CURRENT_WEATHER_KEYWORDS_KO)
        or _CURRENT_WEATHER_PRECIP_KO_RE.search(user_query) is not None
        or any(kw in q for kw in _CURRENT_WEATHER_KEYWORDS_EN)
    )
    if not has_weather:
        return False
    if any(kw in user_query for kw in _CURRENT_TIME_HINTS_KO) or any(
        kw in q for kw in _CURRENT_TIME_HINTS_EN
    ):
        return True
    # Bare "<장소명> 날씨 알려줘" is normally asking for current/today weather.
    return not (
        any(kw in user_query for kw in _FUTURE_TIME_HINTS_KO)
        or any(kw in q for kw in _FUTURE_TIME_HINTS_EN)
    )


def _check_current_weather_terminated_without_observation(
    llm_messages: list[Any],
    user_query: str,
) -> str | None:
    """Require KMA current observation before final current/today weather prose."""
    if not _query_implies_current_weather_observation(user_query):
        return None
    if _conversation_has_primitive_call(
        llm_messages,
        primitive="find",
        tool_id="kma_current_observation",
    ):
        return None
    if not _conversation_has_successful_primitive_any_tool(
        llm_messages,
        primitive="locate",
    ):
        return None
    return (
        "Current weather observation missing: the citizen asked for current/today "
        "weather, but the conversation is about to answer without calling "
        "find(tool_id='kma_current_observation'). RECOVERY: call "
        "find(tool_id='kma_current_observation', params={base_date:<current KST "
        "YYYYMMDD>, base_time:<current or prior HH00>, nx:<latest locate KMA X>, "
        "ny:<latest locate KMA Y>}) using the latest locate result. Do NOT claim "
        "that live/current observation data is unavailable unless this adapter was "
        "called and returned an error."
    )


def _weather_value_tokens(value: object) -> set[str]:
    """Return compact numeric strings a final weather answer may cite."""
    if isinstance(value, bool):
        return set()
    if isinstance(value, int):
        return {str(value)}
    if isinstance(value, float):
        tokens = {f"{value:g}"}
        rounded = round(value)
        if abs(value - rounded) < 0.25:
            tokens.add(str(rounded))
        return tokens
    return set()


def _final_answer_missing_current_weather_observation_values(
    text: str,
    llm_messages: list[Any],
    user_query: str,
) -> bool:
    """Return true when a current-weather answer omits successful KMA values."""
    if not _query_implies_current_weather_observation(user_query):
        return False
    result = _latest_successful_primitive_result_for_tool(
        llm_messages,
        primitive="find",
        tool_id="kma_current_observation",
    )
    if result is None:
        return False
    item = result.get("item")
    if not isinstance(item, dict):
        return False
    tokens: set[str] = set()
    for key in ("t1h", "rn1", "reh", "wsd"):
        tokens.update(_weather_value_tokens(item.get(key)))
    if not tokens:
        return False
    normalized = " ".join(text.strip().split())
    if not normalized:
        return True
    return not any(token in normalized for token in tokens)


def _check_resolve_terminated_without_followup(  # noqa: C901
    llm_messages: list[Any],
    user_query: str,
) -> str | None:
    """Return chain-recovery error message when the LLM is about to terminate
    a turn without invoking a follow-up ``find`` after ``locate``.

    Triggers when ALL of the following hold:
    1. The conversation contains at least one assistant turn that called
       ``locate`` AND the corresponding ``role='tool'`` result.
    2. The conversation contains NO assistant turn that called ``find``
       (fetch-only; ``{tool_id, params}``) on a coord/admcd-input adapter.
    3. The per-turn dynamic ``<available_adapters>`` block, produced by the
       registry retriever for the exact citizen query, contains at least one
       ``primitive=find`` candidate.

    Returns ``None`` when the call is allowed; returns a descriptive
    error message that the caller injects as a synthetic tool_result so the
    next agentic-loop turn produces the missing ``find`` call.

    CC reference parallel: ``Tool.validateInput`` rejection on missing
    prerequisite. The UMMAYA port runs at the *terminal-turn* boundary
    (``if not tool_call_buf:``) because the failure mode here is the inverse
    of the ``_check_chain_prerequisite`` pattern — instead of "called
    coord-input tool too early", this is "stopped after resolve and never
    called the coord-input tool at all".
    """
    available_adapters_block = _latest_available_adapters_block(llm_messages)
    if not _available_adapters_block_has_find_candidate(available_adapters_block):
        return None

    resolve_succeeded = False
    saw_followup_lookup = False
    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        # Detect locate tool result message
        if role == "tool":
            name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)
            if name == "locate":
                resolve_payload = _tool_result_payload_for_primitive(
                    m,
                    primitive="locate",
                )
                resolve_succeeded = bool(resolve_payload) and _primitive_payload_is_success(
                    resolve_payload,
                    primitive="locate",
                )
            continue
        if role != "assistant":
            continue
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if not tool_calls:
            continue
        for tc in tool_calls:
            call_fn = getattr(getattr(tc, "function", None), "name", None) or (
                tc.get("function", {}).get("name") if isinstance(tc, dict) else None
            )
            if call_fn != "find":
                continue
            # Inspect arguments to confirm fetch-mode against an adapter.
            raw_args = getattr(getattr(tc, "function", None), "arguments", None) or (
                tc.get("function", {}).get("arguments") if isinstance(tc, dict) else None
            )
            if isinstance(raw_args, str):
                try:
                    import json as _j  # noqa: PLC0415

                    parsed_args: object = _j.loads(raw_args)
                except Exception:  # noqa: BLE001
                    parsed_args = {}
            else:
                parsed_args = raw_args or {}
            if not isinstance(parsed_args, dict):
                continue
            mode = parsed_args.get("mode")
            tool_id = parsed_args.get("tool_id")
            if mode in (None, "fetch") and isinstance(tool_id, str) and tool_id:
                saw_followup_lookup = True
                break
        if saw_followup_lookup:
            break

    if not resolve_succeeded:
        return None
    if saw_followup_lookup:
        return None
    return (
        "Chain incomplete: this conversation invoked locate but did NOT "
        "follow up with find(tool_id=<adapter>, params={...}) on "
        "any adapter even though the dynamic <available_adapters> block for "
        "this citizen query includes find candidates. Coordinates alone are "
        "not the requested public-service answer when a registry-selected "
        "find adapter is available; treating them as a final answer is a "
        "fabrication risk. RECOVERY: in the next turn, choose the correct "
        "adapter from the <available_adapters> block and call "
        "find(tool_id='<adapter>', params={lat: <resolved>, "
        "lon: <resolved>, ...}) using the coordinates returned by the prior "
        "locate turn. Do NOT produce a final answer this turn."
    )


def _utcnow() -> str:
    """Return current UTC time as RFC 3339 string."""
    from datetime import datetime

    return (
        datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.")
        + f"{datetime.now(tz=UTC).microsecond // 1000:03d}Z"
    )


async def _emit_exit_frame(session_id: str) -> None:
    """Write a ``session_event {event='exit'}`` frame and flush stdout."""
    exit_frame = SessionEventFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="backend",
        ts=_utcnow(),
        kind="session_event",
        event="exit",
        payload={},
    )
    await write_frame(exit_frame)
    logger.debug("Emitted session_event exit frame")


# ---------------------------------------------------------------------------
# Session-event dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_session_event(
    event: str,
    payload: dict[str, Any],
    session_id: str,
    sm: SessionManager,
    shutdown: asyncio.Event,
    correlation_id: str,
) -> None:
    """Route a ``session_event`` frame to the appropriate :class:`SessionManager` method.

    This helper is intentionally kept free of any ``try/except`` so that the
    caller (``_handle_frame``) can catch errors uniformly and emit an
    ``ErrorFrame`` back to the TUI (FR-010 resilience rule).

    Parameters
    ----------
    event:
        One of ``save | load | list | resume | new | exit``.
    payload:
        Event-specific payload dict from the inbound frame.
    session_id:
        The ``session_id`` carried on the inbound frame — used for reply frames.
    sm:
        Active :class:`~ummaya.session.manager.SessionManager` instance.
    shutdown:
        Event that signals the stdio loop to exit when set.
    """
    from ummaya.session.store import list_sessions as _list_sessions

    if event == "new":
        meta = await sm.new_session()
        reply = SessionEventFrame(
            session_id=meta.session_id,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="session_event",
            event="new",
            payload={"session_id": meta.session_id},
        )
        await write_frame(reply)
        logger.debug("session_event new — created session %s", meta.session_id)

    elif event == "save":
        # save_turn is called by the tool-loop per-turn; /save is a checkpoint
        # command.  Emit an ack so the TUI can update its status bar.
        active_sid = sm.session_id or session_id
        reply = SessionEventFrame(
            session_id=active_sid,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="session_event",
            event="save",
            payload={"session_id": active_sid},
        )
        await write_frame(reply)
        logger.debug("session_event save — ack for session %s", active_sid)

    elif event == "list":
        metas = await _list_sessions(session_dir=sm._session_dir)  # noqa: SLF001
        sessions_payload = [
            {
                "id": m.session_id,
                "created_at": m.created_at.isoformat(),
                "turn_count": m.message_count // 2,
            }
            for m in metas
        ]
        active_sid = sm.session_id or session_id
        reply = SessionEventFrame(
            session_id=active_sid,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="session_event",
            event="list",
            payload={"sessions": sessions_payload},
        )
        await write_frame(reply)
        logger.debug("session_event list — returned %d sessions", len(sessions_payload))

    elif event == "resume":
        target_id: str = payload["id"]
        messages = await sm.resume_session(target_id)
        reply = SessionEventFrame(
            session_id=target_id,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="session_event",
            event="load",
            payload={
                "session_id": target_id,
                "messages": [msg.model_dump(mode="json") for msg in messages],
            },
        )
        await write_frame(reply)
        logger.debug(
            "session_event resume — loaded session %s (%d messages)",
            target_id,
            len(messages),
        )

    elif event == "load":
        # load is backend → TUI only; reject TUI → backend direction.
        err = ErrorFrame(
            session_id=session_id,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="error",
            code="invalid_direction",
            message="session_event 'load' is a backend-to-TUI frame; TUI must use 'resume'",
            details={"event": event},
        )
        await write_frame(err)
        logger.warning("session_event load received from TUI — rejected (invalid direction)")

    elif event == "exit":
        logger.debug("session_event exit — setting shutdown flag")
        shutdown.set()

    else:
        # Forward-compatible: unknown events are logged and dropped.
        logger.warning("Unknown session_event: %r", event)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run(  # noqa: C901
    session_id: str | None = None,
    on_frame: Callable[[IPCFrame], Any] | None = None,
    session_manager: SessionManager | None = None,
) -> None:
    """Run the asyncio JSONL stdio loop until stdin closes or a signal arrives.

    Parameters
    ----------
    session_id:
        Session ULID shared with the TUI.  If omitted a random placeholder is
        used (suitable for smoke tests).
    on_frame:
        Callable invoked for every inbound ``IPCFrame``.  May be a coroutine
        function.  Defaults to the built-in ``_handle_frame`` handler that
        echoes ``user_input`` frames and routes ``session_event`` frames to the
        session manager.
    session_manager:
        :class:`~ummaya.session.manager.SessionManager` instance used by the
        default ``_handle_frame`` handler to implement session lifecycle
        operations.  When ``None`` a default ``SessionManager()`` is
        constructed (uses ``~/.ummaya/sessions``).
    """
    from ummaya.session.manager import SessionManager as _SessionManager

    sid = session_id or str(uuid.uuid4())

    # ---- spec-multi-turn-contamination diagnostic — optional log file
    # The TUI bridge spawns this process with `stderr: 'pipe'` and never
    # drains the pipe, so `logger.info(...)` lines are invisible to any
    # external observer (tmux pane, asciinema cast). When the operator
    # sets UMMAYA_BACKEND_LOG_FILE=<path>, attach a FileHandler at INFO
    # so the diagnostic [CHAT_REQUEST_DUMP] / [LATEST_USER_UTT] /
    # [REASONING_PREVIEW] lines persist to disk for post-hoc analysis.
    # Off by default — production behaviour is unchanged when the env
    # var is unset.
    _log_path = os.getenv("UMMAYA_BACKEND_LOG_FILE")
    if _log_path:
        try:
            _root = logging.getLogger()
            _already = any(
                isinstance(h, logging.FileHandler)
                and getattr(h, "baseFilename", "") == os.path.abspath(_log_path)
                for h in _root.handlers
            )
            if not _already:
                _fh = logging.FileHandler(_log_path, mode="a", encoding="utf-8")
                _fh.setLevel(logging.INFO)
                _fh.setFormatter(
                    logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
                )
                _root.addHandler(_fh)
                _root.setLevel(min(_root.level or logging.INFO, logging.INFO))
                logger.info(
                    "spec-multi-turn-contamination: attached FileHandler -> %s",
                    _log_path,
                )
        except Exception:  # noqa: BLE001 — telemetry must never raise
            sys.stderr.write(f"[UMMAYA BACKEND] failed to attach log file {_log_path}\n")

    logger.info("IPC stdio loop starting — session_id=%s", sid)

    # Resolve session manager; always non-None inside this coroutine.
    _sm: _SessionManager = session_manager if session_manager is not None else _SessionManager()

    # Install shutdown flag
    _shutdown = asyncio.Event()

    def _handle_signal(signum: int, _frame: FrameType | None = None) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received signal %s — initiating graceful shutdown", sig_name)
        _shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, int(sig))
        except (ValueError, NotImplementedError):
            # Windows or restricted environments — fall back to signal.signal
            signal.signal(sig, _handle_signal)

    # Connect asyncio StreamReader to sys.stdin.buffer.
    #
    # macOS / kqueue fix (Fix Strategy 2 — thread-based bypass):
    #
    # When the backend is spawned as a child process by Bun.spawn
    # (tui/src/ipc/bridge.ts) with stdin: 'pipe', Python's
    # asyncio.SelectorEventLoop on macOS uses kqueue.  kqueue raises
    # OSError: [Errno 22] Invalid argument (EINVAL) when
    # connect_read_pipe attempts to register a pipe fd via kqueue.control().
    # This happens even after setting O_NONBLOCK on the dup'd fd because
    # the fd type (anonymous pipe) is not accepted by kqueue on macOS 15+
    # (Darwin 25).  The same error also manifests when stdin is a tty.
    #
    # Fix: run a blocking sys.stdin.buffer.readline() loop inside a thread
    # (via loop.run_in_executor with None = default ThreadPoolExecutor),
    # push each line directly into a StreamReader via feed_data()/feed_eof().
    # This bypasses connect_read_pipe entirely so kqueue never sees the fd.
    # On Linux (epoll-based asyncio) connect_read_pipe works fine; we still
    # use the thread path there for portability since run_in_executor has
    # negligible overhead compared to inter-process pipe I/O.
    #
    # Unit-test compatibility: the in-process harness (tests/ipc/test_stdio.py,
    # _run_with_frame) wraps an os.pipe() read-end as sys.stdin.buffer.
    # The thread reads from the same buffer object, so the test payload arrives
    # via the same readline() path — no change needed in the tests.
    # UMMAYA Epic #2077 — limit=16 MiB. The default asyncio.StreamReader limit
    # is 64 KiB (asyncio.streams._DEFAULT_LIMIT), which is too small once the
    # TUI's ChatRequestFrame includes the full 11-tool catalog (~13 KB JSON)
    # plus accumulated message history across agentic-loop turns. A single
    # ``\n``-terminated line easily exceeds 64 KiB after 3-5 turns, causing
    # ``readline()`` to raise ``ValueError('Separator is found, but chunk is
    # longer than limit')`` and the IPC reader loop to silently die — the
    # TUI then waits forever for assistant_chunk frames that never come.
    # 16 MiB matches the K-EXAONE 1M-token context budget in bytes (1M tokens
    # × ~1.5 byte/token UTF-8 average × 10× safety margin).
    stdin_reader = asyncio.StreamReader(limit=16 * 1024 * 1024)
    _stdin_buf_capture = sys.stdin.buffer  # capture now; monkeypatching may change sys.stdin

    async def _stdin_feed_task() -> None:
        """Read stdin synchronously in a thread executor; push lines into stdin_reader.

        Thread loop: blocks on readline() until EOF, then feeds EOF to the
        StreamReader so _reader_loop terminates naturally.  Any OSError or
        ValueError (e.g. closed file during shutdown) also terminates the loop.

        On task cancellation (signalled by the outer shutdown coordinator at
        :func:`run`'s ``asyncio.wait`` boundary), the in-flight ``readline()``
        executor Future is cancelled so the awaiting coroutine returns and
        ``stdin_reader.feed_eof()`` runs in ``finally`` (Codex P1, PR #2111).
        The blocked worker thread itself does not exit — Python cannot kill
        threads — but Python's default-executor shutdown path on
        ``asyncio.run()`` exit is bounded by ``shutdown_default_executor``'s
        timeout, so the interpreter still terminates.
        """
        loop_inner = asyncio.get_running_loop()
        try:
            while True:
                line: bytes = await loop_inner.run_in_executor(None, _stdin_buf_capture.readline)
                if not line:
                    break
                stdin_reader.feed_data(line)
        except (OSError, ValueError, asyncio.CancelledError):
            pass
        finally:
            stdin_reader.feed_eof()

    _stdin_feed_handle = asyncio.create_task(_stdin_feed_task(), name="ipc-stdin-feed")

    # Default on_frame: route `user_input` to the FriendliAI LLM (Epic #1633
    # FR-007/FR-017) and `session_event` to the session manager. Wraps every
    # handler in try/except so malformed payloads never crash the loop
    # (FR-010).
    #
    # Per-session conversation history is kept in `_llm_sessions` below; each
    # user_input appends one message, the model's reply is appended as
    # assistant, and subsequent turns see the full history. System prompt is
    # loaded lazily from Spec 026 PromptLoader on first turn.
    _llm_sessions: dict[str, list[dict[str, object]]] = {}
    _llm_client_ref: list[object] = []  # holds the singleton LLMClient
    _llm_system_prompt_cached: list[str | None] = [None]

    # Spec 1978 T026 — pending tool calls registry per data-model.md D1.
    # Keyed by call_id (ULID emitted in ToolCallFrame), valued by an asyncio
    # Future that resolves when the matching ToolResultFrame arrives.
    _pending_calls: dict[str, asyncio.Future[Any]] = {}

    # Spec 1978 T043-T049 — pending permission requests (D2 invariant).
    # Keyed by request_id (UUID4), resolved when the TUI sends a
    # permission_response frame with the matching request_id.
    # Timeout = 60s; synthetic deny on expiry.
    _pending_perms: dict[str, asyncio.Future[Any]] = {}

    # Per-session auto-approved tool IDs (allow_session grants).
    # Keyed by session_id → set of tool_ids approved for the session lifetime.
    _session_grants: dict[str, set[str]] = {}

    # Latest successful verify AuthContext per session. Submit dispatch uses
    # this backend-owned object for SC-005 tier checks instead of trusting the
    # LLM to reconstruct auth_context from a prior tool result.
    _session_auth_contexts: dict[str, object] = {}
    _session_auth_session_ids: dict[str, str] = {}

    # Epic #2077 T010 — single ToolRegistry + ToolExecutor instance pair
    # reused across every chat_request. Adapter registration happens lazily
    # on first access by invoking ``register_all_tools(registry, executor)``
    # exactly once (Spec 1634); per-turn reconstruction would force every
    # adapter ``register()`` call to re-execute and would also rebuild BM25
    # for no observable gain. The list-of-one indirection mirrors the
    # ``_llm_client_ref`` pattern above so the closure-bound name binding
    # survives reassignment under typing strictness.
    #
    # Bug fix (2026-05-01, citizen "부산 날씨" report):  the previous
    # implementation created an empty ``ToolRegistry()`` here AND another
    # empty pair inside ``_dispatch_primitive`` for every lookup call, so
    # ``lookup(mode="search", ...)`` always returned ``reason="empty_registry"``
    # and ``mode="fetch"`` always failed with ``unknown_tool``. The comment
    # claimed registration happened "via register_all side-effects" but no
    # such side-effects exist — registration is a function call, not a
    # module-level statement. This pair is now the single source of truth
    # for *all* dispatcher paths (search/fetch/export_core_tools_openai).
    _tool_registry_ref: list[ToolRegistry] = []
    _tool_executor_ref: list[ToolExecutor] = []

    def _ensure_tool_registry() -> ToolRegistry:
        # CC reference: (no direct CC analog — UMMAYA-only IPC adaptation).
        # CC's QueryEngine.ts assumes ToolRegistry populated at SDK construction
        # time (Anthropic SDK ``new Anthropic({...}).messages.stream(...)`` has
        # the registry baked in). UMMAYA's stdio JSONL backend is invoked once
        # per process, ahead of any chat_request, so registration must be lazy
        # to avoid bootstrapping cost when the user runs ``ummaya --list-sessions``
        # or other non-LLM commands. Justified as SWAP/llm-provider per
        # parity-matrix.md § 2026-05-01.
        if not _tool_registry_ref:
            from ummaya.tools.executor import ToolExecutor  # noqa: PLC0415
            from ummaya.tools.register_all import register_all_tools  # noqa: PLC0415
            from ummaya.tools.registry import ToolRegistry  # noqa: PLC0415

            registry = ToolRegistry()
            executor = ToolExecutor(registry=registry)
            register_all_tools(registry, executor)
            # Cache only after full success — a partial registration leaves
            # the registry in a mixed state, so let the exception propagate
            # and a subsequent call retry from scratch.
            _tool_registry_ref.append(registry)
            _tool_executor_ref.append(executor)

            # SWAP/llm-provider(2521): emit AdapterManifestSyncFrame to the
            # TUI so the frontend's LookupPrimitive.validateInput can resolve
            # tool_ids. Without this frame, isManifestSynced() stays false
            # and every lookup(mode="fetch") returns "Adapter manifest not
            # yet synced from backend" — the LLM then retries lookup
            # endlessly while fabricating answers from BM25 search candidates
            # (citizen-traced 2026-05-01: fake hourly-temperature tables).
            # emit_manifest() writes the JSONL frame directly to sys.stdout,
            # bypassing the asyncio write_frame helper because lazy init runs
            # outside the event loop's task graph.
            try:
                import sys as _sys  # noqa: PLC0415

                from ummaya.ipc.adapter_manifest_emitter import (  # noqa: PLC0415
                    emit_manifest,
                )

                emit_manifest(_sys.stdout, registry)
                logger.info("Emitted AdapterManifestSyncFrame to TUI")
            except Exception as _exc:
                logger.exception("Failed to emit adapter manifest: %s", _exc)
        return _tool_registry_ref[0]

    def _ensure_tool_executor() -> ToolExecutor:
        """Return the ToolExecutor paired with the singleton ToolRegistry.

        Triggers lazy registration if neither has been built yet so callers
        that need only the executor stay correct without taking a registry
        reference first.
        """
        if not _tool_executor_ref:
            _ensure_tool_registry()  # populates both refs in one shot
        return _tool_executor_ref[0]

    async def _ensure_llm_client() -> object:
        if not _llm_client_ref:
            from ummaya.llm.client import LLMClient  # noqa: PLC0415
            from ummaya.llm.config import LLMClientConfig  # noqa: PLC0415

            cfg = LLMClientConfig()
            _llm_client_ref.append(LLMClient(config=cfg))
        return _llm_client_ref[0]

    async def _ensure_system_prompt() -> str | None:
        if _llm_system_prompt_cached[0] is not None:
            return _llm_system_prompt_cached[0] or None
        try:
            from pathlib import Path  # noqa: PLC0415

            from ummaya.context.prompt_loader import PromptLoader  # noqa: PLC0415

            # Default manifest lives at repo-root/prompts/manifest.yaml. The
            # stdio backend runs from repo root when invoked via
            # `uv run ummaya --ipc stdio`, so resolve relative to CWD.
            manifest = Path("prompts") / "manifest.yaml"
            if not manifest.is_file():
                _llm_system_prompt_cached[0] = ""
                return None
            loader = PromptLoader(manifest_path=manifest)
            _llm_system_prompt_cached[0] = loader.load("system_v1")
        except Exception:  # noqa: BLE001
            _llm_system_prompt_cached[0] = ""  # remember "tried and failed"
        return _llm_system_prompt_cached[0] or None

    async def _handle_user_input_llm(frame: IPCFrame) -> None:  # noqa: C901
        from ummaya.ipc.frame_schema import (  # noqa: PLC0415
            AssistantChunkFrame,
            UserInputFrame,
        )
        from ummaya.llm.models import ChatMessage  # noqa: PLC0415

        if not isinstance(frame, UserInputFrame):
            return

        history = _llm_sessions.setdefault(frame.session_id, [])
        if not history:
            system_text = await _ensure_system_prompt()
            if system_text:
                history.append({"role": "system", "content": system_text})
        history.append({"role": "user", "content": frame.text})

        client = await _ensure_llm_client()
        messages: list[ChatMessage] = []
        for m in history:
            role = str(m.get("role", "user"))
            content = m.get("content")
            if role in ("system", "user", "assistant", "tool") and isinstance(content, str):
                messages.append(
                    ChatMessage(
                        role=role,  # type: ignore[arg-type]
                        content=content,
                    )
                )

        message_id = str(uuid.uuid4())
        assistant_text_chunks: list[str] = []
        stream_error: Exception | None = None

        try:
            async for event in client.stream(  # type: ignore[attr-defined]
                messages=messages, max_tokens=2048
            ):
                event_type = getattr(event, "type", None)
                if event_type == "content_delta":
                    delta = getattr(event, "content", "") or ""
                    if delta:
                        assistant_text_chunks.append(delta)
                        chunk_frame = AssistantChunkFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="llm",
                            ts=_utcnow(),
                            kind="assistant_chunk",
                            message_id=message_id,
                            delta=delta,
                            done=False,
                        )
                        await write_frame(chunk_frame)
                elif event_type == "done":
                    break
                elif event_type == "error":
                    stream_error = RuntimeError(
                        str(getattr(event, "content", "unknown stream error"))
                    )
                    break
        except Exception as exc:  # noqa: BLE001
            stream_error = exc

        full_text = "".join(assistant_text_chunks)
        if stream_error is not None:
            err = ErrorFrame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id or str(uuid.uuid4()),
                role="backend",
                ts=_utcnow(),
                kind="error",
                code="llm_stream_error",
                message=str(stream_error),
                details={"message_id": message_id},
            )
            await write_frame(err)
            return

        # Terminal chunk — done=True signals end-of-turn to the TS side.
        terminal = AssistantChunkFrame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            role="llm",
            ts=_utcnow(),
            kind="assistant_chunk",
            message_id=message_id,
            delta="",
            done=True,
        )
        await write_frame(terminal)

        history.append({"role": "assistant", "content": full_text})

    import os as _os_chat_env  # noqa: PLC0415

    # Spec 1978 T030 — tool-result wait timeout (env-overridable).
    # contracts/tool-bridge-protocol.md gates the asyncio.gather on this value.
    _TOOL_RESULT_TIMEOUT_S = float(  # noqa: N806 — env-derived constant, function-scoped to avoid module-import-time env reads
        _os_chat_env.environ.get("UMMAYA_TOOL_RESULT_TIMEOUT_SECONDS", "120")
    )
    # Spec 1978 T029 — bound the CC query-engine agentic loop to prevent
    # infinite tool-recall. UMMAYA adopts the CC 2.1.88 query engine
    # architecture (native function calling + streaming + parallel tool
    # dispatch), NOT the academic ReAct paradigm — see memory
    # `feedback_ummaya_uses_cc_query_engine`. The UMMAYA_REACT_MAX_TURNS env
    # name is preserved for backward compatibility with already-shipped
    # configuration; the documented variable is logically the agentic-loop
    # max-turn cap.
    _AGENTIC_LOOP_MAX_TURNS = int(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get(
            "UMMAYA_AGENTIC_LOOP_MAX_TURNS",
            _os_chat_env.environ.get("UMMAYA_REACT_MAX_TURNS", "8"),
        )
    )
    # Epic #2152 R4 — separator between the cacheable static prefix (the
    # PromptLoader-resolved citizen system prompt + the augmented
    # ``## Available tools`` block) and the per-turn dynamic suffix. The
    # literal mirrors CC ``prompts.ts:572-575`` so the same identifier reads
    # familiar to anyone with CC source-map context. Downstream tooling
    # (ummaya.prompt.hash slicing in ``ummaya.llm.client``) splits on this
    # marker to compute the static-prefix-only hash.
    _DYNAMIC_BOUNDARY_MARKER = "\nSYSTEM_PROMPT_DYNAMIC_BOUNDARY\n"  # noqa: N806

    # Spec 2521 (2026-05-01) — BM25 candidate count for the dynamic
    # ``<available_adapters>`` block. Must be small enough to keep the
    # dynamic suffix LLM-readable (over-injecting blows the suffix budget
    # and reduces prompt-cache effectiveness for the static prefix). Five
    # mirrors the historical ``find(mode='search')`` default top_k that
    # K-EXAONE had been calling explicitly, so token-budget impact is
    # neutral relative to pre-2521 behavior.
    _AVAILABLE_ADAPTERS_TOP_K = int(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get("UMMAYA_AVAILABLE_ADAPTERS_TOP_K", "5")
    )

    def _build_available_adapters_suffix(user_query: str) -> str:  # noqa: C901
        """Run BM25 against the live registry and emit the citizen-turn
        ``<available_adapters>`` XML block for the dynamic system-prompt
        suffix.

        Returns an empty string on any retrieval failure or when the
        query is blank — fail-open so a flaky retriever does not break
        the citizen path (FR-002 mirror of the find primitive's own
        fail-open contract). Logged warnings are picked up by the OTEL
        spans Spec 028 already wires.
        """
        q = (user_query or "").strip()
        if not q:
            return ""
        try:
            from ummaya.tools.search import search  # noqa: PLC0415

            registry = _ensure_tool_registry()
            raw_top_k = max(_AVAILABLE_ADAPTERS_TOP_K * 3, _AVAILABLE_ADAPTERS_TOP_K)
            candidates = search(
                query=q,
                bm25_index=registry.bm25_index,
                registry=registry,
                top_k=min(raw_top_k, 20),
            )
        except Exception:
            logger.exception("BM25 retrieval failed for '%s'", q[:80])
            return ""
        filtered_candidates = []
        for candidate in candidates:
            try:
                tool = registry.find(candidate.tool_id)
            except Exception:
                logger.debug(
                    "Skipping unavailable adapter candidate %s",
                    candidate.tool_id,
                    exc_info=True,
                )
                continue
            if tool.is_core:
                continue
            filtered_candidates.append(candidate)
            if len(filtered_candidates) >= _AVAILABLE_ADAPTERS_TOP_K:
                break
        candidates = filtered_candidates
        if not candidates:
            return ""
        # Build a compact, LLM-readable block.
        #
        # Spec 2521 (2026-05-02) — emit per-field schema signatures so the
        # LLM can fill ``params`` against each adapter's actual REST shape.
        # The previous suffix only carried ``search_hint`` and assumed the
        # LLM could "infer params from search_hint" — K-EXAONE on FriendliAI
        # consistently invented ``{"location": "...", "date": "..."}`` style
        # payloads which fail every adapter's pydantic validation
        # (``Invalid parameters for tool``). Rendering each field with its
        # type + required flag + truncated description gives K-EXAONE
        # enough signal to call e.g. ``{"lat": 37.5, "lon": 129.0,
        # "base_date": "20260502", "base_time": "0500"}`` correctly.
        lines: list[str] = [
            f'<available_adapters query="{q[:120]}">',
            f"백엔드 BM25 후보 (top {len(candidates)}, 점수 내림차순):",
            "",
        ]
        for c in candidates:
            hint = (c.search_hint or "").strip()
            if len(hint) > 90:
                hint = hint[:87] + "..."
            primitive = c.primitive or "find"
            lines.append(
                f"- {c.tool_id} (primitive={primitive}) [{c.score:.2f}] — {hint or '(설명 없음)'}"
            )
            # Render the adapter's llm_description (usage prose, ORDERING RULE,
            # prerequisites, worked examples) so the LLM sees the complete
            # "먼저 locate 호출" ordering rule.
            # Bug: without this, the per-field description for nx is truncated
            # and K-EXAONE skips locate, producing invalid_params.
            if c.llm_description:
                desc_text = c.llm_description.strip().replace("\n", " ")
                # Emit at most 300 chars — enough for the ORDERING RULE and
                # worked example without blowing the per-turn token budget.
                if len(desc_text) > 300:
                    desc_text = desc_text[:297] + "..."
                lines.append(f"  설명: {desc_text}")
            # Render input schema signature so the LLM sees exact field
            # names + types + required flags + (truncated) descriptions.
            # Field desc limit raised 80→120 so nx/ny examples fit untruncated.
            schema = c.input_schema_json or {}
            properties = schema.get("properties") if isinstance(schema, dict) else None
            required: set[str] = set()
            raw_required = schema.get("required") if isinstance(schema, dict) else None
            if isinstance(raw_required, list):
                required = {str(item) for item in raw_required if isinstance(item, str)}
            # Spec 2522 T010 — ORDERING directive removed.
            # The Spec 2521 ORDERING block ("nx/ny 는 KMA 격자 좌표 — 반드시
            # locate 을 먼저 호출") forced a cross-domain chain that
            # contradicts both the user directive ("chain X / UMMAYA does not
            # force cross-domain chain") and v4 description 5-section
            # self_contained_decl ("이 도구 단독 호출로 완결. locate 등
            # cross-domain chain 불필요"). With both signals present K-EXAONE
            # ignored both and hallucinated nx/ny → Spec 2521 regression.
            # Each adapter's description (섹션 4 domain_quirk + 섹션 5
            # self_contained_decl + 섹션 3 short_reference 17 광역시도 표) is now
            # self-sufficient. The model decides chain vs single-tool autonomously.
            # Reference: research-stdio-ordering.md, frames-busan-weather/ T042 evidence.
            # Spec 2522 T047 fix — resolve $ref to $defs and inline enum values.
            # KOROAD KoroadAccidentSearchInput.search_year_cd uses
            # `$ref: #/$defs/SearchYearCd` (20 values). The previous renderer
            # only inlined `properties.<f>.enum` and gave up on $ref, leaving
            # K-EXAONE to guess plain '2024' (invalid). Spec 2522 frames-gangnam-
            # accident-fix2 evidence: invalid_params persisted after T042 fix.
            # Fix: resolve $ref against schema['$defs'] + raise threshold 8→25.
            defs_raw = schema.get("$defs") if isinstance(schema, dict) else None
            defs: dict[str, Any] | None = defs_raw if isinstance(defs_raw, dict) else None

            def _resolve_enum(
                meta: dict[str, Any], defs: dict[str, Any] | None
            ) -> list[Any] | None:
                # direct enum
                e = meta.get("enum")
                if isinstance(e, list):
                    return e
                # $ref → $defs/<name>
                ref = meta.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/$defs/") and isinstance(defs, dict):
                    name = ref.removeprefix("#/$defs/")
                    target = defs.get(name)
                    if isinstance(target, dict):
                        target_enum = target.get("enum")
                        if isinstance(target_enum, list):
                            return target_enum
                return None

            def _resolve_enum_with_names(
                meta: dict[str, Any], defs: dict[str, Any] | None
            ) -> list[tuple[Any, str]] | None:
                """Spec 2522 — agency 자체 코드체계 (KOROAD GugunCode SEOUL_GANGNAM=680
                등) 의 IntEnum name 을 의미 매핑으로 노출. pydantic JSON schema 의
                $defs 안 IntEnum 의 'enum' (값) + 'x-enum-varnames' (name) 또는
                'description' (docstring) 을 묶어서 LLM 에 보여줌.
                """
                ref = meta.get("$ref")
                if not (isinstance(ref, str) and ref.startswith("#/$defs/")):
                    return None
                if not isinstance(defs, dict):
                    return None
                name = ref.removeprefix("#/$defs/")
                target = defs.get(name)
                if not isinstance(target, dict):
                    return None
                values = target.get("enum")
                if not isinstance(values, list):
                    return None
                # IntEnum name 추출 — pydantic v2 가 'x-enum-varnames' 또는
                # 'enumNames' 로 export 하지 않음. 대신 module-level dict 조회.
                varnames = target.get("x-enum-varnames")
                if isinstance(varnames, list) and len(varnames) == len(values):
                    return list(zip(values, varnames, strict=False))
                return None

            if isinstance(properties, dict) and properties:
                for fname, fmeta in properties.items():
                    if not isinstance(fmeta, dict):
                        continue
                    ftype = fmeta.get("type") or fmeta.get("anyOf") or "any"
                    if isinstance(ftype, list):
                        ftype = "|".join(str(t) for t in ftype)
                    fdesc = str(fmeta.get("description", "")).strip().replace("\n", " ")
                    # Spec 2522 — agency 자체 코드체계 (KOROAD 68 시군구 매핑 ≈ 1600
                    # chars + 기존 description ≈ 600 chars = ~2200 chars / KMA 156
                    # station 등) 인라인 허용. 일반 도구는 100자 미만이라 영향 X.
                    if len(fdesc) > 5000:
                        fdesc = fdesc[:4997] + "..."
                    pat = fmeta.get("pattern")
                    pat_part = f" pattern={pat!r}" if isinstance(pat, str) else ""
                    enum = _resolve_enum(fmeta, defs)
                    # Spec 2522 T047 — threshold 25→200 — KOROAD GugunCode (115) /
                    # SearchYearCd (20) / SidoCode (17) 등 모두 노출. 의미 매핑은
                    # field description 에 따로 인라인 (Pydantic IntEnum 의 name
                    # 은 JSON schema 표준 export 안 됨).
                    if isinstance(enum, list) and len(enum) <= 200:
                        enum_part = f" enum={enum}"
                    else:
                        enum_part = ""
                    flag = "필수" if fname in required else "선택"
                    lines.append(
                        f"    · {fname} ({ftype}, {flag}{pat_part}{enum_part})"
                        + (f" — {fdesc}" if fdesc else "")
                    )
        lines.append("")
        lines.append(
            "규칙: 위 목록의 primitive에 맞는 루트 도구만 호출하세요: "
            'locate/find/check/send({"tool_id":"...", "params":{...}}). '
            "동일 tool_id 를 한 turn 안에서 반복 호출하지 마세요."
        )
        listed_primitives = {str(candidate.primitive or "find") for candidate in candidates}
        if listed_primitives == {"find"}:
            lines.append(
                "공개자료 조회 규칙: 위 후보가 모두 primitive=find 이면 시민이 "
                "인증/본인확인/동의/신청/제출/납부/신고를 명시하지 않은 한 "
                "check/send 를 호출하지 마세요. 성공한 find 결과가 있으면 "
                "다음 turn 은 최종 답변입니다."
            )
        lines.append(
            "호출 전 검증: 시민 발화의 명시 조건(개수, 반경/거리, 날짜/시간, 종류, "
            "카테고리, 진료과/분야, 키워드, 행정구역 등)이 아래 schema 의 선택 "
            "필드와 대응하면 그 필드를 반드시 params 에 포함하세요. 더 좁은 요청을 "
            "넓은 무필터 조회로 실행하지 마세요."
        )
        lines.append(
            'params 는 위에 표시된 정확한 필드명만 사용하세요 — 일반적인 "location"/'
            '"date" 같은 추측 키는 모든 어댑터에서 invalid_params 로 거부됩니다.'
        )
        lines.append(
            "BM25 도구 발견은 백엔드 internal 기능 — find(mode='search') 같은 호출은"
            " 무효화됩니다 (Spec 2521)."
        )
        lines.append("</available_adapters>")
        return "\n".join(lines)

    # Spec 1978 T053 — eager-import the Mock adapter tree so every adapter
    # self-registers with its primitive dispatcher before the first chat
    # turn arrives. Equivalent to plan.md "Mock adapter activation"; failure
    # is logged-only because Live tooling can still serve simple queries.
    try:
        import ummaya.tools.mock  # noqa: F401, PLC0415
    except Exception:  # noqa: BLE001
        logger.exception("failed to import ummaya.tools.mock — Mock adapters unavailable")

    # -----------------------------------------------------------------------
    # Spec 1978 T043-T049/T052 — Permission gauntlet bridge
    # -----------------------------------------------------------------------

    _PERM_TIMEOUT_S: float = float(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get("UMMAYA_PERMISSION_TIMEOUT_SECONDS", "60")
    )

    # Primitives that require a citizen permission request when called outside
    # an existing session-grant. Spec 033 Layer 1 (L1) exempts lookup/
    # locate (read-only, public-tier); verify and submit enter the
    # bridge.
    #
    # Epic #2077 T010 (FR-003) — single-source-of-truth migration: read the
    # gated set from ``ummaya.primitives.GATED_PRIMITIVES`` rather than
    # duplicating the literal set here. The local alias is preserved for
    # downstream call-site brevity (and to keep diff churn minimal in this
    # epic) but the literal set is no longer maintained in this module.
    from ummaya.primitives import (
        GATED_PRIMITIVES as _PERMISSION_GATED_PRIMITIVES,  # noqa: PLC0415, N811
    )

    async def _check_permission_gate(  # noqa: C901
        call_id: str,
        fname: str,
        args_obj: dict[str, object],
        session_id: str,
        correlation_id: str,
    ) -> bool:
        """Return True if the tool call is permitted to proceed.

        For gated primitives (verify/submit):
        1. Check session_grants cache — auto-allow if already approved.
        2. Emit PermissionRequestFrame and await citizen decision (60 s).
        3. On allow_session: cache grant; write consent receipt.
        4. On allow_once: write consent receipt, no cache.
        5. On deny or timeout: emit synthetic tool_result with error, return False.

        For non-gated primitives (lookup/locate/verify): return True
        immediately without touching the bridge.
        """
        from ummaya.ipc.frame_schema import (  # noqa: PLC0415
            PermissionRequestFrame,
            ToolResultEnvelope,
            ToolResultFrame,
        )

        if fname not in _PERMISSION_GATED_PRIMITIVES:
            with _tracer.start_as_current_span("ummaya.permission") as span:
                span.set_attribute("ummaya.permission.mode", "auto_allow")
                span.set_attribute("ummaya.permission.decision", "allow_once")
                span.set_attribute("ummaya.tool.dispatched", fname)
            return True

        # Check session grant cache first (allow_session shortcut — T048).
        session_grant_set = _session_grants.get(session_id, set())
        tool_key = f"{fname}:{args_obj.get('tool_id', fname)}"
        if tool_key in session_grant_set:
            with _tracer.start_as_current_span("ummaya.permission") as span:
                span.set_attribute("ummaya.permission.mode", "auto_allow")
                span.set_attribute("ummaya.permission.decision", "allow_session")
                span.set_attribute("ummaya.tool.dispatched", fname)
            logger.debug("permission: session_grant hit for %s session=%s", tool_key, session_id)
            return True

        # Determine risk level and description from primitive type.
        # verify is LIGHT_GATE (low risk, identity delegation read-only).
        # submit is HEAVY_GATE (high risk, side-effecting).
        _PRIM_RISK: dict[str, str] = {  # noqa: N806
            "check": "low",
            "send": "high",
        }
        _PRIM_KO: dict[str, str] = {  # noqa: N806
            "check": "신원 확인을 위해 인증 위임을 요청합니다.",
            "send": "정부 API에 데이터를 제출합니다. 이 작업은 되돌릴 수 없습니다.",
        }
        _PRIM_EN: dict[str, str] = {  # noqa: N806
            "check": "Request identity delegation for verification.",
            "send": "Submit data to a government API. This action is irreversible.",
        }

        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        _pending_perms[request_id] = loop.create_future()

        with _tracer.start_as_current_span("ummaya.permission") as perm_span:
            perm_span.set_attribute("ummaya.permission.mode", "ask")
            perm_span.set_attribute("ummaya.tool.dispatched", fname)

            # Audit-4 P0-10 fix — propagate the resolving adapter id
            # (e.g. `mock_verify_mobile_id`) as both `worker_id` and the new
            # `tool_id` field. Without this the TUI rendered the literal
            # `"main"` in every permission modal title because
            # `pushIpcPermissionRequest` (ipcPermissionBridge.ts:153) read
            # `frame.worker_id || frame.primitive_kind`.
            _resolved_tool_id = str(args_obj.get("tool_id", fname))
            try:
                await write_frame(
                    PermissionRequestFrame(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="permission_request",
                        request_id=request_id,
                        worker_id=_resolved_tool_id,
                        primitive_kind=fname,  # type: ignore[arg-type]
                        description_ko=_PRIM_KO.get(fname, "도구를 실행합니다."),
                        description_en=_PRIM_EN.get(fname, "Invoke tool."),
                        risk_level=_PRIM_RISK.get(fname, "medium"),  # type: ignore[arg-type]
                        tool_id=_resolved_tool_id,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("permission: failed to emit permission_request: %s", exc)
                _pending_perms.pop(request_id, None)
                perm_span.set_attribute("ummaya.permission.decision", "deny")
                return False

            # Await citizen decision with timeout (D2 invariant).
            decision_frame: Any = None
            try:
                decision_frame = await asyncio.wait_for(
                    _pending_perms[request_id],
                    timeout=_PERM_TIMEOUT_S,
                )
                perm_span.set_attribute("ummaya.permission.decision", "allow_once")
            except TimeoutError:
                logger.warning(
                    "permission: timeout waiting for response to request_id=%s", request_id
                )
                perm_span.set_attribute("ummaya.permission.decision", "timeout")
                _pending_perms.pop(request_id, None)
                # Emit synthetic denied tool_result so the LLM turn resolves.
                denied_env = ToolResultEnvelope(
                    kind=cast("Any", fname),
                    **{"error": "permission_timeout", "denied": True},
                )
                fut = _pending_calls.get(call_id)
                if fut and not fut.done():
                    denied_result_frame = ToolResultFrame(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="tool_result",
                        call_id=call_id,
                        envelope=denied_env,
                    )
                    try:
                        await write_frame(denied_result_frame)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "permission: failed to emit timeout tool_result: %s",
                            exc,
                        )
                    fut.set_result(denied_result_frame)
                return False
            finally:
                _pending_perms.pop(request_id, None)

            # Map PermissionResponseFrame.decision → allow/deny per Spec 1978
            # ADR-0002. Spec 287 baseline emitted only "granted" / "denied"; the
            # 3-decision UI vocabulary (allow_once | allow_session | deny) is
            # accepted now that frame_schema.py extends the Literal.
            raw_decision: str = getattr(decision_frame, "decision", "denied")
            is_deny = raw_decision in {"denied", "deny"}
            is_allow_session = raw_decision == "allow_session"
            if is_deny:
                perm_span.set_attribute("ummaya.permission.decision", "deny")
                # Audit-4 P0-2 — append HMAC-sealed deny record so the audit
                # trail captures BOTH the request emission and the citizen's
                # negative decision. Without this, "permission_denied" tool
                # results have no integrity-verified provenance in the ledger.
                try:
                    from ummaya.permissions.action_digest import (  # noqa: PLC0415
                        compute_action_digest,
                        generate_nonce,
                    )
                    from ummaya.permissions.ledger import (  # noqa: PLC0415
                        append as _ledger_append_deny,
                    )
                    from ummaya.settings import (  # noqa: PLC0415
                        settings as _ummaya_settings_deny,
                    )

                    _deny_args = {k: v for k, v in args_obj.items() if k != "delegation_context"}
                    _deny_digest = compute_action_digest(
                        str(args_obj.get("tool_id", fname)),
                        _deny_args,
                        generate_nonce(),
                    )
                    _ledger_append_deny(
                        tool_id=str(args_obj.get("tool_id", fname)),
                        mode="default",
                        granted=False,
                        action_digest=_deny_digest,
                        action="deny",
                        session_id=session_id,
                        correlation_id=correlation_id,
                        ledger_path=_ummaya_settings_deny.permission_ledger_path,
                        key_path=_ummaya_settings_deny.permission_key_path,
                        key_registry_path=_ummaya_settings_deny.permission_key_registry_path,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("permission: ledger.append(deny) failed: %s", exc)
                # Emit synthetic denied tool_result.
                denied_env2 = ToolResultEnvelope(
                    kind=cast("Any", fname),
                    **{"error": "permission_denied", "denied": True},
                )
                fut2 = _pending_calls.get(call_id)
                if fut2 and not fut2.done():
                    denied_result_frame2 = ToolResultFrame(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="tool_result",
                        call_id=call_id,
                        envelope=denied_env2,
                    )
                    try:
                        await write_frame(denied_result_frame2)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "permission: failed to emit denied tool_result: %s",
                            exc,
                        )
                    fut2.set_result(denied_result_frame2)
                return False

            # Granted — write consent receipt + optionally update session grant cache.
            # Audit-4 P0-4 fix — emit `rcpt-<8-char-hex>` so the format matches the
            # TUI regex `^rcpt-[A-Za-z0-9_-]{8,}$` (schemas/ui-l2/permission.ts:26)
            # AND the executeConsentRevoke validator (commands/consent.ts:90).
            # Without the prefix every backend-issued receipt was rejected by the
            # citizen-facing /consent revoke flow with `invalid_id`.
            receipt_id = f"rcpt-{uuid.uuid4().hex[:8]}"
            decision_label = "allow_session" if is_allow_session else "allow_once"
            perm_span.set_attribute("ummaya.permission.decision", decision_label)
            perm_span.set_attribute("ummaya.consent.receipt_id", receipt_id)

            # Spec 1978 T049 — allow_session caches the (primitive, tool_id)
            # pair so subsequent same-session same-tool calls bypass the
            # bridge entirely (lookup at the top of this function via
            # _session_grants). Audit-4 alignment fix (2026-05-04): the
            # storage key MUST match the lookup key. The lookup at line
            # 1406 uses `f"{fname}:{tool_id}"`; the prior storage stored
            # only `tool_id` → cache miss on every "allow_session" call.
            if is_allow_session:
                tool_key_for_cache = f"{fname}:{args_obj.get('tool_id', fname)}"
                _session_grants.setdefault(session_id, set()).add(tool_key_for_cache)
            try:
                import json as _json_receipt  # noqa: PLC0415
                from pathlib import Path as _Path  # noqa: PLC0415

                consent_dir = _Path.home() / ".ummaya" / "memdir" / "user" / "consent"
                consent_dir.mkdir(parents=True, exist_ok=True)
                receipt_path = consent_dir / f"{receipt_id}.json"
                receipt_data = {
                    "receipt_id": receipt_id,
                    "session_id": session_id,
                    "tool_id": str(args_obj.get("tool_id", fname)),
                    "primitive": fname,
                    "decision": decision_label,
                    "granted_at": _utcnow(),
                    "revoked_at": None,
                }
                receipt_path.write_text(
                    _json_receipt.dumps(receipt_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.debug("permission: wrote consent receipt %s", receipt_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("permission: failed to write consent receipt: %s", exc)

            # Audit-4 P0-2 — append HMAC-sealed, hash-chained ledger record so the
            # consent receipt JSON in the memdir layer is BACKED by an integrity-
            # verified entry in the canonical Spec 033 PIPA ledger
            # (~/.ummaya/consent_ledger.jsonl). Without this append, allow paths
            # left receipts forgeable: no HMAC seal, no chain prev_hash, no key_id.
            #
            # Failures are logged-only — the citizen has already approved the
            # action and the synthetic tool_result must still be emitted. A
            # follow-up `ummaya permissions verify` run will surface any drift.
            try:
                from ummaya.permissions.action_digest import (  # noqa: PLC0415
                    compute_action_digest,
                    generate_nonce,
                )
                from ummaya.permissions.ledger import (  # noqa: PLC0415
                    append as _ledger_append,
                )
                from ummaya.settings import settings as _ummaya_settings  # noqa: PLC0415

                _ledger_args = {k: v for k, v in args_obj.items() if k != "delegation_context"}
                _digest = compute_action_digest(
                    str(args_obj.get("tool_id", fname)),
                    _ledger_args,
                    generate_nonce(),
                )
                _ledger_append(
                    tool_id=str(args_obj.get("tool_id", fname)),
                    mode="default",
                    granted=True,
                    action_digest=_digest,
                    action="allow",
                    consent_receipt_id=receipt_id,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    ledger_path=_ummaya_settings.permission_ledger_path,
                    key_path=_ummaya_settings.permission_key_path,
                    key_registry_path=_ummaya_settings.permission_key_registry_path,
                )
                logger.debug(
                    "permission: ledger.append(allow) ok receipt_id=%s tool=%s",
                    receipt_id,
                    args_obj.get("tool_id", fname),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "permission: ledger.append(allow) failed (receipt_id=%s): %s",
                    receipt_id,
                    exc,
                )

            # Gap A fix — emit PermissionResponseFrame echo back to TUI so
            # that addReceipt() callsites can capture the receipt_id without
            # a separate /consent list round-trip. This is a backend→TUI
            # echo, not a new request; the TUI ignores it safely if it
            # doesn't recognise the receipt_id field (backward-compat via
            # Optional default=None in frame_schema.py).
            from ummaya.ipc.frame_schema import (  # noqa: PLC0415
                PermissionResponseFrame as _PermissionResponseFrame,
            )

            try:
                await write_frame(
                    _PermissionResponseFrame(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="permission_response",
                        request_id=request_id,
                        decision=decision_label,  # type: ignore[arg-type]
                        receipt_id=receipt_id,
                        # Audit-4 P0-6 / P0-7 — propagate enough context for the
                        # TUI's usePermissionReceiptWatcher to recompute the
                        # gauntlet layer (1=green / 2=orange / 3=red) and render
                        # the human-readable adapter name in /consent list.
                        # Without these the TUI hardcoded layer=1 and tool_name=
                        # 'unknown' for every receipt regardless of primitive.
                        primitive_kind=fname,  # type: ignore[arg-type]
                        tool_id=_resolved_tool_id,
                    )
                )
                logger.debug("permission: emitted receipt echo (receipt_id=%s)", receipt_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("permission: failed to emit receipt echo: %s", exc)

            return True

    async def _handle_permission_response(frame: IPCFrame) -> None:
        """Spec 1978 T047 — consume permission_response and resolve pending Future.

        Maps incoming PermissionResponseFrame.request_id to the waiting
        _pending_perms entry. Frames with no matching request_id are logged
        and silently dropped (forward-compat: stale responses after timeout).
        """
        from ummaya.ipc.frame_schema import PermissionResponseFrame  # noqa: PLC0415

        if not isinstance(frame, PermissionResponseFrame):
            return
        fut = _pending_perms.pop(frame.request_id, None)
        if fut is None:
            logger.debug(
                "permission_response with no pending request (request_id=%s) — ignoring",
                frame.request_id,
            )
            return
        if not fut.done():
            fut.set_result(frame)

    # -----------------------------------------------------------------------
    # Spec 1978 T053b — internal primitive dispatcher
    # -----------------------------------------------------------------------

    async def _dispatch_primitive(  # noqa: C901, PLR0912
        call_id: str,
        fname: str,
        args_obj: dict[str, object],
        session_id: str,
        correlation_id: str,
    ) -> None:
        """Dispatch a single primitive call internally and resolve its pending Future.

        CC reference: ``services/tools/toolOrchestration.ts:19-72`` (CC's ``runTools``
        async generator). Note partition policy divergence: UMMAYA dispatches all
        primitive calls in parallel via ``asyncio.gather`` since the citizen-facing
        primitives (lookup/locate/verify) are read-only-equivalent. CC
        partitions by ``isConcurrencySafe`` (read-only batches parallel,
        write-side serial). Tracking the partition adoption as Deferred Item #2574.

        Called immediately after a tool_call frame is emitted and the Future
        is registered in _pending_calls. Routes by fname, awaits the primitive,
        wraps the result in a ToolResultFrame, emits it to the TUI, then
        resolves _pending_calls[call_id] so the agentic-loop continuation can
        inject the result as a role="tool" message.

        Permission gate: verify/submit go through _check_permission_gate
        first. On denial/timeout, the gate itself resolves the Future with an
        error envelope, so this function exits early without double-resolution.

        OTEL: sets ummaya.tool.dispatched on the existing session span.
        """

        from ummaya.ipc.frame_schema import (  # noqa: PLC0415
            ToolResultEnvelope,
            ToolResultFrame,
        )

        with _tracer.start_as_current_span("ummaya.tool.dispatch") as span:
            span.set_attribute("ummaya.tool.dispatched", fname)
            span.set_attribute("ummaya.session.id", session_id)

            invalid_gated_tool_id = (
                _invalid_gated_primitive_tool_id_result(fname, args_obj)
                if fname in _PERMISSION_GATED_PRIMITIVES
                else None
            )
            if invalid_gated_tool_id is not None:
                span.set_attribute("error.type", "invalid_tool_id")
                invalid_envelope = ToolResultEnvelope(
                    kind=cast("Any", fname),
                    **invalid_gated_tool_id,
                )
                invalid_result_frame = ToolResultFrame(
                    session_id=session_id,
                    correlation_id=correlation_id,
                    role="backend",
                    ts=_utcnow(),
                    kind="tool_result",
                    call_id=call_id,
                    envelope=invalid_envelope,
                )
                try:
                    await write_frame(invalid_result_frame)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "_dispatch_primitive: failed to emit invalid tool_id result: %s",
                        exc,
                    )
                fut = _pending_calls.pop(call_id, None)
                if fut is not None and not fut.done():
                    fut.set_result(invalid_result_frame)
                return

            # ----- Permission gate (T043-T049) -----
            allowed = await _check_permission_gate(
                call_id, fname, args_obj, session_id, correlation_id
            )
            if not allowed:
                # Gate already resolved the Future with an error envelope.
                span.set_attribute("ummaya.permission.decision", "deny")
                return

            result_payload: dict[str, object] = {}
            dispatch_error: str | None = None
            # Each primitive returns a different Pydantic model. Annotate as
            # Any so the branches below can assign without mypy assignment
            # narrowing complaints.
            raw: Any

            # Spec 2521 (2026-05-01) — open an outbound HTTP trace scope so
            # any ``data.go.kr`` / agency call the adapter makes is captured
            # and attached to the envelope as ``outbound_traces``. The TUI's
            # verbose render reads this field to show the citizen / operator
            # the exact request/response JSON.
            from ummaya.tools._outbound_trace import (  # noqa: PLC0415
                consume_outbound_capture,
                start_outbound_capture,
            )

            _outbound_trace_token = start_outbound_capture()

            try:
                if fname == "check":
                    from ummaya.primitives.verify import (  # noqa: PLC0415
                        verify,
                    )
                    from ummaya.tools.verify_canonical_map import (  # noqa: PLC0415
                        resolve_family,
                    )

                    # Spec 2297 / Issue #C1 (2026-05-04) — translate
                    # ``tool_id`` → ``family_hint`` via adapter metadata.
                    # The mvp_surface ``_VerifyInputForLLM.translate_tool_id_shape``
                    # validator only fires when the LLM call goes through Pydantic
                    # schema validation; the IPC stdio dispatcher bypasses that
                    # path and historically read ``family_hint`` directly from
                    # the args dict, leaving every K-EXAONE-emitted
                    # ``check({tool_id: …})`` call resolving to ``family_hint=""``
                    # → "No check adapter registered for family ''".
                    # Accept both ``family`` (citizen-facing tool schema) and
                    # ``family_hint`` (primitive's internal arg name) for
                    # legacy / tools-bridge compatibility.
                    tool_id = str(args_obj.get("tool_id") or "")
                    if tool_id:
                        registry = _ensure_tool_registry()
                        try:
                            tool = registry.find(tool_id)
                        except Exception:
                            dispatch_error = f"No check adapter registered for tool_id={tool_id!r}."
                        else:
                            if tool.primitive != "check":
                                dispatch_error = (
                                    f"Adapter {tool_id!r} is primitive={tool.primitive!r}, "
                                    "but was called through check."
                                )
                    if dispatch_error is None:
                        family_hint = resolve_family(tool_id) or str(
                            args_obj.get("family_hint") or args_obj.get("family") or ""
                        )
                        session_ctx = _build_verify_session_context(
                            args_obj,
                            session_id=session_id,
                        )
                        raw = await verify(family_hint=family_hint, session_context=session_ctx)
                        if _cacheable_auth_context(raw):
                            _session_auth_contexts[session_id] = raw
                            issued_session_id = session_ctx.get("session_id", session_id)
                            _session_auth_session_ids[session_id] = str(issued_session_id)
                        result_payload = {
                            "family": family_hint,
                            "result": _serialize_primitive_result(raw),
                        }

                elif fname == "find":
                    # Spec 2521 (2026-05-01): the LLM-visible ``find``
                    # surface is fetch-only. BM25 adapter discovery is a
                    # backend-internal mechanism (auto-injected into the
                    # ``<available_adapters>`` dynamic suffix) — the LLM
                    # MUST NOT see "search" as a callable mode. Stale
                    # ``mode='search'`` payloads from older sessions are
                    # rejected with a typed LookupError so the agentic
                    # loop continues without painting an "internal
                    # function as tool" UI block.
                    from ummaya.tools.errors import LookupErrorReason  # noqa: PLC0415
                    from ummaya.tools.lookup import find  # noqa: PLC0415
                    from ummaya.tools.models import (  # noqa: PLC0415
                        LookupError,  # noqa: A004 — Pydantic model named LookupError; intentional shadow with module-level alias not feasible in narrow import scope
                        LookupFetchInput,
                    )

                    requested_mode = args_obj.get("mode")
                    if requested_mode is not None and str(requested_mode) != "fetch":
                        logger.warning(
                            "find: rejected mode=%r — LLM-visible surface is "
                            "fetch-only since Spec 2521. Skipping dispatch.",
                            requested_mode,
                        )
                        raw = LookupError(
                            kind="error",
                            reason=LookupErrorReason.invalid_params,
                            message=(
                                "find(mode='search') 는 백엔드 internal 기능입니다 — "
                                "직접 호출하지 마십시오. 시스템 프롬프트의 "
                                "<available_adapters> 에서 tool_id 를 골라 fetch 호출만 사용하세요."
                            ),
                            retryable=False,
                        )
                        result_payload = {
                            "kind": "find",
                            "result": _serialize_primitive_result(raw),
                        }
                    else:
                        # Use the session-scoped singleton populated by
                        # register_all_tools (Spec 1634). Constructing a fresh
                        # empty ToolRegistry / ToolExecutor here would trigger
                        # reason="empty_registry" for every fetch — the very
                        # bug fixed on 2026-05-01.
                        registry = _ensure_tool_registry()
                        executor = _ensure_tool_executor()
                        lookup_params = cast(
                            "dict[str, object]",
                            args_obj.get("params") or {},
                        )
                        auth_context = _session_auth_contexts.get(session_id)
                        if auth_context is not None:
                            lookup_params = _inject_delegation_context(
                                lookup_params,
                                auth_context,
                            )
                        inp_lk = LookupFetchInput(
                            mode="fetch",
                            tool_id=str(args_obj.get("tool_id", "")),
                            params=lookup_params,
                        )
                        raw = await find(
                            inp_lk,
                            registry=registry,
                            executor=executor,
                            session_identity=session_id,
                        )
                        result_payload = {
                            "kind": "find",
                            "result": _serialize_primitive_result(raw),
                        }

                elif fname == "locate":
                    tool_id = str(args_obj.get("tool_id") or "")
                    if tool_id:
                        registry = _ensure_tool_registry()
                        try:
                            tool = registry.find(tool_id)
                        except Exception:
                            dispatch_error = (
                                f"No locate adapter registered for tool_id={tool_id!r}."
                            )
                        else:
                            if tool.primitive != "locate":
                                dispatch_error = (
                                    f"Adapter {tool_id!r} is primitive={tool.primitive!r}, "
                                    "but was called through locate."
                                )
                            else:
                                executor = _ensure_tool_executor()
                                locate_params = cast(
                                    "dict[str, object]",
                                    args_obj.get("params") or {},
                                )
                                raw = await executor.invoke_raw(
                                    tool_id=tool_id,
                                    params=locate_params,
                                    request_id=str(uuid.uuid4()),
                                    session_identity=session_id,
                                )
                    else:
                        # Backward compatibility for old transcripts/tests that
                        # still contain locate({query, want}). New LLM-visible
                        # schema is locate({tool_id, params}); no semantic
                        # rewriting is performed before adapter dispatch.
                        from ummaya.tools.models import ResolveLocationInput  # noqa: PLC0415
                        from ummaya.tools.resolve_location import locate  # noqa: PLC0415

                        inp_rl = ResolveLocationInput(
                            query=str(args_obj.get("query", "")),
                            want=str(args_obj.get("want", "coords_and_admcd")),  # type: ignore[arg-type]
                        )
                        raw = await locate(inp_rl)
                    if dispatch_error is None:
                        result_payload = {
                            "kind": "locate",
                            "result": _serialize_primitive_result(raw),
                        }

                elif fname == "send":
                    from ummaya.primitives.submit import submit  # noqa: PLC0415

                    requested_tool_id = str(args_obj.get("tool_id", ""))
                    if requested_tool_id:
                        registry = _ensure_tool_registry()
                        try:
                            tool = registry.find(requested_tool_id)
                        except Exception:
                            dispatch_error = (
                                f"No send adapter registered for tool_id={requested_tool_id!r}."
                            )
                        else:
                            if tool.primitive != "send":
                                dispatch_error = (
                                    f"Adapter {requested_tool_id!r} is "
                                    f"primitive={tool.primitive!r}, "
                                    "but was called through send."
                                )
                    if dispatch_error is None:
                        auth_context = _session_auth_contexts.get(session_id)
                        submit_params = cast(
                            "dict[str, object]",
                            args_obj.get("params") or {},
                        )
                        if auth_context is not None:
                            submit_params = _inject_delegation_context(
                                submit_params,
                                auth_context,
                            )
                        delegation_session_id = _session_auth_session_ids.get(
                            session_id,
                            session_id,
                        )
                        submit_params = _bind_submit_session_id(
                            submit_params,
                            session_id=delegation_session_id,
                        )
                        raw = await submit(
                            tool_id=requested_tool_id,
                            params=submit_params,
                            auth_context=auth_context,
                            session_id=session_id,
                        )
                        result_payload = {
                            "kind": "send",
                            "result": _serialize_primitive_result(raw),
                        }

                else:
                    dispatch_error = f"unknown primitive {fname!r}"

            except Exception as exc:  # noqa: BLE001
                logger.exception("_dispatch_primitive: %s dispatch failed: %s", fname, exc)
                dispatch_error = str(exc)

            if dispatch_error:
                result_payload = {
                    "kind": fname,
                    "error": dispatch_error,
                    "tool_id": str(args_obj.get("tool_id", fname)),
                }

            # Drain the outbound HTTP trace buffer + attach to the envelope.
            outbound_traces = consume_outbound_capture(_outbound_trace_token)
            if outbound_traces:
                # Pydantic model_dump → JSON-serialisable dict; envelope
                # accepts the extra field via ``extra="allow"``.
                result_payload["outbound_traces"] = [t.model_dump() for t in outbound_traces]

            # Build ToolResultEnvelope + ToolResultFrame.
            # ToolResultEnvelope uses extra="allow" so extra payload fields are kept.
            # Strip any payload-level "kind" so the kwarg is single-valued.
            payload_kw = {k: v for k, v in result_payload.items() if k != "kind"}
            envelope = ToolResultEnvelope(kind=cast("Any", fname), **payload_kw)
            result_frame = ToolResultFrame(
                session_id=session_id,
                correlation_id=correlation_id,
                role="backend",
                ts=_utcnow(),
                kind="tool_result",
                call_id=call_id,
                envelope=envelope,
            )

            # Emit to TUI for display.
            try:
                await write_frame(result_frame)
            except Exception as exc:  # noqa: BLE001
                logger.warning("_dispatch_primitive: failed to emit tool_result frame: %s", exc)

            # Resolve the pending Future so the agentic loop can continue.
            fut = _pending_calls.pop(call_id, None)
            if fut is not None and not fut.done():
                fut.set_result(result_frame)

    async def _handle_chat_request(frame: IPCFrame) -> None:  # noqa: C901, PLR0915
        """Spec 1978 ADR-0001 — tools-aware chat handler.

        CC reference: ``QueryEngine.ts`` (whole, 1295 lines) + ``query.ts:120-410``
        (yieldMissingToolResultBlocks pattern). Behavior-mirror: UMMAYA preserves
        CC's per-turn message_id, structured tool_calls dispatch, role="tool"
        injection between turns, max_turns termination semantics. The only
        divergence is the I/O surface — CC reads from Anthropic SDK stream,
        UMMAYA reads from FriendliAI OpenAI-compat SSE via LLMClient and emits
        IPCFrames over stdio JSONL (Spec 287 / Spec 032 IPC contract).

        Implements the CC (Claude Code 2.1.88) query-engine agentic loop —
        native function calling + token streaming + parallel tool dispatch
        + content_block accumulation, NOT the academic ReAct paradigm
        (text-marker-based Thought/Action). See memory
        ``feedback_ummaya_uses_cc_query_engine`` for the architectural
        rationale.

        Replaces ``_handle_user_input_llm`` for ``ChatRequestFrame``. Streams
        text deltas as ``AssistantChunkFrame``, emits one ``ToolCallFrame``
        per K-EXAONE function-call, awaits each matching ``ToolResultFrame``
        via ``_pending_calls`` Futures, then injects synthetic
        ``role="tool"`` messages into the local history and re-invokes
        ``LLMClient.stream`` (agentic-loop continuation per ADR-0005).

        Loop is bounded by ``UMMAYA_AGENTIC_LOOP_MAX_TURNS`` (default 8;
        also accepts the legacy ``UMMAYA_REACT_MAX_TURNS``) and the
        per-call wait by ``UMMAYA_TOOL_RESULT_TIMEOUT_SECONDS`` (default 120).
        """
        from ummaya.ipc.frame_schema import (  # noqa: PLC0415
            AssistantChunkFrame,
            ChatRequestFrame,
            ToolCallFrame,
        )
        from ummaya.llm.models import (  # noqa: PLC0415
            ChatMessage as LLMChatMessage,
        )
        from ummaya.llm.models import (
            FunctionCall as LLMFunctionCall,
        )
        from ummaya.llm.models import (
            ToolCall as LLMToolCall,
        )
        from ummaya.llm.models import (
            ToolDefinition as LLMToolDefinition,
        )
        from ummaya.llm.system_prompt_builder import (  # noqa: PLC0415
            build_system_prompt_with_tools,
        )

        if not isinstance(frame, ChatRequestFrame):
            return

        # ---- spec-multi-turn-contamination diagnostic emit (FR-001/FR-002)
        # Increment the per-session turn counter and dump the inbound
        # ChatRequestFrame.messages tail so we can prove which user turn
        # K-EXAONE actually saw on the wire. Off by default; gated by
        # UMMAYA_CHAT_REQUEST_DUMP=1. Truncates each message content to
        # 256 chars to keep the log line bounded.
        # Always increment the counter so OTEL `ummaya.chat.turn_index`
        # works regardless of the env-gated stderr dump.
        _diag_turn_idx = _session_turn_counter.get(frame.session_id, 0) + 1
        _session_turn_counter[frame.session_id] = _diag_turn_idx
        # Additive Spec 021 OTEL extension — annotate the parent
        # `ummaya.ipc.frame` span (opened by the reader loop) with the
        # turn index so Langfuse traces can group multi-turn flows.
        try:
            _current_span = trace.get_current_span()
            if _current_span is not None:
                _current_span.set_attribute("ummaya.chat.turn_index", _diag_turn_idx)
        except Exception:  # noqa: BLE001, S110 — telemetry must never raise
            pass
        if _diag_chat_request_enabled():
            try:
                _dump_payload = [
                    {
                        "role": m.role,
                        "content": (m.content or "")[:256],
                        "name": m.name,
                        "tool_call_id": m.tool_call_id,
                    }
                    for m in frame.messages
                ]
                logger.info(
                    "[CHAT_REQUEST_DUMP] turn=%d session=%s correlation=%s "
                    "messages_count=%d messages=%s",
                    _diag_turn_idx,
                    frame.session_id,
                    frame.correlation_id,
                    len(frame.messages),
                    _stdlib_json.dumps(_dump_payload, ensure_ascii=False),
                )
            except Exception:  # noqa: BLE001 — diagnostic must never raise
                logger.exception("[CHAT_REQUEST_DUMP] failed to serialise")

        # Tool inventory — backend ToolRegistry is the single source of
        # truth, BUT only the active LLM-callable primitives go into the
        # ``tools`` parameter the model sees. UMMAYA architecture
        # (docs/vision.md L1-C): `system prompt exposes primitive
        # signatures only; BM25 surfaces adapters dynamically`. Adapter
        # tools (kma_*, hira_*, nmc_*, koroad_*, mohw_*, nfa_*) are
        # invoked via `find(tool_id="<adapter_id>", params={...})`,
        # never directly. The previous version of this block
        # (commit 5050417f) emitted every core_tool — primitive AND
        # adapter — into the tools[] parameter, which let K-EXAONE call
        # adapter ids directly (e.g. `kma_current_observation()` instead
        # of `find(tool_id="kma_current_observation", params=...)`).
        # The dispatcher then rejected the call with "Model requested
        # unknown tool 'kma_current_observation'" because PRIMITIVE_REGISTRY
        # only contains the active primitives. Captured live in
        # specs/integration-verification/donga-univ-poi-bug/
        # snap-001-01-kma-now (2026-05-04).
        #
        # Filtering by `ministry == "UMMAYA"` AND id in the primitive
        # whitelist matches the intent of mvp_surface.py — the UMMAYA
        # GovAPITool entries with `primitive=` field set are exactly
        # the LLM-callable surface. Adapters (every other ministry) flow
        # through the `<available_adapters>` system-prompt suffix that
        # `_build_available_adapters_suffix` emits below.
        registry = cast("Any", _ensure_tool_registry())
        from ummaya.primitives import PRIMITIVE_REGISTRY  # noqa: PLC0415

        backend_tools_raw = [
            t.to_openai_tool()
            for t in registry.core_tools()
            if t.ministry == "UMMAYA" and t.id in PRIMITIVE_REGISTRY
        ]
        backend_tool_names: set[object] = set()
        for raw_tool in backend_tools_raw:
            if not isinstance(raw_tool, dict):
                continue
            function = raw_tool.get("function")
            if isinstance(function, dict):
                backend_tool_names.add(function.get("name"))
        llm_tools: list[LLMToolDefinition] = [
            LLMToolDefinition.model_validate(raw) for raw in backend_tools_raw
        ]
        for t in frame.tools:
            tui_name = getattr(getattr(t, "function", None), "name", None)
            if tui_name and tui_name in backend_tool_names:
                continue
            llm_tools.append(LLMToolDefinition.model_validate(t.model_dump()))

        # Build LLMClient input from the frame payload. Conversation history
        # lives in the TUI per ADR-0005 — backend receives the full slate.
        # Epic #2077 T010 (Step 3) — augment the system prompt with a
        # ``## Available tools`` section so K-EXAONE sees the same inventory
        # in BOTH the structured ``tools`` param AND the prose system message
        # (mirrors ``_cc_reference/api.ts:appendSystemContext``). Returns
        # ``base`` unchanged when ``llm_tools`` is empty (no inventory to
        # publish), so the no-tools path is byte-stable with the old code.
        # Epic #2152 R3 + R4 — when the TUI sends an empty ``frame.system``
        # (the new default after R5 dev-context excision), fall back to the
        # PromptLoader-resolved citizen system prompt. Append the boundary
        # marker so the prefix hash emitted by the LLM client is meaningful.
        from ummaya.ipc.citizen_request import (  # noqa: PLC0415
            wrap_citizen_request,
        )

        # G-class chain enforcement (2026-05-04) — top-level scope so the
        # follow-up-lookup gate inside the agentic loop can read the original
        # citizen utterance while the dynamic <available_adapters> block
        # decides whether a registry-selected `find(...)` candidate must run
        # before the LLM is allowed to produce a final answer.
        latest_user_utt = ""

        base_system = frame.system
        if not base_system:
            loaded = await _ensure_system_prompt()
            base_system = loaded or ""
        augmented_system = build_system_prompt_with_tools(base_system, llm_tools)
        if augmented_system:
            augmented_system = augmented_system + _DYNAMIC_BOUNDARY_MARKER
            # UMMAYA hotfix #2520 (2026-04-30 user report — 날짜 hallucination):
            # CC 원본 (.references/claude-code-sourcemap/restored-src/src/constants/
            # prompts.ts:452) 은 system prompt 첫 paragraph 에 동적으로
            # `Date: ${getSessionStartDate()}` 를 inject. UMMAYA 는 prompts/
            # system_v1.md (static markdown) 만 사용해서 LLM 이 자기 추측으로 날짜
            # 답변 → "현재 날짜인 2026년 3월 5일 기준으로 부산 사하구의 날씨 정보"
            # 같은 hallucination. _DYNAMIC_BOUNDARY_MARKER 뒤는 prompt-cache의
            # dynamic-context section 이므로 여기에 today 주입해도 cache prefix
            #
            # UMMAYA hotfix (2026-05-04, KMA base_time hallucination 차단):
            # `오늘 날짜 (UTC)` 만 inject 하면 LLM 이 KMA `base_time` (KST HHMM)
            # 을 추측 (e.g. `0700`). KMA 단기예보/실황 발표 시각은 KST
            # 0200/0500/0800/1100/1400/1700/2000/2300 — 잘못된 base_time 은
            # 4-9 시간 시차의 fabrication 으로 이어짐. 시민 안전 directive 위반.
            # 따라서 KST 날짜 + KST 현재 시각 (HH:MM, HHMM) 둘 다 inject —
            # 도구 description 이 "직전 정시" 를 참조할 수 있도록.
            # invariant 유지. ISO 8601 date format (YYYY-MM-DD) 으로 표기.
            from zoneinfo import ZoneInfo  # noqa: PLC0415

            _kst = ZoneInfo("Asia/Seoul")
            _now_kst = datetime.now(tz=_kst)
            today_kst_iso = _now_kst.strftime("%Y-%m-%d")
            now_kst_hm = _now_kst.strftime("%H:%M")
            now_kst_hhmm = _now_kst.strftime("%H%M")
            # KMA 단기예보는 하루 8회 발표, 초단기실황은 매시 관측이다.
            # 두 규칙을 분리해 주입해야 현재관측 도구가 단기예보 슬롯을
            # 복사하지 않는다.
            _kma_base_date, _kma_base_time, _kma_hint_note = _kma_forecast_base_slot_hint(_now_kst)
            (
                _kma_obs_base_date,
                _kma_obs_base_time,
                _kma_obs_hint_note,
            ) = _kma_observation_base_slot_hint(_now_kst)
            augmented_system = (
                augmented_system + f"\n\n## Current session context\n\n"
                f"오늘 날짜 (KST): {today_kst_iso}.\n"
                f"현재 시각 (KST): {now_kst_hm} ({now_kst_hhmm}).\n"
                "이 날짜/시각을 기준으로 시간 표현을 해석합니다. "
                "날짜/시간 정보를 추측 또는 fabricate 하지 말고, "
                "필요하면 도구 (예: kma_short_term_forecast) 를 호출해서 "
                "실제 데이터를 받아 응답에 인용합니다.\n"
                "KMA 단기예보 발표 시각은 KST 정시 8회: "
                "0200/0500/0800/1100/1400/1700/2000/2300. "
                f"현재 KST 시각의 단기예보 직전 발표는 {_kma_hint_note} "
                f"base_date={_kma_base_date}, base_time={_kma_base_time}. "
                "KMA 초단기실황 관측 기준은 매시 HH00; :40 전이면 "
                "한 시간 더 이전이 안정. "
                f"현재 KST 시각의 초단기실황 권장 기준은 {_kma_obs_hint_note} "
                f"base_date={_kma_obs_base_date}, base_time={_kma_obs_base_time}. "
                "base_time 추측 금지 — 위 hint 또는 그 이전 정시 사용.\n"
            )

            # Spec 2521 (2026-05-01) — BM25 adapter discovery is a backend
            # function, NOT an LLM-callable tool. Run the search against the
            # latest citizen utterance and inject the top-K candidates into
            # the dynamic suffix as ``<available_adapters>``. The LLM picks
            # a tool_id from this block and calls ``find({tool_id, params})``
            # — search-mode calls were the source of the "● find(search:)"
            # phantom tool-UI noise that user surfaced via Layer 5 frame
            # capture (specs/2521 frames/raw.cast frame_0160 onwards).
            try:
                for m in reversed(frame.messages):
                    if m.role == "user" and m.content:
                        latest_user_utt = m.content
                        break
                # spec-multi-turn-contamination diagnostic emit — log the
                # extracted latest user utterance BEFORE the BM25 suffix
                # builder runs. If this string disagrees with the wire-level
                # tail in [CHAT_REQUEST_DUMP] above, the bug is in the
                # extraction loop; if both agree but the model reasons over
                # an older turn, the bug is in K-EXAONE / Hermes (H2/H3).
                if _diag_chat_request_enabled():
                    logger.info(
                        "[LATEST_USER_UTT] turn=%d utt_first256=%s",
                        _diag_turn_idx,
                        (latest_user_utt or "")[:256],
                    )
                if latest_user_utt:
                    suffix_block = _build_available_adapters_suffix(latest_user_utt)
                    if suffix_block:
                        augmented_system = augmented_system + "\n\n" + suffix_block + "\n"
            except Exception:  # noqa: BLE001 — fail-open per FR-002
                logger.exception(
                    "available_adapters auto-inject failed — continuing without suffix"
                )
        llm_messages: list[LLMChatMessage] = []
        if augmented_system:
            llm_messages.append(LLMChatMessage(role="system", content=augmented_system))
        for m in frame.messages:
            # Epic #2152 R3 — wrap citizen utterances in <citizen_request>
            # XML tags so prompt-injection-shaped pastes cannot escalate into
            # instructions (contract chat-request-envelope.md I-C3, I-C4, I-C6).
            content = m.content
            if m.role == "user" and content:
                content = wrap_citizen_request(content)
            # Lead-Diag-4 (2026-05-04, role='tool' wire conversion) — forward
            # the wire-side ``tool_calls`` array (assistant turns that
            # requested one or more tool invocations) into the LLMClient
            # message so the OpenAI multi-turn pairing invariant survives the
            # round-trip. Backward compat: ``m.tool_calls`` is ``None`` for
            # legacy senders that pre-date the wire-format extension, in
            # which case we omit the field entirely (LLMChatMessage default
            # is ``None``).
            llm_tool_calls: list[LLMToolCall] | None = None
            if m.tool_calls:
                llm_tool_calls = [
                    LLMToolCall(
                        id=tc.id,
                        type=tc.type,
                        function=LLMFunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                    for tc in m.tool_calls
                ]
            llm_messages.append(
                LLMChatMessage(
                    role=m.role,
                    content=content,
                    name=m.name,
                    tool_call_id=m.tool_call_id,
                    tool_calls=llm_tool_calls,
                )
            )

        client = await _ensure_llm_client()

        # ---- CC query-engine agentic loop ---------------------------------
        import json as _json  # noqa: PLC0415

        # Epic #2152 follow-up — citizen-facing stream gate. K-EXAONE may
        # interleave a textual ``<tool_call>{...}</tool_call>`` marker with
        # the natural-language reply even when the structured ``tool_calls``
        # field is also populated, so the marker leaks into the streamed
        # AssistantChunkFrame content unless filtered. The gate strips those
        # blocks character-accurately while ``assistant_text_chunks`` still
        # accumulates the *full raw stream* — the post-stream
        # ``extract_textual_tool_calls`` fallback (below) needs the markers
        # to synthesise tool_call_buf entries when the structured form is
        # absent.
        from ummaya.llm.tool_call_parser import StreamGate  # noqa: PLC0415

        # Routing-observation flags — validation gates may reject a bad
        # primitive call and add a repair observation to the conversation.
        # These flags only keep the loop alive for another free-choice model
        # turn; they no longer force OpenAI/Friendli tool_choice.
        force_locate_next_turn = False
        force_verify_next_turn: str | None = None
        force_lookup_next_turn: str | None = None
        force_submit_next_turn: str | None = None
        force_no_tools_next_turn = False
        continue_free_next_turn = False
        mock_disclosure_required = False
        mock_primitives_seen: set[str] = set()
        verify_choice_mismatch_count = 0
        empty_final_retry_count = 0
        duplicate_nonprogress_count = 0

        for _turn in range(_AGENTIC_LOOP_MAX_TURNS):
            message_id = str(uuid.uuid4())
            assistant_text_chunks: list[str] = []
            # Epic #2766 issue B — render-order fix. K-EXAONE emits the
            # assistant's prose preamble ("내과 병원을 검색해 보겠습니다.")
            # BEFORE the structured ``tool_call_delta`` events arrive in the
            # SAME turn. If we forward those prose chunks immediately, the
            # citizen sees ``assistant text → tool_call → result``, the
            # opposite of CC's canonical ``tool_call → result → assistant
            # text`` order. The fix: buffer prose chunks for this turn; emit
            # them as a single AssistantChunkFrame ONLY after we know whether
            # this turn invoked tools. When tools are invoked we suppress the
            # preamble entirely — the next turn produces the real answer
            # after the tool result is appended to context. When no tools
            # are invoked we flush the buffer as a single chunk so the prose
            # still reaches the citizen.
            buffered_visible: list[str] = []
            tool_call_buf: dict[int, dict[str, str]] = {}
            stream_error: Exception | None = None
            stream_gate = StreamGate()

            def _append_tool_routing_observation(reason: str, message: str) -> None:
                """Add a non-tool observation so the model chooses the next call."""
                llm_messages.append(
                    LLMChatMessage(
                        role="user",
                        content=(
                            "[UMMAYA TOOL ROUTING OBSERVATION]\n"
                            f"{message}\n"
                            "Use the available tool descriptions and adapter metadata to "
                            "choose the next primitive call yourself. Do not answer from "
                            "memory when the observation says a tool prerequisite is missing."
                        ),
                    )
                )
                logger.warning(
                    "_handle_chat_request: %s. Re-entering loop with free tool_choice.",
                    reason,
                )

            def _append_final_answer_observation(reason: str, message: str) -> None:
                """Ask the model to finish from observed results without more tools."""
                nonlocal force_no_tools_next_turn
                force_no_tools_next_turn = True
                llm_messages.append(
                    LLMChatMessage(
                        role="user",
                        content=_final_answer_observation_message(
                            message=message,
                            latest_user_utt=latest_user_utt,
                            llm_messages=llm_messages,
                        ),
                    )
                )
                logger.warning(
                    "_handle_chat_request: %s. Re-entering loop without tool definitions.",
                    reason,
                )

            # spec-multi-turn-contamination diagnostic — accumulate the K-EXAONE
            # reasoning_content stream so we can compare its first 1024 bytes
            # against [LATEST_USER_UTT]. If reasoning starts with text that
            # paraphrases an earlier turn, H2 (model-side state contamination)
            # is confirmed even when the wire-level messages are correct.
            # Off by default; gated by UMMAYA_CHAT_REQUEST_DUMP=1.
            _diag_reasoning_buf: list[str] = []
            _diag_reasoning_emitted = False

            # Gate flags now add observations to the model context but do not
            # force a root tool at the API layer. The model must choose the
            # primitive + adapter from tool descriptions and <available_adapters>;
            # runtime validation rejects mismatches.
            stream_tool_choice: str | dict[str, object] | None = None
            stream_tools: list[LLMToolDefinition] | None = llm_tools or None
            no_tools_this_turn = False
            if force_no_tools_next_turn:
                stream_tools = None
                no_tools_this_turn = True
                force_no_tools_next_turn = False
            elif (
                force_locate_next_turn
                or force_verify_next_turn is not None
                or force_lookup_next_turn is not None
                or force_submit_next_turn is not None
            ):
                logger.warning(
                    "_handle_chat_request: continuing turn %d with free tool_choice "
                    "after validation gate hint (locate=%s check=%s find=%s send=%s)",
                    _turn,
                    force_locate_next_turn,
                    force_verify_next_turn,
                    force_lookup_next_turn,
                    force_submit_next_turn,
                )
            try:
                async for event in client.stream(  # type: ignore[attr-defined]
                    messages=llm_messages,
                    tools=stream_tools,
                    temperature=frame.temperature,
                    top_p=frame.top_p,
                    max_tokens=_effective_chat_max_tokens(frame.max_tokens),
                    tool_choice=stream_tool_choice,
                ):
                    event_type = getattr(event, "type", None)
                    if event_type == "content_delta":
                        delta = getattr(event, "content", "") or ""
                        if delta:
                            assistant_text_chunks.append(delta)
                            visible = stream_gate.feed(delta)
                            if visible:
                                buffered_visible.append(visible)
                    elif event_type == "thinking_delta":
                        # K-EXAONE chain-of-thought channel — mirrors CC's
                        # Anthropic ``thinking_delta`` content_block_delta
                        # (``ummaya/llm/_cc_reference/claude.ts:2148-2161``).
                        # Forward as an AssistantChunkFrame on the
                        # ``thinking`` channel; the TUI's deps.ts projects
                        # this to a ``stream_event{thinking_delta}`` and
                        # ``handleMessageFromStream`` routes it via
                        # ``onUpdateLength`` into ``streamingThinking`` so
                        # ``AssistantThinkingMessage`` paints the reasoning
                        # inline. CoT is *not* appended to
                        # ``assistant_text_chunks`` — the inline-tool-call
                        # XML parser only inspects the visible answer
                        # channel, and we never persist reasoning back to
                        # the LLM context.
                        thinking_text = getattr(event, "thinking", "") or ""
                        if thinking_text:
                            # spec-multi-turn-contamination diagnostic —
                            # accumulate reasoning until 1024 bytes, then
                            # emit once per turn. Bounded buffer (cap at 4096
                            # so a runaway CoT can't eat memory).
                            if (
                                _diag_chat_request_enabled()
                                and not _diag_reasoning_emitted
                                and sum(len(s) for s in _diag_reasoning_buf) < 4096
                            ):
                                _diag_reasoning_buf.append(thinking_text)
                                _running_len = sum(len(s) for s in _diag_reasoning_buf)
                                if _running_len >= 1024:
                                    _preview = "".join(_diag_reasoning_buf)[:1024]
                                    logger.info(
                                        "[REASONING_PREVIEW] turn=%d first1024=%s",
                                        _diag_turn_idx,
                                        _preview,
                                    )
                                    _diag_reasoning_emitted = True
                            await write_frame(
                                AssistantChunkFrame(
                                    session_id=frame.session_id,
                                    correlation_id=frame.correlation_id,
                                    role="llm",
                                    ts=_utcnow(),
                                    kind="assistant_chunk",
                                    message_id=message_id,
                                    delta="",
                                    thinking=thinking_text,
                                    done=False,
                                )
                            )
                    elif event_type == "tool_call_delta":
                        if no_tools_this_turn:
                            continue
                        idx = int(getattr(event, "tool_call_index", 0) or 0)
                        slot = tool_call_buf.setdefault(idx, {"id": "", "name": "", "args": ""})
                        cid = getattr(event, "tool_call_id", None)
                        if cid:
                            slot["id"] = cid
                        fname = getattr(event, "function_name", None)
                        if fname:
                            slot["name"] = fname
                        fargs = getattr(event, "function_args_delta", None)
                        if fargs:
                            slot["args"] += fargs
                    elif event_type == "done":
                        # spec-multi-turn-contamination diagnostic — flush a
                        # short reasoning buffer (<1024 bytes) on stream
                        # completion so the [REASONING_PREVIEW] line is
                        # emitted exactly once per turn even when the model
                        # produced little CoT.
                        if (
                            _diag_chat_request_enabled()
                            and not _diag_reasoning_emitted
                            and _diag_reasoning_buf
                        ):
                            _preview = "".join(_diag_reasoning_buf)[:1024]
                            logger.info(
                                "[REASONING_PREVIEW] turn=%d first1024=%s",
                                _diag_turn_idx,
                                _preview,
                            )
                            _diag_reasoning_emitted = True
                        break
                    elif event_type == "error":
                        stream_error = RuntimeError(
                            str(getattr(event, "content", "unknown stream error"))
                        )
                        break
            except Exception as exc:  # noqa: BLE001
                stream_error = exc

            # Drain any pending bytes the stream gate held back at stream end.
            # ``flush()`` returns the safe trailing window (i.e. bytes that
            # were too short to disambiguate during streaming but are now
            # known not to be the start of a ``<tool_call>`` marker).
            tail = stream_gate.flush()
            if tail:
                buffered_visible.append(tail)

            if stream_error is not None:
                # Schema constraint: ErrorFrame.role ∈ {'backend','tui'} —
                # 'llm' was rejected by Pydantic validation. Backend is the
                # correct sender role since this frame originates from the
                # backend's own LLM-stream error handler.
                await write_frame(
                    ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="llm_stream_error",
                        message=str(stream_error),
                        details={"message_id": message_id},
                    )
                )
                return

            # Epic #2152 follow-up — K-EXAONE on FriendliAI sometimes emits
            # its tool-call intent as a textual ``<tool_call>{...}</tool_call>``
            # marker inside the assistant content rather than the OpenAI
            # ``tool_calls`` field. Extract any such markers from the
            # accumulated turn text and synthesise ``tool_call_buf`` entries so
            # the existing dispatch path picks them up as if the model had used
            # the structured form. The cleaned text (markers stripped) is what
            # we record into the assistant history for the next turn.
            assistant_text_full = "".join(assistant_text_chunks)
            cleaned_text = assistant_text_full
            if (
                not no_tools_this_turn
                and not tool_call_buf
                and "<tool_call>" in assistant_text_full
            ):
                from ummaya.llm.tool_call_parser import (  # noqa: PLC0415
                    extract_textual_tool_calls,
                )

                parsed_calls, cleaned_text = extract_textual_tool_calls(assistant_text_full)
                for synth_idx, parsed in enumerate(parsed_calls):
                    tool_call_buf[synth_idx] = {
                        "id": str(uuid.uuid4()),
                        "name": parsed.name,
                        "args": _json.dumps(parsed.arguments, ensure_ascii=False),
                    }
                if parsed_calls:
                    logger.info(
                        "_handle_chat_request: synthesised %d tool_call(s) from "
                        "K-EXAONE textual <tool_call> markers (Epic #2152 follow-up)",
                        len(parsed_calls),
                    )

            # Epic #2766 issue B — render-order fix flush.
            # No tool calls this turn → emit the FULL buffered prose as a
            # single chunk (or empty) before the terminal done=True frame.
            # The TUI's StreamingMarkdown accumulates `delta` over the
            # message_id, so emitting the full text in one chunk yields the
            # same visible result as the per-chunk streaming would have —
            # only the perceived latency changes (full text appears at
            # end-of-turn rather than typewriter-streamed). This is the
            # cost of the ordering guarantee: until end-of-stream we cannot
            # know whether a tool_call follows in this turn.
            if not tool_call_buf:
                location_gate_msg = _check_location_terminated_without_resolve(
                    llm_messages, latest_user_utt
                )
                if location_gate_msg is not None:
                    _append_tool_routing_observation(
                        (
                            "rejected final-answer turn - location-like request "
                            "terminated without locate"
                        ),
                        location_gate_msg,
                    )
                    buffered_visible.clear()
                    continue

                verify_gate = _check_verify_terminated_without_verify(llm_messages, latest_user_utt)
                if verify_gate is not None:
                    _append_tool_routing_observation(
                        (
                            "rejected final-answer turn - verify-required request "
                            "terminated without check"
                        ),
                        verify_gate["message"],
                    )
                    buffered_visible.clear()
                    continue

                submit_followup_gate = _check_submit_terminated_without_submit(
                    llm_messages,
                    latest_user_utt,
                    _session_auth_contexts.get(frame.session_id),
                )
                if submit_followup_gate is not None:
                    _append_tool_routing_observation(
                        (
                            "rejected final-answer turn - submit-class request "
                            "verified but ended without send"
                        ),
                        submit_followup_gate["message"],
                    )
                    buffered_visible.clear()
                    continue

                sensitive_lookup_followup_gate = _check_sensitive_lookup_terminated_without_lookup(
                    llm_messages,
                    latest_user_utt,
                    _session_auth_contexts.get(frame.session_id),
                )
                if sensitive_lookup_followup_gate is not None:
                    _append_tool_routing_observation(
                        (
                            "rejected final-answer turn - sensitive lookup request "
                            "verified but ended without find"
                        ),
                        sensitive_lookup_followup_gate["message"],
                    )
                    buffered_visible.clear()
                    continue

                # ---- G-class fabrication gate (2026-05-04) ---------------
                # Before emitting a final-answer turn, check whether the
                # conversation invoked locate but never followed up with a
                # registry-selected find adapter from the dynamic
                # <available_adapters> block. The donga-univ-poi-bug snap-001-01-kma-now
                # capture (2026-05-04) showed K-EXAONE producing 16°C / 84%
                # humidity by parametric memory — 4.7°C / 61%p drift versus
                # the raw KMA observation — because the agentic loop allowed
                # the answer turn to fire without a tool result in scope.
                # Add a chain-recovery observation and continue the loop so
                # the model chooses the missing follow-up find call itself.
                chain_followup_msg = _check_resolve_terminated_without_followup(
                    llm_messages, latest_user_utt
                )
                if chain_followup_msg is not None:
                    _append_tool_routing_observation(
                        "rejected final-answer turn — locate ran but follow-up find was missing",
                        chain_followup_msg,
                    )
                    # Drop the buffered prose so the citizen never sees the
                    # fabrication that the LLM was about to emit.
                    buffered_visible.clear()
                    continue

                current_weather_gate_msg = _check_current_weather_terminated_without_observation(
                    llm_messages,
                    latest_user_utt,
                )
                if current_weather_gate_msg is not None:
                    _append_tool_routing_observation(
                        "rejected final-answer turn — current weather answer missing observation",
                        current_weather_gate_msg,
                    )
                    buffered_visible.clear()
                    continue

                from ummaya.llm.tool_call_parser import (  # noqa: PLC0415
                    strip_leaked_thinking_markers,
                )

                merged_prose = strip_leaked_thinking_markers("".join(buffered_visible))
                if mock_disclosure_required:
                    merged_prose = _ensure_mock_disclosure(
                        merged_prose,
                        mock_primitives=mock_primitives_seen,
                    )
                else:
                    merged_prose = _remove_unneeded_mock_disclosure(merged_prose)
                    merged_prose = _remove_unneeded_live_meta_disclosure(merged_prose)
                has_successful_tool_result = _conversation_has_successful_any_primitive_result(
                    llm_messages
                )
                if not merged_prose.strip() and has_successful_tool_result:
                    if empty_final_retry_count < 2:
                        empty_final_retry_count += 1
                        _append_final_answer_observation(
                            "rejected empty final-answer turn after successful tool result",
                            (
                                "The previous assistant turn produced no citizen-facing text "
                                "after successful tool results. Produce a concise Korean final "
                                "answer using the latest successful tool_result."
                            ),
                        )
                        buffered_visible.clear()
                        continue
                    await write_frame(
                        ErrorFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id or str(uuid.uuid4()),
                            role="backend",
                            ts=_utcnow(),
                            kind="error",
                            code="empty_final_answer_after_tool_result",
                            message=(
                                "Model returned an empty final answer after successful "
                                "tool results. No synthetic answer was generated."
                            ),
                            details={"retry_count": empty_final_retry_count},
                        )
                    )
                    return
                if (
                    merged_prose.strip()
                    and has_successful_tool_result
                    and _final_answer_looks_like_generic_retry_after_success(merged_prose)
                    and empty_final_retry_count < 2
                ):
                    empty_final_retry_count += 1
                    _append_final_answer_observation(
                        "rejected generic retry final answer after successful tool result",
                        (
                            "The previous assistant turn ignored successful tool results "
                            "and gave a generic retry/handoff answer. Produce a concise "
                            "Korean final answer using the latest successful tool_result. "
                            "For KMA current observation results, include concrete returned "
                            "values such as temperature, precipitation, humidity, wind, "
                            "and the observation base time when present. Do not ask the "
                            "citizen to retry unless the successful tool_result is "
                            "insufficient for the request."
                        ),
                    )
                    buffered_visible.clear()
                    continue
                if (
                    merged_prose.strip()
                    and has_successful_tool_result
                    and _final_answer_missing_current_weather_observation_values(
                        merged_prose,
                        llm_messages,
                        latest_user_utt,
                    )
                    and empty_final_retry_count < 2
                ):
                    empty_final_retry_count += 1
                    _append_final_answer_observation(
                        "rejected current-weather final answer missing KMA values",
                        (
                            "The previous assistant turn had a successful "
                            "kma_current_observation tool_result but omitted the returned "
                            "observation values. Produce a concise Korean final answer "
                            "that cites the current temperature, precipitation, humidity, "
                            "wind, and observation base time from that tool_result."
                        ),
                    )
                    buffered_visible.clear()
                    continue
                if (
                    merged_prose.strip()
                    and has_successful_tool_result
                    and _final_answer_looks_like_pending_tool_plan(merged_prose)
                    and empty_final_retry_count < 2
                ):
                    empty_final_retry_count += 1
                    _append_final_answer_observation(
                        "rejected pending-tool-plan final answer after successful tool result",
                        (
                            "The previous assistant turn described a future tool call "
                            "after successful tool results were already available. "
                            "Produce a concise Korean final answer using the latest "
                            "successful tool_result. Include concrete returned values "
                            "when present. Do not say you will call or look up another "
                            "tool unless additional data is essential."
                        ),
                    )
                    buffered_visible.clear()
                    continue
                if (
                    merged_prose.strip()
                    and has_successful_tool_result
                    and _final_answer_looks_like_recursive_tool_message(merged_prose)
                    and empty_final_retry_count < 2
                ):
                    empty_final_retry_count += 1
                    _append_final_answer_observation(
                        "rejected recursive tool-message final answer after successful tool result",
                        (
                            "The previous assistant turn recursively quoted the phrase "
                            "'도구가 반환한 메시지' instead of answering. Ignore previous "
                            "error-wrapper prose and produce a concise Korean final answer "
                            "using the latest successful tool_result. Include concrete "
                            "returned values when present. Do not quote tool error wrappers."
                        ),
                    )
                    buffered_visible.clear()
                    continue
                if (
                    merged_prose.strip()
                    and has_successful_tool_result
                    and _final_answer_looks_like_unclosed_markdown(merged_prose)
                    and empty_final_retry_count < 2
                ):
                    empty_final_retry_count += 1
                    _append_final_answer_observation(
                        "rejected unclosed markdown final answer after successful tool result",
                        (
                            "The previous assistant turn ended with an unclosed Markdown "
                            "emphasis marker. Produce the same concise Korean final answer "
                            "using the latest successful tool_result, but finish the prose "
                            "cleanly and remove any dangling formatting markers."
                        ),
                    )
                    buffered_visible.clear()
                    continue
                if (
                    merged_prose.strip()
                    and has_successful_tool_result
                    and _final_answer_looks_like_incomplete_sentence(merged_prose)
                    and empty_final_retry_count < 2
                ):
                    empty_final_retry_count += 1
                    _append_final_answer_observation(
                        "rejected incomplete final sentence after successful tool result",
                        (
                            "The previous assistant turn ended with a dangling "
                            "connective or punctuation mark. Produce one concise "
                            "Korean final answer using the latest successful "
                            "tool_result, and finish the sentence cleanly."
                        ),
                    )
                    buffered_visible.clear()
                    continue
                if (
                    merged_prose.strip()
                    and has_successful_tool_result
                    and _final_answer_looks_like_tool_call_narration(merged_prose)
                    and empty_final_retry_count < 2
                ):
                    empty_final_retry_count += 1
                    _append_final_answer_observation(
                        "rejected tool-call narration final answer after successful tool result",
                        (
                            "The previous assistant turn narrated internal tool calls "
                            "to the citizen. Produce a concise Korean final answer that "
                            "starts with the requested result, not with tool-operation "
                            "history. You may cite official data sources, but do not say "
                            "which internal tools were called."
                        ),
                    )
                    buffered_visible.clear()
                    continue
                if (
                    merged_prose.strip()
                    and has_successful_tool_result
                    and _final_answer_looks_like_repeated_sections(merged_prose)
                    and empty_final_retry_count < 2
                ):
                    empty_final_retry_count += 1
                    _append_final_answer_observation(
                        "rejected repeated-section final answer after successful tool result",
                        (
                            "The previous assistant turn repeated the same final-answer "
                            "sections. Produce one concise Korean final answer using the "
                            "latest successful tool_result. Do not repeat headings, "
                            "summaries, or conclusion blocks, and do not include meta "
                            "commentary about the runtime being real, simulated, virtual, "
                            "or not virtual unless a mock disclosure is required."
                        ),
                    )
                    buffered_visible.clear()
                    continue
                if merged_prose:
                    await write_frame(
                        AssistantChunkFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="llm",
                            ts=_utcnow(),
                            kind="assistant_chunk",
                            message_id=message_id,
                            delta=merged_prose,
                            done=False,
                        )
                    )
                await write_frame(
                    AssistantChunkFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="llm",
                        ts=_utcnow(),
                        kind="assistant_chunk",
                        message_id=message_id,
                        delta="",
                        done=True,
                    )
                )
                return
            # Tool calls present → suppress the prose preamble entirely.
            # The next agentic-loop turn will produce the real answer after
            # appending tool_result to context. CC-style ordering preserved:
            # `tool_call → tool_result → final assistant prose`.
            buffered_visible.clear()

            # ---- T027/T029 — emit tool_call frames + register Futures -----
            loop = asyncio.get_event_loop()
            issued_calls: list[tuple[str, str]] = []  # (call_id, name)
            assistant_tool_calls: list[LLMToolCall] = []
            tool_call_indices = sorted(tool_call_buf.keys())
            if len(tool_call_indices) > 1:
                selected_idx = tool_call_indices[0]
                dropped = tool_call_indices[1:]
                logger.warning(
                    "_handle_chat_request: received %d tool calls in one LLM turn; "
                    "dispatching index %s only and dropping indices %s to enforce "
                    "one observed tool result per turn",
                    len(tool_call_indices),
                    selected_idx,
                    dropped,
                )
                tool_call_indices = [selected_idx]
            for idx in tool_call_indices:
                slot = tool_call_buf[idx]
                call_id = slot["id"] or str(uuid.uuid4())
                try:
                    args_obj = _json.loads(slot["args"]) if slot["args"] else {}
                except _json.JSONDecodeError:
                    args_obj = {"_raw": slot["args"]}
                if not isinstance(args_obj, dict):
                    args_obj = {"_value": args_obj}

                fname = slot["name"]
                args_obj = _maybe_reroute_locate_admin_keyword_args(fname, args_obj)
                args_obj = _normalize_lookup_args_for_query(fname, args_obj, latest_user_utt)
                args_obj = _normalize_verify_args_for_query(fname, args_obj, latest_user_utt)
                args_obj = _normalize_verify_tool_id_for_query(fname, args_obj, latest_user_utt)
                args_obj = _normalize_submit_args_for_query(fname, args_obj, latest_user_utt)
                if fname == "find":
                    tool_id_for_schema = str(args_obj.get("tool_id") or "")
                    adapter_param_names: set[str] | None = None
                    if tool_id_for_schema:
                        try:
                            adapter_tool = registry.find(tool_id_for_schema)
                            adapter_param_names = set(adapter_tool.input_schema.model_fields)
                        except Exception:  # noqa: BLE001
                            adapter_param_names = None
                    args_obj = _normalize_lookup_args_for_query(
                        fname,
                        args_obj,
                        latest_user_utt,
                        adapter_param_names=adapter_param_names,
                    )
                # Epic #2077 FR-003 — registry-derived whitelist. spec.md
                # § Out of Scope (Permanent) forbids hardcoded enumerations
                # outside the registry; ``PRIMITIVE_REGISTRY`` is the single
                # source of truth for LLM-visible primitive names.
                from ummaya.primitives import PRIMITIVE_REGISTRY  # noqa: PLC0415

                if fname not in PRIMITIVE_REGISTRY:
                    await write_frame(
                        ErrorFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id or str(uuid.uuid4()),
                            role="backend",
                            ts=_utcnow(),
                            kind="error",
                            code="unknown_tool",
                            message=f"Model requested unknown tool {fname!r}",
                            details={"call_id": call_id},
                        )
                    )
                    continue

                resolve_redirect = _location_independent_resolve_redirect_for_query(
                    fname,
                    latest_user_utt,
                )
                if resolve_redirect is not None:
                    primitive = resolve_redirect["primitive"]
                    if primitive == "check":
                        force_verify_next_turn = resolve_redirect["tool_id"]
                    elif primitive == "send":
                        force_submit_next_turn = resolve_redirect["tool_id"]
                    elif primitive == "find":
                        force_lookup_next_turn = resolve_redirect["tool_id"]
                    else:
                        continue_free_next_turn = True
                    logger.warning(
                        "_handle_chat_request: suppressed irrelevant locate "
                        "call_id=%s for location-independent workflow; next=%s:%s",
                        call_id[:12],
                        primitive,
                        resolve_redirect["tool_id"],
                    )
                    continue

                duplicate_submit_msg = _check_duplicate_submit_prerequisite(
                    fname,
                    args_obj,
                    llm_messages,
                )
                if duplicate_submit_msg is not None:
                    from ummaya.ipc.frame_schema import (  # noqa: PLC0415
                        ToolResultEnvelope,
                        ToolResultFrame,
                    )

                    await write_frame(
                        ToolCallFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_call",
                            call_id=call_id,
                            name=fname,  # type: ignore[arg-type]
                            arguments=args_obj,
                        )
                    )
                    err_envelope = ToolResultEnvelope.model_validate(
                        {
                            "kind": cast("Any", fname),
                            "result": {
                                "kind": "error",
                                "reason": "submit_already_succeeded",
                                "message": duplicate_submit_msg,
                                "retryable": False,
                            },
                        }
                    )
                    await write_frame(
                        ToolResultFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_result",
                            call_id=call_id,
                            envelope=err_envelope,
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=fname,
                                        arguments=_json.dumps(args_obj),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "submit_already_succeeded",
                                    "message": duplicate_submit_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    continue_free_next_turn = True
                    logger.warning(
                        "_handle_chat_request: rejected duplicate submit "
                        "call_id=%s after prior success",
                        call_id[:12],
                    )
                    continue

                if _conversation_has_successful_identical_primitive_call(
                    llm_messages,
                    primitive=fname,
                    args=args_obj,
                ):
                    duplicate_nonprogress_count += 1
                    logger.warning(
                        "_handle_chat_request: suppressed duplicate non-progress "
                        "%s call_id=%s after successful identical result",
                        fname,
                        call_id[:12],
                    )
                    _append_final_answer_observation(
                        (
                            "suppressed duplicate primitive call after successful "
                            "identical tool_result"
                        ),
                        (
                            "The same primitive call with the same arguments already "
                            "returned a successful tool_result. Do not call it again. "
                            "Produce the citizen-facing final answer from the latest "
                            "successful tool_result."
                        ),
                    )
                    continue_free_next_turn = True
                    continue

                unrequested_verify_msg = _check_unrequested_verify_after_public_find(
                    fname,
                    llm_messages,
                    latest_user_utt,
                )
                if unrequested_verify_msg is not None:
                    logger.warning(
                        "_handle_chat_request: suppressed unrequested %s "
                        "call_id=%s after successful public find",
                        fname,
                        call_id[:12],
                    )
                    _append_final_answer_observation(
                        "suppressed unrequested check after successful public find",
                        unrequested_verify_msg,
                    )
                    continue_free_next_turn = True
                    continue

                # Chain prerequisite gate — donga-univ-poi-bug Epic #2766.
                # CC mirror: ``Tool.validateInput?(input, context)`` from
                # ``.references/claude-code-sourcemap/restored-src/src/Tool.ts:489``
                # — tool-scoped prerequisite hook that inspects the
                # surrounding ToolUseContext and may reject with a
                # message the LLM sees as a validation observation. UMMAYA port:
                # we run the check here, before issuing the ToolCallFrame
                # and before the dispatch task starts, so a rejected call
                # never burns an outbound HTTP request and the LLM gets a
                # deterministic chain-recovery instruction without painting
                # a recoverable internal routing error in the citizen UI.
                #
                # Concretely: when fname == "find" + the chosen tool_id
                # is a coordinate/admcd-input adapter (kma_*, hira_*, nmc_*,
                # koroad_*) AND the citizen-supplied params already carry
                # the coordinates AND no prior turn in llm_messages
                # invoked locate, that means the LLM guessed
                # the coordinates from prior knowledge instead of routing
                # through the canonical resolver. Three live captures
                # under specs/integration-verification/donga-univ-poi-bug/
                # showed this exact pattern producing wrong-region
                # hospital lists. Rejecting here forces the next turn
                # through locate.
                chain_error_msg = _check_chain_prerequisite(
                    fname, args_obj, llm_messages, registry=_ensure_tool_registry()
                )
                if chain_error_msg is not None:
                    _append_tool_routing_observation(
                        f"rejected {fname} call_id={call_id[:12]} — chain prerequisite missing",
                        chain_error_msg,
                    )
                    logger.warning(
                        "_handle_chat_request: rejected %s call_id=%s — chain prerequisite missing",
                        fname,
                        call_id[:12],
                    )
                    # Keep the loop alive for a free-choice repair turn.
                    force_locate_next_turn = True
                    continue

                verify_choice_gate = _check_verify_tool_choice_prerequisite(
                    fname,
                    args_obj,
                    latest_user_utt,
                )
                if verify_choice_gate is not None:
                    from ummaya.ipc.frame_schema import (  # noqa: PLC0415
                        ToolResultEnvelope,
                        ToolResultFrame,
                    )

                    await write_frame(
                        ToolCallFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_call",
                            call_id=call_id,
                            name=fname,  # type: ignore[arg-type]
                            arguments=args_obj,
                        )
                    )
                    err_envelope = ToolResultEnvelope.model_validate(
                        {
                            "kind": cast("Any", fname),
                            "result": {
                                "kind": "error",
                                "reason": "verify_tool_choice_mismatch",
                                "message": verify_choice_gate["message"],
                                "retryable": False,
                            },
                        }
                    )
                    await write_frame(
                        ToolResultFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_result",
                            call_id=call_id,
                            envelope=err_envelope,
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=fname,
                                        arguments=_json.dumps(args_obj),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "verify_tool_choice_mismatch",
                                    "message": verify_choice_gate["message"],
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    verify_choice_mismatch_count += 1
                    repeated_forced_verify_mismatch = (
                        force_verify_next_turn == verify_choice_gate["verify_tool_id"]
                    )
                    if repeated_forced_verify_mismatch or verify_choice_mismatch_count > 1:
                        expected_scopes = sorted(
                            {
                                item.strip()
                                for item in verify_choice_gate.get(
                                    "allowed_scopes",
                                    verify_choice_gate.get("scope", ""),
                                ).split(",")
                                if item.strip()
                            }
                        )
                        terminal_message = (
                            "Stopped because the verification tool and permission scope "
                            "do not match this request. This flow must use "
                            f"check(tool_id={verify_choice_gate['verify_tool_id']!r}, "
                            f"scope_list={expected_scopes!r}). "
                            "A delegation cannot be created while identity and submit "
                            "scopes are mixed."
                        )
                        await write_frame(
                            AssistantChunkFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="llm",
                                ts=_utcnow(),
                                kind="assistant_chunk",
                                message_id=message_id,
                                delta=terminal_message,
                                done=False,
                            )
                        )
                        await write_frame(
                            AssistantChunkFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="llm",
                                ts=_utcnow(),
                                kind="assistant_chunk",
                                message_id=message_id,
                                delta="",
                                done=True,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: terminal verify tool-choice "
                            "mismatch after forced retry for call_id=%s expected=%s",
                            call_id[:12],
                            verify_choice_gate["verify_tool_id"],
                        )
                        return
                    force_verify_next_turn = verify_choice_gate["verify_tool_id"]
                    logger.warning(
                        "_handle_chat_request: rejected %s call_id=%s — verify "
                        "tool-choice mismatch for latest user utterance",
                        fname,
                        call_id[:12],
                    )
                    continue

                sensitive_lookup_msg = _check_sensitive_lookup_auth_prerequisite(
                    fname,
                    args_obj,
                    _session_auth_contexts.get(frame.session_id),
                )
                if sensitive_lookup_msg is not None:
                    verify_redirect = _sensitive_lookup_verify_redirect_for_query(
                        fname,
                        args_obj,
                        latest_user_utt,
                        _session_auth_contexts.get(frame.session_id),
                    )
                    if verify_redirect is not None:
                        force_verify_next_turn = verify_redirect["verify_tool_id"]
                        logger.warning(
                            "_handle_chat_request: suppressed premature %s call_id=%s "
                            "and forced verify before sensitive lookup",
                            fname,
                            call_id[:12],
                        )
                        continue

                    from ummaya.ipc.frame_schema import (  # noqa: PLC0415
                        ToolResultEnvelope,
                        ToolResultFrame,
                    )

                    await write_frame(
                        ToolCallFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_call",
                            call_id=call_id,
                            name=fname,  # type: ignore[arg-type]
                            arguments=args_obj,
                        )
                    )
                    err_envelope = ToolResultEnvelope.model_validate(
                        {
                            "kind": cast("Any", fname),
                            "result": {
                                "kind": "error",
                                "reason": "auth_required",
                                "message": sensitive_lookup_msg,
                                "retryable": False,
                            },
                        }
                    )
                    await write_frame(
                        ToolResultFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_result",
                            call_id=call_id,
                            envelope=err_envelope,
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=fname,
                                        arguments=_json.dumps(args_obj),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "auth_required",
                                    "message": sensitive_lookup_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    requirement = _sensitive_lookup_requirement(args_obj)
                    force_verify_next_turn = (
                        requirement["verify_tool_id"] if requirement is not None else "check"
                    )
                    logger.warning(
                        "_handle_chat_request: rejected %s call_id=%s — sensitive "
                        "lookup auth prerequisite missing",
                        fname,
                        call_id[:12],
                    )
                    continue

                _pending_calls[call_id] = loop.create_future()
                issued_calls.append((call_id, fname))
                assistant_tool_calls.append(
                    LLMToolCall(
                        id=call_id,
                        type="function",
                        function=LLMFunctionCall(
                            name=fname,
                            arguments=_json.dumps(args_obj),
                        ),
                    )
                )
                await write_frame(
                    ToolCallFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="tool_call",
                        call_id=call_id,
                        name=fname,  # type: ignore[arg-type]
                        arguments=args_obj,
                    )
                )

                # Spec 1978 T053b — fire internal primitive dispatch as a
                # background task. The task resolves _pending_calls[call_id]
                # when the primitive returns, allowing the gather below to
                # proceed without waiting for an external tool_result frame.
                asyncio.create_task(
                    _dispatch_primitive(
                        call_id,
                        fname,
                        args_obj,
                        frame.session_id,
                        frame.correlation_id,
                    ),
                    name=f"primitive-{fname}-{call_id[:8]}",
                )

                # Neurosymbolic constraint — clear the force flag once a
                # locate turn has actually been dispatched. Any
                # subsequent turn returns to free tool_choice so the LLM
                # can route to the actual coord-input adapter (KMA/HIRA/
                # NMC) with the resolved coordinates.
                if fname == "locate":
                    force_locate_next_turn = False
                if fname == "check":
                    force_verify_next_turn = None
                if fname == "find":
                    force_lookup_next_turn = None
                if fname == "send":
                    force_submit_next_turn = None

            # If every tool call was rejected (whitelist), terminate.
            # Exception: when a validation gate fired (repair flag set), keep
            # the loop alive so the model gets one more free-choice turn.
            # Returning here would leave the citizen with the chain-error
            # tool_result frame as the only visible output.
            if not issued_calls:
                if (
                    force_locate_next_turn
                    or force_verify_next_turn is not None
                    or force_lookup_next_turn is not None
                    or force_submit_next_turn is not None
                    or continue_free_next_turn
                ):
                    if continue_free_next_turn:
                        continue_free_next_turn = False
                    # Synthetic tool_result already injected into
                    # llm_messages; the next loop iteration will fire the LLM
                    # again with tool_choice forced to the missing primitive.
                    continue
                await write_frame(
                    AssistantChunkFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="llm",
                        ts=_utcnow(),
                        kind="assistant_chunk",
                        message_id=message_id,
                        delta="",
                        done=True,
                    )
                )
                return

            # Append the assistant message that requested tools — the CC
            # query-engine contract requires the function-call envelope to
            # precede the tool messages in the next turn.
            #
            # Epic #2152 follow-up — record the *cleaned* text (markers
            # stripped) into the LLM history so subsequent turns don't see
            # the textual ``<tool_call>`` blocks and double-emit them. The
            # post-stream extractor above sets ``cleaned_text`` only when
            # it ran (i.e. tool_call_buf was empty + marker present); when
            # both structured tool_calls AND a textual marker were emitted
            # in the same turn, run the extractor here too so the marker is
            # stripped from history even though we don't synthesise an
            # additional tool_call_buf entry.
            if "<tool_call>" in cleaned_text:
                from ummaya.llm.tool_call_parser import (  # noqa: PLC0415
                    extract_textual_tool_calls,
                )

                _, cleaned_text = extract_textual_tool_calls(cleaned_text)
            llm_messages.append(
                LLMChatMessage(
                    role="assistant",
                    content=cleaned_text,
                    tool_calls=assistant_tool_calls,
                )
            )

            # ---- Await tool_result Futures (gated by T030 timeout) -------
            tasks = [_pending_calls[cid] for cid, _ in issued_calls]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=_TOOL_RESULT_TIMEOUT_S,
                )
            except TimeoutError:
                # Per contracts/tool-bridge-protocol.md timeout → synthetic
                # error result. Drop pending entries to avoid leaks.
                for cid, _ in issued_calls:
                    pending = _pending_calls.pop(cid, None)
                    if pending and not pending.done():
                        pending.cancel()
                await write_frame(
                    ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="tool_timeout",
                        message=(f"Tool result timeout after {_TOOL_RESULT_TIMEOUT_S:.0f}s"),
                        details={
                            "call_ids": [cid for cid, _ in issued_calls],
                        },
                    )
                )
                return

            # ---- Inject tool messages, continue agentic loop --------------
            terminal_permission_code: str | None = None
            verify_result_seen = False
            latest_find_collection_count: int | None = None
            for (cid, fname), result in zip(issued_calls, results, strict=False):
                if isinstance(result, BaseException):
                    payload = _json.dumps({"error": "tool_dispatch_failed", "detail": str(result)})
                else:
                    # ToolResultFrame.envelope is a Pydantic model.
                    envelope = getattr(result, "envelope", None)
                    if envelope is not None and hasattr(envelope, "model_dump"):
                        envelope_dump = envelope.model_dump()
                        if _contains_mock_marker(envelope_dump):
                            mock_disclosure_required = True
                            mock_primitives_seen.add(fname)
                        if fname == "find":
                            result_payload = envelope_dump.get("result")
                            if isinstance(result_payload, dict):
                                result_items = result_payload.get("items")
                                if isinstance(result_items, list):
                                    latest_find_collection_count = len(result_items)
                        payload = _json.dumps(
                            envelope_dump,
                            ensure_ascii=False,
                            default=str,
                        )
                        if envelope_dump.get("denied") is True and envelope_dump.get("error") in {
                            "permission_denied",
                            "permission_timeout",
                        }:
                            terminal_permission_code = str(envelope_dump["error"])
                    else:
                        payload = _json.dumps({"result": str(result)}, ensure_ascii=False)

                if terminal_permission_code is not None:
                    continue
                llm_messages.append(
                    LLMChatMessage(
                        role="tool",
                        content=payload,
                        name=fname,
                        tool_call_id=cid,
                    )
                )
                if fname == "check":
                    verify_result_seen = True

            if terminal_permission_code is not None:
                if terminal_permission_code == "permission_timeout":
                    denial_message = (
                        "Permission response timed out. No follow-up submit or "
                        "subscription action was executed. "
                        "(code: permission_timeout)"
                    )
                else:
                    denial_message = (
                        "Permission request was denied. No follow-up submit or "
                        "subscription action was executed. "
                        "(code: permission_denied)"
                    )
                logger.info(
                    "_handle_chat_request: terminating agentic loop after terminal "
                    "permission decision code=%s",
                    terminal_permission_code,
                )
                await write_frame(
                    AssistantChunkFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="llm",
                        ts=_utcnow(),
                        kind="assistant_chunk",
                        message_id=str(uuid.uuid4()),
                        delta=denial_message,
                        done=False,
                    )
                )
                await write_frame(
                    AssistantChunkFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="llm",
                        ts=_utcnow(),
                        kind="assistant_chunk",
                        message_id=str(uuid.uuid4()),
                        delta="",
                        done=True,
                    )
                )
                return

            if any(fname == "find" for _, fname in issued_calls):
                requested_result_count = _explicit_result_count_from_query(latest_user_utt)
                if (
                    requested_result_count is not None
                    and latest_find_collection_count is not None
                    and latest_find_collection_count >= requested_result_count
                ):
                    _append_final_answer_observation(
                        "latest find result satisfies citizen-requested result count",
                        (
                            "The latest successful find tool_result already contains "
                            f"at least the requested {requested_result_count} result(s). "
                            "Answer with exactly that requested count from the latest "
                            "tool_result, preserving returned names, addresses, phone "
                            "numbers, distances, and source timestamps when present."
                        ),
                    )
                    continue
                call_summaries: list[dict[str, object]] = []
                for tool_call in assistant_tool_calls:
                    call_summaries.append(
                        {
                            "name": tool_call.function.name,
                            "arguments": _tool_call_arguments_dict(tool_call),
                        }
                    )
                last_tool_calls_json = _json.dumps(
                    call_summaries,
                    ensure_ascii=False,
                    default=str,
                )
                checkpoint = (
                    "Internal tool-use checkpoint before final answer. Compare the "
                    "citizen_request with the just-completed tool call arguments and "
                    "the selected adapter schema in <available_adapters>. If the "
                    "citizen request includes an explicit narrowing condition and "
                    "the adapter exposes a matching optional parameter, that condition "
                    "must be present in params before final prose. Examples of "
                    "narrowing conditions are requested result count, radius/distance, "
                    "date/time, institution type, category, specialty/department, "
                    "keyword, and administrative region. If the last find call was "
                    "broader than the citizen request, do not answer from that broad "
                    "collection; call the same adapter again with corrected "
                    "schema-valid params. If the tool call already preserves all "
                    "explicit citizen constraints, answer concisely from the latest "
                    "tool_result only. "
                    f"citizen_request={latest_user_utt!r}; "
                    f"last_tool_calls={last_tool_calls_json}"
                )
                llm_messages.append(LLMChatMessage(role="system", content=checkpoint))

            if verify_result_seen:
                submit_followup_gate = _check_submit_terminated_without_submit(
                    llm_messages,
                    latest_user_utt,
                    _session_auth_contexts.get(frame.session_id),
                )
                if submit_followup_gate is not None:
                    _append_tool_routing_observation(
                        "verify completed for submit-class request and no send tool call followed",
                        submit_followup_gate["message"],
                    )
                    continue

            # Loop back: re-invoke client.stream with extended history.

        # Loop bound exhausted — terminate without synthesizing adapter-specific
        # content. CC keeps recoverable failures in the tool loop; it does not
        # fabricate a domain answer from tool_result payloads at this boundary.
        logger.warning(
            "agentic loop hit UMMAYA_AGENTIC_LOOP_MAX_TURNS=%d; terminating "
            "duplicate_nonprogress_count=%d",
            _AGENTIC_LOOP_MAX_TURNS,
            duplicate_nonprogress_count,
        )
        if _conversation_has_successful_any_primitive_result(llm_messages):
            await write_frame(
                ErrorFrame(
                    session_id=frame.session_id,
                    correlation_id=frame.correlation_id or str(uuid.uuid4()),
                    role="backend",
                    ts=_utcnow(),
                    kind="error",
                    code="final_answer_loop_exhausted",
                    message=(
                        "Final answer loop exhausted after successful tool results. "
                        "No synthetic answer was generated."
                    ),
                    details={
                        "max_turns": _AGENTIC_LOOP_MAX_TURNS,
                        "duplicate_nonprogress_count": duplicate_nonprogress_count,
                    },
                )
            )
            return
        await write_frame(
            AssistantChunkFrame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                role="llm",
                ts=_utcnow(),
                kind="assistant_chunk",
                message_id=str(uuid.uuid4()),
                delta="",
                done=True,
            )
        )

    async def _handle_tool_result(frame: IPCFrame) -> None:
        """Spec 1978 T028 — consume ``tool_result`` and resolve pending Future.

        Looks up ``_pending_calls[call_id]``; if found, sets the Future
        result so any awaiting ``_handle_chat_request`` continuation can
        resume the agentic loop. Frames with no matching pending call are
        logged at debug level (out-of-band tool results are tolerated for
        the demo path; deep validation deferred to subsequent commits).
        """
        from ummaya.ipc.frame_schema import ToolResultFrame  # noqa: PLC0415

        if not isinstance(frame, ToolResultFrame):
            return
        fut = _pending_calls.pop(frame.call_id, None)
        if fut is None:
            logger.debug(
                "tool_result with no pending call (call_id=%s) — ignoring",
                frame.call_id,
            )
            return
        if not fut.done():
            fut.set_result(frame)

    # UMMAYA_IPC_HANDLER env var selects the user_input handler:
    #   - "llm" (default): route UserInputFrame → LLMClient.stream() → FriendliAI
    #   - "echo": mirror UserInputFrame back as AssistantChunkFrame "[echo] {text}"
    # Echo mode is used by integration tests that spawn the real backend but
    # must not depend on FRIENDLI_API_KEY or network reachability.
    import os as _os  # noqa: PLC0415

    _handler_mode = (_os.environ.get("UMMAYA_IPC_HANDLER") or "llm").lower()

    async def _handle_user_input_echo(frame: IPCFrame) -> None:
        from ummaya.ipc.frame_schema import (  # noqa: PLC0415
            AssistantChunkFrame,
            UserInputFrame,
        )

        if not isinstance(frame, UserInputFrame):
            return

        echo_frame = AssistantChunkFrame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="assistant_chunk",
            message_id=str(uuid.uuid4()),
            delta=f"[echo] {frame.text}",
            done=True,
        )
        await write_frame(echo_frame)

    if on_frame is None:

        async def _handle_frame(frame: IPCFrame) -> None:  # noqa: C901
            if frame.kind == "user_input":
                try:
                    if _handler_mode == "echo":
                        await _handle_user_input_echo(frame)
                    else:
                        await _handle_user_input_llm(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("user_input handler failed: %s", exc)
                    err = ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="llm_handler_error",
                        message=f"LLM handler failed: {exc}",
                        details={},
                    )
                    await write_frame(err)

            elif frame.kind == "chat_request":
                # Spec 1978 ADR-0001 — tools-aware chat path.
                try:
                    await _handle_chat_request(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("chat_request handler failed: %s", exc)
                    err = ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="llm",
                        ts=_utcnow(),
                        kind="error",
                        code="chat_request_error",
                        message=f"chat_request handler failed: {exc}",
                        details={},
                    )
                    await write_frame(err)

            elif frame.kind == "tool_result":
                # Spec 1978 T028 — resolve pending tool call Future.
                try:
                    await _handle_tool_result(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("tool_result handler failed: %s", exc)

            elif frame.kind == "permission_response":
                # Spec 1978 T047 — resolve pending permission Future.
                try:
                    await _handle_permission_response(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("permission_response handler failed: %s", exc)

            elif frame.kind == "session_event":
                evt = frame.event
                payload = frame.payload
                try:
                    await _dispatch_session_event(
                        evt,
                        payload,
                        frame.session_id,
                        _sm,
                        _shutdown,
                        frame.correlation_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("session_event handler raised: %s", exc)
                    err = ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="session_event_error",
                        message=f"Failed to handle session_event {evt!r}: {exc}",
                        details={"event": evt},
                    )
                    await write_frame(err)

            elif frame.kind == "consent_revoke_request":
                # Epic 2 — consent revoke IPC arm (arm 22).
                try:
                    await _handle_consent_revoke_request(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("consent_revoke_request handler failed: %s", exc)
                    from ummaya.ipc.frame_schema import (
                        ConsentRevokeResponseFrame as _ConsentRevokeResponseFrame,  # noqa: PLC0415
                    )

                    err_resp = _ConsentRevokeResponseFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="consent_revoke_response",
                        request_id=getattr(frame, "request_id", ""),
                        ok=False,
                        error="io_error",
                    )
                    await write_frame(err_resp)

            elif frame.kind == "plugin_op":
                # Spec 1979 — plugin_op IPC dispatcher arm. Routes citizen
                # /plugin install / uninstall / list slash commands to the
                # backend installer (Spec 1636) via the IPCConsentBridge
                # (60s wait_for + Spec 033 PermissionRequestFrame round-trip).
                try:
                    from ummaya.ipc.plugin_op_dispatcher import (  # noqa: PLC0415
                        handle_plugin_op_request,
                    )
                    from ummaya.plugins.consent_bridge import (  # noqa: PLC0415
                        IPCConsentBridge,
                    )
                    from ummaya.tools.executor import ToolExecutor  # noqa: PLC0415

                    consent_bridge = IPCConsentBridge(
                        write_frame=write_frame,
                        pending_perms=_pending_perms,
                        session_id=frame.session_id,
                    )
                    _registry = _ensure_tool_registry()
                    await handle_plugin_op_request(
                        frame,
                        registry=_registry,
                        executor=ToolExecutor(registry=_registry),
                        write_frame=write_frame,
                        consent_bridge=consent_bridge,
                        session_id=frame.session_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("plugin_op handler failed: %s", exc)
                    err = ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="plugin_op_error",
                        message=f"plugin_op handler failed: {exc}",
                        details={"request_op": getattr(frame, "request_op", None)},
                    )
                    await write_frame(err)

        async def _handle_consent_revoke_request(frame: IPCFrame) -> None:  # noqa: C901, PLR0912
            """Epic 2 — consent revoke request handler (arm 22).

            Reads the target receipt JSON from
            ``~/.ummaya/memdir/user/consent/<receipt_id>.json``, marks it
            revoked (atomic temp+rename write), appends a withdrawal entry to
            the canonical Spec 033 PIPA ledger via
            ``ummaya.permissions.ledger.append`` (HMAC-sealed, hash-chained,
            fcntl-locked), emits an OTEL span, and responds with a
            ``consent_revoke_response`` frame.

            Audit-4 P0-3 (2026-05-04): Replaced ad-hoc unsealed
            ``hashlib.sha256(json.dumps(entry))`` + parallel
            ``~/.ummaya/memdir/user/consent/ledger.jsonl`` path with
            ``ummaya.permissions.ledger.append(action="withdraw", ...)``.
            The ad-hoc path lacked HMAC, hash-chain prev_hash, key_id, and
            fcntl lock — entries were forgeable and could not be verified by
            ``ummaya permissions verify``. The unified path writes to the
            canonical ledger configured by ``settings.permission_ledger_path``
            (default ``~/.ummaya/consent_ledger.jsonl``).

            Error cases:
            - ``not_found``:   receipt file does not exist.
            - ``already_revoked``: receipt already has ``revoked_at`` set.
            - ``io_error``:    any filesystem / JSON parse error.
            """
            import json as _json_revoke  # noqa: PLC0415
            import os as _os_revoke  # noqa: PLC0415
            import tempfile as _tempfile  # noqa: PLC0415
            from datetime import datetime as _dt_revoke  # noqa: PLC0415
            from pathlib import Path as _Path  # noqa: PLC0415

            from ummaya.ipc.frame_schema import (  # noqa: PLC0415
                ConsentRevokeResponseFrame as _CRRespFrame,
            )
            from ummaya.permissions.action_digest import (  # noqa: PLC0415
                compute_action_digest as _compute_action_digest,
            )
            from ummaya.permissions.action_digest import (  # noqa: PLC0415
                generate_nonce as _generate_nonce,
            )
            from ummaya.permissions.ledger import (  # noqa: PLC0415
                append as _ledger_append_withdraw,
            )
            from ummaya.settings import (  # noqa: PLC0415
                settings as _ummaya_settings_revoke,
            )

            request_id: str = getattr(frame, "request_id", "")
            receipt_id: str = getattr(frame, "receipt_id", "")
            scope: str = getattr(frame, "scope", "once")
            reason: str | None = getattr(frame, "reason", None)
            session_id: str = frame.session_id

            with _tracer.start_as_current_span("ummaya.consent.revoke") as revoke_span:
                revoke_span.set_attribute("ummaya.consent.receipt_id", receipt_id)
                revoke_span.set_attribute("ummaya.consent.scope", scope)
                revoke_span.set_attribute("ummaya.session.id", session_id)

                consent_dir = _Path.home() / ".ummaya" / "memdir" / "user" / "consent"
                receipt_path = consent_dir / f"{receipt_id}.json"

                async def _emit_response(
                    ok: bool,
                    revoked_at: str | None = None,
                    record_hash: str | None = None,
                    error: str | None = None,
                ) -> None:
                    resp = _CRRespFrame(
                        session_id=session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="consent_revoke_response",
                        request_id=request_id,
                        ok=ok,
                        revoked_at=revoked_at,
                        record_hash=record_hash,
                        error=error,  # type: ignore[arg-type]
                    )
                    await write_frame(resp)

                # Determine which receipts to revoke.
                if scope == "session-all":
                    # Collect all receipt files for the current session.
                    try:
                        all_paths = sorted(consent_dir.glob("rcpt-*.json"))
                    except Exception:
                        all_paths = []
                    target_paths = []
                    for p in all_paths:
                        try:
                            raw = p.read_text(encoding="utf-8")
                            data = _json_revoke.loads(raw)
                            if data.get("session_id") == session_id and not data.get("revoked_at"):
                                target_paths.append(p)
                        except Exception:  # noqa: BLE001, S112
                            continue
                else:
                    # scope == "once" — single receipt.
                    if not receipt_path.exists():
                        revoke_span.set_attribute("ummaya.consent.revoke_error", "not_found")
                        revoke_span.set_status(Status(StatusCode.ERROR, "not_found"))
                        await _emit_response(ok=False, error="not_found")
                        return
                    target_paths = [receipt_path]

                if not target_paths:
                    # Nothing to revoke — either empty session or single path already handled.
                    revoke_span.set_attribute("ummaya.consent.revoke_error", "already_revoked")
                    revoke_span.set_status(Status(StatusCode.ERROR, "already_revoked"))
                    await _emit_response(ok=False, error="already_revoked")
                    return

                # Revoke each target receipt atomically.
                revoked_at_ts = _utcnow()
                last_record_hash: str | None = None
                any_error = False
                for target_path in target_paths:
                    try:
                        raw = target_path.read_text(encoding="utf-8")
                        data = _json_revoke.loads(raw)
                        if data.get("revoked_at") and scope != "session-all":
                            # Single-receipt revoke on already-revoked receipt.
                            revoke_span.set_attribute(
                                "ummaya.consent.revoke_error",
                                "already_revoked",
                            )
                            revoke_span.set_status(Status(StatusCode.ERROR, "already_revoked"))
                            await _emit_response(ok=False, error="already_revoked")
                            return
                        if data.get("revoked_at"):
                            # session-all: skip already-revoked receipts silently.
                            continue

                        data["revoked_at"] = revoked_at_ts
                        if reason:
                            data["revoke_reason"] = reason

                        # Atomic write: write to temp file then rename.
                        updated_json = _json_revoke.dumps(data, ensure_ascii=False, indent=2)
                        fd, tmp_path_str = _tempfile.mkstemp(
                            dir=str(consent_dir), suffix=".tmp", prefix="rcpt_"
                        )
                        try:
                            with _os_revoke.fdopen(fd, "w", encoding="utf-8") as fh:
                                fh.write(updated_json)
                            _os_revoke.replace(tmp_path_str, str(target_path))
                        except Exception:
                            _os_revoke.unlink(tmp_path_str)
                            raise

                        # Audit-4 P0-3 — append withdraw record to the canonical
                        # Spec 033 PIPA ledger via ummaya.permissions.ledger.
                        # Replaces the prior ad-hoc unsealed hashlib path:
                        # this call computes prev_hash from the prior record,
                        # SHA-256 record_hash over canonical JCS, and seals
                        # with HMAC-SHA-256 under the key_id from registry.json.
                        target_receipt_id = str(data.get("receipt_id", target_path.stem))
                        target_tool_id = str(data.get("tool_id", "unknown"))
                        withdraw_args: dict[str, object] = {
                            "scope_receipt_id": target_receipt_id,
                            "scope": scope,
                            "session_id": session_id,
                        }
                        if reason:
                            withdraw_args["reason"] = reason
                        withdraw_digest = _compute_action_digest(
                            target_tool_id,
                            withdraw_args,
                            _generate_nonce(),
                        )
                        withdraw_record = _ledger_append_withdraw(
                            tool_id=target_tool_id,
                            mode="default",
                            granted=False,
                            action_digest=withdraw_digest,
                            action="withdraw",
                            scope_receipt_id=target_receipt_id,
                            withdrawn_at=_dt_revoke.fromisoformat(
                                revoked_at_ts.replace("Z", "+00:00")
                            )
                            if revoked_at_ts.endswith("Z")
                            else _dt_revoke.fromisoformat(revoked_at_ts),
                            session_id=session_id,
                            correlation_id=frame.correlation_id,
                            ledger_path=_ummaya_settings_revoke.permission_ledger_path,
                            key_path=_ummaya_settings_revoke.permission_key_path,
                            key_registry_path=(
                                _ummaya_settings_revoke.permission_key_registry_path
                            ),
                        )
                        record_hash = withdraw_record.record_hash
                        last_record_hash = record_hash

                        revoke_span.set_attribute("ummaya.consent.record_hash", record_hash)
                        logger.debug(
                            "consent_revoke: revoked %s sealed_hash=%s seq=%d",
                            target_path.name,
                            record_hash[:16],
                            withdraw_record.sequence,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("consent_revoke: io_error on %s: %s", target_path.name, exc)
                        any_error = True

                if any_error and last_record_hash is None:
                    revoke_span.set_status(Status(StatusCode.ERROR, "io_error"))
                    await _emit_response(ok=False, error="io_error")
                    return

                revoke_span.set_status(Status(StatusCode.OK))
                await _emit_response(
                    ok=True,
                    revoked_at=revoked_at_ts,
                    record_hash=last_record_hash,
                )

        on_frame = _handle_frame

    # Spec 1978 T081 / ADR-0004 — root span ``ummaya.session`` covers the
    # entire stdio session lifetime. All inbound/outbound frame spans
    # (ummaya.ipc.frame), LLM chat spans, tool dispatch spans, and
    # permission spans are nested under this root via OTEL implicit
    # context propagation. Closes at session exit (graceful shutdown
    # path or session_event{event=exit}).
    with _tracer.start_as_current_span("ummaya.session") as _session_span:
        _session_span.set_attribute("ummaya.session.id", sid)
        _session_span.set_attribute("ummaya.ipc.handler_mode", _handler_mode)

        # Run reader loop concurrently with shutdown watcher
        reader_task = asyncio.create_task(
            _reader_loop(stdin_reader, on_frame, sid),
            name="ipc-reader",
        )
        shutdown_task = asyncio.create_task(_shutdown.wait(), name="ipc-shutdown")

        done, pending = await asyncio.wait(
            {reader_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Record which task completed first so post-mortem traces show
        # whether the session ended on stdin EOF (reader_task) vs SIGTERM /
        # session_event{event=exit} (shutdown_task).
        if reader_task in done:
            _session_span.set_attribute("ummaya.session.exit_reason", "stdin_closed")
        elif shutdown_task in done:
            _session_span.set_attribute("ummaya.session.exit_reason", "shutdown_signal")

        # Cancel whatever is still running
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        # Cancel the stdin feed task too — its awaiting coroutine winds
        # down so finally runs feed_eof() (Codex P1, PR #2111). The blocked
        # readline() thread keeps running but asyncio.run()'s
        # shutdown_default_executor step bounds the wait at process exit.
        _stdin_feed_handle.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await _stdin_feed_handle

        # Emit exit frame and flush
        try:
            await _emit_exit_frame(sid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to emit exit frame: %s", exc)

        logger.info("IPC stdio loop exited cleanly — session_id=%s", sid)


__all__ = [
    "run",
    "write_frame",
]
