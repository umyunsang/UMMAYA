# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ummaya.tools.executor.ToolExecutor."""

from __future__ import annotations

import json

import pytest

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.hira.hospital_search import HIRA_HOSPITAL_SEARCH_TOOL
from ummaya.tools.kma.forecast_fetch import KMA_FORECAST_FETCH_TOOL
from ummaya.tools.kma.kma_current_observation import KMA_CURRENT_OBSERVATION_TOOL
from ummaya.tools.location_adapters import KAKAO_COORD_TO_REGION_TOOL
from ummaya.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_executor(  # noqa: E501
    sample_tool_factory,
    mock_tool_adapter,
    *,
    tool_id: str = "kma_weather_forecast",
):
    """Build a ToolExecutor pre-loaded with one tool and its adapter."""
    registry = ToolRegistry()
    tool = sample_tool_factory(id=tool_id)
    registry.register(tool)
    executor = ToolExecutor(registry)
    executor.register_adapter(tool_id, mock_tool_adapter)
    return executor


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_success(sample_tool_factory, mock_tool_adapter):
    """Valid arguments produce a ToolResult with success=True and correct data."""
    executor = _make_executor(sample_tool_factory, mock_tool_adapter)
    args = json.dumps({"city": "Seoul"})

    result = await executor.dispatch("kma_weather_forecast", args)

    assert result.success is True
    assert result.tool_id == "kma_weather_forecast"
    assert result.error is None
    assert result.error_type is None
    assert result.data is not None
    assert result.data["temperature"] == 22.5
    assert result.data["humidity"] == 45


@pytest.mark.asyncio
async def test_dispatch_unknown_tool(sample_tool_factory, mock_tool_adapter):
    """Dispatching a tool_id not in the registry returns error_type='not_found'."""
    executor = _make_executor(sample_tool_factory, mock_tool_adapter)
    args = json.dumps({"city": "Busan"})

    result = await executor.dispatch("nonexistent_tool", args)

    assert result.success is False
    assert result.tool_id == "nonexistent_tool"
    assert result.error_type == "not_found"
    assert result.error is not None
    assert result.data is None


@pytest.mark.asyncio
async def test_dispatch_invalid_input_bad_json(sample_tool_factory, mock_tool_adapter):
    """Malformed JSON returns error_type='validation'."""
    executor = _make_executor(sample_tool_factory, mock_tool_adapter)

    result = await executor.dispatch("kma_weather_forecast", "{not valid json}")

    assert result.success is False
    assert result.error_type == "validation"
    assert result.data is None


@pytest.mark.asyncio
async def test_dispatch_invalid_input_schema_violation(sample_tool_factory, mock_tool_adapter):
    """Valid JSON that fails schema validation returns error_type='validation'."""
    executor = _make_executor(sample_tool_factory, mock_tool_adapter)
    # Pydantic v2 coerces int->str, so test with a missing required field instead
    args_missing = json.dumps({"date": "2026-04-12"})
    result = await executor.dispatch("kma_weather_forecast", args_missing)

    assert result.success is False
    assert result.error_type == "validation"
    assert result.data is None


@pytest.mark.asyncio
async def test_invoke_kma_current_observation_validation_names_time_recovery():
    """KMA current observation validation should name the missing time fields."""
    registry = ToolRegistry()
    registry.register(KMA_CURRENT_OBSERVATION_TOOL)
    executor = ToolExecutor(registry)

    async def _never_called(_validated_input):
        raise AssertionError("validation should fail before adapter execution")

    executor.register_adapter("kma_current_observation", _never_called)

    result = await executor.invoke(
        "kma_current_observation",
        {"nx": 97, "ny": 74},
        request_id="test-request",
    )

    assert result.kind == "error"
    assert result.reason.value == "invalid_params"
    assert "base_date" in result.message
    assert "base_time" in result.message
    assert "nx/ny" in result.message
    assert "KST" in result.message


@pytest.mark.asyncio
async def test_invoke_kma_forecast_fetch_validation_rejects_grid_retry():
    """KMA forecast validation should tell the model not to retry nx/ny."""
    registry = ToolRegistry()
    registry.register(KMA_FORECAST_FETCH_TOOL)
    executor = ToolExecutor(registry)

    async def _never_called(_validated_input):
        raise AssertionError("validation should fail before adapter execution")

    executor.register_adapter("kma_forecast_fetch", _never_called)

    result = await executor.invoke(
        "kma_forecast_fetch",
        {"nx": 97, "ny": 74, "base_date": "20260525", "base_time": "1700"},
        request_id="test-request",
    )

    assert result.kind == "error"
    assert result.reason.value == "invalid_params"
    assert "lat" in result.message
    assert "lon" in result.message
    assert "Do NOT pass nx/ny" in result.message
    assert "LOCATE FIRST" in result.message


