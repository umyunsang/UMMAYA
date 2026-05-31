# SPDX-License-Identifier: Apache-2.0
"""Integration tests for QueryEngine (T015).

Covers the US1 acceptance scenarios:
1. One tool call -> task_complete
2. Two sequential tool calls -> task_complete
3. No tool call -> end_turn
4. Event ordering guarantee
5. No-raise contract
6. Turn count increment
7. System prompt initialization
8. Budget property
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from ummaya.context.builder import ContextBuilder
from ummaya.context.models import SystemPromptConfig
from ummaya.engine.config import QueryEngineConfig
from ummaya.engine.engine import QueryEngine
from ummaya.engine.events import QueryEvent, StopReason
from ummaya.engine.models import QueryContext, SessionBudget
from ummaya.ipc.stdio import (
    _check_kma_analysis_tool_choice_prerequisite,
    _final_answer_substitutes_after_kma_chart_failure,
)

# LLMClient must be imported (not just under TYPE_CHECKING) so that
# QueryContext.model_rebuild() can resolve the forward reference and accept
# mock objects for the llm_client field.
from ummaya.llm.client import LLMClient  # noqa: F401
from ummaya.llm.models import ChatMessage, StreamEvent
from ummaya.llm.usage import UsageTracker
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.mvp_surface import register_mvp_surface
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry

QueryContext.model_rebuild()


# ---------------------------------------------------------------------------
# Helper: collect all events from the async generator
# ---------------------------------------------------------------------------


async def _collect(engine: QueryEngine, message: str) -> list[QueryEvent]:
    """Run engine.run() and collect all yielded events into a list."""
    return [event async for event in engine.run(message)]


# ---------------------------------------------------------------------------
# LLMClient-compatible mock base
#
# QueryContext validates llm_client as isinstance(LLMClient) because the model
# is rebuilt with the real LLMClient annotation.  We subclass LLMClient but
# skip super().__init__() so no real config or HTTP client is created.
# ---------------------------------------------------------------------------


class _MockLLMClientBase(LLMClient):
    """Base for test LLM client mocks that inherit from LLMClient.

    Skips LLMClient.__init__ to avoid requiring a real API token.
    Subclasses must set self._usage and implement stream().
    """

    def __new__(cls, *args: object, **kwargs: object) -> _MockLLMClientBase:
        # Bypass LLMClient.__init__ by calling object.__new__ directly
        return object.__new__(cls)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Adapter: wrap a conftest MockLLMClient inside an LLMClient subclass
# ---------------------------------------------------------------------------


class _MockClientAdapter(_MockLLMClientBase):
    """Delegate stream() and usage to a conftest MockLLMClient instance."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    @property
    def usage(self) -> UsageTracker:  # type: ignore[override]
        """Forward to delegate's usage tracker."""
        return self._delegate.usage  # type: ignore[attr-defined]

    async def stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> AsyncIterator[object]:
        """Forward to delegate's stream() async generator."""
        async for event in self._delegate.stream(messages, **kwargs):
            yield event


# ---------------------------------------------------------------------------
# Failing mock LLM client for no-raise contract test
# ---------------------------------------------------------------------------


class _FailingMockClient(_MockLLMClientBase):
    """Mock LLM client that raises RuntimeError on every stream() call."""

    def __init__(self) -> None:
        self._usage = UsageTracker(budget=100_000)

    @property
    def usage(self) -> UsageTracker:  # type: ignore[override]
        """Return internal usage tracker."""
        return self._usage

    async def stream(  # type: ignore[override]
        self,
        messages: object,
        **kwargs: object,
    ) -> AsyncIterator[object]:
        """Raise immediately to simulate a catastrophic LLM failure."""
        raise RuntimeError("Simulated LLM failure")
        yield  # pragma: no cover — makes this an async generator


class _CapturingToolsClient(_MockLLMClientBase):
    """Mock LLM client that records provider tool definitions."""

    def __init__(self) -> None:
        self._usage = UsageTracker(budget=100_000)
        self.tools_seen: object | None = None

    @property
    def usage(self) -> UsageTracker:  # type: ignore[override]
        return self._usage

    async def stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> AsyncIterator[object]:
        self.tools_seen = kwargs.get("tools")
        yield StreamEvent(type="content_delta", content="ok")


