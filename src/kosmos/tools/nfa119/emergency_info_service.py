# SPDX-License-Identifier: Apache-2.0
"""NFA (소방청) 구급정보서비스 adapter — live HTTP handler.

Calls the NFA EmergencyInformationService endpoint for historical, anonymized
EMS statistics by region, fire station, and report year-month.

Wire param research: specs/2522-tool-surface-v4/research-nfa-wire.md

Key wire param rules (NIA-IFT guide v1.0):
  - Base URL: https://apis.data.go.kr/1661000/EmergencyInformationService
  - Sub-endpoint suffix: /<operation> — mandatory, e.g. /getEmgencyActivityInfo
  - Year-month wire param: ``gutYm`` for getEmgencyActivityInfo, ``stmtYm`` for all others
  - getEmgVehicleInfo: no ym param (vehicle registry snapshot, not time-series)
  - resultType=json (capital T, lowercase value)
  - pageNo / numOfRows (camelCase)

Response shape (live API observed 2026-05-03, Variant C — flat, no "response" wrapper):
  {"header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
   "numOfRows": N, "pageNo": N, "totalCount": N,
   "body": {"items": [...]}}
  This differs from other data.go.kr APIs that wrap in "response.body".
  _parse_response() and _parse_items() detect and handle both shapes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, cast

import httpx
from pydantic import (  # noqa: F401 (RootModel kept for compat)
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
)

from kosmos.tools._description_template import build_description_v4
from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ConfigurationError, ToolExecutionError, _require_env
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.nfa119._short_references import NFA_HQ_SHORT_REFERENCE

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/1661000/EmergencyInformationService"

# ---------------------------------------------------------------------------
# T010 — NFA operation enum + input schema
# ---------------------------------------------------------------------------


class NfaEmgOperation(StrEnum):
    """Sub-endpoint selector for EmergencyInformationService."""

    activity = "getEmgencyActivityInfo"  # 구급활동정보 (default)
    transfer = "getEmgPatientTransferInfo"  # 구급환자이송정보
    condition = "getEmgPatientConditionInfo"  # 구급환자상태정보
    firstaid = "getEmgPatientFirstaidInfo"  # 구급환자응급처치정보
    vehicle_dispatch = "getEmgVehicleDispatchInfo"  # 구급차량출동정보
    vehicle_info = "getEmgVehicleInfo"  # 구급차량정보


class NfaEmergencyInfoServiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: NfaEmgOperation = Field(
        default=NfaEmgOperation.activity,
        description=(
            "Which emergency-info sub-endpoint to query. "
            "Pass the NfaEmgOperation enum value string directly. "
            "Default 'getEmgencyActivityInfo' returns dispatch distance, patient "
            "symptoms, and crew qualifications — the most citizen-relevant view. "
            "Use 'getEmgPatientTransferInfo' for patient transport, "
            "'getEmgPatientConditionInfo' for vitals, "
            "'getEmgPatientFirstaidInfo' for treatment codes, "
            "'getEmgVehicleDispatchInfo' or 'getEmgVehicleInfo' for fleet data."
        ),
    )
    sido_hq_ogid_nm: str | None = Field(
        default=None,
        max_length=22,
        description=(
            "Regional fire headquarters name (시도본부). Example: "
            "'서울소방재난본부', '충청남도소방본부', '경기도소방재난본부'. "
            "Optional — omit to query all regions (may return a large result set)."
        ),
    )
    rsac_gut_fstt_ogid_nm: str = Field(
        max_length=7,
        description=(
            "Fire station name (출동소방서). Required. "
            "Example: '공주소방서', '파주소방서', '은평소방서'. "
            "Must be a valid NFA station name — do not guess. "
            "Use nfa_safety_center_lookup (future) or ask the citizen."
        ),
    )
    stmt_ym: str = Field(
        pattern=r"^\d{6}$",
        description=(
            "Report year-month in YYYYMM format (신고년월 or 출동년월). "
            "Example: '202101' for January 2021. Required for all operations. "
            "Do not use future dates."
        ),
    )
    page_no: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed). Default 1.",
    )
    num_of_rows: int = Field(
        default=10,
        ge=1,
        le=100,
        description=("Number of records per page. Default 10, maximum 100 per NFA API contract."),
    )
    result_type: Literal["json"] = Field(
        default="json",
        description=(
            "Response format. Fixed to 'json' — the adapter's Content-Type guard "
            "requires JSON to be requested. Do not override."
        ),
    )


# ---------------------------------------------------------------------------
# T011 — Per-operation output item models + envelope
# ---------------------------------------------------------------------------


class NfaActivityItem(BaseModel):
    """Single 구급활동정보 record (getEmgencyActivityInfo)."""

    model_config = ConfigDict(extra="allow", frozen=True)

    sidoHqOgidNm: str = Field(description="시도본부 (regional HQ name)")  # noqa: N815
    rsacGutFsttOgidNm: str = Field(description="출동소방서 (fire station name)")  # noqa: N815
    gutYm: str = Field(description="출동년월 YYYYMM")  # noqa: N815
    gutHh: str | None = Field(default=None, description="출동시 HH (dispatch hour)")  # noqa: N815
    sptMvmnDtc: str | None = Field(default=None, description="현장과의거리 (metres)")  # noqa: N815
    ptntAge: str | None = Field(default=None, description="환자연령 bracket (e.g. '60~69세')")  # noqa: N815
    ptntSdtSeCdNm: str | None = Field(default=None, description="환자성별 (남/여)")  # noqa: N815
    egrcSidoCdNm: str | None = Field(default=None, description="긴급구조시")  # noqa: N815
    egrcSiggCdNm: str | None = Field(default=None, description="긴급구조구")  # noqa: N815
    ruptOccrPlcCdNm: str | None = Field(default=None, description="구급사고발생장소")  # noqa: N815
    ruptSptmCdNm: str | None = Field(default=None, description="환자증상")  # noqa: N815
    rcptPathCdNm: str | None = Field(default=None, description="접수경로")  # noqa: N815
    cptcSeCdNm: str | None = Field(default=None, description="관할구분")  # noqa: N815
    frnrAt: str | None = Field(default=None, description="외국인여부 Y/N")  # noqa: N815
    emtpQlcClCd1Nm: str | None = Field(default=None, description="구급대원1 자격")  # noqa: N815
    emtpQlcClCd2Nm: str | None = Field(default=None, description="구급대원2 자격")  # noqa: N815
    emtpQlcClCd3Nm: str | None = Field(default=None, description="운전요원 자격")  # noqa: N815


class NfaTransferItem(BaseModel):
    """Single 구급환자이송정보 record (getEmgPatientTransferInfo)."""

    model_config = ConfigDict(extra="allow", frozen=True)

    sidoHqOgidNm: str  # noqa: N815
    rsacGutFsttOgidNm: str  # noqa: N815
    stmtYm: str  # noqa: N815
    stmtHh: str | None = None  # noqa: N815
    rlifAcdAsmCdNm: str | None = Field(default=None, description="구급사고유형")  # noqa: N815
    ptntAge: str | None = None  # noqa: N815
    ptntSdtSeCdNm: str | None = Field(default=None, description="환자성별")  # noqa: N815
    frnrAt: str | None = Field(default=None, description="내외국인")  # noqa: N815
    ptntTyCdNm: str | None = Field(default=None, description="환자유형")  # noqa: N815
    ruptOccrPlcCdNm: str | None = Field(default=None, description="구급사고발생장소")  # noqa: N815
    rlifOccrTyCdNm: str | None = Field(default=None, description="발생유형")  # noqa: N815
    anmlInctCdNm: str | None = Field(default=None, description="동물곤충원인")  # noqa: N815
    wmhtDamgCdNm: str | None = Field(default=None, description="온열손상")  # noqa: N815


class NfaConditionItem(BaseModel):
    """Single 구급환자상태정보 record (getEmgPatientConditionInfo)."""

    model_config = ConfigDict(extra="allow", frozen=True)

    ruptSptmCdNm: str = Field(description="환자증상")  # noqa: N815
    sidoHqOgidNm: str  # noqa: N815
    rsacGutFsttOgidNm: str  # noqa: N815
    stmtYm: str  # noqa: N815
    stmtHh: str | None = None  # noqa: N815
    ptntAge: str | None = None  # noqa: N815
    lwsBpsr: str | None = Field(default=None, description="최저혈압")  # noqa: N815
    topBpsr: str | None = Field(default=None, description="최고혈압")  # noqa: N815
    ptntHbco: str | None = Field(default=None, description="심박수")  # noqa: N815
    ptntBfco: str | None = Field(default=None, description="호흡수")  # noqa: N815
    ptntOsv: str | None = Field(default=None, description="산소포화도")  # noqa: N815
    ptntBht: str | None = Field(default=None, description="체온")  # noqa: N815


class NfaFirstaidItem(BaseModel):
    """Single 구급환자응급처치정보 record (getEmgPatientFirstaidInfo)."""

    model_config = ConfigDict(extra="allow", frozen=True)

    sidoHqOgidNm: str  # noqa: N815
    rsacGutFsttOgidNm: str  # noqa: N815
    stmtYm: str  # noqa: N815
    stmtHh: str | None = None  # noqa: N815
    ptntAge: str | None = None  # noqa: N815
    ptntSdtSeCdNm: str | None = None  # noqa: N815
    fstaCdNm: str | None = Field(default=None, description="응급처치코드")  # noqa: N815


class NfaVehicleDispatchItem(BaseModel):
    """Single 구급차량출동정보 record (getEmgVehicleDispatchInfo)."""

    model_config = ConfigDict(extra="allow", frozen=True)

    sidoHqOgidNm: str  # noqa: N815
    rsacGutFsttOgidNm: str  # noqa: N815
    stmtYm: str  # noqa: N815
    stmtHh: str | None = None  # noqa: N815
    vctpCdNm: str = Field(description="차종코드명")  # noqa: N815
    vhclSeCd: str | None = Field(default=None, description="차량구분")  # noqa: N815
    vhclNo: str | None = Field(default=None, description="차량번호")  # noqa: N815
    vhclStatCdNm: str | None = Field(default=None, description="차량상태")  # noqa: N815
    gotFrmtAt: str | None = Field(default=None, description="출동대편성여부 Y/N")  # noqa: N815
    vhcn: str | None = Field(default=None, description="차량명")  # noqa: N815
    vhclGrCdNm: str | None = Field(default=None, description="차량그룹코드명")  # noqa: N815
    mnm: str | None = Field(default=None, description="제작사")
    mdnm: str | None = Field(default=None, description="기종명")
    gutPcnt: str | None = Field(default=None, description="출동인원수")  # noqa: N815
    tnkCpct: str | None = Field(default=None, description="탱크용량")  # noqa: N815
    gutOdr: str | None = Field(default=None, description="출동차수")  # noqa: N815


class NfaVehicleInfoItem(BaseModel):
    """Single 구급차량정보 record (getEmgVehicleInfo)."""

    model_config = ConfigDict(extra="allow", frozen=True)

    sidoHqOgidNm: str  # noqa: N815
    rsacGutFsttOgidNm: str = Field(description="소방서")  # noqa: N815
    vhclSeCd: str | None = Field(default=None, description="차량구분")  # noqa: N815
    vhclNo: str | None = Field(default=None, description="차량번호")  # noqa: N815
    vctpCdNm: str | None = Field(default=None, description="차종코드명")  # noqa: N815
    vhclStatCdNm: str | None = Field(default=None, description="차량상태코드명")  # noqa: N815
    gotFrmtAt: str | None = Field(default=None, description="출동대편성여부")  # noqa: N815
    vhcn: str | None = Field(default=None, description="차량명")  # noqa: N815
    vhclGrCdNm: str | None = Field(default=None, description="차량그룹코드명")  # noqa: N815
    mnm: str | None = Field(default=None, description="제작사")
    mdnm: str | None = Field(default=None, description="기종명")
    bdgPcnt: str | None = Field(default=None, description="탑승인원수")  # noqa: N815
    tnkCpct: str | None = Field(default=None, description="탱크용량")  # noqa: N815
    stde: str | None = Field(default=None, description="기준일자 YYYYMMDD")


NfaItem = (
    NfaActivityItem
    | NfaTransferItem
    | NfaConditionItem
    | NfaFirstaidItem
    | NfaVehicleDispatchItem
    | NfaVehicleInfoItem
)


class NfaEmergencyInfoServiceOutput(BaseModel):
    """Normalized upstream response wrapper for EmergencyInformationService."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str = Field(description="Queried operation path (e.g. 'getEmgencyActivityInfo').")
    result_code: str = Field(description="API resultCode ('00' = NORMAL SERVICE).")
    result_msg: str = Field(description="API resultMsg.")
    page_no: int
    num_of_rows: int
    total_count: int
    items: list[NfaItem] = Field(
        description=(
            "List of emergency-info records. Empty list when no records match. "
            "Item schema depends on the 'operation' discriminator."
        ),
    )


