# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the KMA weather alert status adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

from kosmos.tools.errors import ConfigurationError, ToolExecutionError
from kosmos.tools.kma.kma_weather_alert_status import (
    KMA_WEATHER_ALERT_STATUS_TOOL,
    KmaWeatherAlertStatusInput,
    KmaWeatherAlertStatusOutput,
    WeatherWarning,
    _call,
    _normalize_items,
    _parse_response,
    register,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text())


# ---------------------------------------------------------------------------
# WeatherWarning model tests
# ---------------------------------------------------------------------------


class TestWeatherWarningModel:
    def test_construction(self) -> None:
        """All fields are set correctly via constructor."""
        w = WeatherWarning(
            stn_id="108",
            tm_fc="202604130600",
            tm_ef="202604130900",
            tm_seq=1,
            area_code="S1151300",
            area_name="서울",
            warn_var=2,
            warn_stress=0,
            cancel=0,
            command=1,
            warn_fc=0,
        )
        assert w.stn_id == "108"
        assert w.tm_fc == "202604130600"
        assert w.tm_ef == "202604130900"
        assert w.tm_seq == 1
        assert w.area_code == "S1151300"
        assert w.area_name == "서울"
        assert w.warn_var == 2
        assert w.warn_stress == 0
        assert w.cancel == 0
        assert w.command == 1
        assert w.warn_fc == 0

    def test_frozen(self) -> None:
        """Mutation of frozen model raises ValidationError."""
        w = WeatherWarning(
            stn_id="108",
            tm_fc="202604130600",
            tm_ef="202604130900",
            tm_seq=1,
            area_code="S1151300",
            area_name="서울",
            warn_var=2,
            warn_stress=0,
            cancel=0,
            command=1,
            warn_fc=0,
        )
        with pytest.raises(ValidationError):
            w.stn_id = "999"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Input model tests
# ---------------------------------------------------------------------------


class TestKmaWeatherAlertStatusInput:
    def test_defaults(self) -> None:
        """Default values are num_of_rows=100, page_no=1, data_type='JSON'.
        stn_id must be provided (required by model_validator).
        """
        inp = KmaWeatherAlertStatusInput(stn_id="108")
        assert inp.num_of_rows == 100
        assert inp.page_no == 1
        assert inp.data_type == "JSON"

    def test_custom_values(self) -> None:
        """Custom values are accepted when stn_id is provided."""
        inp = KmaWeatherAlertStatusInput(stn_id="108", num_of_rows=100, page_no=2, data_type="JSON")
        assert inp.num_of_rows == 100
        assert inp.page_no == 2
        assert inp.data_type == "JSON"

    def test_both_none_raises(self) -> None:
        """Both stn_id=None and tmFc=None must raise ValidationError (model_validator)."""
        with pytest.raises(ValidationError):
            KmaWeatherAlertStatusInput()

    def test_stn_id_only_valid(self) -> None:
        """stn_id alone is sufficient."""
        inp = KmaWeatherAlertStatusInput(stn_id="159")
        assert inp.stn_id == "159"
        assert inp.tmFc is None

    def test_tmFc_only_valid(self) -> None:
        """tmFc alone is sufficient."""
        inp = KmaWeatherAlertStatusInput(tmFc="202605031100")
        assert inp.tmFc == "202605031100"
        assert inp.stn_id is None

    def test_num_of_rows_ge1(self) -> None:
        """num_of_rows must be >= 1."""
        with pytest.raises(ValidationError):
            KmaWeatherAlertStatusInput(stn_id="108", num_of_rows=0)

    def test_page_no_ge1(self) -> None:
        """page_no must be >= 1."""
        with pytest.raises(ValidationError):
            KmaWeatherAlertStatusInput(stn_id="108", page_no=0)


# ---------------------------------------------------------------------------
# _normalize_items tests
# ---------------------------------------------------------------------------


class TestNormalizeItems:
    def test_list_passthrough(self) -> None:
        """A list is returned as-is."""
        items = [{"a": 1}, {"b": 2}]
        assert _normalize_items(items) == items

    def test_single_dict_wrapped(self) -> None:
        """A single dict is wrapped in a list."""
        item = {"a": 1}
        assert _normalize_items(item) == [item]

    def test_none_returns_empty(self) -> None:
        """None returns an empty list."""
        assert _normalize_items(None) == []

    def test_empty_string_returns_empty(self) -> None:
        """An empty string returns an empty list."""
        assert _normalize_items("") == []


