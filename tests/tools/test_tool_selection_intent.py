# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import inspect

from ummaya.tools import search as search_module
from ummaya.tools.routing.intent import (
    ACTIVE_PRIMITIVES,
    LEGACY_PRIMITIVE_ALIASES,
    ToolSelectionIntent,
    extract_tool_selection_intent,
)
from ummaya.tools.search import _expand_query_for_adapter_retrieval


def test_extracts_explicit_tool_id_and_public_data_operation_without_scores() -> None:
    intent = extract_tool_selection_intent(
        "tool_id=kma_apihub_url_air_metar_decoded 로 METAR getSurfaceChart 해독",
        known_tool_ids={"kma_apihub_url_air_metar_decoded"},
    )

    assert intent.explicit_tool_ids == ("kma_apihub_url_air_metar_decoded",)
    assert "operation:getSurfaceChart" in intent.public_data_refs
    assert "kma_airport_aviation" in intent.public_data_refs
    assert intent.candidate_primitives == ("find",)
    assert not any(
        "score" in field or "rank" in field for field in ToolSelectionIntent.model_fields
    )


def test_extracts_document_path_artifact_and_side_effect_marker() -> None:
    intent = extract_tool_selection_intent(
        "~/Downloads/신청서.hwpx 파일을 artifact-abc123 기준으로 채워서 저장해줘"
    )

    assert "~/Downloads/신청서.hwpx" in intent.document_refs
    assert "format:hwpx" in intent.document_refs
    assert "document_harness" in intent.document_refs
    assert intent.explicit_artifact_ids == ("artifact-abc123",)
    assert "document_write" in intent.side_effect_markers
    assert "send" in intent.candidate_primitives
    assert intent.requires_permission is True


def test_extracts_coordinate_location_and_missing_slots_boundary() -> None:
    coordinate_intent = extract_tool_selection_intent("37.5665, 126.9780 근처 AED 위치 알려줘")
    poi_intent = extract_tool_selection_intent("하단역 근처 응급실 어디야?")

    assert "coordinate:37.5665,126.978" in coordinate_intent.location_refs
    assert "poi" in coordinate_intent.location_refs
    assert coordinate_intent.missing_slots == ()
    assert "aed" in coordinate_intent.public_data_refs
    assert "locate" in coordinate_intent.candidate_primitives
    assert "poi_requires_location_resolution" in poi_intent.unsafe_assumptions
    assert poi_intent.missing_slots == ("lat", "lon")


def test_active_primitives_exclude_legacy_aliases_from_candidate_surface() -> None:
    intent = extract_tool_selection_intent("lookup으로 resolve_location 말고 부산시 날씨 찾아줘")

    assert ACTIVE_PRIMITIVES == ("find", "locate", "send", "check")
    assert LEGACY_PRIMITIVE_ALIASES["lookup"] == "find"
    assert LEGACY_PRIMITIVE_ALIASES["resolve_location"] == "locate"
    assert set(intent.candidate_primitives) <= set(ACTIVE_PRIMITIVES)
    assert "lookup" not in intent.candidate_primitives
    assert "resolve_location" not in intent.candidate_primitives


def test_search_expansion_uses_intent_for_explicit_metar_signal() -> None:
    expanded = _expand_query_for_adapter_retrieval("METAR 해독자료 보여줘")

    assert "항공기상" in expanded
    assert "METAR" in expanded


def test_search_active_path_extracts_tool_selection_intent_once(
    monkeypatch, populated_registry
) -> None:
    calls = 0
    real_extract = search_module.extract_tool_selection_intent

    def counting_extract(query: str, *, known_tool_ids=()):
        nonlocal calls
        calls += 1
        return real_extract(query, known_tool_ids=known_tool_ids)

    monkeypatch.setattr(search_module, "extract_tool_selection_intent", counting_extract)

    search_module.search(
        "날씨 METAR 해독자료 보여줘",
        populated_registry.bm25_index,
        populated_registry,
    )

    assert calls == 1


def test_search_module_no_longer_owns_domain_regex_tables() -> None:
    source = inspect.getsource(search_module)

    assert "re.compile(" not in source
    assert "_RE.search(" not in source


def test_emergency_call_box_is_protected_from_medical_emergency_chain() -> None:
    intent = extract_tool_selection_intent("부산역 근처 emergency call box 위치 알려줘")

    assert "mois_emergency_call_box" in intent.public_data_refs
    assert "emergency_medical" not in intent.public_data_refs
    assert "implicit_emergency" not in intent.public_data_refs
    assert "poi" in intent.location_refs


def test_kcue_finance_subsignal_implies_regional_parent_ref() -> None:
    intent = extract_tool_selection_intent(
        "대학 등록금이 지역별로 얼마나 차이 나는지 공식 자료로 보고 싶어"
    )

    assert "kcue_regional" in intent.public_data_refs
    assert "kcue_regional_finance" in intent.public_data_refs


def test_airkorea_air_quality_signal_is_not_weather_ref() -> None:
    intent = extract_tool_selection_intent("부산 공기질과 미세먼지 지금 어때? air quality 확인해줘")

    assert "airkorea_air_quality" in intent.public_data_refs
    assert "kma_lifestyle_weather" not in intent.public_data_refs
