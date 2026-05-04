# Research: StreamGate render-order (Epic #2766 issue B)

## Diagnosis

K-EXAONE on FriendliAI (Hermes-style function calling) emits stream events in
this order in turn-1 of a tool-using flow:

```
content_delta {"content": "병원을 검색해 보겠습니다."}    <-- preamble prose
tool_call_delta {function_name: "lookup", function_args_delta: "..."}
done
```

The pre-fix backend (`src/kosmos/ipc/stdio.py:1633-1650`) immediately wrote the
`content_delta` payload as an `assistant_chunk` IPC frame. The TUI's
`StreamingMarkdown` rendered it as the assistant's prose body. Then the
`tool_call_delta` events accumulated into `tool_call_buf` and dispatched at
end-of-stream as a `tool_call` IPC frame.

**Citizen-visible result**: `⏺ 병원을 검색해 보겠습니다. → ⏺ lookup(...) → ⎿ record`
(prose BEFORE tool_call). User reported this as "도구 사용 결과 화면 순서 거꾸로".

**CC convention**: `⏺ tool_use → ⎿ tool_result → ⏺ assistant prose`. CC's
LLM (Anthropic) rarely emits prose preamble; it emits `tool_use` blocks
directly. The render order naturally matches.

## Fix

`src/kosmos/ipc/stdio.py` — Buffer `content_delta` chunks during the stream
into a turn-local `buffered_visible: list[str]`. After the stream completes:

- If `tool_call_buf` is empty → join the buffer and emit as a single
  `assistant_chunk` (then terminal `done=True`). The streaming typewriter
  effect is lost on no-tool turns; this is the cost of the ordering guarantee
  (we cannot know whether a tool_call will follow until the stream ends).
- If `tool_call_buf` is non-empty → discard the buffer entirely. The next
  agentic-loop turn produces the real answer after `tool_result` is appended
  to context. CC-style ordering preserved.

## Decision

Path: **suppress preamble in tool-call turns; emit single buffered chunk on
no-tool turns**. Rejected paths:

- (a) Modify `StreamGate` to look for `<tool_call>` open marker — only catches
  the *textual* fallback path; structured `tool_call_delta` events do NOT pass
  through `StreamGate`.
- (b) `tool_choice="required"` — would force a tool every turn, breaking
  conversational flows.
- (c) System prompt rule "tool-call turn = no answer" — LLM-soft, frequently
  ignored (memory `feedback_llm_api_option_first_suspect` says LLM rules are
  not hard constraints).

Defense-in-depth tier: backend buffer guard (THIS) + existing
`parallel_tool_calls=False` API (`src/kosmos/llm/client.py:1002`) + future
system prompt hint can stack.

## Test

`tests/ipc/test_stdio.py::test_render_order_tool_call_emitted_before_preamble_prose`
— synthetic K-EXAONE stream emits `content_delta` then `tool_call_delta`;
asserts no `assistant_chunk` carrying non-empty `delta` for the turn-1
`message_id` precedes the `tool_call` IPC frame.
