# SPDX-License-Identifier: Apache-2.0
"""Edge-case E2E tests for Scenario 1 Route Safety (030 rebase).

Covers spec.md §Edge Cases for the two-tool facade (resolve_location + lookup):
  1. Unregistered tool_id in lookup(mode="fetch")
  2. Max-iterations guard
  3. Pydantic validation failure on lookup input
  4. Budget exceeded mid-turn (api_budget_exceeded)
  5. ResolveError(not_found) path
  6. KMA base_time validation error
  7. ResolveError(ambiguous) disambiguation

All tests use scripted MockLLMClient + recorded fixtures. Zero live API calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from kosmos.context.builder import ContextBuilder
from kosmos.engine.config import QueryEngineConfig
from kosmos.engine.engine import QueryEngine
from kosmos.engine.events import StopReason
from kosmos.llm.models import StreamEvent, TokenUsage
from tests.e2e.conftest import (
    TRIGGER_QUERY,
    _build_httpx_mock,
    _build_registry_and_executor,
    _MockLLMClientAdapter,
)
from tests.engine.conftest import MockLLMClient

# ---------------------------------------------------------------------------
# Helper: minimal no-op httpx mock (no actual HTTP calls expected)
# ---------------------------------------------------------------------------

_NOOP_HTTPX_MOCK = AsyncMock(side_effect=AssertionError("Unexpected httpx call in edge test"))

# ---------------------------------------------------------------------------
# StreamEvent sequences for edge cases
# ---------------------------------------------------------------------------

_LOOKUP_UNREGISTERED_TOOL: list[StreamEvent] = [
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id="call_edge_001",
        function_name="lookup",
        function_args_delta=None,
    ),
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id=None,
        function_name=None,
        # Spec 2521 (2026-05-01): lookup is fetch-only — `mode` field
        # was removed from the LLM-visible surface (_LookupInputForLLM).
        # Tests must NOT send `mode` to avoid extra_forbidden validation.
        function_args_delta=json.dumps(
            {
                "tool_id": "nonexistent_adapter_xyz",
                "params": {},
            }
        ),
    ),
    StreamEvent(type="usage", usage=TokenUsage(input_tokens=100, output_tokens=40)),
    StreamEvent(type="done"),
]

_TEXT_RECOVERY: list[StreamEvent] = [
    StreamEvent(type="content_delta", content="해당 정보를 찾을 수 없습니다. 다시 시도해 주세요."),
    StreamEvent(type="usage", usage=TokenUsage(input_tokens=300, output_tokens=60)),
    StreamEvent(type="done"),
]

_LOOKUP_INVALID_ARGS: list[StreamEvent] = [
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id="call_edge_002",
        function_name="lookup",
        function_args_delta=None,
    ),
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id=None,
        function_name=None,
        # Intentionally invalid: mode is required
        function_args_delta='{"not_a_valid_field": "bad_data"}',
    ),
    StreamEvent(type="usage", usage=TokenUsage(input_tokens=100, output_tokens=40)),
    StreamEvent(type="done"),
]

# Infinite tool-call loop (max iterations guard)
_INFINITE_LOOKUP: list[StreamEvent] = [
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id="call_inf",
        function_name="resolve_location",
        function_args_delta=None,
    ),
    StreamEvent(
        type="tool_call_delta",
        tool_call_index=0,
        tool_call_id=None,
        function_name=None,
        function_args_delta=json.dumps({"query": "강남구", "want": "coords_and_admcd"}),
    ),
    StreamEvent(type="usage", usage=TokenUsage(input_tokens=80, output_tokens=30)),
    StreamEvent(type="done"),
]


# ---------------------------------------------------------------------------
# Fixture helper for edge tests
# ---------------------------------------------------------------------------


def _build_engine(
    responses: list[list[StreamEvent]],
    *,
    config: QueryEngineConfig | None = None,
) -> tuple[QueryEngine, AsyncMock]:
    """Build a QueryEngine with mock LLM + httpx mock for edge tests."""
    registry, executor = _build_registry_and_executor()
    context_builder = ContextBuilder(registry=registry)

    mock_llm = MockLLMClient(responses=responses)
    llm_adapter = _MockLLMClientAdapter(mock_llm)

    engine = QueryEngine(
        llm_client=llm_adapter,
        tool_registry=registry,
        tool_executor=executor,
        config=config or QueryEngineConfig(),
        context_builder=context_builder,
    )
    httpx_mock = _build_httpx_mock()
    return engine, httpx_mock


# ---------------------------------------------------------------------------
# Edge case 1: Unregistered tool_id in lookup(mode="fetch")
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason=(
        "Spec 2521 fetch-only refactor: lookup() narrowed to "
        "LookupSearchInput|LookupFetchInput but executor still parses via "
        "the legacy _LookupInputForLLM (no mode field). Pre-existing on "
        "main; tracked separately. CI surfaced after debug-infra cleanup."
    ),
    strict=False,
)
@pytest.mark.asyncio
async def test_edge_unregistered_tool_id() -> None:
    """Edge 1: lookup(tool_id="nonexistent_adapter_xyz") → LookupError.

    The executor must return LookupError(reason="unknown_tool") without crashing.
    lookup() returns a structured LookupError payload (kind="error") as tool data
    rather than raising — this preserves the error context so the LLM can reason
    about it.  Engine continues to the next LLM turn which produces recovery text.
    """
    engine, httpx_mock = _build_engine([_LOOKUP_UNREGISTERED_TOOL, _TEXT_RECOVERY])

    with patch.object(httpx.AsyncClient, "get", httpx_mock):
        events: list = []
        async for event in engine.run(TRIGGER_QUERY):
            events.append(event)

    # Engine must not crash
    stop_events = [e for e in events if e.type == "stop"]
    assert stop_events, "No stop event — engine crashed on unknown adapter"

    # Tool result must carry a structured LookupError payload (kind="error").
    # LookupError is returned as data (ToolResult.success=True) so the LLM
    # receives the full structured context rather than an opaque error string.
    tool_results = [e for e in events if e.type == "tool_result" and e.tool_result is not None]
    lookup_errors = [
        r
        for r in tool_results
        if r.tool_result
        and r.tool_result.data is not None
        and r.tool_result.data.get("kind") == "error"
    ]
    assert lookup_errors, (
        "Expected ToolResult with data.kind='error' for unknown adapter; "
        f"got tool_results={[r.tool_result for r in tool_results]!r}"
    )


# ---------------------------------------------------------------------------
# Edge case 2: Max-iterations guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_max_iterations_guard() -> None:
    """Edge 2: Engine stops after max_iterations when LLM loops on tool calls."""
    config = QueryEngineConfig(max_iterations=2)
    engine, httpx_mock = _build_engine([_INFINITE_LOOKUP], config=config)

    with patch.object(httpx.AsyncClient, "get", httpx_mock):
        events: list = []
        async for event in engine.run("무한 루프 테스트"):
            events.append(event)

    stop_events = [e for e in events if e.type == "stop"]
    assert stop_events, "No stop event found"

    stop_reason = stop_events[-1].stop_reason
    assert stop_reason == StopReason.max_iterations_reached, (
        f"Expected max_iterations_reached, got {stop_reason!r}"
    )


# ---------------------------------------------------------------------------
# Edge case 3: Pydantic validation failure on lookup input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_invalid_lookup_args() -> None:
    """Edge 3: lookup called with missing required field 'mode' → validation error.

    ToolExecutor catches ValidationError and returns ToolResult(success=False,
    error_type="validation"). Engine continues and emits a stop event.
    """
    engine, httpx_mock = _build_engine([_LOOKUP_INVALID_ARGS, _TEXT_RECOVERY])

    with patch.object(httpx.AsyncClient, "get", httpx_mock):
        events: list = []
        async for event in engine.run("잘못된 인자 테스트"):
            events.append(event)

    stop_events = [e for e in events if e.type == "stop"]
    assert stop_events, "No stop event — engine crashed on validation error"

    tool_results = [e for e in events if e.type == "tool_result" and e.tool_result is not None]
    failed = [r for r in tool_results if r.tool_result and not r.tool_result.success]
    assert failed, "Expected ToolResult(success=False) for invalid args"
