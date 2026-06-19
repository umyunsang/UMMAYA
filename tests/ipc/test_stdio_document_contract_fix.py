# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for root document contract repair in the stdio bridge."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from tests.ipc.test_stdio_document_dispatch import (
    _run_stdio_frames,
    _ts,
    _write_minimal_docx,
)
from ummaya.ipc.frame_schema import SessionEventFrame, ToolCallFrame


@pytest.mark.asyncio
async def test_root_document_call_recovers_contract_from_user_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "readonly-inspect.docx"
    _write_minimal_docx(source)

    session_id = str(uuid.uuid4())
    call_id = f"call-document-{uuid.uuid4().hex[:8]}"
    user_query = f"{source} document structure and blanks only. Do not modify or save it."
    document_frame = ToolCallFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tool",
        ts=_ts(),
        kind="tool_call",
        call_id=call_id,
        name="document",
        arguments={"__ummaya_user_query": user_query},
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
    serialized = json.dumps(frames, ensure_ascii=False)
    assert "Missing or invalid fields: correlation_id, document" not in serialized, serialized
    document_results = [
        frame
        for frame in frames
        if frame.get("kind") == "tool_result" and frame.get("call_id") == call_id
    ]
    assert document_results, f"document primitive must emit a tool_result: {frames!r}"
    result = document_results[0]["envelope"].get("result")
    assert isinstance(result, dict)
    assert result.get("tool_id") == "document"
    assert result.get("reason") != "invalid_params"
