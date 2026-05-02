# RFC — KOSMOS 디버깅 인프라 재구축

> **Status**: Draft / 2026-05-02 작성
> **Trigger**: Spec 2521 의 4시간 디버깅 시 자동화 PTY smoke (asciinema + expect + pyte) 가 K-EXAONE on FriendliAI 의 reasoning latency (30-90s) 를 hang 으로 오판 → 잘못된 결론 누적
> **Author**: Lead Opus (커뮤니티 deep research 결과 반영)

---

## § 1. 문제 정의

### 1.1 이번 사건의 결정적 오해

| 시점 | 자동화 smoke 의 결론 | 실제 상태 |
|---|---|---|
| 90s timeout | "K-EXAONE 가 응답 없음" | reasoning_content 진행 중 (정상) |
| `· Cooking…` 만 보임 | "TUI 가 hang" | 실제 9-15s 후에 첫 tool_call paint (사용자 환경 검증) |
| `Invalid parameters` 가 모든 도구 | "도구 시스템 깨짐" | 시스템 프롬프트 suffix 가 schema 정보 안 줌 (token budget 핑계) |
| layout 고치는 fix 가 효과 없음 | "fix 잘못 됐음" | 실제 Bun cache + 잘못된 가설 + smoke 오판 복합 |

각각 **자동화가 거짓 음성을 만들어낸 사례**. 사용자 인터렉티브 환경에서는 즉시 진짜 상태가 보임.

### 1.2 root cause — 자동화 stack 의 결함

