# SPDX-License-Identifier: Apache-2.0
"""T121 — OTEL span emission tests for the IPC stdio frame layer (FR-053).

Verifies:
- Inbound ``user_input`` frame → one ``kosax.ipc.frame`` span with
  ``direction=inbound``, ``kind=user_input``, and the correct ``session_id``.
- Outbound ``assistant_chunk`` frame (via ``write_frame``) → one
  ``kosax.ipc.frame`` span with ``direction=outbound`` and
  ``kind=assistant_chunk``.

Strategy: monkeypatch the module-level ``_tracer`` in ``kosax.ipc.stdio``
to use a dedicated ``TracerProvider`` backed by an ``InMemorySpanExporter``,
mirroring the pattern established in ``tests/observability/test_tool_execute_span.py``.
No subprocess is spawned; ``write_frame`` and ``_reader_loop`` are called
directly or indirectly with a mocked stdout.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import UTC, datetime

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from kosax.ipc.frame_schema import AssistantChunkFrame, UserInputFrame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Per-test InMemorySpanExporter fixture via _tracer monkeypatching
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem_exporter(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    """Patch _tracer in kosax.ipc.stdio with a dedicated test TracerProvider.

    This mirrors the pattern from tests/observability/test_tool_execute_span.py
    so we do not touch the global OpenTelemetry SDK singleton.
    """
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    import kosax.ipc.stdio as stdio_mod

    monkeypatch.setattr(
        stdio_mod,
        "_tracer",
        provider.get_tracer("kosax.ipc"),
    )

    exporter.clear()
    return exporter


# ---------------------------------------------------------------------------
# T121-A: Inbound user_input frame emits correct span
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inbound_user_input_span(
    mem_exporter: InMemorySpanExporter,
) -> None:
    """Inbound user_input frame → one kosax.ipc.frame span with direction=inbound."""
    from kosax.ipc.stdio import _reader_loop  # noqa: PLC0415

    session_id = str(uuid.uuid4())
    frame_in = UserInputFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_ts(),
        kind="user_input",
        text="hello",
    )
    payload_line = (frame_in.model_dump_json() + "\n").encode("utf-8")

    # Use asyncio.StreamReader to feed the payload as if from stdin.
    reader = asyncio.StreamReader()
    reader.feed_data(payload_line)
    reader.feed_eof()

    received: list[object] = []

    async def _on_frame(f: object) -> None:
        received.append(f)

    await _reader_loop(reader, _on_frame, session_id)

    # Exactly one frame dispatched.
    assert len(received) == 1, f"Expected 1 frame dispatched, got {len(received)}"

    # Assert span.
    spans = mem_exporter.get_finished_spans()
    ipc_spans = [s for s in spans if s.name == "kosax.ipc.frame"]
    assert len(ipc_spans) == 1, (
        f"Expected exactly 1 kosax.ipc.frame span, got {len(ipc_spans)}. "
        f"All spans: {[s.name for s in spans]}"
    )
    span = ipc_spans[0]
    attrs = dict(span.attributes or {})

    assert attrs.get("kosax.session.id") == session_id, f"kosax.session.id mismatch: {attrs}"
    assert attrs.get("kosax.frame.kind") == "user_input", f"kosax.frame.kind mismatch: {attrs}"
    assert attrs.get("kosax.frame.direction") == "inbound", (
        f"kosax.frame.direction mismatch: {attrs}"
    )
    assert isinstance(attrs.get("kosax.ipc.latency_ms"), float), (
        f"kosax.ipc.latency_ms must be a float: {attrs}"
    )
    # Status must be UNSET on success.
    assert span.status.status_code == StatusCode.UNSET, (
        f"Expected UNSET on success, got {span.status.status_code}"
    )


# ---------------------------------------------------------------------------
# T121-B: Outbound assistant_chunk frame emits correct span
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outbound_assistant_chunk_span(
    mem_exporter: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outbound assistant_chunk via write_frame → kosax.ipc.frame span (direction=outbound)."""
    from kosax.ipc import stdio as stdio_mod  # noqa: PLC0415

    session_id = str(uuid.uuid4())
    chunk_frame = AssistantChunkFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="backend",
        ts=_ts(),
        kind="assistant_chunk",
        message_id=str(uuid.uuid4()),
        delta="Hello, citizen.",
        done=True,
    )

    # Redirect sys.stdout to a TextIOWrapper-like wrapper backed by a BytesIO buffer
    # so write_frame's sys.stdout.buffer.write/flush calls are intercepted.
    fake_buf = io.BytesIO()

    class _FakeBuffer:
        def write(self, data: bytes) -> None:
            fake_buf.write(data)

        def flush(self) -> None:
            pass

    class _FakeStdout:
        buffer = _FakeBuffer()

    import sys  # noqa: PLC0415

    monkeypatch.setattr(sys, "stdout", _FakeStdout())

    # Reset the module-level lock so we get a fresh one inside this event loop.
    monkeypatch.setattr(stdio_mod, "_stdout_lock", None)

    await stdio_mod.write_frame(chunk_frame)

    # Confirm bytes were written.
    written = fake_buf.getvalue()
    assert written, "write_frame produced no output"

    # Assert span.
    spans = mem_exporter.get_finished_spans()
    ipc_spans = [s for s in spans if s.name == "kosax.ipc.frame"]
    assert len(ipc_spans) == 1, (
        f"Expected exactly 1 kosax.ipc.frame span, got {len(ipc_spans)}. "
        f"All spans: {[s.name for s in spans]}"
    )
    span = ipc_spans[0]
    attrs = dict(span.attributes or {})

    assert attrs.get("kosax.session.id") == session_id, f"kosax.session.id mismatch: {attrs}"
    assert attrs.get("kosax.frame.kind") == "assistant_chunk", f"kosax.frame.kind mismatch: {attrs}"
    assert attrs.get("kosax.frame.direction") == "outbound", (
        f"kosax.frame.direction mismatch: {attrs}"
    )
    assert isinstance(attrs.get("kosax.ipc.latency_ms"), float), (
        f"kosax.ipc.latency_ms must be a float: {attrs}"
    )
    assert span.status.status_code == StatusCode.UNSET, (
        f"Expected UNSET on success, got {span.status.status_code}"
    )
