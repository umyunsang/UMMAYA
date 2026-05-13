# SPDX-License-Identifier: Apache-2.0
"""Tests for the K-EXAONE textual <tool_call> marker parser (Epic #2152).

The four canonical input formats come from the live Epic #2152 P5 smoke run
(specs/2152-system-prompt-redesign/smoke-stdio-*.jsonl). Every test asserts
both extraction (parsed call) and stripping (cleaned text) so the citizen
never sees the marker.
"""

from __future__ import annotations

from ummaya.llm.tool_call_parser import (
    ParsedToolCall,
    StreamGate,
    extract_textual_tool_calls,
    strip_leaked_thinking_markers,
)


def test_no_markers_returns_text_unchanged() -> None:
    text = "안녕하세요. 무엇을 도와드릴까요?"
    calls, cleaned = extract_textual_tool_calls(text)
    assert calls == []
    assert cleaned == text


def test_format1_openai_shape_json() -> None:
    text = '<tool_call>{"name": "locate", "arguments": {"location": "강남역"}}</tool_call>'
    calls, cleaned = extract_textual_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "locate"
    assert calls[0].arguments == {"location": "강남역"}
    assert "<tool_call>" not in cleaned


def test_format3_single_key_dict_with_name_prefix() -> None:
    text = '<tool_call>{"name_nmc_emergency_search": {"query": "근처 응급실"}}</tool_call>'
    calls, _ = extract_textual_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "nmc_emergency_search"
    assert calls[0].arguments == {"query": "근처 응급실"}


def test_format3_single_key_dict_without_prefix() -> None:
    text = '<tool_call>{"locate": {"location": "강남역"}}</tool_call>'
    calls, _ = extract_textual_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "locate"
    assert calls[0].arguments == {"location": "강남역"}


def test_format2_xml_attr_pseudo_json() -> None:
    text = '<tool_call>{"kma_today" name="kma_today" arguments={"location": "서울"}}</tool_call>'
    calls, cleaned = extract_textual_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "kma_today"
    assert calls[0].arguments == {"location": "서울"}
    assert cleaned.strip() == ""


def test_format4_mixed_xml_body() -> None:
    text = (
        "<tool_call>koroad_accident_hotspot_search\n"
        "<arg_key>location</arg_key><arg_value>어린이 보호구역</arg_value>\n"
        "<arg_key>accident_type</arg_key><arg_value>사고 다발</arg_value>\n"
        "</tool_call>"
    )
    calls, _ = extract_textual_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "koroad_accident_hotspot_search"
    assert calls[0].arguments == {
        "location": "어린이 보호구역",
        "accident_type": "사고 다발",
    }


def test_marker_stripped_from_surrounding_prose() -> None:
    text = (
        "기상청 자료를 확인하겠습니다.\n"
        '<tool_call>{"name": "kma_forecast_fetch", '
        '"arguments": {"region": "서울"}}</tool_call>\n'
        "잠시 기다려 주세요."
    )
    calls, cleaned = extract_textual_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "kma_forecast_fetch"
    # The natural-language portions survive; only the marker is removed.
    assert "기상청 자료를 확인하겠습니다" in cleaned
    assert "잠시 기다려 주세요" in cleaned
    assert "<tool_call>" not in cleaned
    assert "</tool_call>" not in cleaned


def test_multiple_markers_in_one_turn() -> None:
    text = (
        '<tool_call>{"name": "locate", '
        '"arguments": {"location": "강남역"}}</tool_call>'
        " 이어서 "
        '<tool_call>{"name": "kma_forecast_fetch", '
        '"arguments": {"region": "서울"}}</tool_call>'
    )
    calls, cleaned = extract_textual_tool_calls(text)
    assert len(calls) == 2
    assert [c.name for c in calls] == ["locate", "kma_forecast_fetch"]
    assert "<tool_call>" not in cleaned


def test_unparseable_block_logged_and_skipped() -> None:
    """A totally unrecognised body is dropped from the parsed list but
    still stripped from the cleaned text — fail-open so the citizen sees
    at least the prose."""
    text = "<tool_call>completely garbled !@#$%^&*()</tool_call>"
    calls, cleaned = extract_textual_tool_calls(text)
    assert calls == []
    assert "<tool_call>" not in cleaned


