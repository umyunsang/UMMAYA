# aimock Quickstart — KOSMOS Operator Guide

> **Spec**: `specs/debug-infra-rebuild/RFC.md § P0`
> **Status**: Phase 2 deliverable — OPT-IN only.
> Default KOSMOS path (real FriendliAI) is unchanged.

---

## What is aimock?

[aimock](https://aimock.copilotkit.dev/) (formerly llmock) is a deterministic fake-LLM HTTP server by CopilotKit. It serves OpenAI-compatible `/v1/chat/completions` responses from fixture JSON files, with configurable streaming physics (`ttft` / `tps` / `jitter`).

KOSMOS uses it to replace the live FriendliAI K-EXAONE endpoint in:
- CI smoke tests (bounded 5-10 s per scenario instead of 30-90 s)
- Local regression runs when FriendliAI is unavailable or rate-limited
- Reproducing specific LLM response shapes (e.g., multi-tool call regression)

---

## Prerequisites

- Docker Engine 24+ with Compose v2 (same as `docker-compose.dev.yml`)
- The `tests/fixtures/llm/` directory (already in the repo)

---

## Start aimock

```bash
# From the repo root:
docker compose -f docker-compose.aimock.yml up -d

# Verify it is healthy (takes ~10 s):
docker compose -f docker-compose.aimock.yml ps
# Expected: aimock   running (healthy)

# Optional: tail logs
docker compose -f docker-compose.aimock.yml logs -f
```

aimock listens on **`http://localhost:4010`** (override with `KOSMOS_AIMOCK_PORT` env var).

---

## Point KOSMOS at aimock

Set two environment variables **before** launching the TUI or running pytest:

```bash
export KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1
export KOSMOS_FRIENDLI_TOKEN=aimock-test
```

`KOSMOS_FRIENDLI_TOKEN` can be any non-empty string — aimock does not validate auth.

Both variables map to `LLMClientConfig` in `src/kosmos/llm/config.py` and are
picked up automatically by the existing pydantic-settings load path.

---

## Run the busan weather scenario against aimock

### Option A — TUI interactive

```bash
export KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1
export KOSMOS_FRIENDLI_TOKEN=aimock-test
bun run tui
# In the TUI, type: 부산 날씨
# Expected: aimock returns a single tool_call to lookup(kma_forecast_fetch)
#           TTFT ≈ 200 ms, TPS ≈ 50 tokens/sec
```

### Option B — tmux capture (non-interactive, recordable)

```bash
export KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1
export KOSMOS_FRIENDLI_TOKEN=aimock-test
bash scripts/tui-tmux-capture.sh /tmp/aimock-smoke \
     specs/debug-infra-rebuild/scenarios/busan-weather.sh
# Check: grep "kma_forecast_fetch" /tmp/aimock-smoke/snap-tool-dispatched.txt
```

### Option C — pytest (unit / integration, no TUI)

```bash
export KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1
export KOSMOS_FRIENDLI_TOKEN=aimock-test
uv run pytest tests/llm tests/ipc -x -q
# Suite must still pass 510+ tests.
# aimock is a transport-level drop-in; no test code changes needed.
```

---

## Stop aimock

```bash
docker compose -f docker-compose.aimock.yml down
```

---

## Fixture reference

All fixtures live in `tests/fixtures/llm/`. The server config is `tests/fixtures/llm/aimock.json`.

| File | Trigger phrase | Purpose |
|---|---|---|
| `busan-weather.json` | `부산 날씨` (contains) | Single-tool: `lookup(kma_forecast_fetch)` with valid `lat/lon/base_date/base_time` |
| `busan-multi-tool.json` | `부산 날씨 여러 도구` (contains) | Regression: emits 3 `toolCalls` — verifies `parallel_tool_calls=False` drops extras (Spec 2521 regression) |

### Fixture JSON format

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

- `match.userMessageContains` — case-sensitive substring match on the latest user message
- `match.userMessage` — exact match (use for single known phrases)
- `response.content` — plain text response (alternative to `toolCalls`)
- `response.toolCalls` — array of function calls following OpenAI tool-use schema
- `streaming.ttft` — time-to-first-token in milliseconds (default: aimock default)
- `streaming.tps` — tokens per second (default: aimock default)
- `streaming.jitter` — ±jitter in milliseconds added to each chunk delay

---

## Hard constraints (do not violate)

1. **aimock is OPT-IN**. KOSMOS runs against real FriendliAI by default. Never set
   `KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010` in `.env` committed to the repo.
2. **Do not add aimock to CI workflows** yet. That is the next Epic's job.
3. **Real-FriendliAI tests** remain gated behind `@pytest.mark.live` — aimock does not
   replace them, it supplements them.
4. **`KOSMOS_FRIENDLI_TOKEN` must remain non-empty** even for aimock — the pydantic
   validator in `LLMClientConfig` rejects blank tokens before the request reaches aimock.

---

## Fallback: aimock-bun (no Docker required)

If Docker is unavailable (Docker Desktop not installed, image pull failure, CI
constraints), use the hand-rolled Bun fallback server instead:

```bash
# Start aimock-bun on port 4010 (same port, transparent to KOSMOS code)
bun scripts/aimock-bun.ts --port 4010

# Optional: different port
bun scripts/aimock-bun.ts --port 4011
# Then: export KOSMOS_FRIENDLI_BASE_URL=http://localhost:4011/v1
```

**aimock-bun tradeoffs vs official image**:
- No Docker required — Bun is already needed for `tui/`
- Reads the same `tests/fixtures/llm/*.json` files with the same format
- Health endpoint at `/health` and `/v1/health`
- SSE streaming with configurable `ttft` / `tps` / `jitter` from fixture
- **Not** the official CopilotKit build; fixture format compatibility is
  maintained manually. See `tests/fixtures/llm/README.md` for the verified format.

**Validated 2026-05-01**: busan-weather smoke ran in ~17s with aimock-bun.

---

## Known Issues (validated 2026-05-01)

### KI-1: Docker Desktop not installed on dev machine

`/usr/local/bin/docker` is a broken symlink to the uninstalled Docker.app.
The official `ghcr.io/copilotkit/aimock:latest` image was never tested.
Use `scripts/aimock-bun.ts` as the fallback (see above). When Docker Desktop
is installed, the original `docker compose -f docker-compose.aimock.yml up -d`
path should work as documented.

### KI-2: Fixture match phrase `"부산 날씨"` was too narrow

The RFC authored `busan-weather.json` with `userMessageContains: "부산 날씨"`.
The actual scenario (`scenarios/busan-weather.sh`) sends `"부산 사하구 날씨 알려줘"`,
which does NOT contain `"부산 날씨"` as a substring (사하구 is inserted between
부산 and 날씨). Fix: `busan-weather.json` was updated to `"부산"` (2026-05-01).

Lesson: `userMessageContains` is a **byte-exact substring match** on the last
user message. Use shorter, more inclusive phrases when the scenario may vary
the exact wording.

### KI-3: Agentic loop is infinite with tool_call-only fixtures

A fixture that always returns `toolCalls` causes the KOSMOS agentic loop to
cycle: tool_result → LLM call → fixture matches → tool_call → ... indefinitely.
The smoke scenario still PASSES because the milestones (`● lookup` + `⎿ result`)
are captured before the loop runs away. The session is terminated by `/quit`.

For a clean exit: add a text-response companion fixture for the second turn,
or modify the scenario to `send_ctrlc_pane` immediately after the result is
captured.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ConnectionRefusedError: [Errno 61]` | aimock not running | `bun scripts/aimock-bun.ts --port 4010` (or Docker path if available) |
| Fixture not matched — TUI waits, no `● lookup` | `userMessageContains` phrase too narrow | Broaden match or add a catch-all fixture; see KI-2 above |
| All responses are `{"error":"no fixture matched"}` | User message doesn't match any `userMessageContains` | Add a fixture or adjust the match phrase |
| `KOSMOS_FRIENDLI_TOKEN must not be empty` | Token env var not set | `export KOSMOS_FRIENDLI_TOKEN=aimock-test` |
| Container exits immediately | Image pull failed | `docker pull ghcr.io/copilotkit/aimock:latest`; or use aimock-bun fallback |
| Port 4010 already in use | Another service on that port | `KOSMOS_AIMOCK_PORT=4011 docker compose -f docker-compose.aimock.yml up -d` or `bun scripts/aimock-bun.ts --port 4011`; set `KOSMOS_FRIENDLI_BASE_URL=http://localhost:4011/v1` |
| Agentic loop never exits | Fixture always returns toolCalls | Add a text-response fixture for the follow-up turn, or terminate with `/quit` / Ctrl-C |