# ---------------------------------------------------------------------------
# T012 — Wire param builder + response parser
# ---------------------------------------------------------------------------

_ACTIVITY_OP = NfaEmgOperation.activity.value  # "getEmgencyActivityInfo"
_VEHICLE_INFO_OP = NfaEmgOperation.vehicle_info.value  # "getEmgVehicleInfo"


def _build_params(inp: NfaEmergencyInfoServiceInput, api_key: str) -> dict[str, str | int]:
    """Build the wire query parameter dict for the given operation.

    Wire rules (NIA-IFT guide, research-nfa-wire.md):
    - getEmgencyActivityInfo: year-month wire param = ``gutYm`` (출동년월)
    - all others: year-month wire param = ``stmtYm`` (신고년월)
    - getEmgVehicleInfo: no ym param (vehicle registry snapshot)
    """
    params: dict[str, str | int] = {
        "serviceKey": api_key,
        "pageNo": inp.page_no,
        "numOfRows": inp.num_of_rows,
        "resultType": inp.result_type,
        "rsacGutFsttOgidNm": inp.rsac_gut_fstt_ogid_nm,
    }

    if inp.sido_hq_ogid_nm is not None:
        params["sidoHqOgidNm"] = inp.sido_hq_ogid_nm

    op = inp.operation.value
    if op == _ACTIVITY_OP:
        params["gutYm"] = inp.stmt_ym
    elif op != _VEHICLE_INFO_OP:
        # transfer / condition / firstaid / vehicle_dispatch: use stmtYm
        params["stmtYm"] = inp.stmt_ym
    # vehicle_info: no ym param (vehicle registry, not time-series)

    return params


