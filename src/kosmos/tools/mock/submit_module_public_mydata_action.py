# SPDX-License-Identifier: Apache-2.0
"""T025 — Mock submit adapter: public MyData action extension (마이데이터 액션 확장).

Epic ε #2296 — US1 Phase 4B new submit mocks.

Adapter identity:
  tool_id: ``mock_submit_module_public_mydata_action``
  ministry: public_mydata (금융보안원 마이데이터 표준 API)
  source_mode: OOS (shape-mirrored from 마이데이터 action-extension mandate)
  primitive: submit

Delegation contract (FR-009/010/011):
  Requires scope ``"submit:public_mydata.action"`` in the caller's DelegationToken.
  Validates expiry, scope, session binding, and revocation before executing.
  Appends a ``delegation_used`` ledger event on EVERY invocation (success or failure).

International reference: Estonia X-Road
Policy authority: https://www.fsb.or.kr/kor.do (금융보안원 마이데이터 표준)
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

_REFERENCE_IMPL: Final = "public-mydata-action-extension"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/submit/public-mydata/action"
_SECURITY_WRAPPING: Final = "마이데이터 표준동의서 OAuth2 + finAuth + mTLS"
_POLICY_AUTHORITY: Final = "https://www.fsb.or.kr/kor.do"
_INTERNATIONAL_REF: Final = "Estonia X-Road"

# Required delegation scope for this adapter
_REQUIRED_SCOPE: Final = "submit:public_mydata.action"

# ---------------------------------------------------------------------------
# Typed input model
# ---------------------------------------------------------------------------


class PublicMydataActionParams(BaseModel):
    """Typed params for the public MyData action extension adapter.

    Domain vocabulary lives HERE, not on the main SubmitInput envelope (SC-002).
    Real-world counterpart: 마이데이터 액션 확장 API (금융보안원 v240930).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_type: Literal[
        "transfer_consent",
        "revoke_consent",
        "update_scope",
        "request_data_portability",
    ] = Field(
        description="MyData action type being invoked.",
    )
    target_institution_code: str = Field(
        min_length=1,
        max_length=20,
        description="Institution code of the data provider (e.g. KSB001, FSC002).",
    )
    applicant_di: str = Field(
        min_length=1,
        max_length=128,
        description="MyData-scoped applicant DI (De-Identification) code.",
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

_ADAPTER_NONCE = "mock_submit_module_public_mydata_action_nonce_v1"


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
    typed = PublicMydataActionParams.model_validate(params)
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
            "mock_submit_module_public_mydata_action: delegation rejected (%s) for token=%s",
            outcome.value,
            token_value[:12],
        )
        append_delegation_used(
            DelegationUsedEvent(
                kind="delegation_used",
                ts=datetime.now(UTC),
                session_id=typed.session_id,
                delegation_token=token_value,
                consumer_tool_id="mock_submit_module_public_mydata_action",
                receipt_id=None,
                outcome=outcome.value,  # type: ignore[arg-type]
            )
        )
        return SubmitOutput(
            transaction_id=derive_transaction_id(
                "mock_submit_module_public_mydata_action",
                {k: v for k, v in params.items() if k != "delegation_context"},
                adapter_nonce=_ADAPTER_NONCE,
            ),
            status=SubmitStatus.rejected,
            adapter_receipt=stamp_mock_response(
                {
                    "error": outcome.value,
                    "tool_id": "mock_submit_module_public_mydata_action",
                },
                reference_implementation=_REFERENCE_IMPL,
                actual_endpoint_when_live=_ACTUAL_ENDPOINT,
                security_wrapping_pattern=_SECURITY_WRAPPING,
                policy_authority=_POLICY_AUTHORITY,
                international_reference=_INTERNATIONAL_REF,
            ),
        )

    # Success path — produce synthetic 접수번호
    suffix = secrets.token_hex(4).upper()
    receipt_id = f"mydata-{datetime.now(_SEOUL_TZ).strftime('%Y-%m-%d')}-ACT-{suffix}"

    logger.debug(
        "mock_submit_module_public_mydata_action: success, receipt_id=%s action_type=%s",
        receipt_id,
        typed.action_type,
    )

    append_delegation_used(
        DelegationUsedEvent(
            kind="delegation_used",
            ts=datetime.now(UTC),
            session_id=typed.session_id,
            delegation_token=token_value,
            consumer_tool_id="mock_submit_module_public_mydata_action",
            receipt_id=receipt_id,
            outcome="success",
        )
    )

    return SubmitOutput(
        transaction_id=derive_transaction_id(
            "mock_submit_module_public_mydata_action",
            {k: v for k, v in params.items() if k != "delegation_context"},
            adapter_nonce=_ADAPTER_NONCE,
        ),
        status=SubmitStatus.succeeded,
        adapter_receipt=stamp_mock_response(
            {
                "receipt_id": receipt_id,
                "action_type": typed.action_type,
                "target_institution_code": typed.target_institution_code,
                "status": "처리완료",
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
    tool_id="mock_submit_module_public_mydata_action",
    primitive=AdapterPrimitive.submit,
    module_path=__name__,
    input_model_ref=f"{__name__}.PublicMydataActionParams",
    source_mode=AdapterSourceMode.OOS,
    published_tier_minimum="mydata_individual_aal2",
    nist_aal_hint="AAL2",
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=5,
    search_hint={
        "ko": ["마이데이터", "동의", "데이터이동권", "마이데이터액션", "금융보안원"],
        "en": ["mydata", "data portability", "consent", "mydata action", "financial security"],
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
            "마이데이터 액션 확장 — 금융보안원 마이데이터 표준 정책 (Spec 1636 mandate)."
        ),
        citizen_facing_gate="submit",
        last_verified=datetime(2026, 5, 4, tzinfo=UTC),
    ),
)

# Register in the submit dispatcher's in-process table
register_submit_adapter(REGISTRATION, invoke)

__all__ = ["REGISTRATION", "PublicMydataActionParams", "invoke"]