class _AdapterContextInput(BaseModel):
    page_no: int = 1


class _AdapterContextOutput(BaseModel):
    kind: str
    items: list[dict[str, object]]


def _adapter_context_tool() -> GovAPITool:
    return GovAPITool(
        id="bfc_funeral_area_fee",
        name_ko="부산시설공단 장례식장 시설 사용료",
        ministry="BFC",
        category=["public-data", "funeral"],
        endpoint="https://apis.data.go.kr/example",
        auth_type="api_key",
        input_schema=_AdapterContextInput,
        output_schema=_AdapterContextOutput,
        search_hint="부산 장례식장 시설 사용료 funeral area fee public data",
        policy=AdapterRealDomainPolicy(
            real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
            real_classification_text="test read-only policy",
            citizen_facing_gate="read-only",
            last_verified=datetime(2026, 5, 16, tzinfo=UTC),
        ),
        primitive="find",
        llm_description="부산광역시 장례식장 시설 사용료 공개 데이터를 조회한다.",
    )


def test_available_adapters_context_includes_retrieved_adapter() -> None:
    """Rich REPL QueryEngine must inject BM25 adapter candidates for the turn."""
    registry = ToolRegistry()
    register_mvp_surface(registry)
    registry.register(_adapter_context_tool())
    executor = ToolExecutor(registry)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message = engine._build_available_adapters_message(  # noqa: SLF001
        "부산광역시 장례식장 시설 사용료 목록을 조회해줘"
    )

    assert message is not None
    assert message.role == "system"
    assert "<available_adapters>" in (message.content or "")
    assert "bfc_funeral_area_fee" in (message.content or "")
    assert "The model-facing function name is the concrete tool_id" in (message.content or "")
    assert "Do not call locate just because" in (message.content or "")
    assert "call_hint: bfc_funeral_area_fee({...})" in (message.content or "")
    assert 'find({"tool_id":"bfc_funeral_area_fee"' not in (message.content or "")
    assert "Do not call the concrete tool_id as a function name" not in (message.content or "")


@pytest.mark.asyncio
async def test_available_adapters_context_exposes_concrete_public_data_tool() -> None:
    """Location-independent public data turns should expose the retrieved adapter directly."""
    registry = ToolRegistry()
    register_mvp_surface(registry)
    registry.register(_adapter_context_tool())
    executor = ToolExecutor(registry)
    client = _CapturingToolsClient()
    engine = QueryEngine(
        llm_client=client,
        tool_registry=registry,
        tool_executor=executor,
    )

    events = [
        event async for event in engine.run("부산광역시 장례식장 시설 사용료 목록을 조회해줘")
    ]

    assert events[-1].type == "stop"
    assert isinstance(client.tools_seen, list)
    tool_names: list[str] = []
    for tool in client.tools_seen:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if isinstance(name, str):
            tool_names.append(name)
    assert tool_names == ["bfc_funeral_area_fee"]


def test_available_adapters_context_constrains_from_primary_candidate() -> None:
    """Lower-ranked location adapters must not expose direct KMA tools for public-data turns."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "대학알리미 학교구분코드 02의 지역별 등록금 현황을 5건 공공 API 도구로 조회해줘."
    )

    assert message is not None
    content = message.content or ""
    assert "kcue_finance_regional_tuition" in content
    assert "koroad_accident_search" not in content
    assert turn_tool_ids[:2] == (
        "kcue_finance_regional_tuition",
        "kcue_student_regional_foreign",
    )


def test_available_adapters_context_preserves_locate_for_location_candidates() -> None:
    """Location-dependent candidates remain exposed as concrete adapter tools."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "서울 강남구 교통사고 다발지역을 공공 API로 조회해줘"
    )

    assert message is not None
    assert "koroad_accident_hazard_search" in (message.content or "")
    assert "koroad_accident_hazard_search" in turn_tool_ids


