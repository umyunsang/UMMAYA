# SPDX-License-Identifier: Apache-2.0
"""Mock lookup adapter — Gov24 Certificate Lookup (정부24 증명서 조회).

Epic ε #2296 — T029 Phase 4C US1 Lookup Mocks.

Registers as a ``GovAPITool`` in the main ``ToolRegistry`` (not a per-primitive
sub-registry) because the ``lookup`` primitive resolves adapter IDs against the
BM25-indexed main registry.

When called with a ``DelegationContext``, validates the scope matches
``"lookup:gov24.certificate"`` (fail-closed per Constitution § II). When no
delegation context is supplied, the adapter proceeds without scope enforcement
(lookups are read-only and may not require delegation in all flows).

Transparency constants (contracts/mock-adapter-response-shape.md § 4):
  _REFERENCE_IMPL    = "public-mydata-read-v240930"
  _INTERNATIONAL_REF = "Estonia X-Road"

Policy authority:
  https://www.gov.kr/portal/main/nlogin
  (정부24 — official citizen portal, certificate issuance gateway)

FR-003, FR-025, SC-005 compliance:
- Six transparency fields stamped via ``stamp_mock_response``.
- Bilingual ``search_hint`` for BM25 discovery.
- Policy authority URL cites the agency-published Gov24 portal.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Final, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, RootModel

from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.transparency import stamp_mock_response

logger = logging.getLogger(__name__)

# KOSMOS canonical citizen-facing timezone (Asia/Seoul). Internal
# OTEL/audit/IPC paths keep UTC; only envelope-visible timestamps switch.
_SEOUL_TZ = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------------------
# Per-adapter transparency constants (contracts/mock-adapter-response-shape.md § 3)
# ---------------------------------------------------------------------------

_REFERENCE_IMPL: Final = "public-mydata-read-v240930"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/lookup/gov24_certificate"
_SECURITY_WRAPPING: Final = "OAuth2.1 + mTLS + scope-bound bearer"
_POLICY_AUTHORITY: Final = "https://www.gov.kr/portal/main/nlogin"
_INTERNATIONAL_REF: Final = "Estonia X-Road"

# Required delegation scope when a DelegationContext is present.
_REQUIRED_SCOPE: Final = "lookup:gov24.certificate"

# ---------------------------------------------------------------------------
# Certificate type literals
# ---------------------------------------------------------------------------

CertificateType = Literal[
    "resident_registration",  # 주민등록등본
    "family_relations",  # 가족관계증명서
    "business_registration",  # 사업자등록증
]

# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class Gov24CertificateInput(BaseModel):
    """Input schema for mock_lookup_module_gov24_certificate.

    Pydantic v2 strict model (extra='forbid', frozen=True).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    certificate_type: CertificateType = Field(
        description=(
            "Type of certificate to look up. "
            "resident_registration: 주민등록등본 (resident registration extract). "
            "family_relations: 가족관계증명서 (family relations certificate). "
            "business_registration: 사업자등록증 (business registration certificate)."
        ),
    )
    purpose: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Purpose for which the certificate is requested (제출 목적). "
            "Example: '금융기관 제출용', '취업 지원 제출용'."
        ),
    )


# ---------------------------------------------------------------------------
# Output schema (placeholder — shape mirrors 마이데이터 read v240930)
# ---------------------------------------------------------------------------


