# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from ummaya.engine.config import QueryEngineConfig
from ummaya.engine.events import QueryEvent
from ummaya.engine.models import QueryContext, QueryState
from ummaya.engine.query import query
from ummaya.llm.client import LLMClient  # noqa: F401
from ummaya.llm.models import ChatMessage, StreamEvent, TokenUsage
from ummaya.llm.usage import UsageTracker
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry

QueryContext.model_rebuild()


async def _collect(ctx: QueryContext) -> list[QueryEvent]:
    events: list[QueryEvent] = []
    async for event in query(ctx):
        events.append(event)
    return events


class _ReplayLLMClient:
    def __init__(self, responses: list[list[StreamEvent]]) -> None:
        self._responses = responses
        self._call_index = 0
        self._usage = UsageTracker(budget=100_000)
        self.call_count = 0

    @property
    def usage(self) -> UsageTracker:
        return self._usage

    async def stream(
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> AsyncIterator[StreamEvent]:
        del messages, kwargs
        self.call_count += 1
        events = self._responses[min(self._call_index, len(self._responses) - 1)]
        self._call_index += 1
        for event in events:
            yield event


def _make_ctx(
    llm_client: _ReplayLLMClient,
    tool_executor: ToolExecutor,
    tool_registry: ToolRegistry,
    config: QueryEngineConfig,
) -> QueryContext:
    state = QueryState(
        usage=UsageTracker(budget=100_000),
        messages=[
            ChatMessage(role="system", content="You are UMMAYA."),
            ChatMessage(
                role="user",
                content=(
                    "오늘 부산 사하구 날씨랑 미세먼지 상태를 확인해줘. "
                    "날씨와 대기질 출처를 나눠서 알려줘."
                ),
            ),
        ],
    )
    return QueryContext.model_construct(
        state=state,
        llm_client=llm_client,
        tool_executor=tool_executor,
        tool_registry=tool_registry,
        config=config,
        iteration=0,
        turn_start_message_index=1,
    )


@pytest.mark.asyncio
async def test_successful_tool_result_repairs_visible_planning_as_nonfinal(
    tool_executor_with_mocks: ToolExecutor,
    populated_registry: ToolRegistry,
    sample_config: QueryEngineConfig,
) -> None:
    client = _ReplayLLMClient(
        responses=[
            [
                StreamEvent(
                    type="tool_call_delta",
                    tool_call_index=0,
                    tool_call_id="call_air",
                    function_name="traffic_accident_search",
                    function_args_delta='{"query": "부산 사하구 미세먼지"}',
                ),
                StreamEvent(type="done"),
            ],
            [
                StreamEvent(
                    type="content_delta",
                    content=(
                        "시스템 지침에 따르면 현재 데이터 요청은 도구를 사용해야 합니다. "
                        "따라서 kma_current_observation을 호출하겠습니다. "
                        "base_date와 base_time을 설정해야 합니다."
                    ),
                ),
                StreamEvent(
                    type="usage",
                    usage=TokenUsage(input_tokens=200, output_tokens=60),
                ),
                StreamEvent(type="done"),
            ],
            [
                StreamEvent(
                    type="content_delta",
                    content="공식 도구 결과 기준으로 확인된 값만 정리합니다.",
                ),
                StreamEvent(type="done"),
            ],
        ],
    )
    ctx = _make_ctx(client, tool_executor_with_mocks, populated_registry, sample_config)

    events = await _collect(ctx)
    visible_text = "".join(event.content or "" for event in events if event.type == "text_delta")

    assert client.call_count == 3
    assert "시스템 지침" not in visible_text
    assert "호출하겠습니다" not in visible_text
    assert "base_time" not in visible_text
    assert "공식 도구 결과 기준" in visible_text


@pytest.mark.asyncio
async def test_successful_tool_result_paints_next_tool_prelude_before_tool_use(
    tool_executor_with_mocks: ToolExecutor,
    populated_registry: ToolRegistry,
    sample_config: QueryEngineConfig,
) -> None:
    client = _ReplayLLMClient(
        responses=[
            [
                StreamEvent(
                    type="tool_call_delta",
                    tool_call_index=0,
                    tool_call_id="call_air",
                    function_name="traffic_accident_search",
                    function_args_delta='{"query": "부산 사하구 미세먼지"}',
                ),
                StreamEvent(type="done"),
            ],
            [
                StreamEvent(
                    type="content_delta",
                    content="대기질 결과를 확인했습니다. 이어서 날씨 관측값을 확인하겠습니다.",
                ),
                StreamEvent(
                    type="tool_call_delta",
                    tool_call_index=0,
                    tool_call_id="call_weather",
                    function_name="weather_info",
                    function_args_delta='{"query": "부산 사하구 날씨"}',
                ),
                StreamEvent(type="done"),
            ],
            [
                StreamEvent(
                    type="content_delta",
                    content="날씨와 대기질 출처를 분리해 정리합니다.",
                ),
                StreamEvent(type="done"),
            ],
        ],
    )
    ctx = _make_ctx(client, tool_executor_with_mocks, populated_registry, sample_config)

    events = await _collect(ctx)
    types = [event.type for event in events]
    prelude_index = next(
        index
        for index, event in enumerate(events)
        if event.type == "text_delta" and "이어서 날씨 관측값" in (event.content or "")
    )
    second_tool_index = next(
        index
        for index, event in enumerate(events)
        if event.type == "tool_use" and event.tool_call_id == "call_weather"
    )
    visible_text = "".join(event.content or "" for event in events if event.type == "text_delta")

    assert types.count("tool_use") == 2
    assert prelude_index < second_tool_index
    assert "이어서 날씨 관측값" in visible_text
    assert "날씨와 대기질 출처" in visible_text
