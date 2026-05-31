# SPDX-License-Identifier: Apache-2.0
"""AirKorea response enrichment guards."""

from __future__ import annotations

import pytest

from ummaya.tools.verified_data_go_kr.airkorea_air_quality import (
    AirKoreaAirQualityInput,
    handle,
)


@pytest.mark.asyncio
async def test_airkorea_air_quality_adds_official_grade_labels() -> None:
    """AirKorea grade numbers must be exposed with their official Korean labels."""

    parsed = AirKoreaAirQualityInput.model_validate({"sido_name": "부산"})
    fixture = """
    {
      "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
        "body": {
          "items": [
            {
              "stationName": "광복동",
              "dataTime": "2026-05-29 01:00",
              "pm10Value": "27",
              "pm10Grade": "1",
              "pm25Value": "16",
              "pm25Grade": "2",
              "khaiGrade": "2"
            }
          ],
          "pageNo": 1,
          "numOfRows": 10,
          "totalCount": 1
        }
      }
    }
    """.encode()

    output = await handle(parsed, fixture_body=fixture)
    record = output["items"][0]["record"]

    assert record["pm10NameKo"] == "미세먼지(PM10)"
    assert record["pm10GradeLabelKo"] == "좋음"
    assert record["pm25NameKo"] == "초미세먼지(PM2.5)"
    assert record["pm25GradeLabelKo"] == "보통"
    assert record["khaiGradeLabelKo"] == "보통"


def test_airkorea_air_quality_normalizes_full_sido_names() -> None:
    """AirKorea city/province endpoint expects short sidoName values."""

    parsed = AirKoreaAirQualityInput.model_validate({"sido_name": "부산광역시"})

    assert parsed.sido_name == "부산"
    assert parsed.num_of_rows == 100