def test_available_adapters_context_constrains_aed_region_filters_to_find() -> None:
    """NMC AED q0/q1 are official region filters, not a locate prerequisite."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "종로구 자동심장충격기 위치 알려줘."
    )

    assert message is not None
    content = message.content or ""
    assert "nmc_aed_site_locate" in content
    assert "kakao_keyword_search" not in content
    assert "nmc_aed_site_locate" in turn_tool_ids
    assert "kakao_keyword_search" not in turn_tool_ids


def test_available_adapters_context_emergency_or_aed_keeps_aed_near_er() -> None:
    """When the citizen explicitly asks for AED, expose it next to emergency search."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "부산역 근처에서 사람이 쓰러졌어. 제일 가까운 응급실이나 AED 어디로 가야 해?"
    )

    assert message is not None
    assert "nmc_emergency_search" in turn_tool_ids[:2]
    assert "nmc_aed_site_locate" in turn_tool_ids[:2]


def test_available_adapters_context_implicit_collapse_exposes_er_and_aed() -> None:
    """Ordinary collapse wording must expose emergency-room and AED adapters."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"
    )

    assert message is not None
    assert "kakao_keyword_search" in turn_tool_ids[:3]
    assert "nmc_emergency_search" in turn_tool_ids[:4]
    assert "nmc_aed_site_locate" in turn_tool_ids[:4]
    assert "kma_current_observation" not in turn_tool_ids


def test_available_adapters_context_unconscious_walk_is_not_weather() -> None:
    """Emergency wording with 산책 must not be classified as ordinary walk weather."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "해운대에서 산책 중인데 사람이 의식을 잃은 것 같아. "
        "근처 응급실이나 심장충격기 있는 곳 알려줘"
    )

    assert message is not None
    assert "nmc_emergency_search" in turn_tool_ids[:4]
    assert "nmc_aed_site_locate" in turn_tool_ids[:4]
    assert "kma_current_observation" not in turn_tool_ids
    assert "kma_short_term_forecast" not in turn_tool_ids


def test_available_adapters_context_chart_query_excludes_amos() -> None:
    """Analyzed weather-chart turns must not expose airport AMOS as a candidate."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "분석일기도 지상일기도를 WthrChartInfoService/getSurfaceChart로 오늘 20260526 "
        "code=24 조건으로 조회해줘"
    )

    assert message is not None
    content = message.content or ""
    assert turn_tool_ids == ("kma_apihub_url_analysis_weather_chart_image",)
    assert "kma_apihub_url_analysis_weather_chart_image" in content
    assert "kma_apihub_url_air_amos_minute" not in content


def test_available_adapters_context_gimhae_aviation_excludes_unsupported_amos() -> None:
    """Gimhae aviation turns should expose METAR, not unsupported AMOS."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "김해공항 AMOS 매분자료로 현재 시정 RVR 바람 기압을 확인해줘. "
        "김해가 AMOS 지원 대상이 아니면 METAR 해독자료로 대체해줘"
    )

    assert message is not None
    content = message.content or ""
    assert turn_tool_ids[0] == "kma_apihub_url_air_metar_decoded"
    assert "kma_apihub_url_air_metar_decoded" in turn_tool_ids
    assert "kma_apihub_url_air_amos_minute" not in turn_tool_ids
    assert "kakao_keyword_search" not in turn_tool_ids
    assert "kakao_address_search" not in turn_tool_ids
    assert "kma_current_observation" not in turn_tool_ids
    assert "kma_apihub_url_air_metar_decoded" in content
    assert "kma_apihub_url_air_amos_minute" not in content
    assert "kakao_keyword_search" not in content
    assert "kma_current_observation" not in content


def test_available_adapters_context_natural_flight_query_prefers_metar() -> None:
    """Natural airport flight wording should expose METAR before ordinary weather."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "오늘 저녁에 김해공항에서 서울 가는 비행기 예약했는데 날씨 어때? 비행기 뜰만한가?"
    )

    assert message is not None
    content = message.content or ""
    assert turn_tool_ids[0] == "kma_apihub_url_air_metar_decoded"
    assert "kma_apihub_url_air_metar_decoded" in turn_tool_ids
    assert "kma_apihub_url_air_amos_minute" not in turn_tool_ids
    assert "kakao_keyword_search" not in turn_tool_ids
    assert "kma_current_observation" not in turn_tool_ids
    assert "kma_apihub_url_air_metar_decoded" in content
    assert "kakao_keyword_search" not in content
    assert "kma_current_observation" not in content


def test_available_adapters_context_mixed_gimhae_gimpo_query_prefers_metar() -> None:
    """김해→김포 ordinary flight turns should not be treated as a Gimpo AMOS-only ask."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘"
    )

    assert message is not None
    content = message.content or ""
    assert turn_tool_ids[0] == "kma_apihub_url_air_metar_decoded"
    assert "kma_apihub_url_air_metar_decoded" in turn_tool_ids
    assert "gyeryong_assistive_device_charging_place_locate" not in turn_tool_ids
    assert "kakao_keyword_search" not in turn_tool_ids
    assert "kma_current_observation" not in turn_tool_ids
    assert "kma_apihub_url_air_metar_decoded" in content
    assert "gyeryong_assistive_device_charging_place_locate" not in content


