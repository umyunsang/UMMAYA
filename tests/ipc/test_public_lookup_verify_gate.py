# SPDX-License-Identifier: Apache-2.0
"""Regression tests for suppressing unrequested verify after public lookup."""

from __future__ import annotations

import json

from ummaya.ipc.stdio import _check_unrequested_verify_after_public_find
from ummaya.llm.models import ChatMessage, FunctionCall, ToolCall


def _successful_find_history() -> list[ChatMessage]:
    call = ToolCall(
        id="call-find",
        function=FunctionCall(
            name="find",
            arguments=json.dumps(
                {
                    "tool_id": "mfds_easy_drug_info_lookup",
                    "params": {"item_name": "타이레놀"},
                },
                ensure_ascii=False,
            ),
        ),
    )
    return [
        ChatMessage(role="assistant", content="", tool_calls=[call]),
        ChatMessage(
            role="tool",
            name="find",
            tool_call_id="call-find",
            content=json.dumps(
                {
                    "kind": "find",
                    "result": {
                        "kind": "collection",
                        "items": [{"품목명": "타이레놀정500밀리그람"}],
                    },
                },
                ensure_ascii=False,
            ),
        ),
    ]


def test_unrequested_check_after_public_find_is_suppressed() -> None:
    message = _check_unrequested_verify_after_public_find(
        "check",
        _successful_find_history(),
        "타이레놀 효능과 복용 주의사항을 공식 자료로 알려줘.",
    )

    assert message is not None
    assert "do NOT call check" in message
    assert "latest successful find" in message


def test_requested_check_is_not_suppressed() -> None:
    message = _check_unrequested_verify_after_public_find(
        "check",
        _successful_find_history(),
        "간편인증으로 로그인해줘.",
    )

    assert message is None


def test_non_check_call_is_not_suppressed() -> None:
    message = _check_unrequested_verify_after_public_find(
        "find",
        _successful_find_history(),
        "타이레놀 효능과 복용 주의사항을 공식 자료로 알려줘.",
    )

    assert message is None
