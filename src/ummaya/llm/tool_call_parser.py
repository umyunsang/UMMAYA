# SPDX-License-Identifier: Apache-2.0
"""K-EXAONE textual <tool_call> marker parser.

K-EXAONE on FriendliAI sometimes emits its tool-call intent as a textual
``<tool_call>...</tool_call>`` marker inside the streamed assistant content
rather than the OpenAI-structured ``tool_calls`` field. The UMMAYA agentic
loop dispatches only the structured form, so without a textual extractor the
intent never round-trips into a real adapter execution.

This module is the bridge: at turn-end, the orchestrator hands the accumulated
assistant text to :func:`extract_textual_tool_calls`. The function returns
zero or more :class:`ParsedToolCall` records the orchestrator can synthesise
into ``tool_call_buf`` entries for the existing dispatch path. It also returns
the cleaned text (with the ``<tool_call>`` blocks stripped) so the citizen
never sees the marker in their reply.

Empirical K-EXAONE formats (Epic #2152 P5 smoke):

1. **OpenAI-shape JSON** (the well-formed case)::

       <tool_call>{"name": "locate", "arguments": {"location": "강남역"}}</tool_call>

2. **XML-attribute pseudo-JSON** (no quotes around keys)::

       <tool_call>{"kma_today" name="kma_today" arguments={"location": "서울"}}</tool_call>

3. **Single-key key=name dict** (no explicit ``name`` field)::

       <tool_call>{"name_nmc_emergency_search": {"query": "근처 응급실"}}</tool_call>

4. **Mixed XML body** (no JSON at all)::

       <tool_call>koroad_accident_hotspot_search
       <arg_key>location</arg_key><arg_value>어린이 보호구역</arg_value>
       </tool_call>

The parser tries each format in order; on the first match it returns. On
total parse failure it still records the raw block so the orchestrator can
log a structured warning rather than silently swallow the intent.

References (Constitution Principle I):
- ``docs/research/system-prompt-harness-comparison.md`` § Tool-call surface
- LangChain ``AgentOutputParser`` family (community baseline for textual
  tool-call extraction across non-OpenAI models)
- Anthropic prompt-engineering guide § "Tool use triggering"
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Tag boundary — non-greedy so multiple tool_call blocks in one turn are
# extracted independently. ``re.DOTALL`` so Korean / multi-line bodies match.
_TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)

# K-EXAONE can leak residual thinking tags into the visible content channel
# even when reasoning is disabled or routed through reasoning_content.
_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_TAIL_RE = re.compile(r"<think\b[^>]*>.*$", re.DOTALL | re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think\s*>", re.IGNORECASE)

# Identifier shape for both tool names and JSON keys we synthesise from.
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class ParsedToolCall:
    """One textual tool-call extracted from streamed assistant content.

    ``arguments`` is a JSON-serialisable dict; the orchestrator wraps it back
    into a JSON string before injecting into ``tool_call_buf`` so the existing
    dispatch path (which expects ``arguments: str``) stays untouched.

    ``raw`` is the original block content for diagnostic logging when parsing
    falls back to the lossy XML-mixed branch.
    """

    name: str
    arguments: dict[str, object] = field(default_factory=dict)
    raw: str = ""


def extract_textual_tool_calls(text: str) -> tuple[list[ParsedToolCall], str]:
    """Extract textual ``<tool_call>`` blocks and return cleaned text.

    Returns a tuple ``(parsed_calls, cleaned_text)``:

    - ``parsed_calls`` is the list of successfully extracted calls in
      occurrence order. An empty list means no markers were present.
    - ``cleaned_text`` has every ``<tool_call>...</tool_call>`` block removed
      so the orchestrator can stream the natural-language portion to the
      citizen without leaking the marker.

    The function never raises on malformed input — it returns whatever it can
    parse and logs a debug message for blocks it could not normalise. This
    matches the orchestrator's fail-open posture for parse failures (the
    citizen gets at least the prose; missing tool-call intent is a soft
    regression, not a crash).
    """
    blocks = _TOOL_CALL_RE.findall(text)
    if not blocks:
        return [], text

    parsed: list[ParsedToolCall] = []
    for raw_block in blocks:
        body = raw_block.strip()
        call = _try_parse_block(body)
        if call is not None:
            parsed.append(call)
        else:
            logger.debug(
                "tool_call_parser: unrecognised <tool_call> block: %r",
                body[:120],
            )

    cleaned = _TOOL_CALL_RE.sub("", text)
    return parsed, cleaned


def strip_leaked_thinking_markers(text: str) -> str:
    """Remove model thinking XML that leaked into citizen-visible prose."""
    if "<think" not in text.lower() and "</think" not in text.lower():
        return text
    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _THINK_OPEN_TAIL_RE.sub("", cleaned)
    cleaned = _THINK_CLOSE_RE.sub("", cleaned)
    return cleaned.lstrip()


def _try_parse_block(body: str) -> ParsedToolCall | None:
    """Try each known K-EXAONE textual format in order; first match wins."""
    return (
        _try_openai_shape_json(body)
        or _try_single_key_dict(body)
        or _try_xml_attr_pseudo_json(body)
        or _try_mixed_xml(body)
    )


def _try_openai_shape_json(body: str) -> ParsedToolCall | None:
    """Format 1 — well-formed JSON with ``name`` and ``arguments`` keys."""
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    name = obj.get("name")
    args = obj.get("arguments")
    if isinstance(name, str) and name and isinstance(args, dict):
        return ParsedToolCall(name=name, arguments=dict(args), raw=body)
    return None


def _try_single_key_dict(body: str) -> ParsedToolCall | None:
    """Format 3 — ``{"name_X": Y}`` where the single key is the tool name
    (often prefixed with ``name_`` and / or quoted) and the value is the
    arguments dict."""
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or len(obj) != 1:
        return None
    (only_key, only_val) = next(iter(obj.items()))
    if not isinstance(only_key, str) or not isinstance(only_val, dict):
        return None
    name = only_key.removeprefix("name_") if only_key.startswith("name_") else only_key
    if not _IDENT_RE.fullmatch(name):
        return None
    return ParsedToolCall(name=name, arguments=dict(only_val), raw=body)


def _try_xml_attr_pseudo_json(body: str) -> ParsedToolCall | None:
    """Format 2 — ``{"X" name="X" arguments={...}}`` using XML-attribute syntax.

    Strategy: locate the ``name="<ident>"`` clause and the ``arguments=`` clause,
    then balance-match the inner JSON object after ``arguments=`` so the outer
    wrapper ``}`` doesn't over-match (greedy regex fails on the closing pair).
    """
    name_m = re.search(r'name\s*=\s*"([A-Za-z_][A-Za-z0-9_]*)"', body)
    args_pos = re.search(r"arguments\s*=\s*", body)
    if not name_m or not args_pos:
        return None
    name = name_m.group(1)
    args_text = _balanced_json_object(body, args_pos.end())
    if args_text is None:
        return None
    try:
        args = json.loads(args_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(args, dict):
        return None
    return ParsedToolCall(name=name, arguments=dict(args), raw=body)


def _balanced_json_object(text: str, start: int) -> str | None:
    """Return the substring of ``text`` starting at ``start`` that forms a
    balanced ``{...}`` JSON object, or ``None`` if no opening brace is at or
    after ``start`` or the braces never balance.

    Honours JSON string-literal escaping so a ``"}"`` inside a string does not
    close the outer object prematurely.
    """
    open_idx = text.find("{", start)
    if open_idx == -1:
        return None
    state = _BraceScanState()
    for i in range(open_idx, len(text)):
        if state.advance(text[i]) and i > open_idx:
            return text[open_idx : i + 1]
    return None


class _BraceScanState:
    """Tiny state machine for ``_balanced_json_object`` brace tracking.

    Extracted to keep the surrounding helper below the C901 complexity limit
    while preserving the exact semantics: depth counter + JSON string-literal
    escape awareness. ``advance`` returns True when the current character
    closed the outer brace (depth dropped back to 0).
    """

    __slots__ = ("depth", "in_string", "escape")

    def __init__(self) -> None:
        self.depth = 0
        self.in_string = False
        self.escape = False

    def advance(self, ch: str) -> bool:
        if self.in_string:
            if self.escape:
                self.escape = False
            elif ch == "\\":
                self.escape = True
            elif ch == '"':
                self.in_string = False
            return False
        if ch == '"':
            self.in_string = True
            return False
        if ch == "{":
            self.depth += 1
            return False
        if ch == "}":
            self.depth -= 1
            return self.depth == 0
        return False


class StreamGate:
    """Streaming filter that hides ``<tool_call>...</tool_call>`` blocks from a
    citizen-facing stream.

    K-EXAONE on FriendliAI sometimes emits BOTH a structured ``tool_calls``
    field AND a textual ``<tool_call>`` block in the same turn — so even
    when the orchestrator dispatches the structured form, the textual marker
    leaks into the streaming `assistant_chunk` content and is shown to the
    citizen as raw markup.

    Usage::

        gate = StreamGate()
        for chunk in stream:
            visible = gate.feed(chunk)
            if visible:
                emit(visible)
        tail = gate.flush()
        if tail:
            emit(tail)

    Stripping is character-accurate — partial markers split across chunk
    boundaries are buffered until a decision can be made. Returns only the
    bytes that should be visible to the citizen; the raw text (with markers)
    is still recoverable from the original stream for the
    ``extract_textual_tool_calls`` post-stream pass.
    """

    _OPEN = "<tool_call>"
    _CLOSE = "</tool_call>"

    __slots__ = ("_pending", "_in_block")

    def __init__(self) -> None:
        self._pending: str = ""
        self._in_block: bool = False

    def feed(self, chunk: str) -> str:
        """Return whatever portion of ``chunk`` is safe to emit right now."""
        if not chunk:
            return ""
        self._pending += chunk
        out: list[str] = []
        while self._pending:
            if self._in_block:
                close_idx = self._pending.find(self._CLOSE)
                if close_idx == -1:
                    # Keep the last len(_CLOSE)-1 chars in case the closing
                    # tag straddles a future chunk; drop everything else.
                    keep = len(self._CLOSE) - 1
                    if len(self._pending) > keep:
                        self._pending = self._pending[-keep:]
                    return "".join(out)
                # Closing tag found — drop everything up to and including it.
                self._pending = self._pending[close_idx + len(self._CLOSE) :]
                self._in_block = False
                continue

            open_idx = self._pending.find(self._OPEN)
            if open_idx != -1:
                if open_idx > 0:
                    out.append(self._pending[:open_idx])
                self._pending = self._pending[open_idx + len(self._OPEN) :]
                self._in_block = True
                continue

            # No opening tag yet. Emit everything except the trailing window
            # that could be the prefix of an opening tag in the next chunk.
            keep = len(self._OPEN) - 1
            if len(self._pending) > keep:
                out.append(self._pending[:-keep])
                self._pending = self._pending[-keep:]
            return "".join(out)
        return "".join(out)

    def flush(self) -> str:
        """Drain any safely-emittable pending bytes at end of stream.

        If we're inside an unfinished ``<tool_call>`` block at flush time the
        block is dropped (best-effort match for the post-stream parser to pick
        up via the full accumulated text). If we're between blocks, the
        pending lookahead window is emitted as plain text.
        """
        if self._in_block:
            self._pending = ""
            self._in_block = False
            return ""
        out = self._pending
        self._pending = ""
        return out


def _try_mixed_xml(body: str) -> ParsedToolCall | None:
    """Format 4 — bare tool name on the first line followed by interleaved
    ``<arg_key>k</arg_key><arg_value>v</arg_value>`` pairs."""
    head = body.split("\n", 1)[0].strip()
    name_m = _IDENT_RE.match(head)
    if not name_m:
        return None
    name = name_m.group(0)
    pairs = re.findall(
        r"<arg_key>(.*?)</arg_key>\s*<arg_value>(.*?)</arg_value>",
        body,
        re.DOTALL,
    )
    if not pairs:
        return None
    args: dict[str, object] = {}
    for k, v in pairs:
        args[k.strip()] = v.strip()
    return ParsedToolCall(name=name, arguments=args, raw=body)
