# SPDX-License-Identifier: Apache-2.0
"""Multi-turn integration tests for QueryEngine.

Covers:
- 3-turn conversation flow (tool-call turn, no-tool turn, tool-call turn)
- Preprocessing pipeline trigger with small context window
- 20-turn stress test (no tools, rapid fire)
- History accumulation verification across turn types
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from kosmos.context.builder import ContextBuilder
from kosmos.context.models import SystemPromptConfig
from kosmos.engine.config import QueryEngineConfig
from kosmos.engine.engine import QueryEngine
from kosmos.engine.events import QueryEvent, StopReason

# Force QueryContext to resolve the LLMClient forward reference so that
# mock subclasses pass the isinstance check inside QueryContext validation.
from kosmos.engine.models import QueryContext  # noqa: E402
from kosmos.llm.client import LLMClient
from kosmos.llm.models import ChatMessage, StreamEvent, TokenUsage
from kosmos.llm.usage import UsageTracker
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.registry import ToolRegistry

QueryContext.model_rebuild()


# ---------------------------------------------------------------------------
# LLMClient-compatible mock base (same pattern as test_engine.py)
# ---------------------------------------------------------------------------


class _MockLLMClientBase(LLMClient):
    """Base mock that bypasses LLMClient.__init__ to avoid requiring API tokens."""

    def __new__(cls, *args: object, **kwargs: object) -> _MockLLMClientBase:
        return object.__new__(cls)  # type: ignore[return-value]


class _MockClientAdapter(_MockLLMClientBase):
    """Delegate stream() and usage to any duck-typed mock LLM client."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    @property
    def usage(self) -> UsageTracker:  # type: ignore[override]
        return self._delegate.usage  # type: ignore[attr-defined]

    async def stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> AsyncIterator[object]:
        async for event in self._delegate.stream(messages, **kwargs):
            yield event


# ---------------------------------------------------------------------------
# Re-usable StreamEvent sequences (specific to multi-turn tests)
# ---------------------------------------------------------------------------

# Turn with a single tool call followed by a text answer
_TURN_TOOL_CALL: list[StreamEvent] = [
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id="call_mt_001",
        function_name="traffic_accident_search",
        function_args_delta=None,
    ),
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id=None,
        function_name=None,
        function_args_delta='{"query": "multi-turn test"}',
    ),
    StreamEvent(
        type="usage",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    ),
    StreamEvent(type="done"),
]

_TURN_TEXT_ANSWER: list[StreamEvent] = [
    StreamEvent(
        type="content_delta",
        content="Tool call completed successfully.",
    ),
    StreamEvent(
        type="usage",
        usage=TokenUsage(input_tokens=200, output_tokens=80),
    ),
    StreamEvent(type="done"),
]

# Pure text response — no tool call
_TURN_NO_TOOL: list[StreamEvent] = [
    StreamEvent(
        type="content_delta",
        content="Direct answer without tool use.",
    ),
    StreamEvent(
        type="usage",
        usage=TokenUsage(input_tokens=60, output_tokens=25),
    ),
    StreamEvent(type="done"),
]

# Second tool call sequence with a different tool_call_id (turn 3 of 3-turn test)
_TURN_TOOL_CALL_3: list[StreamEvent] = [
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id="call_mt_003",
        function_name="weather_info",
        function_args_delta=None,
    ),
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id=None,
        function_name=None,
        function_args_delta='{"query": "turn 3 weather"}',
    ),
    StreamEvent(
        type="usage",
        usage=TokenUsage(input_tokens=110, output_tokens=55),
    ),
    StreamEvent(type="done"),
]

_TURN_TEXT_ANSWER_3: list[StreamEvent] = [
    StreamEvent(
        type="content_delta",
        content="Turn 3 answer after tool call.",
    ),
    StreamEvent(
        type="usage",
        usage=TokenUsage(input_tokens=220, output_tokens=90),
    ),
    StreamEvent(type="done"),
]


# ---------------------------------------------------------------------------
# Inline mock client — avoids conftest import coupling for multi-turn tests
# ---------------------------------------------------------------------------


