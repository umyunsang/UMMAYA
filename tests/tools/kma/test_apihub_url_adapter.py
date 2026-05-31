# SPDX-License-Identifier: Apache-2.0
"""Tests for KMA APIHub non-structured URL wrappers."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from ummaya.tools.errors import ToolExecutionError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.kma.apihub_url_adapter import (
    KmaApiHubUrlOutput,
    build_tool,
    call_operation,
    input_schema_for,
    register,
)
from ummaya.tools.kma.apihub_url_catalog import get_url_operation_by_id
from ummaya.tools.registry import ToolRegistry


def _client_for_response(response: httpx.Response) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        response.request = request
        return response

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_amos_summary_scales_pressure_and_sentinel_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_url_operation_by_id("air_amos_minute")
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        200,
        text=(
            "#START7777\n"
            "#             TM   L_VIS  R_VIS  L_RVR  R_RVR  CH_MIN    TA     TD     HM"
            "     PS     PA     RN  WX1  WX2   WD02   WD02   WD02   WS02   WS02   WS02"
            "   WD10   WD10   WD10   WS10   WS10   WS10\n"
            "#    YYYYMMDDHHMI                                  m   0.1C   0.1C      %"
            " 0.1hPa 0.1hPa  0.1mm                  deg    MAX    MIN 0.1m/s    MAX"
            "    MIN    deg    MAX    MIN 0.1m/s    MAX    MIN\n"
            " 110 202605261236  10000 -99999   2000 -99999  15400    300    188     51"
            "  10066  10046      0 -99999 -99999    160    210    130     10     20"
            "      5    150    150      0     10     23      1\n"
        ),
        headers={"content-type": "text/plain; charset=utf-8"},
    )

    async with _client_for_response(response) as client:
        output = await call_operation(
            operation,
            schema.model_validate({"stn": "110"}),
            client=client,
        )

    assert output.summary == {
        "latest_observation": {
            "station": "110",
            "observed_at": "202605261236",
            "left_visibility_m": 10000,
            "right_visibility_m": None,
            "left_rvr_m": 2000,
            "right_rvr_m": None,
            "cloud_height_min_m": 15400,
            "temperature_c": 30.0,
            "dew_point_c": 18.8,
            "humidity_percent": 51,
            "qff_hpa": 1006.6,
            "qfe_hpa": 1004.6,
            "rain_mm": 0.0,
            "wind_2min_direction_deg": 160,
            "wind_2min_speed_mps": 1.0,
            "wind_10min_direction_deg": 150,
            "wind_10min_speed_mps": 1.0,
        },
        "unit_notes": {
            "temperature_c": "TA and TD are converted from official 0.1C units.",
            "pressure_hpa": "PS/QFF and PA/QFE are converted from official 0.1hPa units.",
            "wind_speed_mps": "WS02 and WS10 are converted from official 0.1m/s units.",
            "sentinel": "-99999 values are omitted as null.",
        },
    }


@pytest.mark.asyncio
async def test_metar_decoded_summary_preserves_raw_fields_without_unsafe_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_url_operation_by_id("air_metar_decoded")
    schema = input_schema_for(operation.operation_id)
    raw_report = (
        "METAR  #153#202605261200#16008####10000####################7#3#035#SC#6#070#AS"
        "#7#100#AS####0280#0200#1006#2972####10063#10045#########CIG070 SLP063 8/520 9/340##="
    )
    response = httpx.Response(
        200,
        text=f"#START7777\n{raw_report}\n#7777END\n",
        headers={"content-type": "text/plain; charset=utf-8"},
    )

    async with _client_for_response(response) as client:
        output = await call_operation(
            operation,
            schema.model_validate({"org": "K", "help": 1}),
            client=client,
        )

    assert output.summary is not None
    records = output.summary["decoded_records"]
    assert isinstance(records, list)
    assert records[0] | {"raw_fields": []} == {
        "report_type": "METAR",
        "station_number": "153",
        "observed_at": "202605261200",
        "station": {
            "airport_name_en": "Gimhae Airport",
            "airport_name_ko": "김해공항",
            "icao": "RKPK",
        },
        "raw_fields": [],
        "raw_report": raw_report,
        "safe_weather": records[0]["safe_weather"],
    }
    raw_fields = records[0]["raw_fields"]
    assert isinstance(raw_fields, list)
    assert raw_fields[0] == "16008"
    assert raw_fields[4] == "10000"
    assert raw_fields[-3] == "CIG070 SLP063 8/520 9/340"
    assert raw_fields[-1] == "="
    assert records[0]["safe_weather"] == {
        "wind": {
            "raw": "16008",
            "direction_deg": 160,
            "direction_from_cardinal_en": "SSE",
            "direction_from_cardinal_ko": "남남동풍",
            "speed_kt": 8,
            "speed_mps": 4.1,
        },
        "visibility_m": 10000,
        "rvr_m": None,
        "ceiling": {
            "raw": "CIG070",
            "height_ft": 7000,
        },
        "sea_level_pressure_hpa": 1006.3,
    }
    assert output.summary["interpretation_warning"] == (
        "Use only decoded_records[].safe_weather for weather values. raw_fields "
        "and raw_report are provenance text, not a model-readable schema; do not "
        "derive pressure, wind, cloud, runway, or temperature values from raw_fields."
    )
    assert output.summary["station_reference_source"] == (
        "Airport station names come from KMA APIHub SfcYearlyInfoService/getrAirStnLstTbl "
        "direct probe for 2024; ICAO codes come from the official "
        "AmmIwxxmService/getMetar examples."
    )
    assert "pressure_hpa" not in records[0]
    assert "wind_speed_mps" not in records[0]


def test_metar_amos_and_analysis_url_schemas_expose_official_contracts() -> None:
    metar = get_url_operation_by_id("air_metar_decoded")
    metar_schema = input_schema_for(metar.operation_id).model_json_schema()
    metar_tool = build_tool(metar)

    assert list(input_schema_for(metar.operation_id).model_fields) == [
        "tm",
        "org",
        "help",
    ]
    assert "authKey" not in metar_schema["properties"]
    assert "METAR decoded-data" in str(metar_tool.llm_description)
    assert "station 153 is Gimhae Airport / RKPK" in str(metar_tool.llm_description)
    assert "Use decoded_records[].safe_weather only" in str(metar_tool.llm_description)
    assert "direction_from_cardinal_ko" in str(metar_tool.llm_description)
    assert "approved for live APIHub use" in str(metar_tool.llm_description)

    amos = get_url_operation_by_id("air_amos_minute")
    amos_schema = input_schema_for(amos.operation_id).model_json_schema()
    amos_tool = build_tool(amos)

    assert list(input_schema_for(amos.operation_id).model_fields) == [
        "tm",
        "dtm",
        "stn",
        "help",
    ]
    assert "authKey" not in amos_schema["properties"]
    assert "stn" in amos_schema["required"]
    assert "Gimpo" in amos_schema["properties"]["stn"]["description"]
    assert "Gimhae is not listed" in amos_schema["properties"]["stn"]["description"]
    assert "AMOS" in str(amos_tool.llm_description)
    assert "Do not use AMOS for Gimhae" in str(amos_tool.llm_description)
    assert "182 is Jeju" in str(amos_tool.llm_description)
    assert "approved for live APIHub use" in str(amos_tool.llm_description)

    highres = get_url_operation_by_id("high_resolution_grid_point")
    highres_schema = input_schema_for(highres.operation_id).model_json_schema()
    highres_tool = build_tool(highres)

    assert {"lat", "lon", "obs"}.issubset(highres_schema["properties"])
    assert "500m" in str(highres_tool.llm_description)
    assert "objective analysis" in str(highres_tool.llm_description).lower()
    assert "After locate returns coordinates" in str(highres_tool.llm_description)
    assert "분석자료" in highres_tool.search_hint
    assert "기온 습도 풍속 풍향 시정" in highres_tool.search_hint

    chart = get_url_operation_by_id("analysis_weather_chart_image")
    chart_tool = build_tool(chart)
    chart_schema = input_schema_for(chart.operation_id).model_json_schema()
    assert "anal_time" in chart_schema["required"]
    assert "YYYYMMDDHHMM" in chart_schema["properties"]["anal_time"]["description"]
    assert "10-digit KST hour" in chart_schema["properties"]["anal_time"]["description"]
    assert "WthrChartInfoService/getSurfaceChart" in str(chart_tool.llm_description)
    assert "Use anal_time, not code" in str(chart_tool.llm_description)
    assert "10-digit local hour" in str(chart_tool.llm_description)
    assert "approved for live APIHub use" in str(chart_tool.llm_description)


def test_url_output_orders_summary_before_raw_text() -> None:
    """Models should see normalized values before provenance raw text."""

    fields = list(KmaApiHubUrlOutput.model_fields)
    assert fields.index("summary") < fields.index("raw_text")


@pytest.mark.asyncio
async def test_url_operation_returns_text_body_and_injects_auth_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_url_operation_by_id("air_amos_minute")
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        200,
        text=("# S TM TA HM WS10\n110 202605261810 215 61 32\n110 202605261820 216 60 30\n"),
        headers={"content-type": "text/plain; charset=utf-8"},
    )

    async with _client_for_response(response) as client:
        output = await call_operation(
            operation,
            schema.model_validate({"stn": "110"}),
            client=client,
        )

    assert output == KmaApiHubUrlOutput(
        operation_id="air_amos_minute",
        endpoint_path="/api/typ01/url/amos.php",
        approval_state="approved",
        content_type="text/plain; charset=utf-8",
        raw_format="text",
        line_count=3,
        raw_text="# S TM TA HM WS10\n110 202605261810 215 61 32\n110 202605261820 216 60 30\n",
        status_code=200,
    )
    assert response.request.url.params["authKey"] == "test-api-hub-key"
    assert response.request.url.params["stn"] == "110"


@pytest.mark.asyncio
async def test_url_operation_approved_403_keeps_upstream_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_url_operation_by_id("analysis_weather_chart_image")
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        403,
        json={"result": {"status": 403, "message": "활용신청이 필요한 API 입니다."}},
        headers={"content-type": "application/json"},
    )

    async with _client_for_response(response) as client:
        with pytest.raises(ToolExecutionError) as exc_info:
            await call_operation(
                operation,
                schema.model_validate({"anal_time": "202605260000"}),
                client=client,
            )

    message = str(exc_info.value)
    assert "HTTP error from KMA APIHub URL operation: 403" in message
    assert "활용신청이 필요한 API" in message
    assert "test-api-hub-key" not in message


@pytest.mark.asyncio
async def test_amos_not_found_error_keeps_upstream_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AMOS 404 should be recoverable prose, not an opaque Not Found."""

    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_url_operation_by_id("air_amos_minute")
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        404,
        text="Not Found",
        headers={"content-type": "text/plain"},
    )

    async with _client_for_response(response) as client:
        with pytest.raises(ToolExecutionError) as exc_info:
            await call_operation(
                operation,
                schema.model_validate({"stn": "110"}),
                client=client,
            )

    message = str(exc_info.value)
    assert "AMOS" in message
    assert "404" in message
    assert "Not Found" in message
    assert "upstream" in message
    assert "METAR" in message
    assert "test-api-hub-key" not in message


