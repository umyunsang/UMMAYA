# SPDX-License-Identifier: Apache-2.0
"""Wrappers for KMA APIHub non-structured URL operations."""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from functools import cache
from typing import Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, create_model

from ummaya.tools._outbound_trace import traced_async_client
from ummaya.tools.errors import ConfigurationError, ToolExecutionError
from ummaya.tools.executor import AdapterFn, ToolExecutor
from ummaya.tools.kma.apihub_endpoint import (
    KMA_API_HUB_AUTH_KEY_ENV,
    KMA_API_HUB_BASE_URL,
)
from ummaya.tools.kma.apihub_url_catalog import (
    KmaApiHubUrlOperation,
    KmaApiHubUrlScalar,
    get_url_operation_by_id,
    iter_url_operations,
)
from ummaya.tools.kma.response_payload import summarize_http_status_error
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

type KmaApiHubUrlQueryValue = str | int | float | bool

_MAX_RAW_TEXT_CHARS = 64_000


class KmaApiHubUrlOutput(BaseModel):
    """Normalized output from one KMA APIHub non-structured URL operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: str
    endpoint_path: str
    approval_state: Literal["approved", "approval_pending"]
    content_type: str
    raw_format: Literal["text", "json", "image", "binary"]
    line_count: int | None = None
    summary: dict[str, object] | None = None
    raw_text: str | None = None
    status_code: int


_MISSING_TEXT_VALUES = frozenset({"-99999", "-9999", "-999", ""})
_METAR_AIRPORT_STATIONS: dict[str, dict[str, str]] = {
    "92": {"airport_name_ko": "양양공항", "airport_name_en": "Yangyang Airport", "icao": "RKNY"},
    "110": {"airport_name_ko": "김포공항", "airport_name_en": "Gimpo Airport", "icao": "RKSS"},
    "113": {"airport_name_ko": "인천공항", "airport_name_en": "Incheon Airport", "icao": "RKSI"},
    "128": {"airport_name_ko": "청주공항", "airport_name_en": "Cheongju Airport", "icao": "RKTU"},
    "139": {
        "airport_name_ko": "포항경주공항",
        "airport_name_en": "Pohang Gyeongju Airport",
        "icao": "RKTH",
    },
    "142": {"airport_name_ko": "대구공항", "airport_name_en": "Daegu Airport", "icao": "RKTN"},
    "151": {"airport_name_ko": "울산공항", "airport_name_en": "Ulsan Airport", "icao": "RKPU"},
    "153": {"airport_name_ko": "김해공항", "airport_name_en": "Gimhae Airport", "icao": "RKPK"},
    "158": {"airport_name_ko": "광주공항", "airport_name_en": "Gwangju Airport", "icao": "RKJJ"},
    "161": {"airport_name_ko": "사천공항", "airport_name_en": "Sacheon Airport", "icao": "RKPS"},
    "163": {"airport_name_ko": "무안공항", "airport_name_en": "Muan Airport", "icao": "RKJB"},
    "167": {"airport_name_ko": "여수공항", "airport_name_en": "Yeosu Airport", "icao": "RKJY"},
    "182": {"airport_name_ko": "제주공항", "airport_name_en": "Jeju Airport", "icao": "RKPC"},
}
_METAR_STATION_REFERENCE_SOURCE = (
    "Airport station names come from KMA APIHub SfcYearlyInfoService/getrAirStnLstTbl "
    "direct probe for 2024; ICAO codes come from the official AmmIwxxmService/getMetar examples."
)


def _field_type(param_type: str, required: bool) -> object:
    if param_type == "integer":
        return int if required else int | None
    if param_type == "number":
        return float if required else float | None
    if param_type == "boolean":
        return bool if required else bool | None
    return str if required else str | None


def _model_name(operation: KmaApiHubUrlOperation) -> str:
    return (
        "KmaApiHubUrl"
        + "".join(part.title() for part in operation.operation_id.split("_") if part)
        + "Input"
    )


_FIELD_PATTERNS: dict[str, str] = {
    "tm": r"^\d{12}$",
    "tm1": r"^\d{12}$",
    "tm2": r"^\d{12}$",
    "analTime": r"^\d{12}$",
}

_FIELD_DESCRIPTIONS: dict[tuple[str, str], str] = {
    (
        "air_metar_decoded",
        "tm",
    ): (
        "METAR decoded-data lookup time in UTC, YYYYMMDDHHMM. Omit it to "
        "request the latest upstream slot."
    ),
    (
        "air_metar_decoded",
        "org",
    ): (
        "METAR issuing organization. Use K for the official KMA decoded-data "
        "product unless the citizen names another official source. The normalized "
        "summary annotates known KMA airport station numbers such as 153 Gimhae/RKPK."
    ),
    (
        "air_metar_decoded",
        "help",
    ): "Set 1 to include KMA field-help lines in the raw text; set 0 for compact decoded records.",
    (
        "air_amos_minute",
        "stn",
    ): (
        "Official AMOS station number. The APIHub page lists 110 Gimpo, "
        "113 Incheon, 182 Jeju, 163 Muan, 151 Ulsan, 167 Yeosu, and "
        "92 Yangyang. Gimhae is not listed for this AMOS endpoint; use "
        "METAR RKPK for Gimhae airport aviation weather."
    ),
    (
        "air_amos_minute",
        "tm",
    ): "AMOS lookup time in KST, YYYYMMDDHHMM. Omit it to request the latest upstream slot.",
    (
        "air_amos_minute",
        "dtm",
    ): "Lookback window in minutes including tm. Official maximum is 60 minutes.",
    (
        "high_resolution_grid_point",
        "obs",
    ): (
        "Comma-separated high-resolution grid elements, for example "
        "ta,td,hm,ws_10m,wd_10m,vs,rn_60m."
    ),
    (
        "high_resolution_grid_point",
        "tm1",
    ): "Start time in KST, YYYYMMDDHHMM. Omit it to request the latest upstream slot.",
    (
        "high_resolution_grid_point",
        "tm2",
    ): "End time in KST, YYYYMMDDHHMM. Official maximum range is 60 minutes.",
    ("high_resolution_grid_point", "lat"): "WGS-84 latitude for the point lookup.",
    ("high_resolution_grid_point", "lon"): "WGS-84 longitude for the point lookup.",
    (
        "aws_objective_analysis_grid",
        "obj",
    ): "Objective-analysis method: mq for Multi Quadric or bn for Barnes.",
    (
        "analysis_weather_chart_image",
        "analTime",
    ): (
        "KMA analyzed weather-chart time in UTC, YYYYMMDDHHMM. Include minutes; "
        "do not pass a 10-digit KST hour. For now/today requests, use the latest "
        "completed official UTC analysis slot before the citizen's local time."
    ),
}


def _field_description(operation: KmaApiHubUrlOperation, param_name: str) -> str:
    base = _FIELD_DESCRIPTIONS.get(
        (operation.operation_id, param_name),
        f"KMA APIHub URL request parameter {param_name}.",
    )
    return f"{base} Official parameter name: {param_name}. Operation: {operation.operation_id}."


def _field_default(param_default: KmaApiHubUrlScalar, required: bool) -> object:
    if required and param_default is None:
        return ...
    return param_default


@cache
def input_schema_for(operation_id: str) -> type[BaseModel]:
    """Build the Pydantic input model for one URL operation."""
    operation = get_url_operation_by_id(operation_id)
    fields: dict[str, tuple[object, object]] = {}
    for param in operation.non_credential_params:
        default = _field_default(param.default, param.required)
        pattern = _FIELD_PATTERNS.get(param.name)
        field = (
            Field(
                default,
                description=_field_description(operation, param.name),
                pattern=pattern,
            )
            if pattern is not None
            else Field(default, description=_field_description(operation, param.name))
        )
        fields[param.field_name] = (_field_type(param.value_type, param.required), field)

    model = create_model(  # type: ignore[call-overload]
        _model_name(operation),
        __config__=ConfigDict(frozen=True, extra="forbid"),
        **fields,
    )
    return cast(type[BaseModel], model)


def _search_hint(operation: KmaApiHubUrlOperation) -> str:
    return (
        f"KMA APIHub 기상청 {operation.category_name_ko} {operation.title_ko} "
        f"{operation.operation_id} {operation.search_keywords}"
    )


def _llm_description(operation: KmaApiHubUrlOperation) -> str:
    visible_params = ", ".join(param.field_name for param in operation.non_credential_params)
    approval = (
        "Direct curl verification on 2026-05-26 returned APIHub utilization "
        "approval required for this runtime key; fail closed and cite the "
        "official APIHub channel if upstream returns 403."
        if operation.approval_state == "approval_pending"
        else "This operation is approved for live APIHub use with the runtime key."
    )
    return (
        f"KMA APIHub non-structured URL operation {operation.operation_id}. "
        f"Category: {operation.category_name_ko}. Purpose: {operation.purpose} "
        f"Selection rule: {operation.selection_rule} Approval: {approval} "
        f"Input fields: {visible_params}. Credential handling: UMMAYA runtime "
        "supplies authKey from UMMAYA_KMA_API_HUB_AUTH_KEY; the model must "
        "never provide authKey."
    )


def _query_params(
    operation: KmaApiHubUrlOperation,
    params: BaseModel,
) -> dict[str, KmaApiHubUrlQueryValue]:
    values = params.model_dump(mode="python")
    query: dict[str, KmaApiHubUrlQueryValue] = {}
    for param in operation.non_credential_params:
        value = values.get(param.field_name)
        if value is None:
            continue
        if not isinstance(value, (str, int, float, bool)):
            value = str(value)
        query[param.name] = value
    return query


def _api_key() -> str:
    value = os.environ.get(KMA_API_HUB_AUTH_KEY_ENV, "").strip()
    if not value:
        raise ConfigurationError(KMA_API_HUB_AUTH_KEY_ENV)
    return value


def _url(operation: KmaApiHubUrlOperation) -> str:
    return f"{KMA_API_HUB_BASE_URL}{operation.endpoint_path}"


def _raw_format(
    operation: KmaApiHubUrlOperation,
    response: httpx.Response,
) -> Literal["text", "json", "image", "binary"]:
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        return "json"
    if "text" in content_type or "xml" in content_type or "csv" in content_type:
        return "text"
    if "image" in content_type or operation.response_kind == "image":
        return "image"
    if operation.response_kind == "text":
        return "text"
    return "binary"


def _text_data_lines(raw_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rows.append(stripped.split())
    return rows


def _int_cell(fields: list[str], index: int) -> int | None:
    if index >= len(fields):
        return None
    value = fields[index]
    if value in _MISSING_TEXT_VALUES:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _scaled_cell(fields: list[str], index: int, denominator: float) -> float | None:
    value = _int_cell(fields, index)
    if value is None:
        return None
    return round(value / denominator, 1)


def _slp_hpa(raw_code: str) -> float | None:
    if not re.fullmatch(r"\d{3}", raw_code):
        return None
    value = int(raw_code)
    base = 900.0 if value >= 500 else 1000.0
    return round(base + (value / 10.0), 1)


def _wind_cardinal(direction_deg: int) -> dict[str, str]:
    labels: tuple[tuple[str, str], ...] = (
        ("N", "북풍"),
        ("NNE", "북북동풍"),
        ("NE", "북동풍"),
        ("ENE", "동북동풍"),
        ("E", "동풍"),
        ("ESE", "동남동풍"),
        ("SE", "남동풍"),
        ("SSE", "남남동풍"),
        ("S", "남풍"),
        ("SSW", "남남서풍"),
        ("SW", "남서풍"),
        ("WSW", "서남서풍"),
        ("W", "서풍"),
        ("WNW", "서북서풍"),
        ("NW", "북서풍"),
        ("NNW", "북북서풍"),
    )
    index = round((direction_deg % 360) / 22.5) % len(labels)
    en, ko = labels[index]
    return {"en": en, "ko": ko}


def _first_metar_visibility(fields: list[str]) -> int | None:
    for value in fields[1:]:
        if re.fullmatch(r"\d{4,5}", value) and value != "99999":
            return int(value)
    return None


def _metar_safe_weather(fields: list[str], raw_report: str) -> dict[str, object]:
    safe_weather: dict[str, object] = {
        "wind": None,
        "visibility_m": _first_metar_visibility(fields),
        "rvr_m": None,
        "ceiling": None,
        "sea_level_pressure_hpa": None,
    }
    if fields:
        wind = fields[0]
        if re.fullmatch(r"\d{5}", wind):
            direction_deg = int(wind[0:3])
            cardinal = _wind_cardinal(direction_deg)
            speed_kt = int(wind[3:5])
            safe_weather["wind"] = {
                "raw": wind,
                "direction_deg": direction_deg,
                "direction_from_cardinal_en": cardinal["en"],
                "direction_from_cardinal_ko": cardinal["ko"],
                "speed_kt": speed_kt,
                "speed_mps": round(speed_kt * 0.514444, 1),
            }

    if rvr_match := re.search(r"\bR\d{2}[LRC]?/(\d{4})", raw_report):
        safe_weather["rvr_m"] = int(rvr_match.group(1))
    if ceiling_match := re.search(r"\bCIG(\d{3})\b", raw_report):
        ceiling_raw = f"CIG{ceiling_match.group(1)}"
        safe_weather["ceiling"] = {
            "raw": ceiling_raw,
            "height_ft": int(ceiling_match.group(1)) * 100,
        }
    if slp_match := re.search(r"\bSLP(\d{3})\b", raw_report):
        safe_weather["sea_level_pressure_hpa"] = _slp_hpa(slp_match.group(1))

    return safe_weather


def _latest_amos_summary(raw_text: str) -> dict[str, object] | None:
    rows = [row for row in _text_data_lines(raw_text) if len(row) >= 27]
    if not rows:
        return None
    latest = rows[-1]
    return {
        "latest_observation": {
            "station": latest[0],
            "observed_at": latest[1],
            "left_visibility_m": _int_cell(latest, 2),
            "right_visibility_m": _int_cell(latest, 3),
            "left_rvr_m": _int_cell(latest, 4),
            "right_rvr_m": _int_cell(latest, 5),
            "cloud_height_min_m": _int_cell(latest, 6),
            "temperature_c": _scaled_cell(latest, 7, 10.0),
            "dew_point_c": _scaled_cell(latest, 8, 10.0),
            "humidity_percent": _int_cell(latest, 9),
            "qff_hpa": _scaled_cell(latest, 10, 10.0),
            "qfe_hpa": _scaled_cell(latest, 11, 10.0),
            "rain_mm": _scaled_cell(latest, 12, 10.0),
            "wind_2min_direction_deg": _int_cell(latest, 15),
            "wind_2min_speed_mps": _scaled_cell(latest, 18, 10.0),
            "wind_10min_direction_deg": _int_cell(latest, 21),
            "wind_10min_speed_mps": _scaled_cell(latest, 24, 10.0),
        },
        "unit_notes": {
            "temperature_c": "TA and TD are converted from official 0.1C units.",
            "pressure_hpa": "PS/QFF and PA/QFE are converted from official 0.1hPa units.",
            "wind_speed_mps": "WS02 and WS10 are converted from official 0.1m/s units.",
            "sentinel": "-99999 values are omitted as null.",
        },
    }


def _metar_decoded_summary(raw_text: str) -> dict[str, object] | None:
    records: list[dict[str, object]] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("METAR", "SPECI")):
            continue
        report_type, _, payload = stripped.partition(" ")
        parts = payload.strip().split("#")
        if len(parts) < 4:
            continue
        station_number = parts[1]
        record: dict[str, object] = {
            "report_type": report_type,
            "station_number": station_number,
            "observed_at": parts[2],
            "raw_fields": parts[3:],
            "raw_report": stripped,
            "safe_weather": _metar_safe_weather(parts[3:], stripped),
        }
        station = _METAR_AIRPORT_STATIONS.get(station_number)
        if station is not None:
            record["station"] = station
        records.append(record)
    if not records:
        return None
    return {
        "decoded_records": records,
        "interpretation_warning": (
            "Use only decoded_records[].safe_weather for weather values. raw_fields "
            "and raw_report are provenance text, not a model-readable schema; do not "
            "derive pressure, wind, cloud, runway, or temperature values from raw_fields."
        ),
        "station_reference_source": _METAR_STATION_REFERENCE_SOURCE,
    }


def _summary_for_operation(
    operation: KmaApiHubUrlOperation,
    raw_text: str | None,
) -> dict[str, object] | None:
    if raw_text is None:
        return None
    if operation.operation_id == "air_amos_minute":
        return _latest_amos_summary(raw_text)
    if operation.operation_id == "air_metar_decoded":
        return _metar_decoded_summary(raw_text)
    return None


def _status_error_message(operation: KmaApiHubUrlOperation, exc: httpx.HTTPStatusError) -> str:
    base = f"HTTP error from KMA APIHub URL operation: {summarize_http_status_error(exc)}"
    if operation.operation_id == "air_amos_minute" and exc.response.status_code == 404:
        return (
            f"{base}. Official KMA APIHub AMOS upstream returned 404 Not Found for "
            "the documented AMOS URL product in this run. Preserve this as an "
            "upstream AMOS failure in the final answer; do not invent runway-area "
            "values. If the citizen needs airport aviation weather and a METAR "
            "candidate/result is available, explain that METAR is the fallback "
            "evidence source."
        )
    if exc.response.status_code != 403:
        return base
    if operation.approval_state != "approval_pending":
        return base
    return (
        f"{base}. APIHub utilization approval is required for "
        f"{operation.operation_id!r}; direct curl verification on 2026-05-26 "
        "observed this endpoint returning the agency approval-required response."
    )


async def call_operation(
    operation: KmaApiHubUrlOperation,
    params: BaseModel,
    *,
    client: httpx.AsyncClient | None = None,
) -> KmaApiHubUrlOutput:
    """Call one non-structured KMA APIHub URL operation."""
    query_params = _query_params(operation, params)
    query_params["authKey"] = _api_key()

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=30.0)

    try:
        assert client is not None  # noqa: S101
        response = await client.get(_url(operation), params=query_params)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        raw_format = _raw_format(operation, response)
        raw_text = response.text[:_MAX_RAW_TEXT_CHARS] if raw_format in {"text", "json"} else None
        line_count = len(raw_text.splitlines()) if raw_text is not None else None
        return KmaApiHubUrlOutput(
            operation_id=operation.operation_id,
            endpoint_path=operation.endpoint_path,
            approval_state=operation.approval_state,
            content_type=content_type,
            raw_format=raw_format,
            line_count=line_count,
            raw_text=raw_text,
            summary=_summary_for_operation(operation, raw_text),
            status_code=response.status_code,
        )
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
    finally:
        if own_client and client is not None:
            await client.aclose()


def build_tool(operation: KmaApiHubUrlOperation) -> GovAPITool:
    """Build the GovAPITool definition for a URL operation."""
    return GovAPITool(
        id=operation.tool_id,
        name_ko=f"KMA APIHub {operation.title_ko}",
        ministry="KMA",
        category=["기상청", "APIHub", operation.category_name_ko, "URL"],
        endpoint=_url(operation),
        auth_type="api_key",
        input_schema=input_schema_for(operation.operation_id),
        output_schema=KmaApiHubUrlOutput,
        search_hint=_search_hint(operation),
        llm_description=_llm_description(operation),
        policy=AdapterRealDomainPolicy(
            real_classification_url=operation.official_page_url,
            real_classification_text=(
                "KMA APIHub non-structured URL surface; read-only meteorological data access."
            ),
            citizen_facing_gate="read-only",
            last_verified=datetime(2026, 5, 26, tzinfo=UTC),
        ),
        is_concurrency_safe=True,
        cache_ttl_seconds=300,
        rate_limit_per_minute=10,
        is_core=False,
        primitive="find",
    )


def _adapter_for(operation: KmaApiHubUrlOperation) -> AdapterFn:
    async def _adapter(inp: BaseModel) -> dict[str, object]:
        output = await call_operation(operation, inp)
        return {"kind": "record", "item": output.model_dump(mode="python")}

    return cast(AdapterFn, _adapter)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register every cataloged non-structured KMA APIHub URL operation."""
    count = 0
    for operation in iter_url_operations():
        tool = build_tool(operation)
        registry.register(tool)
        executor.register_adapter(tool.id, _adapter_for(operation))
        count += 1
    logger.info("Registered %d KMA APIHub non-structured URL tools", count)
