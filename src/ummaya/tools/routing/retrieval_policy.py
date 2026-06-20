# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from ummaya.tools.routing.intent import ToolSelectionIntent, extract_tool_selection_intent

_KCUE_TOOL_IDS = frozenset(
    {
        "kcue_finance_regional_tuition",
        "kcue_student_regional_foreign",
    }
)
_DOCUMENT_TOOL_IDS = frozenset({"document"})
_KMA_URL_AIR_TOOL_IDS = frozenset(
    {
        "kma_apihub_url_air_amos_minute",
        "kma_apihub_url_air_metar_decoded",
    }
)
_KMA_ANALYSIS_TOOL_IDS = frozenset(
    {
        "kma_apihub_url_high_resolution_grid_point",
        "kma_apihub_url_aws_objective_analysis_grid",
        "kma_apihub_url_analysis_weather_chart_image",
    }
)
_KMA_LIFESTYLE_WEATHER_TOOL_IDS = frozenset(
    {
        "kma_current_observation",
        "kma_ultra_short_term_forecast",
        "kma_short_term_forecast",
    }
)
_LOCATION_TOOL_IDS = frozenset(
    {
        "locate",
        "kakao_address_search",
        "kakao_keyword_search",
        "kakao_coord_to_region",
        "juso_adm_cd_lookup",
        "sgis_adm_cd_lookup",
    }
)
_AIRKOREA_TOOL_IDS = frozenset({"airkorea_ctprvn_air_quality"})
_DJTC_SUBWAY_SEGMENT_TOOL_IDS = frozenset({"djtc_subway_segment_fare_time_check"})


def expand_query_for_adapter_retrieval(query: str) -> str:
    intent = extract_tool_selection_intent(query)
    return expand_query_for_intent(query, intent)


def expand_query_for_intent(query: str, intent: ToolSelectionIntent) -> str:
    additions: list[str] = []
    is_airport_aviation_query = intent.has_public_data_ref("kma_airport_aviation")
    if is_airport_aviation_query:
        additions.extend(_airport_aviation_additions(intent))
    if intent.has_public_data_ref("kma_analysis_data"):
        additions.extend(_kma_analysis_data_additions())
    if intent.has_public_data_ref("kma_lifestyle_weather"):
        additions.extend(_kma_lifestyle_weather_additions())
    if intent.has_location_ref("poi") and not is_airport_aviation_query:
        additions.extend(["장소", "키워드", "POI", "랜드마크", "역", "keyword"])
    if intent.has_location_ref("admin"):
        additions.extend(["주소", "행정동", "법정동", "도로명", "지번", "address"])
    if intent.has_public_data_ref("emergency_medical"):
        additions.extend(["응급실", "응급의료", "NMC", "emergency"])
    if intent.has_public_data_ref("aed"):
        additions.extend(["AED", "자동심장충격기", "자동제세동기", "국립중앙의료원"])
    additions.extend(_emergency_chain_additions(intent))
    additions.extend(_pps_bid_additions(intent))
    additions.extend(_airkorea_air_quality_additions(intent))
    additions.extend(_djtc_subway_segment_additions(intent))
    additions.extend(_kcue_regional_additions(intent))
    additions.extend(_ocean_water_quality_additions(intent))
    additions.extend(_health_detail_additions(intent))
    additions.extend(_document_harness_additions(intent))
    additions.extend(_public_safety_location_additions(intent))
    if intent.has_public_data_ref("traffic_hazard"):
        additions.extend(_traffic_hazard_additions())
    if not additions:
        return query
    return f"{query} {' '.join(additions)}"


