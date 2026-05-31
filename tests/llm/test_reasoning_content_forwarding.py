# SPDX-License-Identifier: Apache-2.0
"""Spec 2521 T005 — Reasoning-content forwarding regression test (FR-007).

Asserts that K-EXAONE's `delta.reasoning_content` channel is forwarded to
`StreamEvent(type="thinking_delta", thinking=...)` by `LLMClient._stream_response`.

CC reference: services/api/claude.ts:2148 (`thinking_delta` content_block_delta).
UMMAYA handler: src/ummaya/llm/client.py:788-802.

Scaffold (T005): pytest-asyncio + httpx mock skeleton. Full assertions in T019.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest

from ummaya.llm.client import LLMClient
from ummaya.llm.config import LLMClientConfig
from ummaya.llm.models import ChatMessage, StreamEvent


class _MockSSEByteStream(httpx.AsyncByteStream):
    """Minimal AsyncByteStream concrete impl for SSE replay in tests."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:  # noqa: D401
        return None


def _sse_chunk(payload: dict) -> bytes:
    """Format a single SSE data chunk per OpenAI streaming protocol."""
    return f"data: {json.dumps(payload)}\n\n".encode()


def _sse_done() -> bytes:
    return b"data: [DONE]\n\n"


@pytest.fixture
def fake_friendli_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a synthetic FriendliAI token so LLMClientConfig() succeeds."""
    monkeypatch.setenv("UMMAYA_FRIENDLI_TOKEN", "test-token-2521")
    monkeypatch.setenv("UMMAYA_FRIENDLI_BASE_URL", "https://api.test.invalid/v1")
    monkeypatch.setenv("UMMAYA_FRIENDLI_MODEL", "LGAI-EXAONE/K-EXAONE-236B-A23B")


@pytest.mark.asyncio
async def test_default_reasoning_content_is_suppressed_when_include_reasoning_is_false(
    fake_friendli_token: None,
) -> None:
    """Default balanced policy must hard-drop unexpected reasoning chunks.

    Friendli's documented contract says ``include_reasoning=false`` should not
    stream ``delta.reasoning_content``. UMMAYA still enforces the gate locally
    so a provider-side or mocked SSE drift cannot surface raw CoT in fast /
    balanced modes.
    """
    reasoning_chunks = ["raw ", "provider ", "trace"]

    async def _mock_stream(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["include_reasoning"] is False
        chunks: list[bytes] = [
            _sse_chunk(
                {
                    "id": "chatcmpl-test-reasoning-suppressed",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"reasoning_content": chunk},
                            "finish_reason": None,
                        }
                    ],
                }
            )
            for chunk in reasoning_chunks
        ]
        chunks.append(
            _sse_chunk(
                {
                    "id": "chatcmpl-test-reasoning-suppressed",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": "visible answer"},
                            "finish_reason": "stop",
                        }
                    ],
                }
            )
        )
        chunks.append(_sse_done())
        return httpx.Response(200, stream=_MockSSEByteStream(chunks))

    transport = httpx.MockTransport(_mock_stream)
    config = LLMClientConfig()  # type: ignore[call-arg]
    client = LLMClient(config=config)
    client._client = httpx.AsyncClient(transport=transport, base_url=str(config.base_url))

    events: list[StreamEvent] = []
    async for event in client.stream(
        messages=[ChatMessage(role="user", content="오늘 부산 날씨")],
        max_tokens=100,
    ):
        events.append(event)

    assert [e for e in events if e.type == "thinking_delta"] == []
    assert "".join(e.content or "" for e in events if e.type == "content_delta") == (
        "visible answer"
    )


@pytest.mark.asyncio
async def test_deep_reasoning_content_forwarded_as_thinking_delta(
    fake_friendli_token: None,
) -> None:
    """T005 scaffold: when FriendliAI emits delta.reasoning_content, LLMClient
    yields a StreamEvent(type='thinking_delta', thinking=<text>) — mirroring
    CC's services/api/claude.ts:2148 thinking_delta handling.

    Full implementation in T019 — currently asserts the event type only.
    """
    reasoning_chunks = ["사용자가 ", "부산 날씨를 ", "물어보고 있습니다."]

    async def _mock_stream(request: httpx.Request) -> httpx.Response:
        chunks: list[bytes] = []
        for chunk in reasoning_chunks:
            chunks.append(
                _sse_chunk(
                    {
                        "id": "chatcmpl-test-2521",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"reasoning_content": chunk},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
            )
        chunks.append(
            _sse_chunk(
                {
                    "id": "chatcmpl-test-2521",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                }
            )
        )
        chunks.append(_sse_done())
        return httpx.Response(200, stream=_MockSSEByteStream(chunks))

    transport = httpx.MockTransport(_mock_stream)
    config = LLMClientConfig()  # type: ignore[call-arg]
    client = LLMClient(config=config)
    # Replace internal httpx client with mocked transport
    client._client = httpx.AsyncClient(transport=transport, base_url=str(config.base_url))

    events: list[StreamEvent] = []
    async for event in client.stream(
        messages=[ChatMessage(role="user", content="오늘 부산 날씨")],
        max_tokens=100,
        reasoning_mode="deep",
    ):
        events.append(event)

    thinking_events = [e for e in events if e.type == "thinking_delta"]
    # Spec 2521 (2026-05-01) — backend pacing splits each chunk into
    # sub-chunks of ``UMMAYA_LLM_STREAM_CHUNK_MAX_CHARS``. The contract is
    # now "total reasoning text preserved verbatim" rather than "1:1 chunk
    # boundary preservation"; the split is invisible to the LLM-history
    # consumer (which concatenates) and to the TUI thinking renderer
    # (which appends). The assertion below validates the byte-level
    # invariant the agentic loop actually depends on.
    assert len(thinking_events) >= len(reasoning_chunks), (
        f"expected at least {len(reasoning_chunks)} thinking_delta events, "
        f"got {len(thinking_events)}"
    )

    concatenated = "".join(e.thinking or "" for e in thinking_events)
    assert concatenated == "".join(reasoning_chunks), (
        f"reasoning_content bytes not preserved verbatim: got {concatenated!r}"
    )

    # Content channel should be empty (or only contain post-reasoning content)
    content_events = [e for e in events if e.type == "content_delta"]
    visible_content = "".join(e.content or "" for e in content_events)
    assert "부산 날씨" not in visible_content, (
        "reasoning_content leaked into delta.content — channel separation broken"
    )
