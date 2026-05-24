# SPDX-License-Identifier: Apache-2.0
"""Generic wrappers for KMA APIHub structured ``typ02/openApi`` operations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from functools import cache
from typing import Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, create_model

from ummaya.tools._outbound_trace import traced_async_client
from ummaya.tools.errors import ConfigurationError, ToolExecutionError
from ummaya.tools.executor import AdapterFn, ToolExecutor
from ummaya.tools.kma.apihub_catalog import (
    KmaApiHubOperation,
    get_operation_by_id,
    iter_structured_operations,
)
from ummaya.tools.kma.apihub_endpoint import KMA_API_HUB_BASE_URL, resolve_apihub_endpoint
from ummaya.tools.kma.response_payload import (
    KmaPayloadDecodeError,
    decode_response_payload,
    summarize_http_status_error,
)
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

type KmaApiHubQueryValue = str | int | float | bool


class KmaApiHubStructuredOutput(BaseModel):
    """Normalized output from one KMA APIHub structured operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: str
    service: str
    operation: str
    result_code: str | None = None
    result_msg: str | None = None
    page_no: int | None = None
    num_of_rows: int | None = None
    total_count: int | None = None
    items: list[dict[str, object]]
    raw_format: Literal["json", "xml", "text_error"]


def _field_type(param_type: str) -> type[str] | type[int] | type[float] | type[bool]:
    if param_type == "integer":
        return int
    if param_type == "number":
        return float
    if param_type == "boolean":
        return bool
    return str


def _model_name(operation: KmaApiHubOperation) -> str:
    parts = [
        part
        for part in operation.tool_id.removeprefix("kma_apihub_").split("_")
        if part and part != "2" and part != "0"
    ]
    return "KmaApiHub" + "".join(part.title() for part in parts) + "Input"


_DYNAMIC_TIME_PARAMS = frozenset(
    {
        "fromTmFc",
        "toTmFc",
        "dateTime",
        "tm",
        "baseTime",
        # VilageFcstInfoService_2.0 uses snake_case official parameter names.
        "base_date",
        "base_time",
        "basedatetime",
    }
)

_PARAM_DESCRIPTIONS: dict[str, str] = {
    "pageNo": "Page number, 1-based. Use the default unless the citizen asks for another page.",
    "numOfRows": "Number of rows to return. Use the default unless more rows are needed.",
    "dataType": (
        "Response format requested from KMA APIHub. XML is the official sample/default; "
        "JSON may be used only when the operation supports it."
    ),
    "fromTmFc": (
        "Earthquake/volcano bulletin announcement start date, YYYYMMDD. "
        "Use a recent KST date; APIHub returns an error for ranges outside "
        "the current 3 days window."
    ),
    "toTmFc": (
        "Earthquake/volcano bulletin announcement end date, YYYYMMDD. "
        "Keep the range within the current 3 days window and do not use "
        "stale catalog sample dates."
    ),
    "dateTime": (
        "KMA satellite/radar observation datetime, YYYYMMDDHHMM. Use a recent "
        "KST observation; APIHub returns an error outside the current 2 days "
        "window for these satellite products."
    ),
    "resultType": (
        "KMA product/result code for this satellite, radar, or model product. "
        "Keep the catalog default unless the citizen names a product code."
    ),
    "dongCode": (
        "Administrative area code for area-scoped KMA products. Use only for "
        "Area operations, not All operations."
    ),
    "tm": (
        "GTS world weather observation datetime, YYYYMMDDHHMM. Use a recent "
        "KST/UTC-aligned observation; APIHub returns an error outside the "
        "current 1 day window."
    ),
    "stnId": (
        "KMA/APIHub station identifier for the GTS world-weather operation. "
        "Required by the official GTS APIHub schema; obtain it from the GTS "
        "station-information source or the citizen's station identifier."
    ),
    "icao": (
        "ICAO airport/station code for aviation METAR data, for example RKSI. "
        "Do not pass a Korean place name here."
    ),
    "baseTime": (
        "Numerical weather model base datetime, YYYYMMDDHHMM. Use a current "
        "or recent model slot; do not use stale catalog sample dates."
    ),
    "base_date": (
        "KMA village forecast base date, YYYYMMDD. Use a recent KST date within "
        "the APIHub retention window; stale catalog sample dates are rejected."
    ),
    "base_time": (
        "KMA village forecast base time, HHMM. Use the latest valid KST issue "
        "slot for the selected operation; stale catalog sample times are rejected."
    ),
    "basedatetime": (
        "KMA village forecast version base datetime, YYYYMMDDHHMM. Use a recent "
        "KST datetime within the current APIHub retention window."
    ),
}

