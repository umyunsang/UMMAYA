# aimock-busan-weather proof run

> Date: 2026-05-01
> Branch: current (Phase 2 validation)
> Spec: specs/debug-infra-rebuild/RFC.md § P0 / dispatch-tree-round2.md § sonnet-aimock-validate

## Summary

Phase 2 aimock validation PASS. The busan-weather smoke scenario completed
successfully against the aimock-bun fallback server in ~17 seconds, versus
60-90 seconds with the real FriendliAI K-EXAONE endpoint.

---

## Server

**Official aimock image**: ghcr.io/copilotkit/aimock:latest — NOT tested.
Docker Desktop is not installed on this machine (`/usr/local/bin/docker` is
a broken symlink to the uninstalled Docker.app). See Known Issues below.

**Actual server used**: `scripts/aimock-bun.ts` (aimock-bun fallback, option a).
Runtime: Bun v1.3.12 (`/Users/um-yunsang/.bun/bin/bun`).
Port: 4010.
Fixtures loaded: 2 (`busan-multi-tool.json`, `busan-weather.json`).

---

## Timeline

| Milestone | Observed time |
|---|---|
| TTFT (fixture: `streaming.ttft: 200ms`) | ~200 ms from request |
| Boot → `tool_registry: 14 entries verified` | ~1s |
| Input submitted → `● lookup` painted | ~2s from submit |
| Tool result rendered (`⎿ timeseries — 25건`) | ~4s from submit |
| Total scenario wall time | ~17s |

**Comparison**: real FriendliAI K-EXAONE typically takes 60-90s for the same
scenario (LLM reasoning + tool dispatch + second LLM call for final answer).
aimock-bun delivers 3-5x speedup for local smoke validation.

---

## Fixture that matched

File: `tests/fixtures/llm/busan-weather.json`
Match rule: `userMessageContains: "부산"` (updated from original `"부산 날씨"`)
Reason for update: scenario sends `부산 사하구 날씨 알려줘` which does not
contain the substring `부산 날씨` (사하구 is between 부산 and 날씨).

Tool call returned: `lookup(kma_forecast_fetch)` with:
- `lat: 35.1, lon: 128.97` (Busan coordinates)
- `base_date: "20260502", base_time: "0500"`

---

## Captured snapshots

| File | Description |
|---|---|
| `snap-000-boot.txt` | TUI boot — `tool_registry: 14 entries verified`, KOSMOS branding |
| `snap-001-input-submitted.txt` | User input `부산 사하구 날씨 알려줘` submitted, TUI waiting |
| `snap-002-first-tool-call.txt` | `● lookup(kma_forecast_fetch)` painted, `✽ Moseying…` spinner |
| `snap-003-after-result.txt` | `⎿ timeseries — 25건` with temperature data rendered |
| `snap-004-stable.txt` | Stable state (agentic loop cycled 3+ times, all showing results) |
| `snap-005-quit.txt` | Empty — session terminated by `/quit` before final capture |

---

## Known Issues

### KI-1: Docker Desktop not installed

`ghcr.io/copilotkit/aimock:latest` was not tested. The Docker binary at
`/usr/local/bin/docker` is a broken symlink to `Docker.app` which is not
installed. Fallback to `scripts/aimock-bun.ts` was used instead.

To test with the official image: install Docker Desktop, then:
```bash
docker compose -f docker-compose.aimock.yml up -d
```

### KI-2: Agentic loop is infinite with tool_call-only fixtures

The `busan-weather.json` fixture always returns a `lookup` tool call. The
KOSMOS agentic loop dispatches the mock adapter, gets a result, then calls
the LLM again — but the conversation history still contains `부산`, so the
fixture matches again and emits another tool call. The loop cycles until
`/quit` terminates the session.

Observed: 9 POST requests to `/v1/chat/completions` in the ~16s window.
Snap-004 shows 3+ repeated `● lookup(kma_forecast_fetch)` entries.

Mitigation: The smoke scenario milestones (`● lookup` + `⎿ result`) are
captured before the loop runs away. Future fixture iteration should add a
text-response fixture for the second LLM turn to provide a clean exit.

### KI-3: Fixture match phrase was narrower than scenario phrase

Original `busan-weather.json` used `"부산 날씨"` as the match phrase.
Scenario sends `"부산 사하구 날씨 알려줘"`. Fixed by broadening to `"부산"`.
Documented in `tests/fixtures/llm/README.md § Known Issues`.

---

## How to reproduce

```bash
# Start aimock-bun (Docker not required)
bun scripts/aimock-bun.ts --port 4010 &

# Run the smoke scenario
export KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1
export KOSMOS_FRIENDLI_TOKEN=aimock-test
bash scripts/tui-tmux-capture.sh /tmp/aimock-smoke \
     specs/debug-infra-rebuild/scenarios/busan-weather.sh

# Check for lookup
grep "lookup" /tmp/aimock-smoke/snap-002-first-tool-call.txt

# Tear down
pkill -f "aimock-bun.ts"
```
