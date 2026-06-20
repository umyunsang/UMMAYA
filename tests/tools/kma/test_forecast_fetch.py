# SPDX-License-Identifier: Apache-2.0
"""Tests for ummaya.tools.kma.forecast_fetch (T046/T047)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

import ummaya.tools.kma.forecast_fetch as forecast_module
from ummaya.tools.kma.forecast_fetch import (
    KMA_FORECAST_FETCH_TOOL,
    KmaForecastFetchInput,
    _candidate_base_slots,
    _coerce_recent_base_slot,
    _fetch,
    _normalize_items,
    _parse_forecast_items,
    _previous_base_slot,
    register,
)
from ummaya.tools.models import LookupError, LookupTimeseries  # noqa: A004

_FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "kma"


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
# Input validation
# ---------------------------------------------------------------------------


class TestKmaForecastFetchInput:
    def test_valid_construction(self) -> None:
        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="0800",
        )
        assert inp.lat == pytest.approx(37.5665)
        assert inp.lon == pytest.approx(127.0495)
        assert inp.base_date == "20260416"
        assert inp.base_time == "0800"

    def test_all_valid_base_times(self) -> None:
        for bt in ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]:
            inp = KmaForecastFetchInput(lat=37.0, lon=127.0, base_date="20260416", base_time=bt)
            assert inp.base_time == bt

    @pytest.mark.asyncio
    async def test_invalid_base_time_returns_lookup_error(self) -> None:
        """Invalid base_time is accepted by the model; handler returns LookupError."""
        inp = KmaForecastFetchInput(lat=37.0, lon=127.0, base_date="20260416", base_time="0600")
        result = await _fetch(inp)
        assert isinstance(result, LookupError)
        assert result.reason == "invalid_params"

    def test_invalid_base_date_pattern_raises(self) -> None:
        with pytest.raises(ValidationError):
            KmaForecastFetchInput(lat=37.0, lon=127.0, base_date="2026-04-16", base_time="0800")

    def test_lat_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            KmaForecastFetchInput(lat=100.0, lon=127.0, base_date="20260416", base_time="0800")

    def test_lon_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            KmaForecastFetchInput(lat=37.0, lon=200.0, base_date="20260416", base_time="0800")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestNormalizeItems:
    def test_dict_input_becomes_list(self) -> None:
        item = {"category": "TMP", "fcstValue": "12"}
        assert _normalize_items(item) == [item]

    def test_list_passthrough(self) -> None:
        items = [{"category": "TMP"}, {"category": "SKY"}]
        assert _normalize_items(items) == items

    def test_none_returns_empty(self) -> None:
        assert _normalize_items(None) == []

    def test_empty_list_returns_empty(self) -> None:
        assert _normalize_items([]) == []


class TestParseForecastItems:
    def test_groups_by_time_slot(self) -> None:
        raw = [
            {
                "baseDate": "20260416",
                "baseTime": "0800",
                "nx": "60",
                "ny": "127",
                "category": "TMP",
                "fcstDate": "20260416",
                "fcstTime": "0900",
                "fcstValue": "14",
            },
            {
                "baseDate": "20260416",
                "baseTime": "0800",
                "nx": "60",
                "ny": "127",
                "category": "POP",
                "fcstDate": "20260416",
                "fcstTime": "0900",
                "fcstValue": "10",
            },
            {
                "baseDate": "20260416",
                "baseTime": "0800",
                "nx": "60",
                "ny": "127",
                "category": "TMP",
                "fcstDate": "20260416",
                "fcstTime": "1000",
                "fcstValue": "16",
            },
        ]
        points = _parse_forecast_items(raw)
        assert len(points) == 2
        first = points[0]
        assert first["timestamp_iso"] == "2026-04-16T09:00:00"
        assert first["temperature_c"] == pytest.approx(14.0)
        assert first["pop_pct"] == 10
        assert first["sky_code"] is None

    def test_empty_input_returns_empty(self) -> None:
        assert _parse_forecast_items([]) == []


class TestBaseSlotRecovery:
    def test_previous_slot_same_day(self) -> None:
        assert _previous_base_slot("20260416", "1100") == ("20260416", "0800")

    def test_previous_slot_wraps_to_previous_day(self) -> None:
        assert _previous_base_slot("20260416", "0200") == ("20260415", "2300")

    def test_candidate_slots_walk_back_in_order(self) -> None:
        assert _candidate_base_slots("20260416", "0200", max_attempts=3) == [
            ("20260416", "0200"),
            ("20260415", "2300"),
            ("20260415", "2000"),
        ]

    def test_stale_slot_clamps_to_latest_published_slot(self) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        base_date, base_time = _coerce_recent_base_slot(
            "20260416",
            "0800",
            now=datetime(2026, 6, 20, 11, 4, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        assert (base_date, base_time) == ("20260620", "0800")


# ---------------------------------------------------------------------------
# _fetch: happy path
# ---------------------------------------------------------------------------


class TestFetch:
    @pytest.mark.asyncio
    async def test_happy_path_returns_timeseries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UMMAYA_KMA_API_HUB_AUTH_KEY", raising=False)
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key")
        fixture = _load_fixture("forecast_fetch_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="0800",
        )
        result = await _fetch(inp, client=mock_client)

        assert isinstance(result, LookupTimeseries)
        assert result.kind == "timeseries"
        assert result.interval == "hour"
        assert len(result.points) > 0
        # All points must have the timestamp_iso key
        for pt in result.points:
            assert "timestamp_iso" in pt
            assert "interval" in pt
        # At least one point must have temperature (not all slots have TMP;
        # TMN/TMX slots may lack it)
        temps = [pt["temperature_c"] for pt in result.points if pt["temperature_c"] is not None]
        assert len(temps) > 0, "No point had a temperature_c value"
        query_params = mock_client.get.await_args.kwargs["params"]
        assert "dataType" not in query_params
        assert "_type" not in query_params

    @pytest.mark.asyncio
    async def test_api_hub_key_uses_auth_key_and_api_hub_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "api-hub-key")
        monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
        fixture = _load_fixture("forecast_fetch_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="0800",
        )
        result = await _fetch(inp, client=mock_client)

        assert isinstance(result, LookupTimeseries)
        called_url = mock_client.get.await_args.args[0]
        query_params = mock_client.get.await_args.kwargs["params"]
        assert called_url == (
            "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst"
        )
        assert query_params["authKey"] == "api-hub-key"
        assert "serviceKey" not in query_params

    @pytest.mark.asyncio
    async def test_xml_response_returns_timeseries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Official XML response envelopes are decoded before timeseries aggregation."""
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key")

        xml_body = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL_SERVICE</resultMsg></header>
  <body>
    <items>
      <item>
        <baseDate>20260416</baseDate><baseTime>0800</baseTime>
        <fcstDate>20260416</fcstDate><fcstTime>0900</fcstTime>
        <category>TMP</category><fcstValue>14</fcstValue><nx>60</nx><ny>127</ny>
      </item>
      <item>
        <baseDate>20260416</baseDate><baseTime>0800</baseTime>
        <fcstDate>20260416</fcstDate><fcstTime>0900</fcstTime>
        <category>POP</category><fcstValue>10</fcstValue><nx>60</nx><ny>127</ny>
      </item>
    </items>
    <numOfRows>2</numOfRows><pageNo>1</pageNo><totalCount>2</totalCount>
  </body>
