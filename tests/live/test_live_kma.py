# SPDX-License-Identifier: Apache-2.0
"""Live validation tests for KMA weather adapter endpoints.

Tests hit the REAL KMA APIs via data.go.kr.  They hard-fail on any network or
API error — no silent skips on unavailability.  Assertions are limited to
response *structure*, not specific data values, because weather data changes
constantly.

Required environment variable: ``UMMAYA_DATA_GO_KR_API_KEY``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ummaya.tools.kma.kma_current_observation import (
    KmaCurrentObservationInput,
    KmaCurrentObservationOutput,
)
from ummaya.tools.kma.kma_current_observation import (
    _call as _observation_call,
)
from ummaya.tools.kma.kma_weather_alert_status import (
    KmaWeatherAlertStatusInput,
    KmaWeatherAlertStatusOutput,
)
from ummaya.tools.kma.kma_weather_alert_status import (
    _call as _alert_call,
)

# ---------------------------------------------------------------------------
# Weather Alert tests
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_kma_weather_alert_basic(
    data_go_kr_api_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Call the real KMA getWthrWrnList endpoint and verify response structure.

    Verifies that the result contains ``total_count`` (int >= 0) and
    ``warnings`` (list).  If any warnings are present, also checks that the
    first entry exposes either the compact ``title`` field or full alert fields.
    """
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", data_go_kr_api_key)

    inp = KmaWeatherAlertStatusInput()
    result = await _alert_call(inp)

    assert "total_count" in result, "Missing key 'total_count' in alert response"
    assert "warnings" in result, "Missing key 'warnings' in alert response"

    assert isinstance(result["total_count"], int), (
        f"'total_count' must be int, got {type(result['total_count'])!r}"
    )
    assert result["total_count"] >= 0, f"'total_count' must be >= 0, got {result['total_count']}"
    assert isinstance(result["warnings"], list), (
        f"'warnings' must be list, got {type(result['warnings'])!r}"
    )

    if result["warnings"]:
        first = result["warnings"][0]
        assert first.get("title") or first.get("area_name") or first.get("warn_var") is not None


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_kma_weather_alert_parses_to_model(
    data_go_kr_api_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that the raw _call() dict validates cleanly into KmaWeatherAlertStatusOutput."""
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", data_go_kr_api_key)

    inp = KmaWeatherAlertStatusInput()
    result = await _alert_call(inp)

    # model_validate must succeed without raising a ValidationError
    output = KmaWeatherAlertStatusOutput.model_validate(result)
    assert isinstance(output, KmaWeatherAlertStatusOutput)
    assert output.total_count >= 0
    assert isinstance(output.warnings, list)


# ---------------------------------------------------------------------------
# Current Observation tests
# ---------------------------------------------------------------------------


def _observation_datetime() -> tuple[str, str]:
    """Return (base_date, base_time) using the *previous* hour to avoid data-not-ready errors.

    Uses ``datetime.now(UTC)`` and subtracts one hour so the KMA API has
    already published the observation data for that slot.

    Returns:
        A tuple of (YYYYMMDD, HHMM) strings.
    """
    now = datetime.now(UTC)
    prev_hour = now - timedelta(hours=1)
    base_date = prev_hour.strftime("%Y%m%d")
    base_time = prev_hour.strftime("%H00")
    return base_date, base_time


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_kma_current_observation_basic(
    data_go_kr_api_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Call the real KMA getUltraSrtNcst endpoint for Seoul and verify response structure.

    Uses Seoul grid coordinates (nx=60, ny=127) and the previous hour's
    timestamp.  Verifies required keys and that ``t1h`` is float or None
    and ``rn1`` is float.
    """
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", data_go_kr_api_key)

    base_date, base_time = _observation_datetime()
    inp = KmaCurrentObservationInput(
        base_date=base_date,
        base_time=base_time,
        nx=60,
        ny=127,
    )
    result = await _observation_call(inp)

    for key in ("base_date", "base_time", "nx", "ny"):
        assert key in result, f"Missing required key {key!r} in observation response"

    assert isinstance(result["t1h"], float) or result["t1h"] is None, (
        f"'t1h' must be float or None, got {type(result['t1h'])!r}"
    )
    assert isinstance(result["rn1"], float), f"'rn1' must be float, got {type(result['rn1'])!r}"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_kma_current_observation_parses_to_model(
    data_go_kr_api_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that the raw _call() dict validates cleanly into KmaCurrentObservationOutput."""
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", data_go_kr_api_key)

    base_date, base_time = _observation_datetime()
    inp = KmaCurrentObservationInput(
        base_date=base_date,
        base_time=base_time,
        nx=60,
        ny=127,
    )
    result = await _observation_call(inp)

    # model_validate must succeed without raising a ValidationError
    output = KmaCurrentObservationOutput.model_validate(result)
    assert isinstance(output, KmaCurrentObservationOutput)
    assert isinstance(output.base_date, str) and len(output.base_date) == 8
    assert isinstance(output.base_time, str) and len(output.base_time) == 4
    assert isinstance(output.rn1, float)
