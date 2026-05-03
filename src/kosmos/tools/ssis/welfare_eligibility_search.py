# SPDX-License-Identifier: Apache-2.0
"""MOHW welfare eligibility search adapter via SSIS — interface-only stub.

Calls the SSIS NationalWelfarelistV001 endpoint to return welfare services
matching life stage, household type, interest theme, age, or keyword.

Epic δ #2295: citizen-facing gate = login (welfare eligibility requires authentication).
The Layer 3 auth-gate in ``executor.invoke()`` short-circuits unauthenticated
calls to ``LookupError(reason="auth_required")`` before handle() is reached
(FR-025, FR-026, SC-006). handle() raises Layer3GateViolation as defence-in-depth.

# TODO: implement XML parsing and response normalization once Layer 3 auth gate
# is provisioned (Epic #16 / #20). Response format is XML per SSIS v2.2 §1.1.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from kosmos.tools.errors import Layer3GateViolation
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.ssis.codes import (
    CallType,
    IntrsThemaCode,
    LifeArrayCode,
    OrderBy,
    SrchKeyCode,
    TrgterIndvdlCode,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# T018 — MOHW welfare eligibility search input schema
# ---------------------------------------------------------------------------


class MohwWelfareEligibilitySearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    search_wrd: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Free-text keyword to search welfare-service names/summaries. "
            "Korean preferred. Example: '출산' for childbirth benefits. "
            "Omit to filter by codes only."
        ),
    )
    srch_key_code: SrchKeyCode = Field(
        default=SrchKeyCode.all_fields,
        description="Which fields to search (001 name, 002 summary, 003 both).",
    )
    life_array: LifeArrayCode | None = Field(
        default=None,
        description="Life-stage filter (e.g. '007' for 임신·출산).",
    )
    trgter_indvdl_array: TrgterIndvdlCode | None = Field(
        default=None,
        description="Target individual / household-type filter (e.g. '020' 다자녀).",
    )
    intrs_thema_array: IntrsThemaCode | None = Field(
        default=None,
        description=(
            "Interest-theme filter (e.g. '080' for 임신·출산, '010' for 신체건강). "
            "NOTE: Spec draft used '010' as a placeholder; the authoritative "
            "임신·출산 code for intrsThemaArray is '080'."
        ),
    )
    age: int | None = Field(
        default=None,
        ge=0,
        le=150,
        description=(
            "Citizen age in years. Used to filter age-eligible services. "
            "Do NOT request this from the citizen unless they have consented — "
            "this field is part of the login-gated surface (citizen PII)."
        ),
    )
    onap_psblt_yn: Literal["Y", "N"] | None = Field(
        default=None,
        description=(
            "Filter to only online-applicable services when 'Y'. "
            "Omit to return both online and offline services."
        ),
    )
    order_by: OrderBy = Field(
        default=OrderBy.popular,
        description="Sort order: 'popular' (조회 수) or 'date' (등록순).",
    )
    page_no: int = Field(
        default=1,
        ge=1,
        le=1000,
        description="Page number (1-indexed). SSIS caps at 1000.",
    )
    num_of_rows: int = Field(
        default=10,
        ge=1,
        le=500,
        description="Records per page. Default 10, maximum 500 per SSIS API contract.",
    )
    call_tp: Literal[CallType.list_] = Field(
        default=CallType.list_,
        description="Call type — fixed to 'L' (list) for NationalWelfarelistV001. Do not override.",
    )


# ---------------------------------------------------------------------------
# T019 — Output schemas: SsisWelfareServiceItem + MohwWelfareEligibilitySearchOutput
# ---------------------------------------------------------------------------


class SsisWelfareServiceItem(BaseModel):
    """Single welfare service record from NationalWelfarelistV001."""

    model_config = ConfigDict(extra="allow", frozen=True)

    servId: str = Field(description="서비스ID (e.g. 'WLF00001188')")  # noqa: N815
    servNm: str = Field(description="서비스명")  # noqa: N815
    jurMnofNm: str = Field(description="소관부처명 (ministry)")  # noqa: N815
    jurOrgNm: str | None = Field(default=None, description="소관조직명 (bureau)")  # noqa: N815
    inqNum: str | None = Field(default=None, description="조회수 (raw string)")  # noqa: N815
    servDgst: str | None = Field(default=None, description="서비스 요약")  # noqa: N815
    servDtlLink: str | None = Field(default=None, description="서비스 상세링크 (bokjiro.go.kr)")  # noqa: N815
    svcfrstRegTs: str | None = Field(default=None, description="서비스등록일")  # noqa: N815
    lifeArray: str | None = Field(default=None, description="생애주기 (comma-separated names)")  # noqa: N815
    intrsThemaArray: str | None = Field(default=None, description="관심주제")  # noqa: N815
    trgterIndvdlArray: str | None = Field(default=None, description="가구유형")  # noqa: N815
    sprtCycNm: str | None = Field(default=None, description="지원주기 (e.g. '1회성')")  # noqa: N815
    srvPvsnNm: str | None = Field(default=None, description="제공유형 (e.g. '전자바우처')")  # noqa: N815
    rprsCtadr: str | None = Field(default=None, description="문의처")  # noqa: N815
    onapPsbltYn: Literal["Y", "N"] | None = Field(default=None, description="온라인신청가능여부")  # noqa: N815


class MohwWelfareEligibilitySearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_code: str = Field(description="결과코드 ('0' = SUCCESS in SSIS v2.0)")
    result_message: str = Field(description="결과메세지")
    page_no: int
    num_of_rows: int
    total_count: int
    items: list[SsisWelfareServiceItem] = Field(
        description="List of welfare services matching the query."
    )


# ---------------------------------------------------------------------------
# T020 — Interface-only stub, GovAPITool registration, and handle()
# ---------------------------------------------------------------------------


class _MohwWelfareEligibilitySearchOutputStub(RootModel[dict[str, Any]]):
    """Placeholder output schema for GovAPITool registration.

    Real XML-parsed output shape is deferred until Layer 3 auth is provisioned
    (Epic #16 / #20). Real models (SsisWelfareServiceItem +
    MohwWelfareEligibilitySearchOutput) are authored above ready for switch-over.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)


MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL = GovAPITool(
    id="mohw_welfare_eligibility_search",
    name_ko="복지서비스 목록 조회 (한국사회보장정보원 SSIS)",
    ministry="MOHW",
    category=["복지", "출산", "의료비", "보조금", "사회보장"],
    endpoint=(
        "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
    ),
    auth_type="api_key",
    input_schema=MohwWelfareEligibilitySearchInput,
    output_schema=_MohwWelfareEligibilitySearchOutputStub,  # RootModel[dict] stub
    llm_description=(
        "Search the SSIS central-ministry welfare-service catalog for services matching "
        "life stage, household type, interest theme, age, or keyword. Returns a ranked "
        "list with serviceId, name, ministry, summary, and bokjiro.go.kr detail link. "
        "Use for 'am I eligible for X?' / '출산 보조금 뭐 있어?' questions. "
        "IMPORTANT: This is a login-gated service — citizen authentication required. "
        "Unauthenticated sessions receive auth_required."
    ),
    search_hint=(
        "복지서비스 출산 보조금 복지혜택 신청 사회보장정보원 보건복지부 임산부 지원 "
        "welfare benefit eligibility childbirth subsidy MOHW SSIS social security Korea"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.mohw.go.kr/react/policy/index.jsp?PAR_MENU_ID=06&MENU_ID=06",
        real_classification_text="보건복지부 공공데이터 이용약관 — 복지서��스 적격 조회 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",  # Spec 2522 US4: public API-key catalog, no citizen login
        last_verified=datetime(2026, 5, 2, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    is_core=False,
    primitive="lookup",
    trigger_examples=[
        "기초생활수급 신청",
        "장애인 활동지원",
        "노인장기요양",
    ],
)


async def handle(inp: MohwWelfareEligibilitySearchInput) -> dict[str, object]:
    """Defence-in-depth backstop — should never be reached.

    The Layer 3 auth-gate in executor.invoke() short-circuits on
    Epic δ #2295: auth gate based on policy.citizen_facing_gate (FR-025, FR-026, SC-006).

    # TODO: implement full XML parsing and response normalization once
    # Layer 3 auth gate is provisioned (Epic #16 / #20).

    Raises:
        Layer3GateViolation: Always — signals a programming error if reached.
    """
    raise Layer3GateViolation("mohw_welfare_eligibility_search")


def register(registry: object, executor: object) -> None:
    """Register the MOHW welfare eligibility search tool and its adapter.

    Called by ``register_all.py`` at application startup.

    Args:
        registry: A ToolRegistry instance.
        executor: A ToolExecutor instance.
    """
    from kosmos.tools.executor import ToolExecutor  # noqa: PLC0415
    from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, MohwWelfareEligibilitySearchInput)
        return await handle(inp)

    registry.register(MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL)
    executor.register_adapter("mohw_welfare_eligibility_search", _adapter)
    logger.info(
        "Registered tool: mohw_welfare_eligibility_search "
        "(auth_required gate — interface-only stub, login gate per Epic δ #2295)"
    )
