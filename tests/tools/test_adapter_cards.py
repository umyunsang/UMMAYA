# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import AdapterRealDomainPolicy
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.routing.cards import (
    AdapterCard,
    SchemaFieldSummary,
    assert_adapter_card_quality,
    build_adapter_card,
    lint_adapter_card,
)


def _read_only_policy() -> AdapterRealDomainPolicy:
    return AdapterRealDomainPolicy(
        real_classification_url="https://www.kma.go.kr/kma/notice/personal.jsp",
        real_classification_text="KMA published read-only public weather policy",
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 6, 5, tzinfo=UTC),
    )


def test_build_adapter_card_compacts_schema_and_hashes(sample_tool_factory):
    tool = sample_tool_factory(
        id="kma_weather_forecast",
        policy=_read_only_policy(),
        primitive="find",
        llm_description="Find KMA weather forecasts by city and optional date.",
        trigger_examples=["서울 내일 날씨 알려줘"],
    )

    card = build_adapter_card(tool)

    assert card.tool_id == "kma_weather_forecast"
    assert card.primitive_family == "find"
    assert card.legacy_primitive_aliases == ("lookup",)
    assert card.source_mode == "live"
    assert card.policy_authority_url == "https://www.kma.go.kr/kma/notice/personal.jsp"
    assert card.required_slots == ("city",)
    assert len(card.input_schema_hash) == 64
    assert len(card.manifest_hash) == 64
    assert {field.name for field in card.input_schema_summary} == {"city", "date"}
    assert "properties" not in card.routing_text
    assert "$defs" not in card.routing_text
    assert "{" not in card.routing_text
    assert lint_adapter_card(card) == ()


def test_registry_exports_one_card_per_active_tool(sample_tool_factory):
    registry = ToolRegistry()
    active = sample_tool_factory(
        id="kma_weather_forecast",
        policy=_read_only_policy(),
        primitive="find",
        trigger_examples=["부산 기상 예보 확인"],
    )
    inactive = sample_tool_factory(
        id="koroad_accident_stats",
        ministry="KOROAD",
        policy=_read_only_policy(),
        primitive="find",
        trigger_examples=["교통사고 통계 찾아줘"],
    )
    registry.register(active)
    registry.register(inactive)
    registry.set_active("koroad_accident_stats", False)

    cards = registry.adapter_cards()

    assert [card.tool_id for card in cards] == ["kma_weather_forecast"]
    assert_adapter_card_quality(cards[0])


def test_adapter_card_hashes_are_stable(sample_tool_factory):
    tool = sample_tool_factory(
        id="kma_weather_forecast",
        policy=_read_only_policy(),
        primitive="find",
        trigger_examples=["강릉 날씨 확인"],
    )

    first = build_adapter_card(tool)
    second = build_adapter_card(tool)

    assert first.input_schema_hash == second.input_schema_hash
    assert first.manifest_hash == second.manifest_hash
    assert first.routing_text == second.routing_text


def test_build_adapter_card_rejects_missing_primitive(sample_tool_factory):
    tool = sample_tool_factory(policy=_read_only_policy(), primitive=None)

    with pytest.raises(ValueError, match="primitive"):
        build_adapter_card(tool)


def test_register_all_mock_bridge_cards_use_mock_source_mode():
    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    register_all_tools(registry, executor)

    mock_bridge_cards = [
        card
        for card in registry.adapter_cards()
        if card.tool_id.startswith(("mock_verify", "mock_submit"))
    ]

    assert mock_bridge_cards
    assert {card.source_mode for card in mock_bridge_cards} == {"mock"}
    by_tool_id = {card.tool_id: card for card in mock_bridge_cards}
    assert by_tool_id["mock_submit_module_gov24_minwon"].mock_fidelity_grade == "OOS"


def test_lint_flags_missing_policy_and_card_quality_metadata():
    card = AdapterCard(
        tool_id="kma_weather_forecast",
        primitive_family="find",
        legacy_primitive_aliases=("lookup",),
        domain="weather",
        agency="KMA",
        source_mode="live",
        capabilities=("weather",),
        intent_verbs=("find",),
        entity_types=("city",),
        required_slots=(),
        optional_slots=(),
        prerequisite_tools=(),
        input_schema_hash="0" * 64,
        input_schema_summary=(),
        output_schema_summary=(),
        policy_authority_url=None,
        safety_annotations=(),
        side_effect_level="read_only",
        credential_requirements=(),
        mock_fidelity_grade="not_applicable",
        examples_ko=(),
        examples_en=(),
        negative_examples=(),
        limitations=(),
        manifest_hash="1" * 64,
        routing_text='{"properties": {"city": {"type": "string"}}}',
    )

    violations = {violation.code for violation in lint_adapter_card(card)}

    assert violations == {
        "missing_policy_citation",
        "missing_required_slot_metadata",
        "missing_safety_annotations",
        "missing_credential_requirements",
        "missing_examples",
        "missing_negative_examples",
        "missing_limitations",
        "raw_schema_leakage",
    }


def test_assert_adapter_card_quality_raises_named_violations():
    card = AdapterCard(
        tool_id="kma_weather_forecast",
        primitive_family="find",
        legacy_primitive_aliases=("lookup",),
        domain="weather",
        agency="KMA",
        source_mode="mock",
        capabilities=("weather",),
        intent_verbs=("find",),
        entity_types=("city",),
        required_slots=(),
        optional_slots=("city",),
        prerequisite_tools=(),
        input_schema_hash="2" * 64,
        input_schema_summary=(SchemaFieldSummary(name="city", type="string", required=False),),
        output_schema_summary=(),
        policy_authority_url=None,
        safety_annotations=("read-only",),
        side_effect_level="read_only",
        credential_requirements=("api_key",),
        mock_fidelity_grade="unknown",
        examples_ko=("날씨를 알려줘",),
        examples_en=("Find a weather forecast.",),
        negative_examples=(),
        limitations=("Fixture-backed mock output.",),
        manifest_hash="3" * 64,
        routing_text="kma_weather_forecast primitive find required_slots city",
    )

    with pytest.raises(ValueError, match="missing_policy_citation.*missing_negative_examples"):
        assert_adapter_card_quality(card)
