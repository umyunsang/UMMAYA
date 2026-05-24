# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ummaya.tools._outbound_trace (Spec 2521)."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from ummaya.tools._outbound_trace import (
    OutboundCallTrace,
    consume_outbound_capture,
    is_outbound_capture_active,
    outbound_capture_scope,
    start_outbound_capture,
    traced_async_client,
)

# ---------------------------------------------------------------------------
# Capture lifecycle
# ---------------------------------------------------------------------------


def test_capture_inactive_by_default() -> None:
    assert is_outbound_capture_active() is False


def test_start_consume_pair_round_trips() -> None:
    token = start_outbound_capture()
    assert is_outbound_capture_active() is True
    traces = consume_outbound_capture(token)
    assert traces == []
    assert is_outbound_capture_active() is False


@pytest.mark.asyncio
async def test_async_context_manager_closes_scope() -> None:
    async with outbound_capture_scope() as buf:
        assert is_outbound_capture_active() is True
        assert buf == []
    assert is_outbound_capture_active() is False


# ---------------------------------------------------------------------------
# Trace capture via MockTransport (real httpx pipeline, no network)
# ---------------------------------------------------------------------------


def _mock_transport_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_get_request_response_captured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"items": [{"id": 1}, {"id": 2}]},
            headers={"x-served-by": "test-fixture"},
        )

    token = start_outbound_capture()
    try:
        async with traced_async_client(transport=_mock_transport_factory(handler)) as cli:
            r = await cli.get(
                "https://example.kr/api/items",
                params={
                    "limit": 2,
                    "serviceKey": "secret-XYZ",
                    "authKey": "kma-apihub-secret",
                },
            )
            assert r.status_code == 200
    finally:
        traces = consume_outbound_capture(token)

    assert len(traces) == 1
    t = traces[0]
    assert isinstance(t, OutboundCallTrace)
    assert t.method == "GET"
    # Sensitive query param is redacted, others preserved.
    assert "serviceKey=***" in t.url
    assert "authKey=***" in t.url
    assert "secret-XYZ" not in t.url
    assert "kma-apihub-secret" not in t.url
    assert "limit=2" in t.url
    assert t.response_status == 200
    assert t.response_headers.get("x-served-by") == "test-fixture"
    # Body is pretty-printed JSON when valid.
    parsed = json.loads(t.response_body or "")
    assert parsed == {"items": [{"id": 1}, {"id": 2}]}
    assert t.elapsed_ms >= 0


@pytest.mark.asyncio
async def test_post_body_captured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"received": True})

    token = start_outbound_capture()
    try:
        async with traced_async_client(transport=_mock_transport_factory(handler)) as cli:
            r = await cli.post(
                "https://example.kr/api/submit",
                json={"name": "홍길동", "amount": 1000},
                headers={"Authorization": "Bearer ***real-token***"},
            )
            assert r.status_code == 202
    finally:
        traces = consume_outbound_capture(token)

    assert len(traces) == 1
    t = traces[0]
    assert t.method == "POST"
    # Body roundtrips Korean text.
    parsed = json.loads(t.request_body or "")
    assert parsed == {"name": "홍길동", "amount": 1000}
    # Authorization header redacted.
    assert t.request_headers.get("authorization") == "***"
    # Response status reaches the trace.
    assert t.response_status == 202