1. **PTY-in-PTY nesting** — `asciinema rec --command "expect ..."` 는 asciinema 가 PTY 를 잡고 expect 가 그 안에서 새 PTY 를 spawn 함. asciinema 의 [issue #250](https://github.com/asciinema/asciinema/issues/250) 에 명시된 design 한계 — race / buffer 이슈 발생.
2. **Hardcoded sleep** — `.expect`/`.tape` 의 `Sleep 6` 같은 wall-clock 대기. K-EXAONE reasoning 길이는 6s 가 될 수도 90s 가 될 수도 있음. ardalis ["Thread Sleep in Tests is Evil"](https://ardalis.com/thread-sleep-in-tests-is-evil/) 의 정확한 anti-pattern.
3. **Real LLM in CI** — FriendliAI 가용성 / queue / Tier RPM 에 의존. 응답 시간 비결정적.
4. **Mock 위치 잘못** — 어댑터 함수 단위 mock 보다 *transport 레이어 mock* 이 정답 (arxiv [2602.00409](https://arxiv.org/html/2602.00409v1) "Are Coding Agents Generating Over-Mocked Tests?" 의 결론).
5. **Final-frame fallacy** — `lastFrame()` 만 보고 PASS/FAIL 판정. 80ms transient flash 안 보임.

## § 2. 커뮤니티 레퍼런스 (deep research 요약)

### 2.1 LLM call replay / VCR-style cassettes

| 도구 | 평가 | KOSMOS 적합도 |
|---|---|---|
| [vcr-langchain](https://github.com/amosjyng/vcr-langchain) | 모ngkeypatch 기반, adapter 가 patched scope 밖에서 HTTP 하면 leak | 🟡 부분 |
| [llmock / aimock](https://aimock.copilotkit.dev/) | **HTTP server 형태 + `ttft`/`tps`/`jitter` knob** | 🟢 정확히 우리 문제 |
| [LiteLLM `mock_response`](https://docs.litellm.ai/docs/load_test) | 간단 mock, streaming-physics knob 없음 | 🟡 unit-only |
| [llm-test-harness](https://pypi.org/project/llm-test-harness/) | record/replay + eval | 🟡 docs 부족 |

### 2.2 TUI testing — Ink + 친척

| 도구 | 평가 | KOSMOS 적합도 |
|---|---|---|
| [ink-testing-library](https://github.com/vadimdemedes/ink-testing-library) | 이미 사용 중. `.frames` 배열은 underused (per-render snapshot stream) | 🟢 underused |
| [react-render-stream-testing-library](https://github.com/testing-library/react-render-stream-testing-library) | "createSnapshots after every render + iterate via takeSnapshot" 패턴. React-DOM 전용이지만 Ink 로 포팅 가능 | 🟢 패턴 차용 |
| [VHS (charmbracelet)](https://github.com/charmbracelet/vhs) | wall-clock Sleep only, [issue #715](https://github.com/charmbracelet/vhs/issues/715) — streaming agentic UI 에 안 맞음 | 🔴 부적합 |
| [teatest](https://carlosbecker.com/posts/teatest/) (Bubble Tea) | **`WaitFor(predicate, deadline)` 가 정답 패턴** | 🟢 Ink 로 포팅 |
| [catwalk](https://github.com/knz/catwalk) | golden-file driven, deterministic | 🟡 학습용 |
| [tmux capture-pane](https://jmlago.github.io/skills/debug-tuis-with-tmux.html) | asciinema-in-asciinema 회피 표준 | 🟢 P2 |

### 2.3 Trace observability

| 도구 | "did the LLM stream X bytes by T?" 답할 수 있나? | "did UI paint Y at frame K?" 답할 수 있나? |
|---|---|---|
| Langfuse (이미 사용) | 🟡 chunk 별 timestamp 없이 flat list | 🔴 |
| [Phoenix (Arize)](https://arize.com/docs/phoenix/tracing/how-to-tracing/importing-and-exporting-traces/retrieve-traces-via-cli) | 🟢 traces.json export + replay | 🟡 (지원하지만 직접 instrument 필요) |
| OpenLLMetry | 🟢 (instrumentation only — Langfuse 로 수집) | 🔴 |
| OTEL GenAI semconv | 🟢 (`gen_ai.request.streaming` + chunk events) | 🟡 (`kosmos.tui.*` 우리가 추가) |
| **공통 gap** | 모든 tracing 이 LLM 만 본다 — UI 와 동기 안 됨 ([dev.to The Missing Layer](https://dev.to/custodiaadmin/the-missing-layer-in-langsmith-langfuse-and-helicone-visual-replay-21gk)) |

### 2.4 결정적 anti-pattern

- "Hardcoded waits = #1 cause of flaky tests" — [DevAssure article](https://devassure.medium.com/flaky-tests-from-race-conditions-root-causes-and-fixes-eb345bb0c39f)
- "Asciinema-in-asciinema PTY conflict" — asciinema 자체 issue
- Mock 레이어 잘못 — adapter func 가 아니라 HTTP transport — arxiv 2602.00409
- Real LLM in CI smokes — TanStack [137-tests-7-providers](https://tanstack.com/blog/how-we-test-tanstack-ai-across-7-providers) 가 명시적으로 anti-pattern 으로 다룸

## § 3. 권장 인프라 — Priority 순

### P0 — `aimock` 로 FriendliAI 를 CI 에서 분리 (🔥 단일 최고 leverage)

**무엇**: [aimock.copilotkit.dev](https://aimock.copilotkit.dev/) 를 Docker 컨테이너로 CI 에서 띄우고 `KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010` 로 가리킴.

**왜**: K-EXAONE 의 30-90s reasoning_content 길이가 자동화 smoke 의 timeout 비결정성의 root cause. aimock 의 `ttft`/`tps`/`jitter` knob 으로 *real-feeling* streaming 을 *bounded* 시간에 재현. fixture 는 `match: userMessage`, `response: { content, tool_calls }`, `opts: { ttft, tps, chunkSize }` 로 정의. 한 fixture = 한 시나리오 = 한 결정론적 smoke.

**KOSMOS 적용**:
```
# CI Docker compose
services:
  aimock:
    image: copilotkit/llmock:latest
    ports: ["4010:4010"]
    volumes: ["./tests/fixtures/llm:/fixtures"]
    environment:
      LLMOCK_FIXTURE_DIR: /fixtures

# Test env
env:
  KOSMOS_FRIENDLI_BASE_URL: http://localhost:4010/v1
  KOSMOS_FRIENDLI_TOKEN: aimock-fake-token
```

Fixture 예시 (`tests/fixtures/llm/busan-weather.json`):
```json
{
  "match": { "user_message_contains": "부산 날씨" },
  "response": {
    "tool_calls": [{
      "name": "lookup",
      "arguments": {
        "tool_id": "kma_forecast_fetch",
        "params": {
          "lat": 35.1, "lon": 128.97,
          "base_date": "20260502", "base_time": "0500"
        }
      }
    }]
  },
  "opts": { "ttft": 200, "tps": 50, "jitter": 50 }
}
```

**효과**: smoke 가 항상 ~5초에 끝남. timeout 90s → 15s. invalid_params 같은 회귀가 *fixture 자체* 를 깨뜨려 즉시 fail.

### P1 — `waitForFrame(predicate, deadline)` helper (Ink 용 teatest 포트)

**무엇**: ink-testing-library 의 `render()` 가 반환하는 `frames` 배열을 polled-with-deadline 으로 wait. 모든 `Sleep 6` 같은 hardcoded sleep 제거.

**왜**: teatest 의 `WaitFor` 패턴이 Bubble Tea 진영의 표준 ([Pattern Matched playbook](https://patternmatched.substack.com/p/testing-bubble-tea-interfaces)). KOSMOS 의 `.expect` script 의 모든 `Sleep <wallclock>` 는 K-EXAONE latency 변동에 민감해서 무용지물.

**구현**: `tui/src/test-utils/waitForFrame.ts` (코드 § 4 참조).

**효과**: spec 별 smoke 의 wall-clock 의존도 0. K-EXAONE 빨라지면 빨리 끝나고 느려지면 deadline 에서 명확한 reason 으로 fail.

### P2 — tmux capture-pane harness (asciinema-in-asciinema 대체)

**무엇**: `scripts/tui-tmux-capture.sh` 신설:
```bash
tmux new-session -d -s kosmos 'bun run tui'
tmux send-keys -t kosmos '부산 날씨 알려줘' Enter
# polled wait until predicate
until tmux capture-pane -t kosmos -p | grep -q "● lookup"; do sleep 0.3; done
tmux capture-pane -t kosmos -p > frame_lookup.txt
```

**왜**: asciinema 의 PTY-nesting 제약 ([issue #250](https://github.com/asciinema/asciinema/issues/250)) 회피. 출력은 plain UTF-8 (ANSI 해석 없음) → grep 가능.

**효과**: 자동화 smoke 가 진짜 사용자 환경과 동일한 PTY 동작 재현. nesting race 0.

### P3 — Per-render Ink snapshot stream

**무엇**: `lastFrame()` 만 보지 말고 `frames` 배열 *전체* 를 hash + sequence assert. [react-render-stream](https://github.com/testing-library/react-render-stream-testing-library) 의 `takeSnapshot` 패턴 차용.

**왜**: AGENTS.md anti-pattern #1 ("Final-state fallacy") 정확한 fix. 80ms transient flash 도 감지.

**구현 규칙**:
```ts
const { frames } = render(<App />)
expect(frames.map(hash)).toEqual([
  hash(initialFrame),
  hash(thinkingShown),
  hash(toolCallShown),
  hash(resultShown),
])
```

### P4 — OTEL `kosmos.llm.chunk` + `kosmos.tui.frame_commit` span events

**무엇**: 두 새 OTEL span event:
- `kosmos.llm.chunk` — backend 가 stream 받을 때마다 emit. attributes: `correlation_id`, `bytes`, `delta_ms_since_first_token`, `channel: content|reasoning|tool_call`
- `kosmos.tui.frame_commit` — frontend Ink reconcile 마다 emit. attributes: `correlation_id`, `frame_hash`, `frame_seq`

**왜**: Spec 028 의 OTLP collector → Langfuse 흐름이 이미 깔려 있음. 이 두 event 로 *"X bytes 가 T 에 도착했고 UI 가 K frame 에서 paint 했다"* 의 진실 재구성 가능. [Phoenix 의 traces.json export](https://arize.com/docs/phoenix/tracing/how-to-tracing/importing-and-exporting-traces/retrieve-traces-via-cli) 와 호환.

**효과**: bug report = "Langfuse trace 링크 + frame_commit sequence". CC 의 anti-pattern #2 (grep-as-proof) 영구 폐지.

### P5 — `KosmosCassette` (vcr-langchain 스타일, optional)

**무엇**: aimock 보다 더 가벼운 unit-test layer. `httpx.AsyncClient.send` monkey-patch 로 cassette JSONL 기록/replay.

**왜**: aimock 가 fixture 가 너무 많아질 때 의 fallback. JSONL 형식이 grep + diff 가능.

**우선순위 낮음 — Phase 2 후 결정**.

## § 4. 컴포넌트별 코드 골격

### 4.1 `tui/src/test-utils/waitForFrame.ts` (P1)

```typescript
// SPDX-License-Identifier: Apache-2.0
// Spec: debug-infra-rebuild RFC § P1
// Inspired by Bubble Tea's teatest WaitFor pattern.

import type { render } from 'ink-testing-library'

type RenderResult = ReturnType<typeof render>

export interface WaitForFrameOpts {
  /** 폴링 간격 ms. Default 10. */
  intervalMs?: number
  /** 데드라인 ms. Default 10_000. */
  deadlineMs?: number
  /** 실패 시 진단 메시지. */
  describe?: string
}

/**
 * Poll lastFrame() / frames every intervalMs until predicate(true) or deadline.
 * Replaces every wall-clock `Sleep <N>` in .expect / .tape scripts.
 */
export async function waitForFrame(
  result: RenderResult,
  predicate: (lastFrame: string, allFrames: string[]) => boolean,
  opts: WaitForFrameOpts = {},
): Promise<{ matchedAt: number; frameCount: number; lastFrame: string }> {
  const intervalMs = opts.intervalMs ?? 10
  const deadlineMs = opts.deadlineMs ?? 10_000
  const start = Date.now()
  while (Date.now() - start < deadlineMs) {
    const last = result.lastFrame() ?? ''
    const all = (result as unknown as { frames: string[] }).frames ?? []
    if (predicate(last, all)) {
      return {
        matchedAt: Date.now() - start,
        frameCount: all.length,
        lastFrame: last,
      }
    }
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  const final = result.lastFrame() ?? ''
  const all = (result as unknown as { frames: string[] }).frames ?? []
  throw new Error(
    `waitForFrame timeout after ${deadlineMs}ms ` +
      `(${opts.describe ?? 'no describe'}). ` +
      `Frame count: ${all.length}. Last frame:\n${final}`,
  )
}
```

### 4.2 `scripts/tui-tmux-capture.sh` (P2 골격)

```bash
#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: debug-infra-rebuild RFC § P2
# Replaces scripts/tui-text-debug.sh's asciinema-in-asciinema PTY nesting.

set -euo pipefail
SESSION="kosmos-debug-$$"
OUTDIR="${1:?usage: $0 <output-dir>}"
SCENARIO="${2:?usage: $0 <output-dir> <scenario.sh>}"
mkdir -p "$OUTDIR"

cleanup() { tmux kill-session -t "$SESSION" 2>/dev/null || true; }
trap cleanup EXIT

# 1. Detached session running KOSMOS TUI
tmux new-session -d -s "$SESSION" -x 200 -y 60 'bun run tui'

# 2. Run the scenario script in a sub-shell with helpers
export TMUX_SESSION="$SESSION"
export OUTDIR
source "$SCENARIO"

# 3. Final dump
tmux capture-pane -t "$SESSION" -p > "$OUTDIR/final.txt"
echo "captures saved to $OUTDIR"
```

Helper API (`scripts/tui-tmux-helpers.sh`):
```bash
# Polled wait — replaces Sleep
wait_for_pane() {
  local pattern="$1" deadline="${2:-30}"
  local start=$(date +%s)
  until tmux capture-pane -t "$TMUX_SESSION" -p | grep -qE "$pattern"; do
    if (( $(date +%s) - start > deadline )); then
      echo "TIMEOUT waiting for /$pattern/ after ${deadline}s" >&2
      tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/timeout-$1.txt"
      return 1
    fi
    sleep 0.3
  done
}

snapshot_pane() {
  local label="$1"
  tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/snap-$label.txt"
}

send_keys_pane() {
  tmux send-keys -t "$TMUX_SESSION" -- "$@"
}

send_enter_pane() {
  tmux send-keys -t "$TMUX_SESSION" Enter
}
```

### 4.3 `tests/fixtures/llm/` 디렉토리 (P0 aimock fixtures)

```
tests/fixtures/llm/
├── busan-weather.json        # 단일 turn — kma_forecast_fetch
├── busan-multi-tool.json     # 회귀 #1 재현 — multi-tool drop guard 검증
├── invalid-params.json       # 회귀 #2 재현 — schema visibility 검증
└── verbose-trace.json        # outbound HTTP trace 검증
```

각 fixture 의 ttft/tps 는 *prod-realistic but bounded* 로 — 200ms TTFT, 50 tokens/sec, 50ms jitter.

### 4.4 OTEL span events (P4)

`src/kosmos/llm/client.py`:
```python
# Each chunk arriving from FriendliAI
span.add_event("kosmos.llm.chunk", attributes={
    "kosmos.correlation_id": correlation_id,
    "kosmos.llm.bytes": len(chunk_bytes),
    "kosmos.llm.delta_ms": elapsed_ms_since_first_chunk,
    "kosmos.llm.channel": channel_name,  # content|reasoning|tool_call
})
```

`tui/src/components/Messages.tsx` (or 적절한 곳에서):
```typescript
// Each Ink reconcile
tracer.startSpan('kosmos.tui.frame_commit', {
  attributes: {
    'kosmos.correlation_id': correlationId,
    'kosmos.tui.frame_hash': hashFrame(latestFrame),
    'kosmos.tui.frame_seq': frameSeqCounter,
  },
}).end()
```

## § 5. Migration plan

### Phase 1 — Anti-flake (1 PR, ~1일)

- [ ] `tui/src/test-utils/waitForFrame.ts` 추가
- [ ] 기존 `.expect`/`.tape` 의 `Sleep <≥1>` 모두 grep → 제거 또는 `wait_for_pane` 으로 대체
- [ ] AGENTS.md TUI verification methodology 에 P1 룰 추가

### Phase 2 — LLM determinism (1 Epic, ~3일)

- [ ] aimock Docker compose 추가
- [ ] 5개 핵심 시나리오 fixture 작성 (busan-weather, busan-multi-tool, invalid-params, verbose-trace, error-paths)
- [ ] CI smoke 가 aimock 으로 가리키게 변경
- [ ] `@pytest.mark.live` real-FriendliAI gate 는 nightly only 유지

### Phase 3 — TUI capture replacement (1 Epic, ~2일)

- [x] `scripts/tui-tmux-capture.sh` + helpers 추가 (commit `182f4b7`)
- [x] Spec 2519 / 2297 / 2112 smokes tmux 버전으로 마이그레이션 (2026-05-02)
- [x] Spec 1979 smoke tmux 버전 마이그레이션 (2026-05-02 — 4 sub-scenarios, see table below)
- [ ] `scripts/tui-text-debug.sh` 는 deprecate (offline replay 만 지원)

#### Phase 3 포팅 상태 (2026-05-02 기준)

| Spec | Legacy file | tmux scenario | Proof run | Notes |
|---|---|---|---|---|
| **2519** (Korean IME Enter) | `scripts/smoke-2519-final.expect` | `scenarios/smoke-tmux.sh` ✅ | `proof-runs/tmux-migration/` 8 snaps | Boot match: 1s; turn1 response: 0s (warm). Critical discovery: must wait for turn1 completion before sending turn2 (K-EXAONE queues input while reasoning). One predicate NOT convertible: `expect eof` after spawn exit — tmux session is persistent; replaced with `send_ctrlc_pane`. |
| **2297** (Citizen tax-return) | `scripts/smoke-citizen-taxreturn.expect` | `scenarios/smoke-citizen-taxreturn-tmux.sh` ✅ | `proof-runs/tmux-migration/` 7 snaps | Boot match: 0s (warm). Receipt-id regex (`접수번호: hometax-…`) non-fatal — requires Phase 2 aimock fixture; OPAQUE domain returns clarifying question live. `CHECKPOINTreceipt` non-fatal (TUI T014 pending). |
| **2112** (Boot / Anthropic dead models) | `smoke.expect` | `scenarios/smoke-tmux.sh` ✅ | `proof-runs/tmux-migration/` 14 snaps | Boot match: 0-1s; /help: 0s (local render). Discovery: `expect ">"` is too permissive — replaced with `tool_registry: N entries verified`. Help overlay must be dismissed (`send_keys_pane Escape`) before next scenario sends input. |
| **1979** (Plugin DX TUI integration) | `debug-direct.expect` `debug-enter.expect` `debug-help.expect` `debug-install.expect` | `scenarios/debug-direct-tmux.sh` ✅ `scenarios/debug-enter-tmux.sh` ✅ `scenarios/debug-help-tmux.sh` ✅ `scenarios/debug-install-tmux.sh` ✅ | `proof-runs/tmux-migration/debug-direct/` 4 snaps `debug-enter/` 5 snaps `debug-help/` 5 snaps `debug-install/` 7 snaps | Boot match 0-1s (warm). debug-help: /help overlay confirmed rendered (14-entry help text captured, local render 0s). debug-direct: activity-based settle replaced `sleep 12`. debug-install: PR banner (`PR #2578`) detected in status bar — confirms the diagnostic check works; consent modal absent (plugin not in catalog — expected). debug-enter: CR+LF → `send_text_pane` + `send_enter_pane` + Tab → `send_keys_pane Tab` pattern confirmed correct. One migration friction: `log_file` byte-stream capture in .expect is NOT replicated — snapshots are pane-state only; legacy .expect files retained for offline pyte replay. |
| 2521 | (none shipped yet) | — | — | Future work |
| 1635 | multiple `.tape` files | — | — | Future work |
| 287 | multiple `.tape` files | — | — | Future work |

**Remaining legacy files: 42** (the 3 ported scenarios account for 7 source files across the two spec dirs). Future work covers the 1979 plugin DX scripts (4 `.expect`), 1635 UI L2 tapes, 287 TUI bootstrap tapes, and any new specs added before Phase 3 closes.

#### Key predicates that CANNOT be expressed as `wait_for_pane` regex

1. **`expect eof`** (used in all three original scripts for process exit) — tmux sessions persist after the spawned process exits; `wait_for_pane` sees the frozen last-frame. Replaced with `send_ctrlc_pane` + `sleep 1` + final snapshot.
2. **Negative assertions** (`"dispatched_via" must NOT appear`) — `wait_for_pane` is a positive predicate only. Handled inline via `tmux capture-pane | grep -qF "..."` check with `snapshot_pane` on failure.
3. **`set timeout N` global fallback** (Tcl expect) — per-step deadlines in `wait_for_pane` are the equivalent; no global timeout needed.
4. **`log_file` PTY capture** (expect writes every byte to a log file) — tmux captures are pane-state snapshots, not full byte streams. For offline replay, the legacy `.expect` + pyte chain (`scripts/cast_to_frames.py`) remains the canonical method (those files are NOT deleted).

### Phase 4 — Snapshot streaming (1 Epic, ~3일)

- [x] Ink-side `frames` 배열을 hash sequence 로 assert 하는 helper (`tui/src/test-utils/frameStreamSnapshot.ts` — `assertFrameSequence` + `takeStreamSnapshot`)
- [ ] Spec 1635 / 287 의 핵심 component test 마이그레이션 (future work)
- [x] `kosmos.tui.frame_commit` OTEL event 추가 (`tui/src/utils/frameCommitOtel.ts` — `useFrameCommitTracker` hook wired into `MessagesImpl`)

### Phase 5 — OTEL chunk events (Optional, 1 Epic)

- [ ] `kosmos.llm.chunk` event 추가 (`src/kosmos/llm/client.py`)
- [ ] Phoenix `traces.json` export 통합
- [ ] AGENTS.md "5 mandatory probe points" 의 IPC frame boundary probe 와 통합

## § 6. AGENTS.md 룰 변경 제안

기존 `## TUI verification (LLM-readable smoke) — PR mandatory` 섹션을 보강:

**5-layer verification chain → 5-tier (Layer 5 자체 분기)**:
- Layer 5a: tmux capture-pane snapshots (Phase 3 후 default)
- Layer 5b: pyte cell-grid replay (offline 만)
- Layer 5c: Ink `frames` sequence hash (Phase 4 후 추가)

새 hard rules:
- **No `Sleep <≥1s>` in any expect/tape script** — 위반은 PR auto-block
- **Real FriendliAI in CI smokes는 금지** — `@pytest.mark.live` 만 — Phase 2 후
- **Asciinema 자체는 deprecated** — record-only 또는 offline replay 만, capture 는 tmux

## § 7. 참조 (deep research 출처)

핵심 레퍼런스 (전체 인용은 § 2 의 표 참조):

1. [CopilotKit/llmock + aimock](https://aimock.copilotkit.dev/) — fake LLM HTTP server with streaming physics
2. [TanStack: How We Test TanStack AI Across 7 Providers](https://tanstack.com/blog/how-we-test-tanstack-ai-across-7-providers) — 137 tests / 7 providers / per-test isolation pattern
3. [amosjyng/vcr-langchain](https://github.com/amosjyng/vcr-langchain) — VCR-style cassettes with streaming-aware replay
4. [Charm: teatest pattern](https://carlosbecker.com/posts/teatest/) — `WaitFor(predicate, deadline)` 의 정전
5. [Pattern Matched: Testing Bubble Tea Interfaces](https://patternmatched.substack.com/p/testing-bubble-tea-interfaces) — anti-pattern guide
6. [JM: Debug TUIs with tmux](https://jmlago.github.io/skills/debug-tuis-with-tmux.html) — capture-pane workflow
7. [arxiv:2602.00409 — Are Coding Agents Generating Over-Mocked Tests?](https://arxiv.org/html/2602.00409v1) — mock layer guidance
8. [The Missing Layer: Visual Replay](https://dev.to/custodiaadmin/the-missing-layer-in-langsmith-langfuse-and-helicone-visual-replay-21gk) — gap in tracing platforms
9. [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) — 2025 attribute schema
10. [Phoenix CLI trace export](https://arize.com/docs/phoenix/tracing/how-to-tracing/importing-and-exporting-traces/retrieve-traces-via-cli) — replayable trace dumps

## § 8. 결정 기록 (ADR-style)

**Decision-1**: aimock 채택 (vs litellm mock_response)
- **Why**: streaming physics knob (ttft/tps/jitter) 가 K-EXAONE-realistic 재현에 결정적. litellm 은 이게 없음.
- **Trade-off**: 새 Docker dependency. 하지만 Spec 028 이 이미 docker compose 보유.

**Decision-2**: tmux capture-pane (vs asciinema)
- **Why**: PTY-nesting 회피. plain UTF-8 출력 → grep 가능.
- **Trade-off**: tmux 의존성 (CI runner 에 깔려 있음). asciinema 는 archive-only 로 유지.

**Decision-3**: OTEL span events (vs separate logging stream)
- **Why**: Spec 021 + 028 의 기존 인프라 재사용. Phoenix/Langfuse 둘 다 호환.
- **Trade-off**: span event 는 trace 와 묶여서만 추출 가능.

**Decision-4**: ink-testing-library `.frames` 강화 (vs vhs 대체)
- **Why**: vhs 의 wall-clock Sleep 가 streaming agentic UI 에 부적합. `.frames` 가 이미 React reconciler determinism 보유.
- **Trade-off**: VHS 의 GIF 출력 미지원 (PNG keyframe 만).

---

**다음 단계**: 이 RFC 가 승인되면 Phase 1 (waitForFrame helper) 즉시 착수. Phase 2 (aimock) 는 별도 Epic 으로 GitHub issue 발행.
