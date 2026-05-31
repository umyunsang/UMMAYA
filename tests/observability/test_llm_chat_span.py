# SPDX-License-Identifier: Apache-2.0
"""T021 — Tests for the 'chat' span usage aggregation written by LLMClient.stream().

Verifies:
- Exactly one 'chat' span is exported per stream() call.
- All 4 T019 usage attributes are present and correct on the span:
    gen_ai.usage.input_tokens, gen_ai.usage.output_tokens,
    gen_ai.response.model, gen_ai.response.finish_reasons.
- Write-once invariant: set_attributes() is called exactly once for the 4 usage
  keys (via a spy wrapper on the span object produced by the test tracer).
- Values match the mock's final usage totals.

Strategy:
- Monkeypatch the module-level ``_tracer`` in ``ummaya.llm.client`` to use a
  dedicated TracerProvider backed by an InMemorySpanExporter, following the
  proven pattern from test_tool_execute_span.py.
- Patch ``LLMClient._stream_with_retry`` to yield a controlled sequence of
  StreamEvent objects and populate ``_finalize`` deterministically.  This avoids
  any live HTTP traffic and keeps the test under 2 seconds.
- A spy wrapper around the real span's ``set_attributes`` method counts how many
  times each of the 4 usage keys is written, asserting write-once semantics.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ummaya.llm.models import ChatMessage, StreamEvent, TokenUsage
from ummaya.observability.semconv import (
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
)

# Usage-attribute keys we track for write-once assertions.
_USAGE_KEYS = frozenset(
    [
        GEN_AI_USAGE_INPUT_TOKENS,
        GEN_AI_USAGE_OUTPUT_TOKENS,
        GEN_AI_RESPONSE_MODEL,
        GEN_AI_RESPONSE_FINISH_REASONS,
    ]
)

# Minimal valid env so LLMClientConfig loads without touching the network.
_FAKE_ENV = {"UMMAYA_FRIENDLI_TOKEN": "test-token-for-unit-tests"}


# ---------------------------------------------------------------------------
# Fixture: per-test InMemorySpanExporter with _tracer monkeypatch
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem_exporter(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    """Patch _tracer in ummaya.llm.client with a dedicated test TracerProvider."""
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    import ummaya.llm.client as client_mod

    monkeypatch.setattr(client_mod, "_tracer", provider.get_tracer("ummaya.llm.client"))
    exporter.clear()
    return exporter


# ---------------------------------------------------------------------------
# Helper: build a minimal LLMClient (no real HTTP)
# ---------------------------------------------------------------------------


def _make_client() -> Any:
    """Create an LLMClient with fake env vars (no network calls)."""
    from ummaya.llm.client import LLMClient
    from ummaya.llm.config import LLMClientConfig

    with patch.dict(os.environ, _FAKE_ENV):
        config = LLMClientConfig()

    return LLMClient(config=config)


# ---------------------------------------------------------------------------
# Helper: mock _stream_with_retry factory
# ---------------------------------------------------------------------------


def _make_mock_stream_with_retry(
    *,
    input_tokens: int,
    output_tokens: int,
    response_model: str,
    finish_reasons: list[str],
    extra_events: list[StreamEvent] | None = None,
) -> Any:
    """Return a coroutine function that replaces _stream_with_retry.

    It yields ``extra_events`` (defaults to a single content_delta) and then
    populates ``_finalize`` to simulate a clean EOF, exactly as the real
    implementation does.
    """

    async def _fake(
        self: Any,
        payload: dict[str, object],
        _finalize: dict[str, object],
        *,
        allow_reasoning: bool,
    ) -> AsyncIterator[StreamEvent]:
        del allow_reasoning
        events = extra_events or [
            StreamEvent(type="content_delta", content="Hello world."),
            StreamEvent(
                type="usage",
                usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            ),
        ]
        for event in events:
            # Debit usage into the tracker so input/output_tokens_used are updated.
            if event.type == "usage" and event.usage is not None:
                self._usage.debit(event.usage)
            yield event

        # Populate _finalize exactly as _stream_with_retry does on clean EOF.
        _finalize["input_tokens"] = self._usage.input_tokens_used
        _finalize["output_tokens"] = self._usage.output_tokens_used
        _finalize["response_model"] = response_model
        _finalize["finish_reasons"] = sorted(finish_reasons)

    return _fake


# ---------------------------------------------------------------------------
# Spy: wrap span.set_attributes to count writes per key
# ---------------------------------------------------------------------------


class _SetAttributesSpy:
    """Wraps a span's set_attributes to count per-key calls."""

    def __init__(self, span: Any) -> None:
        self._span = span
        self.call_count: dict[str, int] = defaultdict(int)
        self._original = span.set_attributes

    def __call__(self, attributes: dict[str, Any]) -> None:
        for key in attributes:
            self.call_count[key] += 1
        self._original(attributes)

    def install(self) -> None:
        self._span.set_attributes = self  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# T021-A: Success path with finish_reason='stop'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_span_stop_finish_reason(
    mem_exporter: InMemorySpanExporter,
) -> None:
    """stream() with finish_reason='stop' must produce exactly one 'chat' span
    with all 4 usage attributes set exactly once, values matching the mock totals."""
    INPUT_TOKENS = 42  # noqa: N806
    OUTPUT_TOKENS = 17  # noqa: N806
    RESPONSE_MODEL = "LGAI-EXAONE/K-EXAONE-236B-A23B"  # noqa: N806
    FINISH_REASONS = ["stop"]  # noqa: N806

    client = _make_client()

    mock_fn = _make_mock_stream_with_retry(
        input_tokens=INPUT_TOKENS,
        output_tokens=OUTPUT_TOKENS,
        response_model=RESPONSE_MODEL,
        finish_reasons=FINISH_REASONS,
    )

    # Install spy BEFORE stream() is called so the span is captured.
    # We inject the spy via a custom start_span wrapper that instruments the span
    # after _tracer.start_span("chat") creates it.
    import ummaya.llm.client as client_mod

    original_start_span = client_mod._tracer.start_span  # type: ignore[attr-defined]
    captured_spies: list[_SetAttributesSpy] = []

    def _spy_start_span(name: str, **kwargs: Any) -> Any:
        span = original_start_span(name, **kwargs)
        if name == "chat":
            spy = _SetAttributesSpy(span)
            spy.install()
            captured_spies.append(spy)
        return span

    client_mod._tracer.start_span = _spy_start_span  # type: ignore[method-assign]

    try:
        with patch.object(type(client), "_stream_with_retry", mock_fn):
            messages = [ChatMessage(role="user", content="test query")]
            events: list[StreamEvent] = []
            async for event in client.stream(messages):
                events.append(event)
    finally:
        # Restore original start_span regardless of test outcome.
        client_mod._tracer.start_span = original_start_span  # type: ignore[method-assign]

    # --- Assert: exactly one 'chat' span exported ---
    spans = mem_exporter.get_finished_spans()
    chat_spans = [s for s in spans if s.name == "chat"]
    assert len(chat_spans) == 1, (
        f"Expected exactly 1 'chat' span, got {len(chat_spans)}. "
        f"All spans: {[s.name for s in spans]}"
    )
    span = chat_spans[0]
    attrs = dict(span.attributes or {})

    # --- Assert: all 4 usage attributes present and correct ---
    assert GEN_AI_USAGE_INPUT_TOKENS in attrs, (
        f"{GEN_AI_USAGE_INPUT_TOKENS!r} missing. attrs={attrs}"
    )
    assert GEN_AI_USAGE_OUTPUT_TOKENS in attrs, (
        f"{GEN_AI_USAGE_OUTPUT_TOKENS!r} missing. attrs={attrs}"
    )
    assert GEN_AI_RESPONSE_MODEL in attrs, f"{GEN_AI_RESPONSE_MODEL!r} missing. attrs={attrs}"
    assert GEN_AI_RESPONSE_FINISH_REASONS in attrs, (
        f"{GEN_AI_RESPONSE_FINISH_REASONS!r} missing. attrs={attrs}"
    )

    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == INPUT_TOKENS, (
        f"input_tokens mismatch: expected {INPUT_TOKENS}, got {attrs[GEN_AI_USAGE_INPUT_TOKENS]}"
    )
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == OUTPUT_TOKENS, (
        f"output_tokens mismatch: expected {OUTPUT_TOKENS}, got {attrs[GEN_AI_USAGE_OUTPUT_TOKENS]}"
    )
    assert attrs[GEN_AI_RESPONSE_MODEL] == RESPONSE_MODEL, (
        f"response_model mismatch: expected {RESPONSE_MODEL!r}, "
        f"got {attrs[GEN_AI_RESPONSE_MODEL]!r}"
    )
    # OTel SDK serialises list attrs as tuples.
    assert list(attrs[GEN_AI_RESPONSE_FINISH_REASONS]) == FINISH_REASONS, (
        f"finish_reasons mismatch: expected {FINISH_REASONS}, "
        f"got {list(attrs[GEN_AI_RESPONSE_FINISH_REASONS])}"
    )

    # --- Assert: write-once invariant via spy ---
    assert len(captured_spies) == 1, "Expected spy to be installed on exactly one chat span"
    spy = captured_spies[0]
    for key in _USAGE_KEYS:
        count = spy.call_count.get(key, 0)
        assert count == 1, (
            f"Expected usage key {key!r} to be written exactly once, was written {count} times"
        )


