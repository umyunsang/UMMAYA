# tests/fixtures/llm — LLM fixture files for aimock

> Spec: specs/debug-infra-rebuild/RFC.md § P0
> Status: Live (validated 2026-05-01 against aimock-bun fallback)

## What is this directory?

Each `*.json` file in this directory is a fixture bundle loaded by the aimock
fake-LLM server. The server scans all `*.json` files except `aimock.json`
(the server config) and loads every `fixtures[]` entry into an in-memory
match table.

When the KOSMOS Python backend POSTs to `/v1/chat/completions`, the server
checks the last user message against each fixture's `match` rule (first-match
wins, fixture file load order is alphabetical).

---

## Fixture JSON format (verified 2026-05-01)

```json
{
  "fixtures": [
    {
      "match": {
        "userMessageContains": "substring to match in the last user turn"
      },
      "response": {
        "toolCalls": [
          {
            "name": "function_name",
            "arguments": { "param": "value" }
          }
        ]
      },
      "streaming": {
        "ttft": 200,
        "tps": 50,
        "jitter": 50
      }
    }
  ]
}
```

### Field reference

| Field | Type | Description |
|---|---|---|
| `match.userMessageContains` | string | **Case-sensitive substring match** on the last user message in the conversation. Broader is safer (see Known Issues below). |
| `match.userMessage` | string | Exact-match on the last user message. |
| `response.content` | string | Plain text response to stream back. Alternative to `toolCalls`. |
| `response.toolCalls` | array | Array of function calls following OpenAI tool-use schema (see below). |
| `streaming.ttft` | number | Time-to-first-token in milliseconds. Default: 100 ms (aimock-bun). |
| `streaming.tps` | number | Tokens per second. Default: depends on server impl. |
| `streaming.jitter` | number | ±jitter in milliseconds added to each chunk delay. |

### `response.toolCalls` schema

The `name` and `arguments` fields are surfaced to the Python backend via the
**OpenAI SSE streaming format**:

```
data: {"id":"chatcmpl-…","object":"chat.completion.chunk","model":"…",
       "choices":[{"index":0,"delta":{"tool_calls":[
         {"index":0,"id":"call_…","type":"function",
          "function":{"name":"<name>","arguments":""}}
       ]},"finish_reason":null}]}

data: {"id":"chatcmpl-…","choices":[{"index":0,"delta":{"tool_calls":[
         {"index":0,"function":{"arguments":"{\"param\":\"value\"}"}}
       ]},"finish_reason":null}]}

data: {"id":"chatcmpl-…","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}

data: [DONE]
```

Arguments are streamed as JSON string fragments (20 chars/chunk by aimock-bun,
or a single chunk for the real aimock image — behavior is implementation-defined).
The Python LLM client (`src/kosmos/llm/client.py`) accumulates fragments and
delivers a complete `ToolCallFrame` to the TUI via IPC.

---

## Fixture inventory

| File | Match phrase | Purpose |
|---|---|---|
| `busan-weather.json` | `부산` (contains) | Single-tool: `lookup(kma_forecast_fetch)` with Busan coordinates. Originally `부산 날씨`; broadened to `부산` (2026-05-01) so it also matches `부산 사하구 날씨 알려줘` from `scenarios/busan-weather.sh`. |
| `busan-multi-tool.json` | `부산 날씨 여러 도구` (contains) | Regression: emits 3 `toolCalls` — verifies `parallel_tool_calls=False` drops extras (Spec 2521 regression). More specific than `busan-weather.json`, so it must be loaded first (alphabetical order guarantees this: `multi-tool` < `weather`). |

---

## Known issues

### 1. Original match phrase was wrong (fixed 2026-05-01)

The RFC authored `busan-weather.json` with `userMessageContains: "부산 날씨"`.
The actual scenario (`scenarios/busan-weather.sh`) sends `부산 사하구 날씨 알려줘`,
which does NOT contain the substring `부산 날씨` (사하구 is inserted).
Fix: changed to `"부산"` which matches both the original and the scenario phrase.

RFC format note: the fixture JSON format was **speculative** in the RFC. The
`userMessageContains` / `userMessage` field names are correct for both aimock
(official CopilotKit image) and aimock-bun (fallback). However, the match
semantics were applied to the LAST user message in the conversation history,
not the first — so after the first lookup returns and the backend re-queries
the LLM with a longer message history, the messages=[2] turn also contains
`부산` (in the original user message). This triggers the agentic loop issue below.

### 2. Agentic loop is infinite with tool_call-only fixtures

When a fixture always returns a `toolCalls` response (never a final text
answer), the KOSMOS Python backend's agentic loop will:

1. Receive tool_call → dispatch mock adapter → get timeseries result
2. Append result to conversation history → call LLM again
3. Fixture matches again (history still contains `부산`) → another tool_call
4. Repeat indefinitely until session is terminated by the user (`/quit`).

The smoke scenario still passes because the milestones (`● lookup` + `⎿ result`)
are captured before the loop spirals. For a clean exit, add a companion
`text` fixture that matches on the SECOND turn (e.g., `messages.length > 2`
or a different match phrase in the follow-up). This is deferred to a future
fixture iteration.

### 3. Docker Desktop not installed on this machine

`/usr/local/bin/docker` is a broken symlink to the uninstalled Docker.app.
The official `ghcr.io/copilotkit/aimock:latest` image was not testable.
Fallback: `scripts/aimock-bun.ts` (Bun 1.3.12) — see Known Issues in
`specs/debug-infra-rebuild/aimock-quickstart.md`.

---

## Adding a new fixture

1. Create `tests/fixtures/llm/<scenario-name>.json` with the format above.
2. Use a specific `userMessageContains` phrase to avoid matching unintended turns.
3. Restart aimock / aimock-bun (fixtures are loaded at startup; no hot-reload).
4. Test with: `curl -s -X POST http://localhost:4010/v1/chat/completions ...`