_FIELD_PATTERNS: dict[str, str] = {
    "fromTmFc": r"^\d{8}$",
    "toTmFc": r"^\d{8}$",
    "dateTime": r"^\d{12}$",
    "tm": r"^\d{12}$",
    "baseTime": r"^\d{12}$",
    "base_date": r"^\d{8}$",
    "base_time": r"^\d{4}$",
    "basedatetime": r"^\d{12}$",
}

_REQUIRED_PARAMS_BY_OPERATION: dict[str, frozenset[str]] = {
    "GtsInfoService/getBuoy": frozenset({"stnId"}),
    "GtsInfoService/getSynop": frozenset({"stnId"}),
    "GtsInfoService/getTemp": frozenset({"stnId"}),
}

_CATEGORY_GUIDANCE: dict[int, tuple[str, str]] = {
    6: (
        "KMA satellite product lookup for GK2A imagery/grid products. Use it only "
        "when the citizen asks for satellite, cloud, fog, radiation, or "
        "imagery-derived meteorological products.",
        "위성 satellite GK2A cloud fog imagery grid product",
    ),
    7: (
        "KMA earthquake/volcano bulletin lookup. Use it for 지진, 화산, earthquake "
        "bulletin, seismic notification, and related alert-list questions; it is "
        "not for weather observations.",
        "지진 지진통보 화산 earthquake volcano seismic bulletin alert notification",
    ),
    12: (
        "KMA world-weather GTS observation lookup such as SYNOP, BUOY, or TEMP. "
        "Use it for international station observations, not for earthquake or "
        "Korean neighborhood forecasts.",
        "세계기상 GTS SYNOP BUOY TEMP WMO international station observation",
    ),
    14: (
        "KMA aviation-weather IWXXM/METAR lookup. Use it for airport aviation "
        "weather, METAR, TAF, or ICAO station reports.",
        "항공기상 aviation weather IWXXM METAR TAF airport ICAO",
    ),
}

_OPERATION_GUIDANCE: dict[str, tuple[str, str, str]] = {
    "AmmIwxxmService/getMetar": (
        "Fetch a METAR aviation weather report for one ICAO airport/station code.",
        "Choose this for airport aviation weather or METAR requests. Do not use "
        "it for neighborhood weather by Korean address; resolve location then "
        "use the KMA forecast/observation adapters instead.",
        "METAR aviation airport ICAO RKSI 항공기상 공항 실황",
    ),
    "CloudSatlitInfoService/getGk2aappsAll": (
        "Fetch GK2A APP satellite product data for the whole satellite coverage area.",
        "Choose this for satellite imagery/product questions. date_time must be "
        "a current recent YYYYMMDDHHMM slot; old sample datetimes are rejected "
        "by APIHub.",
        "GK2A APP satellite imagery whole area 위성 산출물 dateTime",
    ),
    "EqkInfoService/getEqkMsgList": (
        "Fetch the KMA earthquake/volcano bulletin list for a recent announcement date range.",
        "Choose this for earthquake bulletin/list questions. It is not for "
        "weather observations or SYNOP; keep from_tm_fc/to_tm_fc within the "
        "current 3 days APIHub window.",
        "지진통보 목록 지진 화산 earthquake bulletin list seismic notification",
    ),
    "GtsInfoService/getSynop": (
        "Fetch one KMA APIHub GTS SYNOP world-weather surface observation.",
        "Choose this for SYNOP/world-weather station observations. It is not "
        "for earthquake bulletins, satellite products, or Korean neighborhood "
        "forecasts.",
        "SYNOP GTS world weather surface observation WMO 세계기상",
    ),
}


def _field_default(operation: KmaApiHubOperation, param_name: str, default: object) -> object:
    """Avoid stale APIHub sample dates becoming model-call defaults."""
    if param_name in _DYNAMIC_TIME_PARAMS:
        return ...
    if param_name in _REQUIRED_PARAMS_BY_OPERATION.get(operation.operation_id, frozenset()):
        return ...
    return default if default is not None else ...


def _field_description(operation: KmaApiHubOperation, param_name: str) -> str:
    if operation.service == "NwpModelInfoService" and param_name == "baseTime":
        return (
            "Legacy NWP model base datetime, YYYYMMDDHHMM. Live APIHub probes "
            "currently return resultCode=99 because file production stopped "
            "after 2026-03-31 while the endpoint also enforces a current "
            "retention window. Do not choose this operation for current "
            f"citizen weather answers. Official parameter name: {param_name}. "
            f"Operation: {operation.operation_id}."
        )
    base = _PARAM_DESCRIPTIONS.get(
        param_name,
        f"KMA APIHub request parameter {param_name}.",
    )
    return f"{base} Official parameter name: {param_name}. Operation: {operation.operation_id}."


