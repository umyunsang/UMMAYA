# SPDX-License-Identifier: Apache-2.0
"""Mock lookup adapter — Gov24 move-in dependent-sequence lookup.

This adapter fills the CIV-001 real-use gap: a move-in request should not jump
from location normalization directly to submit.  The agent first needs a
registry-discovered lookup record describing the required sequence and the
dependent address records that can be updated through the Gov24 move-in flow.

Policy authority:
  https://www.gov.kr/portal/service/serviceList
Evidence:
  https://www.gov.kr/portal/ntcItm/103589?Mcode=11226
  https://www.gov.kr/portal/ntcItm/105910
  https://www.law.go.kr/LSW/flDownload.do?bylClsCd=110202&flSeq=146083953
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Final, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from kosmos.primitives.delegation import DelegationContext
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.transparency import stamp_mock_response

logger = logging.getLogger(__name__)

_SEOUL_TZ = ZoneInfo("Asia/Seoul")

_REFERENCE_IMPL: Final = "ax-infrastructure-callable-channel"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/lookup/gov24/movein-sequence"
_SECURITY_WRAPPING: Final = "OAuth2.1 + mTLS + scope-bound bearer + 행정안전부 OAuth gateway"
_POLICY_AUTHORITY: Final = "https://www.gov.kr/portal/service/serviceList"
_INTERNATIONAL_REF: Final = "Singapore APEX"
_MOCK_FIDELITY_GRADE: Final = "B-official-flow-public-notice-private-schema-inferred"
_MOCK_EVIDENCE: Final[dict[str, Any]] = {
    "credential_status": "student_no_live_authority",
    "basis_urls": [
        "https://www.gov.kr/portal/ntcItm/103589?Mcode=11226",
        "https://www.gov.kr/portal/ntcItm/105910",
        "https://www.law.go.kr/LSW/flDownload.do?bylClsCd=110202&flSeq=146083953",
        "https://www.gm.go.kr/pt/complaint/application/PTMN024/PTCC0031.jsp",
    ],
    "supports": [
        "Government24 online move-in report service operation and staged reopening notice",
        "Government24 UI/UX and form updates for 전입신고+ and move-in report screens",
        "statutory move-in report form notes covering 14-day filing and mail-forwarding consent",
        (
            "official municipality Gov24 move-in page listing address-change, "
            "school-assignment, and vehicle-address related records"
        ),
    ],
    "inference_boundary": (
        "Government24 does not publish an LLM-callable move-in sequence schema. "
        "KOSMOS mirrors only the public workflow shape and marks live endpoint "
        "details as private/onboarding-gated."
    ),
    "live_swap_requirements": [
        "MOIS or Government24 API approval for move-in and linked address-change services",
        "service-specific request/receipt schema for 전입신고 and linked records",
        "scope-bound citizen delegation for lookup:gov24.movein and submit:gov24.minwon",
        "fixture replay replacement with recorded sandbox responses before live enablement",
    ],
}

_REQUIRED_SCOPE: Final = "lookup:gov24.movein"

LinkedMoveInUpdate = Literal[
    "vehicle_address",
    "health_insurance",
    "school_assignment",
    "mail_forwarding",
    "tax_address",
    "driver_license",
    "business_registration",
]

_DEFAULT_UPDATES: Final[list[LinkedMoveInUpdate]] = [
    "vehicle_address",
    "health_insurance",
    "school_assignment",
    "mail_forwarding",
]

_UPDATE_ALIASES: Final[dict[str, LinkedMoveInUpdate]] = {
    "자동차": "vehicle_address",
    "차량": "vehicle_address",
    "차주소": "vehicle_address",
    "vehicle": "vehicle_address",
    "car": "vehicle_address",
    "건강보험": "health_insurance",
    "국민연금": "health_insurance",
    "health": "health_insurance",
    "insurance": "health_insurance",
    "학교": "school_assignment",
    "배정": "school_assignment",
    "school": "school_assignment",
    "우편": "mail_forwarding",
    "mail": "mail_forwarding",
    "세금": "tax_address",
    "지방세": "tax_address",
    "tax": "tax_address",
    "운전면허": "driver_license",
    "면허": "driver_license",
    "license": "driver_license",
    "사업자": "business_registration",
    "business": "business_registration",
}


class Gov24MoveInSequenceInput(BaseModel):
    """Input schema for mock_lookup_module_gov24_movein_sequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adm_cd: str | None = Field(
        default=None,
        min_length=5,
        max_length=10,
        pattern=r"^\d{5,10}$",
        description=(
            "Administrative code returned by resolve_location for the new address. "
            "Pass this when available."
        ),
    )
    address: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
        description="Citizen's new move-in address or district text, if adm_cd is unavailable.",
    )
    requested_updates: list[LinkedMoveInUpdate] = Field(
        default_factory=lambda: list(_DEFAULT_UPDATES),
        max_length=7,
        description=(
            "Dependent address records the citizen wants checked before submit. "
            "Use the default when the request asks for car, health insurance, "
            "school, and other move-in address changes."
        ),
    )
    purpose: str = Field(
        default="전입신고 및 이사 관련 주소변경 절차 조회",
        min_length=1,
        max_length=200,
        description="Korean purpose shown in the lookup receipt.",
    )
    delegation_context: DelegationContext | None = Field(
        default=None,
        description=(
            "DelegationContext returned by mock_verify_ganpyeon_injeung. Required; "
            "must include scope 'lookup:gov24.movein'."
        ),
    )

    @model_validator(mode="after")
    def _require_location_anchor(self) -> Gov24MoveInSequenceInput:
        if not self.adm_cd and not self.address:
            raise ValueError("Either adm_cd or address must be provided.")
        return self

    @field_validator("requested_updates", mode="before")
    @classmethod
    def _normalize_requested_updates(cls, value: object) -> object:
        if value is None:
            return list(_DEFAULT_UPDATES)
        if not isinstance(value, list):
            return value
        normalized: list[LinkedMoveInUpdate] = []
        for raw_item in value:
            if not isinstance(raw_item, str):
                continue
            item = raw_item.strip()
            if item in _UPDATE_ROWS:
                normalized.append(item)
                continue
            item_lower = item.lower()
            for needle, canonical in _UPDATE_ALIASES.items():
                if needle.lower() in item_lower:
                    normalized.append(canonical)
                    break
        deduped = list(dict.fromkeys(normalized))
        return deduped or list(_DEFAULT_UPDATES)


