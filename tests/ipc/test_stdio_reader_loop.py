"""Regression tests for the stdio IPC reader dispatch loop."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest


def _ts() -> str:
    return datetime.now(UTC).isoformat()


@pytest.mark.asyncio
async def test_reader_loop_reads_permission_response_while_chat_request_runs() -> None:
    """A long chat_request must not block the same reader from control frames.

    The real permission gauntlet emits permission_response while the
    chat_request handler is awaiting a pending Future. If the reader awaits the
    whole chat_request inline, the permission_response line can never be read.
    """
    from ummaya.ipc.frame_schema import (
        ChatRequestFrame,
        IPCFrame,
        PermissionResponseFrame,
    )
    from ummaya.ipc.stdio import _reader_loop

    session_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    chat_frame = ChatRequestFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_ts(),
        kind="chat_request",
        messages=[{"role": "user", "content": "권한이 필요한 요청"}],
        tools=[],
    )
    response_frame = PermissionResponseFrame(
        session_id=session_id,
        correlation_id=chat_frame.correlation_id,
        role="tui",
        ts=_ts(),
        kind="permission_response",
        request_id=request_id,
        decision="allow_once",
    )

    reader = asyncio.StreamReader()
    reader.feed_data((chat_frame.model_dump_json() + "\n").encode("utf-8"))
    reader.feed_data((response_frame.model_dump_json() + "\n").encode("utf-8"))
    reader.feed_eof()

    permission_seen = asyncio.Event()
    seen: list[str] = []

    async def _on_frame(frame: IPCFrame) -> None:
        kind = frame.kind
        seen.append(kind)
        if kind == "chat_request":
            await asyncio.wait_for(permission_seen.wait(), timeout=0.5)
        elif kind == "permission_response":
            permission_seen.set()

    await asyncio.wait_for(_reader_loop(reader, _on_frame, session_id), timeout=1.0)

    assert "chat_request" in seen
    assert "permission_response" in seen
    assert permission_seen.is_set()


def test_build_verify_session_context_packs_params_shape() -> None:
    """Backend dispatch must mirror the LLM-visible check(tool_id, params) schema."""
    from ummaya.ipc.stdio import _build_verify_session_context

    ctx = _build_verify_session_context(
        {
            "tool_id": "mock_verify_module_modid",
            "session_context": {"purpose_ko": "기존 목적", "session_id": "explicit"},
            "params": {
                "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
                "purpose_ko": "종합소득세 신고",
            },
        },
        session_id="backend-session",
    )

    assert ctx["scope_list"] == ["find:hometax.simplified", "send:hometax.tax-return"]
    assert ctx["purpose_ko"] == "종합소득세 신고"
    assert ctx["session_id"] == "explicit"


def test_build_verify_session_context_normalizes_tool_id_scopes() -> None:
    """Model-emitted verb:tool_id scope shorthand should not block verify."""
    from ummaya.ipc.stdio import _build_verify_session_context

    ctx = _build_verify_session_context(
        {
            "tool_id": "mock_verify_mydata",
            "params": {
                "scope_list": [
                    "find:mohw_welfare_eligibility_search",
                    "send:mock_welfare_application_submit_v1",
                ],
            },
        },
        session_id="backend-session",
    )

    assert ctx["scope_list"] == ["send:mydata.welfare_application"]


def test_build_verify_session_context_canonicalizes_gov24_submit_tool_scope() -> None:
    """Gov24 submit tool-id shorthand must map to its published domain scope."""
    from ummaya.ipc.stdio import _build_verify_session_context

    ctx = _build_verify_session_context(
        {
            "tool_id": "mock_verify_module_simple_auth",
            "params": {
                "scope_list": [
                    "send:mock_submit_module_gov24_minwon",
                    "send:mock.submit_module_gov24_minwon",
                ],
            },
        },
        session_id="GOV24-MINWON-SESSION-001",
    )

    assert ctx["scope_list"] == ["send:gov24.minwon"]


def test_build_verify_session_context_flattens_nested_legacy_context() -> None:
    """Citizen-shape params may carry a legacy session_context object from the LLM."""
    from ummaya.ipc.stdio import _build_verify_session_context

    ctx = _build_verify_session_context(
        {
            "tool_id": "mock_verify_module_modid",
            "params": {
                "scope_list": ["send:gov24.minwon"],
                "purpose_ko": "주민등록등본 발급 민원 신청",
                "session_context": {"session_id": "GOV24-MINWON-SESSION-001"},
            },
        },
        session_id="backend-session",
    )

    assert ctx["session_id"] == "GOV24-MINWON-SESSION-001"
    assert ctx["scope_list"] == ["send:gov24.minwon"]
    assert "session_context" not in ctx


def test_inject_delegation_context_overwrites_partial_llm_copy() -> None:
    """Submit dispatch should use the typed backend-owned DelegationContext."""
    from ummaya.ipc.stdio import _inject_delegation_context

    def _model_dump(*, mode: str) -> dict[str, object]:
        assert mode == "json"
        return {
            "token": {
                "delegation_token": "del_backend_owned_token_value",
                "scope": "send:hometax.tax-return",
            },
            "purpose_ko": "신고",
            "purpose_en": "Filing",
        }

    typed_delegation = SimpleNamespace(model_dump=_model_dump)
    auth_context = SimpleNamespace(delegation_context=typed_delegation)

    params = _inject_delegation_context(
        {
            "tax_year": 2025,
            "citizen_did": "did:web:mobileid.go.kr:leaked",
            "delegation_context": {"token": {"delegation_token": "partial"}},
            "mode": "mock",
            "_mode": "mock",
            "purpose_ko": "루트에 잘못 복사된 목적",
        },
        auth_context,
    )

    assert params["tax_year"] == 2025
    assert "citizen_did" not in params
    assert "mode" not in params
    assert "_mode" not in params
    assert "purpose_ko" not in params
    assert params["delegation_context"] == {
        "token": {
            "delegation_token": "del_backend_owned_token_value",
            "scope": "send:hometax.tax-return",
        },
        "purpose_ko": "신고",
        "purpose_en": "Filing",
    }


def test_bind_submit_session_id_overwrites_llm_value_without_mutation() -> None:
    """Submit session binding must stay tied to the verified delegation session."""
    from ummaya.ipc.stdio import _bind_submit_session_id

    original = {
        "session_id": "GOV24-MINWON-SESSION-001",
        "service_code": "JUMINDEUNGCHOBON",
    }

    bound = _bind_submit_session_id(original, session_id="verified-session")

    assert bound == {
        "session_id": "verified-session",
        "service_code": "JUMINDEUNGCHOBON",
    }
    assert original["session_id"] == "GOV24-MINWON-SESSION-001"


def test_bind_submit_session_id_leaves_unscoped_payload_identity() -> None:
    """Payloads without a session field should pass through unchanged."""
    from ummaya.ipc.stdio import _bind_submit_session_id

    original = {"service_code": "JUMINDEUNGCHOBON"}

    bound = _bind_submit_session_id(original, session_id="verified-session")

    assert bound is original


@pytest.mark.asyncio
async def test_mydata_verify_issues_scope_bound_delegation_context(tmp_path) -> None:
    """Public MyData action submit must receive a real DelegationContext."""
    from ummaya.memdir.consent_ledger import FileLedgerReader
    from ummaya.primitives.delegation import (
        DelegationValidationOutcome,
        validate_delegation,
    )
    from ummaya.tools.mock.verify_mydata import invoke

    session_id = "MYDATA-ACTION-SESSION-001"
    ctx = invoke(
        {
            "scope_list": ["send:public_mydata.action"],
            "session_id": session_id,
            "purpose_ko": "공공 마이데이터 제공 동의",
            "purpose_en": "Public MyData consent action",
            "ledger_root": tmp_path,
        }
    )

    assert ctx.delegation_context is not None
    assert ctx.delegation_context.token.scope == "send:public_mydata.action"
    assert (
        await validate_delegation(
            ctx.delegation_context,
            required_scope="send:public_mydata.action",
            current_session_id=session_id,
            revoked_set=set(),
            ledger_reader=FileLedgerReader(tmp_path),
        )
        == DelegationValidationOutcome.OK
    )


def test_invalid_gated_primitive_tool_id_result_blocks_blank_tool() -> None:
    """Gated primitives must not open permission modals for blank tool ids."""
    from ummaya.ipc.stdio import _invalid_gated_primitive_tool_id_result

    result = _invalid_gated_primitive_tool_id_result("send", {"params": {}})

    assert result is not None
    assert "error" not in result
    assert result["tool_id"] == "invalid_tool_id"
    assert result["invalid_tool_id"] is True
    assert result["result"] == {
        "reason": "adapter_not_found",
        "tool_id": "invalid_tool_id",
        "message": (
            "send requires a non-empty registered adapter tool_id; "
            "call send(tool_id=<adapter>, params={...})."
        ),
    }


def test_invalid_gated_primitive_tool_id_result_accepts_valid_tool() -> None:
    """Valid adapter ids should continue into the normal permission gauntlet."""
    from ummaya.ipc.stdio import _invalid_gated_primitive_tool_id_result

    assert (
        _invalid_gated_primitive_tool_id_result(
            "send",
            {"tool_id": "mock_submit_module_gov24_minwon", "params": {}},
        )
        is None
    )


def test_contains_mock_marker_detects_nested_adapter_receipt() -> None:
    """Mock transparency can live below result.adapter_receipt."""
    from ummaya.ipc.stdio import _contains_mock_marker

    assert _contains_mock_marker(
        {
            "result": {
                "adapter_receipt": {
                    "_mode": "mock",
                    "receipt_id": "gov24-2026-05-06-MW-2BB4C5DD",
                }
            }
        }
    )
    assert _contains_mock_marker({"result": [{"mock": True}]})
    assert not _contains_mock_marker({"result": {"adapter_receipt": {"_mode": "live"}}})


def test_ensure_mock_disclosure_appends_once() -> None:
    """Citizen-facing final answers must carry a mandatory mock disclosure."""
    from ummaya.ipc.stdio import _ensure_mock_disclosure

    prose = "모바일 신분증 시연 인증이 완료되었습니다."

    disclosed = _ensure_mock_disclosure(prose)

    assert prose in disclosed
    assert "실제 행정 영향이 없는 시연(모의) 결과" in disclosed
    assert "접수번호" not in disclosed
    assert _ensure_mock_disclosure(disclosed) == disclosed


def test_ensure_mock_disclosure_mentions_receipt_only_when_present() -> None:
    """Mock receipt lookup warning is reserved for mock send receipt answers."""
    from ummaya.ipc.stdio import _ensure_mock_disclosure

    disclosed = _ensure_mock_disclosure("접수번호: gov24-2026-05-07-MW-4FA74579")

    assert "실제 행정 영향이 없는 시연(모의) 결과" in disclosed
    assert "실제 기관 포털에서 조회되지 않습니다" in disclosed
    assert _ensure_mock_disclosure(disclosed) == disclosed


def test_ensure_mock_disclosure_removes_internal_tool_id_prose() -> None:
    """Final answers should not expose internal mock adapter IDs to citizens."""
    from ummaya.ipc.stdio import _ensure_mock_disclosure

    disclosed = _ensure_mock_disclosure(
        "\n".join(
            [
                "방금 mock_verify_mobile_id 도구를 호출해 모바일 신분증 본인확인을 조회했습니다.",
                "본인확인이 성공적으로 완료되었습니다. (상태: verified, 인증 수준: AAL2)",
            ]
        )
    )

    assert "mock_verify_mobile_id" not in disclosed
    assert "도구를 호출" not in disclosed
    assert "본인확인이 성공적으로 완료되었습니다" in disclosed
    assert "접수번호" not in disclosed


def test_ensure_mock_disclosure_normalizes_check_only_prose() -> None:
    """Mock check-only turns should answer as verification, not lookup/application."""
    from ummaya.ipc.stdio import _ensure_mock_disclosure

    disclosed = _ensure_mock_disclosure(
        "\n".join(
            [
                "방금 모바일 신분증 본인확인 절차를 조회했습니다.",
                "조회 결과 본인확인이 완료된 것으로 확인되었습니다.",
                "이 정보는 모바일 신분증 본인확인 절차의 시연 결과입니다.",
            ]
        ),
        mock_primitives={"check"},
    )

    assert "모바일 신분증 본인확인이 완료되었습니다" in disclosed
    assert "조회" not in disclosed
    assert "이 정보는" not in disclosed
    assert "접수번호" not in disclosed
    assert "실제 행정 영향이 없는 시연(모의) 결과" in disclosed


def test_ensure_mock_disclosure_removes_real_portal_claims() -> None:
    """Mock final answers must not retain real portal lookup instructions."""
    from ummaya.ipc.stdio import _ensure_mock_disclosure

    disclosed = _ensure_mock_disclosure(
        "\n".join(
            [
                "정부24에서 주민등록등본 발급 민원 신청이 완료되었습니다.",
                "1. 정부24 포털에서 해당 접수번호로 조회하실 수 있습니다.",
                "2. 정부24 홈페이지 또는 모바일 앱에서 바로 발급받을 수 있습니다.",
                "3. 세션 유효기간은 인증 토큰 발급일로부터 24시간입니다.",
            ]
        )
    )

    assert "정부24 포털에서 해당 접수번호로 조회" not in disclosed
    assert "정부24 홈페이지 또는 모바일 앱" not in disclosed
    assert "인증 토큰 발급일로부터 24시간" not in disclosed
    assert "실제 행정 영향이 없는 시연(모의) 결과" in disclosed


def test_ensure_mock_disclosure_removes_unsupported_gov24_next_steps() -> None:
    """Mock final answers must not invent real-world processing guidance."""
    from ummaya.ipc.stdio import _ensure_mock_disclosure

    disclosed = _ensure_mock_disclosure(
        "\n".join(
            [
                "정부24에서 주민등록등본 발급 민원이 성공적으로 접수되었습니다.",
                "다음 단계 안내:",
                "2. 발급 기한: 일반적으로 접수 후 즉시 발급 가능하며, "
                "특별한 경우 1~2일 내에 처리됩니다.",
                "참고사항:",
                "- 발급된 주민등록등본은 공공기관 제출, 금융거래, 취업 지원 등 "
                "다양한 용도로 사용 가능합니다.",
                "- 발급 시 본인인증이 필요하니 미리 준비해주세요.",
                "- 추가 문의사항이 있으시면 민원 접수번호를 참고하시기 바랍니다.",
                "민원 처리 과정에서 문제 발생 시 정부24 고객센터(110)에 문의하실 수 있습니다.",
                "다음 단계",
                "본인인증: 간편인증 또는 공인인증서로 본인확인을 진행하세요.",
                "발급 신청: 민원신청 내역에서 해당 접수번호를 찾아 온라인 발급을 요청하세요.",
                "문서 다운로드: 발급된 주민등록등본을 온라인으로 다운로드할 수 있습니다.",
                "발급 소요시간은 일반적으로 10-30분 정도 소요됩니다.",
                "온라인 발급을 위해 인터넷 연결과 스마트폰 또는 컴퓨터가 필요합니다.",
                "처리 내역",
                "안내사항:",
                "인증 절차 완료: 간편인증 모듈을 통해 위임 토큰 발급",
                "민원 신청 완료: 정부24 시스템에 정식 접수",
                "신청 ID: urn:ummaya:send:abc",
                "접수번호를 보관하시면 조회 시 필요합니다.",
                "접수번호를 확인하시고 필요시 보관해주세요.",
                "발급 완료 시 등록된 연락처로 알림이 발송됩니다.",
                "3. 문의: 발급 관련 추가 문의가 있으시면 "
                "정부24 콜센터(1588-2121)로 연락주시기 바랍니다.",
                "접수번호를 확인하셨으니, 정부24 홈페이지나 앱에서 다음과 같이 진행하시면 됩니다:",
                "온라인 발급 안내",
                "주민등록등본은 온라인 발급이 완료되었습니다. 다음 방법으로 확인하실 수 있습니다:",
                '1. 로그인 후 "민원신청/발급" 메뉴 선택',
                "2. '민원신청/발급' 메뉴 → '발급 신청 내역 조회'",
                "2. 접수번호 gov24-2026-05-07-MW-12345678로 조회",
                "3. 온라인 발급 옵션 선택하여 다운로드",
                "- 추가 수정이나 변경이 필요한 경우, 접수 후 24시간 이내로 "
                "정부24 민원 접수 취소 신청이 가능합니다",
            ]
        )
    )

    assert "발급 기한" not in disclosed
    assert "1~2일" not in disclosed
    assert "발급된 주민등록등본" not in disclosed
    assert "문서 다운로드" not in disclosed
    assert "발급 소요시간" not in disclosed
    assert "10-30분" not in disclosed
    assert "발급 시 본인인증" not in disclosed
    assert "본인인증" not in disclosed
    assert "해당 접수번호" not in disclosed
    assert "인터넷 연결" not in disclosed
    assert "처리 내역" not in disclosed
    assert "안내사항" not in disclosed
    assert "정식 접수" not in disclosed
    assert "신청 ID" not in disclosed
    assert "필요시 보관" not in disclosed
    assert "등록된 연락처" not in disclosed
    assert "정부24 고객센터" not in disclosed
    assert "정부24 콜센터" not in disclosed
    assert "1588-2121" not in disclosed
    assert "정부24 홈페이지나 앱" not in disclosed
    assert "온라인 발급 안내" not in disclosed
    assert "온라인 발급이 완료" not in disclosed
    assert "민원신청/발급" not in disclosed
    assert "발급 신청 내역 조회" not in disclosed
    assert "접수번호 gov24" not in disclosed
    assert "다운로드" not in disclosed
    assert "접수 후 24시간" not in disclosed
    assert "취소 신청" not in disclosed
    assert "실제 행정 영향" in disclosed
    assert "실제 기관 포털에서 조회되지 않습니다" in disclosed


def test_ensure_mock_disclosure_normalizes_gov24_mock_submit_summary() -> None:
    """Gov24 mock submit finals should be receipt-only, not portal guidance."""
    from ummaya.ipc.stdio import _ensure_mock_disclosure

    disclosed = _ensure_mock_disclosure(
        "\n".join(
            [
                "정부24 주민등록등본 발급 민원 신청이 완료되었습니다!",
                "접수번호: gov24-2026-05-07-MW-4FA74579",
                "거래 ID: "
                "urn:ummaya:send:807823304ad5dfeb0b4d8b938bf8f493c76ea9f30d2b7abecee3401179faaf84",
                "신청자: 홍길동",
                "수령 방법: 온라인 발급",
                "세션 ID: GOV24-MINWON-SESSION-001",
                "발급 방법 안내",
                "온라인 발급 절차",
                "정부24 웹사이트(http://www.gov.kr) 또는 정부24 모바일 앱 접속",
                "신청 내역에서 접수번호 gov24-2026-05-07-MW-4FA74579 확인",
                "온라인으로 즉시 발급 및 출력 가능",
                "발급 유효기간: 접수일로부터 30일 이내",
                "필요시 언제든지 동일 절차로 재발급 가능",
                "온라인 발급 시 공인인증서 또는 간편인증 필요",
            ]
        )
    )

    assert "시연 환경에서 접수되었습니다" in disclosed
    assert "gov24-2026-05-07-MW-4FA74579 (시연용)" in disclosed
    assert (
        "urn:ummaya:send:807823304ad5dfeb0b4d8b938bf8f493c76ea9f30d2b7abecee3401179faaf84"
        in disclosed
    )
    assert "홍길동" in disclosed
    assert "GOV24-MINWON-SESSION-001" in disclosed
    assert "정부24 웹사이트" not in disclosed
    assert "모바일 앱" not in disclosed
    assert "즉시 발급" not in disclosed
    assert "즉시 발급 및 출력" not in disclosed
    assert "발급 유효기간" not in disclosed
    assert "재발급" not in disclosed
    assert "공인인증서" not in disclosed
    assert "실제 행정 영향" in disclosed


def test_ensure_mock_disclosure_normalizes_hometax_mock_submit_summary() -> None:
    """Hometax mock submit finals must not claim real portal lookup is possible."""
    from ummaya.ipc.stdio import _ensure_mock_disclosure

    disclosed = _ensure_mock_disclosure(
        "\n".join(
            [
                "작년 종합소득세 신고 절차가 완료되었습니다.",
                "접수번호: hometax-2026-05-07-RX-76814FEF",
                "거래 ID: "
                "urn:ummaya:send:72d28a717acb576351be4106aa78b4a8cd552bd889b6e79b5875242f76b7507b",
                "총 신고 소득: 42,000,000원",
                "홈택스 로그인 후 신고 내역에서 확인 가능합니다.",
                "기한 내 추가 수정이 필요하면 홈택스에서 직접 진행하실 수 있습니다.",
            ]
        )
    )

    assert "홈택스 종합소득세 신고가 시연 환경에서 접수되었습니다" in disclosed
    assert "hometax-2026-05-07-RX-76814FEF (시연용)" in disclosed
    assert (
        "urn:ummaya:send:72d28a717acb576351be4106aa78b4a8cd552bd889b6e79b5875242f76b7507b"
        in disclosed
    )
    assert "42,000,000원" in disclosed
    assert "홈택스 로그인" not in disclosed
    assert "홈택스에서 직접" not in disclosed
    assert "실제 행정 영향" in disclosed
    assert "실제 기관 포털에서 조회되지 않습니다" in disclosed
