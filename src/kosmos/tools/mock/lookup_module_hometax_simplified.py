# SPDX-License-Identifier: Apache-2.0
"""Mock lookup adapter — Hometax Simplified Data (홈택스 간소화 자료).

Epic ε #2296 — T028 Phase 4C US1 Lookup Mocks.

Registers as a ``GovAPITool`` in the main ``ToolRegistry`` (not a per-primitive
sub-registry) because the ``lookup`` primitive resolves adapter IDs against the
BM25-indexed main registry.

Requires a ``DelegationContext`` and validates the scope matches
``"lookup:hometax.simplified"`` (fail-closed per Constitution § II). Without
delegation the adapter returns a typed auth_required envelope instead of
returning synthetic citizen tax data.

Transparency constants (contracts/mock-adapter-response-shape.md § 4):
  _REFERENCE_IMPL    = "public-mydata-read-v240930"
  _INTERNATIONAL_REF = "UK HMRC Making Tax Digital"

Policy authority:
  https://www.hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index.xml
  (Hometax public-data policy disclosure, read-only gateway)

FR-003, FR-025, SC-005 compliance:
- Six transparency fields stamped via ``stamp_mock_response``.
- Bilingual ``search_hint`` for BM25 discovery.
- Policy authority URL cites the agency-published Hometax portal.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, RootModel

from kosmos.primitives.delegation import DelegationContext
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
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/lookup/hometax_simplified"
_SECURITY_WRAPPING: Final = "마이데이터 표준동의서 OAuth2 + finAuth"
_POLICY_AUTHORITY: Final = (
    "https://www.hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index.xml"
)
_INTERNATIONAL_REF: Final = "UK HMRC Making Tax Digital"
_MOCK_FIDELITY_GRADE: Final = "B-official-consent-flow-private-payload-inferred"
_MOCK_EVIDENCE: Final[dict[str, Any]] = {
    "credential_status": "student_no_live_authority",
    "basis_urls": [
        "https://mob.tbys.hometax.go.kr/jsonAction.do?actionId=UTBYSFAA02F001",
        "https://www.mydata.go.kr/pc/intro/serviceIntro.do?tab=tab_3&type=A",
        "https://docs.developer.singpass.gov.sg/docs/legacy-myinfo-v3-v4/technical-specifications/myinfo-v4",
    ],
    "supports": [
        "official Hometax simplified-data consent and cancellation flow",
        "public MyData consent-based document substitution pattern",
        "OAuth consent-code-token-person-data analog for private data retrieval",
    ],
    "inference_boundary": (
        "Private Hometax partner payload names are not public; KOSMOS mirrors the "
        "official consent lifecycle and data minimization fields, not a claimed live schema."
    ),
    "live_swap_requirements": [
        "NTS or MOIS partner approval",
        "citizen authentication and consent artifact",
        "agency API key or certificate",
        "recorded fixture regenerated from official development sandbox",
    ],
}

# Required delegation scope when a DelegationContext is present.
_REQUIRED_SCOPE: Final = "lookup:hometax.simplified"

# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class HometaxSimplifiedInput(BaseModel):
    """Input schema for mock_lookup_module_hometax_simplified.

    Pydantic v2 strict model (extra='forbid', frozen=True).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int = Field(
        default=2025,
        ge=2020,
        le=2030,
        description=(
            "귀속 연도 (year of income attribution). "
            "Example: 2024 for the 2024 tax year (신고 기한: 2025-05). "
            "If the citizen did not specify a year, omit this field and the "
            "Mock fixture default is used."
        ),
    )
    resident_id_prefix: str = Field(
        default="900101",
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description=(
            "Mock-only fixture selector. Do NOT ask the citizen for resident ID "
            "digits in chat; omit this field unless it already came from a "
            "secure non-LLM channel."
        ),
    )
    delegation_context: DelegationContext | None = Field(
        default=None,
        description=(
            "DelegationContext returned by mock_verify_module_modid. Required; "
            "must include scope 'lookup:hometax.simplified'."
        ),
    )


# ---------------------------------------------------------------------------
# Output schema (placeholder — shape mirrors 마이데이터 read v240930)
# ---------------------------------------------------------------------------


