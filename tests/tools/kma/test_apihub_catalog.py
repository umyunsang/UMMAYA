# SPDX-License-Identifier: Apache-2.0
"""Tests for the KMA APIHub structured operation catalog."""

from __future__ import annotations

from collections import Counter

from ummaya.tools.kma.apihub_catalog import (
    KMA_APIHUB_STRUCTURED_OPERATIONS,
    get_operation_by_id,
    get_operation_by_tool_id,
    iter_structured_operations,
)


def test_catalog_contains_all_structured_typ02_operations() -> None:
    assert len(iter_structured_operations(include_retired=True)) == 145
    assert len(iter_structured_operations()) == 77


def test_catalog_tool_ids_are_unique_and_prefixed() -> None:
    tool_ids = [operation.tool_id for operation in KMA_APIHUB_STRUCTURED_OPERATIONS]

    assert len(tool_ids) == len(set(tool_ids))
    assert all(tool_id.startswith("kma_apihub_") for tool_id in tool_ids)


def test_catalog_category_counts_match_captured_apihub_evidence() -> None:
    counts = Counter(operation.category_seq for operation in KMA_APIHUB_STRUCTURED_OPERATIONS)

    assert counts == {
        2: 23,
        3: 14,
        4: 6,
        5: 5,
        6: 20,
        7: 4,
        8: 1,
        9: 10,
        10: 13,
        12: 4,
        14: 22,
        971: 23,
    }


def test_approved_operations_match_current_mypage_evidence() -> None:
    approved = {
        operation.operation_id
        for operation in KMA_APIHUB_STRUCTURED_OPERATIONS
        if operation.approval_state == "approved"
    }

    assert len(approved) == 87
    assert {
        "AmmIwxxmService/getMetar",
        "WthrChartInfoService/getAuxillaryChart",
        "WthrChartInfoService/getSurfaceChart",
    }.issubset(approved)


def test_disabled_operations_are_kept_in_catalog_but_not_active() -> None:
    disabled = {
        operation.operation_id
        for operation in KMA_APIHUB_STRUCTURED_OPERATIONS
        if operation.availability != "active"
    }

    assert disabled == {
        "GtsInfoService/getBuoy",
        "GtsInfoService/getSynop",
        "GtsInfoService/getTemp",
        "AmmIwxxmService/getMetar",
        "NwpModelInfoService/getLdapsUnisAll",
        "NwpModelInfoService/getLdapsUnisArea",
        "NwpModelInfoService/getRdapsUnisAll",
        "NwpModelInfoService/getRdapsUnisArea",
        "WthrChartInfoService/getAuxillaryChart",
        "WthrChartInfoService/getSurfaceChart",
        "AftnAmmService/getMetar",
        "AftnAmmService/getSigmet",
        "AftnAmmService/getTaf",
        "AirInfoService/getAirInfo",
        "AirPortService/getAirPort",
        "AmmIwxxmService/getAirmet",
        "AmmIwxxmService/getSigmet",
        "AmmIwxxmService/getTaf",
        "AmmService/getAirmet",
        "AmmService/getSigmet",
        "AmmService/getTaf",
        "AmmService/getWarning",
        "AwsMtlyInfoService/getAwsStnLstTbl",
        "AwsMtlyInfoService/getDailyAwsData",
        "AwsMtlyInfoService/getMmSumry",
        "AwsMtlyInfoService/getNote",
        "AwsYearlyInfoService/getAwsStnLstTbl",
        "AwsYearlyInfoService/getNote",
        "AwsYearlyInfoService/getStnbyMmSumry",
        "AwsYearlyInfoService/getYearSumry",
        "BeachInfoservice/getSunInfoBeach",
        "BeachInfoservice/getTideInfoBeach",
        "BeachInfoservice/getTwBuoyBeach",
        "BeachInfoservice/getUltraSrtFcstBeach",
        "BeachInfoservice/getVilageFcstBeach",
        "BeachInfoservice/getWhBuoyBeach",
        "EqkInfoService/getTsunamiMsg",
        "EqkInfoService/getTsunamiMsgList",
        "FcstZoneInfoService/getFcstZoneCd",
        "FmlandWthrInfoService/getDayStatistics",
        "FmlandWthrInfoService/getFmlandPwn",
        "FmlandWthrInfoService/getFmlandVilageFcst",
        "FmlandWthrInfoService/getFmlandVilageNcst",
        "FmlandWthrInfoService/getMmStatistics",
        "FmlandWthrInfoService/getPureStatistics",
        "FrstFcstInfoService/getFrstOcurFcst",
        "GtsInfoService/getGtsStn",
        "HealthWthrIdxServiceV2/getOakPollenRiskIdxV2",
        "HealthWthrIdxServiceV2/getPinePollenRiskIdxV2",
        "HealthWthrIdxServiceV2/getWeedsPollenRiskndxV2",
        "LivingWthrIdxServiceV3/getAirDiffusionIdxV3",
        "LivingWthrIdxServiceV3/getSenTaIdxV3",
        "LivingWthrIdxServiceV3/getUVIdxV3",
        "MidFcstInfoService/getMidFcst",
        "MidFcstInfoService/getMidLandFcst",
        "MidFcstInfoService/getMidSeaFcst",
        "MidFcstInfoService/getMidTa",
        "RoadWthrInfoService/getCctvStnRoadWthr",
        "RoadWthrInfoService/getStdNodeLinkRoadWw",
        "TourStnInfoService/getCityTourClmIdx",
        "TourStnInfoService/getTourStnVilageFcst",
        "WethrBasicInfoService/getRadarObsStn",
        "WethrBasicInfoService/getWrnZoneCd",
        "WthrRadarInfoService/getSiteCappiQcdAll",
        "WthrRadarInfoService/getSiteCappiQcdArea",
        "YdstInfoService/getYdstObs",
        "YdstInfoService/getYdstSatlitImg",
        "YdstInfoService/getYdstSfcChart",
    }
    assert disabled.isdisjoint(operation.operation_id for operation in iter_structured_operations())

    assert get_operation_by_id("GtsInfoService/getSynop").availability == ("upstream_unavailable")
    assert get_operation_by_id("NwpModelInfoService/getLdapsUnisAll").availability == ("retired")
    assert get_operation_by_id("AmmIwxxmService/getMetar").availability == ("upstream_unavailable")
    assert get_operation_by_id("WthrChartInfoService/getSurfaceChart").availability == (
        "upstream_unavailable"
    )
    assert get_operation_by_id("AftnAmmService/getMetar").availability == ("approval_pending")


def test_catalog_lookup_helpers_return_stable_operations() -> None:
    operation = get_operation_by_id("AmmIwxxmService/getMetar")

    assert operation.tool_id == "kma_apihub_amm_iwxxm_service_get_metar"
    assert get_operation_by_tool_id(operation.tool_id) == operation
    assert [param.name for param in operation.request_params] == [
        "pageNo",
        "numOfRows",
        "dataType",
        "icao",
        "authKey",
    ]
    assert [param.field_name for param in operation.non_credential_params] == [
        "page_no",
        "num_of_rows",
        "data_type",
        "icao",
    ]
