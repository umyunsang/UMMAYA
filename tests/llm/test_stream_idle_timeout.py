# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from ummaya.llm.client import LLMClient
from ummaya.llm.config import LLMClientConfig
from ummaya.llm.errors import StreamInterruptedError
from ummaya.llm.models import ChatMessage, StreamEvent

_COMPLETIONS_URL = "https://api.friendli.ai/serverless/v1/chat/completions"


class _NeverYieldingStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        await asyncio.Event().wait()
        yield b""


class _KeepAliveOnlyStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        while True:
            await asyncio.sleep(0.005)
            yield b": keepalive\n\n"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("UMMAYA_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("UMMAYA_FRIENDLI_TOKEN", "test-token-12345")


async def _drain_stream(stream: AsyncIterator[StreamEvent]) -> None:
    async for _ in stream:
        pass


@respx.mock
async def test_stream_raises_project_error_when_next_sse_line_idles(
    monkeypatch: pytest.MonkeyPatch,
    sample_messages: list[ChatMessage],
) -> None:
    monkeypatch.setenv("UMMAYA_LLM_STREAM_IDLE_TIMEOUT_SECONDS", "0.01")
    respx.post(_COMPLETIONS_URL).mock(
        return_value=httpx.Response(
            200,
            stream=_NeverYieldingStream(),
            headers={"content-type": "text/event-stream"},
        )
    )
    config = LLMClientConfig(timeout=5.0)

    async with LLMClient(config) as client:
        started = time.monotonic()
        with pytest.raises(StreamInterruptedError, match="idle"):
            await asyncio.wait_for(_drain_stream(client.stream(sample_messages)), timeout=0.3)

    assert time.monotonic() - started < 0.25


@respx.mock
async def test_stream_raises_when_only_sse_keepalives_arrive(
    monkeypatch: pytest.MonkeyPatch,
    sample_messages: list[ChatMessage],
) -> None:
    monkeypatch.setenv("UMMAYA_LLM_STREAM_IDLE_TIMEOUT_SECONDS", "0.03")
    respx.post(_COMPLETIONS_URL).mock(
        return_value=httpx.Response(
            200,
            stream=_KeepAliveOnlyStream(),
            headers={"content-type": "text/event-stream"},
        )
    )
    config = LLMClientConfig(timeout=5.0)

    async with LLMClient(config) as client:
        started = time.monotonic()
        with pytest.raises(StreamInterruptedError, match="idle"):
            await asyncio.wait_for(_drain_stream(client.stream(sample_messages)), timeout=0.3)

    assert time.monotonic() - started < 0.25
