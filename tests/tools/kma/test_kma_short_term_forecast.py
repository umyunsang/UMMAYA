# SPDX-License-Identifier: Apache-2.0
"""Tests for ummaya.tools.kma.kma_short_term_forecast."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import httpx
import pytest
from pydantic import ValidationError

import ummaya.tools.kma.kma_short_term_forecast as short_module
from ummaya.tools.errors import ConfigurationError, ToolExecutionError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.kma.kma_short_term_forecast import (
    KMA_SHORT_TERM_FORECAST_TOOL,
    KmaShortTermForecastInput,
    KmaShortTermForecastOutput,
    _call,
    _candidate_base_slots,
    _coerce_future_base_slot,
    _coerce_recent_base_slot,
    _normalize_items,
    _parse_response,
    register,
)
from ummaya.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text())


def _make_mock_client(fixture_data: dict) -> httpx.AsyncClient:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = fixture_data
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response
    return mock_client


def _make_mock_client_sequence(payloads: list[dict]) -> httpx.AsyncClient:
    responses = []
    for fixture_data in payloads:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = fixture_data
        mock_response.raise_for_status = MagicMock()
        responses.append(mock_response)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = responses
    return mock_client


def _no_data_payload(message: str = "NO_DATA") -> dict:
    return {
        "response": {
            "header": {"resultCode": "03", "resultMsg": message},
            "body": {},
        }
    }


# ---------------------------------------------------------------------------
# TestKmaShortTermForecastInput
# ---------------------------------------------------------------------------


class TestKmaShortTermForecastInput:
    def test_valid_construction(self):
        params = KmaShortTermForecastInput(
            base_date="20260414",
            base_time="0800",
            nx=61,
            ny=126,
        )
        assert params.base_date == "20260414"
        assert params.base_time == "0800"
        assert params.nx == 61
        assert params.ny == 126
        assert params.num_of_rows == 290
        assert params.page_no == 1
        assert params.data_type == "XML"

    def test_all_valid_base_times(self):
        """All eight published base times must be accepted."""
        valid_times = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]
        for t in valid_times:
            params = KmaShortTermForecastInput(base_date="20260414", base_time=t, nx=61, ny=126)
            assert params.base_time == t

    def test_invalid_base_time_raises(self):
        """A time not in the published schedule must raise ValidationError."""
        with pytest.raises(ValidationError):
            KmaShortTermForecastInput(base_date="20260414", base_time="0600", nx=61, ny=126)

    def test_invalid_base_date_format_raises(self):
        with pytest.raises(ValidationError):
            KmaShortTermForecastInput(base_date="2026-04-14", base_time="0800", nx=61, ny=126)

    def test_grid_bounds_nx_min(self):
        params = KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=1, ny=1)
        assert params.nx == 1

    def test_grid_bounds_nx_max(self):
        params = KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=149, ny=253)
        assert params.nx == 149

    def test_grid_bounds_nx_too_large(self):
        with pytest.raises(ValidationError):
            KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=150, ny=126)

    def test_grid_bounds_ny_too_large(self):
        with pytest.raises(ValidationError):
            KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=61, ny=254)

    def test_custom_num_of_rows(self):
        params = KmaShortTermForecastInput(
            base_date="20260414", base_time="0800", nx=61, ny=126, num_of_rows=50
        )
        assert params.num_of_rows == 50

    def test_num_of_rows_minimum(self):
        with pytest.raises(ValidationError):
            KmaShortTermForecastInput(
                base_date="20260414", base_time="0800", nx=61, ny=126, num_of_rows=0
            )


# ---------------------------------------------------------------------------
# TestNormalizeItems
# ---------------------------------------------------------------------------


class TestNormalizeItems:
    def test_list_input_returned_as_is(self):
        items = [{"a": 1}, {"a": 2}]
        result = _normalize_items(items)
        assert result == items

    def test_dict_input_wrapped_in_list(self):
        """Single-item dict must be wrapped in a list."""
        item = {"category": "TMP", "fcstValue": "12"}
        result = _normalize_items(item)
        assert result == [item]

    def test_empty_string_returns_empty_list(self):
        assert _normalize_items("") == []

    def test_none_returns_empty_list(self):
        assert _normalize_items(None) == []

    def test_non_dict_rows_filtered_out(self):
        items = [{"a": 1}, "unexpected_string", {"b": 2}]
        result = _normalize_items(items)
        assert result == [{"a": 1}, {"b": 2}]


class TestBaseSlotRecovery:
    def test_future_midnight_slot_clamps_to_previous_day_latest_published_slot(self):
        kst = ZoneInfo("Asia/Seoul")
        base_date, base_time = _coerce_future_base_slot(
            "20260525",
            "2300",
            now=datetime(2026, 5, 25, 0, 9, tzinfo=kst),
        )

        assert (base_date, base_time) == ("20260524", "2300")

    def test_candidate_slots_cross_midnight_after_future_2300(self):
        slots = _candidate_base_slots("20260525", "2300")

        assert slots[-1] == ("20260524", "2300")

    def test_stale_slot_clamps_to_latest_published_slot(self):
        kst = ZoneInfo("Asia/Seoul")

        base_date, base_time = _coerce_recent_base_slot(
            "20240617",
            "1400",
            now=datetime(2026, 6, 20, 11, 4, tzinfo=kst),
        )

        assert (base_date, base_time) == ("20260620", "0800")

    def test_invalid_calendar_slot_clamps_to_latest_published_slot(self):
        kst = ZoneInfo("Asia/Seoul")

        base_date, base_time = _coerce_recent_base_slot(
            "20260230",
            "1400",
            now=datetime(2026, 6, 20, 11, 4, tzinfo=kst),
        )

        assert (base_date, base_time) == ("20260620", "0800")


# ---------------------------------------------------------------------------
# TestParseResponse
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_success(self):
        """Load the success fixture and verify output structure."""
        data = _load_fixture("kma_short_term_forecast_success.json")
        out = _parse_response(data)
        assert isinstance(out, KmaShortTermForecastOutput)
        assert out.total_count == 14
        assert len(out.items) == 14

        tmp_item = next(i for i in out.items if i.category == "TMP")
        assert tmp_item.base_date == "20260414"
        assert tmp_item.base_time == "0800"
        assert tmp_item.fcst_date == "20260414"
        assert tmp_item.fcst_time == "0900"
        assert tmp_item.fcst_value == "12"
        assert tmp_item.nx == 61
        assert tmp_item.ny == 126

    def test_single_item_response(self):
        """A single-item dict must be normalized to a one-element list."""
        data = _load_fixture("kma_short_term_forecast_single_item.json")
        out = _parse_response(data)
        assert len(out.items) == 1
        assert out.items[0].category == "TMP"

    def test_empty_response_returns_empty_items(self):
        """An items='' response must return an empty items list without error."""
        data = _load_fixture("kma_short_term_forecast_empty.json")
        out = _parse_response(data)
        assert out.total_count == 0
        assert out.items == []

    def test_error_code_raises_tool_execution_error(self):
        """An error result code must raise ToolExecutionError."""
        data = _load_fixture("kma_short_term_forecast_error.json")
        with pytest.raises(ToolExecutionError) as exc_info:
            _parse_response(data)
        assert "03" in str(exc_info.value)

    def test_all_categories_present(self):
        """All 14 forecast categories in the success fixture must be parsed."""
        data = _load_fixture("kma_short_term_forecast_success.json")
        out = _parse_response(data)
        categories = {item.category for item in out.items}
        expected = {
            "TMP",
            "UUU",
            "VVV",
            "VEC",
            "WSD",
            "SKY",
            "PTY",
            "POP",
            "WAV",
            "PCP",
            "REH",
            "SNO",
            "TMN",
            "TMX",
        }
        assert categories == expected

    def test_string_forecast_values_preserved(self):
        """String values like '강수없음' and '적설없음' must be stored verbatim."""
        data = _load_fixture("kma_short_term_forecast_success.json")
        out = _parse_response(data)
        pcp_item = next(i for i in out.items if i.category == "PCP")
        assert pcp_item.fcst_value == "강수없음"
        sno_item = next(i for i in out.items if i.category == "SNO")
        assert sno_item.fcst_value == "적설없음"


# ---------------------------------------------------------------------------
# TestCall
# ---------------------------------------------------------------------------


class TestCall:
    @pytest.mark.asyncio
    async def test_success_flow(self, monkeypatch):
        """_call with a mocked httpx client returns a dict matching output schema."""
        monkeypatch.delenv("UMMAYA_KMA_API_HUB_AUTH_KEY", raising=False)
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key-abc")
        fixture_data = _load_fixture("kma_short_term_forecast_success.json")
        mock_client = _make_mock_client(fixture_data)

        params = KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=61, ny=126)
        result = await _call(params, client=mock_client)

        assert isinstance(result, dict)
        assert result["total_count"] == 14
        assert isinstance(result["items"], list)
        assert len(result["items"]) == 14
        query_params = mock_client.get.await_args.kwargs["params"]
        assert "dataType" not in query_params
        assert "_type" not in query_params

    @pytest.mark.asyncio
    async def test_api_hub_key_uses_auth_key_and_api_hub_endpoint(self, monkeypatch):
        """KMA API Hub credentials must use authKey on the API Hub endpoint."""
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "api-hub-key")
        monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
        fixture_data = _load_fixture("kma_short_term_forecast_success.json")
        mock_client = _make_mock_client(fixture_data)

        params = KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=61, ny=126)
        await _call(params, client=mock_client)

        called_url = mock_client.get.await_args.args[0]
        query_params = mock_client.get.await_args.kwargs["params"]
        assert called_url == (
            "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst"
        )
        assert query_params["authKey"] == "api-hub-key"
        assert "serviceKey" not in query_params

    @pytest.mark.asyncio
    async def test_missing_api_key(self, monkeypatch):
        """Absent KMA API Hub key raises ConfigurationError."""
        monkeypatch.delenv("UMMAYA_KMA_API_HUB_AUTH_KEY", raising=False)
        monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)

        params = KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=61, ny=126)
        with pytest.raises(ConfigurationError):
            await _call(params)

    @pytest.mark.asyncio
    async def test_xml_content_type_parses(self, monkeypatch):
        """Official XML response envelopes must parse successfully."""
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key-abc")

        xml_body = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL_SERVICE</resultMsg></header>
  <body>
    <items>
      <item>
        <baseDate>20260414</baseDate><baseTime>0800</baseTime>
        <fcstDate>20260414</fcstDate><fcstTime>0900</fcstTime>
        <category>TMP</category><fcstValue>12</fcstValue><nx>61</nx><ny>126</ny>
      </item>
    </items>
    <numOfRows>1</numOfRows><pageNo>1</pageNo><totalCount>1</totalCount>
  </body>
</response>"""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml; charset=UTF-8"}
        mock_response.text = xml_body
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        params = KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=61, ny=126)
        result = await _call(params, client=mock_client)

        assert result["total_count"] == 1
        assert result["items"][0]["category"] == "TMP"

    @pytest.mark.asyncio
    async def test_json_data_type_uses_json_selectors(self, monkeypatch):
        """JSON remains available when explicitly requested."""
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key-abc")
        fixture_data = _load_fixture("kma_short_term_forecast_success.json")
        mock_client = _make_mock_client(fixture_data)

        params = KmaShortTermForecastInput(
            base_date="20260414",
            base_time="0800",
            nx=61,
            ny=126,
            data_type="JSON",
        )
        await _call(params, client=mock_client)

        query_params = mock_client.get.await_args.kwargs["params"]
        assert query_params["dataType"] == "JSON"
        assert query_params["_type"] == "json"

    @pytest.mark.asyncio
    async def test_no_data_retries_previous_base_slot(self, monkeypatch):
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key-abc")
        monkeypatch.setattr(short_module, "_coerce_recent_base_slot", _preserve_requested_slot)
        fixture_data = _load_fixture("kma_short_term_forecast_success.json")
        mock_client = _make_mock_client_sequence([_no_data_payload(), fixture_data])

        params = KmaShortTermForecastInput(base_date="20260414", base_time="1100", nx=61, ny=126)
        result = await _call(params, client=mock_client)

        assert result["total_count"] == 14
        assert mock_client.get.await_count == 2
        call_params = [call.kwargs["params"] for call in mock_client.get.await_args_list]
        assert [params["base_time"] for params in call_params] == ["1100", "0800"]

    @pytest.mark.asyncio
    async def test_stale_base_slot_is_coerced_before_request(self, monkeypatch):
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key-abc")
        fixture_data = _load_fixture("kma_short_term_forecast_success.json")
        mock_client = _make_mock_client(fixture_data)

        def fake_coerce_recent_base_slot(
            base_date: str,
            base_time: str,
        ) -> tuple[str, str]:
            assert (base_date, base_time) == ("20240617", "1400")
            return "20260620", "0800"

        monkeypatch.setattr(short_module, "_coerce_recent_base_slot", fake_coerce_recent_base_slot)

        params = KmaShortTermForecastInput(base_date="20240617", base_time="1400", nx=97, ny=75)
        await _call(params, client=mock_client)

        query_params = mock_client.get.await_args.kwargs["params"]
        assert query_params["base_date"] == "20260620"
        assert query_params["base_time"] == "0800"

    @pytest.mark.asyncio
    async def test_http_status_error(self, monkeypatch):
        """An HTTP 500 must raise ToolExecutionError."""
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key-abc")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        params = KmaShortTermForecastInput(base_date="20260414", base_time="0800", nx=61, ny=126)
        with pytest.raises(ToolExecutionError) as exc_info:
            await _call(params, client=mock_client)
        assert "500" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestToolDefinition
