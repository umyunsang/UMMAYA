# SPDX-License-Identifier: Apache-2.0
"""T025 — Mock submit adapter: traffic fine payment (data_go_kr ministry).

Matches the worked example from ``specs/031-five-primitive-harness/quickstart.md § 3``.

Adapter identity:
  tool_id: ``mock_traffic_fine_pay_v1``
  ministry: data_go_kr (공공데이터포털 — openapi.data.go.kr)
  source_mode: OOS (shape-mirrored from public data.go.kr traffic fine REST endpoints)
  primitive: submit

SC-002 compliance: ``FinesPayParams`` carries ministry-specific vocabulary
(payment methods, fine references) — this vocabulary MUST NOT appear on the
main ``SubmitInput`` / ``SubmitOutput`` envelope, only here in the adapter.

SC-005 compliance: ``published_tier_minimum="ganpyeon_injeung_kakao_aal2"`` gates
access to AAL2+ callers. Tier gate enforcement is the dispatcher's responsibility
(``kosmos.primitives.submit.submit()``); this module only declares the requirement.

Epic δ #2295: ``primitive=submit`` — payment is irreversible (submit gate).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

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

# ---------------------------------------------------------------------------
# Transparency constants — Epic ε #2296 retrofit (FR-005 / FR-025)
# contracts/mock-adapter-response-shape.md § 4 "EXISTING (retrofitted)" row
# ---------------------------------------------------------------------------

_REFERENCE_IMPL: Final = "ax-infrastructure-callable-channel"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/submit/traffic/fine-pay"
_SECURITY_WRAPPING: Final = "OAuth2.1 + mTLS + 경찰청 간편결제 gateway"
_POLICY_AUTHORITY: Final = "https://www.efine.go.kr/main/main.do"
_INTERNATIONAL_REF: Final = "UK GOV.UK Pay"

# ---------------------------------------------------------------------------
# T025-A: Adapter-typed input model
# ---------------------------------------------------------------------------


class FinesPayParams(BaseModel):
    """Typed params for the traffic fine payment adapter.

    Ministry-specific vocabulary lives HERE, not on the main SubmitInput envelope.
    Adapters validate params against this model at invocation time.

    SC-002: ``payment_method``, ``fine_reference`` are domain fields and MUST
    NOT appear on ``SubmitInput`` / ``SubmitOutput``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fine_reference: str = Field(
        min_length=1,
        max_length=32,
        description="Unique identifier for the traffic fine (e.g. 이의신청번호 or 고지서번호).",
    )
    payment_method: Literal["virtual_account", "card", "bank_transfer"] = Field(
        description="Payment channel for the fine settlement.",
    )


# ---------------------------------------------------------------------------
# T025-B: Mock invoke coroutine
# ---------------------------------------------------------------------------

# Nonce for deterministic transaction_id namespacing (T023)
_ADAPTER_NONCE = "mock_traffic_fine_pay_v1_nonce_v1"


async def invoke(params: dict[str, object]) -> SubmitOutput:
    """Mock invoke — validates params and returns a deterministic SubmitOutput.

    In production this coroutine would call the data.go.kr traffic fine API.
    In mock mode it validates the typed params and returns a fixture receipt.

    Args:
        params: Raw params dict from the main ``submit()`` envelope.

    Returns:
        ``SubmitOutput`` with deterministic ``transaction_id``.

    Raises:
        ``pydantic.ValidationError`` if params fail typed validation (the
        dispatcher catches this as ``AdapterInvocationError``).
    """
    # Validate params against the typed model (raises ValidationError on failure)
    typed: FinesPayParams = FinesPayParams.model_validate(params)
    logger.debug(
        "mock_traffic_fine_pay_v1: processing fine_reference=%s payment_method=%s",
        typed.fine_reference,
        typed.payment_method,
    )

    # Deterministic mock receipt — keyed on fine_reference for test predictability
    receipt_ref = hashlib.sha256(typed.fine_reference.encode()).hexdigest()[:12]

    return SubmitOutput(
        transaction_id=derive_transaction_id(
            "mock_traffic_fine_pay_v1",
            dict(params),
            adapter_nonce=_ADAPTER_NONCE,
        ),
        status=SubmitStatus.succeeded,
        adapter_receipt=stamp_mock_response(
            {
                "receipt_ref": f"MOCK-FP-{receipt_ref}",
                "fine_reference": typed.fine_reference,
                "payment_channel": typed.payment_method,
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
# T025-C: AdapterRegistration + self-registration
# ---------------------------------------------------------------------------

REGISTRATION = AdapterRegistration(
    tool_id="mock_traffic_fine_pay_v1",
    primitive=AdapterPrimitive.submit,
    module_path=__name__,
    input_model_ref=f"{__name__}.FinesPayParams",
    source_mode=AdapterSourceMode.OOS,
    published_tier_minimum="ganpyeon_injeung_kakao_aal2",
    nist_aal_hint="AAL2",
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    search_hint={
        "ko": ["과태료", "교통범칙금", "납부", "벌금"],
        "en": ["traffic fine", "payment", "fine settlement"],
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
            "교통 범칙금 / 과태료 납부 — 경찰청 이파인 공식 정책 페이지 (Spec 1636 mandate)."
        ),
        citizen_facing_gate="submit",
        last_verified=datetime(2026, 5, 4, tzinfo=UTC),
    ),
)

# Register in the submit dispatcher's in-process table
register_submit_adapter(REGISTRATION, invoke)

__all__ = ["REGISTRATION", "FinesPayParams", "invoke"]