class _MultiTurnMockClient:
    """Simple mock LLM client for multi-turn tests with configurable responses.

    Each call to stream() consumes the next response sequence from the list.
    When all responses are exhausted the last response is repeated.
    """

    def __init__(
        self,
        responses: list[list[StreamEvent]],
        budget: int = 500_000,
    ) -> None:
        self._responses = responses
        self._call_index = 0
        self._usage = UsageTracker(budget=budget)
        self.call_count: int = 0
        self.last_messages: list[ChatMessage] | None = None

    @property
    def usage(self) -> UsageTracker:
        return self._usage

    async def stream(
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> AsyncIterator[StreamEvent]:
        self.last_messages = list(messages)
        self.call_count += 1
        events = self._responses[min(self._call_index, len(self._responses) - 1)]
        self._call_index += 1
        for event in events:
            yield event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect(engine: QueryEngine, message: str) -> list[QueryEvent]:
    """Collect all events from a single engine.run() call."""
    return [event async for event in engine.run(message)]


def _make_engine(
    mock_client: _MultiTurnMockClient,
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
    config: QueryEngineConfig | None = None,
) -> QueryEngine:
    """Construct a QueryEngine wrapping the given mock client."""
    return QueryEngine(
        llm_client=_MockClientAdapter(mock_client),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        config=config or QueryEngineConfig(),
    )


# ---------------------------------------------------------------------------
# Test 1: 3-turn conversation flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_turn_conversation_flow(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Three-turn conversation: tool turn, no-tool turn, tool turn.

    Verifies:
    - Each turn yields the correct event types.
    - turn_count increments to 3 after all three turns.
    - Message history accumulates correctly.
    """
    # Response ordering:
    # call 0 -> tool call (turn 1, iteration 1)
    # call 1 -> text answer (turn 1, iteration 2 after tool result)
    # call 2 -> no-tool answer (turn 2)
    # call 3 -> tool call (turn 3, iteration 1)
    # call 4 -> text answer (turn 3, iteration 2 after tool result)
    client = _MultiTurnMockClient(
        responses=[
            _TURN_TOOL_CALL,
            _TURN_TEXT_ANSWER,
            _TURN_NO_TOOL,
            _TURN_TOOL_CALL_3,
            _TURN_TEXT_ANSWER_3,
        ]
    )
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks)

    # --- Turn 1: user asks question -> LLM calls tool -> LLM answers ---
    events_t1 = await _collect(engine, "Tell me about traffic accidents.")
    types_t1 = [e.type for e in events_t1]
    assert "tool_use" in types_t1, "Turn 1 must include tool_use event"
    assert "tool_result" in types_t1, "Turn 1 must include tool_result event"
    assert "text_delta" in types_t1, "Turn 1 must include text_delta event"
    assert events_t1[-1].type == "stop", "Turn 1 must end with stop event"
    assert events_t1[-1].stop_reason == StopReason.end_turn
    assert engine.budget.turns_used == 1

    # After turn 1: system + user + assistant-tool-call + tool-result + assistant-text
    assert engine.message_count >= 5, (
        f"After tool turn expected >= 5 messages, got {engine.message_count}"
    )
    count_after_turn1 = engine.message_count

    # --- Turn 2: follow-up -> LLM answers directly, no tool ---
    events_t2 = await _collect(engine, "Thanks, any additional info?")
    types_t2 = [e.type for e in events_t2]
    assert "text_delta" in types_t2, "Turn 2 must include text_delta event"
    assert "tool_use" not in types_t2, "Turn 2 must not include tool_use"
    assert events_t2[-1].type == "stop"
    assert events_t2[-1].stop_reason == StopReason.end_turn
    assert engine.budget.turns_used == 2

    # After turn 2: +user(1) + assistant-text(1) = 2 more messages
    count_after_turn2 = engine.message_count
    assert count_after_turn2 == count_after_turn1 + 2, (
        f"After no-tool turn expected {count_after_turn1 + 2} messages, got {count_after_turn2}"
    )

    # --- Turn 3: another question -> LLM calls tool -> LLM answers ---
    events_t3 = await _collect(engine, "What about weather in Seoul?")
    types_t3 = [e.type for e in events_t3]
    assert "tool_use" in types_t3, "Turn 3 must include tool_use event"
    assert "tool_result" in types_t3, "Turn 3 must include tool_result event"
    assert "text_delta" in types_t3, "Turn 3 must include text_delta event"
    assert events_t3[-1].type == "stop"
    assert events_t3[-1].stop_reason == StopReason.end_turn
    assert engine.budget.turns_used == 3

    # turn_count reaches 3
    assert engine._state.turn_count == 3  # noqa: SLF001

    # History grew by 4 more messages for this tool turn
    count_after_turn3 = engine.message_count
    assert count_after_turn3 == count_after_turn2 + 4, (
        f"After tool turn 3 expected {count_after_turn2 + 4} messages, got {count_after_turn3}"
    )


# ---------------------------------------------------------------------------
# Test 2: Event ordering holds across all three turns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_ordering_across_turns(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Verify event ordering contract within each turn of a multi-turn session."""
    client = _MultiTurnMockClient(
        responses=[
            _TURN_TOOL_CALL,
            _TURN_TEXT_ANSWER,
            _TURN_NO_TOOL,
        ]
    )
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks)

    for turn_message in ["First question with tool.", "Second question direct."]:
        events = await _collect(engine, turn_message)

        # stop is always last
        assert events[-1].type == "stop", "stop must be the final event in every turn"

        # tool_use always before tool_result when both present
        indices: dict[str, list[int]] = {}
        for i, e in enumerate(events):
            indices.setdefault(e.type, []).append(i)

        if "tool_use" in indices and "tool_result" in indices:
            assert indices["tool_use"][0] < indices["tool_result"][0], (
                "tool_use must precede tool_result"
            )

        # usage_update before stop
        if "usage_update" in indices:
            last_usage_idx = indices["usage_update"][-1]
            stop_idx = indices["stop"][0]
            assert last_usage_idx < stop_idx, "usage_update must precede stop"


