# SPDX-License-Identifier: Apache-2.0
"""Tests for generic KMA APIHub structured adapters."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from ummaya.tools.bm25_index import BM25Index
from ummaya.tools.errors import ToolExecutionError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.kma.apihub_catalog import get_operation_by_id
from ummaya.tools.kma.apihub_structured_adapter import (
    KmaApiHubStructuredOutput,
    build_tool,
    call_operation,
    input_schema_for,
    register,
)
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.search import search

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "apihub"


def _fixture(name: str) -> str:
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


def _client_for_response(response: httpx.Response) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        response.request = request
        return response

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_input_schema_excludes_auth_key_and_uses_official_param_names() -> None:
    operation = get_operation_by_id("AmmIwxxmService/getMetar")
    schema = input_schema_for(operation.operation_id)

    assert list(schema.model_fields) == ["page_no", "num_of_rows", "data_type", "icao"]
    validated = schema.model_validate({})
    assert validated.model_dump() == {
        "page_no": 1,
        "num_of_rows": 10,
        "data_type": "XML",
        "icao": "RKSI",
    }


def test_failed_live_apihub_ops_expose_precise_schema_and_tool_selection_hints() -> None:
    """The model-facing APIHub tools must explain the real parameter contract.

    These operations were selected during live TUI use and failed or were
    mis-selected when the schema/description only said "weather data".
    """
    eqk = get_operation_by_id("EqkInfoService/getEqkMsgList")
    eqk_schema = input_schema_for(eqk.operation_id).model_json_schema()
    eqk_tool = build_tool(eqk)
    assert {"from_tm_fc", "to_tm_fc"}.issubset(set(eqk_schema["required"]))
    assert "지진" in str(eqk_tool.llm_description)
    assert "earthquake" in str(eqk_tool.llm_description).lower()
    assert "3 days" in eqk_schema["properties"]["from_tm_fc"]["description"]
    assert "not for weather observations" in str(eqk_tool.llm_description).lower()

    sat = get_operation_by_id("CloudSatlitInfoService/getGk2aappsAll")
    sat_schema = input_schema_for(sat.operation_id).model_json_schema()
    sat_tool = build_tool(sat)
    assert "date_time" in sat_schema["required"]
    assert "2 days" in sat_schema["properties"]["date_time"]["description"]
    assert "satellite" in str(sat_tool.llm_description).lower()
    assert "satellite" in sat_tool.search_hint.lower()

    gts = get_operation_by_id("GtsInfoService/getSynop")
    gts_schema = input_schema_for(gts.operation_id).model_json_schema()
    gts_tool = build_tool(gts)
    assert gts.availability == "upstream_unavailable"
    assert {"tm", "stn_id"}.issubset(set(gts_schema["required"]))
    assert "default" not in gts_schema["properties"]["stn_id"]
    assert "1 day" in gts_schema["properties"]["tm"]["description"]
    assert "official GTS APIHub schema" in gts_schema["properties"]["stn_id"]["description"]
    assert "SYNOP" in str(gts_tool.llm_description)
    assert "not for earthquake" in str(gts_tool.llm_description).lower()

    metar = get_operation_by_id("AmmIwxxmService/getMetar")
    metar_schema = input_schema_for(metar.operation_id).model_json_schema()
    metar_tool = build_tool(metar)
    assert metar.availability == "upstream_unavailable"
    assert "ICAO" in metar_schema["properties"]["icao"]["description"]
    assert "RKSS" in metar_schema["properties"]["icao"]["description"]
    assert "RKPK" in metar_schema["properties"]["icao"]["description"]
    assert "aviation" in str(metar_tool.llm_description).lower()
    assert "APPLICATION_ERROR" in str(metar_tool.llm_description)

    chart = get_operation_by_id("WthrChartInfoService/getSurfaceChart")
    chart_schema = input_schema_for(chart.operation_id).model_json_schema()
    chart_tool = build_tool(chart)
    assert chart.availability == "upstream_unavailable"
    assert {"time", "code"}.issubset(set(chart_schema["properties"]))
    assert chart_schema["properties"]["time"]["pattern"] == r"^\d{8,12}$"
    assert "resultCode=99" in str(chart_tool.llm_description)

    pending = get_operation_by_id("AftnAmmService/getMetar")
    pending_tool = build_tool(pending)
    assert pending.availability == "approval_pending"
    assert "not yet enabled" in str(pending_tool.llm_description)

    air_station = get_operation_by_id("SfcMtlyInfoService/getrAirStnLstTbl")
    air_station_tool = build_tool(air_station)
    assert "historical" in str(air_station_tool.llm_description).lower()
    assert "not live airport weather" in str(air_station_tool.llm_description).lower()
    assert "METAR" not in air_station_tool.search_hint
    assert "airport current weather" not in str(air_station_tool.llm_description).lower()

    village = get_operation_by_id("VilageFcstInfoService_2.0/getUltraSrtNcst")
    village_schema = input_schema_for(village.operation_id).model_json_schema()
    assert {"base_date", "base_time"}.issubset(set(village_schema["required"]))
    assert village_schema["properties"]["base_date"]["pattern"] == r"^\d{8}$"
    assert village_schema["properties"]["base_time"]["pattern"] == r"^\d{4}$"
    assert "stale catalog sample" in village_schema["properties"]["base_date"]["description"]

    nwp = get_operation_by_id("NwpModelInfoService/getLdapsUnisAll")
    nwp_schema = input_schema_for(nwp.operation_id).model_json_schema()
    nwp_tool = build_tool(nwp)
    assert nwp.availability == "retired"
    assert "resultCode=99" in nwp_schema["properties"]["base_time"]["description"]
    assert "Do not choose this for citizen-facing current weather" in str(nwp_tool.llm_description)


@pytest.mark.asyncio
async def test_call_operation_parses_xml_success_and_injects_auth_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_operation_by_id("AmmIwxxmService/getMetar")
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        200,
        text=_fixture("metar_success.xml"),
        headers={"content-type": "application/xml"},
    )

    async with _client_for_response(response) as client:
        output = await call_operation(operation, schema.model_validate({}), client=client)

    assert output.operation_id == "AmmIwxxmService/getMetar"
    assert output.result_code == "00"
    assert output.raw_format == "xml"
    assert output.total_count == 1
    assert output.items == [
        {
            "icao": "RKSI",
            "tm": "202605240900",
            "metarMsg": "METAR RKSI 240900Z 22005KT CAVOK 20/12 Q1016",
        }
    ]
    assert response.request.url.params["authKey"] == "test-api-hub-key"
    assert response.request.url.params["icao"] == "RKSI"


@pytest.mark.asyncio
async def test_call_operation_parses_json_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_operation_by_id("EqkInfoService/getEqkMsg")
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        200,
        text=_fixture("eqk_success.json"),
        headers={"content-type": "application/json"},
    )

    async with _client_for_response(response) as client:
        output = await call_operation(
            operation,
            schema.model_validate({"from_tm_fc": "20260523", "to_tm_fc": "20260523"}),
            client=client,
        )

    assert output.raw_format == "json"
    assert output.items[0]["tmFc"] == "202605240901"
    assert output.total_count == 1


@pytest.mark.asyncio
async def test_call_operation_no_data_result_code_returns_empty_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_operation_by_id("AmmIwxxmService/getMetar")
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        200,
        text=_fixture("non_success.xml"),
        headers={"content-type": "application/xml"},
    )

    async with _client_for_response(response) as client:
        output = await call_operation(operation, schema.model_validate({}), client=client)

    assert output.result_code == "03"
    assert output.result_msg == "NO_DATA"
    assert output.items == []
    assert output.total_count is None


@pytest.mark.asyncio
async def test_call_operation_non_recoverable_result_code_raises_tool_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_operation_by_id("AmmIwxxmService/getMetar")
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        200,
        text=(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<response><header><resultCode>02</resultCode>"
            "<resultMsg>DB_ERROR</resultMsg></header></response>"
        ),
        headers={"content-type": "application/xml"},
    )

    async with _client_for_response(response) as client:
        with pytest.raises(ToolExecutionError) as exc_info:
            await call_operation(operation, schema.model_validate({}), client=client)

    assert "resultCode='02'" in str(exc_info.value)
    assert "DB_ERROR" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pending_approval_http_403_names_approval_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_operation_by_id("AmmIwxxmService/getMetar").model_copy(
        update={"approval_state": "approval_pending"}
    )
    schema = input_schema_for(operation.operation_id)
    response = httpx.Response(
        403,
        text=_fixture("authorization_error.html"),
        headers={"content-type": "text/html"},
    )

    async with _client_for_response(response) as client:
        with pytest.raises(ToolExecutionError) as exc_info:
            await call_operation(operation, schema.model_validate({}), client=client)

    message = str(exc_info.value)
    assert "HTTP error from KMA APIHub" in message
    assert "utilization approval" in message
    assert "test-api-hub-key" not in message


@pytest.mark.asyncio
async def test_register_binds_all_structured_tools_and_executor_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_operation(
        operation: object,
        params: object,
        *,
        client: object | None = None,
    ) -> KmaApiHubStructuredOutput:
        del params, client
        op = get_operation_by_id("EqkInfoService/getEqkMsg")
        assert operation == op
        return KmaApiHubStructuredOutput(
            operation_id=op.operation_id,
            service=op.service,
            operation=op.operation,
            result_code="00",
            result_msg="NORMAL_SERVICE",
            page_no=1,
            num_of_rows=10,
            total_count=1,
            items=[{"mt": 2.1}],
            raw_format="xml",
        )

    monkeypatch.setattr(
        "ummaya.tools.kma.apihub_structured_adapter.call_operation",
        fake_call_operation,
    )
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    register(registry, executor)
    result = await executor.invoke(
        "kma_apihub_eqk_info_service_get_eqk_msg",
        {"from_tm_fc": "20260526", "to_tm_fc": "20260526"},
        request_id=str(uuid4()),
    )

    assert len(registry) == 77
    assert len(executor._adapters) == 77
    assert "kma_apihub_amm_iwxxm_service_get_metar" not in registry._tools
    assert "kma_apihub_aftn_amm_service_get_metar" not in registry._tools
    assert "kma_apihub_gts_info_service_get_synop" not in registry._tools
    assert "kma_apihub_nwp_model_info_service_get_ldaps_unis_all" not in registry._tools
    assert "kma_apihub_wthr_chart_info_service_get_surface_chart" not in registry._tools
    assert result.kind == "record"
    assert result.item["operation_id"] == "EqkInfoService/getEqkMsg"
    assert result.item["items"] == [{"mt": 2.1}]


def test_register_all_preserves_specialized_kma_weather_tools() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    register_all_tools(registry, executor)

    registered_ids = set(registry._tools)
    assert {
        "kma_forecast_fetch",
        "kma_current_observation",
        "kma_short_term_forecast",
        "kma_ultra_short_term_forecast",
        "kma_apihub_url_air_metar_decoded",
        "kma_apihub_url_air_amos_minute",
        "kma_apihub_url_high_resolution_grid_point",
        "kma_apihub_url_aws_objective_analysis_grid",
        "kma_apihub_url_analysis_weather_chart_image",
    }.issubset(registered_ids)
    assert "kma_apihub_vilage_fcst_info_service_2_0_get_vilage_fcst" in registered_ids


def test_aviation_retrieval_prefers_metar_over_historical_station_lists() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    results = search(
        "김해공항 김포공항 항공기상 METAR 항공 실황",
        BM25Index({}),
        registry,
        top_k=12,
    )
    ids = [candidate.tool_id for candidate in results]

    assert "kma_apihub_url_air_metar_decoded" in ids
    assert "kma_apihub_sfc_mtly_info_service_getr_air_stn_lst_tbl" in ids
    assert ids.index("kma_apihub_url_air_metar_decoded") < ids.index(
        "kma_apihub_sfc_mtly_info_service_getr_air_stn_lst_tbl"
    )
