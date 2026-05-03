# SPDX-License-Identifier: Apache-2.0
"""Unit tests for NMC freshness validation (T005, T006, T008, T009, T010).

Covers user stories from spec 023-nmc-freshness-slo:
  - T005 / US1: Fresh-path — hvidate within threshold is accepted.
  - T006 / US2: Stale-path — hvidate outside threshold or missing is rejected (fail-closed).
  - T008 / US1+US2: Integration — executor pipeline returns LookupCollection (fresh) or
                    LookupError (stale) based on fixture response.
  - T009 / US3: Threshold config — custom and settings-derived thresholds are honoured;
                pydantic bounds (ge=1, le=1440) are enforced.
  - T010 / US3: Threshold integration — custom nmc_freshness_minutes from settings is
                propagated through the full executor pipeline.

``datetime.now`` is patched for every test that inspects age or is_fresh so that
results are deterministic regardless of wall-clock time.

Fixed reference time: 2026-04-16 14:10:00 KST
  - fresh_response.json hvidate 14:00:00  →  10 min old
  - stale_response.json hvidate 13:00:00  →  70 min old
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
import respx
from pydantic import ValidationError

from kosmos.tools.executor import ToolExecutor
from kosmos.tools.nmc.emergency_search import register
from kosmos.tools.nmc.freshness import FreshnessResult, check_freshness
from kosmos.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_KST = ZoneInfo("Asia/Seoul")
FIXED_NOW = datetime(2026, 4, 16, 14, 10, 0, tzinfo=_KST)

# Absolute paths to NMC test fixtures
_FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "nmc"
_FRESH_FIXTURE = _FIXTURE_DIR / "fresh_response.json"
_STALE_FIXTURE = _FIXTURE_DIR / "stale_response.json"


def _mock_dt(mock_dt_cls: object) -> None:
    """Configure a patched datetime class used inside freshness.py.

    ``datetime.strptime`` is a classmethod on the real datetime class; we must
    restore it on the mock so that timestamp parsing still works while only
    ``datetime.now`` is intercepted.
    """
    mock_dt_cls.now.return_value = FIXED_NOW  # type: ignore[attr-defined]
    mock_dt_cls.strptime = datetime.strptime  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# T005 — Fresh-path tests [US1]
# ---------------------------------------------------------------------------


class TestFreshPath:
    """T005: hvidate values that fall within the freshness threshold."""

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_fresh_10_minutes_old(self, mock_dt: object) -> None:
        """14:00 hvidate with now=14:10 and threshold=30 → is_fresh=True, age≈10 min."""
        _mock_dt(mock_dt)
        result = check_freshness("2026-04-16 14:00:00", threshold_minutes=30)

        assert isinstance(result, FreshnessResult)
        assert result.is_fresh is True
        assert abs(result.data_age_minutes - 10.0) < 0.1
        assert result.threshold_minutes == 30
        assert result.hvidate_raw == "2026-04-16 14:00:00"

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_fresh_exactly_at_boundary(self, mock_dt: object) -> None:
        """Exactly 30 min old with threshold=30 → is_fresh=True (age <= threshold is fresh)."""
        _mock_dt(mock_dt)
        # 14:10 - 13:40 = 30 min exactly → boundary must be fresh per spec
        result = check_freshness("2026-04-16 13:40:00", threshold_minutes=30)

        assert result.is_fresh is True
        assert abs(result.data_age_minutes - 30.0) < 0.1
        assert result.threshold_minutes == 30

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_fresh_fixture_file(self, mock_dt: object) -> None:
        """fresh_response.json first-item hvidate (14:00:00) → is_fresh=True with now=14:10."""
        _mock_dt(mock_dt)
        payload = json.loads(_FRESH_FIXTURE.read_text(encoding="utf-8"))
        hvidate = payload["response"]["body"]["items"][0]["hvidate"]

        result = check_freshness(hvidate, threshold_minutes=30)

        assert result.is_fresh is True, (
            f"Expected fresh for hvidate={hvidate!r}, got is_fresh=False"
        )


# ---------------------------------------------------------------------------
# T006 — Stale-path tests [US2]
# ---------------------------------------------------------------------------


class TestStalePath:
    """T006: hvidate values that exceed the freshness threshold or are missing/invalid."""

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_stale_31_minutes_old(self, mock_dt: object) -> None:
        """14:10 - 13:39 = 31 min with threshold=30 → is_fresh=False."""
        _mock_dt(mock_dt)
        result = check_freshness("2026-04-16 13:39:00", threshold_minutes=30)

        assert result.is_fresh is False
        assert abs(result.data_age_minutes - 31.0) < 0.1
        assert result.threshold_minutes == 30

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_stale_1440_minutes_old(self, mock_dt: object) -> None:
        """24 hours old (1440 min) with threshold=30 → is_fresh=False."""
        _mock_dt(mock_dt)
        result = check_freshness("2026-04-15 14:10:00", threshold_minutes=30)

        assert result.is_fresh is False
        assert abs(result.data_age_minutes - 1440.0) < 0.1

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_stale_none_hvidate(self, mock_dt: object) -> None:
        """None hvidate → fail-closed: is_fresh=False, data_age_minutes=inf."""
        _mock_dt(mock_dt)
        result = check_freshness(None, threshold_minutes=30)

        assert result.is_fresh is False
        assert result.data_age_minutes == float("inf")
        assert result.threshold_minutes == 30
        assert result.hvidate_raw is None

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_stale_empty_string_hvidate(self, mock_dt: object) -> None:
        """Empty string hvidate → fail-closed: is_fresh=False, data_age_minutes=inf."""
        _mock_dt(mock_dt)
        result = check_freshness("", threshold_minutes=30)

        assert result.is_fresh is False
        assert result.data_age_minutes == float("inf")

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_stale_invalid_date_string(self, mock_dt: object) -> None:
        """Unparseable hvidate → fail-closed: is_fresh=False, data_age_minutes=inf."""
        _mock_dt(mock_dt)
        result = check_freshness("invalid-date", threshold_minutes=30)

        assert result.is_fresh is False
        assert result.data_age_minutes == float("inf")
        assert result.hvidate_raw == "invalid-date"

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_stale_fixture_file(self, mock_dt: object) -> None:
        """stale_response.json first-item hvidate (13:00:00) → is_fresh=False with now=14:10."""
        _mock_dt(mock_dt)
        payload = json.loads(_STALE_FIXTURE.read_text(encoding="utf-8"))
        hvidate = payload["response"]["body"]["items"][0]["hvidate"]

        result = check_freshness(hvidate, threshold_minutes=30)

        assert result.is_fresh is False, (
            f"Expected stale for hvidate={hvidate!r}, got is_fresh=True"
        )

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_stale_future_timestamp(self, mock_dt: object) -> None:
        """hvidate 5 min in the future → fail-closed: is_fresh=False, age < 0."""
        _mock_dt(mock_dt)
        result = check_freshness("2026-04-16 14:15:00", threshold_minutes=30)

        assert result.is_fresh is False
        assert result.data_age_minutes < 0


# ---------------------------------------------------------------------------
# T009 — Threshold config tests [US3]
# ---------------------------------------------------------------------------


class TestThresholdConfig:
    """T009: custom thresholds and pydantic validation bounds."""

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_custom_threshold_fresh(self, mock_dt: object) -> None:
        """59 min old with threshold=60 → is_fresh=True."""
        _mock_dt(mock_dt)
        # 14:10 - 13:11 = 59 min → within 60-min threshold
        result = check_freshness("2026-04-16 13:11:00", threshold_minutes=60)

        assert result.is_fresh is True
        assert abs(result.data_age_minutes - 59.0) < 0.1
        assert result.threshold_minutes == 60

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_custom_threshold_stale(self, mock_dt: object) -> None:
        """61 min old with threshold=60 → is_fresh=False."""
        _mock_dt(mock_dt)
        # 14:10 - 13:09 = 61 min → exceeds 60-min threshold
        result = check_freshness("2026-04-16 13:09:00", threshold_minutes=60)

        assert result.is_fresh is False
        assert abs(result.data_age_minutes - 61.0) < 0.1
        assert result.threshold_minutes == 60

    @patch("kosmos.tools.nmc.freshness.datetime")
    def test_default_threshold_from_settings(self, mock_dt: object) -> None:
        """threshold_minutes=None reads settings.nmc_freshness_minutes (default 30)."""
        _mock_dt(mock_dt)
        # freshness.py imports settings lazily inside the function via
        # ``from kosmos.settings import settings``, so we patch the singleton
        # on its home module (kosmos.settings.settings).
        with patch("kosmos.settings.settings") as mock_settings:
            mock_settings.nmc_freshness_minutes = 30
            # 10-min-old hvidate should be fresh with the mocked 30-min default
            result = check_freshness("2026-04-16 14:00:00", threshold_minutes=None)

        assert result.is_fresh is True
        assert result.threshold_minutes == 30

    def test_pydantic_validation_rejects_zero(self) -> None:
        """KosmosSettings(nmc_freshness_minutes=0) must raise ValidationError (ge=1)."""
        from kosmos.settings import KosmosSettings

        with pytest.raises(ValidationError):
            KosmosSettings(nmc_freshness_minutes=0)

    def test_pydantic_validation_rejects_1441(self) -> None:
        """KosmosSettings(nmc_freshness_minutes=1441) must raise ValidationError (le=1440)."""
        from kosmos.settings import KosmosSettings

        with pytest.raises(ValidationError):
            KosmosSettings(nmc_freshness_minutes=1441)


# ---------------------------------------------------------------------------
# Shared fixture for integration tests (T008, T010)
# ---------------------------------------------------------------------------


@pytest.fixture()
def nmc_reg_exec():
    """Function-scoped registry + executor pair with NMC tool registered."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)
    return registry, executor