def _parse_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract item list from data.go.kr response envelope.

    Supports three JSON shapes produced by data.go.kr:
    Shape A (wrapped): ``response.body.items`` is a direct list.
    Shape B (XML-to-JSON): ``response.body.items.item`` is a list or single dict.
    Shape C (NFA flat): top-level ``body.items`` list (no ``response`` wrapper).

    Also normalises the single-item-as-dict quirk in shape B.
    """
    # Shape C — NFA flat (live API observed 2026-05-03):
    # {"header": {...}, "numOfRows": N, "pageNo": N, "totalCount": N,
    #  "body": {"items": [...]}}
    if "response" not in payload and "body" in payload:
        body_c = payload.get("body") or {}
        items_c = body_c.get("items") if isinstance(body_c, dict) else None
        if items_c is None:
            return []
        if isinstance(items_c, list):
            return items_c
        if isinstance(items_c, dict):
            raw = items_c.get("item")
            if raw is None:
                return []
            if isinstance(raw, dict):
                return [raw]
            if isinstance(raw, list):
                return raw
        return []

    try:
        response_body = payload["response"]
        body = response_body.get("body", {}) or {}
        items_val = body.get("items")
        if items_val is None:
            return []
        # Shape A: items is a list directly
        if isinstance(items_val, list):
            return items_val
        # Shape B: items is a dict wrapping an "item" key
        if isinstance(items_val, dict):
            raw = items_val.get("item")
            if raw is None:
                return []
            if isinstance(raw, dict):
                return [raw]
            if isinstance(raw, list):
                return raw
    except (KeyError, TypeError):
        pass
    return []


def _parse_response(
    payload: dict[str, Any],
    operation: str,
) -> NfaEmergencyInfoServiceOutput:
    """Parse raw JSON response dict into NfaEmergencyInfoServiceOutput.

    Supports three JSON layout variants from data.go.kr:
    - Variant A (wrapped): pageNo/numOfRows/totalCount inside ``response.body``
    - Variant B (alternate): pageNo/numOfRows/totalCount at ``response`` level
    - Variant C (NFA flat, live API observed 2026-05-03):
        top-level ``header`` + ``pageNo``/``numOfRows``/``totalCount`` + ``body.items``
        (no ``response`` wrapper; confirmed via live curl: resultType=json returns this shape)

    Raises:
        ToolExecutionError: On resultCode != "00" or missing header.
    """
    try:
        # Variant C — NFA flat (no "response" wrapper)
        if "response" not in payload and "header" in payload:
            header = payload["header"]
            result_code: str = str(header["resultCode"])
            result_msg: str = str(header.get("resultMsg", ""))
            page_no: int = int(payload.get("pageNo") or 1)
            num_of_rows: int = int(payload.get("numOfRows") or 10)
            total_count: int = int(payload.get("totalCount") or 0)
        else:
            resp = payload["response"]
            header = resp["header"]
            result_code = str(header["resultCode"])
            result_msg = str(header.get("resultMsg", ""))
            # Variant A: pagination fields inside body
            body = resp.get("body", {}) or {}
            page_no = int(body.get("pageNo") or resp.get("pageNo") or 1)
            num_of_rows = int(body.get("numOfRows") or resp.get("numOfRows") or 10)
            total_count = int(body.get("totalCount") or resp.get("totalCount") or 0)
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolExecutionError(
            tool_id="nfa_emergency_info_service",
            message=f"Unexpected response shape from NFA API: {exc}",
        ) from exc

    if result_code != "00":
        raise ToolExecutionError(
            tool_id="nfa_emergency_info_service",
            message=(
                f"NFA API error resultCode={result_code!r} resultMsg={result_msg!r}. "
                "Check rsacGutFsttOgidNm (max 7 chars), stmt_ym format, and serviceKey."
            ),
        )

    raw_items = _parse_items(payload)

    # Parse each item with operation-specific model (extra="allow" tolerates drift)
    _model_map: dict[str, type[BaseModel]] = {
        NfaEmgOperation.activity.value: NfaActivityItem,
        NfaEmgOperation.transfer.value: NfaTransferItem,
        NfaEmgOperation.condition.value: NfaConditionItem,
        NfaEmgOperation.firstaid.value: NfaFirstaidItem,
        NfaEmgOperation.vehicle_dispatch.value: NfaVehicleDispatchItem,
        NfaEmgOperation.vehicle_info.value: NfaVehicleInfoItem,
    }
    item_model = _model_map.get(operation, NfaActivityItem)
    parsed_items: list[NfaItem] = [
        cast("NfaItem", item_model.model_validate(raw)) for raw in raw_items
    ]

    return NfaEmergencyInfoServiceOutput(
        operation=operation,
        result_code=result_code,
        result_msg=result_msg,
        page_no=page_no,
        num_of_rows=num_of_rows,
        total_count=total_count,
        items=parsed_items,
    )


# ---------------------------------------------------------------------------
# T031 — Live HTTP handle()
# ---------------------------------------------------------------------------


async def handle(
    inp: NfaEmergencyInfoServiceInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Query the NFA EmergencyInformationService endpoint.

    Args:
        inp: Validated input parameters.
        client: Optional injected ``httpx.AsyncClient`` (for testing).

    Returns:
        A plain dict matching ``NfaEmergencyInfoServiceOutput`` field names.

    Raises:
        ConfigurationError: If ``KOSMOS_DATA_GO_KR_API_KEY`` is not set.
        ToolExecutionError: On HTTP errors, unexpected response shapes, or API error codes.
    """
    api_key = _require_env("KOSMOS_DATA_GO_KR_API_KEY")

    operation = inp.operation.value
    url = f"{_BASE_URL}/{operation}"
    query_params = _build_params(inp, api_key)

    logger.debug(
        "NFA request: operation=%s station=%s ym=%s page=%d",
        operation,
        inp.rsac_gut_fstt_ogid_nm,
        inp.stmt_ym,
        inp.page_no,
    )

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=30.0)

    try:
        assert client is not None  # noqa: S101
        response = await client.get(url, params=query_params)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower():
            raise ToolExecutionError(
                tool_id="nfa_emergency_info_service",
                message=(
                    f"Unexpected XML response from NFA API (content-type={content_type!r}). "
                    "Check serviceKey validity and resultType=json param."
                ),
            )

        payload: dict[str, Any] = response.json()
        output = _parse_response(payload, operation)

        logger.info(
            "NFA %s: station=%s ym=%s total=%d page=%d/%d",
            operation,
            inp.rsac_gut_fstt_ogid_nm,
            inp.stmt_ym,
            output.total_count,
            output.page_no,
            output.num_of_rows,
        )
        return output.model_dump()

    except (ToolExecutionError, ConfigurationError):
        raise
    except httpx.HTTPStatusError as exc:
        raise ToolExecutionError(
            tool_id="nfa_emergency_info_service",
            message=f"HTTP {exc.response.status_code} from NFA API: {exc}",
        ) from exc
    except httpx.RequestError as exc:
        raise ToolExecutionError(
            tool_id="nfa_emergency_info_service",
            message=f"Network error calling NFA API: {exc}",
        ) from exc
    finally:
        if own_client and client is not None:
            await client.aclose()