class _Gov24CertificateOutput(RootModel[dict[str, Any]]):
    """Placeholder output schema.

    Real shape tracks the Gov24 public API certificate endpoint spec. Mock
    returns a synthetic fixture stamped with the six transparency fields.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ---------------------------------------------------------------------------
# Synthetic fixture builder
# ---------------------------------------------------------------------------

_CERT_FIXTURES: dict[CertificateType, dict[str, Any]] = {
    "resident_registration": {
        "certificate_type": "resident_registration",
        "certificate_type_ko": "주민등록등본",
        "issue_date": "2026-04-29",
        "issuer": "서울특별시 강남구청",
        "holder_name": "홍길동 (MOCK)",
        "household_members": [
            {"relation": "본인", "birth_year": 1985},
            {"relation": "배우자", "birth_year": 1987},
            {"relation": "자녀", "birth_year": 2015},
        ],
        "address": "서울특별시 강남구 테헤란로 1길 MOCK동 101호",
    },
    "family_relations": {
        "certificate_type": "family_relations",
        "certificate_type_ko": "가족관계증명서",
        "issue_date": "2026-04-29",
        "issuer": "서울특별시 강남구청",
        "holder_name": "홍길동 (MOCK)",
        "family_members": [
            {"relation": "본인", "birth_year": 1985, "gender": "남"},
            {"relation": "배우자", "birth_year": 1987, "gender": "여"},
            {"relation": "자녀", "birth_year": 2015, "gender": "남"},
        ],
    },
    "business_registration": {
        "certificate_type": "business_registration",
        "certificate_type_ko": "사업자등록증",
        "issue_date": "2026-04-29",
        "issuer": "국세청 서울지방국세청",
        "business_name": "MOCK 주식회사",
        "registration_number": "123-45-67890",
        "business_type": "법인",
        "representative": "홍길동 (MOCK)",
        "address": "서울특별시 강남구 테헤란로 MOCK빌딩 5층",
    },
}


def _build_fixture(inp: Gov24CertificateInput) -> dict[str, Any]:
    """Build a synthetic certificate fixture for the given certificate type."""
    base = dict(_CERT_FIXTURES[inp.certificate_type])
    return {
        **base,
        "purpose": inp.purpose,
        "fetched_at": datetime.now(_SEOUL_TZ).isoformat(),
        "disclaimer": (
            "Mock fixture — data is synthetic. Real endpoint requires authenticated Gov24 session."
        ),
    }


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


async def handle(
    inp: Gov24CertificateInput,
    *,
    delegation_context: object | None = None,
) -> dict[str, Any]:
    """Handle a Gov24 certificate lookup.

    When ``delegation_context`` is supplied, validates that the token scope
    matches ``"lookup:gov24.certificate"``; rejects with a scope-violation
    error if not. When absent, proceeds without delegation enforcement (the
    lookup is read-only).

    Returns a transparent, stamped synthetic fixture.
    """
    # Optional delegation scope check (fail-closed when context is present).
    if delegation_context is not None:
        from kosmos.primitives.delegation import DelegationContext

        if isinstance(delegation_context, DelegationContext):
            token_scope = delegation_context.token.scope
            # Scope may be comma-joined multi-scope; match exact entry.
            if _REQUIRED_SCOPE not in token_scope.split(","):
                logger.warning(
                    "mock_lookup_module_gov24_certificate: scope violation "
                    "(token_scope=%r required=%r)",
                    token_scope,
                    _REQUIRED_SCOPE,
                )
                return stamp_mock_response(
                    {
                        "kind": "error",
                        "reason": "scope_violation",
                        "message": (
                            f"Delegation token scope {token_scope!r} does not "
                            f"grant {_REQUIRED_SCOPE!r}."
                        ),
                        "retryable": False,
                    },
                    reference_implementation=_REFERENCE_IMPL,
                    actual_endpoint_when_live=_ACTUAL_ENDPOINT,
                    security_wrapping_pattern=_SECURITY_WRAPPING,
                    policy_authority=_POLICY_AUTHORITY,
                    international_reference=_INTERNATIONAL_REF,
                )

    domain_payload = _build_fixture(inp)
    return stamp_mock_response(
        domain_payload,
        reference_implementation=_REFERENCE_IMPL,
        actual_endpoint_when_live=_ACTUAL_ENDPOINT,
        security_wrapping_pattern=_SECURITY_WRAPPING,
        policy_authority=_POLICY_AUTHORITY,
        international_reference=_INTERNATIONAL_REF,
    )


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL = GovAPITool(
    id="mock_lookup_module_gov24_certificate",
    name_ko="정부24 증명서 조회 (Mock — AX 채널 참조 구현)",
    ministry="GOV24",
    category=["정부24", "주민등록등본", "가족관계증명서", "사업자등록증", "증명서"],
    endpoint=_ACTUAL_ENDPOINT,
    auth_type="oauth",
    input_schema=Gov24CertificateInput,
    output_schema=_Gov24CertificateOutput,
    llm_description=(
        "Look up citizen certificates via Gov24 (정부24): "
        "주민등록등본 (resident registration extract), "
        "가족관계증명서 (family relations certificate), or "
        "사업자등록증 (business registration certificate). "
        "Returns a synthetic fixture stamped with six AX-channel transparency fields. "
        "When a DelegationContext is provided, requires scope 'lookup:gov24.certificate'. "
        "This is a Mock adapter — no real Gov24 API is called. "
        "Use when a citizen asks to retrieve their registration documents or "
        "business registration details through the government portal."
    ),
    search_hint=(
        "정부24 주민등록등본 가족관계증명서 사업자등록증 증명서 발급 조회 "
        "gov24 resident certificate family relations cert business reg cert"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url=_POLICY_AUTHORITY,
        real_classification_text=(
            "정부24 공공데이터 포털 — 증명서 조회 서비스 공공데이터 이용약관 "
            "(OAuth2.1 인증 기반 읽기 전용 공공이용 허가)"
        ),
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    adapter_mode="mock",
    is_concurrency_safe=True,
    cache_ttl_seconds=0,
    rate_limit_per_minute=60,
    is_core=False,
    primitive="lookup",
    published_tier_minimum=None,
    nist_aal_hint=None,
    trigger_examples=[
        "주민등록등본 발급",
        "가족관계증명서 조회",
        "사업자등록증 확인",
        "정부24 증명서",
        "등본 발급",
    ],
)


def register(registry: object, executor: object) -> None:
    """Register the Gov24 certificate lookup mock into the main ToolRegistry.

    Called by ``register_all_tools()`` in ``src/kosmos/tools/register_all.py``.
    Follows the same ``register(registry, executor)`` pattern as Live adapters
    (e.g., ``nmc_emergency_search.register``).

    Args:
        registry: A ``ToolRegistry`` instance.
        executor: A ``ToolExecutor`` instance.
    """
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, Gov24CertificateInput)
        return await handle(inp)

    registry.register(MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL)
    executor.register_adapter("mock_lookup_module_gov24_certificate", _adapter)
    logger.info(
        "Registered mock tool: mock_lookup_module_gov24_certificate "
        "(read-only, mock mode, AX-channel reference: %s)",
        _REFERENCE_IMPL,
    )