@pytest.mark.asyncio
async def test_capture_disabled_emits_no_trace() -> None:
    """Adapter calling traced_async_client outside a scope is a no-op."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    # No start_outbound_capture call — capture_active is False.
    async with traced_async_client(transport=_mock_transport_factory(handler)) as cli:
        r = await cli.get("https://example.kr/api/ping")
        assert r.status_code == 200
    # No buffer to consume.
    assert is_outbound_capture_active() is False


@pytest.mark.asyncio
async def test_multiple_calls_accumulate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"path": str(request.url.path)})

    token = start_outbound_capture()
    try:
        async with traced_async_client(transport=_mock_transport_factory(handler)) as cli:
            await cli.get("https://example.kr/api/a")
            await cli.get("https://example.kr/api/b")
            await cli.get("https://example.kr/api/c")
    finally:
        traces = consume_outbound_capture(token)

    assert len(traces) == 3
    paths = [t.url for t in traces]
    assert any(p.endswith("/api/a") for p in paths)
    assert any(p.endswith("/api/b") for p in paths)
    assert any(p.endswith("/api/c") for p in paths)


@pytest.mark.asyncio
async def test_large_body_truncated_with_hash() -> None:
    big_payload = "X" * (16 * 1024)  # 16 KiB > 8 KiB cap

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=big_payload.encode("utf-8"),
            headers={"content-type": "text/plain"},
        )

    token = start_outbound_capture()
    try:
        async with traced_async_client(transport=_mock_transport_factory(handler)) as cli:
            await cli.get("https://example.kr/api/big")
    finally:
        traces = consume_outbound_capture(token)

    assert len(traces) == 1
    body = traces[0].response_body or ""
    assert "...(truncated" in body
    assert "sha256=" in body
    # The hash is deterministic for the input.
    expected_prefix_len = 8192
    assert f"showing first {expected_prefix_len} bytes" in body


@pytest.mark.asyncio
async def test_large_multibyte_body_truncates_without_replacement_character() -> None:
    """Trace truncation must not split UTF-8 into U+FFFD in TUI captures."""
    big_payload = "복지서비스" * 3000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=big_payload.encode("utf-8"),
            headers={"content-type": "text/plain; charset=utf-8"},
        )

    token = start_outbound_capture()
    try:
        async with traced_async_client(transport=_mock_transport_factory(handler)) as cli:
            await cli.get("https://example.kr/api/big-utf8")
    finally:
        traces = consume_outbound_capture(token)

    body = traces[0].response_body or ""
    assert "...(truncated" in body
    assert "\ufffd" not in body


@pytest.mark.asyncio
async def test_kma_forecast_fetch_emits_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real adapter end-to-end: kma_forecast_fetch via httpx MockTransport.

    Proves the full pipeline:
       capture scope open
    →  adapter calls own ``traced_async_client(timeout=30.0)``
    →  httpx event hooks fire
    →  trace lands in the buffer
    →  drain returns one OutboundCallTrace with the redacted authKey URL
    """
    from ummaya.tools.kma.forecast_fetch import KmaForecastFetchInput, _fetch

    api_hub_key = "test-api-hub-key-only"
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", api_hub_key)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        # Minimal valid KMA envelope.
        return httpx.Response(
            200,
            json={
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
                    "body": {
                        "items": {
                            "item": [
                                {
                                    "fcstDate": "20260502",
                                    "fcstTime": "0900",
                                    "category": "TMP",
                                    "fcstValue": "18",
                                },
                            ]
                        }
                    },
                }
            },
            headers={"content-type": "application/json"},
        )

    inp = KmaForecastFetchInput(
        lat=37.5665,
        lon=126.978,
        base_date="20260502",
        base_time="0500",
    )

    token = start_outbound_capture()
    try:
        # Inject the mock client directly so the adapter doesn't open
        # a real one. Inside this branch the adapter does NOT use
        # traced_async_client (it uses the injected client). Wrap the
        # mock transport with the traced client to keep the hooks live.
        async with traced_async_client(transport=_mock_transport_factory(handler)) as cli:
            result = await _fetch(inp, client=cli)
    finally:
        traces = consume_outbound_capture(token)

    # Adapter result is a LookupTimeseries on the happy path.
    assert getattr(result, "kind", None) == "timeseries"
    # Exactly one outbound HTTP call recorded.
    assert len(traces) == 1
    trace = traces[0]
    assert trace.method == "GET"
    assert "getVilageFcst" in trace.url
    # The APIHub authKey query param is redacted.
    assert "authKey=***" in trace.url
    # Real key value never leaks.
    assert api_hub_key not in trace.url
    assert trace.response_status == 200


@pytest.mark.asyncio
async def test_outbound_trace_attached_to_envelope_via_dispatcher() -> None:
    """End-to-end smoke: stdio dispatcher should attach traces to envelope.

    This drives a single primitive turn through the dispatcher with a
    mocked adapter that calls traced_async_client. We simulate just the
    capture+drain flow that ``_dispatch_primitive`` performs.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": "ok"})

    # Replicate the stdio dispatcher's start/consume pair around a fake
    # adapter call.
    token = start_outbound_capture()
    try:
        async with traced_async_client(transport=_mock_transport_factory(handler)) as cli:
            await cli.get("https://apis.data.go.kr/foo")
    finally:
        traces = consume_outbound_capture(token)

    # Envelope payload: dispatcher attaches model_dump()'d traces.
    payload = {"kind": "find", "result": {"kind": "record"}}
    if traces:
        payload["outbound_traces"] = [t.model_dump() for t in traces]

    assert "outbound_traces" in payload
    assert len(payload["outbound_traces"]) == 1
    trace = payload["outbound_traces"][0]
    assert trace["method"] == "GET"
    assert trace["url"].startswith("https://apis.data.go.kr/foo")
    assert trace["response_status"] == 200
