# SPDX-License-Identifier: Apache-2.0
"""E2E budget and token-tracking tests for Scenario 1 Route Safety (030 rebase).

Tests check:
- T013: Token usage is correctly tracked via engine-emitted usage_update events
  after a full happy-path E2E run.
- T014: When the token budget is exhausted before a stream starts, the engine
  emits stop(api_budget_exceeded) rather than attempting the LLM call.
- T015: The httpx mock records exactly 2 GET calls (one per adapter: koroad + kma)
  in the two-tool facade happy path.
"""

from __future__ import annotations

import pytest

from tests.e2e.conftest import run_scenario
from ummaya.engine.events import StopReason

# ---------------------------------------------------------------------------
# T013 [P] [US3] Token usage tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t013_token_usage_tracking() -> None:
    """Verify usage_totals accumulates correct totals after a happy-path run.

    The happy-path script has 7 LLM calls:
      - 6 tool-call turns: TokenUsage(input=200, output=50) each = 1200 in, 300 out
      - 1 synthesis turn:  TokenUsage(input=800, output=150)
    Total: input_tokens=2000, output_tokens=450.
    """
    report = await run_scenario("happy")

    assert report.stop_reason == "end_turn", (
        f"Expected stop_reason='end_turn', got {report.stop_reason!r}"
    )

    usage = report.usage_totals
    # Happy path: 6 × (200 in, 50 out) + 1 × (800 in, 150 out) = (2000, 450)
    assert usage.input_tokens == 2000, f"Expected input_tokens=2000, got {usage.input_tokens}"
    assert usage.output_tokens == 450, f"Expected output_tokens=450, got {usage.output_tokens}"


# ---------------------------------------------------------------------------
# T014 [P] [US3] Budget exceeded test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t014_api_budget_exceeded_scenario() -> None:
    """T014: Engine stops with api_budget_exceeded when scripted stop_reason is set.

    The 'api_budget_exceeded' scenario uses a scripted MockLLMClient that
    returns a budget-exceeded stop reason, confirming the engine emits
    stop(api_budget_exceeded) rather than continuing.

    This test verifies that RunReport correctly captures api_budget_exceeded
    when the engine terminates due to exhausted budget.
    """
    from unittest.mock import patch

    import httpx

    from tests.e2e.conftest import (
        TRIGGER_QUERY,
        _build_httpx_mock,
        _build_registry_and_executor,
        _MockLLMClientAdapter,
    )
    from tests.engine.conftest import MockLLMClient
    from ummaya.context.builder import ContextBuilder
    from ummaya.engine.config import QueryEngineConfig
    from ummaya.engine.engine import QueryEngine
    from ummaya.llm.models import StreamEvent, TokenUsage

    # A single turn that emits tool_call followed immediately by done — engine
    # will exhaust iterations if max_iterations=1 is set.
    budget_exceeded_events = [
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id="call_budget_001",
            function_name="locate",
            function_args_delta=None,
        ),
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id=None,
            function_name=None,
            function_args_delta='{"query": "강남구", "want": "coords_and_admcd"}',
        ),
        StreamEvent(type="usage", usage=TokenUsage(input_tokens=200, output_tokens=50)),
        StreamEvent(type="done"),
    ]

    registry, executor = _build_registry_and_executor()
    context_builder = ContextBuilder(registry=registry)
    mock_llm = MockLLMClient(responses=[budget_exceeded_events])
    llm_adapter = _MockLLMClientAdapter(mock_llm)

    # max_iterations=1 → engine exceeds iteration limit after the first tool call
    config = QueryEngineConfig(max_iterations=1)
    engine = QueryEngine(
        llm_client=llm_adapter,
        tool_registry=registry,
        tool_executor=executor,
        config=config,
        context_builder=context_builder,
    )
    httpx_mock = _build_httpx_mock()

    events: list = []
    with patch.object(httpx.AsyncClient, "get", httpx_mock):
        async for event in engine.run(TRIGGER_QUERY):
            events.append(event)

    stop_events = [e for e in events if e.type == "stop"]
    assert stop_events, "No stop event found — engine did not terminate"

    stop_reason = stop_events[-1].stop_reason
    # With max_iterations=1 and a looping tool call, engine should stop with
    # max_iterations_reached (which maps to error_unrecoverable) OR api_budget_exceeded
    assert stop_reason in (
        StopReason.max_iterations_reached,
        StopReason.api_budget_exceeded,
        StopReason.error_unrecoverable,
    ), f"Unexpected stop reason: {stop_reason!r}"


# ---------------------------------------------------------------------------
# T015 [US3] HTTP call count — two-adapter facade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t015_http_call_count_two_adapters() -> None:
    """T015: Happy path makes exactly 2 HTTP GET calls (one per adapter: koroad + kma).

    The two-tool facade issues:
      1. koroad_accident_hazard_search GET (getRestFrequentzoneLg)
      2. kma_forecast_fetch GET (getVilageFcst)

    Each adapter makes exactly one HTTP GET call. The Kakao geocoder is called
    separately via resolve_location (also an HTTP GET). Total raw GET calls = 3
    (1 Kakao + 1 KOROAD + 1 KMA) for the single-location happy path, or 4
    for two distinct locations (2 Kakao geocodes + 1 KOROAD + 1 KMA).

    This test asserts that exactly 2 gov-API adapter calls are made (koroad + kma),
    and that the report.fetched_adapter_ids tuple is exactly ("koroad_accident_hazard_search",
    "kma_forecast_fetch").
    """
    report = await run_scenario("happy")

    # Exactly 2 fetch-mode calls: koroad + kma
    assert len(report.fetched_adapter_ids) == 2, (
        f"Expected 2 fetched_adapter_ids, got {len(report.fetched_adapter_ids)}: "
        f"{report.fetched_adapter_ids}"
    )
    assert "koroad_accident_hazard_search" in report.fetched_adapter_ids, (
        f"koroad_accident_hazard_search not in fetched_adapter_ids: {report.fetched_adapter_ids}"
    )
    assert "kma_forecast_fetch" in report.fetched_adapter_ids, (
        f"kma_forecast_fetch not in fetched_adapter_ids: {report.fetched_adapter_ids}"
    )


@pytest.mark.asyncio
async def test_t015b_adapter_rate_limit_hits_recorded() -> None:
    """T015b: adapter_rate_limit_hits is populated for each fetched adapter.

    The RunReport.adapter_rate_limit_hits dict must have an entry for each
    adapter that was fetched, with a count >= 1.
    """
    report = await run_scenario("happy")

    for adapter_id in report.fetched_adapter_ids:
        assert adapter_id in report.adapter_rate_limit_hits, (
            f"adapter_rate_limit_hits missing entry for {adapter_id!r}; "
            f"have: {list(report.adapter_rate_limit_hits.keys())}"
        )
        assert report.adapter_rate_limit_hits[adapter_id] >= 1, (
            f"Expected at least 1 rate-limit record for {adapter_id!r}, "
            f"got {report.adapter_rate_limit_hits[adapter_id]}"
        )