# ---------------------------------------------------------------------------
# T021-B: finish_reason='tool_calls'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_span_tool_calls_finish_reason(
    mem_exporter: InMemorySpanExporter,
) -> None:
    """stream() with finish_reason='tool_calls' must export a 'chat' span with
    finish_reasons=['tool_calls'] and correct token counts."""
    INPUT_TOKENS = 100  # noqa: N806
    OUTPUT_TOKENS = 30  # noqa: N806
    RESPONSE_MODEL = "LGAI-EXAONE/K-EXAONE-236B-A23B"  # noqa: N806
    FINISH_REASONS = ["tool_calls"]  # noqa: N806

    client = _make_client()

    extra_events = [
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id="call-xyz",
            function_name="search_traffic",
            function_args_delta='{"road_id": "1"}',
        ),
        StreamEvent(
            type="usage",
            usage=TokenUsage(input_tokens=INPUT_TOKENS, output_tokens=OUTPUT_TOKENS),
        ),
    ]

    mock_fn = _make_mock_stream_with_retry(
        input_tokens=INPUT_TOKENS,
        output_tokens=OUTPUT_TOKENS,
        response_model=RESPONSE_MODEL,
        finish_reasons=FINISH_REASONS,
        extra_events=extra_events,
    )

    with patch.object(type(client), "_stream_with_retry", mock_fn):
        messages = [ChatMessage(role="user", content="경부고속도로 혼잡 상황 알려줘")]
        events: list[StreamEvent] = []
        async for event in client.stream(messages):
            events.append(event)

    # --- Assert: exactly one 'chat' span ---
    spans = mem_exporter.get_finished_spans()
    chat_spans = [s for s in spans if s.name == "chat"]
    assert len(chat_spans) == 1, (
        f"Expected exactly 1 'chat' span, got {len(chat_spans)}. "
        f"All spans: {[s.name for s in spans]}"
    )
    span = chat_spans[0]
    attrs = dict(span.attributes or {})

    # --- Assert: finish_reasons=['tool_calls'] ---
    assert list(attrs[GEN_AI_RESPONSE_FINISH_REASONS]) == FINISH_REASONS, (
        f"finish_reasons mismatch: expected {FINISH_REASONS}, "
        f"got {list(attrs[GEN_AI_RESPONSE_FINISH_REASONS])}"
    )

    # --- Assert: token counts ---
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == INPUT_TOKENS, (
        f"input_tokens mismatch: expected {INPUT_TOKENS}, got {attrs[GEN_AI_USAGE_INPUT_TOKENS]}"
    )
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == OUTPUT_TOKENS, (
        f"output_tokens mismatch: expected {OUTPUT_TOKENS}, got {attrs[GEN_AI_USAGE_OUTPUT_TOKENS]}"
    )

    # --- Assert: a tool_call_delta event was emitted ---
    tool_events = [e for e in events if e.type == "tool_call_delta"]
    assert len(tool_events) == 1, f"Expected 1 tool_call_delta event, got {len(tool_events)}"
    assert tool_events[0].function_name == "search_traffic"


