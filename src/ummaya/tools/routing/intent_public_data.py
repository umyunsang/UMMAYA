# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from ummaya.tools.routing.intent_patterns import (
    _AED_RE,
    _EMERGENCY_RE,
    _GYERYONG_ASSISTIVE_CHARGER_RE,
    _HIRA_MEDICAL_DETAIL_RE,
    _IMPLICIT_EMERGENCY_RE,
    _KCUE_REGIONAL_FINANCE_RE,
    _KCUE_REGIONAL_FOREIGN_STUDENT_RE,
    _KCUE_REGIONAL_RE,
    _KMA_AIRPORT_AVIATION_RE,
    _KMA_ANALYSIS_CHART_RE,
    _KMA_ANALYSIS_DATA_RE,
    _KMA_ANALYSIS_MAP_RE,
    _KMA_ANALYSIS_POINT_RE,
    _KMA_EXPLICIT_METAR_RE,
    _KMA_GIMHAE_AIRPORT_RE,
    _KMA_GIMPO_AIRPORT_RE,
    _KMA_LIFESTYLE_WEATHER_RE,
    _KMA_RUNWAY_AREA_RE,
    _MOF_OCEAN_WATER_QUALITY_RE,
    _MOIS_EMERGENCY_CALL_BOX_RE,
    _PPS_BID_RE,
    _PPS_SHOPPING_RE,
    _PUBLIC_DATA_OPERATION_RE,
    _TRAFFIC_HAZARD_RE,
    _TRAFFIC_HAZARD_SPECIFIC_RE,
)


def extract_public_data_refs(query: str) -> tuple[str, ...]:
    refs = [f"operation:{match.group(1)}" for match in _PUBLIC_DATA_OPERATION_RE.finditer(query)]
    refs.extend(_extract_kma_public_data_refs(query))
    refs.extend(_extract_emergency_public_data_refs(query))
    refs.extend(_extract_domain_public_data_refs(query))
    return _ordered_unique(refs)


def _extract_kma_public_data_refs(query: str) -> list[str]:
    has_airport_aviation = bool(_KMA_AIRPORT_AVIATION_RE.search(query))
    has_emergency = bool(_EMERGENCY_RE.search(query) or _IMPLICIT_EMERGENCY_RE.search(query))
    refs: list[str] = []
    refs.extend(_extract_kma_aviation_refs(query, has_airport_aviation=has_airport_aviation))
    refs.extend(_extract_kma_analysis_refs(query))
    if _is_lifestyle_weather_ref(query, has_airport_aviation, has_emergency):
        refs.append("kma_lifestyle_weather")
    return refs


def _extract_kma_aviation_refs(query: str, *, has_airport_aviation: bool) -> list[str]:
    refs: list[str] = []
    if has_airport_aviation:
        refs.append("kma_airport_aviation")
    if _KMA_GIMHAE_AIRPORT_RE.search(query):
        refs.append("kma_gimhae_airport")
    if _KMA_GIMPO_AIRPORT_RE.search(query):
        refs.append("kma_gimpo_airport")
    if _KMA_EXPLICIT_METAR_RE.search(query):
        refs.append("kma_explicit_metar")
    if _KMA_RUNWAY_AREA_RE.search(query):
        refs.append("kma_runway_area")
    return refs


def _extract_kma_analysis_refs(query: str) -> list[str]:
    refs: list[str] = []
    if _KMA_ANALYSIS_CHART_RE.search(query):
        refs.append("kma_analysis_chart")
    if _KMA_ANALYSIS_DATA_RE.search(query):
        refs.append("kma_analysis_data")
    if _KMA_ANALYSIS_MAP_RE.search(query):
        refs.append("kma_analysis_map")
    if _KMA_ANALYSIS_POINT_RE.search(query):
        refs.append("kma_analysis_point")
    return refs


def _is_lifestyle_weather_ref(query: str, has_airport_aviation: bool, has_emergency: bool) -> bool:
    return bool(
        _KMA_LIFESTYLE_WEATHER_RE.search(query)
        and not has_airport_aviation
        and not has_emergency
        and not _KMA_ANALYSIS_DATA_RE.search(query)
        and not _TRAFFIC_HAZARD_RE.search(query)
        and not _MOF_OCEAN_WATER_QUALITY_RE.search(query)
    )


def _extract_emergency_public_data_refs(query: str) -> list[str]:
    refs: list[str] = []
    has_call_box = bool(_MOIS_EMERGENCY_CALL_BOX_RE.search(query))
    has_emergency = bool(_EMERGENCY_RE.search(query) or _IMPLICIT_EMERGENCY_RE.search(query))
    if has_emergency and not has_call_box:
        refs.append("emergency_medical")
    if _IMPLICIT_EMERGENCY_RE.search(query) and not has_call_box:
        refs.append("implicit_emergency")
    if _AED_RE.search(query):
        refs.append("aed")
    if has_call_box:
        refs.append("mois_emergency_call_box")
    return refs


def _extract_domain_public_data_refs(query: str) -> list[str]:
    refs: list[str] = []
    if _TRAFFIC_HAZARD_RE.search(query):
        refs.append("traffic_hazard")
    if _TRAFFIC_HAZARD_SPECIFIC_RE.search(query):
        refs.append("traffic_hazard_specific")
    if _MOF_OCEAN_WATER_QUALITY_RE.search(query):
        refs.append("mof_ocean_water_quality")
    if _PPS_BID_RE.search(query) and not _PPS_SHOPPING_RE.search(query):
        refs.append("pps_bid")
    has_kcue_finance = bool(_KCUE_REGIONAL_FINANCE_RE.search(query))
    has_kcue_foreign_student = bool(_KCUE_REGIONAL_FOREIGN_STUDENT_RE.search(query))
    if _KCUE_REGIONAL_RE.search(query) or has_kcue_finance or has_kcue_foreign_student:
        refs.append("kcue_regional")
    if has_kcue_finance:
        refs.append("kcue_regional_finance")
    if has_kcue_foreign_student:
        refs.append("kcue_regional_foreign_student")
    if _HIRA_MEDICAL_DETAIL_RE.search(query):
        refs.append("hira_medical_detail")
    if _GYERYONG_ASSISTIVE_CHARGER_RE.search(query):
        refs.append("gyeryong_assistive_charger")
    return refs


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)
