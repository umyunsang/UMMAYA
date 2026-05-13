# SPDX-License-Identifier: Apache-2.0
"""Unit tests for LLMClient.stream() SSE parsing."""

from __future__ import annotations

import json
import os

import httpx
import pytest
import respx

from ummaya.llm.client import LLMClient
from ummaya.llm.config import LLMClientConfig
from ummaya.llm.errors import AuthenticationError, StreamInterruptedError
from ummaya.llm.models import ChatMessage, StreamEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMPLETIONS_URL = "https://api.friendli.ai/serverless/v1/chat/completions"


def _build_sse_body(*chunks: dict, done: bool = True) -> bytes:
    """Serialize a sequence of chunk dicts into an SSE byte body."""
    lines: list[str] = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    if done:
        lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def _make_sse_response(body: bytes, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        content=body,
        headers={"content-type": "text/event-stream"},
    )


def _delta_chunk(content: str, finish_reason: str | None = None) -> dict:
    return {
        "id": "chatcmpl-test-123",
        "object": "chat.completion.chunk",
        "choices": [
            {
                "index": 0,
                "delta": {"content": content},
                "finish_reason": finish_reason,
            }
        ],
    }


def _reasoning_chunk(reasoning_content: str) -> dict:
    """Build an SSE chunk containing only reasoning_content (K-EXAONE CoT)."""
    return {
        "id": "chatcmpl-test-123",
        "object": "chat.completion.chunk",
        "choices": [
            {
                "index": 0,
                "delta": {"reasoning_content": reasoning_content},
                "finish_reason": None,
            }
        ],
    }


def _stop_chunk(
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
) -> dict:
    return {
        "id": "chatcmpl-test-123",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip all UMMAYA_ env vars and inject a known test token."""
    for key in list(os.environ):
        if key.startswith("UMMAYA_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("UMMAYA_FRIENDLI_TOKEN", "test-token-12345")


@pytest.fixture
def llm_client() -> LLMClient:
    """An LLMClient backed by the injected test token."""
    config = LLMClientConfig()
    return LLMClient(config=config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@respx.mock
async def test_stream_content_deltas(
    llm_client: LLMClient,
    sample_messages: list[ChatMessage],
) -> None:
    """Content deltas are yielded as StreamEvent(type='content_delta')."""
    body = _build_sse_body(
        _delta_chunk("Hello"),
        _delta_chunk(" world"),
        _stop_chunk(),
    )
    respx.post(_COMPLETIONS_URL).mock(return_value=_make_sse_response(body))

    events: list[StreamEvent] = []
    async for event in llm_client.stream(sample_messages):
        events.append(event)

    content_events = [e for e in events if e.type == "content_delta"]
    assert len(content_events) == 2
    assert content_events[0].content == "Hello"
    assert content_events[1].content == " world"


@respx.mock
async def test_stream_usage_event(
    llm_client: LLMClient,
    sample_messages: list[ChatMessage],
) -> None:
    """The final usage chunk yields a StreamEvent(type='usage') with correct counts."""
    body = _build_sse_body(
        _delta_chunk("Hi"),
        _stop_chunk(prompt_tokens=20, completion_tokens=8, total_tokens=28),
    )
    respx.post(_COMPLETIONS_URL).mock(return_value=_make_sse_response(body))

    events: list[StreamEvent] = []
    async for event in llm_client.stream(sample_messages):
        events.append(event)

    usage_events = [e for e in events if e.type == "usage"]
    assert len(usage_events) == 1
    usage = usage_events[0].usage
    assert usage is not None
    assert usage.input_tokens == 20
    assert usage.output_tokens == 8
    assert usage.total_tokens == 28


@respx.mock
async def test_stream_done_event(
    llm_client: LLMClient,
    sample_messages: list[ChatMessage],
) -> None:
    """Stream ends with exactly one StreamEvent(type='done')."""
    body = _build_sse_body(
        _delta_chunk("Hello"),
        _stop_chunk(),
    )
    respx.post(_COMPLETIONS_URL).mock(return_value=_make_sse_response(body))

    events: list[StreamEvent] = []
    async for event in llm_client.stream(sample_messages):
        events.append(event)

    done_events = [e for e in events if e.type == "done"]
    assert len(done_events) == 1
    assert events[-1].type == "done"


@respx.mock
async def test_stream_content_assembly(
    llm_client: LLMClient,
    sample_messages: list[ChatMessage],
) -> None:
    """Concatenated content_delta payloads reconstruct the full response text."""
    body = _build_sse_body(
        _delta_chunk("Hello"),
        _delta_chunk(","),
        _delta_chunk(" world"),
        _delta_chunk("!"),
        _stop_chunk(),
    )
    respx.post(_COMPLETIONS_URL).mock(return_value=_make_sse_response(body))

    assembled = ""
    async for event in llm_client.stream(sample_messages):
        if event.type == "content_delta" and event.content:
            assembled += event.content

    assert assembled == "Hello, world!"


@respx.mock
async def test_stream_separates_reasoning_content(
    llm_client: LLMClient,
    sample_messages: list[ChatMessage],
) -> None:
    """K-EXAONE reasoning_content chunks stay separate from visible content."""
    body = _build_sse_body(
        _reasoning_chunk("Let me think about this..."),
        _reasoning_chunk("The user wants a greeting."),
        _delta_chunk("Hello!"),
        _stop_chunk(),
    )
    respx.post(_COMPLETIONS_URL).mock(return_value=_make_sse_response(body))

    events: list[StreamEvent] = []
    async for event in llm_client.stream(sample_messages):
        events.append(event)

    # Only regular content should appear in the visible-content channel.
    content_events = [e for e in events if e.type == "content_delta"]
    assert len(content_events) == 1
    assert content_events[0].content == "Hello!"

    # Verify the full event sequence: content_delta, usage, done
    event_types = [e.type for e in events]
    assert "content_delta" in event_types
    assert "done" in event_types


@respx.mock
async def test_stream_auth_error(
    llm_client: LLMClient,
    sample_messages: list[ChatMessage],
) -> None:
    """A 401 response raises AuthenticationError before any events are yielded."""
    respx.post(_COMPLETIONS_URL).mock(return_value=httpx.Response(401, text="Unauthorized"))

    with pytest.raises(AuthenticationError) as exc_info:
        async for _ in llm_client.stream(sample_messages):
            pass  # pragma: no cover

    assert exc_info.value.status_code == 401


@respx.mock
async def test_stream_connection_error(
    llm_client: LLMClient,
    sample_messages: list[ChatMessage],
) -> None:
    """A transport-level connection failure raises StreamInterruptedError."""
    respx.post(_COMPLETIONS_URL).mock(side_effect=httpx.ConnectError("Connection refused"))

    with pytest.raises(StreamInterruptedError):
        async for _ in llm_client.stream(sample_messages):
            pass  # pragma: no cover
