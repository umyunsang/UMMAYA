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

    uv run kosmos --ipc stdio

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
from collections.abc import Callable
from datetime import UTC
from types import FrameType
from typing import TYPE_CHECKING, Any, Final, Literal, cast

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import TypeAdapter, ValidationError

from kosmos.ipc.envelope import attach_envelope_span_attributes
from kosmos.ipc.frame_schema import (
    ErrorFrame,
    IPCFrame,
    SessionEventFrame,
)

if TYPE_CHECKING:
    from kosmos.session.manager import SessionManager

logger = logging.getLogger(__name__)

# Module-level tracer — follows the same pattern as kosmos.tools.executor and
# kosmos.engine.query (trace.get_tracer(__name__) at module load time).
_tracer = trace.get_tracer(__name__)

# Frames whose handlers can legitimately await follow-up frames from the same
# stdin stream. Running them inline deadlocks the reader: chat_request waits for
# permission_response while the reader is still awaiting chat_request.
_BACKGROUND_FRAME_KINDS: frozenset[str] = frozenset({"chat_request", "user_input", "plugin_op"})
_SCOPE_ENTRY_RE = re.compile(r"^(lookup|submit|verify|subscribe):[a-z0-9_]+\.[a-z0-9_-]+$")
_TOOL_ID_SCOPE_RE = re.compile(
    r"^(?P<verb>lookup|submit|verify|subscribe):(?P<tool_id>[a-z][a-z0-9_]*[a-z0-9])$"
)
_CANONICAL_SCOPE_ALIASES: Final[dict[str, str]] = {
    "lookup:mock_lookup_module_hometax_simplified": "lookup:hometax.simplified",
    "lookup:mock.lookup_module_hometax_simplified": "lookup:hometax.simplified",
    "submit:mock_submit_module_gov24_minwon": "submit:gov24.minwon",
    "submit:mock.submit_module_gov24_minwon": "submit:gov24.minwon",
    "submit:mock_submit_module_hometax_taxreturn": "submit:hometax.tax-return",
    "submit:mock.submit_module_hometax_taxreturn": "submit:hometax.tax-return",
    "submit:mock_welfare_application_submit_v1": "submit:mydata.welfare_application",
    "submit:mock.welfare_application_submit_v1": "submit:mydata.welfare_application",
    "submit:mohw.welfare_application": "submit:mydata.welfare_application",
    "submit:pub.mohw.welfare_application": "submit:mydata.welfare_application",
    "submit:mock_traffic_fine_pay_v1": "submit:traffic.fine-pay",
    "submit:mock.traffic_fine_pay_v1": "submit:traffic.fine-pay",
    "submit:traffic_fine.payment": "submit:traffic.fine-pay",
    "submit:traffic_fine.pay": "submit:traffic.fine-pay",
    "submit:traffic.fine.payment": "submit:traffic.fine-pay",
    "submit:traffic.fine.pay": "submit:traffic.fine-pay",
    "submit:traffic.fine_pay": "submit:traffic.fine-pay",
}
_NON_DELEGATING_VERIFY_SCOPE_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "lookup:gov24.certificate",
        "lookup:gov24.resident_certificate",
        "lookup:gov24.simplified",
        "lookup:gov24_certificate.lookup",
        "lookup:mock_lookup_module_gov24_certificate",
        "lookup:mock.lookup_module_gov24_certificate",
        "lookup:mydata.welfare",
        "lookup:mydata.welfare_eligibility_search",
        "lookup:public_mydata.welfare_eligibility_search",
        "lookup:mohw.welfare_eligibility",
        "lookup:mohw_welfare_eligibility_search",
        "lookup:mohw.welfare_eligibility_search",
        "lookup:pub.mohw.welfare_eligibility",
        "lookup:pub.mohw.welfare_eligibility_search",
        "lookup:traffic_fine.check",
        "lookup:traffic.fine",
        "lookup:traffic.fine_check",
        "lookup:traffic.fine.check",
        "lookup:traffic_fine.inquiry",
        "lookup:traffic.fine_inquiry",
        "lookup:traffic.fine.inquiry",
        "lookup:traffic_fine.search",
        "lookup:traffic.fine_search",
        "lookup:traffic.fine.search",
    }
)
_PRUNABLE_OVERBROAD_VERIFY_SCOPES: Final[frozenset[str]] = frozenset(
    {
        "lookup:hometax.simplified",
        "submit:hometax.tax-return",
    }
)
_QUERY_BOUND_NON_DELEGATING_SCOPE_PREFIXES: Final[dict[str, tuple[str, ...]]] = {
    "submit:gov24.minwon": ("lookup:gov24.",),
}
_PRIMITIVE_TOOL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MOCK_DISCLOSURE_KO: Final = (
    "이 결과는 실제 행정 영향이 없는 시연(모의) 결과입니다. "
    "접수번호는 시연용이며 실제 기관 포털에서 조회되지 않습니다."
)
_GOV24_MINWON_RECEIPT_RE: Final = re.compile(r"gov24-\d{4}-\d{2}-\d{2}-MW-[A-Z0-9]+")
_HOMETAX_TAXRETURN_RECEIPT_RE: Final = re.compile(r"hometax-\d{4}-\d{2}-\d{2}-RX-[A-Z0-9]+")
_KOSMOS_SUBMIT_TX_RE: Final = re.compile(r"urn:kosmos:submit:[a-f0-9]+")
_GOV24_MINWON_SESSION_RE: Final = re.compile(r"GOV24-[A-Z0-9-]+")
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
        "scope": "lookup:hometax.simplified",
        "purpose_ko": "연말정산 간소화 자료 조회",
        "purpose_en": "Hometax simplified year-end tax lookup",
    },
}
_VERIFY_QUERY_REQUIREMENTS: Final[tuple[tuple[tuple[str, ...], dict[str, str]], ...]] = (
    (
        ("간편인증", "pass 인증", "kakao 인증", "naver 인증"),
        {
            "verify_tool_id": "mock_verify_ganpyeon_injeung",
            "allowed_tool_ids": "mock_verify_ganpyeon_injeung,mock_verify_module_simple_auth",
            "scope": "verify:ganpyeon.identity",
            "allowed_scopes": "verify:ganpyeon.identity",
            "purpose_ko": "간편인증 로그인",
            "purpose_en": "Simple authentication login",
        },
    ),
    (
        ("모바일신분증", "모바일id", "모바일 id", "mobile id"),
        {
            "verify_tool_id": "mock_verify_mobile_id",
            "allowed_tool_ids": "mock_verify_mobile_id",
            "scope": "verify:mobile_id.identity",
            "allowed_scopes": "verify:mobile_id.identity",
            "purpose_ko": "모바일 신분증 본인확인",
            "purpose_en": "Mobile ID identity verification",
        },
    ),
    (
        ("마이데이터", "mydata"),
        {
            "verify_tool_id": "mock_verify_mydata",
            "allowed_tool_ids": "mock_verify_mydata",
            "scope": "verify:mydata.consent",
            "allowed_scopes": "verify:mydata.consent,submit:public_mydata.action",
            "purpose_ko": "마이데이터 인증",
            "purpose_en": "MyData authentication",
        },
    ),
    (
        ("홈택스", "연말정산", "간소화"),
        {
            "verify_tool_id": "mock_verify_module_modid",
            "allowed_tool_ids": "mock_verify_module_modid",
            "scope": "lookup:hometax.simplified",
            "allowed_scopes": "lookup:hometax.simplified",
            "purpose_ko": "연말정산 간소화 자료 조회",
            "purpose_en": "Hometax simplified year-end tax lookup",
        },
    ),
    (
        ("정부24", "주민등록등본", "등본", "민원"),
        {
            "verify_tool_id": "mock_verify_module_simple_auth",
            "allowed_tool_ids": "mock_verify_module_simple_auth",
            "scope": "submit:gov24.minwon",
            "allowed_scopes": "submit:gov24.minwon",
            "purpose_ko": "주민등록등본 발급 민원 신청",
            "purpose_en": "Gov24 resident registration certificate civil petition",
        },
    ),
    (
        ("복지 급여 신청", "한부모가족", "아동양육비"),
        {
            "verify_tool_id": "mock_verify_mydata",
            "allowed_tool_ids": "mock_verify_mydata",
            "scope": "submit:mydata.welfare_application",
            "allowed_scopes": "submit:mydata.welfare_application",
            "purpose_ko": "한부모가족 아동양육비 지원 신청",
            "purpose_en": "Single-parent family child support application",
        },
    ),
    (
        ("과태료", "교통범칙금", "범칙금"),
        {
            "verify_tool_id": "mock_verify_ganpyeon_injeung",
            "allowed_tool_ids": "mock_verify_ganpyeon_injeung",
            "scope": "submit:traffic.fine-pay",
            "allowed_scopes": "submit:traffic.fine-pay",
            "purpose_ko": "교통 과태료 납부",
            "purpose_en": "Traffic fine payment",
        },
    ),
)
_SUBSCRIBE_TOOL_IDS: Final[frozenset[str]] = frozenset(
    {
        "mock_cbs_disaster_v1",
        "mock_rest_pull_tick_v1",
        "mock_rss_public_notices_v1",
    }
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


def _ensure_mock_disclosure(text: str) -> str:
    """Append the mandatory citizen-facing mock disclosure when absent."""
    text = _normalize_gov24_mock_minwon_final_answer(text)
    text = _normalize_hometax_mock_taxreturn_final_answer(text)
    text = _remove_mock_conflicting_real_world_claims(text)
    if "실제 행정 영향" in text and ("시연" in text or "모의" in text):
        return text
    suffix = _MOCK_DISCLOSURE_KO
    if not text.strip():
        return suffix
    return f"{text.rstrip()}\n\n{suffix}"


def _append_str_line(lines: list[str], label: str, value: object) -> None:
    if isinstance(value, str) and value:
        lines.append(f"{label}: {value}")


def _finish_synthetic_submit_lines(lines: list[str], tx_line: str | None) -> str:
    if tx_line is not None:
        lines.append(tx_line)
    lines.append(_MOCK_DISCLOSURE_KO)
    return "\n".join(lines)


def _synthetic_gov24_submit_answer(
    params: dict[str, object],
    receipt: dict[str, object],
    tx_line: str | None,
) -> str:
    lines = ["정부24 주민등록등본 발급 민원 신청이 시연 환경에서 접수되었습니다."]
    receipt_id = receipt.get("receipt_id")
    if isinstance(receipt_id, str):
        lines.append(f"접수번호: {receipt_id} (시연용)")
    _append_str_line(lines, "신청자", params.get("applicant_name"))
    lines.append("문서 종류: 주민등록등본")
    if params.get("delivery_method") == "online":
        lines.append("수령 방법: 온라인 발급")
    return _finish_synthetic_submit_lines(lines, tx_line)


def _synthetic_traffic_fine_answer(
    params: dict[str, object],
    receipt: dict[str, object],
    tx_line: str | None,
) -> str:
    lines = ["교통 과태료 납부가 시연 환경에서 접수되었습니다."]
    receipt_ref = receipt.get("receipt_ref")
    if isinstance(receipt_ref, str):
        lines.append(f"접수번호: {receipt_ref} (시연용)")
    fine_reference = receipt.get("fine_reference") or params.get("fine_reference")
    payment_channel = receipt.get("payment_channel") or params.get("payment_method")
    _append_str_line(lines, "과태료 참조", fine_reference)
    _append_str_line(lines, "결제 수단", payment_channel)
    return _finish_synthetic_submit_lines(lines, tx_line)


def _synthetic_public_mydata_answer(
    _params: dict[str, object],
    receipt: dict[str, object],
    tx_line: str | None,
) -> str:
    lines = ["공공 마이데이터 제공 동의가 시연 환경에서 접수되었습니다."]
    receipt_id = receipt.get("receipt_id")
    if isinstance(receipt_id, str):
        lines.append(f"접수번호: {receipt_id} (시연용)")
    _append_str_line(lines, "처리 상태", receipt.get("status"))
    return _finish_synthetic_submit_lines(lines, tx_line)


def _synthetic_welfare_application_answer(
    params: dict[str, object],
    receipt: dict[str, object],
    tx_line: str | None,
) -> str:
    lines = ["복지 급여 신청이 시연 환경에서 접수되었습니다."]
    application_ref = receipt.get("application_ref")
    if isinstance(application_ref, str):
        lines.append(f"접수번호: {application_ref} (시연용)")
    _append_str_line(lines, "급여 코드", receipt.get("benefit_code") or params.get("benefit_code"))
    return _finish_synthetic_submit_lines(lines, tx_line)


def _synthetic_submit_final_answer(
    tool_id: str,
    submit_args: dict[str, object],
    envelope_dump: dict[str, object],
) -> str | None:
    """Build a receipt-only final answer when the backend had to synthesize submit."""
    result = envelope_dump.get("result")
    if not isinstance(result, dict) or result.get("status") != "succeeded":
        return None
    receipt = result.get("adapter_receipt")
    receipt_dict = receipt if isinstance(receipt, dict) else {}
    raw_params = submit_args.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    transaction_id = result.get("transaction_id")
    tx_line = f"거래 ID: {transaction_id}" if isinstance(transaction_id, str) else None
    builders: dict[str, Callable[[dict[str, object], dict[str, object], str | None], str]] = {
        "mock_submit_module_gov24_minwon": _synthetic_gov24_submit_answer,
        "mock_traffic_fine_pay_v1": _synthetic_traffic_fine_answer,
        "mock_submit_module_public_mydata_action": _synthetic_public_mydata_answer,
        "mock_welfare_application_submit_v1": _synthetic_welfare_application_answer,
    }
    builder = builders.get(tool_id)
    return None if builder is None else builder(params, receipt_dict, tx_line)


def _normalize_gov24_mock_minwon_final_answer(text: str) -> str:
    """Replace Gov24 mock-submit prose with a receipt-only citizen summary."""
    if "gov24-" not in text or "주민등록등본" not in text:
        return text
    receipt = _first_match(_GOV24_MINWON_RECEIPT_RE, text)
    transaction_id = _first_match(_KOSMOS_SUBMIT_TX_RE, text)
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
    lines.append(_MOCK_DISCLOSURE_KO)
    return "\n".join(lines)


def _normalize_hometax_mock_taxreturn_final_answer(text: str) -> str:
    """Replace Hometax mock-submit prose with a receipt-only citizen summary."""
    if "hometax-" not in text or "종합소득세" not in text:
        return text
    receipt = _first_match(_HOMETAX_TAXRETURN_RECEIPT_RE, text)
    transaction_id = _first_match(_KOSMOS_SUBMIT_TX_RE, text)

    lines = ["홈택스 종합소득세 신고가 시연 환경에서 접수되었습니다."]
    if receipt is not None:
        lines.append(f"접수번호: {receipt} (시연용)")
    if transaction_id is not None:
        lines.append(f"거래 ID: {transaction_id}")
    if "42,000,000" in text or "42000000" in text:
        lines.append("총 신고 소득: 42,000,000원")
    lines.append("신고 상태: 신고완료")
    lines.append(_MOCK_DISCLOSURE_KO)
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
# ONLY, gated by KOSMOS_CHAT_REQUEST_DUMP=1; off by default — production
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
    """Return True when KOSMOS_CHAT_REQUEST_DUMP env var is set to '1'.

    Helper exists so the env-var lookup is centralised and the call sites
    stay one-liners that are easy to grep / remove later.
    """
    return os.getenv("KOSMOS_CHAT_REQUEST_DUMP") == "1"


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

    OTEL: emits a ``kosmos.ipc.frame`` child span (FR-053) with direction
    ``"outbound"``.  ``_assembly_start_ns`` is the ``time.monotonic_ns()``
    captured by the caller before building the frame payload; when absent,
    the span clock starts at the write call itself.  ``tx_cache_state`` is
    forwarded from the :class:`~kosmos.ipc.transaction_lru.TransactionLRU`
    path for irreversible-tool frames (Spec 032 T048 / FR-053).
    """
    t0_ns = _assembly_start_ns if _assembly_start_ns is not None else time.monotonic_ns()
    payload = frame.model_dump_json() + "\n"
    encoded = payload.encode("utf-8")
    lock = _get_stdout_lock()
    with _tracer.start_as_current_span("kosmos.ipc.frame") as span:
        try:
            async with lock:
                sys.stdout.buffer.write(encoded)
                sys.stdout.buffer.flush()
            latency_ms = (time.monotonic_ns() - t0_ns) / 1_000_000
            span.set_attribute("kosmos.session.id", frame.session_id)
            span.set_attribute("kosmos.frame.kind", frame.kind)
            span.set_attribute("kosmos.frame.direction", "outbound")
            span.set_attribute("kosmos.ipc.latency_ms", latency_ms)
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
    with _tracer.start_as_current_span("kosmos.ipc.frame") as span:
        try:
            result = on_frame(frame)
            if asyncio.iscoroutine(result):
                await result
            latency_ms = (time.monotonic_ns() - dispatch_start_ns) / 1_000_000
            span.set_attribute("kosmos.session.id", frame.session_id)
            span.set_attribute("kosmos.frame.kind", frame.kind)
            span.set_attribute("kosmos.frame.direction", "inbound")
            span.set_attribute("kosmos.ipc.latency_ms", latency_ms)
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
    """Translate LLM citizen-shape verify args into adapter session context.

    The OpenAI tool schema teaches ``verify(tool_id, params={scope_list, ...})``.
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
    alias = _CANONICAL_SCOPE_ALIASES.get(scope)
    if alias is not None:
        logger.debug("verify: normalized scope alias %r -> %r", scope, alias)
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
    logger.debug("verify: normalized scope entry %r -> %r", scope, normalized)
    return normalized


def _normalize_verify_scope_entry(scope: str) -> str | None:
    """Normalize a verify scope and drop public lookup aliases from delegation."""
    normalized = _normalize_scope_entry(scope)
    if normalized in _NON_DELEGATING_VERIFY_SCOPE_ALIASES:
        logger.debug("verify: ignored non-delegating scope alias %r", scope)
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
            "submit: removed model-spread delegation fields before injecting "
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
            "submit: replacing model-emitted session_id with verified session_id "
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
    return {entry.strip() for entry in scope.split(",") if entry.strip()}


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

    KOSMOS keeps read-only public-data lookups permissive, but citizen-specific
    tax records carry private financial/medical/education deduction fields. The
    gateway boundary therefore requires a prior verify result whose delegation
    token grants the exact lookup scope before the lookup dispatch can proceed.
    """
    if fname != "lookup":
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
        f"verify(tool_id={verify_tool_id!r}, params={{"
        f'"scope_list": [{required_scope!r}], '
        f'"purpose_ko": {purpose_ko!r}, '
        f'"purpose_en": {purpose_en!r}'
        "}}). Do NOT answer from cached or synthetic tax data until that verify "
        "tool_result succeeds; then retry the original lookup."
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
    lookup call and forces the next turn to the canonical verify primitive.
    """
    if fname != "lookup":
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


def _tool_result_payload_is_error(payload: object) -> bool:
    """Return True for structured tool-result payloads that are errors."""
    if not isinstance(payload, dict):
        return False
    if payload.get("kind") == "error" or payload.get("denied") is True:
        return True
    error = payload.get("error")
    if isinstance(error, str) and error:
        return True
    result = payload.get("result")
    if isinstance(result, dict):
        if result.get("kind") == "error":
            return True
        nested_error = result.get("error")
        if isinstance(nested_error, str) and nested_error:
            return True
    return False


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
            if call_fn != "lookup":
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
    if name != "lookup":
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


def _primitive_payload_is_success(payload: object, *, primitive: str) -> bool:
    """Return True when a primitive payload represents a completed operation."""
    if _tool_result_payload_is_error(payload):
        return False
    if not isinstance(payload, dict):
        return True
    result = payload.get("result")
    if primitive == "submit":
        if isinstance(result, dict) and result.get("status") == "succeeded":
            return True
        return payload.get("status") == "succeeded"
    if primitive == "subscribe":
        if isinstance(result, dict):
            return result.get("status") == "opened" or isinstance(
                result.get("subscription_id"), str
            )
        return payload.get("status") == "opened" or isinstance(payload.get("subscription_id"), str)
    return True


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
            f"lookup(mode='fetch', tool_id={tool_id!r}, params={{}}). "
            "Do NOT answer from the verify result alone; summarize the requested "
            "medical and education deduction fields only after the lookup "
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


def _verify_requirement_for_query(user_query: str) -> dict[str, str] | None:
    """Map citizen auth wording to the verify tool/scope the next turn must call."""
    if not user_query:
        return None
    submit_requirement = _submit_requirement_for_query(user_query)
    if (
        submit_requirement is not None
        and submit_requirement["tool_id"] == "mock_submit_module_public_mydata_action"
    ):
        return {
            "verify_tool_id": "mock_verify_mydata",
            "allowed_tool_ids": "mock_verify_mydata",
            "scope": "submit:public_mydata.action",
            "allowed_scopes": "submit:public_mydata.action",
            "purpose_ko": "공공 마이데이터 제공 동의",
            "purpose_en": "Public MyData consent action",
        }
    if (
        submit_requirement is not None
        and submit_requirement["tool_id"] == "mock_submit_module_hometax_taxreturn"
    ):
        return {
            "verify_tool_id": "mock_verify_module_modid",
            "allowed_tool_ids": "mock_verify_module_modid",
            "scope": "lookup:hometax.simplified",
            "required_scopes": "lookup:hometax.simplified,submit:hometax.tax-return",
            "allowed_scopes": "lookup:hometax.simplified,submit:hometax.tax-return",
            "purpose_ko": "종합소득세 신고",
            "purpose_en": "Comprehensive income tax filing",
        }
    compact = re.sub(r"\s+", "", user_query).lower()
    lowered = user_query.lower()
    for keywords, requirement in _VERIFY_QUERY_REQUIREMENTS:
        for keyword in keywords:
            needle = re.sub(r"\s+", "", keyword).lower()
            if needle in compact or keyword.lower() in lowered:
                return requirement
    return None


def _initial_verify_tool_choice_for_query(
    llm_messages: list[Any],
    user_query: str,
) -> str | None:
    """Force identity-only verification requests through the verify primitive."""
    requirement = _verify_requirement_for_query(user_query)
    if requirement is None:
        return None
    if not requirement["scope"].startswith("verify:"):
        return None
    allowed_tool_ids = {
        item.strip()
        for item in requirement.get("allowed_tool_ids", requirement["verify_tool_id"]).split(",")
        if item.strip()
    }
    if any(
        _conversation_has_successful_primitive(
            llm_messages,
            primitive="verify",
            tool_id=tool_id,
        )
        for tool_id in allowed_tool_ids
    ):
        return None
    return requirement["verify_tool_id"]


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
            "scope": "submit:hometax.tax-return",
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
            "scope": "submit:gov24.minwon",
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
            "scope": "submit:mydata.welfare_application",
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
            "scope": "submit:traffic.fine-pay",
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
            "scope": "submit:public_mydata.action",
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
        primitive="submit",
        tool_id=requirement["tool_id"],
    ):
        return None
    if auth_context is None or not _conversation_has_tool_call(llm_messages, "verify"):
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
            "Submit follow-up missing: the citizen asked to complete a write, "
            "payment, consent, or filing flow and verification has already run, "
            f"but {tool_id!r} has not succeeded. RECOVERY: in the next turn call "
            f"submit(tool_id={tool_id!r}, params={params_json}). The backend will "
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
    if fname != "submit":
        return None
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id:
        return None
    if not _conversation_has_successful_primitive(
        llm_messages,
        primitive="submit",
        tool_id=tool_id,
    ):
        return None
    return (
        f"Submit already succeeded for {tool_id!r} in this conversation. "
        "RECOVERY: do NOT call submit again and do NOT request another "
        "permission decision. Produce the final citizen-facing answer from the "
        "prior successful submit tool_result and include the mock disclosure."
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
    emitted_scope = _normalize_scope_entry(f"submit:{tool_id}")
    if tool_id != "submit" and emitted_scope != requirement["scope"]:
        return args_obj
    logger.info(
        "submit: normalized model-emitted tool_id %r -> %r for citizen request",
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
    if fname != "submit":
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
    if tool_id and tool_id != "lookup":
        return args_obj
    sensitive_lookup = _sensitive_lookup_requirement_for_query(user_query)
    if sensitive_lookup is None:
        return args_obj
    normalized = dict(args_obj)
    normalized["tool_id"] = sensitive_lookup["tool_id"]
    logger.info(
        "lookup: normalized model-emitted tool_id %r -> %r for citizen request",
        tool_id or "<missing>",
        sensitive_lookup["tool_id"],
    )
    return normalized


def _normalize_lookup_args_for_query(
    fname: str,
    args_obj: dict[str, object],
    user_query: str,
) -> dict[str, object]:
    """Fill deterministic lookup filters already present in the citizen request."""
    if fname != "lookup":
        return args_obj
    args_obj = _canonicalize_lookup_tool_id_for_query(args_obj, user_query)
    args_obj = _normalize_hometax_lookup_args_for_query(args_obj, user_query)
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


def _subscribe_requirement_for_query(user_query: str) -> dict[str, str] | None:
    """Map citizen subscription wording to the subscribe adapter that must run."""
    if not user_query:
        return None
    compact = _compact_query(user_query)
    if "구독" not in compact and "알림" not in compact:
        return None
    if not _query_contains_any(user_query, ("재난문자", "재난 알림", "긴급재난문자", "cbs")):
        return None
    params = {
        "region": "부산 사하구" if "부산" in user_query and "사하" in user_query else "전국",
        "burst_count": 3,
    }
    return {
        "tool_id": "mock_cbs_disaster_v1",
        "params_json": _stdlib_json.dumps(params, ensure_ascii=False),
        "lifetime_seconds": "300",
        "message": (
            "Subscribe follow-up missing: the citizen asked for an ongoing "
            "disaster-alert subscription. RECOVERY: in the next turn call "
            "subscribe(tool_id='mock_cbs_disaster_v1', "
            f"params={_stdlib_json.dumps(params, ensure_ascii=False)}, "
            "lifetime_seconds=300). Do NOT call lookup for a subscribe adapter."
        ),
    }


def _check_subscribe_terminated_without_subscribe(
    llm_messages: list[Any],
    user_query: str,
) -> dict[str, str] | None:
    """Return recovery metadata when a subscription request ends without subscribe."""
    requirement = _subscribe_requirement_for_query(user_query)
    if requirement is None:
        return None
    if _conversation_has_successful_primitive(
        llm_messages,
        primitive="subscribe",
        tool_id=requirement["tool_id"],
    ):
        return None
    return requirement


def _check_lookup_wrong_primitive_prerequisite(
    fname: str,
    args_obj: dict[str, object],
) -> dict[str, str] | None:
    """Reject lookup calls that target adapters registered for another primitive."""
    if fname != "lookup":
        return None
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str) or tool_id not in _SUBSCRIBE_TOOL_IDS:
        return None
    params = args_obj.get("params") if isinstance(args_obj.get("params"), dict) else {}
    return {
        "tool_id": tool_id,
        "params_json": _stdlib_json.dumps(params, ensure_ascii=False),
        "message": (
            f"Wrong primitive for adapter {tool_id!r}: this adapter is registered "
            "under subscribe, not lookup. RECOVERY: call "
            f"subscribe(tool_id={tool_id!r}, params="
            f"{_stdlib_json.dumps(params, ensure_ascii=False)}, lifetime_seconds=300). "
            "Do NOT tell the citizen the adapter is unavailable."
        ),
    }


def _check_verify_terminated_without_verify(
    llm_messages: list[Any],
    user_query: str,
) -> dict[str, str] | None:
    """Return verify recovery metadata when an auth request is about to end as prose."""
    requirement = _verify_requirement_for_query(user_query)
    if requirement is None:
        return None
    if _conversation_has_tool_call(llm_messages, "verify"):
        return None
    verify_tool_id = requirement["verify_tool_id"]
    scope_entries = _requirement_scope_entries(requirement)
    purpose_ko = requirement["purpose_ko"]
    purpose_en = requirement["purpose_en"]
    return {
        **requirement,
        "message": (
            "Verify prerequisite missing: the citizen asked for an authentication, "
            "login, consent, or identity flow, but this turn is about to answer "
            "without invoking verify. RECOVERY: in the next turn call "
            f"verify(tool_id={verify_tool_id!r}, params={{"
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

    from kosmos.tools.verify_canonical_map import resolve_family  # noqa: PLC0415

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
    if fname != "verify":
        wrong_verify_tool = (
            tool_id == "verify"
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
                "Verify primitive prerequisite mismatch: the citizen wording maps "
                f"to verify tool(s) {sorted(allowed_tool_ids)!r} with scope(s) "
                f"{sorted(allowed_scopes)!r}, but the model emitted {fname}"
                f"(tool_id={tool_id!r}). RECOVERY: call "
                f"verify(tool_id={expected_tool!r}, params={{"
                f'"scope_list": {expected_scope_list!r}, '
                f'"purpose_ko": {purpose_ko!r}, '
                f'"purpose_en": {purpose_en!r}'
                "}}). Do NOT call verify adapters through lookup or another primitive."
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
            "Verify tool-choice prerequisite mismatch: the citizen wording maps "
            f"to verify tool(s) {sorted(allowed_tool_ids)!r} with scope(s) "
            f"{sorted(allowed_scopes)!r}, but the model emitted tool_id={tool_id!r} "
            f"and scope_list={sorted(scopes)!r}. RECOVERY: call "
            f"verify(tool_id={expected_tool!r}, params={{"
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
    if fname != "verify":
        return args_obj
    requirement = _verify_requirement_for_query(user_query)
    if requirement is None:
        return args_obj

    entries = _verify_scope_list_entries(args_obj)
    if entries is None:
        if not requirement["scope"].startswith("verify:"):
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
            "verify: filled missing identity scope_list for citizen request (%s)",
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
            "verify: normalized query-bound scope_list by dropping non-required scope(s): %s",
            ",".join(dropped),
        )
    return _with_verify_scope_list(args_obj, normalized_entries)


def _normalize_verify_tool_id_for_query(
    fname: str,
    args_obj: dict[str, object],
    user_query: str,
) -> dict[str, object]:
    """Canonicalize generic verify tool_id when scope already selects one adapter."""
    if fname != "verify":
        return args_obj
    requirement = _verify_requirement_for_query(user_query)
    if requirement is None:
        return args_obj
    tool_id = str(args_obj.get("tool_id") or "")
    if tool_id and tool_id != "verify":
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
        "verify: normalized model-emitted tool_id %r -> %r for citizen request",
        tool_id or "<missing>",
        required_tool_id,
    )
    return {**args_obj, "tool_id": required_tool_id}


def _query_implies_location_resolution(user_query: str) -> bool:
    """Return True when a citizen query must canonicalise a place string first."""
    if not user_query:
        return False
    if any(keyword in user_query for keyword in _LOCATION_RESOLUTION_HINTS_KO):
        return True
    lowered = user_query.lower()
    return any(
        keyword in lowered
        for keyword in ("near", "nearby", "around", "address", "location", "station")
    )


def _location_independent_resolve_redirect_for_query(
    fname: str,
    user_query: str,
) -> dict[str, str] | None:
    """Return the next primitive when resolve_location is irrelevant."""
    if fname != "resolve_location":
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
            "primitive": "verify",
            "tool_id": submit_requirement["verify_tool_id"],
        }

    sensitive_lookup = _sensitive_lookup_requirement_for_query(user_query)
    if sensitive_lookup is not None:
        return {
            "primitive": "verify",
            "tool_id": sensitive_lookup["verify_tool_id"],
        }

    if _query_contains_any(
        user_query,
        ("간편인증", "모바일신분증", "모바일 id", "mobile id", "마이데이터"),
    ):
        verify_requirement = _verify_requirement_for_query(user_query)
        if verify_requirement is not None:
            return {
                "primitive": "verify",
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
    if _conversation_has_tool_call(llm_messages, "resolve_location"):
        return None
    return (
        "Location resolution prerequisite missing: the citizen supplied a place, "
        "address, station, or nearby-search request, but this turn is about to "
        "answer without invoking resolve_location. RECOVERY: in the next turn call "
        "resolve_location(query=<citizen supplied place/address text>, "
        "want='coords_and_admcd') even when the text looks fake or incomplete. "
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
# resolve_location to have run first (Epic #2766 chain prerequisite gate).
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
    The CC hook is tool-scoped; KOSMOS centralises the equivalent
    pre-dispatch check here because every coord-input adapter has the
    identical prerequisite (resolve_location must have been called in
    a prior turn of the same conversation). Adapter-scoped overrides can
    be added later by extending this function to dispatch on tool_id.

    Returns ``None`` when the call is allowed; returns a descriptive
    error message when the call should be rejected. The caller emits
    that message verbatim to the LLM via a tool_result envelope so the
    next agentic-loop turn can recover.
    """
    # Only the `lookup` primitive carries adapter calls (mode='fetch'
    # routes to a registered GovAPITool). All other primitives are
    # either coord-free (verify) or carry their own param schema
    # (submit, subscribe, resolve_location).
    if fname != "lookup":
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

    # Two ways to recognise a coord-input adapter call:
    # 1. The supplied params already carry coordinate/admcd fields — the
    #    LLM filled them in (possibly from prior knowledge). This is the
    #    primary failure mode the gate exists to catch.
    # 2. The supplied params are empty / coord-free, but the tool_id's
    #    registered input_schema declares coord/admcd fields. The LLM is
    #    about to hit invalid_params; getting here gives the chain hint
    #    one turn earlier and saves the round-trip.
    has_coord = any(k in params for k in _COORD_INPUT_FIELDS)
    has_admcd = any(k in params for k in _ADMCD_INPUT_FIELDS)
    schema_coord_fields: set[str] = set()
    schema_admcd_fields: set[str] = set()
    if not (has_coord or has_admcd):
        # Inspect the adapter's declared input schema to find out whether
        # this is a coord/admcd tool that simply has not been parameterised
        # yet. Best-effort — adapter lookup failures fall through as
        # "unknown shape, allow".
        if registry is None:
            return None
        try:
            tool = registry.lookup(tool_id)
            schema = tool.input_schema.model_json_schema()
            props = schema.get("properties", {})
            schema_coord_fields = set(props) & _COORD_INPUT_FIELDS
            schema_admcd_fields = set(props) & _ADMCD_INPUT_FIELDS
            if not (schema_coord_fields or schema_admcd_fields):
                return None
        except Exception:  # noqa: BLE001
            # Unknown tool / registry not booted — let the dispatcher
            # produce its own unknown_tool error instead of guessing.
            return None

    if tool_id == "nmc_emergency_search":
        has_prior_resolve = False
        for m in llm_messages:
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
            if role != "assistant":
                continue
            tool_calls = getattr(m, "tool_calls", None) or (
                m.get("tool_calls") if isinstance(m, dict) else None
            )
            if tool_calls:
                for tc in tool_calls:
                    call_fn = getattr(getattr(tc, "function", None), "name", None) or (
                        tc.get("function", {}).get("name") if isinstance(tc, dict) else None
                    )
                    if call_fn == "resolve_location":
                        has_prior_resolve = True
            content = getattr(m, "content", None) or (
                m.get("content") if isinstance(m, dict) else None
            )
            if isinstance(content, str) and "resolve_location" in content:
                has_prior_resolve = True
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
                "operation. The prior resolve_location call did not provide the q0/q1 "
                "region-mode parameters used by NMC. RECOVERY: call "
                "resolve_location(query='<지역명>', want='all'), then call "
                "lookup(mode='fetch', tool_id='nmc_emergency_search', "
                "params={mode:'region', q0:region.region_1depth_name, "
                "q1:region.region_2depth_name, origin_lat:coords.lat, "
                "origin_lon:coords.lon, limit:<N>}). Do NOT retry coordinate mode for "
                "station/neighborhood ER search and do NOT invent NMC filters such as QZ."
            )

    # Walk prior turns for a resolve_location invocation. Both function-
    # call envelopes (assistant.tool_calls[*].function.name) and the
    # textual <tool_call> markers (assistant.content) count — K-EXAONE
    # uses both. We accept either as evidence the citizen's location
    # was canonicalised through the registered resolver.
    for m in llm_messages:
        # LLMChatMessage instance OR dict — handle both.
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role != "assistant":
            continue
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if tool_calls:
            for tc in tool_calls:
                call_fn = getattr(getattr(tc, "function", None), "name", None) or (
                    tc.get("function", {}).get("name") if isinstance(tc, dict) else None
                )
                if call_fn == "resolve_location":
                    return None
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        if isinstance(content, str) and "resolve_location" in content:
            # Textual <tool_call> marker fallback for K-EXAONE inline form.
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
            "operations and must receive location fields from resolve_location in the "
            "same conversation. No resolve_location turn precedes the current call. "
            "RECOVERY: in the next turn call resolve_location(query='<지역명>', "
            "want='all'), then call lookup(mode='fetch', tool_id='nmc_emergency_search', "
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
        f"that MUST come from a prior resolve_location call in the same "
        f"conversation. No resolve_location turn precedes the current call — "
        f"that means the values would be guessed from prior knowledge instead "
        f"of being resolved against Kakao Local API. "
        f"RECOVERY: in the next turn call resolve_location(query='<지역명>', "
        f"want='coords') to obtain the canonical lat/lon for the citizen's "
        f"location, then re-invoke this tool with the returned values. Do NOT "
        f"guess coordinates."
    )


# ---------------------------------------------------------------------------
# Follow-up lookup gate (G-class fabrication countermeasure — 2026-05-04)
# ---------------------------------------------------------------------------
# Citizen query keywords that signal "the LLM needs to call a follow-up
# adapter (lookup mode='fetch') after resolve_location returns coordinates
# or admcd". Without the follow-up, LLM fabricates the data from parametric
# memory (the donga-univ-poi-bug 1-day-newer regression: snap-001 captured
# 4.7°C drift / 61%p humidity drift between LLM-claimed values and the raw
# KMA observation).  This list is the policy hint — adapter_id is decided
# by BM25 from the available_adapters suffix.
_FOLLOWUP_REQUIRED_KEYWORDS_KO: frozenset[str] = frozenset(
    {
        "날씨",
        "기온",
        "온도",
        "습도",
        "강수",
        "비",
        "눈",
        "바람",
        "풍속",
        "예보",
        "특보",
        "폭염",
        "한파",
        "황사",
        "미세먼지",
        "병원",
        "응급실",
        "응급의료",
        "의료기관",
        "약국",
        "사고",
        "교통사고",
        "위험",
        "스쿨존",
        "어린이보호구역",
        "구급",
        "119",
        "소방서",
        "재해",
        "복지",
        "급여",
        "보조금",
        "지원금",
    }
)
_FOLLOWUP_REQUIRED_KEYWORDS_EN: frozenset[str] = frozenset(
    {
        "weather",
        "temperature",
        "humidity",
        "rainfall",
        "wind",
        "forecast",
        "warning",
        "hospital",
        "er",
        "emergency",
        "pharmacy",
        "accident",
        "traffic",
        "hazard",
        "ambulance",
        "fire",
        "disaster",
        "welfare",
        "benefit",
        "subsidy",
    }
)


def _query_implies_followup_lookup(user_query: str) -> bool:
    """Return True when the citizen query semantics require a follow-up
    ``lookup(mode='fetch', tool_id=...)`` after ``resolve_location`` resolves
    coordinates.

    G-class chain enforcement: the integration-verification capture
    ``snap-001-01-kma-now`` showed K-EXAONE calling ``resolve_location`` twice
    and then producing a fabricated weather answer (16°C / 84% humidity vs
    raw KMA 20.7°C / 23%) without ever invoking ``lookup(kma_current_observation)``.
    The fabrication mode is deterministic when the citizen query mentions a
    location-bound observable (weather / hospital / accident / 119) — no
    adapter shipped today answers those purely from coordinates.
    """
    if not user_query:
        return False
    q = user_query.lower()
    for kw in _FOLLOWUP_REQUIRED_KEYWORDS_KO:
        if kw in user_query:  # Korean — case is irrelevant
            return True
    return any(kw in q for kw in _FOLLOWUP_REQUIRED_KEYWORDS_EN)


def _check_resolve_terminated_without_followup(  # noqa: C901
    llm_messages: list[Any],
    user_query: str,
) -> str | None:
    """Return chain-recovery error message when the LLM is about to terminate
    a turn without invoking a follow-up ``lookup`` after ``resolve_location``.

    Triggers when ALL of the following hold:
    1. The conversation contains at least one assistant turn that called
       ``resolve_location`` AND the corresponding ``role='tool'`` result.
    2. The conversation contains NO assistant turn that called
       ``lookup`` with ``mode='fetch'`` (or shape-equivalent bare
       ``{tool_id, params}``) on a coord/admcd-input adapter.
    3. The user query mentions a location-bound observable that demands a
       follow-up lookup (weather / hospital / ER / accident / 119 / welfare).

    Returns ``None`` when the call is allowed; returns a descriptive
    error message that the caller injects as a synthetic tool_result so the
    next agentic-loop turn produces the missing ``lookup`` call.

    CC reference parallel: ``Tool.validateInput`` rejection on missing
    prerequisite. The KOSMOS port runs at the *terminal-turn* boundary
    (``if not tool_call_buf:``) because the failure mode here is the inverse
    of the ``_check_chain_prerequisite`` pattern — instead of "called
    coord-input tool too early", this is "stopped after resolve and never
    called the coord-input tool at all".
    """
    if not _query_implies_followup_lookup(user_query):
        return None

    saw_resolve_result = False
    saw_followup_lookup = False
    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        # Detect resolve_location tool result message
        if role == "tool":
            name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)
            if name == "resolve_location":
                saw_resolve_result = True
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
            if call_fn != "lookup":
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

    if not saw_resolve_result:
        return None
    if saw_followup_lookup:
        return None
    return (
        "Chain incomplete: this conversation invoked resolve_location but did NOT "
        "follow up with lookup(mode='fetch', tool_id=<adapter>, params={...}) on "
        "any coord/admcd-input adapter. The citizen query asks about an "
        "observable (weather / hospital / accident / 119 / welfare) whose "
        "authoritative value lives in an external agency API — answering from "
        "coordinates alone IS fabrication (citizen-safety violation per "
        "system_v1.md CRITICAL directive). RECOVERY: in the next turn, choose "
        "the correct adapter from the <available_adapters> block and call "
        "lookup(mode='fetch', tool_id='<adapter>', params={lat: <resolved>, "
        "lon: <resolved>, ...}) using the coordinates returned by the prior "
        "resolve_location turn. Do NOT produce a final answer this turn."
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
        Active :class:`~kosmos.session.manager.SessionManager` instance.
    shutdown:
        Event that signals the stdio loop to exit when set.
    """
    from kosmos.session.store import list_sessions as _list_sessions

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
        :class:`~kosmos.session.manager.SessionManager` instance used by the
        default ``_handle_frame`` handler to implement session lifecycle
        operations.  When ``None`` a default ``SessionManager()`` is
        constructed (uses ``~/.kosmos/sessions``).
    """
    from kosmos.session.manager import SessionManager as _SessionManager

    sid = session_id or str(uuid.uuid4())

    # ---- spec-multi-turn-contamination diagnostic — optional log file
    # The TUI bridge spawns this process with `stderr: 'pipe'` and never
    # drains the pipe, so `logger.info(...)` lines are invisible to any
    # external observer (tmux pane, asciinema cast). When the operator
    # sets KOSMOS_BACKEND_LOG_FILE=<path>, attach a FileHandler at INFO
    # so the diagnostic [CHAT_REQUEST_DUMP] / [LATEST_USER_UTT] /
    # [REASONING_PREVIEW] lines persist to disk for post-hoc analysis.
    # Off by default — production behaviour is unchanged when the env
    # var is unset.
    _log_path = os.getenv("KOSMOS_BACKEND_LOG_FILE")
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
            sys.stderr.write(f"[KOSMOS BACKEND] failed to attach log file {_log_path}\n")

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
    # KOSMOS Epic #2077 — limit=16 MiB. The default asyncio.StreamReader limit
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
    _tool_registry_ref: list[object] = []
    _tool_executor_ref: list[object] = []

    def _ensure_tool_registry() -> object:
        # CC reference: (no direct CC analog — KOSMOS-only IPC adaptation).
        # CC's QueryEngine.ts assumes ToolRegistry populated at SDK construction
        # time (Anthropic SDK ``new Anthropic({...}).messages.stream(...)`` has
        # the registry baked in). KOSMOS's stdio JSONL backend is invoked once
        # per process, ahead of any chat_request, so registration must be lazy
        # to avoid bootstrapping cost when the user runs ``kosmos --list-sessions``
        # or other non-LLM commands. Justified as SWAP/llm-provider per
        # parity-matrix.md § 2026-05-01.
        if not _tool_registry_ref:
            from kosmos.tools.executor import ToolExecutor  # noqa: PLC0415
            from kosmos.tools.register_all import register_all_tools  # noqa: PLC0415
            from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415

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

                from kosmos.ipc.adapter_manifest_emitter import (  # noqa: PLC0415
                    emit_manifest,
                )

                emit_manifest(_sys.stdout, registry)
                logger.info("Emitted AdapterManifestSyncFrame to TUI")
            except Exception as _exc:
                logger.exception("Failed to emit adapter manifest: %s", _exc)
        return _tool_registry_ref[0]

    def _ensure_tool_executor() -> object:
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
            from kosmos.llm.client import LLMClient  # noqa: PLC0415
            from kosmos.llm.config import LLMClientConfig  # noqa: PLC0415

            cfg = LLMClientConfig()
            _llm_client_ref.append(LLMClient(config=cfg))
        return _llm_client_ref[0]

    async def _ensure_system_prompt() -> str | None:
        if _llm_system_prompt_cached[0] is not None:
            return _llm_system_prompt_cached[0] or None
        try:
            from pathlib import Path  # noqa: PLC0415

            from kosmos.context.prompt_loader import PromptLoader  # noqa: PLC0415

            # Default manifest lives at repo-root/prompts/manifest.yaml. The
            # stdio backend runs from repo root when invoked via
            # `uv run kosmos --ipc stdio`, so resolve relative to CWD.
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
        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            AssistantChunkFrame,
            UserInputFrame,
        )
        from kosmos.llm.models import ChatMessage  # noqa: PLC0415

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
        _os_chat_env.environ.get("KOSMOS_TOOL_RESULT_TIMEOUT_SECONDS", "120")
    )
    # Spec 1978 T029 — bound the CC query-engine agentic loop to prevent
    # infinite tool-recall. KOSMOS adopts the CC 2.1.88 query engine
    # architecture (native function calling + streaming + parallel tool
    # dispatch), NOT the academic ReAct paradigm — see memory
    # `feedback_kosmos_uses_cc_query_engine`. The KOSMOS_REACT_MAX_TURNS env
    # name is preserved for backward compatibility with already-shipped
    # configuration; the documented variable is logically the agentic-loop
    # max-turn cap.
    _AGENTIC_LOOP_MAX_TURNS = int(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get(
            "KOSMOS_AGENTIC_LOOP_MAX_TURNS",
            _os_chat_env.environ.get("KOSMOS_REACT_MAX_TURNS", "8"),
        )
    )
    # Epic #2152 R4 — separator between the cacheable static prefix (the
    # PromptLoader-resolved citizen system prompt + the augmented
    # ``## Available tools`` block) and the per-turn dynamic suffix. The
    # literal mirrors CC ``prompts.ts:572-575`` so the same identifier reads
    # familiar to anyone with CC source-map context. Downstream tooling
    # (kosmos.prompt.hash slicing in ``kosmos.llm.client``) splits on this
    # marker to compute the static-prefix-only hash.
    _DYNAMIC_BOUNDARY_MARKER = "\nSYSTEM_PROMPT_DYNAMIC_BOUNDARY\n"  # noqa: N806

    # Spec 2521 (2026-05-01) — BM25 candidate count for the dynamic
    # ``<available_adapters>`` block. Must be small enough to keep the
    # dynamic suffix LLM-readable (over-injecting blows the suffix budget
    # and reduces prompt-cache effectiveness for the static prefix). Five
    # mirrors the historical ``lookup(mode='search')`` default top_k that
    # K-EXAONE had been calling explicitly, so token-budget impact is
    # neutral relative to pre-2521 behavior.
    _AVAILABLE_ADAPTERS_TOP_K = int(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get("KOSMOS_AVAILABLE_ADAPTERS_TOP_K", "5")
    )

    def _build_available_adapters_suffix(user_query: str) -> str:  # noqa: C901
        """Run BM25 against the live registry and emit the citizen-turn
        ``<available_adapters>`` XML block for the dynamic system-prompt
        suffix.

        Returns an empty string on any retrieval failure or when the
        query is blank — fail-open so a flaky retriever does not break
        the citizen path (FR-002 mirror of the lookup primitive's own
        fail-open contract). Logged warnings are picked up by the OTEL
        spans Spec 028 already wires.
        """
        q = (user_query or "").strip()
        if not q:
            return ""
        try:
            from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415
            from kosmos.tools.search import search  # noqa: PLC0415

            registry = cast("ToolRegistry", _ensure_tool_registry())
            candidates = search(
                query=q,
                bm25_index=registry.bm25_index,
                registry=registry,
                top_k=_AVAILABLE_ADAPTERS_TOP_K,
            )
        except Exception:
            logger.exception("BM25 retrieval failed for '%s'", q[:80])
            return ""
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
            lines.append(f"- {c.tool_id} [{c.score:.2f}] — {hint or '(설명 없음)'}")
            # Render the adapter's llm_description (usage prose, ORDERING RULE,
            # prerequisites, worked examples) so the LLM sees the complete
            # "먼저 resolve_location 호출" ordering rule.
            # Bug: without this, the per-field description for nx is truncated
            # and K-EXAONE skips resolve_location, producing invalid_params.
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
            # resolve_location 을 먼저 호출") forced a cross-domain chain that
            # contradicts both the user directive ("chain X / KOSMOS does not
            # force cross-domain chain") and v4 description 5-section
            # self_contained_decl ("이 도구 단독 호출로 완결. resolve_location 등
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
            '규칙: 위 목록의 tool_id 만 lookup({"tool_id":"...", "params":{...}})'
            " 으로 호출하세요. 동일 tool_id 를 한 turn 안에서 반복 호출하지 마세요."
        )
        lines.append(
            'params 는 위에 표시된 정확한 필드명만 사용하세요 — 일반적인 "location"/'
            '"date" 같은 추측 키는 모든 어댑터에서 invalid_params 로 거부됩니다.'
        )
        lines.append(
            "BM25 도구 발견은 백엔드 internal 기능 — lookup(mode='search') 같은 호출은"
            " 무효화됩니다 (Spec 2521)."
        )
        lines.append("</available_adapters>")
        return "\n".join(lines)

    # Spec 1978 T053 — eager-import the Mock adapter tree so every adapter
    # self-registers with its primitive dispatcher before the first chat
    # turn arrives. Equivalent to plan.md "Mock adapter activation"; failure
    # is logged-only because Live tooling can still serve simple queries.
    try:
        import kosmos.tools.mock  # noqa: F401, PLC0415
    except Exception:  # noqa: BLE001
        logger.exception("failed to import kosmos.tools.mock — Mock adapters unavailable")

    # -----------------------------------------------------------------------
    # Spec 1978 T043-T049/T052 — Permission gauntlet bridge
    # -----------------------------------------------------------------------

    _PERM_TIMEOUT_S: float = float(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get("KOSMOS_PERMISSION_TIMEOUT_SECONDS", "60")
    )

    # Primitives that require a citizen permission request when called outside
    # an existing session-grant. Spec 033 Layer 1 (L1) exempts verify/lookup/
    # resolve_location (read-only, public-tier); submit/subscribe are side-
    # effecting (Layer 2/3) and always enter the bridge.
    #
    # Epic #2077 T010 (FR-003) — single-source-of-truth migration: read the
    # gated set from ``kosmos.primitives.GATED_PRIMITIVES`` rather than
    # duplicating the literal set here. The local alias is preserved for
    # downstream call-site brevity (and to keep diff churn minimal in this
    # epic) but the literal set is no longer maintained in this module.
    from kosmos.primitives import (
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

        For gated primitives (submit/subscribe):
        1. Check session_grants cache — auto-allow if already approved.
        2. Emit PermissionRequestFrame and await citizen decision (60 s).
        3. On allow_session: cache grant; write consent receipt.
        4. On allow_once: write consent receipt, no cache.
        5. On deny or timeout: emit synthetic tool_result with error, return False.

        For non-gated primitives (lookup/resolve_location/verify): return True
        immediately without touching the bridge.
        """
        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            PermissionRequestFrame,
            ToolResultEnvelope,
            ToolResultFrame,
        )

        if fname not in _PERMISSION_GATED_PRIMITIVES:
            with _tracer.start_as_current_span("kosmos.permission") as span:
                span.set_attribute("kosmos.permission.mode", "auto_allow")
                span.set_attribute("kosmos.permission.decision", "allow_once")
                span.set_attribute("kosmos.tool.dispatched", fname)
            return True

        # Check session grant cache first (allow_session shortcut — T048).
        session_grant_set = _session_grants.get(session_id, set())
        tool_key = f"{fname}:{args_obj.get('tool_id', fname)}"
        if tool_key in session_grant_set:
            with _tracer.start_as_current_span("kosmos.permission") as span:
                span.set_attribute("kosmos.permission.mode", "auto_allow")
                span.set_attribute("kosmos.permission.decision", "allow_session")
                span.set_attribute("kosmos.tool.dispatched", fname)
            logger.debug("permission: session_grant hit for %s session=%s", tool_key, session_id)
            return True

        # Determine risk level and description from primitive type.
        # verify is LIGHT_GATE (low risk, identity delegation read-only).
        # submit/subscribe are HEAVY_GATE (medium/high risk, side-effecting).
        _PRIM_RISK: dict[str, str] = {  # noqa: N806
            "verify": "low",
            "submit": "high",
            "subscribe": "medium",
        }
        _PRIM_KO: dict[str, str] = {  # noqa: N806
            "verify": "신원 확인을 위해 인증 위임을 요청합니다.",
            "submit": "정부 API에 데이터를 제출합니다. 이 작업은 되돌릴 수 없습니다.",
            "subscribe": "공공 데이터 스트림을 구독합니다.",
        }
        _PRIM_EN: dict[str, str] = {  # noqa: N806
            "verify": "Request identity delegation for verification.",
            "submit": "Submit data to a government API. This action is irreversible.",
            "subscribe": "Subscribe to a public data stream.",
        }

        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        _pending_perms[request_id] = loop.create_future()

        with _tracer.start_as_current_span("kosmos.permission") as perm_span:
            perm_span.set_attribute("kosmos.permission.mode", "ask")
            perm_span.set_attribute("kosmos.tool.dispatched", fname)

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
                perm_span.set_attribute("kosmos.permission.decision", "deny")
                return False

            # Await citizen decision with timeout (D2 invariant).
            decision_frame: Any = None
            try:
                decision_frame = await asyncio.wait_for(
                    _pending_perms[request_id],
                    timeout=_PERM_TIMEOUT_S,
                )
                perm_span.set_attribute("kosmos.permission.decision", "allow_once")
            except TimeoutError:
                logger.warning(
                    "permission: timeout waiting for response to request_id=%s", request_id
                )
                perm_span.set_attribute("kosmos.permission.decision", "timeout")
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
                perm_span.set_attribute("kosmos.permission.decision", "deny")
                # Audit-4 P0-2 — append HMAC-sealed deny record so the audit
                # trail captures BOTH the request emission and the citizen's
                # negative decision. Without this, "permission_denied" tool
                # results have no integrity-verified provenance in the ledger.
                try:
                    from kosmos.permissions.action_digest import (  # noqa: PLC0415
                        compute_action_digest,
                        generate_nonce,
                    )
                    from kosmos.permissions.ledger import (  # noqa: PLC0415
                        append as _ledger_append_deny,
                    )
                    from kosmos.settings import (  # noqa: PLC0415
                        settings as _kosmos_settings_deny,
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
                        ledger_path=_kosmos_settings_deny.permission_ledger_path,
                        key_path=_kosmos_settings_deny.permission_key_path,
                        key_registry_path=_kosmos_settings_deny.permission_key_registry_path,
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
            perm_span.set_attribute("kosmos.permission.decision", decision_label)
            perm_span.set_attribute("kosmos.consent.receipt_id", receipt_id)

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

                consent_dir = _Path.home() / ".kosmos" / "memdir" / "user" / "consent"
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
            # (~/.kosmos/consent_ledger.jsonl). Without this append, allow paths
            # left receipts forgeable: no HMAC seal, no chain prev_hash, no key_id.
            #
            # Failures are logged-only — the citizen has already approved the
            # action and the synthetic tool_result must still be emitted. A
            # follow-up `kosmos permissions verify` run will surface any drift.
            try:
                from kosmos.permissions.action_digest import (  # noqa: PLC0415
                    compute_action_digest,
                    generate_nonce,
                )
                from kosmos.permissions.ledger import (  # noqa: PLC0415
                    append as _ledger_append,
                )
                from kosmos.settings import settings as _kosmos_settings  # noqa: PLC0415

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
                    ledger_path=_kosmos_settings.permission_ledger_path,
                    key_path=_kosmos_settings.permission_key_path,
                    key_registry_path=_kosmos_settings.permission_key_registry_path,
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
            from kosmos.ipc.frame_schema import (  # noqa: PLC0415
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
        from kosmos.ipc.frame_schema import PermissionResponseFrame  # noqa: PLC0415

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
        async generator). Note partition policy divergence: KOSMOS dispatches all
        primitive calls in parallel via ``asyncio.gather`` since the citizen-facing
        primitives (lookup/resolve_location/verify) are read-only-equivalent. CC
        partitions by ``isConcurrencySafe`` (read-only batches parallel,
        write-side serial). Tracking the partition adoption as Deferred Item #2574.

        Called immediately after a tool_call frame is emitted and the Future
        is registered in _pending_calls. Routes by fname, awaits the primitive,
        wraps the result in a ToolResultFrame, emits it to the TUI, then
        resolves _pending_calls[call_id] so the agentic-loop continuation can
        inject the result as a role="tool" message.

        Permission gate: submit/subscribe go through _check_permission_gate
        first. On denial/timeout, the gate itself resolves the Future with an
        error envelope, so this function exits early without double-resolution.

        OTEL: sets kosmos.tool.dispatched on the existing session span.
        """

        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            ToolResultEnvelope,
            ToolResultFrame,
        )

        with _tracer.start_as_current_span("kosmos.tool.dispatch") as span:
            span.set_attribute("kosmos.tool.dispatched", fname)
            span.set_attribute("kosmos.session.id", session_id)

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
                span.set_attribute("kosmos.permission.decision", "deny")
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
            from kosmos.tools._outbound_trace import (  # noqa: PLC0415
                consume_outbound_capture,
                start_outbound_capture,
            )

            _outbound_trace_token = start_outbound_capture()

            try:
                if fname == "verify":
                    from kosmos.primitives.verify import (  # noqa: PLC0415
                        verify,
                    )
                    from kosmos.tools.verify_canonical_map import (  # noqa: PLC0415
                        resolve_family,
                    )

                    # Spec 2297 / Issue #C1 (2026-05-04) — translate
                    # ``tool_id`` → ``family_hint`` via the canonical map
                    # parsed from ``prompts/system_v1.md`` ``<verify_families>``.
                    # The mvp_surface ``_VerifyInputForLLM.translate_tool_id_shape``
                    # validator only fires when the LLM call goes through Pydantic
                    # schema validation; the IPC stdio dispatcher bypasses that
                    # path and historically read ``family_hint`` directly from
                    # the args dict, leaving every K-EXAONE-emitted
                    # ``verify({tool_id: …})`` call resolving to ``family_hint=""``
                    # → "No verify adapter registered for family ''".
                    # Accept both ``family`` (citizen-facing tool schema) and
                    # ``family_hint`` (primitive's internal arg name) for
                    # legacy / tools-bridge compatibility.
                    tool_id = str(args_obj.get("tool_id") or "")
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

                elif fname == "lookup":
                    # Spec 2521 (2026-05-01): the LLM-visible ``lookup``
                    # surface is fetch-only. BM25 adapter discovery is a
                    # backend-internal mechanism (auto-injected into the
                    # ``<available_adapters>`` dynamic suffix) — the LLM
                    # MUST NOT see "search" as a callable mode. Stale
                    # ``mode='search'`` payloads from older sessions are
                    # rejected with a typed LookupError so the agentic
                    # loop continues without painting an "internal
                    # function as tool" UI block.
                    from kosmos.tools.errors import LookupErrorReason  # noqa: PLC0415
                    from kosmos.tools.lookup import lookup  # noqa: PLC0415
                    from kosmos.tools.models import (  # noqa: PLC0415
                        LookupError,  # noqa: A004 — Pydantic model named LookupError; intentional shadow with module-level alias not feasible in narrow import scope
                        LookupFetchInput,
                    )

                    requested_mode = args_obj.get("mode")
                    if requested_mode is not None and str(requested_mode) != "fetch":
                        logger.warning(
                            "lookup: rejected mode=%r — LLM-visible surface is "
                            "fetch-only since Spec 2521. Skipping dispatch.",
                            requested_mode,
                        )
                        raw = LookupError(
                            kind="error",
                            reason=LookupErrorReason.invalid_params,
                            message=(
                                "lookup(mode='search') 는 백엔드 internal 기능입니다 — "
                                "직접 호출하지 마십시오. 시스템 프롬프트의 "
                                "<available_adapters> 에서 tool_id 를 골라 fetch 호출만 사용하세요."
                            ),
                            retryable=False,
                        )
                        result_payload = {
                            "kind": "lookup",
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
                        raw = await lookup(
                            inp_lk,
                            registry=registry,
                            executor=executor,
                            session_identity=session_id,
                        )
                        result_payload = {
                            "kind": "lookup",
                            "result": _serialize_primitive_result(raw),
                        }

                elif fname == "resolve_location":
                    from kosmos.tools.models import ResolveLocationInput  # noqa: PLC0415
                    from kosmos.tools.resolve_location import resolve_location  # noqa: PLC0415

                    inp_rl = ResolveLocationInput(
                        query=str(args_obj.get("query", "")),
                        want=str(args_obj.get("want", "coords_and_admcd")),  # type: ignore[arg-type]
                    )
                    raw = await resolve_location(inp_rl)
                    result_payload = {
                        "kind": "resolve_location",
                        "result": _serialize_primitive_result(raw),
                    }

                elif fname == "submit":
                    from kosmos.primitives.submit import submit  # noqa: PLC0415

                    auth_context = _session_auth_contexts.get(session_id)
                    submit_params = cast("dict[str, object]", args_obj.get("params") or {})
                    if auth_context is not None:
                        submit_params = _inject_delegation_context(submit_params, auth_context)
                    delegation_session_id = _session_auth_session_ids.get(session_id, session_id)
                    submit_params = _bind_submit_session_id(
                        submit_params,
                        session_id=delegation_session_id,
                    )
                    raw = await submit(
                        tool_id=str(args_obj.get("tool_id", "")),
                        params=submit_params,
                        auth_context=auth_context,
                        session_id=session_id,
                    )
                    result_payload = {
                        "kind": "submit",
                        "result": _serialize_primitive_result(raw),
                    }

                elif fname == "subscribe":
                    # T069 streaming events are deferred. Return the SubscriptionHandle.
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                        WorkerStatusFrame,
                    )
                    from kosmos.primitives.subscribe import (  # noqa: PLC0415
                        SubscribeInput,
                        _SubscribeIterator,
                        subscribe,
                    )

                    inp_sub = SubscribeInput(
                        tool_id=str(args_obj.get("tool_id", "")),
                        params=cast("dict[str, object]", args_obj.get("params") or {}),
                        lifetime_seconds=int(cast("Any", args_obj.get("lifetime_seconds", 300))),
                    )
                    iterator_or_error = subscribe(inp_sub)
                    if isinstance(iterator_or_error, _SubscribeIterator):
                        # Audit-5 P0-2 fix (2026-05-04): use the canonical
                        # subscription_id from the real ``SubscriptionHandle``
                        # so the TUI ``subscriptionRegistry`` key matches every
                        # subsequent OTEL span / drop event / consent ledger
                        # entry. Synthetic ``uuid.uuid4()`` removed.
                        handle = iterator_or_error.peek_handle()
                        result_payload = {
                            "kind": "subscribe",
                            "subscription_id": handle.subscription_id,
                            "handle_id": handle.subscription_id,  # alias for TS-side
                            "tool_id": inp_sub.tool_id,
                            "opened_at": handle.opened_at.isoformat(),
                            "closes_at": handle.closes_at.isoformat(),
                            "lifetime_seconds": int(inp_sub.lifetime_seconds),
                            "status": "opened",
                            "note": "Streaming events deferred (T069).",
                        }

                        # Audit-5 P0-4 fix (2026-05-04): emit a WorkerStatusFrame
                        # so the TUI ``AgentVisibilityPanel`` (subscribed via
                        # ``bridge.frames()``) records the active subscription
                        # channel as a "running" ministry agent. The panel maps
                        # ``role_id`` → display label; we pass the adapter
                        # ``tool_id`` so the citizen sees the real source name.
                        # The frontend ``subscriptionRegistry`` (TS-side) and
                        # this ``worker_status`` IPC stream now agree on the
                        # same ``worker_id`` (``subscribe:<subscription_id>``).
                        try:
                            ws_frame = WorkerStatusFrame(
                                session_id=session_id,
                                correlation_id=correlation_id,
                                ts=_utcnow(),
                                role="backend",
                                kind="worker_status",
                                worker_id=f"subscribe:{handle.subscription_id}",
                                role_id=inp_sub.tool_id,
                                current_primitive="subscribe",
                                status="running",
                            )
                            await write_frame(ws_frame)
                        except Exception as _ws_exc:  # noqa: BLE001
                            logger.warning(
                                "subscribe: failed to emit worker_status frame: %s",
                                _ws_exc,
                            )
                    else:
                        # AdapterNotFoundError or similar
                        result_payload = {
                            "kind": "subscribe",
                            "error": str(iterator_or_error),
                            "tool_id": str(args_obj.get("tool_id", "")),
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
        (yieldMissingToolResultBlocks pattern). Behavior-mirror: KOSMOS preserves
        CC's per-turn message_id, structured tool_calls dispatch, role="tool"
        injection between turns, max_turns termination semantics. The only
        divergence is the I/O surface — CC reads from Anthropic SDK stream,
        KOSMOS reads from FriendliAI OpenAI-compat SSE via LLMClient and emits
        IPCFrames over stdio JSONL (Spec 287 / Spec 032 IPC contract).

        Implements the CC (Claude Code 2.1.88) query-engine agentic loop —
        native function calling + token streaming + parallel tool dispatch
        + content_block accumulation, NOT the academic ReAct paradigm
        (text-marker-based Thought/Action). See memory
        ``feedback_kosmos_uses_cc_query_engine`` for the architectural
        rationale.

        Replaces ``_handle_user_input_llm`` for ``ChatRequestFrame``. Streams
        text deltas as ``AssistantChunkFrame``, emits one ``ToolCallFrame``
        per K-EXAONE function-call, awaits each matching ``ToolResultFrame``
        via ``_pending_calls`` Futures, then injects synthetic
        ``role="tool"`` messages into the local history and re-invokes
        ``LLMClient.stream`` (agentic-loop continuation per ADR-0005).

        Loop is bounded by ``KOSMOS_AGENTIC_LOOP_MAX_TURNS`` (default 8;
        also accepts the legacy ``KOSMOS_REACT_MAX_TURNS``) and the
        per-call wait by ``KOSMOS_TOOL_RESULT_TIMEOUT_SECONDS`` (default 120).
        """
        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            AssistantChunkFrame,
            ChatRequestFrame,
            ToolCallFrame,
        )
        from kosmos.llm.models import (  # noqa: PLC0415
            ChatMessage as LLMChatMessage,
        )
        from kosmos.llm.models import (
            FunctionCall as LLMFunctionCall,
        )
        from kosmos.llm.models import (
            ToolCall as LLMToolCall,
        )
        from kosmos.llm.models import (
            ToolDefinition as LLMToolDefinition,
        )
        from kosmos.llm.system_prompt_builder import (  # noqa: PLC0415
            build_system_prompt_with_tools,
        )

        if not isinstance(frame, ChatRequestFrame):
            return

        # ---- spec-multi-turn-contamination diagnostic emit (FR-001/FR-002)
        # Increment the per-session turn counter and dump the inbound
        # ChatRequestFrame.messages tail so we can prove which user turn
        # K-EXAONE actually saw on the wire. Off by default; gated by
        # KOSMOS_CHAT_REQUEST_DUMP=1. Truncates each message content to
        # 256 chars to keep the log line bounded.
        # Always increment the counter so OTEL `kosmos.chat.turn_index`
        # works regardless of the env-gated stderr dump.
        _diag_turn_idx = _session_turn_counter.get(frame.session_id, 0) + 1
        _session_turn_counter[frame.session_id] = _diag_turn_idx
        # Additive Spec 021 OTEL extension — annotate the parent
        # `kosmos.ipc.frame` span (opened by the reader loop) with the
        # turn index so Langfuse traces can group multi-turn flows.
        try:
            _current_span = trace.get_current_span()
            if _current_span is not None:
                _current_span.set_attribute("kosmos.chat.turn_index", _diag_turn_idx)
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
        # truth, BUT only the five LLM-callable primitives go into the
        # ``tools`` parameter the model sees. KOSMOS architecture
        # (docs/vision.md L1-C): `system prompt exposes primitive
        # signatures only; BM25 surfaces adapters dynamically`. Adapter
        # tools (kma_*, hira_*, nmc_*, koroad_*, mohw_*, nfa_*) are
        # invoked via `lookup(tool_id="<adapter_id>", params={...})`,
        # never directly. The previous version of this block
        # (commit 5050417f) emitted every core_tool — primitive AND
        # adapter — into the tools[] parameter, which let K-EXAONE call
        # adapter ids directly (e.g. `kma_current_observation()` instead
        # of `lookup(tool_id="kma_current_observation", params=...)`).
        # The dispatcher then rejected the call with "Model requested
        # unknown tool 'kma_current_observation'" because PRIMITIVE_REGISTRY
        # only contains the five primitives. Captured live in
        # specs/integration-verification/donga-univ-poi-bug/
        # snap-001-01-kma-now (2026-05-04).
        #
        # Filtering by `ministry == "KOSMOS"` AND id in the primitive
        # whitelist matches the intent of mvp_surface.py — the five
        # GovAPITool entries with `primitive=` field set are exactly
        # the LLM-callable surface. Adapters (every other ministry) flow
        # through the `<available_adapters>` system-prompt suffix that
        # `_build_available_adapters_suffix` emits below.
        registry = cast("Any", _ensure_tool_registry())
        from kosmos.primitives import PRIMITIVE_REGISTRY  # noqa: PLC0415

        backend_tools_raw = [
            t.to_openai_tool()
            for t in registry.core_tools()
            if t.ministry == "KOSMOS" and t.id in PRIMITIVE_REGISTRY
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
        from kosmos.ipc.citizen_request import (  # noqa: PLC0415
            wrap_citizen_request,
        )

        # G-class chain enforcement (2026-05-04) — top-level scope so the
        # follow-up-lookup gate inside the agentic loop can read the original
        # citizen utterance to decide whether the conversation must end with a
        # `lookup(mode='fetch', ...)` call (weather / hospital / accident /
        # 119 / welfare queries) before the LLM is allowed to produce a final
        # answer. Lifted out of the BM25 try-block so the variable survives
        # the suffix-builder failure path.
        latest_user_utt = ""

        base_system = frame.system
        if not base_system:
            loaded = await _ensure_system_prompt()
            base_system = loaded or ""
        augmented_system = build_system_prompt_with_tools(base_system, llm_tools)
        if augmented_system:
            augmented_system = augmented_system + _DYNAMIC_BOUNDARY_MARKER
            # KOSMOS hotfix #2520 (2026-04-30 user report — 날짜 hallucination):
            # CC 원본 (.references/claude-code-sourcemap/restored-src/src/constants/
            # prompts.ts:452) 은 system prompt 첫 paragraph 에 동적으로
            # `Date: ${getSessionStartDate()}` 를 inject. KOSMOS 는 prompts/
            # system_v1.md (static markdown) 만 사용해서 LLM 이 자기 추측으로 날짜
            # 답변 → "현재 날짜인 2026년 3월 5일 기준으로 부산 사하구의 날씨 정보"
            # 같은 hallucination. _DYNAMIC_BOUNDARY_MARKER 뒤는 prompt-cache의
            # dynamic-context section 이므로 여기에 today 주입해도 cache prefix
            #
            # KOSMOS hotfix (2026-05-04, KMA base_time hallucination 차단):
            # `오늘 날짜 (UTC)` 만 inject 하면 LLM 이 KMA `base_time` (KST HHMM)
            # 을 추측 (e.g. `0700`). KMA 단기예보/실황 발표 시각은 KST
            # 0200/0500/0800/1100/1400/1700/2000/2300 — 잘못된 base_time 은
            # 4-9 시간 시차의 fabrication 으로 이어짐. 시민 안전 directive 위반.
            # 따라서 KST 날짜 + KST 현재 시각 (HH:MM, HHMM) 둘 다 inject —
            # 도구 description 이 "직전 정시" 를 참조할 수 있도록.
            # invariant 유지. ISO 8601 date format (YYYY-MM-DD) 으로 표기.
            from datetime import datetime  # noqa: PLC0415
            from zoneinfo import ZoneInfo  # noqa: PLC0415

            _kst = ZoneInfo("Asia/Seoul")
            _now_kst = datetime.now(tz=_kst)
            today_kst_iso = _now_kst.strftime("%Y-%m-%d")
            now_kst_hm = _now_kst.strftime("%H:%M")
            now_kst_hhmm = _now_kst.strftime("%H%M")
            # KMA base_time 은 KST 정시 발표 (0200/0500/0800/1100/1400/
            # 1700/2000/2300). 현재 KST 시각의 직전 정시 hint 도 함께 emit
            # — LLM 이 추측하지 않도록.
            _valid_base_times = (2, 5, 8, 11, 14, 17, 20, 23)
            _h = _now_kst.hour
            _prev = max(
                (b for b in _valid_base_times if b <= _h),
                default=_valid_base_times[-1],
            )
            # 오늘 시각이 첫 발표(0200) 이전이면 어제 2300 사용
            if _h < _valid_base_times[0]:
                _kma_base_date = (_now_kst.replace(hour=23, minute=0)).strftime("%Y%m%d")
                _kma_base_time = "2300"
                _kma_hint_note = "어제"
            else:
                _kma_base_date = _now_kst.strftime("%Y%m%d")
                _kma_base_time = f"{_prev:02d}00"
                _kma_hint_note = "오늘"
            augmented_system = (
                augmented_system + f"\n\n## Current session context\n\n"
                f"오늘 날짜 (KST): {today_kst_iso}.\n"
                f"현재 시각 (KST): {now_kst_hm} ({now_kst_hhmm}).\n"
                "이 날짜/시각을 기준으로 시간 표현을 해석합니다. "
                "날짜/시간 정보를 추측 또는 fabricate 하지 말고, "
                "필요하면 도구 (예: kma_short_term_forecast) 를 호출해서 "
                "실제 데이터를 받아 응답에 인용합니다.\n"
                "KMA 단기예보/실황 발표 시각은 KST 정시 8회: "
                "0200/0500/0800/1100/1400/1700/2000/2300. "
                f"현재 KST 시각의 직전 발표는 {_kma_hint_note} "
                f"base_date={_kma_base_date}, base_time={_kma_base_time}. "
                "base_time 추측 금지 — 위 hint 또는 그 이전 정시 사용.\n"
            )

            # Spec 2521 (2026-05-01) — BM25 adapter discovery is a backend
            # function, NOT an LLM-callable tool. Run the search against the
            # latest citizen utterance and inject the top-K candidates into
            # the dynamic suffix as ``<available_adapters>``. The LLM picks
            # a tool_id from this block and calls ``lookup({tool_id, params})``
            # — search-mode calls were the source of the "● lookup(search:)"
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
        from kosmos.llm.tool_call_parser import StreamGate  # noqa: PLC0415

        # Neurosymbolic constraint flag — set when the chain-prerequisite
        # gate rejected a coord-input tool call earlier in the loop. The
        # next LLM turn forces tool_choice=resolve_location, removing the
        # bypass path the LLM used in donga-univ-poi-bug captures
        # (the LLM read the chain hint and then refused the tool anyway,
        # answering "I don't have a location resolver" — a documented
        # failure mode in the 2026 hallucination literature: business
        # rules in prompts are interpreted as suggestions, not constraints,
        # so the constraint must move to the API layer where the model
        # cannot bypass it). Once a turn fires resolve_location the flag
        # clears so the agentic loop returns to free tool_choice.
        force_resolve_location_next_turn = False
        force_verify_next_turn = _initial_verify_tool_choice_for_query(
            llm_messages,
            latest_user_utt,
        )
        force_lookup_next_turn: str | None = None
        force_submit_next_turn: str | None = None
        force_subscribe_next_turn: str | None = None
        continue_free_next_turn = False
        mock_disclosure_required = False

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

            async def _dispatch_synthetic_submit_followup(
                submit_followup_gate: dict[str, str],
                *,
                message_id_for_turn: str,
                reason: str,
            ) -> Literal["continue", "return"]:
                """Run the required submit adapter after verify using cached auth context."""
                nonlocal mock_disclosure_required

                synth_call_id = str(uuid.uuid4())
                submit_args = {
                    "tool_id": submit_followup_gate["tool_id"],
                    "params": _stdlib_json.loads(submit_followup_gate["params_json"]),
                }
                await write_frame(
                    ToolCallFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="tool_call",
                        call_id=synth_call_id,
                        name="submit",
                        arguments=submit_args,
                    )
                )
                loop = asyncio.get_event_loop()
                _pending_calls[synth_call_id] = loop.create_future()
                asyncio.create_task(
                    _dispatch_primitive(
                        synth_call_id,
                        "submit",
                        submit_args,
                        frame.session_id,
                        frame.correlation_id,
                    ),
                    name=f"primitive-submit-{synth_call_id[:8]}",
                )
                llm_messages.append(
                    LLMChatMessage(
                        role="assistant",
                        content="",
                        tool_calls=[
                            LLMToolCall(
                                id=synth_call_id,
                                type="function",
                                function=LLMFunctionCall(
                                    name="submit",
                                    arguments=_json.dumps(
                                        submit_args,
                                        ensure_ascii=False,
                                    ),
                                ),
                            )
                        ],
                    )
                )
                try:
                    result = await asyncio.wait_for(
                        _pending_calls[synth_call_id],
                        timeout=_TOOL_RESULT_TIMEOUT_S,
                    )
                except TimeoutError:
                    pending = _pending_calls.pop(synth_call_id, None)
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
                            details={"call_ids": [synth_call_id]},
                        )
                    )
                    return "return"

                envelope = getattr(result, "envelope", None)
                if envelope is not None and hasattr(envelope, "model_dump"):
                    envelope_dump = envelope.model_dump()
                    if _contains_mock_marker(envelope_dump):
                        mock_disclosure_required = True
                    if envelope_dump.get("denied") is True and envelope_dump.get("error") in {
                        "permission_denied",
                        "permission_timeout",
                    }:
                        code = str(envelope_dump["error"])
                        if code == "permission_timeout":
                            denial_message = (
                                "권한 응답 시간이 초과되어 작업을 진행하지 않았습니다. "
                                "후속 제출 작업은 실행되지 않았습니다. "
                                f"(code: {code})"
                            )
                        else:
                            denial_message = (
                                "권한 요청이 거부되어 작업을 진행하지 않았습니다. "
                                "후속 제출 작업은 실행되지 않았습니다. "
                                f"(code: {code})"
                            )
                        await write_frame(
                            AssistantChunkFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="llm",
                                ts=_utcnow(),
                                kind="assistant_chunk",
                                message_id=message_id_for_turn,
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
                                message_id=message_id_for_turn,
                                delta="",
                                done=True,
                            )
                        )
                        return "return"
                    payload = _json.dumps(
                        envelope_dump,
                        ensure_ascii=False,
                        default=str,
                    )
                else:
                    payload = _json.dumps({"result": str(result)}, ensure_ascii=False)

                llm_messages.append(
                    LLMChatMessage(
                        role="tool",
                        content=payload,
                        name="submit",
                        tool_call_id=synth_call_id,
                    )
                )
                if envelope is not None and hasattr(envelope, "model_dump"):
                    final_answer = _synthetic_submit_final_answer(
                        submit_followup_gate["tool_id"],
                        submit_args,
                        envelope_dump,
                    )
                    if final_answer is not None:
                        await write_frame(
                            AssistantChunkFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="llm",
                                ts=_utcnow(),
                                kind="assistant_chunk",
                                message_id=message_id_for_turn,
                                delta=final_answer,
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
                                message_id=message_id_for_turn,
                                delta="",
                                done=True,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: %s. Dispatched synthetic submit "
                            "call and emitted deterministic receipt answer (%s).",
                            reason,
                            submit_followup_gate["tool_id"],
                        )
                        return "return"
                logger.warning(
                    "_handle_chat_request: %s. Dispatched synthetic submit call immediately (%s).",
                    reason,
                    submit_followup_gate["tool_id"],
                )
                return "continue"

            # spec-multi-turn-contamination diagnostic — accumulate the K-EXAONE
            # reasoning_content stream so we can compare its first 1024 bytes
            # against [LATEST_USER_UTT]. If reasoning starts with text that
            # paraphrases an earlier turn, H2 (model-side state contamination)
            # is confirmed even when the wire-level messages are correct.
            # Off by default; gated by KOSMOS_CHAT_REQUEST_DUMP=1.
            _diag_reasoning_buf: list[str] = []
            _diag_reasoning_emitted = False

            # Materialise the tool_choice for this turn from the gate flag.
            # When forced, OpenAI/FriendliAI accept the explicit-function
            # form (verified live against FriendliAI Serverless 2026-05-04);
            # K-EXAONE on FriendliAI honours it as a hard constraint at the
            # decoding boundary rather than a system-prompt hint.
            stream_tool_choice: str | dict[str, object] | None = None
            if force_resolve_location_next_turn:
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "resolve_location"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=resolve_location for "
                    "turn %d (chain gate previously rejected a coord-input call)",
                    _turn,
                )
            elif force_verify_next_turn is not None:
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "verify"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=verify for turn %d "
                    "(sensitive lookup gate requires %s)",
                    _turn,
                    force_verify_next_turn,
                )
            elif force_lookup_next_turn is not None:
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "lookup"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=lookup for turn %d "
                    "(sensitive lookup gate requires %s)",
                    _turn,
                    force_lookup_next_turn,
                )
            elif force_submit_next_turn is not None:
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "submit"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=submit for turn %d "
                    "(submit gate requires %s)",
                    _turn,
                    force_submit_next_turn,
                )
            elif force_subscribe_next_turn is not None:
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "subscribe"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=subscribe for turn %d "
                    "(subscribe gate requires %s)",
                    _turn,
                    force_subscribe_next_turn,
                )
            try:
                async for event in client.stream(  # type: ignore[attr-defined]
                    messages=llm_messages,
                    tools=llm_tools or None,
                    temperature=frame.temperature,
                    top_p=frame.top_p,
                    max_tokens=frame.max_tokens,
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
                        # (``kosmos/llm/_cc_reference/claude.ts:2148-2161``).
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
            if not tool_call_buf and "<tool_call>" in assistant_text_full:
                from kosmos.llm.tool_call_parser import (  # noqa: PLC0415
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
                    synth_call_id = str(uuid.uuid4())
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=synth_call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name="resolve_location",
                                        arguments=_json.dumps(
                                            {
                                                "query": latest_user_utt,
                                                "want": "coords_and_admcd",
                                            },
                                            ensure_ascii=False,
                                        ),
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
                                    "reason": "location_prerequisite_missing",
                                    "message": location_gate_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name="resolve_location",
                            tool_call_id=synth_call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected final-answer turn — "
                        "location-like request terminated without resolve_location. "
                        "Re-entering loop with resolve_location forced."
                    )
                    buffered_visible.clear()
                    force_resolve_location_next_turn = True
                    continue

                verify_gate = _check_verify_terminated_without_verify(llm_messages, latest_user_utt)
                if verify_gate is not None:
                    synth_call_id = str(uuid.uuid4())
                    verify_args: dict[str, object] = {
                        "tool_id": verify_gate["verify_tool_id"],
                        "params": {
                            "scope_list": list(_requirement_scope_entries(verify_gate)),
                            "purpose_ko": verify_gate["purpose_ko"],
                            "purpose_en": verify_gate["purpose_en"],
                        },
                    }
                    await write_frame(
                        ToolCallFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_call",
                            call_id=synth_call_id,
                            name="verify",
                            arguments=verify_args,
                        )
                    )
                    loop = asyncio.get_event_loop()
                    _pending_calls[synth_call_id] = loop.create_future()
                    asyncio.create_task(
                        _dispatch_primitive(
                            synth_call_id,
                            "verify",
                            verify_args,
                            frame.session_id,
                            frame.correlation_id,
                        ),
                        name=f"primitive-verify-{synth_call_id[:8]}",
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=synth_call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name="verify",
                                        arguments=_json.dumps(
                                            verify_args,
                                            ensure_ascii=False,
                                        ),
                                    ),
                                )
                            ],
                        )
                    )
                    try:
                        result = await asyncio.wait_for(
                            _pending_calls[synth_call_id],
                            timeout=_TOOL_RESULT_TIMEOUT_S,
                        )
                    except TimeoutError:
                        pending = _pending_calls.pop(synth_call_id, None)
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
                                message=(
                                    f"Tool result timeout after {_TOOL_RESULT_TIMEOUT_S:.0f}s"
                                ),
                                details={"call_ids": [synth_call_id]},
                            )
                        )
                        return

                    envelope = getattr(result, "envelope", None)
                    if envelope is not None and hasattr(envelope, "model_dump"):
                        envelope_dump = envelope.model_dump()
                        if _contains_mock_marker(envelope_dump):
                            mock_disclosure_required = True
                        if envelope_dump.get("denied") is True and envelope_dump.get("error") in {
                            "permission_denied",
                            "permission_timeout",
                        }:
                            code = str(envelope_dump["error"])
                            if code == "permission_timeout":
                                denial_message = (
                                    "권한 응답 시간이 초과되어 작업을 진행하지 않았습니다. "
                                    "후속 제출 또는 구독 작업은 실행되지 않았습니다. "
                                    f"(code: {code})"
                                )
                            else:
                                denial_message = (
                                    "권한 요청이 거부되어 작업을 진행하지 않았습니다. "
                                    "후속 제출 또는 구독 작업은 실행되지 않았습니다. "
                                    f"(code: {code})"
                                )
                            await write_frame(
                                AssistantChunkFrame(
                                    session_id=frame.session_id,
                                    correlation_id=frame.correlation_id,
                                    role="llm",
                                    ts=_utcnow(),
                                    kind="assistant_chunk",
                                    message_id=message_id,
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
                                    message_id=message_id,
                                    delta="",
                                    done=True,
                                )
                            )
                            return
                        payload = _json.dumps(
                            envelope_dump,
                            ensure_ascii=False,
                            default=str,
                        )
                    else:
                        payload = _json.dumps({"result": str(result)}, ensure_ascii=False)

                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=payload,
                            name="verify",
                            tool_call_id=synth_call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected final-answer turn — "
                        "verify-required request terminated without verify. "
                        "Dispatched synthetic verify call immediately (%s).",
                        verify_gate["verify_tool_id"],
                    )
                    buffered_visible.clear()
                    continue

                submit_followup_gate = _check_submit_terminated_without_submit(
                    llm_messages,
                    latest_user_utt,
                    _session_auth_contexts.get(frame.session_id),
                )
                if submit_followup_gate is not None:
                    synthetic_submit_outcome = await _dispatch_synthetic_submit_followup(
                        submit_followup_gate,
                        message_id_for_turn=message_id,
                        reason=(
                            "rejected final-answer turn — submit-class request "
                            "verified but ended without submit"
                        ),
                    )
                    if synthetic_submit_outcome == "return":
                        return
                    buffered_visible.clear()
                    continue

                sensitive_lookup_followup_gate = _check_sensitive_lookup_terminated_without_lookup(
                    llm_messages,
                    latest_user_utt,
                    _session_auth_contexts.get(frame.session_id),
                )
                if sensitive_lookup_followup_gate is not None:
                    synth_call_id = str(uuid.uuid4())
                    lookup_args = {
                        "mode": "fetch",
                        "tool_id": sensitive_lookup_followup_gate["tool_id"],
                        "params": {},
                    }
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=synth_call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name="lookup",
                                        arguments=_json.dumps(
                                            lookup_args,
                                            ensure_ascii=False,
                                        ),
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
                                    "reason": "sensitive_lookup_followup_missing",
                                    "message": sensitive_lookup_followup_gate["message"],
                                },
                                ensure_ascii=False,
                            ),
                            name="lookup",
                            tool_call_id=synth_call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected final-answer turn — "
                        "sensitive lookup request verified but ended without "
                        "the required lookup. Re-entering loop with lookup "
                        "forced (%s).",
                        sensitive_lookup_followup_gate["tool_id"],
                    )
                    buffered_visible.clear()
                    force_lookup_next_turn = sensitive_lookup_followup_gate["tool_id"]
                    continue

                subscribe_followup_gate = _check_subscribe_terminated_without_subscribe(
                    llm_messages,
                    latest_user_utt,
                )
                if subscribe_followup_gate is not None:
                    synth_call_id = str(uuid.uuid4())
                    subscribe_args = {
                        "tool_id": subscribe_followup_gate["tool_id"],
                        "params": _stdlib_json.loads(subscribe_followup_gate["params_json"]),
                        "lifetime_seconds": int(subscribe_followup_gate["lifetime_seconds"]),
                    }
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=synth_call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name="subscribe",
                                        arguments=_json.dumps(
                                            subscribe_args,
                                            ensure_ascii=False,
                                        ),
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
                                    "reason": "subscribe_followup_missing",
                                    "message": subscribe_followup_gate["message"],
                                },
                                ensure_ascii=False,
                            ),
                            name="subscribe",
                            tool_call_id=synth_call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected final-answer turn — "
                        "subscription request ended without subscribe. "
                        "Re-entering loop with subscribe forced (%s).",
                        subscribe_followup_gate["tool_id"],
                    )
                    buffered_visible.clear()
                    force_subscribe_next_turn = subscribe_followup_gate["tool_id"]
                    continue

                # ---- G-class fabrication gate (2026-05-04) ---------------
                # Before emitting a final-answer turn, check whether the
                # conversation invoked resolve_location but never followed up
                # with a coord/admcd-input lookup despite the citizen query
                # demanding one (weather / hospital / accident / 119 /
                # welfare). The donga-univ-poi-bug snap-001-01-kma-now
                # capture (2026-05-04) showed K-EXAONE producing 16°C / 84%
                # humidity by parametric memory — 4.7°C / 61%p drift versus
                # the raw KMA observation — because the agentic loop allowed
                # the answer turn to fire without a tool result in scope.
                # Inject a synthetic chain-recovery tool_result and continue
                # the loop so the next turn produces the missing lookup call.
                chain_followup_msg = _check_resolve_terminated_without_followup(
                    llm_messages, latest_user_utt
                )
                if chain_followup_msg is not None:
                    synth_call_id = str(uuid.uuid4())
                    # Synthesise an assistant turn that appears to have
                    # called a sentinel "chain_gate" — keeps the message
                    # ordering invariant (assistant tool_calls precede the
                    # role='tool' content). The model will not see this
                    # call_id again — only the role='tool' content matters.
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=synth_call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name="lookup",
                                        arguments=_json.dumps(
                                            {
                                                "mode": "fetch",
                                                "tool_id": "<chain-gate-pending>",
                                                "params": {},
                                            }
                                        ),
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
                                    "reason": "chain_followup_missing",
                                    "message": chain_followup_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name="lookup",
                            tool_call_id=synth_call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected final-answer turn — "
                        "resolve_location ran but follow-up lookup was never "
                        "invoked despite citizen query implying it. "
                        "Re-entering loop with chain-recovery hint."
                    )
                    # Drop the buffered prose so the citizen never sees the
                    # fabrication that the LLM was about to emit.
                    buffered_visible.clear()
                    continue

                merged_prose = "".join(buffered_visible)
                if mock_disclosure_required:
                    merged_prose = _ensure_mock_disclosure(merged_prose)
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
                args_obj = _normalize_lookup_args_for_query(
                    fname,
                    args_obj,
                    latest_user_utt,
                )
                args_obj = _normalize_submit_args_for_query(
                    fname,
                    args_obj,
                    latest_user_utt,
                )
                args_obj = _normalize_verify_args_for_query(
                    fname,
                    args_obj,
                    latest_user_utt,
                )
                args_obj = _normalize_verify_tool_id_for_query(
                    fname,
                    args_obj,
                    latest_user_utt,
                )
                # Epic #2077 FR-003 — registry-derived whitelist. spec.md
                # § Out of Scope (Permanent) forbids hardcoded enumerations
                # outside the registry; ``PRIMITIVE_REGISTRY`` is the single
                # source of truth for LLM-visible primitive names.
                from kosmos.primitives import PRIMITIVE_REGISTRY  # noqa: PLC0415

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
                    if primitive == "verify":
                        force_verify_next_turn = resolve_redirect["tool_id"]
                    elif primitive == "submit":
                        force_submit_next_turn = resolve_redirect["tool_id"]
                    elif primitive == "lookup":
                        force_lookup_next_turn = resolve_redirect["tool_id"]
                    else:
                        continue_free_next_turn = True
                    logger.warning(
                        "_handle_chat_request: suppressed irrelevant resolve_location "
                        "call_id=%s for location-independent workflow; next=%s:%s",
                        call_id[:12],
                        primitive,
                        resolve_redirect["tool_id"],
                    )
                    continue

                wrong_primitive_gate = _check_lookup_wrong_primitive_prerequisite(
                    fname,
                    args_obj,
                )
                if wrong_primitive_gate is not None:
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
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
                                "reason": "wrong_primitive",
                                "message": wrong_primitive_gate["message"],
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
                                    "reason": "wrong_primitive",
                                    "message": wrong_primitive_gate["message"],
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    force_subscribe_next_turn = wrong_primitive_gate["tool_id"]
                    logger.warning(
                        "_handle_chat_request: rejected %s call_id=%s — "
                        "adapter belongs to subscribe primitive",
                        fname,
                        call_id[:12],
                    )
                    continue

                duplicate_submit_msg = _check_duplicate_submit_prerequisite(
                    fname,
                    args_obj,
                    llm_messages,
                )
                if duplicate_submit_msg is not None:
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
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

                # Chain prerequisite gate — donga-univ-poi-bug Epic #2766.
                # CC mirror: ``Tool.validateInput?(input, context)`` from
                # ``.references/claude-code-sourcemap/restored-src/src/Tool.ts:489``
                # — tool-scoped prerequisite hook that inspects the
                # surrounding ToolUseContext and may reject with a
                # message the LLM sees in the tool_result. KOSMOS port:
                # we run the check here, before issuing the ToolCallFrame
                # and before the dispatch task starts, so a rejected call
                # never burns an outbound HTTP request and the LLM gets
                # a deterministic chain-recovery instruction in the same
                # turn it tried to skip the prerequisite.
                #
                # Concretely: when fname == "lookup" + the chosen tool_id
                # is a coordinate/admcd-input adapter (kma_*, hira_*, nmc_*,
                # koroad_*) AND the citizen-supplied params already carry
                # the coordinates AND no prior turn in llm_messages
                # invoked resolve_location, that means the LLM guessed
                # the coordinates from prior knowledge instead of routing
                # through the canonical resolver. Three live captures
                # under specs/integration-verification/donga-univ-poi-bug/
                # showed this exact pattern producing wrong-region
                # hospital lists. Rejecting here forces the next turn
                # through resolve_location.
                chain_error_msg = _check_chain_prerequisite(
                    fname, args_obj, llm_messages, registry=_ensure_tool_registry()
                )
                if chain_error_msg is not None:
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                        ToolResultEnvelope,
                        ToolResultFrame,
                    )

                    # Emit a ToolCallFrame first so the TUI registers the
                    # call_id in seenToolUseIds (deps.ts L420). Without it
                    # the subsequent ToolResultFrame surfaces as a
                    # `tool_result_orphan` system error in the transcript.
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
                                "reason": "chain_prerequisite_missing",
                                "message": chain_error_msg,
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
                    # Inject a synthetic tool message into history so the
                    # next LLM turn sees the chain hint and follows it.
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
                                    "reason": "chain_prerequisite_missing",
                                    "message": chain_error_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected %s call_id=%s — chain prerequisite missing",
                        fname,
                        call_id[:12],
                    )
                    # Neurosymbolic constraint — the next LLM turn must
                    # call resolve_location before any other tool. Set the
                    # flag here so the next loop iteration's tool_choice
                    # forces the model down the chain. See the flag
                    # comment at the loop start for the full rationale.
                    force_resolve_location_next_turn = True
                    continue

                verify_choice_gate = _check_verify_tool_choice_prerequisite(
                    fname,
                    args_obj,
                    latest_user_utt,
                )
                if verify_choice_gate is not None:
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
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

                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
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
                        requirement["verify_tool_id"] if requirement is not None else "verify"
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
                # resolve_location turn has actually been dispatched. Any
                # subsequent turn returns to free tool_choice so the LLM
                # can route to the actual coord-input adapter (KMA/HIRA/
                # NMC) with the resolved coordinates.
                if fname == "resolve_location":
                    force_resolve_location_next_turn = False
                if fname == "verify":
                    force_verify_next_turn = None
                if fname == "lookup":
                    force_lookup_next_turn = None
                if fname == "submit":
                    force_submit_next_turn = None
                if fname == "subscribe":
                    force_subscribe_next_turn = None

            # If every tool call was rejected (whitelist), terminate.
            # Exception: when the chain gate fired (force flag set) we
            # MUST continue to the next iteration so the forced
            # tool_choice=resolve_location actually gets a chance to run.
            # Returning here would leave the citizen with the chain-error
            # tool_result frame as the only visible output.
            if not issued_calls:
                if (
                    force_resolve_location_next_turn
                    or force_verify_next_turn is not None
                    or force_lookup_next_turn is not None
                    or force_submit_next_turn is not None
                    or force_subscribe_next_turn is not None
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
                from kosmos.llm.tool_call_parser import (  # noqa: PLC0415
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
                if fname == "verify":
                    verify_result_seen = True

            if terminal_permission_code is not None:
                if terminal_permission_code == "permission_timeout":
                    denial_message = (
                        "권한 응답 시간이 초과되어 작업을 진행하지 않았습니다. "
                        "후속 제출 또는 구독 작업은 실행되지 않았습니다. "
                        "(code: permission_timeout)"
                    )
                else:
                    denial_message = (
                        "권한 요청이 거부되어 작업을 진행하지 않았습니다. "
                        "후속 제출 또는 구독 작업은 실행되지 않았습니다. "
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

            if verify_result_seen:
                submit_followup_gate = _check_submit_terminated_without_submit(
                    llm_messages,
                    latest_user_utt,
                    _session_auth_contexts.get(frame.session_id),
                )
                if submit_followup_gate is not None:
                    synthetic_submit_outcome = await _dispatch_synthetic_submit_followup(
                        submit_followup_gate,
                        message_id_for_turn=message_id,
                        reason=(
                            "verify completed for submit-class request and no submit "
                            "tool call followed in the same observed turn"
                        ),
                    )
                    if synthetic_submit_outcome == "return":
                        return
                    continue

            # Loop back: re-invoke client.stream with extended history.

        # Loop bound exhausted — emit terminal chunk anyway so the TUI
        # un-spins; the model will not be re-invoked beyond the bound.
        logger.warning(
            "agentic loop hit KOSMOS_AGENTIC_LOOP_MAX_TURNS=%d; terminating",
            _AGENTIC_LOOP_MAX_TURNS,
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

    async def _handle_tool_result(frame: IPCFrame) -> None:
        """Spec 1978 T028 — consume ``tool_result`` and resolve pending Future.

        Looks up ``_pending_calls[call_id]``; if found, sets the Future
        result so any awaiting ``_handle_chat_request`` continuation can
        resume the agentic loop. Frames with no matching pending call are
        logged at debug level (out-of-band tool results are tolerated for
        the demo path; deep validation deferred to subsequent commits).
        """
        from kosmos.ipc.frame_schema import ToolResultFrame  # noqa: PLC0415

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

    # KOSMOS_IPC_HANDLER env var selects the user_input handler:
    #   - "llm" (default): route UserInputFrame → LLMClient.stream() → FriendliAI
    #   - "echo": mirror UserInputFrame back as AssistantChunkFrame "[echo] {text}"
    # Echo mode is used by integration tests that spawn the real backend but
    # must not depend on FRIENDLI_API_KEY or network reachability.
    import os as _os  # noqa: PLC0415

    _handler_mode = (_os.environ.get("KOSMOS_IPC_HANDLER") or "llm").lower()

    async def _handle_user_input_echo(frame: IPCFrame) -> None:
        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
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
                    from kosmos.ipc.frame_schema import (
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
                    from kosmos.ipc.plugin_op_dispatcher import (  # noqa: PLC0415
                        handle_plugin_op_request,
                    )
                    from kosmos.plugins.consent_bridge import (  # noqa: PLC0415
                        IPCConsentBridge,
                    )
                    from kosmos.tools.executor import ToolExecutor  # noqa: PLC0415

                    consent_bridge = IPCConsentBridge(
                        write_frame=write_frame,
                        pending_perms=_pending_perms,
                        session_id=frame.session_id,
                    )
                    _registry = _ensure_tool_registry()
                    await handle_plugin_op_request(
                        frame,
                        registry=_registry,
                        executor=ToolExecutor(registry=_registry),  # type: ignore[arg-type]
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
            ``~/.kosmos/memdir/user/consent/<receipt_id>.json``, marks it
            revoked (atomic temp+rename write), appends a withdrawal entry to
            the canonical Spec 033 PIPA ledger via
            ``kosmos.permissions.ledger.append`` (HMAC-sealed, hash-chained,
            fcntl-locked), emits an OTEL span, and responds with a
            ``consent_revoke_response`` frame.

            Audit-4 P0-3 (2026-05-04): Replaced ad-hoc unsealed
            ``hashlib.sha256(json.dumps(entry))`` + parallel
            ``~/.kosmos/memdir/user/consent/ledger.jsonl`` path with
            ``kosmos.permissions.ledger.append(action="withdraw", ...)``.
            The ad-hoc path lacked HMAC, hash-chain prev_hash, key_id, and
            fcntl lock — entries were forgeable and could not be verified by
            ``kosmos permissions verify``. The unified path writes to the
            canonical ledger configured by ``settings.permission_ledger_path``
            (default ``~/.kosmos/consent_ledger.jsonl``).

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

            from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                ConsentRevokeResponseFrame as _CRRespFrame,
            )
            from kosmos.permissions.action_digest import (  # noqa: PLC0415
                compute_action_digest as _compute_action_digest,
            )
            from kosmos.permissions.action_digest import (  # noqa: PLC0415
                generate_nonce as _generate_nonce,
            )
            from kosmos.permissions.ledger import (  # noqa: PLC0415
                append as _ledger_append_withdraw,
            )
            from kosmos.settings import (  # noqa: PLC0415
                settings as _kosmos_settings_revoke,
            )

            request_id: str = getattr(frame, "request_id", "")
            receipt_id: str = getattr(frame, "receipt_id", "")
            scope: str = getattr(frame, "scope", "once")
            reason: str | None = getattr(frame, "reason", None)
            session_id: str = frame.session_id

            with _tracer.start_as_current_span("kosmos.consent.revoke") as revoke_span:
                revoke_span.set_attribute("kosmos.consent.receipt_id", receipt_id)
                revoke_span.set_attribute("kosmos.consent.scope", scope)
                revoke_span.set_attribute("kosmos.session.id", session_id)

                consent_dir = _Path.home() / ".kosmos" / "memdir" / "user" / "consent"
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
                        revoke_span.set_attribute("kosmos.consent.revoke_error", "not_found")
                        revoke_span.set_status(Status(StatusCode.ERROR, "not_found"))
                        await _emit_response(ok=False, error="not_found")
                        return
                    target_paths = [receipt_path]

                if not target_paths:
                    # Nothing to revoke — either empty session or single path already handled.
                    revoke_span.set_attribute("kosmos.consent.revoke_error", "already_revoked")
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
                                "kosmos.consent.revoke_error",
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
                        # Spec 033 PIPA ledger via kosmos.permissions.ledger.
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
                            ledger_path=_kosmos_settings_revoke.permission_ledger_path,
                            key_path=_kosmos_settings_revoke.permission_key_path,
                            key_registry_path=(
                                _kosmos_settings_revoke.permission_key_registry_path
                            ),
                        )
                        record_hash = withdraw_record.record_hash
                        last_record_hash = record_hash

                        revoke_span.set_attribute("kosmos.consent.record_hash", record_hash)
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

    # Spec 1978 T081 / ADR-0004 — root span ``kosmos.session`` covers the
    # entire stdio session lifetime. All inbound/outbound frame spans
    # (kosmos.ipc.frame), LLM chat spans, tool dispatch spans, and
    # permission spans are nested under this root via OTEL implicit
    # context propagation. Closes at session exit (graceful shutdown
    # path or session_event{event=exit}).
    with _tracer.start_as_current_span("kosmos.session") as _session_span:
        _session_span.set_attribute("kosmos.session.id", sid)
        _session_span.set_attribute("kosmos.ipc.handler_mode", _handler_mode)

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
            _session_span.set_attribute("kosmos.session.exit_reason", "stdin_closed")
        elif shutdown_task in done:
            _session_span.set_attribute("kosmos.session.exit_reason", "shutdown_signal")

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