# ---------------------------------------------------------------------------
# T008 — Integration tests [US1 + US2]
# ---------------------------------------------------------------------------


class TestFreshnessIntegration:
    """T008: executor pipeline returns LookupCollection (fresh) or LookupError (stale)."""

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.tools.nmc.freshness.datetime")
    @patch("kosmos.settings.settings")
    async def test_fresh_response_returns_collection(
        self, mock_settings, mock_dt, nmc_reg_exec
    ) -> None:
        """Fresh fixture → executor returns LookupCollection with freshness_status='fresh'."""
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 30
        _mock_dt(mock_dt)
        registry, executor = nmc_reg_exec

        payload = json.loads(_FRESH_FIXTURE.read_text(encoding="utf-8"))
        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, json=payload)

        from kosmos.tools.models import LookupCollection

        result = await executor.invoke(
            "nmc_emergency_search",
            {"lat": 37.5, "lon": 127.0, "limit": 5},
            request_id="test-req-001",
            session_identity=object(),  # bypass Layer 3 auth gate
        )

        assert isinstance(result, LookupCollection), (
            f"Expected LookupCollection, got {type(result).__name__}: {result!r}"
        )
        assert result.kind == "collection"
        assert result.meta.freshness_status == "fresh"
        assert len(result.items) == 2

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.tools.nmc.freshness.datetime")
    @patch("kosmos.settings.settings")
    async def test_stale_response_returns_error(self, mock_settings, mock_dt, nmc_reg_exec) -> None:
        """Stale fixture → executor returns LookupError with reason='stale_data'."""
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 30
        _mock_dt(mock_dt)
        registry, executor = nmc_reg_exec

        payload = json.loads(_STALE_FIXTURE.read_text(encoding="utf-8"))
        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, json=payload)

        from kosmos.tools.models import LookupError as LookupErrorModel

        result = await executor.invoke(
            "nmc_emergency_search",
            {"lat": 37.5, "lon": 127.0, "limit": 5},
            request_id="test-req-002",
            session_identity=object(),
        )

        assert isinstance(result, LookupErrorModel), (
            f"Expected LookupError, got {type(result).__name__}: {result!r}"
        )
        assert result.kind == "error"
        assert result.reason == "stale_data"
        assert "min old" in result.message
        assert "threshold" in result.message

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.tools.nmc.freshness.datetime")
    @patch("kosmos.settings.settings")
    async def test_missing_hvidate_returns_not_applicable_collection(
        self, mock_settings, mock_dt, nmc_reg_exec
    ) -> None:
        """Response with no hvidate field → endpoint-static collection with
        meta.freshness_status='not_applicable'.

        Behavior changed on 2026-05-04 (integration-verification): the NMC
        adapter now targets `getEgytLcinfoInqire` (location endpoint) which
        returns ER static metadata WITHOUT real-time bed counts or hvidate.
        Treating absent hvidate as stale would now mean every location
        request fails closed — instead, when hvidate is uniformly absent we
        recognise the response as a static-location batch and tag freshness
        as not_applicable. The fail-closed stale_data behaviour is preserved
        for the real-time bed endpoint, which always carries hvidate per
        record (verified upstream by `_evaluate_freshness`'s worst-case loop).
        """
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 30
        _mock_dt(mock_dt)
        registry, executor = nmc_reg_exec

        no_hvidate_payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
                "body": {
                    "items": [{"dutyName": "Test Hospital", "hvec": 5}],
                    "totalCount": 1,
                },
            }
        }
        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, json=no_hvidate_payload)

        from kosmos.tools.models import LookupCollection

        result = await executor.invoke(
            "nmc_emergency_search",
            {"lat": 37.5, "lon": 127.0, "limit": 5},
            request_id="test-req-003",
            session_identity=object(),
        )

        assert isinstance(result, LookupCollection), (
            f"Expected LookupCollection, got {type(result).__name__}: {result!r}"
        )
        assert result.meta.freshness_status == "not_applicable"
        assert result.total_count == 1

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.settings.settings")
    async def test_upstream_error_resultcode_returns_upstream_unavailable(
        self, mock_settings, nmc_reg_exec
    ) -> None:
        """NMC API resultCode != '00' → LookupError(reason='upstream_unavailable')."""
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 30
        _, executor = nmc_reg_exec

        error_payload = {
            "response": {
                "header": {"resultCode": "99", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"},
                "body": {"items": [], "totalCount": 0},
            }
        }
        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, json=error_payload)

        from kosmos.tools.models import LookupError as LookupErrorModel

        result = await executor.invoke(
            "nmc_emergency_search",
            {"lat": 37.5, "lon": 127.0, "limit": 5},
            request_id="test-req-rc-err",
            session_identity=object(),
        )

        assert isinstance(result, LookupErrorModel)
        assert result.reason == "upstream_unavailable"
        assert "resultCode" in result.message

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.settings.settings")
    async def test_non_json_response_returns_upstream_unavailable(
        self, mock_settings, nmc_reg_exec
    ) -> None:
        """NMC API returns HTML instead of JSON → LookupError(reason='upstream_unavailable')."""
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 30
        _, executor = nmc_reg_exec

        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(
            200,
            content=b"<html>Service Unavailable</html>",
            headers={"content-type": "text/html"},
        )

        from kosmos.tools.models import LookupError as LookupErrorModel

        result = await executor.invoke(
            "nmc_emergency_search",
            {"lat": 37.5, "lon": 127.0, "limit": 5},
            request_id="test-req-html",
            session_identity=object(),
        )

        assert isinstance(result, LookupErrorModel)
        assert result.reason == "upstream_unavailable"
        assert "non-JSON" in result.message

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.settings.settings")
    async def test_empty_items_returns_empty_collection(self, mock_settings, nmc_reg_exec) -> None:
        """resultCode=00 with empty items → LookupCollection (not stale_data)."""
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 30
        _, executor = nmc_reg_exec

        empty_payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
                "body": {"items": [], "totalCount": 0},
            }
        }
        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, json=empty_payload)

        from kosmos.tools.models import LookupCollection

        result = await executor.invoke(
            "nmc_emergency_search",
            {"lat": 37.5, "lon": 127.0, "limit": 5},
            request_id="test-req-empty",
            session_identity=object(),
        )

        assert isinstance(result, LookupCollection), (
            f"Expected LookupCollection for empty results, got {type(result).__name__}"
        )
        assert result.items == []
        assert result.total_count == 0


