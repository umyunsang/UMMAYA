# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.routing import RouteDecision, RouteDecisionService
from ummaya.tools.routing import decision_service as decision_service_module


class CoordinateInput(BaseModel):
    lat: float
    lon: float


class EmptyOutput(BaseModel):
    ok: bool


def _policy(gate: str = "read-only") -> AdapterRealDomainPolicy:
    return AdapterRealDomainPolicy(
        real_classification_url="https://example.go.kr/policy",
        real_classification_text="Published agency policy",
        citizen_facing_gate=gate,
        last_verified=datetime(2026, 6, 5, tzinfo=UTC),
    )


def test_route_decision_uses_registry_retrieval_and_selects_feasible_candidate(
    sample_tool_factory,
) -> None:
    registry = ToolRegistry()
    tool = sample_tool_factory(
        id="kma_weather_forecast",
        primitive="find",
        policy=_policy(),
        search_hint="서울 날씨 forecast weather",
    )
    registry.register(tool)

    decision = RouteDecisionService(registry).decide("서울 날씨 알려줘")

    assert decision.selected_tools == ("kma_weather_forecast",)
    assert decision.schema_projection_level == "summary"
    assert decision.stop_reason is None
    assert decision.candidate_set[0].feasible is True
    assert decision.candidate_set[0].filter_reasons == ()
    assert decision.backend_label == "bm25"
    assert decision.effective_top_k == 1


def test_route_decision_models_reject_unknown_fields(sample_tool_factory) -> None:
    registry = ToolRegistry()
    registry.register(sample_tool_factory(id="kma_weather_forecast", policy=_policy()))
    decision = RouteDecisionService(registry).select_adapters("서울 날씨 알려줘")

    payload = decision.model_dump()
    payload["unexpected"] = True

    try:
        RouteDecision.model_validate(payload)
    except ValidationError as exc:
        assert "unexpected" in str(exc)
    else:
        raise AssertionError("RouteDecision accepted an unknown field")


def test_route_decision_filters_missing_coordinate_slots() -> None:
    registry = ToolRegistry()
    tool = GovAPITool(
        id="nmc_aed_site_locate",
        name_ko="AED 위치",
        ministry="NMC",
        category=["응급", "AED"],
        endpoint="internal://nmc-aed",
        auth_type="public",
        primitive="find",
        policy=_policy(),
        input_schema=CoordinateInput,
        output_schema=EmptyOutput,
        search_hint="AED 자동심장충격기 위치",
    )
    registry.register(tool)

    decision = RouteDecisionService(registry).decide(
        "하단역 근처 AED 위치 알려줘",
        initial_scores=(("nmc_aed_site_locate", 10.0),),
    )

    assert decision.selected_tools == ()
    assert decision.schema_projection_level == "none"
    assert decision.stop_reason == "no_feasible_candidate"
    assert decision.clarification_question == "Required slot missing: lat, lon."
    assert set(decision.candidate_set[0].filter_reasons) == {
        "missing_slot:lat",
        "missing_slot:lon",
    }


def test_route_decision_filters_inactive_and_missing_prerequisite(sample_tool_factory) -> None:
    registry = ToolRegistry()
    submit = sample_tool_factory(
        id="gov24_minwon_submit",
        ministry="GOV24",
        auth_type="oauth",
        primitive="send",
        policy=_policy("send"),
        llm_description="Requires prior check before submission.",
        search_hint="민원 신청 제출 submit",
    )
    registry.register(submit)
    service = RouteDecisionService(registry)

    missing_prereq = service.decide(
        "민원 신청 제출해줘",
        initial_scores=(("gov24_minwon_submit", 9.0),),
    )

    assert missing_prereq.selected_tools == ()
    assert "missing_prerequisite_primitive:check" in missing_prereq.candidate_set[0].filter_reasons

    check = sample_tool_factory(
        id="simple_auth_check",
        ministry="UMMAYA",
        auth_type="oauth",
        primitive="check",
        policy=_policy("login"),
        search_hint="본인인증 check verify",
    )
    registry.register(check)
    feasible = service.decide(
        "민원 신청 제출해줘",
        initial_scores=(("gov24_minwon_submit", 9.0),),
    )

    assert feasible.selected_tools == ("gov24_minwon_submit",)
    assert feasible.permission_gate is True

    registry.set_active("gov24_minwon_submit", False)
    inactive = service.decide(
        "민원 신청 제출해줘",
        initial_scores=(("gov24_minwon_submit", 9.0),),
    )

    assert inactive.selected_tools == ()
    assert inactive.candidate_set == ()
    assert "hard_excluded:inactive_adapter:gov24_minwon_submit" in inactive.evidence_events


def test_route_decision_preserves_mock_source_mode(sample_tool_factory) -> None:
    registry = ToolRegistry()
    tool = sample_tool_factory(
        id="mock_public_fixture_find",
        primitive="find",
        adapter_mode="mock",
        mock_fidelity_grade="OOS",
        policy=_policy(),
        search_hint="fixture mock public data",
    )
    registry.register(tool)

    decision = RouteDecisionService(registry).decide(
        "fixture public data",
        initial_scores=(("mock_public_fixture_find", 5.0),),
    )

    assert decision.selected_tools == ("mock_public_fixture_find",)
    assert decision.candidate_set[0].card.source_mode == "mock"
    assert decision.candidate_set[0].card.mock_fidelity_grade == "OOS"


