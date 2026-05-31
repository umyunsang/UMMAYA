# SPDX-License-Identifier: Apache-2.0
"""KMA APIHub non-structured URL operation catalog.

These endpoints are official KMA APIHub surfaces, but they are not
``typ02/openApi`` operations and do not share the structured XML/JSON envelope.
Keep them in a separate catalog so text, image, and binary response contracts do
not contaminate the structured OpenAPI wrapper.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

type KmaApiHubUrlScalar = str | int | float | bool | None
type KmaApiHubUrlApprovalState = Literal["approved", "approval_pending"]
type KmaApiHubUrlResponseKind = Literal["text", "image", "binary"]


class KmaApiHubUrlParam(BaseModel):
    """Official request parameter metadata for one APIHub URL operation."""

    model_config = ConfigDict(frozen=True)

    name: str
    field_name: str
    required: bool = True
    default: KmaApiHubUrlScalar = None
    value_type: Literal["string", "integer", "number", "boolean"] = "string"
    is_credential: bool = False


class KmaApiHubUrlOperation(BaseModel):
    """One official non-structured KMA APIHub URL operation."""

    model_config = ConfigDict(frozen=True)

    operation_id: str
    category_seq: int
    category_name_ko: str
    title_ko: str
    endpoint_path: str
    request_params: tuple[KmaApiHubUrlParam, ...]
    response_kind: KmaApiHubUrlResponseKind
    approval_state: KmaApiHubUrlApprovalState = "approval_pending"
    purpose: str
    selection_rule: str
    search_keywords: str
    official_page_url: str

    @property
    def tool_id(self) -> str:
        """Return the stable UMMAYA tool id for this URL operation."""
        return f"kma_apihub_url_{self.operation_id}"

    @property
    def non_credential_params(self) -> tuple[KmaApiHubUrlParam, ...]:
        """Return request parameters that are safe for model/user input."""
        return tuple(param for param in self.request_params if not param.is_credential)


def _snake(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return value.strip("_").lower()


def _value_type(value: KmaApiHubUrlScalar) -> Literal["string", "integer", "number", "boolean"]:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def _param(
    name: str,
    default: KmaApiHubUrlScalar,
    *,
    required: bool = True,
    value_type: Literal["string", "integer", "number", "boolean"] | None = None,
) -> KmaApiHubUrlParam:
    is_credential = name == "authKey"
    return KmaApiHubUrlParam(
        name=name,
        field_name=_snake(name),
        required=False if is_credential else required,
        default=None if is_credential else default,
        value_type=value_type or _value_type(default),
        is_credential=is_credential,
    )


KMA_APIHUB_URL_OPERATIONS: tuple[KmaApiHubUrlOperation, ...] = (
    KmaApiHubUrlOperation(
        operation_id="air_metar_decoded",
        category_seq=14,
        category_name_ko="항공기상",
        title_ko="기상청 METAR 해독자료",
        endpoint_path="/api/typ01/url/air_metar_dec.php",
        request_params=(
            _param("tm", None, required=False),
            _param("org", "K"),
            _param("help", 1),
            _param("authKey", None, required=False),
        ),
        response_kind="text",
        approval_state="approved",
        purpose=(
            "Fetch official KMA decoded METAR/SPECI aviation weather text. "
            "This is the approved APIHub URL product for the Korean METAR "
            "decoded-data channel."
        ),
        selection_rule=(
            "Choose this for METAR decoded-data requests and as the primary "
            "fallback when the structured AmmIwxxmService/getMetar endpoint "
            "returns APIHub APPLICATION_ERROR. It returns KMA decoded text "
            "for the requested time slot, not the structured IWXXM envelope. "
            "The normalized summary identifies known airport stations: station "
            "153 is Gimhae Airport / RKPK, station 110 is Gimpo Airport / RKSS. "
            "Use decoded_records[].safe_weather only for weather values; never "
            "derive values from raw_fields or raw_report. If a wind cardinal "
            "label is needed, use safe_weather.wind.direction_from_cardinal_ko "
            "or direction_from_cardinal_en; do not infer your own label from "
            "degrees."
        ),
        search_keywords=(
            "METAR SPECI 해독자료 항공기상전문 공항기상 항공 실황 "
            "비행기 항공편 비행편 운항 이륙 착륙 결항 지연 시정 "
            "air_metar_dec decoded aviation weather flight takeoff landing delay"
        ),
        official_page_url="https://apihub.kma.go.kr/apiList.do?seqApi=14",
    ),
    KmaApiHubUrlOperation(
        operation_id="air_amos_minute",
        category_seq=14,
        category_name_ko="항공기상",
        title_ko="기상청 AMOS 매분자료 조회",
        endpoint_path="/api/typ01/url/amos.php",
        request_params=(
            _param("tm", None, required=False),
            _param("dtm", 60),
            _param("stn", None),
            _param("help", 1),
            _param("authKey", None, required=False),
        ),
        response_kind="text",
        approval_state="approved",
        purpose=(
            "Fetch official AMOS minute observations for supported airports. "
            "AMOS reports runway-area aviation weather such as visibility, RVR, "
            "cloud height, temperature, humidity, pressure, rain, and wind."
        ),
        selection_rule=(
            "Choose this for supported-airport runway-area current conditions or "
            "AMOS requests. It covers official AMOS stations such as 110 Gimpo, "
            "but the official APIHub station list does not include Gimhae. "
            "Do not use AMOS for Gimhae; 182 is Jeju, not Gimhae. Use METAR "
            "RKPK for Gimhae aviation weather."
        ),
        search_keywords=(
            "AMOS 공항기상관측 매분자료 활주로 기상실황 김포공항 stn110 "
            "비행기 항공편 운항 이륙 착륙 결항 지연 "
            "airport runway minute observation visibility RVR wind flight delay"
        ),
        official_page_url=(
            "https://apihub.kma.go.kr/apiList.do?apiMov=%EA%B8%B0%EC%83%81%EC%B2%AD+"
            "AMOS+%EB%A7%A4%EB%B6%84%EC%9E%90%EB%A3%8C+%EC%A1%B0%ED%9A%8C&seqApi=14&seqApiSub=259"
        ),
    ),
    KmaApiHubUrlOperation(
        operation_id="high_resolution_grid_point",
        category_seq=971,
        category_name_ko="융합기상",
        title_ko="고해상도 격자자료 특정지점 다중요소 조회",
        endpoint_path="/api/typ01/url/sfc_nc_var.php",
        request_params=(
            _param("tm1", None, required=False),
            _param("tm2", None, required=False),
            _param("obs", "ta,td,hm,ws_10m,wd_10m,vs,rn_60m"),
            _param("itv", 10),
            _param("lon", None, value_type="number"),
            _param("lat", None, value_type="number"),
            _param("help", 1),
            _param("authKey", None, required=False),
        ),
        response_kind="text",
        approval_state="approved",
        purpose=(
            "Fetch KMA 500m high-resolution analyzed grid values for one "
            "latitude/longitude point. The product applies objective analysis "
            "to KMA and public-agency observations with terrain effects."
        ),
        selection_rule=(
            "Choose this when a citizen asks for analyzed weather values at a "
            "coordinate or when point observations are sparse. It complements, "
            "not replaces, official airport METAR/AMOS for flight safety wording. "
            "After locate returns coordinates, call this tool with lat/lon instead "
            "of switching to current-observation or forecast adapters."
        ),
        search_keywords=(
            "고해상도 격자자료 분석자료 객관분석 500m 특정지점 다중요소 "
            "기온 습도 풍속 풍향 시정 objective analysis grid point lat lon 융합기상"
        ),
        official_page_url=(
            "https://apihub.kma.go.kr/apiList.do?apiMov=1.+%EA%B3%A0%ED%95%B4%EC%83%81%EB%8F%84+"
            "%EA%B2%A9%EC%9E%90%EC%9E%90%EB%A3%8C+%EC%A1%B0%ED%9A%8C%28%ED%95%B4%EC%83%81%EB%8F%84%3A+500m%29"
            "&seqApi=971&seqApiSub=936"
        ),
    ),
    KmaApiHubUrlOperation(
        operation_id="aws_objective_analysis_grid",
        category_seq=2,
        category_name_ko="지상관측",
        title_ko="AWS 객관분석 격자자료 조회",
        endpoint_path="/api/typ01/cgi-bin/aws/nph-aws_min_obj",
        request_params=(
            _param("obs", "ta"),
            _param("tm", None, required=False),
            _param("obj", "mq"),
            _param("map", "D3"),
            _param("grid", 1),
            _param("stn", 0),
            _param("gov", "", required=False),
            _param("authKey", None, required=False),
        ),
        response_kind="text",
        approval_state="approved",
        purpose=(
            "Fetch AWS objective-analysis grid data produced from automatic "
            "weather-station observations."
        ),
        selection_rule=(
            "Choose this for AWS objective-analysis grid products, not for a "
            "single airport METAR or ordinary address forecast."
        ),
        search_keywords=(
            "AWS 객관분석 격자자료 분석자료 objective analysis grid Multi Quadric Barnes"
        ),
        official_page_url=(
            "https://apihub.kma.go.kr/apiList.do?apiMov=AWS%20%EA%B0%9D%EA%B4%80%EB%B6%84%EC%84%9D"
            "&seqApi=2&seqApiSub=248"
        ),
    ),
    KmaApiHubUrlOperation(
        operation_id="analysis_weather_chart_image",
        category_seq=9,
        category_name_ko="수치모델",
        title_ko="분석일기도 이미지 조회",
        endpoint_path="/api/typ07/afsiwa/iwa/api/iwaImgUrlApi/retRecreateImgUrl.kfrm",
        request_params=(
            _param("analTime", None),
            _param("isTyp", "false"),
            _param("imageType", "png"),
            _param("groupName", "925_default"),
            _param("meta", 1),
            _param("authKey", None, required=False),
        ),
        response_kind="image",
        approval_state="approved",
        purpose=("Fetch KMA analyzed weather-chart imagery or metadata for a UTC analysis time."),
        selection_rule=(
            "Choose this for analyzed weather charts or synoptic chart images. "
            "It is not a tabular airport-weather observation source. "
            "For WthrChartInfoService/getSurfaceChart wording, the structured "
            "service is cataloged-disabled after resultCode=99 probes; this URL "
            "image product uses anal_time, not code. Use anal_time, not code. "
            "anal_time is UTC YYYYMMDDHHMM; include minutes and convert from KST "
            "instead of sending a 10-digit local hour."
        ),
        search_keywords=(
            "분석일기도 일기도 이미지 수치모델 분석자료 synoptic chart image analTime"
        ),
        official_page_url=(
            "https://apihub.kma.go.kr/apiList.do?apiMov=1.+%28%EA%B7%B8%EB%9E%98%ED%94%BD%29+"
            "%EB%B6%84%EC%84%9D%EC%9D%BC%EA%B8%B0%EB%8F%84+%EC%A1%B0%ED%9A%8C&seqApi=9&seqApiSub=285"
        ),
    ),
)


def iter_url_operations() -> tuple[KmaApiHubUrlOperation, ...]:
    """Return all cataloged non-structured URL operations."""
    return KMA_APIHUB_URL_OPERATIONS


def get_url_operation_by_id(operation_id: str) -> KmaApiHubUrlOperation:
    """Return one URL operation by stable operation id."""
    for operation in KMA_APIHUB_URL_OPERATIONS:
        if operation.operation_id == operation_id:
            return operation
    raise KeyError(f"Unknown KMA APIHub URL operation: {operation_id}")
