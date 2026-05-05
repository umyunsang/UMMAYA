# SPDX-License-Identifier: Apache-2.0
"""Field-semantics enrichment tests for nmc_emergency_search (Spec 2637 Epic F).

Safety-critical regression: the upstream `getEgytLcinfoInqire` endpoint
returns abbreviated `startTime` / `endTime` fields whose values are the
institution's *outpatient* (외래) open/close time — NOT the emergency-room
operating window. Surfacing these raw fields as "운영시간: 08:30~17:00" to
a citizen searching for an ER is a critical mis-info pattern (snap-010,
2026-05-04). The adapter's ``_enrich_item`` MUST rewrite these fields into
explicit semantic names AND surface a 24-hour ER operating flag so the LLM
cannot render the wrong window.

Live evidence (Jongno-gu coordinates, captured during integration
verification 2026-05-04):

- 강북삼성병원 (지역응급의료센터, G006): startTime=0830, endTime=1700
- 서울대학교병원 (권역응급의료센터, G001): startTime=0800, endTime=1800
- 국립중앙의료원 (지역응급의료센터, G006): startTime=0830, endTime=1700

All three operate 24/7 ER per the ``dutyEryn=1`` flag in the sibling
``getEgytBassInfoInqire`` endpoint and per 응급의료에 관한 법률 §31.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import respx
from zoneinfo import ZoneInfo

from datetime import datetime

from kosmos.tools.executor import ToolExecutor
from kosmos.tools.nmc.emergency_search import (
    _enrich_item,
    _format_hhmm,
    register,
)
from kosmos.tools.registry import ToolRegistry

_KST = ZoneInfo("Asia/Seoul")
FIXED_NOW = datetime(2026, 5, 4, 14, 30, 0, tzinfo=_KST)


def _mock_dt(mock_dt_cls: object) -> None:
    mock_dt_cls.now.return_value = FIXED_NOW  # type: ignore[attr-defined]
    mock_dt_cls.strptime = datetime.strptime  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _format_hhmm — handles both string ("0830") and integer (1700) shapes
# ---------------------------------------------------------------------------


class TestFormatHhmm:
    """Verify HHMM normalization handles upstream's inconsistent JSON shapes."""

    def test_string_zero_padded(self) -> None:
        """`"0830"` → `"08:30"` (the wire format for startTime)."""
        assert _format_hhmm("0830") == "08:30"

    def test_string_midnight(self) -> None:
        """`"0000"` → `"00:00"`."""
        assert _format_hhmm("0000") == "00:00"

    def test_string_late_evening(self) -> None:
        """`"1830"` → `"18:30"`."""
        assert _format_hhmm("1830") == "18:30"

    def test_integer_unpadded(self) -> None:
        """`1700` → `"17:00"` (the wire format for endTime — int, no leading 0)."""
        assert _format_hhmm(1700) == "17:00"

    def test_integer_under_1000(self) -> None:
        """`830` → `"08:30"` (rare but possible — left-pad to 4)."""
        assert _format_hhmm(830) == "08:30"

    def test_integer_zero_becomes_midnight(self) -> None:
        """`0` → `"00:00"`."""
        assert _format_hhmm(0) == "00:00"

    def test_24_hour_marker_accepted(self) -> None:
        """`2400` → `"24:00"` (valid end-of-day marker per upstream convention)."""
        assert _format_hhmm(2400) == "24:00"

    def test_invalid_minute_returns_none(self) -> None:
        """Minute > 59 must reject (return None)."""
        assert _format_hhmm("0875") is None

    def test_invalid_string_returns_none(self) -> None:
        """Non-digit returns None — we never fabricate a value."""
        assert _format_hhmm("abc") is None

    def test_none_returns_none(self) -> None:
        assert _format_hhmm(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _format_hhmm("") is None


# ---------------------------------------------------------------------------
# _enrich_item — semantic field renaming + 24h ER flag
# ---------------------------------------------------------------------------


class TestEnrichItem:
    """Verify ``_enrich_item`` rewrites raw fields into safety-clear semantics.

    The 5 records below are byte-for-byte from a real Jongno-gu API call
    (2026-05-04, KOSMOS_DATA_GO_KR_API_KEY) — these are NOT a mock fixture
    but the live wire shape that the LLM is currently rendering as
    "운영시간: 08:30~17:00".
    """

    def _real_kbsmc_record(self) -> dict:
        """강북삼성병원 — live API record from 2026-05-04 Jongno-gu probe."""
        return {
            "cnt": 77,
            "distance": 1.12,
            "dutyAddr": "서울특별시 종로구 새문안로 29 (평동)",
            "dutyDiv": "A",
            "dutyDivName": "종합병원",
            "dutyFax": 20012117,
            "dutyName": "강북삼성병원",
            "dutyTel1": "02-2001-2001",
            "endTime": 1700,
            "hpid": "A1100006",
            "latitude": 37.568497631233825,
            "longitude": 126.96793805451702,
            "rnum": 4,
            "startTime": "0830",
        }

    def test_outpatient_fields_renamed(self) -> None:
        """`startTime`/`endTime` MUST be removed and replaced with explicit names."""
        out = _enrich_item(self._real_kbsmc_record())
        assert "startTime" not in out, (
            "Raw `startTime` MUST be removed — it gets rendered as ER hours by the LLM"
        )
        assert "endTime" not in out, (
            "Raw `endTime` MUST be removed — it gets rendered as ER hours by the LLM"
        )
        assert out["outpatient_open_time"] == "08:30"
        assert out["outpatient_close_time"] == "17:00"

    def test_er_24h_flag_present(self) -> None:
        """Every record from this endpoint operates a 24/7 ER by definition."""
        out = _enrich_item(self._real_kbsmc_record())
        assert out["er_24h_operating"] is True
        # The note must explicitly disambiguate so a downstream reader cannot
        # mis-interpret outpatient_*_time as ER hours.
        assert "24시간" in out["er_operating_hours_note"]
        assert "외래진료" in out["er_operating_hours_note"]

    def test_outpatient_hours_display_includes_outpatient_label(self) -> None:
        """The display string MUST carry the '외래진료' label so it is never
        rendered as ER hours by accident."""
        out = _enrich_item(self._real_kbsmc_record())
        assert "외래진료" in out["outpatient_hours_display"]
        assert "08:30~17:00" in out["outpatient_hours_display"]

    def test_phone_aliased_with_warning(self) -> None:
        """`dutyTel1` is the hospital main switchboard, NOT the ER hotline.
        We surface it under a clearer name AND attach a warning note."""
        out = _enrich_item(self._real_kbsmc_record())
        assert out["hospital_main_phone"] == "02-2001-2001"
        assert "병원 대표번호" in out["er_phone_note"]
        assert "응급실 직통" in out["er_phone_note"]

    def test_hospital_type_distinguished_from_er_class(self) -> None:
        """`dutyDivName` (의료기관 종별) must NOT be confused with `dutyEmclsName`
        (응급의료센터 등급)."""
        out = _enrich_item(self._real_kbsmc_record())
        assert out["hospital_type"] == "종합병원"
        assert "응급의료센터 등급 아님" in out["hospital_type_note"]

    def test_raw_values_preserved_under_underscore_prefix(self) -> None:
        """Raw upstream values are kept under `_raw_*` keys for explicit consumers."""
        out = _enrich_item(self._real_kbsmc_record())
        assert out["_raw_outpatient_start_hhmm"] == "0830"
        assert out["_raw_outpatient_end_hhmm"] == 1700

    def test_passthrough_fields_preserved(self) -> None:
        """Distance, address, hpid, lat/lon must pass through unchanged."""
        raw = self._real_kbsmc_record()
        out = _enrich_item(raw)
        assert out["distance"] == raw["distance"]
        assert out["dutyAddr"] == raw["dutyAddr"]
        assert out["hpid"] == raw["hpid"]
        assert out["latitude"] == raw["latitude"]
        assert out["longitude"] == raw["longitude"]
        assert out["dutyName"] == raw["dutyName"]

    def test_does_not_mutate_caller(self) -> None:
        """Enrichment must return a fresh dict — never mutate the caller's record."""
        raw = self._real_kbsmc_record()
        snapshot = dict(raw)
        _enrich_item(raw)
        assert raw == snapshot, "Enrichment leaked mutation back into caller"

    def test_missing_fields_handled(self) -> None:
        """A record with no startTime/endTime/dutyTel1/dutyDivName must not crash."""
        out = _enrich_item({"dutyName": "Some Hospital", "hpid": "X1234567"})
        assert out["er_24h_operating"] is True
        assert out["outpatient_open_time"] is None
        assert out["outpatient_close_time"] is None
        assert out["outpatient_hours_display"] is None
        assert "hospital_main_phone" not in out
        assert "hospital_type" not in out

    def test_partial_hours_handled(self) -> None:
        """Half-present hours must render gracefully ('미상' marker)."""
        out = _enrich_item({"startTime": "0830", "dutyName": "x"})
        assert out["outpatient_open_time"] == "08:30"
        assert out["outpatient_close_time"] is None
        assert "미상" in out["outpatient_hours_display"]

    def test_24h_record_renders_as_zero_to_24(self) -> None:
        """Hypothetical 0000-2400 (rare; confirms 24h-marker doesn't wrap)."""
        out = _enrich_item({"startTime": "0000", "endTime": 2400, "dutyName": "x"})
        assert out["outpatient_open_time"] == "00:00"
        assert out["outpatient_close_time"] == "24:00"


# ---------------------------------------------------------------------------
# End-to-end: enrichment flows through the executor pipeline
# ---------------------------------------------------------------------------


@pytest.fixture()
def nmc_reg_exec():
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)
    return registry, executor


