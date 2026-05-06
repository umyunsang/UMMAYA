# SPDX-License-Identifier: Apache-2.0
"""T024 — Mock submit adapter: Government24 civil petition filing (정부24 민원신청).

Epic ε #2296 — US1 Phase 4B new submit mocks.

Adapter identity:
  tool_id: ``mock_submit_module_gov24_minwon``
  ministry: gov24 (행정안전부 정부24)
  source_mode: OOS (shape-mirrored from 정부24 LLM-callable channel mandate)
  primitive: submit

Delegation contract (FR-009/010/011):
  Requires scope ``"submit:gov24.minwon"`` in the caller's DelegationToken.
  Validates expiry, scope, session binding, and revocation before executing.
  Appends a ``delegation_used`` ledger event on EVERY invocation (success or failure).

International reference: Singapore APEX
Policy authority: https://www.gov.kr/portal/service/serviceList
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any, Final, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from kosmos.memdir.consent_ledger import DelegationUsedEvent, append_delegation_used
from kosmos.primitives.delegation import (
    DelegationContext,
    DelegationValidationOutcome,
    validate_delegation,
)
from kosmos.primitives.submit import (
    SubmitOutput,
    SubmitStatus,
    derive_transaction_id,
    register_submit_adapter,
)
from kosmos.tools.models import AdapterRealDomainPolicy
from kosmos.tools.registry import AdapterPrimitive, AdapterRegistration, AdapterSourceMode
from kosmos.tools.transparency import stamp_mock_response

logger = logging.getLogger(__name__)

# KOSMOS canonical citizen-facing timezone (Asia/Seoul). Internal
# OTEL/audit/IPC paths keep UTC; only envelope-visible timestamps switch.
_SEOUL_TZ = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------------------
# Transparency constants (FR-005 / FR-025)
# ---------------------------------------------------------------------------

_REFERENCE_IMPL: Final = "ax-infrastructure-callable-channel"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/submit/gov24/minwon"
_SECURITY_WRAPPING: Final = "OAuth2.1 + mTLS + scope-bound bearer + 행정안전부 OAuth gateway"
_POLICY_AUTHORITY: Final = "https://www.gov.kr/portal/service/serviceList"
_INTERNATIONAL_REF: Final = "Singapore APEX"
_MOCK_FIDELITY_GRADE: Final = "B-official-api-onboarding-private-submit-spec-inferred"
_MOCK_EVIDENCE: Final[dict[str, Any]] = {
    "credential_status": "student_no_live_authority",
    "basis_urls": [
        "https://www.dpaper.kr/ewp/smm/intrcn.do",
        "https://www.dpaper.kr/ewp/busiAccountUrl.do",
        "https://www.apex.gov.sg/",
    ],
    "supports": [
        "official electronic certificate API application and approval path",
        "official electronic document wallet service terms and wallet address concept",
        "central government API hub pattern for secure API onboarding and monitoring",
    ],
    "inference_boundary": (
        "The 민원 submit operation schema is gated behind approved institution access; "
        "KOSMOS mirrors the official onboarding and document lifecycle, not live forms."
    ),
    "live_swap_requirements": [
        "MOIS or Government24 API approval",
        "server certificate and portal account",
        "development API key and successful test-result review",
        "operation API key and service-specific 민원 schema",
    ],
}

# Required delegation scope for this adapter
_REQUIRED_SCOPE: Final = "submit:gov24.minwon"

# ---------------------------------------------------------------------------
# Typed input model
# ---------------------------------------------------------------------------


class Gov24MinwonParams(BaseModel):
    """Typed params for the Government24 civil petition filing adapter.

    Domain vocabulary lives HERE, not on the main SubmitInput envelope (SC-002).
    Real-world counterpart: 정부24 민원신청 API (행정안전부).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    minwon_type: Literal[
        "주민등록등본",
        "가족관계증명서",
        "건강보험료납부확인서",
        "인감증명서",
        "사업자등록증명",
        "전입신고",
        "주소변경",
        "임대차신고",
        "확정일자",
        "취득세감면",
        "소유권이전등기",
        "전학신청",
        "돌봄신청",
        "출생신고",
        "아동수당",
        "첫만남이용권",
        "영업신고",
        "모바일신분증발급",
        "인증수단연결",
        "워크넷등록",
        "고용센터예약",
        "체류기간연장",
        "방문예약",
        "사망신고",
        "국민연금유족급여",
        "4대보험신고",
        "근로계약",
        "피해신고",
        "재난피해신고",
        "재난지원금",
    ] = Field(
        description="Type of civil petition document being requested.",
    )
    applicant_name: str = Field(
        min_length=1,
        max_length=64,
        description="Name of the applicant (Korean).",
    )
    delivery_method: Literal["online", "print", "postal"] = Field(
        description="Delivery channel for the requested document.",
    )
    session_id: str = Field(
        min_length=1,
        max_length=128,
        description="Consuming session ID (used for delegation session-binding check).",
    )
    delegation_context: DelegationContext = Field(
        description="DelegationContext from the prior verify step.",
    )


