# SPDX-License-Identifier: Apache-2.0
"""Regression tests for document harness dispatch through the stdio bridge."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import sys
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ummaya.ipc.frame_schema import SessionEventFrame, ToolCallFrame

_RUNNER_TIMEOUT = 30.0


def _ts() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


class _CaptureBuf:
    def __init__(self) -> None:
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    def flush(self) -> None:
        pass

    def as_frames(self) -> list[dict[str, Any]]:
        self._buf.seek(0)
        frames: list[dict[str, Any]] = []
        for line in self._buf:
            stripped = line.strip()
            if stripped:
                with contextlib.suppress(json.JSONDecodeError):
                    frames.append(json.loads(stripped))
        return frames


class _FakeStdout:
    def __init__(self) -> None:
        self.buffer = _CaptureBuf()

    def write(self, data: str) -> None:
        self.buffer.write(data.encode())

    def flush(self) -> None:
        pass


@pytest.mark.asyncio
async def test_concrete_document_inspect_tool_call_bypasses_lookup_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)

    session_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    call_id = f"call-document-{uuid.uuid4().hex[:8]}"
    tool_call_frame = ToolCallFrame(
        session_id=session_id,
        correlation_id=correlation_id,
        role="tool",
        ts=_ts(),
        kind="tool_call",
        call_id=call_id,
        name="document_inspect",
        arguments={
            "correlation_id": "corr-doc-ipc",
            "document": {"path": str(source), "expected_format": "docx"},
        },
    )
    exit_frame = SessionEventFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_ts(),
        kind="session_event",
        event="exit",
        payload={},
    )
    buf = await _run_stdio_frames([tool_call_frame, exit_frame], session_id, monkeypatch)

    frames = buf.as_frames()
    tool_results = [
        frame
        for frame in frames
        if frame.get("kind") == "tool_result" and frame.get("call_id") == call_id
    ]
    assert tool_results, f"document_inspect must emit a tool_result frame: {frames!r}"
    envelope = tool_results[0]["envelope"]
    assert envelope["kind"] == "find"
    result = envelope.get("result")
    assert isinstance(result, dict)
    assert result.get("tool_id") == "document_inspect"
    assert "expected envelope schema" not in json.dumps(result)


async def _run_stdio_frames(
    frames: list[ToolCallFrame | SessionEventFrame],
    session_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> _CaptureBuf:
    from ummaya.ipc import stdio as stdio_mod

    monkeypatch.setattr(stdio_mod, "_stdout_lock", None)

    fake_stdout = _FakeStdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    payload = b"".join((frame.model_dump_json() + "\n").encode() for frame in frames)
    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    r_file = os.fdopen(r_fd, "rb")

    class _FakeStdinWrapper:
        buffer = r_file

    monkeypatch.setattr(sys, "stdin", _FakeStdinWrapper())

    from ummaya.ipc.stdio import run as ipc_run

    try:
        await asyncio.wait_for(ipc_run(session_id=session_id), timeout=_RUNNER_TIMEOUT)
    finally:
        if not r_file.closed:
            r_file.close()

    return fake_stdout.buffer


def _write_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")