class TestEnrichmentEndToEnd:
    """Verify enrichment flows through `handle()` and the executor pipeline."""

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.tools.nmc.freshness.datetime")
    @patch("kosmos.settings.settings")
    async def test_live_jongno_response_enriched(
        self, mock_settings, mock_dt, nmc_reg_exec
    ) -> None:
        """A real Jongno-gu API response shape MUST surface enriched fields, not raw."""
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 30
        _mock_dt(mock_dt)
        _registry, executor = nmc_reg_exec

        live_payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {
                    "items": {
                        "item": [
                            {
                                "cnt": 77,
                                "distance": 1.12,
                                "dutyAddr": "서울특별시 종로구 새문안로 29 (평동)",
                                "dutyDivName": "종합병원",
                                "dutyName": "강북삼성병원",
                                "dutyTel1": "02-2001-2001",
                                "endTime": 1700,
                                "hpid": "A1100006",
                                "latitude": 37.568497631233825,
                                "longitude": 126.96793805451702,
                                "startTime": "0830",
                            },
                            {
                                "cnt": 77,
                                "distance": 1.88,
                                "dutyAddr": "서울특별시 종로구 대학로 101 (연건동)",
                                "dutyDivName": "종합병원",
                                "dutyName": "서울대학교병원",
                                "dutyTel1": "02-1588-5700",
                                "endTime": 1800,
                                "hpid": "A1100017",
                                "latitude": 37.57966608924356,
                                "longitude": 126.99896308412191,
                                "startTime": "0800",
                            },
                        ]
                    },
                    "numOfRows": 2,
                    "pageNo": 1,
                    "totalCount": 76,
                },
            }
        }
        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, json=live_payload)

        from kosmos.tools.models import LookupCollection

        result = await executor.invoke(
            "nmc_emergency_search",
            {"lat": 37.5729, "lon": 126.9794, "limit": 2},
            request_id="test-req-jongno-live-shape",
            session_identity=object(),
        )

        assert isinstance(result, LookupCollection), (
            f"Expected LookupCollection, got {type(result).__name__}: {result!r}"
        )
        assert len(result.items) == 2

        # CRITICAL: The dangerous raw fields MUST NOT appear in the
        # LLM-visible output, because past observations (snap-010, 2026-05-04)
        # show the LLM renders them as "응급실 운영시간" → safety risk.
        for item in result.items:
            assert "startTime" not in item, (
                f"raw startTime leaked through enrichment for {item.get('dutyName')}: "
                f"the LLM will mis-render this as ER hours"
            )
            assert "endTime" not in item, (
                f"raw endTime leaked through enrichment for {item.get('dutyName')}: "
                f"the LLM will mis-render this as ER hours"
            )
            assert item["er_24h_operating"] is True
            assert "외래진료" in item["outpatient_hours_display"]

        # Spot-check the SNUH record specifically — known 24h Level-1 trauma
        # whose API record shows 0800-1800 (clearly outpatient).
        snuh = next(i for i in result.items if i["dutyName"] == "서울대학교병원")
        assert snuh["outpatient_open_time"] == "08:00"
        assert snuh["outpatient_close_time"] == "18:00"
        assert snuh["er_24h_operating"] is True
