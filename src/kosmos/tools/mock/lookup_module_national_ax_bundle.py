# SPDX-License-Identifier: Apache-2.0
"""Mock lookup adapter — national AX bundle discovery.

This adapter provides a read-only, policy-shaped lookup record for bundled
citizen requests whose live agency module is not yet available in the student
project. It does not invent a private API contract; it returns a workflow
inventory, handoff boundary, and next-primitive hints grounded in KOSMOS' own
target-state national AX thesis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, RootModel

from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.transparency import stamp_mock_response

_SEOUL_TZ = ZoneInfo("Asia/Seoul")

_REFERENCE_IMPL: Final = "national-ax-common-service-discovery"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/lookup/national-ax/bundle"
_SECURITY_WRAPPING: Final = "read-only registry lookup + per-adapter delegated execution"
_POLICY_AUTHORITY: Final = "https://www.gov.kr/portal/service/serviceList"
_INTERNATIONAL_REF: Final = "Singapore APEX"
_MOCK_FIDELITY_GRADE: Final = "C-policy-mandated-common-routing-shape"
_MOCK_EVIDENCE: Final[dict[str, Any]] = {
    "credential_status": "student_no_live_authority",
    "basis_urls": [
        "https://www.gov.kr/portal/service/serviceList",
        "https://www.data.go.kr/",
        "https://www.apex.gov.sg/",
        "https://x-road.global/",
    ],
    "supports": [
        "public service catalog discovery before delegated agency execution",
        "common API hub pattern for cross-agency routing",
        "read-only workflow inventory when agency write APIs are not live",
    ],
    "inference_boundary": (
        "This adapter does not claim a live cross-agency endpoint. It is a "
        "read-only mock workflow inventory used until each agency module is "
        "wrapped as its own GovAPITool adapter."
    ),
    "live_swap_requirements": [
        "replace each bundle item with the agency-specific lookup adapter",
        "attach recorded official fixture or live sandbox response",
        "preserve primitive sequence shape and permission gate citations",
    ],
}


class NationalAXBundleLookupInput(BaseModel):
    """Read-only bundle lookup input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(
        min_length=1,
        max_length=300,
        description="Citizen request or narrowed service bundle to inventory.",
    )
    purpose: str = Field(
        default="국가 AX 묶음 민원/서비스 선행 조회",
        min_length=1,
        max_length=200,
        description="Korean purpose shown in the lookup receipt.",
    )


class _NationalAXBundleLookupOutput(RootModel[dict[str, Any]]):
    model_config = ConfigDict(arbitrary_types_allowed=True)


def _build_fixture(inp: NationalAXBundleLookupInput) -> dict[str, Any]:
    now = datetime.now(_SEOUL_TZ).isoformat()
    return {
        "workflow_kind": "national_ax_bundle_discovery",
        "lookup_ref": "mock-national-ax-bundle-20260505-001",
        "query": inp.query,
        "purpose": inp.purpose,
        "matched_public_service_surface": "registered-or-policy-mandated-citizen-channel",
        "recommended_next_primitives": [
            {
                "primitive": "submit",
                "why": "신청, 신고, 예약, 납부, 정정은 시민 확인 후 submit 단계에서만 처리합니다.",
            },
            {
                "primitive": "subscribe",
                "why": "기한, 처리상태, 알림, 후속 서류 요청은 subscribe 단계로 추적합니다.",
            },
        ],
        "bundle_items": [
            {
                "item": "status_or_eligibility_lookup",
                "boundary": "mock_inventory_only_until_agency_lookup_adapter_exists",
            },
            {
                "item": "application_or_payment_submit",
                "boundary": "requires_separate_permission_and_adapter_receipt",
            },
            {
                "item": "deadline_or_status_subscription",
                "boundary": "read_only_stream_or_polling_handle",
            },
        ],
        "citizen_visible_boundary": [
            "이 조회는 등록된 live/mock 도구를 고르기 위한 모의 선행 조회입니다.",
            "실제 신청·신고·납부 효력은 후속 submit 어댑터의 접수번호가 기준입니다.",
            "기관별 live API가 없으면 결과는 공식 포털/방문/별도 앱 handoff로 표시해야 합니다.",
        ],
        "fetched_at": now,
    }


async def handle(inp: NationalAXBundleLookupInput) -> dict[str, Any]:
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
    return {"kind": "record", "item": stamped_item}


MOCK_LOOKUP_MODULE_NATIONAL_AX_BUNDLE_TOOL = GovAPITool(
    id="mock_lookup_module_national_ax_bundle",
    name_ko="국가 AX 묶음 서비스 선행 조회 (Mock)",
    ministry="KOSMOS",
    category=["국가AX", "묶음민원", "상태조회", "절차조회", "알림추적"],
    endpoint=_ACTUAL_ENDPOINT,
    auth_type="public",
    input_schema=NationalAXBundleLookupInput,
    output_schema=_NationalAXBundleLookupOutput,
    llm_description=(
        "Read-only bundle discovery lookup for target-state citizen requests "
        "when the exact agency lookup adapter is not yet live. Use before submit "
        "for status, eligibility, required sequence, bill/fine/tax inventory, "
        "reservation prerequisites, documents, deadlines, or public-service "
        "handoff boundaries. It returns workflow inventory only; it does not "
        "claim live agency data."
    ),
    search_hint=(
        "상태 조회 자격 확인 절차 조회 서류 확인 기한 확인 처리상태 묶음 민원 "
        "운전면허 갱신 적성검사 과태료 자동차세 전기 수도 도시가스 자동이체 "
        "출생신고 아동수당 첫만남이용권 건강보험 피부양자 사망신고 유족급여 "
        "재산세 지방세 납부 위택스 생활비 기초생활 주거급여 긴급복지 의료비 "
        "본인부담상한제 전세 확정일자 임대차 신고 보증 생애최초 주택구입 "
        "사업자등록 영업신고 위생교육 4대보험 실업급여 워크넷 국가장학금 "
        "소음 민원 외국인등록 체류기간 개인정보 이용내역 내정보 주소정정 "
        "연락처정정 정보수정 record status eligibility "
        "workflow bundle lookup deadline reminder public service inventory"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url=_POLICY_AUTHORITY,
        real_classification_text=(
            "정부24 서비스 목록 기반 선행 서비스 탐색. 기관별 세부 권한은 후속 어댑터가 인용합니다."
        ),
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 5, 5, tzinfo=UTC),
    ),
    adapter_mode="mock",
    is_concurrency_safe=True,
    cache_ttl_seconds=0,
    rate_limit_per_minute=60,
    is_core=False,
    primitive="lookup",
)


def register(registry: object, executor: object) -> None:
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, NationalAXBundleLookupInput)
        return await handle(inp)

    registry.register(MOCK_LOOKUP_MODULE_NATIONAL_AX_BUNDLE_TOOL)
    executor.register_adapter("mock_lookup_module_national_ax_bundle", _adapter)


__all__ = [
    "MOCK_LOOKUP_MODULE_NATIONAL_AX_BUNDLE_TOOL",
    "NationalAXBundleLookupInput",
    "handle",
    "register",
]
