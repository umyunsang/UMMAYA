# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime

from ummaya.tools.models import AdapterRealDomainPolicy
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.routing import RouteDecisionService
from ummaya.tools.routing.projection import build_available_adapters_projection


def _policy() -> AdapterRealDomainPolicy:
    return AdapterRealDomainPolicy(
        real_classification_url="https://example.go.kr/policy",
        real_classification_text="Published agency policy",
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 6, 5, tzinfo=UTC),
    )


def _projected_tool_id_lines(content: str) -> tuple[str, ...]:
    return tuple(
        line.strip().removeprefix("- tool_id:").strip()
        for line in content.splitlines()
        if line.strip().startswith("- tool_id:")
    )


def test_available_adapter_projection_summary_uses_route_decision_backend(
    sample_tool_factory,
) -> None:
    registry = ToolRegistry()
    registry.register(
        sample_tool_factory(
            id="kma_weather_forecast",
            primitive="find",
            policy=_policy(),
            llm_description="Official weather forecast lookup.",
            search_hint="weather forecast",
        )
    )
    decision = RouteDecisionService(registry).select_adapters(
        "weather forecast",
        initial_scores=(("kma_weather_forecast", 10.0),),
    )

    projection = build_available_adapters_projection(
        decision,
        registry,
        query="weather forecast",
        projection_level="summary",
    )

    assert projection.tool_ids == ("kma_weather_forecast",)
    assert projection.content is not None
    assert 'backend="injected"' in projection.content
    assert 'schema_projection="summary"' in projection.content
    assert "input_schema_summary" in projection.content
    assert "city" in projection.content
    assert "input_schema_json" not in projection.content
    assert '"properties"' not in projection.content
    assert "백엔드 BM25 후보" not in projection.content


def test_available_adapter_projection_full_schema_is_explicit(
    sample_tool_factory,
) -> None:
    registry = ToolRegistry()
    registry.register(
        sample_tool_factory(
            id="kma_weather_forecast",
            primitive="find",
            policy=_policy(),
            search_hint="weather forecast",
        )
    )
    decision = RouteDecisionService(registry).select_adapters(
        "weather forecast",
        initial_scores=(("kma_weather_forecast", 10.0),),
    )

    projection = build_available_adapters_projection(
        decision,
        registry,
        query="weather forecast",
        projection_level="full_schema",
    )

    assert projection.content is not None
    assert 'schema_projection="full_schema"' in projection.content
    assert "input_schema_json:" in projection.content
    assert '"properties"' in projection.content


def test_available_adapter_projection_none_hides_candidates(sample_tool_factory) -> None:
    registry = ToolRegistry()
    registry.register(
        sample_tool_factory(
            id="kma_weather_forecast",
            primitive="find",
            policy=_policy(),
            search_hint="weather forecast",
        )
    )
    decision = RouteDecisionService(registry).select_adapters(
        "weather forecast",
        initial_scores=(("kma_weather_forecast", 10.0),),
    )

    projection = build_available_adapters_projection(
        decision,
        registry,
        query="weather forecast",
        projection_level="none",
    )

    assert projection.tool_ids == ()
    assert projection.content is None


def test_available_adapter_projection_renders_only_visible_tool_ids(
    sample_tool_factory,
) -> None:
    registry = ToolRegistry()
    registry.register(
        sample_tool_factory(
            id="find",
            primitive="find",
            policy=_policy(),
            search_hint="generic root primitive search",
        )
    )
    registry.register(
        sample_tool_factory(
            id="bfc_funeral_area_fee",
            primitive="find",
            policy=_policy(),
            search_hint="부산 장례식장 시설 사용료 public data",
        )
    )
    decision = RouteDecisionService(registry).select_adapters(
        "부산광역시 장례식장 시설 사용료 목록을 조회해줘",
        initial_scores=(("find", 10.0), ("bfc_funeral_area_fee", 9.0)),
        max_selected=2,
    )

    projection = build_available_adapters_projection(
        decision,
        registry,
        query="부산광역시 장례식장 시설 사용료 목록을 조회해줘",
        projection_level="summary",
        visible_tool_ids=("bfc_funeral_area_fee",),
    )

    assert projection.tool_ids == ("bfc_funeral_area_fee",)
    assert projection.content is not None
    assert _projected_tool_id_lines(projection.content) == ("bfc_funeral_area_fee",)
    assert "tool_id: bfc_funeral_area_fee" in projection.content
    assert "tool_id: find" not in projection.content
    assert not (
        set(_projected_tool_id_lines(projection.content))
        & {"find", "locate", "check", "send", "search_tools"}
    )
