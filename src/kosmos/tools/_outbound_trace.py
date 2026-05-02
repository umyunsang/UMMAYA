# SPDX-License-Identifier: Apache-2.0
"""Per-call outbound HTTP trace capture (Spec 2521 — verbose tool view).

Adapters wrap their httpx client with :func:`traced_async_client`. The lookup /
submit / verify primitive dispatcher in :mod:`kosmos.ipc.stdio` opens a trace
scope around each call so every external request the adapter makes
(``data.go.kr`` shape, agency endpoint, cached vendor, etc.) is recorded and
attached to the result envelope as ``outbound_traces``.

The TUI verbose view (Ctrl+R toggle / Ctrl+O transcript) reads the field and
renders a per-request block with method, URL, query params, body and the raw
response body so the citizen / operator can see exactly what hit the agency
API and what came back — without enabling Wireshark or staring at OTEL
spans.

Sensitive headers (``Authorization``, the ``serviceKey`` query param) are
redacted before being attached to the envelope. Body capture is capped at
8 KiB per direction; over the cap the body is replaced with the SHA-256
hash and a ``…(truncated)`` marker.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Bodies above this size are hashed instead of inlined (defends LLM context).
_MAX_BODY_BYTES = 8 * 1024

# Headers and query-param keys that must never leave the backend process.
_REDACT_HEADERS = frozenset({"authorization", "x-api-key", "x-secret-key", "cookie", "set-cookie"})
_REDACT_QUERY_PARAMS = frozenset({"servicekey", "service_key", "apikey", "api_key"})

# ---------------------------------------------------------------------------
# Public schema
# ---------------------------------------------------------------------------


class OutboundCallTrace(BaseModel):
    """One outbound HTTP call recorded by :func:`traced_async_client`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: str = Field(description="HTTP method, e.g. ``GET``, ``POST``.")
    url: str = Field(description="Request URL with redacted sensitive query params.")
    request_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Outbound headers; secrets redacted to ``***``.",
    )
    request_body: str | None = Field(
        default=None,
        description="Request body as text. Truncated above 8 KiB.",
    )
    response_status: int = Field(description="HTTP status code of the response.")
    response_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Response headers (all kept; no secrets expected here).",
    )
    response_body: str | None = Field(
        default=None,
        description="Response body as text. Truncated above 8 KiB.",
    )
    elapsed_ms: int = Field(description="Wall-clock duration of the request, milliseconds.")
    timestamp_iso: str = Field(description="UTC start timestamp in ISO-8601 format.")


# ContextVar holds the per-call trace list. ``None`` means "capture disabled"
# so adapters wrapped in :func:`traced_async_client` outside a capture scope
# (e.g. unit tests calling ``_fetch`` directly) emit no traces. Declared
# AFTER ``OutboundCallTrace`` so the generic parameter resolves directly
# (no PEP 563 forward reference needed — keeps ruff UP037 happy).
_outbound_traces_var: ContextVar[list[OutboundCallTrace] | None] = ContextVar(
    "kosmos_outbound_traces", default=None
)


# ---------------------------------------------------------------------------
# Capture lifecycle
# ---------------------------------------------------------------------------


def start_outbound_capture() -> object:
    """Begin a new trace scope.

    Returns an opaque ContextVar token the caller passes to
    :func:`finish_outbound_capture` to drain the buffer.
    """
    return _outbound_traces_var.set([])


def consume_outbound_capture(token: object) -> list[OutboundCallTrace]:
    """End the trace scope and return the recorded traces."""
    traces = _outbound_traces_var.get() or []
    _outbound_traces_var.reset(token)  # type: ignore[arg-type]
    return list(traces)


def is_outbound_capture_active() -> bool:
    """Return True when a capture scope is currently open."""
    return _outbound_traces_var.get() is not None


# ---------------------------------------------------------------------------
# Capture helpers (used by the httpx event hooks below)
# ---------------------------------------------------------------------------


def _redact_url(url: httpx.URL) -> str:
    """Strip sensitive query-param values from the URL.

    httpx's ``URL.copy_with(params=...)`` url-encodes the replacement
    value, so ``***`` becomes ``%2A%2A%2A`` and is illegible. We rebuild
    the query string manually so the redaction stays human-readable in
    the verbose JSON view.
    """
    if not url.query:
        return str(url)
    redacted_pairs: list[str] = []
    for k, v in url.params.multi_items():
        if k.lower() in _REDACT_QUERY_PARAMS:
            redacted_pairs.append(f"{k}=***")
        else:
            from urllib.parse import quote

            redacted_pairs.append(f"{k}={quote(str(v), safe='')}")
    base = str(url.copy_with(query=None)).rstrip("?")
    return f"{base}?{'&'.join(redacted_pairs)}"