@pytest.mark.asyncio
async def test_invoke_hira_hospital_search_validation_rejects_rounded_coords():
    """HIRA validation should tell the model to preserve locate decimals."""
    registry = ToolRegistry()
    registry.register(HIRA_HOSPITAL_SEARCH_TOOL)
    executor = ToolExecutor(registry)

    async def _never_called(_validated_input):
        raise AssertionError("validation should fail before adapter execution")

    executor.register_adapter("hira_hospital_search", _never_called)

    result = await executor.invoke(
        "hira_hospital_search",
        {"xPos": 128, "yPos": 35, "radius": 2000},
        request_id="test-request",
    )

    assert result.kind == "error"
    assert result.reason.value == "invalid_params"
    assert "do NOT round" in result.message
    assert "xPos:<exact lon>" in result.message


@pytest.mark.asyncio
async def test_invoke_raw_reverse_geocode_validation_rejects_rounded_coords():
    """Locate adapters should expose exact-coordinate recovery hints."""
    registry = ToolRegistry()
    registry.register(KAKAO_COORD_TO_REGION_TOOL)
    executor = ToolExecutor(registry)

    async def _never_called(_validated_input):
        raise AssertionError("validation should fail before adapter execution")

    executor.register_adapter("kakao_coord_to_region", _never_called)

    result = await executor.invoke_raw(
        "kakao_coord_to_region",
        {"lat": 35, "lon": 129},
        request_id="test-request",
    )

    assert result.kind == "error"
    assert result.reason.value == "invalid_params"
    assert "COPY EXACT COORDINATES" in result.message
    assert "Do NOT round" in result.message


@pytest.mark.asyncio
async def test_dispatch_rate_limit_exceeded(sample_tool_factory, mock_tool_adapter):
    """After exhausting the rate limit, dispatch returns error_type='rate_limit'."""
    registry = ToolRegistry()
    # Set rate_limit_per_minute=1 so one call exhausts it
    tool = sample_tool_factory(id="kma_weather_forecast", rate_limit_per_minute=1)
    registry.register(tool)
    executor = ToolExecutor(registry)
    executor.register_adapter("kma_weather_forecast", mock_tool_adapter)

    args = json.dumps({"city": "Seoul"})

    # First call should succeed (consumes the only slot)
    first = await executor.dispatch("kma_weather_forecast", args)
    assert first.success is True

    # Second call should be rate-limited
    second = await executor.dispatch("kma_weather_forecast", args)
    assert second.success is False
    assert second.error_type == "rate_limit"
    assert second.data is None


@pytest.mark.asyncio
async def test_dispatch_adapter_exception(sample_tool_factory):
    """An adapter that raises RuntimeError returns error_type='execution'."""
    registry = ToolRegistry()
    tool = sample_tool_factory(id="kma_weather_forecast")
    registry.register(tool)
    executor = ToolExecutor(registry)

    async def _failing_adapter(validated_input):
        raise RuntimeError("upstream service unavailable")

    executor.register_adapter("kma_weather_forecast", _failing_adapter)

    result = await executor.dispatch("kma_weather_forecast", json.dumps({"city": "Incheon"}))

    assert result.success is False
    assert result.error_type == "execution"
    assert result.error == "Tool execution failed."
    assert result.data is None


@pytest.mark.asyncio
async def test_dispatch_output_schema_mismatch(sample_tool_factory):
    """An adapter returning wrong shape returns error_type='schema_mismatch'."""
    registry = ToolRegistry()
    tool = sample_tool_factory(id="kma_weather_forecast")
    registry.register(tool)
    executor = ToolExecutor(registry)

    async def _wrong_shape_adapter(validated_input):
        # Missing required fields: temperature, condition, humidity
        return {"unexpected_field": "oops"}

    executor.register_adapter("kma_weather_forecast", _wrong_shape_adapter)

    result = await executor.dispatch("kma_weather_forecast", json.dumps({"city": "Daegu"}))

    assert result.success is False
    assert result.error_type == "schema_mismatch"
    assert result.data is None
