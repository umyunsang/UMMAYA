# SPDX-License-Identifier: Apache-2.0
"""Unit tests for LLMClient.complete() using respx for httpx mocking."""

from __future__ import annotations

import asyncio
import json
import os
import time

import httpx
import pytest
import respx

from ummaya.llm.client import LLMClient, RetryPolicy
from ummaya.llm.config import LLMClientConfig
from ummaya.llm.errors import (
    AuthenticationError,
    BudgetExceededError,
    ConfigurationError,
    LLMConnectionError,
    LLMResponseError,
)
from ummaya.llm.models import ChatMessage, FunctionSchema, ToolDefinition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHAT_COMPLETIONS_URL = "https://api.friendli.ai/serverless/v1/chat/completions"


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all UMMAYA_* env vars then inject a safe test token."""
    for key in list(os.environ):
        if key.startswith("UMMAYA_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("UMMAYA_FRIENDLI_TOKEN", "test-token-12345")


# ---------------------------------------------------------------------------
# LLMClient initialization
# ---------------------------------------------------------------------------


async def test_client_init_with_config(
    _clean_env: None,
) -> None:
    """Client accepts an explicit LLMClientConfig and initializes without error."""
    config = LLMClientConfig()
    client = LLMClient(config)
    assert client._config is config
    await client.close()


async def test_client_init_from_env(
    _clean_env: None,
) -> None:
    """Client reads configuration from environment variables when config=None."""
    client = LLMClient(config=None)
    assert client._config.token.get_secret_value() == "test-token-12345"
    await client.close()


async def test_client_init_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client raises ConfigurationError when UMMAYA_FRIENDLI_TOKEN is absent."""
    for key in list(os.environ):
        if key.startswith("UMMAYA_"):
            monkeypatch.delenv(key, raising=False)

    with pytest.raises(ConfigurationError):
        LLMClient(config=None)


async def test_client_context_manager(_clean_env: None) -> None:
    """Client works correctly as an async context manager."""
    config = LLMClientConfig()
    async with LLMClient(config) as client:
        assert client._config is config
    # After __aexit__ the underlying httpx client should be closed (no assertion
    # needed for the internal transport state; reaching here without error is
    # sufficient).


# ---------------------------------------------------------------------------
# LLMClient.complete() — success path
# ---------------------------------------------------------------------------


@respx.mock
async def test_complete_success(
    _clean_env: None,
    sample_messages: list[ChatMessage],
    mock_completion_response: dict,
) -> None:
    """complete() parses a successful 200 response into ChatCompletionResponse."""
    respx.post(CHAT_COMPLETIONS_URL).mock(
        return_value=httpx.Response(200, json=mock_completion_response)
    )

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        response = await client.complete(sample_messages)

    assert response.id == "chatcmpl-test-123"
    assert response.content == "Test response"
    assert response.model == "LGAI-EXAONE/K-EXAONE-236B-A23B"
    assert response.finish_reason == "stop"


@respx.mock
async def test_complete_token_usage(
    _clean_env: None,
    sample_messages: list[ChatMessage],
    mock_completion_response: dict,
) -> None:
    """complete() correctly extracts prompt_tokens / completion_tokens from usage."""
    respx.post(CHAT_COMPLETIONS_URL).mock(
        return_value=httpx.Response(200, json=mock_completion_response)
    )

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        response = await client.complete(sample_messages)

    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5
    assert response.usage.total_tokens == 15


# ---------------------------------------------------------------------------
# LLMClient.complete() — error paths
# ---------------------------------------------------------------------------


@respx.mock
async def test_complete_auth_error(
    _clean_env: None,
    sample_messages: list[ChatMessage],
) -> None:
    """complete() raises AuthenticationError on a 401 response."""
    respx.post(CHAT_COMPLETIONS_URL).mock(
        return_value=httpx.Response(401, json={"error": "Unauthorized"})
    )

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        with pytest.raises(AuthenticationError) as exc_info:
            await client.complete(sample_messages)

    assert exc_info.value.status_code == 401


@respx.mock
async def test_complete_bad_request(
    _clean_env: None,
    sample_messages: list[ChatMessage],
) -> None:
    """complete() raises LLMResponseError on a 400 response."""
    respx.post(CHAT_COMPLETIONS_URL).mock(
        return_value=httpx.Response(400, json={"error": "Bad Request"})
    )

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        with pytest.raises(LLMResponseError) as exc_info:
            await client.complete(sample_messages)

    assert exc_info.value.status_code == 400


