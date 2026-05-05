# SPDX-License-Identifier: Apache-2.0
"""T023 — Mock submit adapter: hometax tax return filing (홈택스 종합소득세 신고).

Epic ε #2296 — US1 Phase 4B new submit mocks.

Adapter identity:
  tool_id: ``mock_submit_module_hometax_taxreturn``
  ministry: hometax (국세청 홈택스)
  source_mode: OOS (shape-mirrored from hometax LLM-callable channel mandate)
  primitive: submit

Delegation contract (FR-009/010/011):
  Requires scope ``"submit:hometax.tax-return"`` in the caller's DelegationToken.
  Validates expiry, scope, session binding, and revocation before executing.
  Appends a ``delegation_used`` ledger event on EVERY invocation (success or failure).

International reference: UK HMRC Making Tax Digital
Policy authority: https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=12892&cntntsId=8104
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any, Final
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
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/submit/hometax/tax-return"
_SECURITY_WRAPPING: Final = "OAuth2.1 + mTLS + scope-bound bearer + hometax session-pin"
_POLICY_AUTHORITY: Final = (
    "https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=12892&cntntsId=8104"
)
_INTERNATIONAL_REF: Final = "UK HMRC Making Tax Digital"

# Required delegation scope for this adapter
_REQUIRED_SCOPE: Final = "submit:hometax.tax-return"

# ---------------------------------------------------------------------------
# Typed input model
# ---------------------------------------------------------------------------


class HometaxTaxreturnParams(BaseModel):
    """Typed params for the hometax tax return filing adapter.

    Domain vocabulary lives HERE, not on the main SubmitInput envelope (SC-002).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tax_year: int = Field(
        ge=2020,
        le=2030,
        description="Tax year for the return (e.g. 2025 for 2025 income).",
    )
    income_type: str = Field(
        min_length=1,
        max_length=32,
        description=(
            "Income category code (e.g. '사업소득', '근로소득', '종합소득'). "
            "Agency-defined classification."
        ),
    )
    total_income_krw: int = Field(
        ge=0,
        description="Total declared income in KRW.",
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

_ADAPTER_NONCE = "mock_submit_module_hometax_taxreturn_nonce_v1"


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
    typed = HometaxTaxreturnParams.model_validate(params)
    delegation_ctx = typed.delegation_context
    token = delegation_ctx.token
    token_value = token.delegation_token

    # Lazy import to avoid circular dependency; FileLedgerReader is lightweight
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
            "mock_submit_module_hometax_taxreturn: delegation rejected (%s) for token=%s",
            outcome.value,
            token_value[:12],
        )
        # Append delegation_used event with rejection outcome
        append_delegation_used(
            DelegationUsedEvent(
                kind="delegation_used",
                ts=datetime.now(UTC),
                session_id=typed.session_id,
                delegation_token=token_value,
                consumer_tool_id="mock_submit_module_hometax_taxreturn",
                receipt_id=None,
                outcome=outcome.value,  # type: ignore[arg-type]
            )
        )
        return SubmitOutput(
            transaction_id=derive_transaction_id(
                "mock_submit_module_hometax_taxreturn",
                {k: v for k, v in params.items() if k != "delegation_context"},
                adapter_nonce=_ADAPTER_NONCE,
            ),
            status=SubmitStatus.rejected,
            adapter_receipt=stamp_mock_response(
                {"error": outcome.value, "tool_id": "mock_submit_module_hometax_taxreturn"},
                reference_implementation=_REFERENCE_IMPL,
                actual_endpoint_when_live=_ACTUAL_ENDPOINT,
                security_wrapping_pattern=_SECURITY_WRAPPING,
                policy_authority=_POLICY_AUTHORITY,
                international_reference=_INTERNATIONAL_REF,
            ),
        )

    # Success path — produce deterministic synthetic 접수번호
    suffix = secrets.token_hex(4).upper()
    receipt_id = f"hometax-{datetime.now(_SEOUL_TZ).strftime('%Y-%m-%d')}-RX-{suffix}"

    logger.debug(
        "mock_submit_module_hometax_taxreturn: success, receipt_id=%s tax_year=%d",
        receipt_id,
        typed.tax_year,
    )

    # Append delegation_used event with success outcome
    append_delegation_used(
        DelegationUsedEvent(
            kind="delegation_used",
            ts=datetime.now(UTC),
            session_id=typed.session_id,
            delegation_token=token_value,
            consumer_tool_id="mock_submit_module_hometax_taxreturn",
            receipt_id=receipt_id,
            outcome="success",
        )
    )

    return SubmitOutput(
        transaction_id=derive_transaction_id(
            "mock_submit_module_hometax_taxreturn",
            {k: v for k, v in params.items() if k != "delegation_context"},
            adapter_nonce=_ADAPTER_NONCE,
        ),
        status=SubmitStatus.succeeded,
        adapter_receipt=stamp_mock_response(
            {
                "receipt_id": receipt_id,
                "tax_year": typed.tax_year,
                "income_type": typed.income_type,
                "total_income_krw": typed.total_income_krw,
                "status": "신고완료",
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
    tool_id="mock_submit_module_hometax_taxreturn",
    primitive=AdapterPrimitive.submit,
    module_path=__name__,
    input_model_ref=f"{__name__}.HometaxTaxreturnParams",
    source_mode=AdapterSourceMode.OOS,
    published_tier_minimum="mobile_id_mdl_aal2",  # minimum identity tier for delegation token
    nist_aal_hint="AAL2",
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=5,
    search_hint={
        "ko": ["홈택스", "종합소득세", "신고", "세금신고", "연말정산"],
        "en": ["hometax", "tax return", "income tax", "tax filing"],
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
            "홈택스 종합소득세 신고 — 국세청 공식 정책 페이지 (Spec 1636 Live-channel mandate)."
        ),
        citizen_facing_gate="submit",
        last_verified=datetime(2026, 5, 4, tzinfo=UTC),
    ),
)

# Register in the submit dispatcher's in-process table
register_submit_adapter(REGISTRATION, invoke)

__all__ = ["REGISTRATION", "HometaxTaxreturnParams", "invoke"]