class _Gov24MoveInSequenceOutput(RootModel[dict[str, Any]]):
    """Opaque lookup output schema for the stamped sequence fixture."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


_UPDATE_ROWS: dict[LinkedMoveInUpdate, dict[str, Any]] = {
    "vehicle_address": {
        "record": "자동차 등록원부 주소",
        "owner": "차량등록 관할기관",
        "sequence": "after_move_in_report",
        "kosmos_submit_minwon_type": "주소변경",
        "automation_boundary": "eligible_when_official_Gov24_linked_channel_exists",
    },
    "health_insurance": {
        "record": "건강보험/국민연금 주소",
        "owner": "국민건강보험공단/국민연금공단",
        "sequence": "after_move_in_report",
        "kosmos_submit_minwon_type": "주소변경",
        "automation_boundary": "official-public-guidance-shape-mirrored",
    },
    "school_assignment": {
        "record": "초등학교 배정",
        "owner": "관할 교육지원청/주민센터",
        "sequence": "after_move_in_report",
        "kosmos_submit_minwon_type": "주소변경",
        "automation_boundary": "school-assignment-notice-or-visit-may-be-required",
    },
    "mail_forwarding": {
        "record": "우편물 전입지 전송",
        "owner": "우정사업본부",
        "sequence": "with_or_after_move_in_report",
        "kosmos_submit_minwon_type": "주소변경",
        "automation_boundary": "requires separate citizen consent to provide address data",
    },
    "tax_address": {
        "record": "국세/지방세 관련 주소",
        "owner": "국세청/지방자치단체",
        "sequence": "after_move_in_report",
        "kosmos_submit_minwon_type": "주소변경",
        "automation_boundary": "eligible_when_official_Gov24_linked_channel_exists",
    },
    "driver_license": {
        "record": "운전면허 주소",
        "owner": "경찰청/도로교통공단",
        "sequence": "after_move_in_report",
        "kosmos_submit_minwon_type": "주소변경",
        "automation_boundary": "may_require_separate_license-channel_confirmation",
    },
    "business_registration": {
        "record": "사업자 등록 정정",
        "owner": "국세청",
        "sequence": "after_move_in_report",
        "kosmos_submit_minwon_type": "주소변경",
        "automation_boundary": "business-only_when_citizen_confirms_business_context",
    },
}


def _requested_update_rows(
    requested_updates: list[LinkedMoveInUpdate],
) -> list[dict[str, Any]]:
    return [{"update_id": update_id, **_UPDATE_ROWS[update_id]} for update_id in requested_updates]


def _build_fixture(inp: Gov24MoveInSequenceInput) -> dict[str, Any]:
    now = datetime.now(_SEOUL_TZ).isoformat()
    return {
        "workflow_kind": "gov24_movein_dependent_sequence",
        "lookup_ref": "mock-gov24-movein-sequence-20260505-001",
        "purpose": inp.purpose,
        "new_address": inp.address,
        "adm_cd": inp.adm_cd,
        "required_sequence": [
            {
                "step": 1,
                "primitive": "submit",
                "tool_id": "mock_submit_module_gov24_minwon",
                "minwon_type": "전입신고",
                "why": "전입신고가 접수되어야 주소 기반 연계 변경을 진행할 수 있습니다.",
                "blocking": True,
            },
            {
                "step": 2,
                "primitive": "submit",
                "tool_id": "mock_submit_module_gov24_minwon",
                "minwon_type": "주소변경",
                "why": (
                    "자동차, 건강보험, 학교배정, 우편물 전송 등 허용된 연계 주소 변경을 처리합니다."
                ),
                "blocking": False,
            },
        ],
        "dependent_records": _requested_update_rows(inp.requested_updates),
        "suggested_submit_params": {
            "first_submit": {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {
                    "minwon_type": "전입신고",
                    "delivery_method": "online",
                },
            },
            "linked_address_update": {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {
                    "minwon_type": "주소변경",
                    "delivery_method": "online",
                },
            },
        },
        "citizen_visible_boundary": [
            "이 조회는 실데이터가 아닌 모의 절차 레코드입니다.",
            "전입신고 및 연계 변경은 정부24 또는 관할 기관의 실제 접수 결과가 기준입니다.",
            (
                "자동차/학교/우편물 등 일부 항목은 기관별 별도 확인이나 "
                "추가 동의가 필요할 수 있습니다."
            ),
        ],
        "fetched_at": now,
    }


async def handle(
    inp: Gov24MoveInSequenceInput,
    *,
    delegation_context: object | None = None,
) -> dict[str, Any]:
    """Handle a Gov24 move-in dependent-sequence lookup."""
    delegation_context = delegation_context or inp.delegation_context
    if not isinstance(delegation_context, DelegationContext):
        logger.warning("mock_lookup_module_gov24_movein_sequence: missing delegation context")
        return {
            "kind": "error",
            "reason": "auth_required",
            "message": (
                "DelegationContext with scope 'lookup:gov24.movein' is required "
                "before Gov24 move-in sequence lookup. Call verify first and pass "
                "the returned delegation_context in lookup params."
            ),
            "retryable": False,
        }

    token_scope = delegation_context.token.scope
    if _REQUIRED_SCOPE not in token_scope.split(","):
        logger.warning(
            "mock_lookup_module_gov24_movein_sequence: scope violation "
            "(token_scope=%r required=%r)",
            token_scope,
            _REQUIRED_SCOPE,
        )
        return {
            "kind": "error",
            "reason": "auth_required",
            "message": (
                f"Delegation token scope {token_scope!r} does not grant {_REQUIRED_SCOPE!r}."
            ),
            "retryable": False,
        }

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


MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL = GovAPITool(
    id="mock_lookup_module_gov24_movein_sequence",
    name_ko="정부24 전입신고 연계절차 조회 (Mock — AX 채널 참조 구현)",
    ministry="GOV24",
    category=[
        "정부24",
        "전입신고",
        "이사민원",
        "주소변경",
        "자동차주소",
        "건강보험주소",
        "학교배정",
        "우편물전송",
    ],
    endpoint=_ACTUAL_ENDPOINT,
    auth_type="oauth",
    input_schema=Gov24MoveInSequenceInput,
    output_schema=_Gov24MoveInSequenceOutput,
    llm_description=(
        "Look up the required Gov24 move-in sequence before filing submit calls. "
        "Use this lookup after resolve_location when the citizen asks to move, "
        "file 전입신고, and update linked address records such as 자동차 주소, "
        "건강보험/국민연금 주소, 학교배정, or 우편물 전송. Returns a mock record "
        "that tells the model to submit mock_submit_module_gov24_minwon twice: "
        "first with minwon_type='전입신고', then with minwon_type='주소변경' for "
        "eligible linked records. Requires DelegationContext from "
        "mock_verify_ganpyeon_injeung with scope 'lookup:gov24.movein'. "
        "This is a Mock adapter — no real Gov24 API is called."
    ),
    search_hint=(
        "정부24 전입신고 이사민원 이사 전입 주소변경 주소 일괄 변경 자동차주소 "
        "자동차 등록원부 건강보험 국민연금 학교배정 초등학교 우편물 전송 전입신고플러스 "
        "gov24 move in report address change vehicle health insurance "
        "school assignment mail forwarding"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url=_POLICY_AUTHORITY,
        real_classification_text=(
            "정부24 민원신청/전입신고+ — 행정안전부 공공서비스 포털의 이사 관련 민원 흐름."
        ),
        citizen_facing_gate="login",
        last_verified=datetime(2026, 5, 5, tzinfo=UTC),
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
        "전입신고하고 자동차 주소도 바꿔줘",
        "이사민원 주소변경 한 번에",
        "전입신고 학교배정 건강보험 주소 변경",
        "우편물 전송까지 같이 신청",
    ],
    delegation_source_tool_id="mock_verify_ganpyeon_injeung",
)


def register(registry: object, executor: object) -> None:
    """Register the Gov24 move-in sequence lookup mock."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, Gov24MoveInSequenceInput)
        return await handle(inp, delegation_context=inp.delegation_context)

    registry.register(MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL)
    executor.register_adapter("mock_lookup_module_gov24_movein_sequence", _adapter)
    logger.info(
        "Registered mock tool: mock_lookup_module_gov24_movein_sequence "
        "(login-gated, mock mode, AX-channel reference: %s)",
        _REFERENCE_IMPL,
    )