def test_available_adapters_context_gimpo_runway_query_prefers_amos() -> None:
    """Gimpo runway-area wording should expose AMOS before decoded METAR."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "김포공항에서 제주 가는 밤 비행기인데 활주로 쪽 바람이랑 시정 괜찮아? 지연될 정도야?"
    )

    assert message is not None
    content = message.content or ""
    assert turn_tool_ids[0] == "kma_apihub_url_air_amos_minute"
    assert "kma_apihub_url_air_amos_minute" in turn_tool_ids
    assert "kma_apihub_url_air_metar_decoded" in turn_tool_ids
    assert "kma_apihub_url_air_amos_minute" in content
    assert "kma_current_observation" not in turn_tool_ids


def test_available_adapters_context_pps_bid_search_exposes_search_contract() -> None:
    """PPS bid-list wording should expose search-date fields, not bid-number detail lookup."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "이번 주 부산시 전기공사 입찰 올라온 거 있어?"
    )

    assert message is not None
    content = message.content or ""
    assert turn_tool_ids[0] == "pps_bid_public_info"
    assert "pps_bid_public_info" in turn_tool_ids
    assert "kakao_address_search" not in turn_tool_ids
    assert "getBidPblancListInfoCnstwkPPSSrch" in content
    assert "inqry_bgn_dt" in content
    assert "inqry_end_dt" in content
    assert "bid_ntce_nm" in content
    assert "bid_ntce_no" not in content


def test_available_adapters_context_natural_kcue_finance_excludes_locate() -> None:
    """Natural official university tuition wording should expose KCUE finance first."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "대학 등록금이 지역별로 얼마나 차이 나는지 공식 자료로 보고 싶어"
    )

    assert message is not None
    assert turn_tool_ids[:2] == (
        "kcue_finance_regional_tuition",
        "kcue_student_regional_foreign",
    )


def test_available_adapters_context_natural_kcue_foreign_students_excludes_locate() -> None:
    """Natural official foreign-student wording should expose KCUE student data first."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "지역별 외국인 유학생 현황을 대학 공식 공개자료로 확인해줘"
    )

    assert message is not None
    assert turn_tool_ids[:2] == (
        "kcue_student_regional_foreign",
        "kcue_finance_regional_tuition",
    )


def test_available_adapters_context_natural_weather_flow_uses_analysis_data() -> None:
    """Natural nationwide weather-flow wording should expose KMA analysis data."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "오늘 전국 날씨 흐름이 어떤지 공식 기상자료로 확인해줘"
    )

    assert message is not None
    assert turn_tool_ids[0] == "kma_apihub_url_analysis_weather_chart_image"
    assert "kma_current_observation" not in turn_tool_ids


def test_available_adapters_context_lifestyle_weather_keeps_kma_and_location() -> None:
    """Ordinary rain/umbrella wording should expose KMA weather + locate, not unrelated APIs."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "퇴근하고 해운대 산책 갈 건데 지금 비 와? 우산 챙겨야 해?"
    )

    assert message is not None
    assert "kakao_keyword_search" in turn_tool_ids[:3]
    assert "kma_current_observation" in turn_tool_ids[:4]
    assert any(
        tool_id in turn_tool_ids
        for tool_id in ("kma_ultra_short_term_forecast", "kma_short_term_forecast")
    )
    assert "bfc_funeral_area_fee" not in turn_tool_ids

    message, forecast_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "내일 아침 부산 사상구 비 예보랑 기온 알려줘"
    )
    assert message is not None
    assert "kma_short_term_forecast" in forecast_tool_ids
    assert "bfc_funeral_area_fee" not in forecast_tool_ids


