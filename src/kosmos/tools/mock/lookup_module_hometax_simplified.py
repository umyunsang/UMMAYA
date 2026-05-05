# SPDX-License-Identifier: Apache-2.0
"""Mock lookup adapter — Hometax Simplified Data (홈택스 간소화 자료).

Epic ε #2296 — T028 Phase 4C US1 Lookup Mocks.

Registers as a ``GovAPITool`` in the main ``ToolRegistry`` (not a per-primitive
sub-registry) because the ``lookup`` primitive resolves adapter IDs against the
BM25-indexed main registry.

When called with a ``DelegationContext``, validates the scope matches
``"lookup:hometax.simplified"`` (fail-closed per Constitution § II). When no
delegation context is supplied, the adapter proceeds without scope enforcement
(lookups are read-only and may not require delegation in all flows).

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
        ge=2020,
        le=2030,
        description=(
            "귀속 연도 (year of income attribution). "
            "Example: 2024 for the 2024 tax year (신고 기한: 2025-05)."
        ),
    )
    resident_id_prefix: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description=(
            "주민등록번호 앞 6자리 (first six digits of resident ID). "
            "Used to scope the simplified data query in Mock mode."
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
    return {
        "year": inp.year,
        "kind": "simplified_data_summary",
        "items": [
            {
                "category": "근로소득",
                "category_en": "employment_income",
                "amount_krw": 42_000_000,
                "issuer": "MOCK_EMPLOYER_CORP",
            },
            {
                "category": "의료비",
                "category_en": "medical_expense",
                "amount_krw": 1_200_000,
                "issuer": "MOCK_HOSPITAL",
            },
            {
                "category": "교육비",
                "category_en": "education_expense",
                "amount_krw": 800_000,
                "issuer": "MOCK_SCHOOL",
            },
        ],
        "fetched_at": datetime.now(_SEOUL_TZ).isoformat(),
        "resident_id_prefix": inp.resident_id_prefix,
        "disclaimer": (
            "Mock fixture — data is synthetic. Real endpoint requires authenticated MyData consent."
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

    When ``delegation_context`` is supplied, validates that the token scope
    matches ``"lookup:hometax.simplified"``; rejects with a scope-violation
    error if not. When absent, proceeds without delegation enforcement (the
    lookup is read-only).

    Returns a ``LookupOutput``-shaped envelope (``{"kind": "record", "item": …}``
    or ``{"kind": "error", …}``) so the response passes the executor's
    discriminated-union validator (``kosmos.tools.envelope.normalize``). The
    six transparency fields are stamped onto the inner ``item`` payload (or the
    error envelope itself, for error variants).

    The outer ``meta`` block is injected by ``normalize()`` — adapters MUST NOT
    pre-populate ``meta`` themselves (system-reserved keys are dropped).
    """
    # Optional delegation scope check (fail-closed when context is present).
    if delegation_context is not None:
        from kosmos.primitives.delegation import DelegationContext

        if isinstance(delegation_context, DelegationContext):
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
        "settlement (연말정산) or comprehensive income tax filing (종합소득세). "
        "Returns a synthetic fixture including employment income, medical expenses, "
        "and education expenses stamped with six AX-channel transparency fields. "
        "When a DelegationContext is provided, requires scope 'lookup:hometax.simplified'. "
        "This is a Mock adapter — no real Hometax API is called. "
        "Use this when a citizen asks to look up their tax-deduction data or "
        "simplified income data for the current or prior tax year."
    ),
    search_hint=(
        "홈택스 간소화 연말정산 종합소득세 근로소득 의료비 교육비 마이데이터 "
        "hometax simplified year-end tax income tax deduction mydata"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url=_POLICY_AUTHORITY,
        real_classification_text=(
            "홈택스 공공데이터 포털 — 간소화 서비스 공공데이터 이용약관 "
            "(마이데이터 표준 연계 읽기 전용 공공이용 허가)"
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
        "연말정산 간소화 자료 조회",
        "홈택스 소득공제 내역",
        "종합소득세 신고 자료",
        "2024년 의료비 공제",
        "근로소득 원천징수 확인",
    ],
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
        return await handle(inp)

    registry.register(MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL)
    executor.register_adapter("mock_lookup_module_hometax_simplified", _adapter)
    logger.info(
        "Registered mock tool: mock_lookup_module_hometax_simplified "
        "(read-only, mock mode, AX-channel reference: %s)",
        _REFERENCE_IMPL,
    )
