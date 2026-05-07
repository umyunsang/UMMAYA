# SPDX-License-Identifier: Apache-2.0
"""Offline IPC backend for the README VHS user-scenario demo.

The VHS recording must exercise the real Ink TUI, but it must not call
FriendliAI or live public-service channels. This backend accepts the TUI's
``chat_request`` JSONL frames and returns deterministic tool-call and assistant
frames for the README scenario prompts.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from typing import Any


@dataclass(frozen=True)
class Scenario:
    code: str
    match: str
    title: str
    tool_chain: tuple[tuple[str, str], ...]
    answer: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        code="TAX",
        match="종합소득세",
        title="Tax execution",
        tool_chain=(
            ("verify", "mock_verify_module_modid"),
            ("lookup", "mock_lookup_module_hometax_simplified"),
            ("submit", "mock_submit_module_hometax_taxreturn"),
        ),
        answer="Hometax 자료 조회와 신고 전 최종 검토 순서를 구성했습니다. 제출은 시민 확인 뒤 진행됩니다.",
    ),
    Scenario(
        code="MOVE",
        match="전입신고",
        title="Residence transfer",
        tool_chain=(
            ("verify", "mock_verify_module_simple_auth"),
            ("resolve_location", "resolve_location"),
            ("submit", "mock_submit_module_gov24_minwon"),
        ),
        answer="전입신고를 선행하고 자동차, 건강보험, 학교 주소 변경을 순서와 병렬 가능 항목으로 나눴습니다.",
    ),
    Scenario(
        code="PAY",
        match="재산세",
        title="Payment consolidation",
        tool_chain=(
            ("verify", "mock_verify_module_ganpyeon"),
            ("lookup", "mock_traffic_fine_lookup_v1"),
            ("submit", "mock_traffic_fine_pay_v1"),
        ),
        answer="재산세, 자동차세, 과태료를 항목별로 분리하고 납부 가능한 항목만 명시적 확인 뒤 처리합니다.",
    ),
    Scenario(
        code="BIRTH",
        match="아기가 태어났어",
        title="Birth and welfare bundle",
        tool_chain=(
            ("verify", "mock_verify_mydata"),
            ("lookup", "mohw_welfare_eligibility_search"),
            ("submit", "mock_welfare_application_submit_v1"),
        ),
        answer="출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 등록을 중복 신청 없이 묶었습니다.",
    ),
    Scenario(
        code="HOME",
        match="전세 계약",
        title="Housing transaction",
        tool_chain=(
            ("verify", "mock_verify_module_simple_auth"),
            ("lookup", "mock_lookup_module_gov24_certificate"),
            ("submit", "mock_submit_module_gov24_minwon"),
            ("lookup", "mock_deadline_watch"),
        ),
        answer="확정일자, 임대차 신고, 보증 관련 위험 플래그와 공식 handoff 지점을 정리했습니다.",
    ),
    Scenario(
        code="BIZ",
        match="카페 창업",
        title="Business start",
        tool_chain=(
            ("verify", "mock_verify_module_modid"),
            ("lookup", "mock_lookup_module_hometax_simplified"),
            ("submit", "mock_submit_module_hometax_taxreturn"),
            ("lookup", "mock_deadline_watch"),
        ),
        answer="사업자등록, 영업신고, 위생교육, 카드가맹, 세금 준비를 개업 전 의존 순서로 배열했습니다.",
    ),
    Scenario(
        code="ER",
        match="응급실",
        title="Emergency care",
        tool_chain=(
            ("resolve_location", "resolve_location"),
            ("lookup", "nmc_emergency_search"),
            ("lookup", "hira_hospital_search"),
        ),
        answer="현재 위치 기준 응급실과 야간진료 후보를 우선순위로 제시하고 119 우선 안내를 유지합니다.",
    ),
    Scenario(
        code="ROUTE",
        match="부산에서 서울",
        title="Route safety",
        tool_chain=(
            ("resolve_location", "resolve_location"),
            ("lookup", "kma_forecast_lookup"),
            ("lookup", "koroad_accident_hazard_search"),
            ("lookup", "mock_safety_alert_watch"),
        ),
        answer="날씨, 도로 위험, 대중교통 지연을 함께 보고 우회 경로와 출발 전 알림 계획을 만들었습니다.",
    ),
    Scenario(
        code="SAFE",
        match="침수",
        title="Disaster response",
        tool_chain=(
            ("verify", "mock_verify_mobile_id"),
            ("lookup", "mock_cbs_disaster_feed"),
            ("submit", "mock_submit_module_gov24_minwon"),
            ("lookup", "mock_safety_alert_watch"),
        ),
        answer="피해 신고, 재난지원금, 임시주거, 전기/가스 안전 점검을 긴급도 순서로 묶었습니다.",
    ),
    Scenario(
        code="DATA",
        match="어디에 쓰고",
        title="Personal-data rights",
        tool_chain=(
            ("verify", "mock_verify_mydata"),
            ("lookup", "mock_public_mydata_inventory"),
            ("submit", "mock_submit_module_gov24_minwon"),
        ),
        answer="기관별 개인정보 이용 현황을 조회하고 주소와 연락처 정정 요청을 동의 추적으로 분리했습니다.",
    ),
)

_FRAME_SEQ = count()


def _ts() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _uuid() -> str:
    uuid7 = getattr(uuid, "uuid7", None)
    return str(uuid7()) if callable(uuid7) else str(uuid.uuid4())


def _write(frame: dict[str, Any], delay: float = 0.12) -> None:
    sys.stdout.write(json.dumps(frame, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    time.sleep(delay)


def _base(request: dict[str, Any], role: str = "backend") -> dict[str, Any]:
    return {
        "version": "1.0",
        "session_id": request.get("session_id", "readme-demo"),
        "correlation_id": request.get("correlation_id", _uuid()),
        "ts": _ts(),
        "role": role,
        "frame_seq": next(_FRAME_SEQ),
    }


def _last_user_text(request: dict[str, Any]) -> str:
    messages = request.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else ""
    return ""


def _select(text: str) -> Scenario:
    for scenario in SCENARIOS:
        if scenario.match in text:
            return scenario
    return SCENARIOS[0]


def _assistant(request: dict[str, Any], message_id: str, delta: str, done: bool) -> dict[str, Any]:
    return {
        **_base(request),
        "kind": "assistant_chunk",
        "message_id": message_id,
        "delta": delta,
        "thinking": "",
        "done": done,
    }


def _tool_call(request: dict[str, Any], call_id: str, name: str, tool_id: str) -> dict[str, Any]:
    return {
        **_base(request),
        "kind": "tool_call",
        "call_id": call_id,
        "name": name,
        "arguments": {"tool_id": tool_id, "demo": True},
    }


def _tool_result(request: dict[str, Any], call_id: str, name: str, tool_id: str) -> dict[str, Any]:
    return {
        **_base(request),
        "kind": "tool_result",
        "call_id": call_id,
        "envelope": {
            "kind": name,
            "tool_id": tool_id,
            "status": "demo_ok",
            "mock": True,
        },
    }


def _handle_chat_request(request: dict[str, Any]) -> None:
    scenario = _select(_last_user_text(request))
    message_id = _uuid()
    _write(
        _assistant(
            request,
            message_id,
            f"Scenario {scenario.code}: {scenario.title}\n",
            False,
        ),
        delay=0.08,
    )
    _write(
        _assistant(
            request,
            message_id,
            "공식 채널, 권한, 제출 가능 여부를 확인합니다.\n",
            False,
        ),
        delay=0.08,
    )
    for primitive, tool_id in scenario.tool_chain:
        call_id = _uuid()
        _write(_tool_call(request, call_id, primitive, tool_id), delay=0.08)
        _write(_tool_result(request, call_id, primitive, tool_id), delay=0.05)
    final_text = (
        f"{scenario.answer}\n"
        "모의 결과이며 실제 행정 제출은 시민의 최종 확인과 공식 채널 검증 뒤 진행됩니다.\n"
        f"Scenario {scenario.code} complete"
    )
    _write(_assistant(request, message_id, final_text, True), delay=0.05)


def main() -> int:
    for raw in sys.stdin:
        if not raw.strip():
            continue
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(frame, dict) and frame.get("kind") == "chat_request":
            _handle_chat_request(frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