def test_available_adapters_context_safety_location_queries_keep_domain_tool() -> None:
    """Ordinary safety-location wording should not be swallowed by generic locate."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "가까운 비상벨이나 긴급신고함 위치 알려줘"
    )

    assert message is not None
    assert "mois_emergency_call_box_lookup" in turn_tool_ids[:3]


def test_available_adapters_context_emergency_bell_is_not_medical_emergency() -> None:
    """Emergency-call-box wording should not be captured by medical collapse routing."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "해운대 해수욕장 근처에 위급할 때 누를 수 있는 비상벨 있어?"
    )

    assert message is not None
    assert turn_tool_ids[0] == "mois_emergency_call_box_lookup"
    assert "nmc_emergency_search" not in turn_tool_ids[:3]


def test_available_adapters_context_assistive_charger_keeps_domain_tool() -> None:
    """Assistive-device charger wording should expose the dedicated charger adapter."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "계룡시 전동보장구 충전소 어디 있어?"
    )

    assert message is not None
    assert "gyeryong_assistive_device_charging_place_locate" in turn_tool_ids[:3]


def test_available_adapters_context_hospital_detail_keeps_detail_tool() -> None:
    """Hospital detail wording should expose HIRA detail alongside general search."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "해운대 근처 병원 상세정보랑 진료과 확인해줘"
    )

    assert message is not None
    assert "hira_hospital_search" in turn_tool_ids
    assert "hira_medical_institution_detail" in turn_tool_ids