</response>"""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml; charset=UTF-8"}
        mock_response.text = xml_body
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="0800",
        )
        result = await _fetch(inp, client=mock_client)

        assert isinstance(result, LookupTimeseries)
        assert len(result.points) == 1
        assert result.points[0]["temperature_c"] == 14.0
        assert result.points[0]["pop_pct"] == 10

    @pytest.mark.asyncio
    async def test_out_of_domain_coords_returns_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key")
        inp = KmaForecastFetchInput(
            lat=5.0,  # outside KMA domain (< 22°)
            lon=127.0,
            base_date="20260416",
            base_time="0800",
        )
        # No mock client needed — domain check happens before HTTP call
        result = await _fetch(inp)

        assert isinstance(result, LookupError)
        assert result.reason == "out_of_domain"

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UMMAYA_KMA_API_HUB_AUTH_KEY", raising=False)
        monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="0800",
        )
        from ummaya.tools.errors import ConfigurationError

        with pytest.raises(ConfigurationError):
            await _fetch(inp)

    @pytest.mark.asyncio
    async def test_upstream_error_result_code_returns_lookup_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "bad-key")
        error_payload = {
            "response": {
                "header": {"resultCode": "10", "resultMsg": "APPLICATION_ERROR"},
                "body": {},
            }
        }
        mock_client = _make_mock_client(error_payload)

        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="0800",
        )
        result = await _fetch(inp, client=mock_client)

        assert isinstance(result, LookupError)
        assert result.reason == "upstream_unavailable"
        assert result.upstream_code == "10"

    @pytest.mark.asyncio
    async def test_http_rate_limit_error_includes_upstream_body(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key")
        request = httpx.Request("GET", "https://apihub.kma.go.kr/test")
        mock_response = httpx.Response(
            status_code=429,
            text="API rate limit exceeded",
            request=request,
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="0800",
        )
        result = await _fetch(inp, client=mock_client)

        assert isinstance(result, LookupError)
        assert result.reason == "upstream_unavailable"
        assert "429" in result.message
        assert "API rate limit exceeded" in result.message

    @pytest.mark.asyncio
    async def test_no_data_retries_previous_base_slot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key")
        monkeypatch.setattr(forecast_module, "_coerce_recent_base_slot", _preserve_requested_slot)
        fixture = _load_fixture("forecast_fetch_happy.json")
        mock_client = _make_mock_client_sequence([_no_data_payload(), fixture])

        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="1100",
        )
        result = await _fetch(inp, client=mock_client)

        assert isinstance(result, LookupTimeseries)
        assert mock_client.get.await_count == 2
        call_params = [call.kwargs["params"] for call in mock_client.get.await_args_list]
        assert [params["base_time"] for params in call_params] == ["1100", "0800"]
        assert all(point["base_time"] == "0800" for point in result.points)

    @pytest.mark.asyncio
    async def test_no_data_exhaustion_returns_retryable_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "test-key")
        monkeypatch.setattr(forecast_module, "_coerce_recent_base_slot", _preserve_requested_slot)
        mock_client = _make_mock_client_sequence([_no_data_payload()] * 8)

        inp = KmaForecastFetchInput(
            lat=37.5665,
            lon=127.0495,
            base_date="20260416",
            base_time="0200",
        )
        result = await _fetch(inp, client=mock_client)

        assert isinstance(result, LookupError)
        assert result.reason == "upstream_unavailable"
        assert result.upstream_code == "03"
        assert result.retryable is True
        assert mock_client.get.await_count == 8
        assert "20260415 2300" in result.message


# ---------------------------------------------------------------------------
# Tool definition & registration
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_tool_id(self) -> None:
        assert KMA_FORECAST_FETCH_TOOL.id == "kma_forecast_fetch"

    # test_requires_auth_true / test_is_personal_data_false removed in Epic δ #2295
    # — requires_auth / is_personal_data deleted from GovAPITool (Constitution § II).

    def test_is_concurrency_safe_true(self) -> None:
        assert KMA_FORECAST_FETCH_TOOL.is_concurrency_safe is True

    def test_cache_ttl_zero(self) -> None:
        assert KMA_FORECAST_FETCH_TOOL.cache_ttl_seconds == 0

    def test_search_hint_bilingual(self) -> None:
        hint = KMA_FORECAST_FETCH_TOOL.search_hint
        # Must contain Korean weather keywords
        assert "단기예보" in hint
        assert "forecast" in hint.lower()


class TestRegister:
    def test_register_adds_to_registry(self) -> None:
        from ummaya.tools.executor import ToolExecutor
        from ummaya.tools.registry import ToolRegistry

        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register(registry, executor)
        assert "kma_forecast_fetch" in registry
        assert "kma_forecast_fetch" in executor._adapters


def _preserve_requested_slot(base_date: str, base_time: str) -> tuple[str, str]:
    return base_date, base_time