# ---------------------------------------------------------------------------
# T032 — GovAPITool registration with build_description_v4 5-section
# ---------------------------------------------------------------------------

NFA_EMERGENCY_INFO_SERVICE_TOOL = GovAPITool(
    id="nfa_emergency_info_service",
    name_ko="소방청 구급정보서비스 (구급활동 통계 조회)",
    ministry="NFA",
    category=["안전", "응급", "소방", "119", "구급통계"],
    endpoint="https://apis.data.go.kr/1661000/EmergencyInformationService",
    auth_type="api_key",
    input_schema=NfaEmergencyInfoServiceInput,
    output_schema=NfaEmergencyInfoServiceOutput,
    llm_description=build_description_v4(
        purpose=(
            "소방청(NFA) 구급정보서비스 — 시도본부·출동소방서·신고년월 기준으로 "
            "구급활동/이송/상태/처치/차량 통계를 조회. "
            "실시간 출동 조회 불가 — 월별 익명화 통계만 제공."
        ),
        input_quirk=(
            "rsac_gut_fstt_ogid_nm(필수,7자이내), stmt_ym(YYYYMM필수), "
            "operation(기본=getEmgencyActivityInfo). "
            "소방서명 확실히 알 때만 호출 — 추측 금지."
        ),
        short_reference=(f"[시도본부 17개] {NFA_HQ_SHORT_REFERENCE}"),
        domain_quirk=(
            "wire URL = base/operation(suffix필수). "
            "activity는 gutYm, 나머지는 stmtYm. "
            "vehicle_info는 ym파라미터 없음(차량 registry). "
            "resultType=json 고정."
        ),
        self_contained_decl=(
            "이 도구는 자립적(self-contained). 다른 도구 호출 불필요. "
            "소방서명 모를 경우 시민에게 직접 질문."
        ),
    ),
    search_hint=(
        "119 구급 출동 소방청 구급정보 구급활동 구급차 통계 현황 소방서 긴급구조 "
        "119 NFA emergency ambulance dispatch activity statistics fire station Korea"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.nfa.go.kr/nfa/main/contents.do?menuKey=66",
        real_classification_text="소방청 공공데이터 이용약관 — 119 응급서비스 데이터 비상업적 공공 이용 허가",
        citizen_facing_gate="login",  # api_key auth_type — requires serviceKey credential (AAL2)
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=86400,
    rate_limit_per_minute=10,
    is_core=False,
    primitive="lookup",
    trigger_examples=[
        "심정지 응급 처치",
        "AED 위치 알려줘",
    ],
)


def register(registry: object, executor: object) -> None:
    """Register the NFA emergency info service tool and its adapter.

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
        assert isinstance(inp, NfaEmergencyInfoServiceInput)
        return await handle(inp)

    registry.register(NFA_EMERGENCY_INFO_SERVICE_TOOL)
    executor.register_adapter("nfa_emergency_info_service", _adapter)
    logger.info("Registered tool: nfa_emergency_info_service (live HTTP handler)")