def test_parsed_tool_call_is_frozen() -> None:
    """ParsedToolCall is a frozen dataclass — immutable contract."""
    import dataclasses

    import pytest

    call = ParsedToolCall(name="x", arguments={"a": 1})
    with pytest.raises(dataclasses.FrozenInstanceError):
        call.name = "y"  # type: ignore[misc]


def test_extract_returns_text_when_only_garbled_marker() -> None:
    """No markers → cleaned == original (identity preservation)."""
    text = "단순 텍스트만 있고 마커는 없음"
    calls, cleaned = extract_textual_tool_calls(text)
    assert calls == []
    assert cleaned is text  # same object — no copy


def test_xml_attr_with_korean_argument_value() -> None:
    """K-EXAONE pseudo-JSON arguments often hold Korean strings — must
    survive json.loads round-trip without escaping."""
    text = '<tool_call>{"x" name="x" arguments={"city": "부산광역시"}}</tool_call>'
    calls, _ = extract_textual_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].arguments == {"city": "부산광역시"}


def test_strip_leaked_thinking_markers_removes_dangling_close_tag() -> None:
    text = "</think>\n\n현재 날씨를 확인했습니다."
    assert strip_leaked_thinking_markers(text) == "현재 날씨를 확인했습니다."


def test_strip_leaked_thinking_markers_removes_complete_block() -> None:
    text = "<think>internal trace</think>\n최종 답변입니다."
    assert strip_leaked_thinking_markers(text) == "최종 답변입니다."


# ---------------------------------------------------------------------------
# StreamGate — character-accurate streaming filter
# ---------------------------------------------------------------------------


def _drive(gate: StreamGate, chunks: list[str]) -> str:
    out = "".join(gate.feed(c) for c in chunks)
    out += gate.flush()
    return out


def test_stream_gate_passthrough_when_no_marker() -> None:
    gate = StreamGate()
    assert _drive(gate, ["안녕하세요. ", "무엇을 ", "도와드릴까요?"]) == (
        "안녕하세요. 무엇을 도와드릴까요?"
    )


def test_stream_gate_strips_complete_marker_in_one_chunk() -> None:
    gate = StreamGate()
    chunk = (
        "기상청 자료를 확인합니다.\n"
        '<tool_call>{"name": "find", "arguments": {"q": "서울"}}</tool_call>\n'
        "잠시만 기다려 주세요."
    )
    out = _drive(gate, [chunk])
    assert out == "기상청 자료를 확인합니다.\n\n잠시만 기다려 주세요."
    assert "<tool_call>" not in out


def test_stream_gate_strips_marker_split_across_chunks() -> None:
    """Streaming chunks may split the marker boundary at any character."""
    gate = StreamGate()
    chunks = [
        "안녕 ",
        "<tool_",
        'call>{"name":',
        ' "find", "arguments":',
        ' {"q": "x"}}</tool',
        "_call>",
        " 끝.",
    ]
    out = _drive(gate, chunks)
    assert out == "안녕  끝."


def test_stream_gate_handles_multiple_markers() -> None:
    gate = StreamGate()
    text = 'A<tool_call>{"name":"t1"}</tool_call>B<tool_call>{"name":"t2"}</tool_call>C'
    out = _drive(gate, [text])
    assert out == "ABC"


def test_stream_gate_drops_unfinished_block_at_flush() -> None:
    """If the stream ends mid-block (network drop, model truncation), the
    pending block is dropped rather than leaked. The post-stream parser can
    still recover the call from the raw accumulated text."""
    gate = StreamGate()
    chunks = ["B4 ", '<tool_call>{"name":"x', '", "arguments":']
    out = _drive(gate, chunks)
    assert out == "B4 "


def test_stream_gate_emits_lookahead_window_on_flush_when_safe() -> None:
    """If we're not in a block and there's a short pending window that
    couldn't have been the start of <tool_call>, flush emits it."""
    gate = StreamGate()
    chunks = ["abc"]  # too short to be a marker prefix
    out = _drive(gate, chunks)
    assert out == "abc"


def test_stream_gate_partial_open_tag_treated_as_text() -> None:
    """A '<' that is NOT followed by 'tool_call>' must be emitted as text.
    Stream ends with just the '<' character — flush emits it."""
    gate = StreamGate()
    chunks = ["hello < world"]
    out = _drive(gate, chunks)
    assert out == "hello < world"