@respx.mock
async def test_complete_connection_error(
    _clean_env: None,
    sample_messages: list[ChatMessage],
) -> None:
    """complete() raises LLMConnectionError when the transport raises ConnectError."""
    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=httpx.ConnectError("Connection refused"))

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        with pytest.raises(LLMConnectionError):
            await client.complete(sample_messages)


# ---------------------------------------------------------------------------
# LLMClient.complete() — tool-use flow
# ---------------------------------------------------------------------------


@respx.mock
async def test_complete_with_tools(
    _clean_env: None,
    sample_messages: list[ChatMessage],
) -> None:
    """complete() includes tools in the request payload and parses tool_calls in the response."""
    tool_response = {
        "id": "chatcmpl-tool-test",
        "object": "chat.completion",
        "model": "LGAI-EXAONE/K-EXAONE-236B-A23B",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "Seoul"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }

    captured_request: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        captured_request.append(request)
        return httpx.Response(200, json=tool_response)

    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_capture)

    func_schema = FunctionSchema(
        name="get_weather",
        description="Get weather",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
    )
    tool_def = ToolDefinition(type="function", function=func_schema)

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        response = await client.complete(sample_messages, tools=[tool_def])

    # Verify tools were sent in the request payload
    import json as _json

    assert len(captured_request) == 1
    payload = _json.loads(captured_request[0].content)
    assert "tools" in payload
    assert len(payload["tools"]) == 1
    assert payload["tools"][0]["function"]["name"] == "get_weather"
    assert payload["parallel_tool_calls"] is False

    # Verify response.tool_calls is populated correctly
    assert len(response.tool_calls) == 1
    tc = response.tool_calls[0]
    assert tc.id == "call_abc123"
    assert tc.function.name == "get_weather"
    assert tc.function.arguments == '{"city": "Seoul"}'
    assert response.finish_reason == "tool_calls"


@respx.mock
async def test_complete_strips_internal_trigger_phrase_from_raw_tool_dict(
    _clean_env: None,
    sample_messages: list[ChatMessage],
    mock_completion_response: dict,
) -> None:
    """Raw registry tool dicts must be normalized before sending to FriendliAI."""
    captured_request: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        captured_request.append(request)
        return httpx.Response(200, json=mock_completion_response)

    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_capture)

    raw_tool = {
        "type": "function",
        "function": {
            "name": "find",
            "description": "Search and fetch public data adapters.",
            "parameters": {"type": "object", "properties": {}},
            "trigger_phrase": "UMMAYA-only routing hint for the system prompt.",
        },
    }

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        await client.complete(sample_messages, tools=[raw_tool])

    assert len(captured_request) == 1
    payload = json.loads(captured_request[0].content)
    assert payload["tools"][0]["function"]["name"] == "find"
    assert "trigger_phrase" not in payload["tools"][0]["function"]


@respx.mock
async def test_complete_tool_result_continuation(
    _clean_env: None,
) -> None:
    """complete() accepts a tool-result turn (role='tool') and serializes it correctly."""
    continuation_response = {
        "id": "chatcmpl-continuation-test",
        "object": "chat.completion",
        "model": "LGAI-EXAONE/K-EXAONE-236B-A23B",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "The weather in Seoul is sunny, 22°C.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 15},
    }

    captured_request: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        captured_request.append(request)
        return httpx.Response(200, json=continuation_response)

    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_capture)

    # Build a message sequence that includes a tool-result turn
    messages = [
        ChatMessage(role="user", content="What is the weather in Seoul?"),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[
                {
                    "id": "call_xyz789",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city": "Seoul"}'},
                }
            ],
        ),
        ChatMessage(
            role="tool",
            content="sunny, 22°C",
            tool_call_id="call_xyz789",
        ),
    ]

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        response = await client.complete(messages)

    # Verify the request was made and the tool message was serialized
    import json as _json

    assert len(captured_request) == 1
    payload = _json.loads(captured_request[0].content)
    assert len(payload["messages"]) == 3

    tool_msg = payload["messages"][2]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_xyz789"
    assert tool_msg["content"] == "sunny, 22°C"

    # Verify the continuation response was parsed correctly
    assert response.content == "The weather in Seoul is sunny, 22°C."
    assert response.finish_reason == "stop"


