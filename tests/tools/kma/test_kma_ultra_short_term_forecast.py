# SPDX-License-Identifier: Apache-2.0
"""Tests for ummaya.tools.kma.kma_ultra_short_term_forecast."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

import ummaya.tools.kma.kma_ultra_short_term_forecast as ultra_module
from ummaya.tools.errors import ConfigurationError, ToolExecutionError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.kma.kma_ultra_short_term_forecast import (
    KMA_ULTRA_SHORT_TERM_FORECAST_TOOL,
    KmaUltraShortTermForecastInput,
    KmaUltraShortTermForecastOutput,
    _call,
    _parse_response,
    register,
)
from ummaya.tools.models import LookupRecord
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


# ---------------------------------------------------------------------------
# TestKmaUltraShortTermForecastInput
# ---------------------------------------------------------------------------


class TestKmaUltraShortTermForecastInput:
    def test_valid_construction(self):
        params = KmaUltraShortTermForecastInput(
            base_date="20260414",
            base_time="0830",
            nx=61,
            ny=126,
        )
        assert params.base_date == "20260414"
        assert params.base_time == "0830"
        assert params.nx == 61
        assert params.ny == 126
        assert params.num_of_rows == 60
        assert params.page_no == 1
        assert params.data_type == "JSON"

    def test_valid_clock_times(self):
        """Any valid HHMM clock time must be accepted."""
        for t in ("0000", "0630", "0830", "1500", "1515", "1529", "2359"):
            params = KmaUltraShortTermForecastInput(
                base_date="20260414", base_time=t, nx=61, ny=126
            )
            assert params.base_time == t

    def test_invalid_clock_time_raises(self):
        """base_time must be a valid HHMM clock time."""
        with pytest.raises(ValidationError):
            KmaUltraShortTermForecastInput(base_date="20260414", base_time="2460", nx=61, ny=126)

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError):
            KmaUltraShortTermForecastInput(base_date="20260414", base_time="08:30", nx=61, ny=126)

    def test_invalid_base_date_format_raises(self):
        with pytest.raises(ValidationError):
            KmaUltraShortTermForecastInput(base_date="2026-04-14", base_time="0830", nx=61, ny=126)

    def test_grid_bounds_nx_too_large(self):
        with pytest.raises(ValidationError):
            KmaUltraShortTermForecastInput(base_date="20260414", base_time="0830", nx=150, ny=126)

    def test_grid_bounds_ny_too_large(self):
        with pytest.raises(ValidationError):
            KmaUltraShortTermForecastInput(base_date="20260414", base_time="0830", nx=61, ny=254)

    def test_num_of_rows_minimum(self):
        with pytest.raises(ValidationError):
            KmaUltraShortTermForecastInput(
                base_date="20260414", base_time="0830", nx=61, ny=126, num_of_rows=0
            )


# ---------------------------------------------------------------------------
# TestParseResponse
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_success(self):
        """Load the success fixture and verify output structure."""
        data = _load_fixture("kma_ultra_short_term_success.json")
        out = _parse_response(data)
        assert isinstance(out, KmaUltraShortTermForecastOutput)
        assert out.total_count == 10
        assert len(out.items) == 10

        t1h_item = next(i for i in out.items if i.category == "T1H")
        assert t1h_item.base_date == "20260414"
        assert t1h_item.base_time == "0830"
        assert t1h_item.fcst_date == "20260414"
        assert t1h_item.fcst_time == "0900"
        assert t1h_item.fcst_value == "13"
        assert t1h_item.nx == 61
        assert t1h_item.ny == 126

    def test_empty_response_returns_empty_items(self):
        """An items='' response must return an empty items list."""
        data = _load_fixture("kma_ultra_short_term_empty.json")
        out = _parse_response(data)
        assert out.total_count == 0
        assert out.items == []

    def test_error_code_raises_tool_execution_error(self):
        """A non-'00' result code must raise ToolExecutionError."""
        error_payload = {
            "response": {
                "header": {"resultCode": "03", "resultMsg": "NO_DATA"},
                "body": None,
            }
        }
        with pytest.raises(ToolExecutionError) as exc_info:
            _parse_response(error_payload)
        assert "03" in str(exc_info.value)

    def test_single_item_normalized(self):
        """A single-item dict must be normalized to a one-element list."""
        single_item_payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
                "body": {
                    "totalCount": 1,
                    "items": {
                        "item": {
                            "baseDate": "20260414",
                            "baseTime": "0830",
                            "fcstDate": "20260414",
                            "fcstTime": "0900",
                            "nx": 61,
                            "ny": 126,
                            "category": "T1H",
                            "fcstValue": "13",
                        }
                    },
                },
            }
        }
        out = _parse_response(single_item_payload)
        assert len(out.items) == 1
        assert out.items[0].category == "T1H"

    def test_all_categories_present(self):
        """All categories in the success fixture must be parsed correctly."""
        data = _load_fixture("kma_ultra_short_term_success.json")
        out = _parse_response(data)
        categories = {item.category for item in out.items}
        expected = {"T1H", "RN1", "SKY", "UUU", "VVV", "REH", "PTY", "LGT", "VEC", "WSD"}
        assert categories == expected


# ---------------------------------------------------------------------------
# TestCall
# ---------------------------------------------------------------------------


class TestCall:
    @pytest.mark.asyncio
    async def test_success_flow(self, monkeypatch):
        """_call with a mocked httpx client returns a dict matching output schema."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-abc")
        fixture_data = _load_fixture("kma_ultra_short_term_success.json")
        mock_client = _make_mock_client(fixture_data)

        params = KmaUltraShortTermForecastInput(
            base_date="20260414", base_time="0830", nx=61, ny=126
        )
        result = await _call(params, client=mock_client)

        assert isinstance(result, dict)
        assert result["total_count"] == 10
        assert isinstance(result["items"], list)
        assert len(result["items"]) == 10

    @pytest.mark.asyncio
    async def test_missing_api_key(self, monkeypatch):
        """Absent UMMAYA_DATA_GO_KR_API_KEY raises ConfigurationError."""
        monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)

        params = KmaUltraShortTermForecastInput(
            base_date="20260414", base_time="0830", nx=61, ny=126
        )
        with pytest.raises(ConfigurationError):
            await _call(params)

    @pytest.mark.asyncio
    async def test_xml_content_type_guard(self, monkeypatch):
        """An XML content-type response must raise ToolExecutionError."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-abc")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml; charset=UTF-8"}
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        params = KmaUltraShortTermForecastInput(
            base_date="20260414", base_time="0830", nx=61, ny=126
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            await _call(params, client=mock_client)
        assert "XML" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_xml_data_type_raises(self, monkeypatch):
        """Setting data_type='XML' must raise ToolExecutionError immediately."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-abc")

        params = KmaUltraShortTermForecastInput(
            base_date="20260414", base_time="0830", nx=61, ny=126, data_type="XML"
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            await _call(params)
        assert "XML" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_status_error(self, monkeypatch):
        """An HTTP 500 must raise ToolExecutionError."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-abc")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        params = KmaUltraShortTermForecastInput(
            base_date="20260414", base_time="0830", nx=61, ny=126
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            await _call(params, client=mock_client)
        assert "500" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestToolDefinition
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_tool_id(self):
        assert KMA_ULTRA_SHORT_TERM_FORECAST_TOOL.id == "kma_ultra_short_term_forecast"

    def test_is_core_true(self):
        assert KMA_ULTRA_SHORT_TERM_FORECAST_TOOL.is_core is True

    def test_provider(self):
        assert KMA_ULTRA_SHORT_TERM_FORECAST_TOOL.ministry == "KMA"

    def test_cache_ttl(self):
        assert KMA_ULTRA_SHORT_TERM_FORECAST_TOOL.cache_ttl_seconds == 600

    # test_not_personal_data removed in Epic δ #2295 (is_personal_data deleted).

    def test_input_schema(self):
        assert KMA_ULTRA_SHORT_TERM_FORECAST_TOOL.input_schema is KmaUltraShortTermForecastInput

    def test_output_schema(self):
        assert KMA_ULTRA_SHORT_TERM_FORECAST_TOOL.output_schema is KmaUltraShortTermForecastOutput

    def test_search_hint_bilingual(self):
        hint = KMA_ULTRA_SHORT_TERM_FORECAST_TOOL.search_hint
        assert "초단기예보" in hint
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

        assert "kma_ultra_short_term_forecast" in registry
        assert (
            registry.lookup("kma_ultra_short_term_forecast") is KMA_ULTRA_SHORT_TERM_FORECAST_TOOL
        )
        assert "kma_ultra_short_term_forecast" in executor._adapters

    @pytest.mark.asyncio
    async def test_registered_adapter_returns_lookup_record_envelope(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Regression: registered find adapters must return a LookupOutput envelope."""

        async def fake_call(params: KmaUltraShortTermForecastInput) -> dict[str, object]:
            return {"total_count": 0, "items": []}

        monkeypatch.setattr(ultra_module, "_call", fake_call)
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register(registry, executor)

        adapter = executor._adapters["kma_ultra_short_term_forecast"]
        result = await adapter(
            KmaUltraShortTermForecastInput(base_date="20260414", base_time="0830", nx=61, ny=126)
        )

        assert result == {"kind": "record", "item": {"total_count": 0, "items": []}}
        normalized = LookupRecord.model_validate(
            {
                **result,
                "meta": {
                    "source": "kma_ultra_short_term_forecast",
                    "fetched_at": "2026-05-18T12:00:00+09:00",
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                    "elapsed_ms": 1,
                },
            }
        )
        assert normalized.kind == "record"

    @pytest.mark.asyncio
    async def test_dispatch_accepts_registered_lookup_record_envelope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Legacy direct dispatch accepts the registered find adapter envelope."""

        async def fake_call(params: KmaUltraShortTermForecastInput) -> dict[str, object]:
            return {"total_count": 0, "items": []}

        monkeypatch.setattr(ultra_module, "_call", fake_call)
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register(registry, executor)

        result = await executor.dispatch(
            "kma_ultra_short_term_forecast",
            json.dumps({"base_date": "20260414", "base_time": "0830", "nx": 61, "ny": 126}),
            tool_call_id="forecast-direct-dispatch",
        )

        assert result.success is True
        assert result.error_type is None
        assert result.data is not None
        assert result.data["kind"] == "record"
        assert result.data["item"] == {"total_count": 0, "items": []}
        assert result.data["meta"]["source"] == "kma_ultra_short_term_forecast"
