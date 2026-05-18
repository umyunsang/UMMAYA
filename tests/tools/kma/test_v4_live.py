# SPDX-License-Identifier: Apache-2.0
"""KMA v4 live integration tests — @pytest.mark.live only.

Covers all 6 KMA tools with at least 1 live scenario each.
Key regression: test_busan_current_observation_no_invalid_params verifies
Spec 2521 regression fix — KMA call with Busan grid coords must not produce
invalid_params (nx/ny confusion with lat/lon).

Run:
    uv run pytest tests/tools/kma/test_v4_live.py -m live -v
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

# ---------------------------------------------------------------------------
# Skip all tests if env key is absent
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.live

_KEY_PRESENT = bool(os.environ.get("UMMAYA_DATA_GO_KR_API_KEY"))


def _skip_if_no_key() -> None:
    if not _KEY_PRESENT:
        pytest.skip("UMMAYA_DATA_GO_KR_API_KEY not set — skipping live test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_base_date() -> str:
    """Return today's date as YYYYMMDD."""
    return datetime.now(tz=UTC).strftime("%Y%m%d")


def _now_obs_time() -> str:
    """Return base_time for getUltraSrtNcst: previous whole hour, HHMM.

    Minutes >= 40: use current hour; else use previous hour.
    Always returns HH00 (round down to :00).
    """
    now = datetime.now(tz=UTC)
    # Convert UTC to KST (+9)
    from datetime import timedelta

    kst = now + timedelta(hours=9)
    hour = kst.hour if kst.minute >= 40 else (kst.hour - 1) % 24
    return f"{hour:02d}00"


def _now_forecast_base_time() -> str:
    """Return valid base_time for getVilageFcst: latest announcement before now.

    Valid times: 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300 (KST).
    """
    from datetime import timedelta

    _VALID_HOURS = [2, 5, 8, 11, 14, 17, 20, 23]
    now = datetime.now(tz=UTC) + timedelta(hours=9)  # to KST
    current_hour = now.hour
    # Find latest valid hour <= current_hour
    past_hours = [h for h in _VALID_HOURS if h <= current_hour]
    if not past_hours:
        # Before 0200 KST — use previous day's 2300
        hour = 23
    else:
        hour = past_hours[-1]
    return f"{hour:02d}00"


def _ultra_short_base_time() -> str:
    """Return base_time for getUltraSrtFcst: latest HH30 before now (KST)."""
    from datetime import timedelta

    now = datetime.now(tz=UTC) + timedelta(hours=9)  # to KST
    # base_time is HH30, but there's also HH00 apparently; use HH30
    # The KMA docs say every 30 minutes from 0030
    minute = now.minute
    if minute >= 30:
        return f"{now.hour:02d}30"
    else:
        prev_hour = (now.hour - 1) % 24
        return f"{prev_hour:02d}30"


# ---------------------------------------------------------------------------
# Tool 1: kma_current_observation
# ---------------------------------------------------------------------------


class TestKmaCurrentObservationLive:
    """Live tests for kma_current_observation (getUltraSrtNcst)."""

    @pytest.mark.asyncio
    async def test_seoul_current_observation(self) -> None:
        """Seoul (nx=61, ny=126) current observation returns valid temperature."""
        _skip_if_no_key()

        from ummaya.tools.kma.kma_current_observation import KmaCurrentObservationInput, _call

        inp = KmaCurrentObservationInput(
            base_date=_now_base_date(),
            base_time=_now_obs_time(),
            nx=61,
            ny=126,
        )
        result = await _call(inp)

        assert isinstance(result, dict)
        assert "t1h" in result or result.get("base_date") is not None
        assert result.get("nx") == 61
        assert result.get("ny") == 126

    @pytest.mark.asyncio
    async def test_busan_current_observation_no_invalid_params(self) -> None:
        """Spec 2521 regression fix — Busan (nx=98, ny=76) must not produce invalid_params.

        This test verifies that the KMA adapter correctly uses KMA grid coords (nx, ny)
        NOT lat/lon.  Busan's grid is (98, 76) — passing lat(35.1)/lon(129.0) would
        fail with invalid range errors (nx 1-149, ny 1-253 check).
        """
        _skip_if_no_key()

        from ummaya.tools.kma.kma_current_observation import KmaCurrentObservationInput, _call

        # Busan KMA grid: nx=98, ny=76
        inp = KmaCurrentObservationInput(
            base_date=_now_base_date(),
            base_time=_now_obs_time(),
            nx=98,
            ny=76,
        )
        result = await _call(inp)

        assert isinstance(result, dict)
        # Must succeed with grid coords, not raise ValidationError or ToolExecutionError
        assert result.get("nx") == 98
        assert result.get("ny") == 76
        # Temperature should be a plausible float (−50 to +50 °C)
        if result.get("t1h") is not None:
            assert -50.0 <= float(result["t1h"]) <= 50.0


# ---------------------------------------------------------------------------
# Tool 2: kma_short_term_forecast
# ---------------------------------------------------------------------------


class TestKmaShortTermForecastLive:
    """Live tests for kma_short_term_forecast (getVilageFcst)."""

    @pytest.mark.asyncio
    async def test_seoul_short_term_forecast(self) -> None:
        """Seoul (nx=61, ny=126) short-term forecast returns ≥1 item."""
        _skip_if_no_key()

        from ummaya.tools.kma.kma_short_term_forecast import KmaShortTermForecastInput, _call

        inp = KmaShortTermForecastInput(
            base_date=_now_base_date(),
            base_time=_now_forecast_base_time(),
            nx=61,
            ny=126,
            num_of_rows=10,
        )
        result = await _call(inp)

        assert isinstance(result, dict)
        assert "items" in result
        items = result["items"]
        assert isinstance(items, list)
        assert len(items) >= 1
        # Each item has required fields
        first = items[0]
        assert "fcst_date" in first
        assert "fcst_time" in first
        assert "category" in first


