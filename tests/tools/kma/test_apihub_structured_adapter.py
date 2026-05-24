# SPDX-License-Identifier: Apache-2.0
"""Tests for generic KMA APIHub structured adapters."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from ummaya.tools.errors import ToolExecutionError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.kma.apihub_catalog import get_operation_by_id
from ummaya.tools.kma.apihub_structured_adapter import (
    KmaApiHubStructuredOutput,
    call_operation,
    input_schema_for,
    register,
)
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry

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
        output = await call_operation(operation, schema.model_validate({}), client=client)

    assert output.raw_format == "json"
    assert output.items[0]["tmFc"] == "202605240901"
    assert output.total_count == 1


@pytest.mark.asyncio
async def test_call_operation_non_success_result_code_raises_tool_error(
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
        with pytest.raises(ToolExecutionError) as exc_info:
            await call_operation(operation, schema.model_validate({}), client=client)

    assert "resultCode='03'" in str(exc_info.value)
    assert "NO_DATA" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pending_approval_http_403_names_approval_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-api-hub-key")
    operation = get_operation_by_id("AmmIwxxmService/getMetar")
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
        op = get_operation_by_id("AmmIwxxmService/getMetar")
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
            items=[{"icao": "RKSI"}],
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
        "kma_apihub_amm_iwxxm_service_get_metar",
        {},
        request_id=str(uuid4()),
    )

    assert len(registry) == 85
    assert len(executor._adapters) == 85
    assert result.kind == "record"
    assert result.item["operation_id"] == "AmmIwxxmService/getMetar"
    assert result.item["items"] == [{"icao": "RKSI"}]


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
    }.issubset(registered_ids)
    assert "kma_apihub_vilage_fcst_info_service_2_0_get_vilage_fcst" in registered_ids