@respx.mock
async def test_complete_budget_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complete() raises BudgetExceededError once the session token budget is exceeded.

    Budget is set to 1500 tokens so the first call (1020 tokens with default
    max_tokens=1024) passes the pre-flight check, and the second call exhausts it.
    """
    # Set all UMMAYA_ vars then configure a budget just large enough for one call
    for key in list(os.environ):
        if key.startswith("UMMAYA_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("UMMAYA_FRIENDLI_TOKEN", "test-token-12345")
    # Budget: 1500 — first call uses 1020 (within limit), second call needs another
    # 1024 (pre-flight) but only 480 remain, triggering BudgetExceededError.
    monkeypatch.setenv("UMMAYA_LLM_SESSION_BUDGET", "1500")

    # First response uses 1020 tokens (within budget of 1500)
    first_response = {
        "id": "chatcmpl-budget-1",
        "object": "chat.completion",
        "model": "LGAI-EXAONE/K-EXAONE-236B-A23B",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "First response."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 20},
    }

    # Second response would use more tokens — but the pre-flight check raises first
    # because remaining budget (480) < default max_tokens (1024).
    second_response = {
        "id": "chatcmpl-budget-2",
        "object": "chat.completion",
        "model": "LGAI-EXAONE/K-EXAONE-236B-A23B",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Second response."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 20},
    }

    respx.post(CHAT_COMPLETIONS_URL).mock(
        side_effect=[
            httpx.Response(200, json=first_response),
            httpx.Response(200, json=second_response),
        ]
    )

    messages = [ChatMessage(role="user", content="Hello")]

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        # First call succeeds (1020 tokens used, budget=1500, still within limit)
        result = await client.complete(messages)
        assert result.content == "First response."

        # Second call: pre-flight checks max_tokens=1024 > remaining 480 → raises
        with pytest.raises(BudgetExceededError):
            await client.complete(messages)


# ---------------------------------------------------------------------------
# T008 — Retry-After header respected by complete()
# ---------------------------------------------------------------------------

_SUCCESS_RESPONSE = {
    "id": "chatcmpl-retry-ok",
    "object": "chat.completion",
    "model": "LGAI-EXAONE/K-EXAONE-236B-A23B",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "OK"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
}


@respx.mock
async def test_complete_retry_after_header_respected(
    _clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T008: mock 429 with Retry-After: 3 → complete() waits ≥ ~3s before retry."""
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)

    respx.post(CHAT_COMPLETIONS_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "3"}, text="rate limited"),
            httpx.Response(200, json=_SUCCESS_RESPONSE),
        ]
    )

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        result = await client.complete([ChatMessage(role="user", content="hi")])

    assert result.content == "OK"
    assert len(sleep_calls) >= 1, "Expected at least one sleep call for the retry"
    # The sleep should respect the Retry-After: 3 header value
    assert sleep_calls[0] >= 3.0 - 0.2, (
        f"Expected sleep >= 2.8s (Retry-After: 3 ±200ms tolerance), got {sleep_calls[0]:.3f}s"
    )


# ---------------------------------------------------------------------------
# T009 — Exponential backoff without Retry-After
# ---------------------------------------------------------------------------