def _redact_headers(headers: httpx.Headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in headers.items():
        out[k] = "***" if k.lower() in _REDACT_HEADERS else v
    return out


def _stringify_body(raw: bytes | None) -> str | None:
    """Decode + truncate a body. Pretty-print JSON when possible."""
    if raw is None or len(raw) == 0:
        return None
    if len(raw) > _MAX_BODY_BYTES:
        digest = hashlib.sha256(raw).hexdigest()[:16]
        return (
            f"...(truncated {len(raw)} bytes, sha256={digest}, "
            f"showing first {_MAX_BODY_BYTES} bytes)\n"
            + raw[:_MAX_BODY_BYTES].decode("utf-8", errors="replace")
        )
    text = raw.decode("utf-8", errors="replace")
    # Best-effort JSON pretty print.
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(text)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, ValueError):
            return text
    return text


# ---------------------------------------------------------------------------
# httpx event hooks
# ---------------------------------------------------------------------------


def _record_request_start(request: httpx.Request) -> None:
    """Stamp the start time on the request via extensions."""
    request.extensions["_kosmos_t_start"] = time.perf_counter()


async def _arecord_request_start(request: httpx.Request) -> None:
    request.extensions["_kosmos_t_start"] = time.perf_counter()


def _emit_trace(request: httpx.Request, response: httpx.Response) -> None:
    buffer = _outbound_traces_var.get()
    if buffer is None:
        # Capture not active — skip silently.
        return

    t_start = request.extensions.get("_kosmos_t_start")
    elapsed_ms = int((time.perf_counter() - t_start) * 1000) if isinstance(t_start, float) else 0

    request_body_bytes: bytes | None = None
    try:
        # httpx populates ``request.content`` after the request has been
        # serialised. For streaming / multipart this may be empty — accept that.
        request_body_bytes = bytes(request.content) if request.content else None
    except Exception:  # noqa: BLE001
        request_body_bytes = None

    try:
        response_body_bytes = response.content
    except Exception:  # noqa: BLE001
        response_body_bytes = b""

    trace = OutboundCallTrace(
        method=request.method,
        url=_redact_url(request.url),
        request_headers=_redact_headers(request.headers),
        request_body=_stringify_body(request_body_bytes),
        response_status=response.status_code,
        response_headers=dict(response.headers),
        response_body=_stringify_body(response_body_bytes),
        elapsed_ms=elapsed_ms,
        timestamp_iso=request.extensions.get(
            "_kosmos_ts_iso",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ),
    )
    buffer.append(trace)


async def _arecord_response(response: httpx.Response) -> None:
    # httpx does not deliver the response body via the response hook unless
    # we explicitly read it. Adapter code typically calls ``response.json()``
    # after the hook fires, so we read here defensively. The cost is a single
    # extra ``aread()`` on streaming bodies.
    try:
        if not response.is_closed:
            await response.aread()
    except Exception:  # noqa: BLE001, S110 — defensive read; capture path must not abort the adapter
        pass
    _emit_trace(response.request, response)


# ---------------------------------------------------------------------------
# Public client factory
# ---------------------------------------------------------------------------


def traced_async_client(**httpx_kwargs: Any) -> httpx.AsyncClient:
    """Return an ``httpx.AsyncClient`` wired up to the trace buffer.

    All keyword args are forwarded to :class:`httpx.AsyncClient`. The caller's
    own ``event_hooks``, if any, are appended after the trace hooks so user
    hooks can still inspect the response.
    """
    user_event_hooks = httpx_kwargs.pop("event_hooks", None) or {}
    request_hooks = list(user_event_hooks.get("request", []))
    response_hooks = list(user_event_hooks.get("response", []))

    request_hooks.insert(0, _arecord_request_start)
    response_hooks.append(_arecord_response)

    httpx_kwargs["event_hooks"] = {
        "request": request_hooks,
        "response": response_hooks,
    }
    return httpx.AsyncClient(**httpx_kwargs)


@asynccontextmanager
async def outbound_capture_scope() -> AsyncIterator[list[OutboundCallTrace]]:
    """Async context manager wrapping start/consume.

    Yields the trace buffer that gets populated as adapters issue HTTP calls.
    """
    token = start_outbound_capture()
    try:
        yield _outbound_traces_var.get() or []
    finally:
        consume_outbound_capture(token)