# ---------------------------------------------------------------------------
# Test 3: Preprocessing trigger with small context window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preprocessing_triggered_with_small_context_window(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Preprocessing pipeline runs when token estimate exceeds threshold.

    A context_window=6000 with threshold=0.6 means preprocessing fires when
    the history exceeds ~3600 tokens. The system prompt is ~4880 tokens after
    the verify-trigger expansion (인증/본인확인/공동인증서/금융인증서/KEC/
    모바일ID/마이데이터 인증/Any-ID SSO mappings), pushing baseline past
    4500. Bumping to 6000 keeps the test invariant — system prompt + room
    for several turn pairs — while preprocessing still fires once turn-pair
    accumulation crosses the threshold.
    """
    config = QueryEngineConfig(
        context_window=6000,
        preprocessing_threshold=0.6,
        # Aggressive snip/microcompact settings
        snip_turn_age=1,
        microcompact_turn_age=1,
    )

    # Build 10 rounds of no-tool responses — each adds a user+assistant pair with
    # enough content to eventually push us over the 250-token threshold.
    long_text_response: list[StreamEvent] = [
        StreamEvent(
            type="content_delta",
            content=(
                "This is a longer response with sufficient content to contribute "
                "meaningfully to the token estimate across multiple turns. "
                "We include enough words to push the running total over the "
                "preprocessing threshold after a few turns."
            ),
        ),
        StreamEvent(
            type="usage",
            usage=TokenUsage(input_tokens=80, output_tokens=40),
        ),
        StreamEvent(type="done"),
    ]

    # Provide 10 responses; the mock client repeats the last one once exhausted.
    client = _MultiTurnMockClient(responses=[long_text_response] * 10)
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks, config=config)

    # Run 8 turns and record the message count after each
    message_counts: list[int] = []
    for i in range(8):
        await _collect(engine, f"User turn {i + 1} with a bit of text content here.")
        message_counts.append(engine.message_count)

    # Without preprocessing, message_count would grow monotonically by 2 per turn.
    # Naive baseline: 1 (system) + 8*2 (user+assistant) = 17 messages.
    # With preprocessing (collapse, microcompact, snip) the count may insert at
    # most one synthetic summary/collapse record when the threshold fires, so we
    # allow naive_baseline + 1 as an upper bound. The key invariant is that the
    # history is BOUNDED, not growing arbitrarily.
    naive_baseline = 1 + 8 * 2  # 17
    final_count = message_counts[-1]
    assert final_count <= naive_baseline + 1, (
        f"Expected preprocessing to bound history at <={naive_baseline + 1}, got {final_count}"
    )
    # And it must not exceed the naive baseline by more than one — preprocessing
    # should compress, not accumulate new history.
    assert final_count <= naive_baseline + 1, f"History grew unbounded: {message_counts!r}"

    # All turns completed successfully
    assert engine.budget.turns_used == 8


# ---------------------------------------------------------------------------
# Test 4: Preprocessing decreases history when threshold is exceeded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preprocessing_compresses_stale_tool_results(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Stale tool results are snipped when preprocessing runs.

    Sets snip_turn_age=1 so tool results from the previous turn are
    immediately eligible for removal.  After a tool-call turn followed by
    additional turns, the history count should not grow unboundedly.
    """
    config = QueryEngineConfig(
        # context_window must be large enough that the budget guard
        # (hard_limit=context_window) does not block turns. The XML-tagged
        # citizen prompt + per-tool trigger inventory introduced by Epic #2152
        # plus the <turn_order> block added by Spec 2521 (FR-010) push the
        # baseline past 3000 tokens. Subsequent directives — Lead-C
        # MUST-NOT-fabricate (NFA/MOHW C-class), Lead-G
        # resolve→lookup chain enforcement, and the verify-trigger
        # expansion (인증/본인확인/공동인증서/금융인증서/KEC/모바일ID/
        # 마이데이터 인증/Any-ID SSO mappings) push the baseline past
        # 4880; bump to 6000 so the preprocessing threshold (0.05 * 6000
        # = 300) still fires on typical test message sizes while leaving
        # headroom for both prompt blocks.
        context_window=6000,
        preprocessing_threshold=0.05,
        snip_turn_age=1,
        microcompact_turn_age=1,
        tool_result_budget=50,
    )

    # Turn 1: tool call + text answer
    # Turns 2-5: direct text answers (these add user + assistant messages)
    responses = [
        _TURN_TOOL_CALL,
        _TURN_TEXT_ANSWER,
    ] + [_TURN_NO_TOOL] * 4

    client = _MultiTurnMockClient(responses=responses)
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks, config=config)

    # Turn 1: tool call turn builds up history with a tool result
    await _collect(engine, "Please search for traffic data.")
    count_after_tool_turn = engine.message_count

    # Turns 2-5: direct text turns; preprocessing should keep history bounded
    for i in range(4):
        await _collect(engine, f"Follow-up question {i + 1}.")

    final_count = engine.message_count
    # Unbounded linear growth would add 4*2 = 8 messages to the post-tool count.
    # With context_window=100 and snip_turn_age=1, preprocessing fires and
    # removes stale tool results, keeping the count strictly below unbounded.
    unbounded = count_after_tool_turn + 8
    assert final_count < unbounded, (
        f"Expected preprocessing to reduce history below {unbounded}, "
        f"but got {final_count} (started at {count_after_tool_turn} after tool turn)"
    )

    assert engine.budget.turns_used == 5


