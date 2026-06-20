# SPDX-License-Identifier: Apache-2.0
"""Recent-slot guards for KMA APIs with short retention windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

_SEOUL_TZ: Final = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True, slots=True)
class KmaBaseSlot:
    """A KMA base slot in API wire format."""

    base_date: str
    base_time: str


@dataclass(frozen=True, slots=True)
class KmaRecentSlotPolicy:
    """Publication and retention policy for a KMA recent-data endpoint."""

    retention_days: int
    slot_minute: int
    publication_lag_minutes: int


CURRENT_OBSERVATION_SLOT_POLICY: Final = KmaRecentSlotPolicy(
    retention_days=1,
    slot_minute=0,
    publication_lag_minutes=40,
)
ULTRA_SHORT_TERM_FORECAST_SLOT_POLICY: Final = KmaRecentSlotPolicy(
    retention_days=3,
    slot_minute=30,
    publication_lag_minutes=15,
)


def latest_recent_slot(
    policy: KmaRecentSlotPolicy,
    *,
    now: datetime | None = None,
) -> KmaBaseSlot:
    """Return the latest slot expected to satisfy the endpoint's freshness window."""
    kst_now = now.astimezone(_SEOUL_TZ) if now is not None else datetime.now(_SEOUL_TZ)
    stable = kst_now - timedelta(minutes=policy.publication_lag_minutes)
    slot = stable.replace(minute=policy.slot_minute, second=0, microsecond=0)
    if stable.minute < policy.slot_minute:
        slot = slot - timedelta(hours=1)
    return KmaBaseSlot(base_date=slot.strftime("%Y%m%d"), base_time=slot.strftime("%H%M"))


def coerce_recent_slot(
    requested: KmaBaseSlot,
    policy: KmaRecentSlotPolicy,
    *,
    now: datetime | None = None,
) -> KmaBaseSlot:
    """Clamp stale or unpublished KMA slots to the latest published slot."""
    latest = latest_recent_slot(policy, now=now)
    latest_dt = _slot_datetime(latest)
    try:
        requested_dt = _slot_datetime(requested)
    except ValueError:
        return latest
    earliest_dt = latest_dt - timedelta(days=policy.retention_days)
    if requested_dt < earliest_dt or requested_dt > latest_dt:
        return latest
    return requested


def _slot_datetime(slot: KmaBaseSlot) -> datetime:
    parsed = datetime.strptime(f"{slot.base_date}{slot.base_time}", "%Y%m%d%H%M")
    return parsed.replace(tzinfo=_SEOUL_TZ)