# ---------------------------------------------------------------------------
# _parse_response tests
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_success_filters_cancelled(self) -> None:
        """Fixture has 3 items; 1 is cancelled (cancel=1). Only 2 active should remain."""
        raw = _load("kma_alert_success.json")
        result = _parse_response(raw)
        assert isinstance(result, KmaWeatherAlertStatusOutput)
        assert result.total_count == 2
        assert len(result.warnings) == 2
        for w in result.warnings:
            assert w.cancel == 0

    def test_empty_results(self) -> None:
        """Empty fixture (items='') should produce 0 warnings."""
        raw = _load("kma_alert_empty.json")
        result = _parse_response(raw)
        assert result.total_count == 0
        assert result.warnings == []

    def test_no_data_code_03_returns_empty(self) -> None:
        """resultCode '03' (NO_DATA) means zero active alerts — not an error."""
        raw = {
            "response": {
                "header": {"resultCode": "03", "resultMsg": "NO_DATA"},
                "body": {},
            }
        }
        result = _parse_response(raw)
        assert isinstance(result, KmaWeatherAlertStatusOutput)
        assert result.total_count == 0
        assert result.warnings == []

    def test_error_raises(self) -> None:
        """Non-'00' resultCode must raise ToolExecutionError."""
        raw = _load("kma_alert_error.json")
        with pytest.raises(ToolExecutionError) as exc_info:
            _parse_response(raw)
        assert exc_info.value.tool_id == "kma_weather_alert_status"
        assert "30" in str(exc_info.value)

    def test_all_cancelled_returns_empty(self) -> None:
        """When all items are cancelled, result should have 0 active warnings."""
        raw = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
                "body": {
                    "totalCount": 2,
                    "items": {
                        "item": [
                            {
                                "stnId": "108",
                                "tmFc": "202604130600",
                                "tmEf": "202604130900",
                                "tmSeq": 1,
                                "areaCode": "S1151300",
                                "areaName": "서울",
                                "warnVar": 2,
                                "warnStress": 0,
                                "cancel": 1,
                                "command": 1,
                                "warFc": 0,
                            },
                            {
                                "stnId": "159",
                                "tmFc": "202604120600",
                                "tmEf": "202604121200",
                                "tmSeq": 2,
                                "areaCode": "S2632000",
                                "areaName": "부산",
                                "warnVar": 1,
                                "warnStress": 0,
                                "cancel": 1,
                                "command": 2,
                                "warFc": 0,
                            },
                        ]
                    },
                },
            }
        }
        result = _parse_response(raw)
        assert result.total_count == 0
        assert result.warnings == []


# ---------------------------------------------------------------------------
# _call async adapter tests
# ---------------------------------------------------------------------------


class TestCall:
    @pytest.mark.asyncio
    async def test_success_flow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy-path: mock httpx client returns success fixture; output has 2 warnings."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "test-key")

        fixture_data = _load("kma_alert_success.json")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = fixture_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        inp = KmaWeatherAlertStatusInput(stn_id="108")
        result = await _call(inp, client=mock_client)

        assert result["kind"] == "collection"
        assert result["total_count"] == 2
        assert len(result["items"]) == 2
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        assert (
            call_kwargs[0][0] == "https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrWrnMsg"
        )
        params = call_kwargs[1]["params"]
        assert params["serviceKey"] == "test-key"
        assert params["numOfRows"] == 100
        assert params["pageNo"] == 1
        assert params["dataType"] == "JSON"
        assert params["_type"] == "json"
        assert params["stnId"] == "108"

    @pytest.mark.asyncio
    async def test_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing env var must raise ConfigurationError before any HTTP call."""
        monkeypatch.delenv("KOSMOS_DATA_GO_KR_API_KEY", raising=False)

        inp = KmaWeatherAlertStatusInput(stn_id="108")
        with pytest.raises(ConfigurationError) as exc_info:
            await _call(inp)
        assert "KOSMOS_DATA_GO_KR_API_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_xml_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """XML content-type response must raise ToolExecutionError."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "test-key")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml; charset=utf-8"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        inp = KmaWeatherAlertStatusInput(stn_id="108")
        with pytest.raises(ToolExecutionError) as exc_info:
            await _call(inp, client=mock_client)
        assert "XML" in str(exc_info.value)
        assert exc_info.value.tool_id == "kma_weather_alert_status"


# ---------------------------------------------------------------------------
# Tool definition tests
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_tool_id(self) -> None:
        assert KMA_WEATHER_ALERT_STATUS_TOOL.id == "kma_weather_alert_status"

    def test_is_core_true(self) -> None:
        assert KMA_WEATHER_ALERT_STATUS_TOOL.is_core is True

    def test_auth_type_api_key(self) -> None:
        assert KMA_WEATHER_ALERT_STATUS_TOOL.auth_type == "api_key"

    def test_provider(self) -> None:
        assert KMA_WEATHER_ALERT_STATUS_TOOL.ministry == "KMA"

    def test_cache_ttl(self) -> None:
        assert KMA_WEATHER_ALERT_STATUS_TOOL.cache_ttl_seconds == 300

    def test_concurrency_safe(self) -> None:
        assert KMA_WEATHER_ALERT_STATUS_TOOL.is_concurrency_safe is True

    # test_not_personal_data removed in Epic δ #2295 (is_personal_data deleted).


# ---------------------------------------------------------------------------
# register() tests
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_adds_to_registry_and_executor(self) -> None:
        """register() adds the tool to both registry and executor."""
        from kosmos.tools.executor import ToolExecutor
        from kosmos.tools.registry import ToolRegistry

        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        register(registry, executor)

        # Verify tool is in registry
        tool = registry.lookup("kma_weather_alert_status")
        assert tool.id == "kma_weather_alert_status"

        # Verify adapter is in executor
        assert "kma_weather_alert_status" in executor._adapters
