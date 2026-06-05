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
async def test_concrete_document_primitive_tool_call_bypasses_lookup_envelope(
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
        name="document",
        arguments={
            "correlation_id": "corr-doc-ipc",
            "document": {"path": str(source), "expected_format": "docx"},
            "operation": "inspect",
            "instruction": "Inspect this DOCX file through the document primitive.",
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
    assert tool_results, f"document primitive must emit a tool_result frame: {frames!r}"
    envelope = tool_results[0]["envelope"]
    assert envelope["kind"] == "document"
    result = envelope.get("result")
    assert isinstance(result, dict)
    assert result.get("tool_id") == "document"
    assert "expected envelope schema" not in json.dumps(result)


@pytest.mark.asyncio
async def test_local_document_primitive_bypasses_citizen_permission_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "weekly.hwpx"
    _write_minimal_hwpx(source)

    session_id = str(uuid.uuid4())
    call_id = f"call-document-{uuid.uuid4().hex[:8]}"
    document_frame = ToolCallFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tool",
        ts=_ts(),
        kind="tool_call",
        call_id=call_id,
        name="document",
        arguments={
            "correlation_id": "corr-doc-perm",
            "document": {"path": str(source), "expected_format": "hwpx"},
            "operation": "inspect",
            "instruction": "Inspect this HWPX file without opening a citizen permission prompt.",
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

    monkeypatch.setenv("UMMAYA_PERMISSION_TIMEOUT_SECONDS", "0.01")
    buf = await _run_stdio_frames([document_frame, exit_frame], session_id, monkeypatch)

    frames = buf.as_frames()
    assert not [frame for frame in frames if frame.get("kind") == "permission_request"]
    document_results = [
        frame
        for frame in frames
        if frame.get("kind") == "tool_result" and frame.get("call_id") == call_id
    ]
    assert document_results, f"document primitive must emit a tool_result: {frames!r}"
    envelope = document_results[0]["envelope"]
    assert envelope["kind"] == "document"
    result = envelope.get("result")
    assert isinstance(result, dict)
    assert result.get("tool_id") == "document"
    assert result.get("status") == "ok"


@pytest.mark.asyncio
async def test_direct_document_extract_tool_call_promotes_to_write_workflow_from_user_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "weekly.hwpx"
    destination = tmp_path / "weekly-auto.hwpx"
    _write_minimal_hwpx(source)

    session_id = str(uuid.uuid4())
    call_id = f"call-document-{uuid.uuid4().hex[:8]}"
    user_query = (
        f"{source} 문서 내용을 파악해서 다음 주차 활동일지로 알아서 작성하고, "
        f"저장은 {destination} 로 해줘. 수정 후 변경된 부분만 바로 확인할 수 있게 보여줘."
    )
    document_frame = ToolCallFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tool",
        ts=_ts(),
        kind="tool_call",
        call_id=call_id,
        name="document",
        arguments={
            "correlation_id": "corr-doc-autosave",
            "document": {"path": str(source), "expected_format": "hwpx"},
            "operation": "extract",
            "instruction": "문서 내용을 구조적으로 추출하고 다음 주차 작성 정보를 파악하세요.",
            "__ummaya_user_query": user_query,
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

    buf = await _run_stdio_frames([document_frame, exit_frame], session_id, monkeypatch)

    frames = buf.as_frames()
    document_results = [
        frame
        for frame in frames
        if frame.get("kind") == "tool_result" and frame.get("call_id") == call_id
    ]
    assert document_results, f"document primitive must emit a tool_result: {frames!r}"
    result = document_results[0]["envelope"].get("result")
    assert isinstance(result, dict)
    assert result.get("tool_id") == "document"
    assert result.get("status") in {"ok", "blocked"}
    assert result.get("diff") is not None
    if result.get("status") == "ok":
        assert result.get("saved_exports"), result
        assert destination.exists()
    else:
        assert result.get("blocked_reason") == "validation_failed"
        assert not destination.exists()


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


def _write_minimal_hwpx(path: Path) -> None:
    section = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
        xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
  <hp:p><hp:run><hp:t>13 주차 </hp:t></hp:run></hp:p>
</hs:sec>
""".encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("mimetype", "application/owpml")
        package.writestr("version.xml", "<version />")
        package.writestr("Contents/header.xml", "<header />")
        package.writestr("Contents/section0.xml", section)
        package.writestr("META-INF/manifest.xml", "<manifest />")
        package.writestr("Preview/PrvText.txt", "<13 주차 >")