def filter_special_case_scores(
    intent: ToolSelectionIntent,
    scored: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    is_airport_aviation_query = intent.has_public_data_ref("kma_airport_aviation")
    is_analysis_query = intent.has_public_data_ref("kma_analysis_data")
    is_analysis_map_query = intent.has_public_data_ref("kma_analysis_map")
    is_analysis_point_query = (
        intent.has_public_data_ref("kma_analysis_point") and not is_analysis_map_query
    )
    is_lifestyle_weather_query = intent.has_public_data_ref("kma_lifestyle_weather")
    scored = _filter_initial_special_scores(intent, scored)
    if is_analysis_query:
        scored = _filter_kma_analysis_scores(
            scored,
            is_analysis_map_query=is_analysis_map_query,
            is_analysis_point_query=is_analysis_point_query,
            prefer_poi_location=intent.has_location_ref("poi"),
        )
    if is_lifestyle_weather_query:
        scored = _filter_kma_lifestyle_weather_scores(scored)
    scored = _filter_document_harness_scores(intent, scored)
    scored = _filter_emergency_chain_scores(intent, scored)
    scored = _filter_pps_bid_scores(intent, scored)
    scored = _filter_airkorea_air_quality_scores(intent, scored)
    scored = _filter_djtc_subway_segment_scores(intent, scored)
    scored = _filter_kcue_regional_scores(intent, scored)
    scored = _filter_health_detail_scores(intent, scored)
    scored = _filter_public_safety_location_scores(intent, scored)
    scored = _filter_ocean_water_quality_scores(intent, scored)
    scored = _filter_kma_aviation_scores(
        intent, scored, is_airport_aviation_query=is_airport_aviation_query
    )
    scored = _boost_aed_scores(intent, scored)

    return [
        (tool_id, score + 1000.0 if tool_id in intent.explicit_tool_ids else score)
        for tool_id, score in scored
    ]


def is_document_harness_query(query: str) -> bool:
    return extract_tool_selection_intent(query).has_document_ref("document_harness")


def _filter_kma_analysis_scores(
    scored: list[tuple[str, float]],
    *,
    is_analysis_map_query: bool,
    is_analysis_point_query: bool,
    prefer_poi_location: bool,
) -> list[tuple[str, float]]:
    chart_boost = 900.0 if is_analysis_map_query else 150.0
    if is_analysis_point_query and not is_analysis_map_query:
        chart_boost = -20.0
    analysis_boosts = {
        "kma_apihub_url_analysis_weather_chart_image": chart_boost,
        "kma_apihub_url_high_resolution_grid_point": (900.0 if is_analysis_point_query else 450.0),
        "kma_apihub_url_aws_objective_analysis_grid": (800.0 if is_analysis_point_query else 400.0),
    }
    allowed_location_ids = _LOCATION_TOOL_IDS if is_analysis_point_query else frozenset()
    adjusted: list[tuple[str, float]] = []
    for tool_id, score in scored:
        if tool_id in _KMA_ANALYSIS_TOOL_IDS:
            adjusted.append((tool_id, score + analysis_boosts.get(tool_id, 0.0)))
            continue
        if tool_id in allowed_location_ids:
            location_score = max(1.0, score - 10.0)
            if prefer_poi_location and tool_id == "kakao_keyword_search":
                location_score += 30.0
            elif prefer_poi_location and tool_id == "kakao_address_search":
                location_score = max(1.0, location_score - 15.0)
            adjusted.append((tool_id, location_score))
    return adjusted


def _kma_lifestyle_weather_additions() -> list[str]:
    return [
        "기상청",
        "KMA",
        "현재날씨",
        "초단기실황",
        "초단기예보",
        "단기예보",
        "강수",
        "우산",
        "nx",
        "ny",
        "base_date",
        "base_time",
        "current",
        "observation",
        "forecast",
        "precipitation",
    ]


def _airport_aviation_additions(intent: ToolSelectionIntent) -> list[str]:
    additions = [
        "METAR",
        "SPECI",
        "AMOS",
        "항공기상",
        "공항기상",
        "항공",
        "비행기",
        "항공편",
        "운항",
        "이륙",
        "시정",
        "RVR",
        "wind",
        "visibility",
    ]
    if intent.has_public_data_ref("kma_gimpo_airport") and intent.has_public_data_ref(
        "kma_runway_area"
    ):
        additions.extend(["AMOS", "공항기상관측", "매분자료", "활주로", "김포공항", "stn110"])
    return additions


def _kma_analysis_data_additions() -> list[str]:
    return [
        "분석자료",
        "고해상도",
        "격자자료",
        "객관분석",
        "AWS",
        "분석일기도",
        "지도",
        "비구름",
        "바람흐름",
        "objective",
        "analysis",
        "grid",
        "chart",
    ]


def _traffic_hazard_additions() -> list[str]:
    return [
        "교통사고",
        "사고다발구역",
        "위험지점",
        "도로위험구역",
        "어린이보호구역",
        "행정동코드",
        "KOROAD",
        "accident",
        "hazard",
    ]


def _emergency_chain_additions(intent: ToolSelectionIntent) -> list[str]:
    if not intent.has_public_data_ref("emergency_medical"):
        return []
    additions = [
        "응급실",
        "응급의료",
        "자동심장충격기",
        "AED",
        "국립중앙의료원",
        "NMC",
        "nearby",
        "emergency",
        "hospital",
    ]
    if intent.has_location_ref("poi"):
        additions.extend(["장소", "키워드", "POI", "랜드마크", "역", "keyword"])
    return additions


def _public_safety_location_additions(intent: ToolSelectionIntent) -> list[str]:
    additions: list[str] = []
    if intent.has_public_data_ref("mois_emergency_call_box"):
        additions.extend(
            [
                "안전비상벨",
                "비상벨",
                "긴급신고함",
                "방범",
                "행정안전부",
                "MOIS",
                "emergency",
                "call",
                "box",
            ]
        )
    if intent.has_public_data_ref("gyeryong_assistive_charger"):
        additions.extend(
            [
                "계룡시",
                "전동보장구",
                "전동휠체어",
                "장애인",
                "충전소",
                "충전장소",
                "accessibility",
                "charger",
            ]
        )
    return additions


def _ocean_water_quality_additions(intent: ToolSelectionIntent) -> list[str]:
    if not intent.has_public_data_ref("mof_ocean_water_quality"):
        return []
    return [
        "해양수산부",
        "해양수질",
        "수질자동측정망",
        "관측소",
        "SEA3003",
        "용존산소",
        "water",
        "quality",
        "ocean",
    ]


def _pps_bid_additions(intent: ToolSelectionIntent) -> list[str]:
    if not intent.has_public_data_ref("pps_bid"):
        return []
    return [
        "조달청",
        "나라장터",
        "입찰공고",
        "공사입찰",
        "bidNtceNm",
        "inqryBgnDt",
        "inqryEndDt",
        "PPS",
        "bid",
        "procurement",
    ]


def _airkorea_air_quality_additions(intent: ToolSelectionIntent) -> list[str]:
    if not intent.has_public_data_ref("airkorea_air_quality"):
        return []
    return [
        "에어코리아",
        "AirKorea",
        "미세먼지",
        "초미세먼지",
        "대기질",
        "대기오염",
        "공기질",
        "PM10",
        "PM2.5",
        "sido_name",
        "city province air quality",
    ]


def _djtc_subway_segment_additions(intent: ToolSelectionIntent) -> list[str]:
    if not intent.has_public_data_ref("djtc_subway_segment"):
        return []
    return [
        "대전교통공사",
        "대전도시철도",
        "역간",
        "소요시간",
        "거리",
        "요금",
        "운임",
        "DJTC",
        "strstnno",
        "endstnno",
        "subway segment fare time distance",
    ]


def _kcue_regional_additions(intent: ToolSelectionIntent) -> list[str]:
    if not intent.has_public_data_ref("kcue_regional"):
        return []
    additions = [
        "한국대학교육협의회",
        "대학알리미",
        "대학정보공시",
        "학교구분코드",
        "schlDivCd",
        "지역별통계",
        "KCUE",
    ]
    if intent.has_public_data_ref("kcue_regional_finance"):
        additions.extend(["재정현황", "등록금", "FinancesService", "regional tuition"])
    if intent.has_public_data_ref("kcue_regional_foreign_student"):
        additions.extend(["학생현황", "외국인유학생", "regional foreign student"])
    return additions


def _health_detail_additions(intent: ToolSelectionIntent) -> list[str]:
    if not intent.has_public_data_ref("hira_medical_detail"):
        return []
    return [
        "의료기관",
        "상세정보",
        "진료과목",
        "진료시간",
        "주차",
        "요양기호",
        "ykiho",
        "HIRA",
        "hospital",
        "detail",
    ]


def _document_harness_additions(intent: ToolSelectionIntent) -> list[str]:
    if not intent.has_document_ref("document_harness"):
        return []
    return [
        "document",
        "document.path",
        "local",
        "file",
        "path",
        "artifact_refs",
        "public",
        "document",
        "harness",
        "form",
        "render",
        "diff",
        "save",
    ]


def _filter_kma_lifestyle_weather_scores(
    scored: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    allowed_tool_ids = _KMA_LIFESTYLE_WEATHER_TOOL_IDS | _LOCATION_TOOL_IDS
    if any(tool_id in allowed_tool_ids for tool_id, _ in scored):
        scored = [(tool_id, score) for tool_id, score in scored if tool_id in allowed_tool_ids]
    boosts = {
        "kakao_keyword_search": 1100.0,
        "kakao_address_search": 1000.0,
        "kma_current_observation": 900.0,
        "kma_ultra_short_term_forecast": 800.0,
        "kma_short_term_forecast": 650.0,
        "kakao_coord_to_region": 260.0,
        "juso_adm_cd_lookup": 260.0,
        "sgis_adm_cd_lookup": 260.0,
    }
    return [(tool_id, score + boosts.get(tool_id, 0.0)) for tool_id, score in scored]


def _filter_public_safety_location_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    boosts = {}
    if intent.has_public_data_ref("mois_emergency_call_box"):
        boosts["mois_emergency_call_box_lookup"] = 1000.0
    if intent.has_public_data_ref("gyeryong_assistive_charger"):
        boosts["gyeryong_assistive_device_charging_place_locate"] = 1000.0
    if not boosts:
        return scored
    return [(tool_id, score + boosts.get(tool_id, 0.0)) for tool_id, score in scored]


def _filter_emergency_chain_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if not intent.has_public_data_ref("emergency_medical"):
        return scored
    emergency_tool_ids = {
        "nmc_emergency_search",
        "nmc_aed_site_locate",
        "hira_hospital_search",
        "hira_medical_institution_detail",
    }
    allowed_tool_ids = emergency_tool_ids | _LOCATION_TOOL_IDS
    if any(tool_id in emergency_tool_ids for tool_id, _ in scored):
        scored = [(tool_id, score) for tool_id, score in scored if tool_id in allowed_tool_ids]
    implicit_collapse = intent.has_public_data_ref("implicit_emergency")
    boosts = {
        "nmc_emergency_search": 1200.0,
        "nmc_aed_site_locate": 1150.0 if implicit_collapse else 950.0,
        "kakao_keyword_search": 1100.0 if implicit_collapse else 900.0,
        "kakao_address_search": 800.0,
        "kakao_coord_to_region": 500.0,
        "juso_adm_cd_lookup": 300.0,
        "sgis_adm_cd_lookup": 300.0,
        "hira_hospital_search": 250.0,
        "hira_medical_institution_detail": 200.0,
    }
    return [(tool_id, score + boosts.get(tool_id, 0.0)) for tool_id, score in scored]


def _filter_ocean_water_quality_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if not intent.has_public_data_ref("mof_ocean_water_quality"):
        return scored
    return [
        (
            tool_id,
            score + (1000.0 if tool_id == "mof_ocean_water_quality_check" else 0.0),
        )
        for tool_id, score in scored
    ]


def _filter_pps_bid_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if not intent.has_public_data_ref("pps_bid"):
        return scored
    has_pps_bid = any(tool_id == "pps_bid_public_info" for tool_id, _ in scored)
    if not has_pps_bid:
        return scored
    return [
        (tool_id, score + 1000.0) for tool_id, score in scored if tool_id == "pps_bid_public_info"
    ]


def _filter_airkorea_air_quality_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if not intent.has_public_data_ref("airkorea_air_quality"):
        return scored
    has_airkorea = any(tool_id in _AIRKOREA_TOOL_IDS for tool_id, _ in scored)
    if not has_airkorea:
        return scored
    return [(tool_id, score + 1200.0) for tool_id, score in scored if tool_id in _AIRKOREA_TOOL_IDS]


def _filter_djtc_subway_segment_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if not intent.has_public_data_ref("djtc_subway_segment"):
        return scored
    has_djtc = any(tool_id in _DJTC_SUBWAY_SEGMENT_TOOL_IDS for tool_id, _ in scored)
    if not has_djtc:
        return scored
    return [
        (tool_id, score + 1400.0)
        for tool_id, score in scored
        if tool_id in _DJTC_SUBWAY_SEGMENT_TOOL_IDS
    ]


def _filter_kcue_regional_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if not intent.has_public_data_ref("kcue_regional"):
        return scored
    has_kcue = any(tool_id in _KCUE_TOOL_IDS for tool_id, _ in scored)
    if not has_kcue:
        return scored

    prefer_finance = intent.has_public_data_ref("kcue_regional_finance")
    prefer_foreign_student = intent.has_public_data_ref("kcue_regional_foreign_student")
    boosts = {
        "kcue_finance_regional_tuition": 1000.0 if prefer_finance else 700.0,
        "kcue_student_regional_foreign": 1000.0 if prefer_foreign_student else 700.0,
    }
    return [
        (tool_id, score + boosts[tool_id]) for tool_id, score in scored if tool_id in _KCUE_TOOL_IDS
    ]


def _filter_health_detail_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if not intent.has_public_data_ref("hira_medical_detail"):
        return scored
    return [
        (
            tool_id,
            score + (650.0 if tool_id == "hira_medical_institution_detail" else 0.0),
        )
        for tool_id, score in scored
    ]


def _filter_document_harness_scores(
    intent: ToolSelectionIntent,
    scored: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    if not intent.has_document_ref("document_harness"):
        return scored
    if not any(tool_id in _DOCUMENT_TOOL_IDS for tool_id, _score in scored):
        return scored
    boosts = {"document": 1600.0}
    return [
        (tool_id, score + boosts[tool_id])
        for tool_id, score in scored
        if tool_id in _DOCUMENT_TOOL_IDS
    ]


def _filter_initial_special_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if intent.has_public_data_ref("traffic_hazard_specific"):
        scored = [
            (tool_id, score) for tool_id, score in scored if tool_id != "koroad_accident_search"
        ]
    if intent.has_public_data_ref("kma_analysis_chart"):
        return [
            (tool_id, score)
            for tool_id, score in scored
            if tool_id == "kma_apihub_url_analysis_weather_chart_image"
        ]
    return scored


def _filter_kma_aviation_scores(
    intent: ToolSelectionIntent,
    scored: list[tuple[str, float]],
    *,
    is_airport_aviation_query: bool,
) -> list[tuple[str, float]]:
    if intent.has_public_data_ref("kma_gimhae_airport") and is_airport_aviation_query:
        scored = [
            (tool_id, score)
            for tool_id, score in scored
            if tool_id != "kma_apihub_url_air_amos_minute"
        ]
    if (
        intent.has_public_data_ref("kma_gimpo_airport")
        and intent.has_public_data_ref("kma_runway_area")
        and is_airport_aviation_query
    ):
        scored = [
            (tool_id, score + 500.0 if tool_id == "kma_apihub_url_air_amos_minute" else score)
            for tool_id, score in scored
        ]
    if not is_airport_aviation_query:
        return scored

    has_air_url_candidate = any(tool_id in _KMA_URL_AIR_TOOL_IDS for tool_id, _ in scored)
    if not has_air_url_candidate:
        return scored
    if intent.has_public_data_ref("kma_explicit_metar"):
        blocked_tool_ids = (
            _LOCATION_TOOL_IDS | _KMA_LIFESTYLE_WEATHER_TOOL_IDS | {"kma_forecast_fetch"}
        )
        scored = [(tool_id, score) for tool_id, score in scored if tool_id not in blocked_tool_ids]
    else:
        scored = [(tool_id, score) for tool_id, score in scored if tool_id in _KMA_URL_AIR_TOOL_IDS]
    prefer_amos = bool(
        intent.has_public_data_ref("kma_gimpo_airport")
        and intent.has_public_data_ref("kma_runway_area")
        and not intent.has_public_data_ref("kma_gimhae_airport")
    )
    return [
        (
            tool_id,
            score
            + (
                800.0
                if tool_id == "kma_apihub_url_air_amos_minute" and prefer_amos
                else 700.0
                if tool_id == "kma_apihub_url_air_metar_decoded"
                else 0.0
            ),
        )
        for tool_id, score in scored
    ]


def _boost_aed_scores(
    intent: ToolSelectionIntent, scored: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    if not intent.has_public_data_ref("aed"):
        return scored
    return [
        (
            tool_id,
            score + 900.0
            if tool_id == "nmc_aed_site_locate"
            else score + 700.0
            if tool_id == "nmc_emergency_search" and intent.has_public_data_ref("emergency_medical")
            else score,
        )
        for tool_id, score in scored
    ]
