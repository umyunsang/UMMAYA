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
            ),
        )

    # Success path — produce synthetic 접수번호
    suffix = secrets.token_hex(4).upper()
    receipt_id = f"gov24-{datetime.now(_SEOUL_TZ).strftime('%Y-%m-%d')}-MW-{suffix}"

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
                "mock": True,
            },
            reference_implementation=_REFERENCE_IMPL,
            actual_endpoint_when_live=_ACTUAL_ENDPOINT,
            security_wrapping_pattern=_SECURITY_WRAPPING,
            policy_authority=_POLICY_AUTHORITY,
            international_reference=_INTERNATIONAL_REF,
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
        "ko": ["정부24", "민원", "주민등록등본", "가족관계증명서", "민원신청"],
        "en": ["government24", "civil petition", "resident certificate", "document request"],
    },
    auth_type="oauth",
    nonce=_ADAPTER_NONCE,
)

# Register in the submit dispatcher's in-process table
register_submit_adapter(REGISTRATION, invoke)

__all__ = ["REGISTRATION", "Gov24MinwonParams", "invoke"]