# ---------------------------------------------------------------------------
# T010 — Threshold integration test [US3]
# ---------------------------------------------------------------------------


class TestThresholdIntegration:
    """T010: custom nmc_freshness_minutes from settings propagates through executor pipeline."""

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.tools.nmc.freshness.datetime")
    @patch("kosmos.settings.settings")
    async def test_custom_settings_threshold_used(
        self, mock_settings, mock_dt, nmc_reg_exec
    ) -> None:
        """stale_response.json (70 min old) + threshold=120 → LookupCollection (fresh).

        The stale fixture has hvidate 13:00:00, which is 70 min old at FIXED_NOW 14:10.
        With a 120-minute threshold (70 < 120), the data should be accepted as fresh,
        proving that the custom nmc_freshness_minutes setting is honoured end-to-end.
        """
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 120  # custom 120-min threshold
        _mock_dt(mock_dt)
        registry, executor = nmc_reg_exec

        # stale_response.json: hvidate 13:00:00 → 70 min old at FIXED_NOW 14:10
        # With threshold=120, 70 < 120 → should be fresh
        payload = json.loads(_STALE_FIXTURE.read_text(encoding="utf-8"))
        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, json=payload)

        from kosmos.tools.models import LookupCollection

        result = await executor.invoke(
            "nmc_emergency_search",
            {"lat": 37.5, "lon": 127.0, "limit": 5},
            request_id="test-req-010",
            session_identity=object(),
        )

        assert isinstance(result, LookupCollection), (
            f"With threshold=120 and data age=70 min, expected LookupCollection, "
            f"got {type(result).__name__}: {result!r}"
        )
        assert result.meta.freshness_status == "fresh"