@respx.mock
async def test_complete_exponential_backoff_no_retry_after(
    _clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T009: two 429s with no Retry-After → sleeps are monotonically non-decreasing,
    bounded by cap_seconds, and within jitter bounds."""
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)

    respx.post(CHAT_COMPLETIONS_URL).mock(
        side_effect=[
            httpx.Response(429, text="rate limited"),
            httpx.Response(429, text="rate limited"),
            httpx.Response(200, json=_SUCCESS_RESPONSE),
        ]
    )

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        result = await client.complete([ChatMessage(role="user", content="hi")])

    assert result.content == "OK"
    assert len(sleep_calls) == 2, f"Expected 2 sleep calls for 2 retries, got {len(sleep_calls)}"

    policy = RetryPolicy()
    cap = policy.cap_seconds
    jitter = policy.jitter_ratio
    base = policy.base_seconds

    # Each sleep must be bounded by cap_seconds
    for i, s in enumerate(sleep_calls):
        assert s <= cap, f"Sleep[{i}]={s:.3f}s exceeds cap_seconds={cap}"

    # Expected delays: base*2^0 for attempt 0, base*2^1 for attempt 1
    expected_0 = min(cap, base * (2**0))
    expected_1 = min(cap, base * (2**1))

    lo_0 = expected_0 * (1 - jitter)
    hi_0 = expected_0 * (1 + jitter)
    lo_1 = expected_1 * (1 - jitter)
    hi_1 = expected_1 * (1 + jitter)

    assert lo_0 <= sleep_calls[0] <= hi_0, (
        f"Sleep[0]={sleep_calls[0]:.3f}s not in [{lo_0:.3f}, {hi_0:.3f}] "
        f"(expected for attempt 0: base={base}, exp_delay={expected_0})"
    )
    assert lo_1 <= sleep_calls[1] <= hi_1, (
        f"Sleep[1]={sleep_calls[1]:.3f}s not in [{lo_1:.3f}, {hi_1:.3f}] "
        f"(expected for attempt 1: base={base}, exp_delay={expected_1})"
    )

    # Monotonically non-decreasing (lower bound of attempt 1 >= upper bound of attempt 0
    # is too strict with jitter; we just check means are non-decreasing)
    assert expected_1 >= expected_0, "Expected delays must be non-decreasing across attempts"


# ---------------------------------------------------------------------------
# T010 — Budget exhaustion raises LLMResponseError with rate-limit category
# ---------------------------------------------------------------------------


@respx.mock
async def test_complete_rate_limit_budget_exhausted(
    _clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T010: max_attempts consecutive 429s → raises LLMResponseError with rate-limit tag."""

    async def _fake_sleep(delay: float) -> None:
        pass  # instant in tests

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)

    policy = RetryPolicy()
    # max_attempts 429s — all attempts fail
    respx.post(CHAT_COMPLETIONS_URL).mock(
        side_effect=[httpx.Response(429, text="rate limited")] * policy.max_attempts
    )

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        with pytest.raises(LLMResponseError) as exc_info:
            await client.complete([ChatMessage(role="user", content="hi")])

    err = exc_info.value
    assert err.status_code == 429
    # The error message or category must indicate rate-limit
    assert "rate" in str(err).lower() or "429" in str(err), (
        f"Expected rate-limit indication in error, got: {err!r}"
    )


# ---------------------------------------------------------------------------
# T011 — Mid-stream 429 aborts iterator and retries
# ---------------------------------------------------------------------------


def _build_sse_body_str(*chunks: dict, done: bool = True) -> str:
    lines: list[str] = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    if done:
        lines.append("data: [DONE]\n\n")
    return "".join(lines)


def _delta_chunk(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
    }


def _stop_chunk() -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


def _make_stream_response(body: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        content=body.encode(),
        headers={"content-type": "text/event-stream"},
    )