def test_available_adapters_context_analysis_point_exposes_high_resolution() -> None:
    """Analysis-data wording should expose KMA analyzed grid tools, not only forecasts."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "김해공항 주변은 기상청이 이미 분석한 자료로 보면 비나 바람 상태 괜찮아?"
    )

    assert message is not None
    content = message.content or ""
    assert "kma_apihub_url_high_resolution_grid_point" in turn_tool_ids
    assert "kma_apihub_url_aws_objective_analysis_grid" in turn_tool_ids
    assert "kma_apihub_url_high_resolution_grid_point" in content
    assert "kma_short_term_forecast" not in turn_tool_ids[:3]


def test_available_adapters_context_analysis_map_exposes_chart_tool() -> None:
    """Map/chart analysis wording should expose the analyzed chart URL adapter."""

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)
    engine = QueryEngine(
        llm_client=_FailingMockClient(),
        tool_registry=registry,
        tool_executor=executor,
    )

    message, turn_tool_ids = engine._build_available_adapters_context(  # noqa: SLF001
        "공항 관측값 말고 기상청에서 이미 분석한 일기도나 지도 자료 기준으로 "
        "오늘 저녁 남부 쪽 비구름이랑 바람 흐름은 어때?"
    )

    assert message is not None
    content = message.content or ""
    assert turn_tool_ids[0] == "kma_apihub_url_analysis_weather_chart_image"
    assert "kma_apihub_url_analysis_weather_chart_image" in content
    assert "kakao_keyword_search" not in turn_tool_ids
    assert "kma_apihub_url_air_amos_minute" not in turn_tool_ids
    assert "kma_apihub_url_air_metar_decoded" not in turn_tool_ids


def test_kma_analysis_map_gate_rejects_grid_substitution() -> None:
    """Map/chart requests must not fall back to point-grid analysis tools."""

    query = (
        "공항 관측값 말고 기상청에서 이미 분석한 일기도나 지도 자료 기준으로 "
        "오늘 저녁 남부 쪽 비구름이랑 바람 흐름은 어때?"
    )

    assert _check_kma_analysis_tool_choice_prerequisite(
        "find",
        {"tool_id": "kma_apihub_url_aws_objective_analysis_grid", "params": {"obs": "TA"}},
        query,
    )
    assert _check_kma_analysis_tool_choice_prerequisite(
        "kma_apihub_url_high_resolution_grid_point",
        {"lat": 35.1, "lon": 129.0},
        query,
    )
    assert (
        _check_kma_analysis_tool_choice_prerequisite(
            "find",
            {
                "tool_id": "kma_apihub_url_analysis_weather_chart_image",
                "params": {"anal_time": "2026052618"},
            },
            query,
        )
        is None
    )


def test_kma_analysis_final_gate_rejects_chart_failure_substitution() -> None:
    """Chart approval failures should not be replaced with grid or observation claims."""

    query = (
        "공항 관측값 말고 기상청에서 이미 분석한 일기도나 지도 자료 기준으로 "
        "오늘 저녁 남부 쪽 비구름이랑 바람 흐름은 어때?"
    )
    llm_messages = [
        SimpleNamespace(
            role="tool",
            name="kma_apihub_url_analysis_weather_chart_image",
            content=(
                '{"tool_id":"kma_apihub_url_analysis_weather_chart_image",'
                '"result":{"kind":"error","message":"활용신청이 필요한 API 입니다","status":403}}'
            ),
        )
    ]

    assert _final_answer_substitutes_after_kma_chart_failure(
        "분석일기도 API는 활용신청이 필요합니다. 대안으로 AWS 객관분석 값을 보면 "
        "기온은 22.5도, 풍속은 4.7m/s입니다.",
        query,
        llm_messages,
    )
    assert _final_answer_substitutes_after_kma_chart_failure(
        "기상청 APIHub 분석일기도 조회는 활용신청이 필요한 상태입니다. "
        "다만 일반적인 남부 지역 패턴상 비구름은 남해안 쪽에 걸치고 "
        "서풍 계열 바람 흐름이 이어질 가능성이 있어 보입니다.",
        query,
        llm_messages,
    )
    assert not _final_answer_substitutes_after_kma_chart_failure(
        "기상청 APIHub 분석일기도 조회가 활용신청 필요 상태로 실패해, "
        "이번 실행에서는 지도 기준 비구름이나 바람 흐름을 확인할 수 없습니다.",
        query,
        llm_messages,
    )


# ---------------------------------------------------------------------------
# Scenario 1: One tool call -> task_complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_tool_call_task_complete(
    mock_llm_client: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """One tool call followed by a text answer produces the expected event stream."""
    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    events = await _collect(engine, "서울 강남구 교통사고 현황")

    event_types = [e.type for e in events]

    # Must include all four essential event types
    assert "tool_use" in event_types
    assert "tool_result" in event_types
    assert "text_delta" in event_types
    assert "stop" in event_types

    # Last event is always stop
    assert events[-1].type == "stop"

    # Stop reason indicates the model finished speaking (end_turn after text answer)
    assert events[-1].stop_reason in (StopReason.end_turn, StopReason.task_complete)

    # Message history: system + user + assistant(tool_call) + tool + assistant(text)
    assert engine.message_count >= 5

    # One turn completed
    assert engine.budget.turns_used == 1


# ---------------------------------------------------------------------------
# Scenario 2: Two sequential tool calls -> task_complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_tool_calls_both_dispatched(
    mock_llm_client_two_tools: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """Two tool calls in one LLM response: both tool_use and tool_result events appear."""
    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client_two_tools),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    events = await _collect(engine, "서울 강남구 날씨와 교통사고 정보를 알려주세요")

    tool_use_events = [e for e in events if e.type == "tool_use"]
    tool_result_events = [e for e in events if e.type == "tool_result"]

    # Both tools dispatched
    assert len(tool_use_events) == 2
    assert len(tool_result_events) == 2

    tool_names_used = {e.tool_name for e in tool_use_events}
    assert "traffic_accident_search" in tool_names_used
    assert "weather_info" in tool_names_used

    # Stream ends with stop
    assert events[-1].type == "stop"


# ---------------------------------------------------------------------------
# Scenario 3: No tool call -> end_turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_tool_call_end_turn(
    mock_llm_client_no_tools: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """A direct text response without tool calls yields text_delta events and end_turn stop."""
    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client_no_tools),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    events = await _collect(engine, "안녕하세요")

    event_types = [e.type for e in events]

    # Text content is emitted
    assert "text_delta" in event_types

    # No tool events
    assert "tool_use" not in event_types
    assert "tool_result" not in event_types

    # Stop is end_turn
    assert events[-1].type == "stop"
    assert events[-1].stop_reason == StopReason.end_turn


# ---------------------------------------------------------------------------
# Scenario 4: Event ordering guarantee
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_ordering_guarantee(
    mock_llm_client: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """Verify strict event ordering: tool_use before tool_result, usage_update before stop."""
    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    events = await _collect(engine, "교통사고 정보")

    # stop is always the very last event
    assert events[-1].type == "stop"

    # Locate indices for ordering checks
    indices: dict[str, list[int]] = {}
    for i, e in enumerate(events):
        indices.setdefault(e.type, []).append(i)

    # tool_use must precede its corresponding tool_result
    if "tool_use" in indices and "tool_result" in indices:
        assert indices["tool_use"][0] < indices["tool_result"][0]

    # usage_update must precede stop (if present)
    if "usage_update" in indices:
        last_usage_idx = indices["usage_update"][-1]
        stop_idx = indices["stop"][0]
        assert last_usage_idx < stop_idx


# ---------------------------------------------------------------------------
# Scenario 5: No-raise contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_raise_contract(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """engine.run() must not raise even when the LLM client throws an exception."""
    failing_client = _FailingMockClient()

    engine = QueryEngine(
        llm_client=failing_client,
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    # Must not raise; collect all events normally
    events = await _collect(engine, "이 요청은 실패합니다")

    assert len(events) >= 1
    last = events[-1]
    assert last.type == "stop"
    assert last.stop_reason == StopReason.error_unrecoverable


# ---------------------------------------------------------------------------
# Scenario 6: Turn count increment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_turn_count_increments_each_run(
    mock_llm_client_no_tools: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """budget.turns_used increments by 1 after each call to run()."""
    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client_no_tools),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    assert engine.budget.turns_used == 0

    await _collect(engine, "첫 번째 메시지")
    assert engine.budget.turns_used == 1

    await _collect(engine, "두 번째 메시지")
    assert engine.budget.turns_used == 2


# ---------------------------------------------------------------------------
# Scenario 7: System prompt initialization
# ---------------------------------------------------------------------------


def test_default_system_prompt_is_first_message(
    mock_llm_client_no_tools: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """First message in history is the system prompt from the default ContextBuilder."""
    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client_no_tools),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    # message_count is 1: the system prompt
    assert engine.message_count == 1

    # The internal state carries a system message generated by ContextBuilder
    first_message = engine._state.messages[0]  # noqa: SLF001
    assert first_message.role == "system"
    # Content must be non-empty (default ContextBuilder uses SystemPromptConfig defaults)
    assert first_message.content
    # The default persona must be present
    assert "UMMAYA" in (first_message.content or "")


def test_custom_system_prompt(
    mock_llm_client_no_tools: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """A custom SystemPromptConfig passed via ContextBuilder is stored as the first message."""
    custom_prompt = "You are a specialized assistant for road safety information."

    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client_no_tools),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
        context_builder=ContextBuilder(config=SystemPromptConfig(platform_name=custom_prompt)),
    )

    first_message = engine._state.messages[0]  # noqa: SLF001
    assert first_message.role == "system"
    assert custom_prompt in first_message.content


# ---------------------------------------------------------------------------
# Scenario 8: Budget property
# ---------------------------------------------------------------------------


def test_budget_initial_snapshot(
    mock_llm_client_no_tools: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """Initial budget snapshot reflects zero usage and correct configured limits."""
    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client_no_tools),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    budget = engine.budget

    assert isinstance(budget, SessionBudget)
    assert budget.tokens_used == 0
    assert budget.turns_used == 0
    assert budget.tokens_budget == 100_000  # MockLLMClient default budget
    assert budget.turns_budget == sample_config.max_turns
    assert budget.is_exhausted is False


@pytest.mark.asyncio
async def test_budget_reflects_token_usage_after_run(
    mock_llm_client_no_tools: object,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    sample_config: QueryEngineConfig,
) -> None:
    """Budget snapshot reflects token consumption after a completed turn."""
    engine = QueryEngine(
        llm_client=_MockClientAdapter(mock_llm_client_no_tools),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=sample_config,
    )

    await _collect(engine, "안녕하세요")

    budget = engine.budget
    assert budget.turns_used == 1
    assert budget.is_exhausted is False
    # turns_remaining decreases after a completed turn
    assert budget.turns_remaining == sample_config.max_turns - 1
