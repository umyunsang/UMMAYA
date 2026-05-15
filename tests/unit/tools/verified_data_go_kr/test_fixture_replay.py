# SPDX-License-Identifier: Apache-2.0
"""Fixture replay through adapter handles, without live network calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from ummaya.tools.envelope import normalize
from ummaya.tools.models import LookupCollection
from ummaya.tools.verified_data_go_kr import (
    VERIFIED_DATA_GO_KR_ADAPTERS,
    module_for_tool_id,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "docs/api/data-go-kr-candidate-docs"

FIXTURE_CASES = {
    "fsc_corporate_finance_summary": (
        {"crno": "1746110000741", "biz_year": "2019", "page_no": 1, "num_of_rows": 1},
        "15043459/probes/live-2026-05-16/corporate-finance-summary.body.json",
        "crno",
    ),
    "airkorea_ctprvn_air_quality": (
        {"sido_name": "서울", "page_no": 1, "num_of_rows": 5, "ver": "1.0"},
        "15073861/probes/live-2026-05-16/airkorea-ctprvn.body.json",
        "stationName",
    ),
    "ftc_large_group_status": (
        {"presentn_year": "202105", "page_no": 1, "num_of_rows": 10},
        "15091886/probes/live-2026-05-16/ftc-large-group.body.xml",
        "unityGrupNm",
    ),
    "ftc_public_ym_list": (
        {"job_se_code": "0001", "presentn_year": "2021", "page_no": 1, "num_of_rows": 10},
        "15091910/probes/live-2026-05-16/ftc-public-ym.body.xml",
        "othbcYm",
    ),
    "tago_bus_route_search": (
        {"city_code": "25", "route_no": "5", "page_no": 1, "num_of_rows": 10},
        "15098529/probes/live-2026-05-16/tago-bus-route.body.xml",
        "routeid",
    ),
    "tago_bus_arrival_search": (
        {"city_code": "25", "node_id": "DJB8001793", "page_no": 1, "num_of_rows": 10},
        "15098530/probes/live-2026-05-16/tago-bus-arrival.body.xml",
        None,
    ),
    "tago_bus_location_search": (
        {"city_code": "25", "route_id": "DJB30300052", "page_no": 1, "num_of_rows": 10},
        "15098533/probes/live-2026-05-16/tago-bus-location.body.xml",
        None,
    ),
    "tago_bus_station_search": (
        {
            "city_code": "25",
            "node_nm": "전통시장",
            "node_no": "44810",
            "page_no": 1,
            "num_of_rows": 10,
        },
        "15098534/probes/live-2026-05-16/tago-bus-station.body.xml",
        "nodeid",
    ),
    "kepco_contract_power_usage": (
        {
            "year": "2020",
            "month": "11",
            "metro_cd": "11",
            "city_cd": "110",
            "cntr_cd": "100",
        },
        "15101360/probes/live-2026-05-16/kepco-contract-type.body.json",
        "powerUsage",
    ),
    "pps_bid_public_info": (
        {"inqry_div": "2", "bid_ntce_no": "R25BK00934017", "page_no": 1, "num_of_rows": 10},
        "15129394/probes/live-2026-05-16/pps-bid-service.body.json",
        "bidNtceNo",
    ),
    "reb_real_estate_stat_table": (
        {"p_index": 1, "p_size": 5},
        "15134761/probes/live-2026-05-16/reb-stat-table.body.json",
        "STATBL_ID",
    ),
    "bfc_funeral_area_fee": (
        {"page_no": 1, "num_of_rows": 5},
        "15157485/probes/live-2026-05-16/funeral-area-list.body.json",
        "faName",
    ),
    "kcue_finance_regional_tuition": (
        {"schl_div_cd": "02", "page_no": 1, "num_of_rows": 5},
        "15158680/probes/live-2026-05-16/finance-regional-tuition.body.xml",
        "schlDivCd",
    ),
    "kcue_student_regional_foreign": (
        {"schl_div_cd": "02", "page_no": 1, "num_of_rows": 5},
        "15158684/probes/live-2026-05-16/student-regional-foreign.body.xml",
        "schlDivCd",
    ),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("spec", VERIFIED_DATA_GO_KR_ADAPTERS, ids=lambda spec: spec.tool_id)
async def test_adapter_handle_replays_live_probe_fixture(spec: object) -> None:
    module = module_for_tool_id(spec.tool_id)
    params, relpath, expected_field = FIXTURE_CASES[spec.tool_id]
    fixture_body = (FIXTURES / relpath).read_bytes()

    validated_input = module.INPUT_SCHEMA.model_validate(params)
    raw = await module.handle(validated_input, fixture_body=fixture_body)

    assert raw["kind"] == "collection"
    assert raw["total_count"] >= 0
    assert isinstance(raw["items"], list)
    if expected_field is not None:
        assert raw["items"]
        assert expected_field in raw["items"][0]["record"]


def test_kepco_input_accepts_official_wire_param_aliases() -> None:
    """KEPCO public docs expose metroCd/cityCd/cntrCd, while model fields stay snake_case."""

    module = module_for_tool_id("kepco_contract_power_usage")

    validated_input = module.INPUT_SCHEMA.model_validate(
        {
            "year": "2020",
            "month": "11",
            "metroCd": "11",
            "cityCd": "110",
            "cntrCd": "100",
        }
    )

    assert validated_input.model_dump(mode="python") == {
        "year": "2020",
        "month": "11",
        "metro_cd": "11",
        "city_cd": "110",
        "cntr_cd": "100",
    }


@pytest.mark.asyncio
async def test_adapter_fixture_output_normalizes_to_lookup_collection() -> None:
    spec = next(
        item for item in VERIFIED_DATA_GO_KR_ADAPTERS if item.tool_id == "bfc_funeral_area_fee"
    )
    module = module_for_tool_id(spec.tool_id)
    fixture_body = (
        FIXTURES / "15157485/probes/live-2026-05-16/funeral-area-list.body.json"
    ).read_bytes()

    validated_input = module.INPUT_SCHEMA.model_validate({"page_no": 1, "num_of_rows": 5})
    raw = await module.handle(validated_input, fixture_body=fixture_body)
    validated = normalize(raw, module.TOOL, request_id="fixture-replay", elapsed_ms=5)

    assert isinstance(validated, LookupCollection)
    assert validated.meta.source == "bfc_funeral_area_fee"
    assert validated.total_count == 4