def _operation_guidance(operation: KmaApiHubOperation) -> tuple[str, str, str]:
    specific = _OPERATION_GUIDANCE.get(operation.operation_id)
    if specific is not None:
        return specific
    if operation.service == "NwpModelInfoService":
        return (
            "Legacy KMA NWP model grid-data lookup. Live APIHub probes currently "
            "return resultCode=99 because this product is no longer producible "
            "through the current retention window.",
            "Do not choose this for citizen-facing current weather or forecast "
            "answers. Prefer KMA village/current forecast adapters or KIMModel "
            "operations when model-grid data is specifically needed.",
            "legacy NWP model resultCode 99 discontinued retention 수치모델 중단",
        )
    category_purpose, category_keywords = _CATEGORY_GUIDANCE.get(
        operation.category_seq,
        (
            "KMA APIHub structured OpenAPI operation for direct agency meteorological data lookup.",
            "KMA APIHub official agency meteorological data",
        ),
    )
    return (
        f"{category_purpose} Specific operation: {operation.operation_id}.",
        "Choose this only when the citizen request matches this exact API family "
        "and operation name. Prefer specialized KMA current/forecast adapters "
        "for Korean address weather.",
        category_keywords,
    )


def _search_hint(operation: KmaApiHubOperation) -> str:
    _, _, keywords = _operation_guidance(operation)
    return (
        f"KMA APIHub 기상청 {operation.category_name_ko} {operation.service} "
        f"{operation.operation} {operation.operation_id} {keywords}"
    )


def _llm_description(operation: KmaApiHubOperation) -> str:
    purpose, selection, _ = _operation_guidance(operation)
    visible_params = ", ".join(param.field_name for param in operation.non_credential_params)
    return (
        f"KMA APIHub structured OpenAPI operation {operation.operation_id}. "
        f"Category: {operation.category_name_ko}. "
        f"Purpose: {purpose} Selection rule: {selection} "
        f"Input fields: {visible_params}. "
        "Credential handling: UMMAYA runtime supplies authKey from "
        "UMMAYA_KMA_API_HUB_AUTH_KEY; the model must never provide authKey."
    )


@cache
def input_schema_for(operation_id: str) -> type[BaseModel]:
    """Build the Pydantic input model for ``<service>/<operation>``."""
    operation = get_operation_by_id(operation_id)
    fields: dict[str, tuple[object, object]] = {}
    for param in operation.non_credential_params:
        default = _field_default(operation, param.name, param.default)
        pattern = _FIELD_PATTERNS.get(param.name)
        field = (
            Field(
                default,
                description=_field_description(operation, param.name),
                pattern=pattern,
            )
            if pattern is not None
            else Field(
                default,
                description=_field_description(operation, param.name),
            )
        )
        fields[param.field_name] = (
            _field_type(param.value_type),
            field,
        )

    model = create_model(  # type: ignore[call-overload]
        _model_name(operation),
        __config__=ConfigDict(frozen=True, extra="forbid"),
        **fields,
    )
    return cast(type[BaseModel], model)


def _response_format(response: httpx.Response) -> Literal["json", "xml", "text_error"]:
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        return "json"
    if "xml" in content_type or response.text.lstrip().startswith("<"):
        return "xml"
    return "text_error"


def _dict_or_empty(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): val for key, val in value.items()}


def _normalize_items(value: object) -> list[dict[str, object]]:
    if not value:
        return []
    if isinstance(value, dict):
        return [_dict_or_empty(value)]
    if isinstance(value, list):
        return [_dict_or_empty(item) for item in value if isinstance(item, dict)]
    return [{"value": value}]


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _parse_response(
    operation: KmaApiHubOperation,
    payload: dict[str, object],
    *,
    raw_format: Literal["json", "xml", "text_error"],
) -> KmaApiHubStructuredOutput:
    try:
        response = _dict_or_empty(payload["response"])
    except KeyError as exc:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=f"Unexpected KMA APIHub response structure: missing {exc}",
            cause=exc,
        ) from exc

    header = _dict_or_empty(response.get("header"))
    result_code = str(header.get("resultCode", "")) or None
    result_msg = str(header.get("resultMsg", "")) or None
    if result_code and result_code not in {"00", "03"}:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=(
                "KMA APIHub error: "
                f"operation={operation.operation_id!r} "
                f"resultCode={result_code!r} resultMsg={result_msg!r}"
            ),
        )

    body = _dict_or_empty(response.get("body"))
    items_container = _dict_or_empty(body.get("items"))
    raw_items = items_container.get("item")
    items = _normalize_items(raw_items)

    return KmaApiHubStructuredOutput(
        operation_id=operation.operation_id,
        service=operation.service,
        operation=operation.operation,
        result_code=result_code,
        result_msg=result_msg,
        page_no=_int_or_none(body.get("pageNo")),
        num_of_rows=_int_or_none(body.get("numOfRows")),
        total_count=_int_or_none(body.get("totalCount")),
        items=items,
        raw_format=raw_format,
    )