# ---------------------------------------------------------------------------
# Tool 3: kma_ultra_short_term_forecast
# ---------------------------------------------------------------------------


class TestKmaUltraShortTermForecastLive:
    """Live tests for kma_ultra_short_term_forecast (getUltraSrtFcst)."""

    @pytest.mark.asyncio
    async def test_seoul_ultra_short_forecast(self) -> None:
        """Seoul (nx=61, ny=126) ultra-short-term forecast returns ≥1 item."""
        _skip_if_no_key()

        from ummaya.tools.kma.kma_ultra_short_term_forecast import (
            KmaUltraShortTermForecastInput,
            _call,
        )

        inp = KmaUltraShortTermForecastInput(
            base_date=_now_base_date(),
            base_time=_ultra_short_base_time(),
            nx=61,
            ny=126,
            num_of_rows=10,
        )
        result = await _call(inp)

        assert isinstance(result, dict)
        assert "items" in result
        assert isinstance(result["items"], list)
        assert len(result["items"]) >= 1


# ---------------------------------------------------------------------------
# Tool 4: kma_forecast_fetch
# ---------------------------------------------------------------------------


class TestKmaForecastFetchLive:
    """Live tests for kma_forecast_fetch (getVilageFcst, lat/lon variant)."""

    @pytest.mark.asyncio
    async def test_busan_forecast_fetch_by_latlon(self) -> None:
        """Busan by lat/lon — adapter internally converts to nx/ny."""
        _skip_if_no_key()

        from ummaya.tools.kma.forecast_fetch import KmaForecastFetchInput, _call

        inp = KmaForecastFetchInput(
            lat=35.1796,
            lon=129.0756,
            num_of_rows=10,
        )
        result = await _call(inp)

        assert isinstance(result, dict)
        assert "items" in result
        items = result["items"]
        assert isinstance(items, list)
        assert len(items) >= 1


# ---------------------------------------------------------------------------
# Tool 5: kma_pre_warning
# ---------------------------------------------------------------------------


class TestKmaPreWarningLive:
    """Live tests for kma_pre_warning (getWthrWrnList — confirmed 200)."""

    @pytest.mark.asyncio
    async def test_nationwide_pre_warning(self) -> None:
        """Nationwide pre-warning list (no stn_id) returns valid output."""
        _skip_if_no_key()

        from ummaya.tools.kma.kma_pre_warning import KmaPreWarningInput, _call

        inp = KmaPreWarningInput(num_of_rows=10)
        result = await _call(inp)

        assert isinstance(result, dict)
        assert "total_count" in result
        assert "items" in result
        assert isinstance(result["items"], list)
        # Regardless of alert state (0 or N), structure is valid
        assert result["total_count"] >= 0

    @pytest.mark.asyncio
    async def test_seoul_pre_warning_with_stn_id(self) -> None:
        """Seoul (stn_id=108) pre-warning filtered list is valid."""
        _skip_if_no_key()

        from ummaya.tools.kma.kma_pre_warning import KmaPreWarningInput, _call

        inp = KmaPreWarningInput(stn_id="108", num_of_rows=10)
        result = await _call(inp)

        assert isinstance(result, dict)
        assert "total_count" in result
        assert isinstance(result["items"], list)


# ---------------------------------------------------------------------------
# Tool 6: kma_weather_alert_status
# ---------------------------------------------------------------------------


class TestKmaWeatherAlertStatusLive:
    """Live tests for kma_weather_alert_status (getWthrWrnList).

    Evidence: empty params perform nationwide active-warning lookup.
    stn_id and tmFc remain optional filters.
    """

    @pytest.mark.asyncio
    async def test_seoul_alert_status_by_stn_id(self) -> None:
        """Seoul (stn_id=108) alert status by stn_id returns valid output."""
        _skip_if_no_key()

        from ummaya.tools.kma.kma_weather_alert_status import (
            KmaWeatherAlertStatusInput,
            _call,
        )

        inp = KmaWeatherAlertStatusInput(stn_id="108", num_of_rows=10)
        result = await _call(inp)

        assert isinstance(result, dict)
        assert "total_count" in result
        assert "warnings" in result
        assert isinstance(result["warnings"], list)
        assert result["total_count"] >= 0

    @pytest.mark.asyncio
    async def test_jeju_alert_status_by_stn_id(self) -> None:
        """Jeju (stn_id=184) alert status returns valid output (active marine area)."""
        _skip_if_no_key()

        from ummaya.tools.kma.kma_weather_alert_status import (
            KmaWeatherAlertStatusInput,
            _call,
        )

        inp = KmaWeatherAlertStatusInput(stn_id="184", num_of_rows=10)
        result = await _call(inp)

        assert isinstance(result, dict)
        assert "total_count" in result
        assert "warnings" in result

    @pytest.mark.asyncio
    async def test_missing_both_is_nationwide_lookup(self) -> None:
        """Both stn_id=None and tmFc=None is accepted for nationwide lookup."""
        from ummaya.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        inp = KmaWeatherAlertStatusInput()
        assert inp.stn_id is None
        assert inp.tmFc is None