# ---------------------------------------------------------------------------


def _preserve_requested_slot(
    base_date: str,
    base_time: str,
) -> tuple[str, str]:
    return base_date, base_time


class TestToolDefinition:
    def test_tool_id(self):
        assert KMA_SHORT_TERM_FORECAST_TOOL.id == "kma_short_term_forecast"

    def test_is_core_true(self):
        assert KMA_SHORT_TERM_FORECAST_TOOL.is_core is True

    def test_provider(self):
        assert KMA_SHORT_TERM_FORECAST_TOOL.ministry == "KMA"

    def test_cache_ttl(self):
        assert KMA_SHORT_TERM_FORECAST_TOOL.cache_ttl_seconds == 1800

    # test_not_personal_data removed in Epic δ #2295 (is_personal_data deleted).

    def test_input_schema(self):
        assert KMA_SHORT_TERM_FORECAST_TOOL.input_schema is KmaShortTermForecastInput

    def test_output_schema(self):
        assert KMA_SHORT_TERM_FORECAST_TOOL.output_schema is KmaShortTermForecastOutput

    def test_search_hint_bilingual(self):
        hint = KMA_SHORT_TERM_FORECAST_TOOL.search_hint
        assert "단기예보" in hint
        assert "forecast" in hint


# ---------------------------------------------------------------------------
# TestRegister
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_adds_to_registry_and_executor(self):
        """register() wires the tool into both registry and executor."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        register(registry, executor)

        assert "kma_short_term_forecast" in registry
        assert registry.lookup("kma_short_term_forecast") is KMA_SHORT_TERM_FORECAST_TOOL
        assert "kma_short_term_forecast" in executor._adapters
