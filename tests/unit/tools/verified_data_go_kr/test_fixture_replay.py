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
    "tago_bus_route_station_search": (
        {"city_code": "21", "route_id": "BSB5201001000", "page_no": 1, "num_of_rows": 100},
        "15098529/probes/live-2026-05-28/tago-bus-route-station.body.xml",
        "nodeid",
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
        {
            "inqry_div": "1",
            "inqry_bgn_dt": "202507010000",
            "inqry_end_dt": "202507012359",
            "bid_ntce_nm": "전기공사",
            "page_no": 1,
            "num_of_rows": 10,
        },
        "15129394/probes/live-2026-05-27/pps-bid-construction-search.body.json",
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
    "moj_village_lawyer_lookup": (
        {"page_no": 1, "num_of_rows": 5},
        "15121954/probes/live-2026-05-16-direct-check/moj-village-lawyer-http.body",
        "Attorney",
    ),
    "mois_facility_safety_info_lookup": (
        {"fclts_nm": "호텔", "page_no": 1, "num_of_rows": 5},
        "15073554/probes/live-2026-05-16-direct-check/mois-facility-safety-search.body",
        "fcltyNm",
    ),
    "hira_medical_institution_detail": (
        {
            "ykiho": (
                "JDQ4MTYyMiM1MSMkMSMkMCMkODkkMzgxMzUxIzIxIyQxIyQ5IyQ3MiQyNjEyMjIjNjEjJDEjJDgjJDgz"
            )
        },
        "15001699/probes/live-2026-05-16-direct-check/hira-medical-detail.body",
        "emyDayYn",
    ),
    "mois_emergency_call_box_lookup": (
        {"road_address": "서울", "page_no": 1, "num_of_rows": 5},
        "15155046/probes/live-2026-05-16-direct-check/emergency-call-box.body",
        "INSTL_PSTN",
    ),
    "djtc_subway_segment_fare_time_check": (
        {"strstnno": "104", "endstnno": "111"},
        "15158794/probes/live-2026-05-16-direct-check/djtc-time-distance.body",
        "fee",
    ),
    "gyeryong_assistive_device_charging_place_locate": (
        {"current_page": 1, "per_page": 5, "indoor_outdoor": "실내"},
        "15096040/probes/live-2026-05-16-direct-check/gyeryong-charger.body",
        "INSTL_PLACE",
    ),
    "nmc_aed_site_locate": (
        {"q0": "서울특별시", "q1": "종로구", "page_no": 1, "num_of_rows": 5},
        "15000652/probes/live-2026-05-16-direct-check/nmc-aed-manage.body",
        "buildAddress",
    ),
    "mof_ocean_water_quality_check": (
        {"station_code": "SEA3003", "page_no": 1, "num_of_rows": 5},
        "15127779/probes/live-2026-05-16-direct-check/ocean-water-quality.body",
        "rtmWqWtchStaCd",
    ),
    "mfds_easy_drug_info_lookup": (
        {"item_name": "타이레놀", "page_no": 1, "num_of_rows": 5},
        "15075057/probes/live-2026-05-16-direct-check/mfds-easy-drug.body",
        "itemName",
    ),
    "mpm_public_job_lookup": (
        {
            "pblanc_ty": "e01",
            "instt_se": "g01",
            "sort_order": "내림차순",
            "page_no": 1,
            "num_of_rows": 5,
        },
        "15156780/probes/live-2026-05-16-direct-check/mpm-public-job-g01.body",
        "insttname",
    ),
    "pps_shopping_mall_product_lookup": (
        {"inqry_div": "1", "prdct_clsfc_no_nm": "의자", "page_no": 1, "num_of_rows": 5},
        "15129471/probes/live-2026-05-16-direct-check/pps-shopping-product.body",
        "cntrctCorpNm",
    ),
    "ksd_financial_term_lookup": (
        {"term": "주식", "page_no": 1, "num_of_rows": 5},
        "15158905/probes/live-2026-05-16-direct-check/ksd-financial-term.body",
        "fnceDictNm",
    ),
    "mss_sme_support_notice_lookup": (
        {"hashtags": "소상공인", "page_no": 1, "num_of_rows": 5},
        "15157820/probes/live-2026-05-16-direct-check/sme-support-announcement.body",
        "pblancNm",
    ),
    "ccourt_publication_documents": (
        {"title": "헌법", "page_no": 1, "num_of_rows": 5},
        "15140950/probes/live-2026-05-16-direct-check/ccourt-publication.body",
        "title",
    ),
    "moj_stay_person_counter": (
        {"search_ym": "202504", "page_no": 1, "num_of_rows": 5},
        "15149906/probes/live-2026-05-16-blocker-resolution/moj-gateway-ServiceKey.body",
        "division",
    ),
    "msit_business_announcement_lookup": (
        {"page_no": 1, "num_of_rows": 10, "return_type": "xml"},
        "15074634/probes/live-2026-05-16-blocker-resolution/msit-rawkey-ua-only.body",
        "subject",
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


@pytest.mark.asyncio
async def test_tago_bus_arrival_accepts_route_no_as_response_filter() -> None:
    module = module_for_tool_id("tago_bus_arrival_search")
    fixture_body = (
        FIXTURES / "15098530/probes/live-2026-05-16-direct-check/tago-bus-arrival.body"
    ).read_bytes()

    validated_input = module.INPUT_SCHEMA.model_validate(
        {
            "city_code": "25",
            "node_id": "DJB8001793",
            "route_no": "301",
            "page_no": 1,
            "num_of_rows": 5,
        }
    )
    raw = await module.handle(validated_input, fixture_body=fixture_body)

    assert raw["kind"] == "collection"
    assert raw["total_count"] == 1
    assert raw["items"][0]["record"]["routeno"] == "301"
    assert raw["items"][0]["record"]["routeid"] == "DJB30300054"


@pytest.mark.asyncio
async def test_tago_bus_route_station_accepts_node_name_as_response_filter() -> None:
    module = module_for_tool_id("tago_bus_route_station_search")
    fixture_body = (
        FIXTURES / "15098529/probes/live-2026-05-28/tago-bus-route-station.body.xml"
    ).read_bytes()

    validated_input = module.INPUT_SCHEMA.model_validate(
        {
            "city_code": "21",
            "route_id": "BSB5201001000",
            "node_nm": "부산역",
            "page_no": 1,
            "num_of_rows": 100,
        }
    )
    raw = await module.handle(validated_input, fixture_body=fixture_body)

    assert raw["kind"] == "collection"
    assert raw["total_count"] == 2
    node_ids = {item["record"]["nodeid"] for item in raw["items"]}
    assert node_ids == {"BSB509950000", "BSB509960000"}


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