@pytest.mark.asyncio
async def test_stream_close_from_other_task_does_not_detach_otel_context(
    caplog: pytest.LogCaptureFixture,
    mem_exporter: InMemorySpanExporter,
) -> None:
    """Closing a partially consumed stream from another task must not log OTel
    context detach errors.

    The TUI stops reading the model stream as soon as a tool call is ready, then
    drives the next agentic step. That closes this async generator across a
    yield boundary, so the chat span cannot keep an active OTel context manager
    alive while control is in the caller.
    """

    client = _make_client()

    async def _fake(
        self: Any,
        payload: dict[str, object],
        _finalize: dict[str, object],
        *,
        allow_reasoning: bool,
    ) -> AsyncIterator[StreamEvent]:
        del allow_reasoning
        yield StreamEvent(type="content_delta", content="partial")
        _finalize["input_tokens"] = 1
        _finalize["output_tokens"] = 1
        _finalize["response_model"] = "LGAI-EXAONE/K-EXAONE-236B-A23B"
        _finalize["finish_reasons"] = ["stop"]

    caplog.set_level(logging.ERROR, logger="opentelemetry.context")

    with patch.object(type(client), "_stream_with_retry", _fake):
        stream = client.stream([ChatMessage(role="user", content="test query")])
        event = await stream.__anext__()
        assert event.type == "content_delta"
        await asyncio.create_task(stream.aclose())

    assert not [
        record
        for record in caplog.records
        if record.name == "opentelemetry.context"
        and "Failed to detach context" in record.getMessage()
    ]

    spans = mem_exporter.get_finished_spans()
    assert [span.name for span in spans].count("chat") == 1