def _query_params(
    operation: KmaApiHubOperation,
    params: BaseModel,
) -> dict[str, KmaApiHubQueryValue]:
    values = params.model_dump(mode="python")
    query: dict[str, KmaApiHubQueryValue] = {}
    for param in operation.non_credential_params:
        value = values.get(param.field_name)
        if value is None:
            continue
        if not isinstance(value, (str, int, float, bool)):
            value = str(value)
        query[param.name] = value
    return query


def _status_error_message(operation: KmaApiHubOperation, exc: httpx.HTTPStatusError) -> str:
    base = f"HTTP error from KMA APIHub: {summarize_http_status_error(exc)}"
    if exc.response.status_code not in {401, 403}:
        return base
    if operation.approval_state != "approval_pending":
        return base
    return (
        f"{base}. APIHub utilization approval for {operation.operation_id!r} "
        "was not observed in the approved-app evidence captured on 2026-05-24."
    )


async def call_operation(
    operation: KmaApiHubOperation,
    params: BaseModel,
    *,
    client: httpx.AsyncClient | None = None,
) -> KmaApiHubStructuredOutput:
    """Call one structured KMA APIHub operation and normalize its envelope."""
    endpoint = resolve_apihub_endpoint(operation)
    query_params = _query_params(operation, params)
    query_params[endpoint.auth_query_param] = endpoint.api_key

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=30.0)

    try:
        assert client is not None  # noqa: S101
        response = await client.get(endpoint.url, params=query_params)
        response.raise_for_status()
        raw_format = _response_format(response)
        payload = decode_response_payload(response)
        return _parse_response(operation, payload, raw_format=raw_format)
    except (ToolExecutionError, ConfigurationError):
        raise
    except httpx.HTTPStatusError as exc:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=_status_error_message(operation, exc),
            cause=exc,
        ) from exc
    except httpx.RequestError as exc:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=f"Network error reaching KMA APIHub: {exc}",
            cause=exc,
        ) from exc
    except KmaPayloadDecodeError as exc:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=f"Unable to decode KMA APIHub response: {exc}",
            cause=exc,
        ) from exc
    finally:
        if own_client and client is not None:
            await client.aclose()


def build_tool(operation: KmaApiHubOperation) -> GovAPITool:
    """Build the GovAPITool definition for a catalog operation."""
    return GovAPITool(
        id=operation.tool_id,
        name_ko=f"KMA APIHub {operation.category_name_ko} {operation.operation}",
        ministry="KMA",
        category=["기상청", "APIHub", operation.category_name_ko, operation.service],
        endpoint=f"{KMA_API_HUB_BASE_URL}{operation.endpoint_path}",
        auth_type="api_key",
        input_schema=input_schema_for(operation.operation_id),
        output_schema=KmaApiHubStructuredOutput,
        search_hint=_search_hint(operation),
        llm_description=_llm_description(operation),
        policy=AdapterRealDomainPolicy(
            real_classification_url="https://apihub.kma.go.kr/",
            real_classification_text=(
                "KMA APIHub structured OpenAPI surface; read-only weather and "
                "meteorological data access."
            ),
            citizen_facing_gate="read-only",
            last_verified=datetime(2026, 5, 24, tzinfo=UTC),
        ),
        is_concurrency_safe=True,
        cache_ttl_seconds=600,
        rate_limit_per_minute=10,
        is_core=False,
        primitive="find",
    )


def _adapter_for(operation: KmaApiHubOperation) -> AdapterFn:
    async def _adapter(inp: BaseModel) -> dict[str, object]:
        output = await call_operation(operation, inp)
        return {"kind": "record", "item": output.model_dump(mode="python")}

    return cast(AdapterFn, _adapter)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register every cataloged structured KMA APIHub operation."""
    count = 0
    for operation in iter_structured_operations():
        tool = build_tool(operation)
        registry.register(tool)
        executor.register_adapter(tool.id, _adapter_for(operation))
        count += 1
    logger.info("Registered %d KMA APIHub structured OpenAPI tools", count)