# ---------------------------------------------------------------------------
# Adapter nonce (deterministic transaction_id)
# ---------------------------------------------------------------------------

_ADAPTER_NONCE = "mock_submit_module_gov24_minwon_nonce_v1"


# ---------------------------------------------------------------------------
# Mock invoke coroutine
# ---------------------------------------------------------------------------


async def invoke(params: dict[str, Any]) -> SubmitOutput:
    """Mock invoke — validates delegation then returns a synthetic 접수번호.

    Validation order (FR-009/010/011):
      1. Extract DelegationContext from params.
      2. validate_delegation() — checks expiry, scope, session, revocation.
      3. On failure: append delegation_used with rejection outcome; return SubmitOutput(rejected).
      4. On success: produce synthetic 접수번호; append
         delegation_used(success); return SubmitOutput(succeeded).

    Args:
        params: Raw params dict from the main submit() envelope.

    Returns:
        SubmitOutput with transparency fields in adapter_receipt.
    """
    typed = Gov24MinwonParams.model_validate(params)
    delegation_ctx = typed.delegation_context
    token = delegation_ctx.token
    token_value = token.delegation_token

    from kosmos.memdir.consent_ledger import FileLedgerReader  # noqa: PLC0415
    from kosmos.primitives.delegation import revoked_for_session  # noqa: PLC0415

    ledger_reader = FileLedgerReader()

    outcome = await validate_delegation(
        delegation_ctx,
        required_scope=_REQUIRED_SCOPE,
        current_session_id=typed.session_id,
        revoked_set=revoked_for_session(typed.session_id),
        ledger_reader=ledger_reader,
    )

    if outcome != DelegationValidationOutcome.OK:
        logger.info(
            "mock_submit_module_gov24_minwon: delegation rejected (%s) for token=%s",
            outcome.value,
            token_value[:12],
        )
        append_delegation_used(
            DelegationUsedEvent(
                kind="delegation_used",
                ts=datetime.now(UTC),
                session_id=typed.session_id,
                delegation_token=token_value,
                consumer_tool_id="mock_submit_module_gov24_minwon",
                receipt_id=None,
                outcome=outcome.value,  # type: ignore[arg-type]
            )
        )
        return SubmitOutput(
            transaction_id=derive_transaction_id(
                "mock_submit_module_gov24_minwon",
                {k: v for k, v in params.items() if k != "delegation_context"},
                adapter_nonce=_ADAPTER_NONCE,
            ),
            status=SubmitStatus.rejected,
            adapter_receipt=stamp_mock_response(
                {"error": outcome.value, "tool_id": "mock_submit_module_gov24_minwon"},
                reference_implementation=_REFERENCE_IMPL,
                actual_endpoint_when_live=_ACTUAL_ENDPOINT,
                security_wrapping_pattern=_SECURITY_WRAPPING,
                policy_authority=_POLICY_AUTHORITY,
                international_reference=_INTERNATIONAL_REF,
                mock_fidelity_grade=_MOCK_FIDELITY_GRADE,
                mock_evidence=_MOCK_EVIDENCE,
            ),
        )

    # Success path — produce synthetic 접수번호
    suffix = secrets.token_hex(4).upper()
    now = datetime.now(_SEOUL_TZ)
    receipt_id = f"gov24-{now.strftime('%Y-%m-%d')}-MW-{suffix}"
    received_at = now.isoformat()

    logger.debug(
        "mock_submit_module_gov24_minwon: success, receipt_id=%s minwon_type=%s",
        receipt_id,
        typed.minwon_type,
    )

    append_delegation_used(
        DelegationUsedEvent(
            kind="delegation_used",
            ts=datetime.now(UTC),
            session_id=typed.session_id,
            delegation_token=token_value,
            consumer_tool_id="mock_submit_module_gov24_minwon",
            receipt_id=receipt_id,
            outcome="success",
        )
    )

    return SubmitOutput(
        transaction_id=derive_transaction_id(
            "mock_submit_module_gov24_minwon",
            {k: v for k, v in params.items() if k != "delegation_context"},
            adapter_nonce=_ADAPTER_NONCE,
        ),
        status=SubmitStatus.succeeded,
        adapter_receipt=stamp_mock_response(
            {
                "receipt_id": receipt_id,
                "minwon_type": typed.minwon_type,
                "delivery_method": typed.delivery_method,
                "status": "접수완료",
                "application_flow": [
                    "verify_delegation_scope",
                    "validate_citizen_identity_and_request_payload",
                    "route_to_issuing_authority",
                    "issue_or_stage_electronic_document",
                    "deliver_to_requested_channel",
                    "record_receipt",
                ],
                "api_onboarding_assumptions": {
                    "server_certificate_required": True,
                    "portal_account_required": True,
                    "development_api_key_required": True,
                    "operation_api_key_required": True,
                },
                "wallet_delivery": {
                    "wallet_address": "mock-wallet-address-not-routable",
                    "document_ref": f"mock-gov24-document-{suffix.lower()}",
                    "integrity": "fixture_only_not_cryptographic",
                },
                "status_history": [
                    {"status": "received", "at": received_at},
                    {"status": "routed_to_issuer", "at": received_at},
                    {"status": "accepted", "at": received_at},
                ],
                "mock": True,
            },
            reference_implementation=_REFERENCE_IMPL,
            actual_endpoint_when_live=_ACTUAL_ENDPOINT,
            security_wrapping_pattern=_SECURITY_WRAPPING,
            policy_authority=_POLICY_AUTHORITY,
            international_reference=_INTERNATIONAL_REF,
            mock_fidelity_grade=_MOCK_FIDELITY_GRADE,
            mock_evidence=_MOCK_EVIDENCE,
        ),
    )


