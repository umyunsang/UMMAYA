# SPDX-License-Identifier: Apache-2.0
"""Tests for KMA recent-slot retention guards."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ummaya.tools.kma.recent_slots import (
    CURRENT_OBSERVATION_SLOT_POLICY,
    ULTRA_SHORT_TERM_FORECAST_SLOT_POLICY,
    KmaBaseSlot,
    coerce_recent_slot,
    latest_recent_slot,
)

_KST = ZoneInfo("Asia/Seoul")


class TestLatestRecentSlot:
    def test_current_observation_uses_previous_stable_hour_when_before_forty(self) -> None:
        now = datetime(2026, 6, 20, 11, 4, tzinfo=_KST)

        slot = latest_recent_slot(CURRENT_OBSERVATION_SLOT_POLICY, now=now)

        assert slot == KmaBaseSlot(base_date="20260620", base_time="1000")

    def test_ultra_short_forecast_uses_latest_published_half_hour(self) -> None:
        now = datetime(2026, 6, 20, 11, 4, tzinfo=_KST)

        slot = latest_recent_slot(ULTRA_SHORT_TERM_FORECAST_SLOT_POLICY, now=now)

        assert slot == KmaBaseSlot(base_date="20260620", base_time="1030")


class TestCoerceRecentSlot:
    def test_stale_current_observation_slot_is_replaced(self) -> None:
        now = datetime(2026, 6, 20, 11, 4, tzinfo=_KST)
        requested = KmaBaseSlot(base_date="20260430", base_time="1200")

        slot = coerce_recent_slot(requested, CURRENT_OBSERVATION_SLOT_POLICY, now=now)

        assert slot == KmaBaseSlot(base_date="20260620", base_time="1000")

    def test_stale_ultra_short_forecast_slot_is_replaced(self) -> None:
        now = datetime(2026, 6, 20, 11, 4, tzinfo=_KST)
        requested = KmaBaseSlot(base_date="20260430", base_time="1200")

        slot = coerce_recent_slot(requested, ULTRA_SHORT_TERM_FORECAST_SLOT_POLICY, now=now)

        assert slot == KmaBaseSlot(base_date="20260620", base_time="1030")

    def test_recent_slot_inside_retention_window_is_preserved(self) -> None:
        now = datetime(2026, 6, 20, 11, 4, tzinfo=_KST)
        requested = KmaBaseSlot(base_date="20260620", base_time="0900")

        slot = coerce_recent_slot(requested, CURRENT_OBSERVATION_SLOT_POLICY, now=now)

        assert slot == requested

    def test_invalid_calendar_slot_is_replaced(self) -> None:
        now = datetime(2026, 6, 20, 11, 4, tzinfo=_KST)
        requested = KmaBaseSlot(base_date="20260230", base_time="1200")

        slot = coerce_recent_slot(requested, ULTRA_SHORT_TERM_FORECAST_SLOT_POLICY, now=now)

        assert slot == KmaBaseSlot(base_date="20260620", base_time="1030")
