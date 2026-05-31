# SPDX-License-Identifier: Apache-2.0
"""PPS bid public information contract guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ummaya.tools.verified_data_go_kr._manifest import require_spec
from ummaya.tools.verified_data_go_kr.pps_bid_public_info import (
    PpsBidPublicInfoInput,
    handle,
)


def test_pps_bid_public_info_schema_matches_search_condition_operation() -> None:
    """The model-facing contract must fit ordinary list searches, not only detail lookup."""

    schema = PpsBidPublicInfoInput.model_json_schema()
    properties = schema["properties"]

    assert schema["required"] == ["inqry_bgn_dt", "inqry_end_dt"]
    assert "bid_ntce_no" not in properties
    assert "inqry_bgn_dt" in properties
    assert "inqry_end_dt" in properties
    assert "bid_ntce_nm" in properties
    assert "ntce_instt_nm" in properties
    assert "dminstt_nm" in properties
    assert "region_name" in properties
    assert "prtcpt_lmt_rgn_nm" in properties
    assert "indstryty_nm" in properties
    assert "31 days" in properties["inqry_bgn_dt"]["description"]
    assert "31 days" in properties["inqry_end_dt"]["description"]


def test_pps_bid_public_info_accepts_busan_electrical_construction_search() -> None:
    """A real citizen phrase maps to official PPS search-condition fields."""

    parsed = PpsBidPublicInfoInput.model_validate(
        {
            "inqry_div": "1",
            "inqry_bgn_dt": "202605270000",
            "inqry_end_dt": "202606022359",
            "bid_ntce_nm": "전기공사",
            "region_name": "부산광역시",
            "prtcpt_lmt_rgn_nm": "부산광역시",
            "indstryty_nm": "전기공사업",
        }
    )

    assert parsed.inqry_div == "1"
    assert parsed.bid_ntce_nm == "전기공사"
    assert parsed.region_name == "부산광역시"
    assert parsed.prtcpt_lmt_rgn_nm == "부산광역시"
    assert parsed.indstryty_nm == "전기공사업"


def test_pps_bid_public_info_manifest_uses_construction_search_operation() -> None:
    """The manifest must map snake_case fields to official PPS query names."""

    spec = require_spec("pps_bid_public_info")

    assert spec.endpoint.endswith("/getBidPblancListInfoCnstwkPPSSrch")
    assert spec.query_param_map["inqry_bgn_dt"] == "inqryBgnDt"
    assert spec.query_param_map["inqry_end_dt"] == "inqryEndDt"
    assert spec.query_param_map["bid_ntce_nm"] == "bidNtceNm"
    assert spec.query_param_map["prtcpt_lmt_rgn_nm"] == "prtcptLmtRgnNm"
    assert "region_name" not in spec.query_param_map
    assert spec.query_param_map["indstryty_nm"] == "indstrytyNm"
    assert "getBidPblancListInfoCnstwkPPSSrch" in spec.llm_description
    assert "31-day-or-smaller" in spec.llm_description


def test_pps_bid_public_info_rejects_over_broad_search_window() -> None:
    """PPS upstream reports resultCode 07 for over-broad windows, so block locally."""

    with pytest.raises(ValidationError) as exc_info:
        PpsBidPublicInfoInput.model_validate(
            {
                "inqry_div": "1",
                "inqry_bgn_dt": "202603240000",
                "inqry_end_dt": "202605312359",
                "bid_ntce_nm": "태블릿",
            }
        )

    assert "31-day-or-smaller" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pps_bid_public_info_filters_region_name_client_side() -> None:
    """Citizen region wording filters official PPS rows by documented region fields."""

    parsed = PpsBidPublicInfoInput.model_validate(
        {
            "inqry_div": "1",
            "inqry_bgn_dt": "202605250000",
            "inqry_end_dt": "202605292359",
            "bid_ntce_nm": "전기공사",
            "region_name": "부산광역시",
            "indstryty_nm": "전기공사업",
        }
    )
    fixture = """
    {
      "response": {
        "header": {"resultCode": "00", "resultMsg": "정상"},
        "body": {
          "items": [
            {
              "bidNtceNm": "부산항 배전반 전기공사",
              "ntceInsttNm": "부산광역시",
              "dminsttNm": "부산광역시",
              "cnstrtsiteRgnNm": "부산광역시 동구"
            },
            {
              "bidNtceNm": "충주 배전반 전기공사",
              "ntceInsttNm": "충청북도 충주시",
              "dminsttNm": "충청북도 충주시",
              "cnstrtsiteRgnNm": "충청북도 충주시"
            }
          ],
          "pageNo": 1,
          "numOfRows": 10,
          "totalCount": 2
        }
      }
    }
    """.encode()

    output = await handle(parsed, fixture_body=fixture)

    assert output["total_count"] == 1
    assert output["items"][0]["record"]["bidNtceNm"] == "부산항 배전반 전기공사"
    assert output["meta"]["upstream_total_count"] == 2
    assert output["meta"]["client_filter"]["field"] == "region_name"