# ---------------------------------------------------------------------------
# AdapterRegistration + self-registration
# ---------------------------------------------------------------------------

REGISTRATION = AdapterRegistration(
    tool_id="mock_submit_module_gov24_minwon",
    primitive=AdapterPrimitive.submit,
    module_path=__name__,
    input_model_ref=f"{__name__}.Gov24MinwonParams",
    source_mode=AdapterSourceMode.OOS,
    published_tier_minimum="ganpyeon_injeung_kakao_aal2",  # minimum identity tier for delegation token  # noqa: E501
    nist_aal_hint="AAL2",
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    search_hint={
        "ko": [
            "정부24",
            "민원",
            "민원신청",
            "주민등록등본",
            "가족관계증명서",
            "전입신고",
            "이사민원",
            "주소변경",
            "자동차주소",
            "건강보험주소",
            "학교배정",
            "전학신청",
            "학교전학",
            "돌봄신청",
            "초등돌봄",
            "방과후돌봄",
            "아이돌봄",
            "출생신고",
            "아동수당",
            "첫만남이용권",
            "영업신고",
            "모바일신분증발급",
            "인증수단연결",
            "워크넷등록",
            "고용센터예약",
            "체류기간연장",
            "사망신고",
            "장례지원",
            "국민연금유족급여",
            "4대보험신고",
            "근로계약",
            "직원채용",
            "재난피해신고",
            "피해신고",
            "침수피해",
            "재난지원금",
            "임시주거",
            "전기가스안전점검",
            "외국인등록",
            "전자민원",
            "방문예약",
            "출입국예약",
            "외국인등록예약",
            "전자민원예약",
            "임대차신고",
            "확정일자",
            "전세보증",
            "생애최초",
            "주택구입",
            "취득세감면",
            "소유권이전등기",
        ],
        "en": [
            "government24",
            "civil petition",
            "resident certificate",
            "document request",
            "move-in report",
            "address change",
            "lease report",
            "fixed date confirmation",
            "jeonse guarantee",
            "first home purchase",
            "acquisition tax reduction",
            "property registration",
            "school transfer",
            "after-school care",
            "child care application",
            "immigration reservation",
            "alien registration reservation",
        ],
    },
    auth_type="oauth",
    nonce=_ADAPTER_NONCE,
    # Audit-4 P0-9 — agency-published policy citation (Constitution § II cite-only).
    # Required by AdapterManifestEntry I4 (mock entries must declare a policy URL
    # so the citizen sees the citation in the permission UI). The values mirror
    # the per-call transparency constants emitted via stamp_mock_response().
    policy=AdapterRealDomainPolicy(
        real_classification_url=_POLICY_AUTHORITY,
        real_classification_text=(
            "정부24 민원신청 — 행정안전부 공공서비스 포털 (Spec 1636 Live-channel mandate)."
        ),
        citizen_facing_gate="submit",
        last_verified=datetime(2026, 5, 4, tzinfo=UTC),
    ),
)

# Register in the submit dispatcher's in-process table
register_submit_adapter(REGISTRATION, invoke)

__all__ = ["REGISTRATION", "Gov24MinwonParams", "invoke"]
