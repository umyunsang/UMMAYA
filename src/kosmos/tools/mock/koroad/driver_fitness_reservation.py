# SPDX-License-Identifier: Apache-2.0
"""Mock submit adapter: KOROAD driver fitness test reservation.

Adapter identity:
  tool_id: ``mock_koroad_driver_fitness_reservation_v1``
  ministry: 한국도로교통공단 안전운전 통합민원
  source_mode: OOS (official flow exists; callable AX channel is not public)
  primitive: submit

The official public page documents online availability for driver license
renewal / fitness-test flows. KOSMOS mirrors only the receipt shape needed for
the privileged submit chain; it does not claim a private KOROAD API contract.
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

_REFERENCE_IMPL: Final = "ax-infrastructure-callable-channel"
_ACTUAL_ENDPOINT: Final = (
    "https://api.gateway.kosmos.gov.kr/v1/submit/koroad/driver-fitness-reservation"
)
_SECURITY_WRAPPING: Final = "OAuth2.1 + mTLS + scope-bound bearer + KOROAD portal handoff"
_POLICY_AUTHORITY: Final = (
    "https://www.safedriving.or.kr/diGuide/selectDiGuide18.do?menuCd=MN-PO-12111"
)
_INTERNATIONAL_REF: Final = "Singapore APEX"
_ADAPTER_NONCE: Final = "mock_koroad_driver_fitness_reservation_v1_nonce_v1"


class DriverFitnessReservationParams(BaseModel):
    """Typed params for a mock driver fitness-test / renewal reservation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reservation_type: Literal["fitness_test", "license_renewal"] = Field(
        default="fitness_test",
        description="Requested KOROAD service flow.",
    )
    applicant_id: str = Field(
        min_length=1,
        max_length=64,
        description="Verified citizen subject identifier from the delegated session.",
    )
    preferred_center: str = Field(
        default="nearest_license_test_center",
        min_length=1,
        max_length=80,
        description="Citizen-selected or inferred driver license test center.",
    )
    preferred_date: str = Field(
        default="next_available",
        min_length=1,
        max_length=40,
        description="Requested date slot, or 'next_available' for mock reservation.",
    )
    contact_channel: Literal["sms", "email", "none"] = Field(
        default="sms",
        description="Notification channel for the mock reservation receipt.",
    )


async def invoke(params: dict[str, object]) -> SubmitOutput:
    """Validate params and return a deterministic mock reservation receipt."""
    typed = DriverFitnessReservationParams.model_validate(params)
    logger.debug(
        "mock_koroad_driver_fitness_reservation_v1: reserving type=%s center=%s",
        typed.reservation_type,
        typed.preferred_center,
    )

    canonical = "|".join(
        [
            typed.applicant_id,
            typed.reservation_type,
            typed.preferred_center,
            typed.preferred_date,
        ]
    )
    receipt_ref = hashlib.sha256(canonical.encode()).hexdigest()[:12]

    return SubmitOutput(
        transaction_id=derive_transaction_id(
            "mock_koroad_driver_fitness_reservation_v1",
            dict(params),
            adapter_nonce=_ADAPTER_NONCE,
        ),
        status=SubmitStatus.succeeded,
        adapter_receipt=stamp_mock_response(
            {
                "receipt_id": f"koroad-resv-{receipt_ref}",
                "reservation_type": typed.reservation_type,
                "reservation_status": "reserved",
                "preferred_center": typed.preferred_center,
                "preferred_date": typed.preferred_date,
                "contact_channel": typed.contact_channel,
                "service_surface": "KOROAD Safe Driving Integrated Civil Service",
                "mock": True,
            },
            reference_implementation=_REFERENCE_IMPL,
            actual_endpoint_when_live=_ACTUAL_ENDPOINT,
            security_wrapping_pattern=_SECURITY_WRAPPING,
            policy_authority=_POLICY_AUTHORITY,
            international_reference=_INTERNATIONAL_REF,
            mock_fidelity_grade="C-official-flow-documented-private-submit-api-inferred",
            mock_evidence={
                "credential_status": "student_no_live_authority",
                "basis_urls": [_POLICY_AUTHORITY],
                "supports": [
                    "driver license renewal and fitness-test public workflow",
                    "online application availability documented by official KOROAD page",
                    "shape-stable mock receipt until an official callable submit API exists",
                ],
                "inference_boundary": (
                    "KOSMOS does not know a private KOROAD reservation API. "
                    "This mock mirrors the public citizen workflow boundary and a "
                    "future AX-channel receipt shape only."
                ),
                "live_swap_requirements": [
                    "replace mock receipt with official KOROAD sandbox or production response",
                    "preserve tool_id params shape unless official schema requires migration",
                    "keep agency policy citation visible in the permission prompt",
                ],
            },
        ),
    )


REGISTRATION = AdapterRegistration(
    tool_id="mock_koroad_driver_fitness_reservation_v1",
    primitive=AdapterPrimitive.submit,
    module_path=__name__,
    input_model_ref=f"{__name__}.DriverFitnessReservationParams",
    source_mode=AdapterSourceMode.OOS,
    published_tier_minimum="ganpyeon_injeung_kakao_aal2",
    nist_aal_hint="AAL2",
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    search_hint={
        "ko": [
            "운전면허",
            "운전면허 갱신",
            "면허갱신",
            "적성검사",
            "적성검사예약",
            "운전면허적성검사예약",
            "도로교통공단",
            "운전면허 통합민원",
            "면허시험장예약",
        ],
        "en": [
            "driver license renewal",
            "driver fitness test",
            "fitness test reservation",
            "KOROAD reservation",
            "driver licensing civil service",
        ],
    },
    auth_type="oauth",
    nonce=_ADAPTER_NONCE,
    policy=AdapterRealDomainPolicy(
        real_classification_url=_POLICY_AUTHORITY,
        real_classification_text=(
            "운전면허 적성검사·갱신 예약 — 한국도로교통공단 안전운전 통합민원 공식 안내."
        ),
        citizen_facing_gate="submit",
        last_verified=datetime(2026, 5, 5, tzinfo=UTC),
    ),
)

register_submit_adapter(REGISTRATION, invoke)

__all__ = ["DriverFitnessReservationParams", "REGISTRATION", "invoke"]