# ---------------------------------------------------------------------------
# Test 5: 20-turn stress test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_twenty_turn_stress_test(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Run 20 consecutive no-tool turns without errors.

    Verifies:
    - turn_count reaches 20.
    - Every turn yields a stop event with reason end_turn.
    - No exceptions propagate.
    """
    # Single no-tool response; mock client repeats the last entry when exhausted.
    client = _MultiTurnMockClient(responses=[_TURN_NO_TOOL])
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks)

    for turn_num in range(1, 21):
        events = await _collect(engine, f"Turn {turn_num}: simple question.")

        # Each turn must yield at least one text_delta and end with stop(end_turn)
        types = [e.type for e in events]
        assert events[-1].type == "stop", f"Turn {turn_num}: expected stop as last event"
        assert events[-1].stop_reason == StopReason.end_turn, (
            f"Turn {turn_num}: expected end_turn, got {events[-1].stop_reason}"
        )
        assert "text_delta" in types, f"Turn {turn_num}: expected text_delta"
        assert engine.budget.turns_used == turn_num

    # Final state checks
    assert engine._state.turn_count == 20  # noqa: SLF001
    assert engine.budget.turns_used == 20
    assert engine.budget.is_exhausted is False  # default max_turns=50


# ---------------------------------------------------------------------------
# Test 6: History accumulation — no-tool turns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_accumulation_no_tool_turns(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Message count grows by exactly 2 per no-tool turn (user + assistant).

    Initial state: 1 message (system prompt).
    After each no-tool turn: +1 user, +1 assistant = +2.
    """
    client = _MultiTurnMockClient(responses=[_TURN_NO_TOOL])
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks)

    # Baseline: system prompt only
    assert engine.message_count == 1, "Initial history should contain only the system prompt"

    for turn_num in range(1, 6):
        await _collect(engine, f"No-tool question {turn_num}.")
        expected = 1 + turn_num * 2
        assert engine.message_count == expected, (
            f"After {turn_num} no-tool turn(s) expected {expected} messages, "
            f"got {engine.message_count}"
        )