@pytest.mark.asyncio
async def test_register_binds_url_tools_and_executor_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_operation(
        operation: object,
        params: object,
        *,
        client: object | None = None,
    ) -> KmaApiHubUrlOutput:
        del params, client
        op = get_url_operation_by_id("air_amos_minute")
        assert operation == op
        return KmaApiHubUrlOutput(
            operation_id=op.operation_id,
            endpoint_path=op.endpoint_path,
            approval_state=op.approval_state,
            content_type="text/plain",
            raw_format="text",
            line_count=1,
            raw_text="110 202605261820 216\n",
            status_code=200,
        )

    monkeypatch.setattr(
        "ummaya.tools.kma.apihub_url_adapter.call_operation",
        fake_call_operation,
    )
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    register(registry, executor)
    result = await executor.invoke(
        "kma_apihub_url_air_amos_minute",
        {"stn": "110"},
        request_id=str(uuid4()),
    )

    assert len(registry) == 5
    assert len(executor._adapters) == 5
    assert result.kind == "record"
    assert result.item["operation_id"] == "air_amos_minute"


@pytest.mark.asyncio
async def test_executor_marks_amos_404_as_nonretryable_upstream_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AMOS 404 should reach the agent loop as a final-explainable failure."""

    async def fake_call_operation(
        operation: object,
        params: object,
        *,
        client: object | None = None,
    ) -> KmaApiHubUrlOutput:
        del operation, params, client
        request = httpx.Request("GET", "https://apihub.kma.go.kr/api/typ01/url/amos.php")
        response = httpx.Response(404, request=request, text="Not Found")
        raise ToolExecutionError(
            tool_id="kma_apihub_url_air_amos_minute",
            message="Official KMA APIHub AMOS upstream returned 404 Not Found.",
            cause=httpx.HTTPStatusError("404 Not Found", request=request, response=response),
        )

    monkeypatch.setattr(
        "ummaya.tools.kma.apihub_url_adapter.call_operation",
        fake_call_operation,
    )
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    result = await executor.invoke(
        "kma_apihub_url_air_amos_minute",
        {"stn": "110"},
        request_id=str(uuid4()),
    )

    assert result.kind == "error"
    assert result.retryable is False
    assert result.reason == "upstream_unavailable"
    assert "AMOS upstream returned 404" in result.message