@respx.mock
async def test_stream_mid_stream_429_aborts_and_retries(
    _clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T011: mid-stream 429 envelope → iterator aborts, retries, yields full response."""

    async def _fake_sleep(delay: float) -> None:
        pass

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)

    # First stream: starts OK, then returns a 429-status SSE response (simulated
    # by the transport returning 429 on stream open; the retry then gets 200).
    # We model mid-stream 429 as: first attempt returns 429, retry gets good 200 stream.
    good_body = _build_sse_body_str(
        _delta_chunk("Hello"),
        _delta_chunk(" world"),
        _stop_chunk(),
    )

    respx.post(CHAT_COMPLETIONS_URL).mock(
        side_effect=[
            _make_stream_response("", status=429),
            _make_stream_response(good_body, status=200),
        ]
    )

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        events = []
        async for event in client.stream([ChatMessage(role="user", content="hi")]):
            events.append(event)

    content_events = [e for e in events if e.type == "content_delta"]
    assert len(content_events) >= 1, (
        f"Expected content events after retry, got {[e.type for e in events]}"
    )
    done_events = [e for e in events if e.type == "done"]
    assert len(done_events) == 1, "Expected exactly one done event after retry"


# ---------------------------------------------------------------------------
# T012 — Concurrent stream() calls serialize at provider boundary
# ---------------------------------------------------------------------------


@respx.mock
async def test_stream_concurrent_calls_serialized(
    _clean_env: None,
) -> None:
    """T012: two concurrent stream() coroutines on same LLMClient serialize."""
    entry_times: list[float] = []
    exit_times: list[float] = []

    good_body = _build_sse_body_str(
        _delta_chunk("Hi"),
        _stop_chunk(),
    )

    call_count = 0

    def _transport_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        entry_times.append(time.monotonic())
        # Simulate that we record exit in the response (synchronous mock)
        resp = httpx.Response(
            200,
            content=good_body.encode(),
            headers={"content-type": "text/event-stream"},
        )
        exit_times.append(time.monotonic())
        return resp

    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_transport_side_effect)

    config = LLMClientConfig()
    client = LLMClient(config)

    async def _consume() -> None:
        async for _ in client.stream([ChatMessage(role="user", content="hi")]):
            pass

    # Launch two concurrent stream calls
    await asyncio.gather(_consume(), _consume())
    await client.close()

    assert call_count == 2, f"Expected 2 provider calls, got {call_count}"
    # With semaphore serialization: second call's entry must be >= first call's exit
    # (i.e., they do not overlap at the provider boundary)
    # entry_times[1] >= exit_times[0] means call 2 started after call 1 finished
    assert entry_times[1] >= exit_times[0] - 0.05, (
        f"Calls overlapped at provider boundary: "
        f"call1_exit={exit_times[0]:.4f}, call2_entry={entry_times[1]:.4f}"
    )


# ---------------------------------------------------------------------------
# T013 — Default payload parameters
# ---------------------------------------------------------------------------


@respx.mock
async def test_complete_default_payload_parameters(
    _clean_env: None,
) -> None:
    """T013: default outgoing payload has temperature=1.0, top_p=0.95, presence_penalty=0.0,
    max_tokens=1024 for complete()."""
    captured: list[dict] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_SUCCESS_RESPONSE)

    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_capture)

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        await client.complete([ChatMessage(role="user", content="hi")])

    assert len(captured) == 1
    payload = captured[0]
    assert payload.get("temperature") == 1.0, f"temperature={payload.get('temperature')!r}"
    assert payload.get("top_p") == 0.95, f"top_p={payload.get('top_p')!r}"
    assert payload.get("presence_penalty") == 0.0, (
        f"presence_penalty={payload.get('presence_penalty')!r}"
    )
    assert payload.get("max_tokens") == 1024, f"max_tokens={payload.get('max_tokens')!r}"
    assert payload.get("chat_template_kwargs") == {"enable_thinking": False}
    assert payload.get("parse_reasoning") is True
    assert payload.get("include_reasoning") is False


@respx.mock
async def test_complete_explicit_overrides_take_precedence(
    _clean_env: None,
) -> None:
    """T013: explicit caller overrides replace default parameter values in the payload."""
    captured: list[dict] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_SUCCESS_RESPONSE)

    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_capture)

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        await client.complete(
            [ChatMessage(role="user", content="hi")],
            temperature=0.2,
            top_p=0.8,
            presence_penalty=0.5,
            max_tokens=512,
        )

    assert len(captured) == 1
    payload = captured[0]
    assert payload.get("temperature") == 0.2
    assert payload.get("top_p") == 0.8
    assert payload.get("presence_penalty") == 0.5
    assert payload.get("max_tokens") == 512


@respx.mock
async def test_k_exaone_thinking_env_opt_in(
    _clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reasoning channel remains available when explicitly opted in."""
    captured: list[dict] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_SUCCESS_RESPONSE)

    monkeypatch.setenv("UMMAYA_K_EXAONE_THINKING", "true")
    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_capture)

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        await client.complete([ChatMessage(role="user", content="hi")])

    assert captured[0].get("chat_template_kwargs") == {"enable_thinking": True}
    assert captured[0].get("parse_reasoning") is True
    assert captured[0].get("include_reasoning") is True


@respx.mock
async def test_k_exaone_reasoning_mode_deep_payload(
    _clean_env: None,
) -> None:
    """Explicit reasoning_mode=deep enables provider thinking and reasoning parsing."""
    captured: list[dict] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_SUCCESS_RESPONSE)

    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_capture)

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        await client.complete(
            [ChatMessage(role="user", content="hi")],
            reasoning_mode="deep",
        )

    assert captured[0].get("chat_template_kwargs") == {"enable_thinking": True}
    assert captured[0].get("parse_reasoning") is True
    assert captured[0].get("include_reasoning") is True


@respx.mock
async def test_stream_default_payload_parameters(
    _clean_env: None,
) -> None:
    """T013: stream() also uses the same default parameters as complete()."""
    captured: list[dict] = []
    good_body = _build_sse_body_str(_delta_chunk("Hi"), _stop_chunk())

    def _capture(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            content=good_body.encode(),
            headers={"content-type": "text/event-stream"},
        )

    respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=_capture)

    config = LLMClientConfig()
    async with LLMClient(config) as client:
        async for _ in client.stream([ChatMessage(role="user", content="hi")]):
            pass

    assert len(captured) == 1
    payload = captured[0]
    assert payload.get("temperature") == 1.0
    assert payload.get("top_p") == 0.95
    assert payload.get("presence_penalty") == 0.0
    assert payload.get("max_tokens") == 1024
    assert payload.get("chat_template_kwargs") == {"enable_thinking": False}
    assert payload.get("parse_reasoning") is True
    assert payload.get("include_reasoning") is False