def test_route_decision_hard_excludes_disallowed_source_modes(sample_tool_factory) -> None:
    registry = ToolRegistry()
    tool = sample_tool_factory(
        id="mock_public_fixture_find",
        primitive="find",
        adapter_mode="mock",
        policy=_policy(),
        search_hint="fixture mock public data",
    )
    registry.register(tool)

    decision = RouteDecisionService(registry).select_adapters(
        "fixture public data",
        initial_scores=(("mock_public_fixture_find", 5.0),),
        allowed_source_modes=("live",),
        include_infeasible=True,
    )

    assert decision.selected_tools == ()
    assert decision.candidate_set == ()
    assert "hard_excluded:disallowed_source_mode:mock:mock_public_fixture_find" in (
        decision.evidence_events
    )


def test_route_decision_hard_excludes_disallowed_credentials(sample_tool_factory) -> None:
    registry = ToolRegistry()
    tool = sample_tool_factory(
        id="kma_weather_forecast",
        primitive="find",
        auth_type="api_key",
        policy=_policy(),
        search_hint="weather forecast",
    )
    registry.register(tool)

    decision = RouteDecisionService(registry).select_adapters(
        "weather forecast",
        initial_scores=(("kma_weather_forecast", 7.0),),
        allowed_credentials=("public",),
        include_infeasible=True,
    )

    assert decision.selected_tools == ()
    assert decision.candidate_set == ()
    assert "hard_excluded:disallowed_credential:api_key:kma_weather_forecast" in (
        decision.evidence_events
    )


def test_route_decision_keeps_login_gate_candidates_visible(sample_tool_factory) -> None:
    registry = ToolRegistry()
    tool = sample_tool_factory(
        id="nmc_emergency_search",
        primitive="find",
        auth_type="oauth",
        policy=_policy("login"),
        search_hint="응급실 응급의료 hospital emergency",
    )
    registry.register(tool)

    decision = RouteDecisionService(registry).select_adapters(
        "하단역 근처 야간 응급실 어디야",
        initial_scores=(("nmc_emergency_search", 12.0),),
    )

    assert decision.selected_tools == ("nmc_emergency_search",)
    assert decision.permission_gate is True


def test_route_decision_permission_gate_uses_selected_slice(sample_tool_factory) -> None:
    registry = ToolRegistry()
    read_only = sample_tool_factory(
        id="kma_weather_forecast",
        primitive="find",
        policy=_policy(),
        search_hint="weather forecast",
    )
    login = sample_tool_factory(
        id="nmc_emergency_search",
        primitive="find",
        auth_type="oauth",
        policy=_policy("login"),
        search_hint="emergency hospital",
    )
    registry.register(read_only)
    registry.register(login)

    decision = RouteDecisionService(registry).select_adapters(
        "weather forecast",
        initial_scores=(("kma_weather_forecast", 10.0), ("nmc_emergency_search", 1.0)),
        top_k=2,
        max_selected=1,
    )

    assert decision.selected_tools == ("kma_weather_forecast",)
    assert decision.permission_gate is False


def test_route_decision_include_infeasible_retains_soft_rejection_reasons() -> None:
    registry = ToolRegistry()
    tool = GovAPITool(
        id="nmc_aed_site_locate",
        name_ko="AED 위치",
        ministry="NMC",
        category=["응급", "AED"],
        endpoint="internal://nmc-aed",
        auth_type="public",
        primitive="find",
        policy=_policy(),
        input_schema=CoordinateInput,
        output_schema=EmptyOutput,
        search_hint="AED 자동심장충격기 위치",
    )
    registry.register(tool)

    hidden = RouteDecisionService(registry).select_adapters(
        "하단역 근처 AED 위치 알려줘",
        initial_scores=(("nmc_aed_site_locate", 10.0),),
    )
    visible = RouteDecisionService(registry).select_adapters(
        "하단역 근처 AED 위치 알려줘",
        initial_scores=(("nmc_aed_site_locate", 10.0),),
        include_infeasible=True,
    )

    assert hidden.candidate_set == ()
    assert visible.candidate_set[0].filter_reasons == ("missing_slot:lat", "missing_slot:lon")


def test_route_decision_extracts_intent_once_when_not_supplied(
    monkeypatch, sample_tool_factory
) -> None:
    registry = ToolRegistry()
    registry.register(sample_tool_factory(id="kma_weather_forecast", policy=_policy()))
    calls = 0
    real_extract = decision_service_module.extract_tool_selection_intent

    def counting_extract(query: str, *, known_tool_ids=()):
        nonlocal calls
        calls += 1
        return real_extract(query, known_tool_ids=known_tool_ids)

    monkeypatch.setattr(decision_service_module, "extract_tool_selection_intent", counting_extract)

    RouteDecisionService(registry).select_adapters("서울 날씨 알려줘")

    assert calls == 1


def test_route_decision_falls_back_to_bm25_companion_when_retriever_raises(
    sample_tool_factory,
) -> None:
    class CompanionRetriever:
        def rebuild(self, corpus: dict[str, str]) -> None:
            self.corpus = corpus

        def score(self, query: str) -> list[tuple[str, float]]:
            return [("kma_current_observation", 11.0)]

    class BrokenHybridRetriever:
        _requested_backend_label = "hybrid"

        def __init__(self) -> None:
            self._bm25 = CompanionRetriever()

        def rebuild(self, corpus: dict[str, str]) -> None:
            self._bm25.rebuild(corpus)

        def score(self, query: str) -> list[tuple[str, float]]:
            raise RuntimeError("dense path failed")

    registry = ToolRegistry()
    registry._retriever = BrokenHybridRetriever()
    registry.register(
        sample_tool_factory(id="kma_current_observation", primitive="find", policy=_policy())
    )

    decision = RouteDecisionService(registry).select_adapters("서울 날씨 알려줘")

    assert decision.selected_tools == ("kma_current_observation",)
    assert decision.backend_label == "bm25"
    assert decision.degradation_reason == "hybrid_score_failed"