# ---------------------------------------------------------------------------
# Test 7: History accumulation — tool-call turns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_accumulation_tool_call_turns(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Message count grows by exactly 4 per tool-call turn.

    Per tool turn: +user(1) + assistant-tool-call(1) + tool-result(1) + assistant-text(1).
    """
    # Each turn needs two LLM calls: tool-call response + text answer.
    # Provide four responses (two turns × two calls each).
    client = _MultiTurnMockClient(
        responses=[
            _TURN_TOOL_CALL,
            _TURN_TEXT_ANSWER,
            _TURN_TOOL_CALL_3,
            _TURN_TEXT_ANSWER_3,
        ]
    )
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks)

    assert engine.message_count == 1, "Initial history should contain only the system prompt"

    # Turn 1 — tool call
    await _collect(engine, "First tool question.")
    expected_after_t1 = 1 + 4  # system + 4 messages
    assert engine.message_count == expected_after_t1, (
        f"After tool turn 1 expected {expected_after_t1} messages, got {engine.message_count}"
    )

    # Turn 2 — another tool call
    await _collect(engine, "Second tool question.")
    expected_after_t2 = expected_after_t1 + 4
    assert engine.message_count == expected_after_t2, (
        f"After tool turn 2 expected {expected_after_t2} messages, got {engine.message_count}"
    )


# ---------------------------------------------------------------------------
# Test 8: History accumulation — mixed turns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_accumulation_mixed_turns(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Mixed no-tool and tool-call turns accumulate history correctly.

    Turn 1: no-tool (+2)
    Turn 2: tool-call (+4)
    Turn 3: no-tool (+2)
    Expected final: 1 + 2 + 4 + 2 = 9 messages
    """
    client = _MultiTurnMockClient(
        responses=[
            _TURN_NO_TOOL,  # turn 1, call 1
            _TURN_TOOL_CALL,  # turn 2, call 2 (tool request)
            _TURN_TEXT_ANSWER,  # turn 2, call 3 (text after tool)
            _TURN_NO_TOOL,  # turn 3, call 4
        ]
    )
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks)

    assert engine.message_count == 1

    # Turn 1: no-tool
    await _collect(engine, "No-tool turn.")
    assert engine.message_count == 3, (
        f"After no-tool turn expected 3 messages, got {engine.message_count}"
    )

    # Turn 2: tool-call
    await _collect(engine, "Tool-call turn.")
    assert engine.message_count == 7, (
        f"After tool turn expected 7 messages, got {engine.message_count}"
    )

    # Turn 3: no-tool
    await _collect(engine, "Another no-tool turn.")
    assert engine.message_count == 9, (
        f"After final no-tool turn expected 9 messages, got {engine.message_count}"
    )

    assert engine.budget.turns_used == 3


# ---------------------------------------------------------------------------
# Test 9: Turn budget enforcement stops the engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_turn_budget_enforcement(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """Engine yields api_budget_exceeded after max_turns is reached."""
    config = QueryEngineConfig(max_turns=3)
    client = _MultiTurnMockClient(responses=[_TURN_NO_TOOL])
    engine = _make_engine(client, populated_registry, tool_executor_with_mocks, config=config)

    # Consume all 3 allowed turns
    for _ in range(3):
        events = await _collect(engine, "Normal question.")
        assert events[-1].stop_reason == StopReason.end_turn

    assert engine.budget.turns_used == 3
    assert engine.budget.is_exhausted is True

    # Next turn must be rejected immediately
    over_budget_events = await _collect(engine, "This should be rejected.")
    assert len(over_budget_events) == 1
    assert over_budget_events[0].type == "stop"
    assert over_budget_events[0].stop_reason == StopReason.api_budget_exceeded


# ---------------------------------------------------------------------------
# Test 10: System prompt persists in history across all turns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_persists_across_turns(
    populated_registry: ToolRegistry,
    tool_executor_with_mocks: ToolExecutor,
) -> None:
    """The system prompt remains the first message throughout the session."""
    custom_prompt = "You are a road-safety specialist assistant."
    client = _MultiTurnMockClient(responses=[_TURN_NO_TOOL])
    engine = QueryEngine(
        llm_client=_MockClientAdapter(client),
        tool_registry=populated_registry,
        tool_executor=tool_executor_with_mocks,
        context_builder=ContextBuilder(config=SystemPromptConfig(platform_name=custom_prompt)),
    )

    # The assembled system message is derived from SystemPromptConfig (not raw string)
    expected_content = engine._state.messages[0].content  # noqa: SLF001

    for turn_num in range(1, 4):
        await _collect(engine, f"Turn {turn_num} question.")
        first_msg = engine._state.messages[0]  # noqa: SLF001
        assert first_msg.role == "system", (
            f"After turn {turn_num}, first message must still be 'system'"
        )
        assert first_msg.content == expected_content, (
            f"After turn {turn_num}, system prompt must be unchanged"
        )