class _HometaxSimplifiedOutput(RootModel[dict[str, Any]]):
    """Placeholder output schema.

    Real shape tracks the 마이데이터 표준동의서 v240930 spec. Mock returns a
    synthetic fixture stamped with the six transparency fields.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ---------------------------------------------------------------------------
# Synthetic fixture builder
# ---------------------------------------------------------------------------


def _build_fixture(inp: HometaxSimplifiedInput) -> dict[str, Any]:
    """Build a synthetic 간소화 자료 fixture for the given year / resident ID prefix."""
    fetched_at = datetime.now(_SEOUL_TZ).isoformat()
    citizen_scope_ref = f"hometax-simplified-{inp.year}-mock-subject"
    return {
        "year": inp.year,
        "kind": "simplified_data_summary",
        "citizen_scope_ref": citizen_scope_ref,
        "consent_receipt": {
            "consent_type": "annual_simplified_data_bulk_provision",
            "subject": "taxpayer_and_consented_dependents",
            "recipient_role": "withholding_agent_or_tax_agent",
            "purpose": "year_end_tax_settlement_or_income_tax_filing",
            "retention_rule": "up_to_5_years_after_statutory_filing_deadline",
            "citizen_exclusion_allowed": True,
            "revocation_channel": "hometax_sontax_consent_status",
        },
        "retrieval_flow": [
            "verify_delegation_scope",
            "confirm_consent_receipt",
            "select_minimum_required_deduction_categories",
            "join_source_documents",
            "return_fixture_bundle",
        ],
        "bundle": {
            "bundle_id": f"mock-nts-yds-{inp.year}-001",
            "data_minimization": "category_totals_and_issuer_summaries_only",
            "freshness": "fixture",
            "fetched_at": fetched_at,
        },
        "items": [
            {
                "category": "부가세 과세 매출",
                "category_en": "vat_taxable_sales",
                "amount_krw": 38_500_000,
                "issuer": "MOCK_CARD_AND_CASH_RECEIPT_NETWORK",
                "source_document_code": "vat_sales_reconciliation_summary",
                "eligible_for_company_bundle": True,
                "excluded_by_citizen": False,
            },
            {
                "category": "매입세액 공제 가능 매입",
                "category_en": "vat_deductible_purchases",
                "amount_krw": 12_300_000,
                "issuer": "MOCK_E_TAX_INVOICE_NETWORK",
                "source_document_code": "vat_purchase_tax_invoice_summary",
                "eligible_for_company_bundle": True,
                "excluded_by_citizen": False,
            },
            {
                "category": "근로소득",
                "category_en": "employment_income",
                "amount_krw": 42_000_000,
                "issuer": "MOCK_EMPLOYER_CORP",
                "source_document_code": "earned_income_payment_statement",
                "eligible_for_company_bundle": True,
                "excluded_by_citizen": False,
            },
            {
                "category": "의료비",
                "category_en": "medical_expense",
                "amount_krw": 1_200_000,
                "issuer": "MOCK_HOSPITAL",
                "source_document_code": "medical_expense_deduction",
                "eligible_for_company_bundle": True,
                "excluded_by_citizen": False,
            },
            {
                "category": "교육비",
                "category_en": "education_expense",
                "amount_krw": 800_000,
                "issuer": "MOCK_SCHOOL",
                "source_document_code": "education_expense_deduction",
                "eligible_for_company_bundle": True,
                "excluded_by_citizen": False,
            },
        ],
        "vat_reconciliation": {
            "tax_year": inp.year,
            "income_type": "부가가치세",
            "total_income_krw": 38_500_000,
            "deductible_purchase_krw": 12_300_000,
            "estimated_tax_due_krw": 2_620_000,
            "payment_guardrail": (
                "Mock payment is not executed without a separate submit step "
                "or explicit citizen confirmation."
            ),
        },
        "fetched_at": fetched_at,
        "subject_ref": "mock-subject-redacted",
        "disclaimer": (
            "Mock fixture — data is synthetic. Real endpoint requires authenticated "
            "Hometax or public MyData consent and partner API authority."
        ),
    }


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


async def handle(
    inp: HometaxSimplifiedInput,
    *,
    delegation_context: object | None = None,
) -> dict[str, Any]:
    """Handle a Hometax simplified data lookup.

    Requires a ``delegation_context`` and validates that the token scope
    matches ``"lookup:hometax.simplified"``; rejects with a typed
    auth_required envelope when missing or mismatched.

    Returns a ``LookupOutput``-shaped envelope (``{"kind": "record", "item": …}``
    or ``{"kind": "error", …}``) so the response passes the executor's
    discriminated-union validator (``kosmos.tools.envelope.normalize``). The
    six transparency fields are stamped onto the inner ``item`` payload (or the
    error envelope itself, for error variants).

    The outer ``meta`` block is injected by ``normalize()`` — adapters MUST NOT
    pre-populate ``meta`` themselves (system-reserved keys are dropped).
    """
    delegation_context = delegation_context or inp.delegation_context
    if not isinstance(delegation_context, DelegationContext):
        logger.warning("mock_lookup_module_hometax_simplified: missing delegation context")
        return {
            "kind": "error",
            "reason": "auth_required",
            "message": (
                "DelegationContext with scope 'lookup:hometax.simplified' is required "
                "before Hometax simplified data lookup. Call verify first and pass the "
                "returned delegation_context in lookup params."
            ),
            "retryable": False,
        }

    token_scope = delegation_context.token.scope
    # Scope may be comma-joined multi-scope; match exact entry.
    if _REQUIRED_SCOPE not in token_scope.split(","):
        logger.warning(
            "mock_lookup_module_hometax_simplified: scope violation "
            "(token_scope=%r required=%r)",
            token_scope,
            _REQUIRED_SCOPE,
        )
        # LookupError envelope variant — `kind="error"` is the
        # discriminator. ``reason`` MUST be a member of
        # ``LookupErrorReason`` (envelope ``extra='forbid'``); a
        # missing-scope delegation maps to ``auth_required`` (the
        # closest semantic match in the closed enum). Transparency
        # fields are NOT stamped here — the LookupError schema
        # forbids extra keys; ``meta.source`` (injected by
        # ``envelope.normalize()``) carries the tool_id instead.
        return {
            "kind": "error",
            "reason": "auth_required",
            "message": (
                f"Delegation token scope {token_scope!r} does not "
                f"grant {_REQUIRED_SCOPE!r}."
            ),
            "retryable": False,
        }

    # LookupRecord envelope variant — domain payload + transparency stamp
    # live inside `item`; `meta` is filled by `envelope.normalize()`.
    stamped_item = stamp_mock_response(
        _build_fixture(inp),
        reference_implementation=_REFERENCE_IMPL,
        actual_endpoint_when_live=_ACTUAL_ENDPOINT,
        security_wrapping_pattern=_SECURITY_WRAPPING,
        policy_authority=_POLICY_AUTHORITY,
        international_reference=_INTERNATIONAL_REF,
        mock_fidelity_grade=_MOCK_FIDELITY_GRADE,
        mock_evidence=_MOCK_EVIDENCE,
    )
    return {
        "kind": "record",
        "item": stamped_item,
    }


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL = GovAPITool(
    id="mock_lookup_module_hometax_simplified",
    name_ko="홈택스 간소화 자료 조회 (Mock — AX 채널 참조 구현)",
    ministry="MOIS",  # 행정안전부 (마이데이터 표준 관장)
    category=["홈택스", "연말정산", "간소화", "종합소득세", "마이데이터"],
    endpoint=_ACTUAL_ENDPOINT,
    auth_type="oauth",
    input_schema=HometaxSimplifiedInput,
    output_schema=_HometaxSimplifiedOutput,
    llm_description=(
        "Look up citizen's Hometax simplified data (간소화 자료) for year-end tax "
        "settlement (연말정산), comprehensive income tax filing (종합소득세), "
        "or VAT/sales-record reconciliation (부가세 매출자료 대조). "
        "Returns a synthetic fixture including employment income, medical expenses, "
        "VAT taxable sales, deductible purchases, and education expenses stamped "
        "with six AX-channel transparency fields. "
        "Requires a DelegationContext from mock_verify_module_modid with scope "
        "'lookup:hometax.simplified'; never call before verify. "
        "Do not ask for resident ID digits in chat; omit resident_id_prefix unless "
        "it already came from a secure non-LLM channel. "
        "This is a Mock adapter — no real Hometax API is called. "
        "Use this when a citizen asks to look up their tax-deduction data or "
        "simplified income data for the current or prior tax year."
    ),
    search_hint=(
        "홈택스 간소화 연말정산 종합소득세 부가세 부가가치세 매출자료 카드매출 "
        "현금영수증 세금납부 근로소득 의료비 교육비 마이데이터 hometax "
        "simplified year-end tax income tax VAT sales data card sales cash receipt "
        "tax payment deduction mydata"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url=_POLICY_AUTHORITY,
        real_classification_text=(
            "홈택스 공공데이터 포털 — 간소화 서비스 공공데이터 이용약관 "
            "(마이데이터 표준 연계 인증 기반 개인자료 조회)"
        ),
        citizen_facing_gate="login",
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
        "연말정산 간소화 자료 조회",
        "홈택스 소득공제 내역",
        "종합소득세 신고 자료",
        "부가세 매출자료 조회",
        "2024년 의료비 공제",
    ],
    delegation_source_tool_id="mock_verify_module_modid",
)


def register(registry: object, executor: object) -> None:
    """Register the Hometax simplified lookup mock into the main ToolRegistry.

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
        assert isinstance(inp, HometaxSimplifiedInput)
        return await handle(inp, delegation_context=inp.delegation_context)

    registry.register(MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL)
    executor.register_adapter("mock_lookup_module_hometax_simplified", _adapter)
    logger.info(
        "Registered mock tool: mock_lookup_module_hometax_simplified "
        "(login-gated, mock mode, AX-channel reference: %s)",
        _REFERENCE_IMPL,
    )
