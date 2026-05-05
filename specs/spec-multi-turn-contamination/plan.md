# Implementation Plan: Multi-turn Message-State Contamination Diagnosis & Fix

**Branch**: `spec-multi-turn-contamination` | **Date**: 2026-05-04 | **Spec**: [`spec.md`](./spec.md)
**Input**: Feature specification from `/specs/spec-multi-turn-contamination/spec.md`

## Summary

K-EXAONE on FriendliAI is contaminating multi-turn citizen sessions: turn 2's reasoning starts from turn 1's payload, and tool calls dispatched in turn 2 carry parameters that originate in neither turn 1 nor turn 2 (hallucinated). Three open hypotheses (H1 frontend race / H2 K-EXAONE internal / H3 tool-result residue) cannot be discriminated by the existing single-turn smoke harness. This Epic enforces a diagnostic-before-fix methodology: instrument the IPC envelope flow at three layers (frontend message-array build, backend frame ingest, K-EXAONE reasoning preview), reproduce the canonical two-turn scenario, classify the verdict, then fix at the verdict-confirmed layer with a regression-locking test that future contamination cannot bypass. AGENTS.md `feedback_partial_fix_revealed_by_better_infra` (Spec 2521 lesson) is the operating principle.

## Technical Context

**Language/Version**: Python 3.12+ (backend, existing baseline; no version bump). TypeScript 5.6+ on Bun v1.2.x (TUI, existing Spec 287 stack; no version bump).

**Primary Dependencies**: All existing.
- Python — `pydantic >= 2.13` (frame schema, `ChatRequestFrame.messages`), `pydantic-settings >= 2.0` (env catalog: `KOSMOS_CHAT_REQUEST_DUMP`, `KOSMOS_QUERY_TRACE`), `httpx >= 0.27` (FriendliAI client, untouched), `opentelemetry-sdk` + `opentelemetry-semantic-conventions` (Spec 021 spans, NEW span attribute `kosmos.chat.turn_index` on diagnostic emit), `pytest` + `pytest-asyncio` (existing test stack).
- TypeScript — existing `ink`, `react`, `@inkjs/ui`, `string-width`, `zod ^3.23`, `@modelcontextprotocol/sdk`, Bun stdlib + `crypto.randomUUID()`. The `bun:test` framework + `ink-testing-library` v4 already vendored (Spec 287 + Spec 1635).
- Stdlib only for new diagnostic code: `logging` (Python — AGENTS.md hard rule, no `print`), `process.stderr.write` via `require('fs').writeSync(2, ...)` pattern already in use at `tui/src/query/deps.ts:113-115`.

**Zero new runtime dependencies** — AGENTS.md hard rule + spec FR-010 + SC-005.

**Storage**: N/A. Diagnostic logs are stderr-only, captured into committed text files under `specs/spec-multi-turn-contamination/diagnostic-runs/<timestamp>/` for post-hoc analysis. No database, no on-disk schema. Spec 027 session JSONL transcripts unchanged. Spec 028 OTLP collector unchanged (one new span attribute is additive only).

**Testing**:
- `bun test` (Layer 1b Ink snapshot via `ink-testing-library` v4) — `tui/src/__tests__/multi-turn-contamination.test.ts` exercises a stub-bridge two-turn flow and intercepts the emitted `ChatRequestFrame` payloads to assert message-array tail invariants.
- `pytest` + `pytest-asyncio` — backend `_handle_chat_request` unit test with a fake `LLMClient` returning a canned multi-turn reasoning trace.
- Layer 5 tmux smoke (`scripts/tui-tmux-capture.sh`) — `specs/spec-multi-turn-contamination/scripts/{repro-two-turn.sh,regress-multi-turn.sh}` against deterministic fake LLM (`KOSMOS_LLM_PROVIDER=fake-multi-turn`).
- `@pytest.mark.live` manual — real K-EXAONE on FriendliAI two-turn smoke. AGENTS.md hard rule: NEVER in CI.

**Target Platform**: macOS / Linux developer terminals running Bun v1.2.x + Python 3.12+. Identical to all prior KOSMOS deliverables.

**Project Type**: TUI + backend hybrid (existing). No new module boundaries introduced.

**Performance Goals**: Diagnostic emit MUST add <1ms per turn when env-gated off (no-op fast path). When gated on, MUST add <10ms per turn (single stderr write per layer × 3 layers, bounded log size 1024 bytes per layer per turn).

**Constraints**:
- AGENTS.md hard rules (frozen) — no new deps, KOSMOS_-prefixed env vars, stdlib `logging`, no `print()`, no `--force` push to main.
- Spec 032 IPC envelope MUST NOT change shape — diagnostic is additive (stderr-only) and the envelope is read-only from the diagnostic's perspective.
- Spec 2521 byte-copy procedure MUST be cited if any LLM-client-layer change is required (only if H2 confirms).
- Per AGENTS.md `feedback_pty_log_full_inspection` — full PTY log read mandatory; grep alone insufficient. Diagnostic-runs/ artefacts MUST be enumerated frame-by-frame in the ADR's Decision section.

**Scale/Scope**: Single feature affecting two files (frontend `tui/src/query/deps.ts`, backend `src/kosmos/ipc/stdio.py`) for diagnostic emit + ≤2 files for the fix (layer determined by US1 verdict) + 2 test files + 1 ADR + 1 spec directory. Total LOC delta projected ≤300.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This Epic is a diagnostic-before-fix bug investigation; the constitution check enumerates the AGENTS.md + `docs/vision.md` hard rules each phase MUST satisfy.

### Hard rules (AGENTS.md, frozen)

| Rule | Check | Status |
|------|-------|--------|
| All source text in English | Diagnostic log lines, ADR, spec, plan, tasks all English. Korean only in domain-data fixtures (intent-keyword-map.json) | PASS |
| Env vars prefixed `KOSMOS_` | `KOSMOS_CHAT_REQUEST_DUMP`, `KOSMOS_QUERY_TRACE` (extends existing), `KOSMOS_LLM_PROVIDER=fake-multi-turn` (test-only) | PASS |
| Stdlib `logging` only; no `print()` outside CLI | Backend uses `logger.info(...)` for diagnostic emits. TUI uses existing `require('fs').writeSync(2, ...)` pattern at `tui/src/query/deps.ts:113-115` (NOT `console.log`) | PASS |
| Pydantic v2 for all tool I/O. Never `Any` | `ChatRequestFrame` already pydantic v2 frozen; diagnostic adds no new schema | PASS |
| Never call live `data.go.kr` APIs from CI tests | Diagnostic + regression tests use fake LLM + stub bridge; no live HTTP | PASS |
| Never add a dependency outside a spec-driven PR | This IS a spec-driven PR. Zero new deps committed | PASS |
| Never `--force` push `main`, `--no-verify`, or bypass signing | Standard PR flow | PASS |
| Never create `requirements.txt`, `setup.py`, or `Pipfile` | N/A | PASS |
| Never commit a file larger than 1 MB without asking | Diagnostic-runs/ logs bounded (1024 bytes per layer per turn × 3 layers × <10 turns ≪ 1 MB) | PASS |
| Never introduce Go or Rust | N/A | PASS |

### Reference materials (mandatory per `docs/vision.md § Reference materials`)

Per AGENTS.md "Reference source rule": every Phase 0 must consult `.specify/memory/constitution.md` and `docs/vision.md § Reference materials`. Map each design decision:

| Decision | CC Reference | KOSMOS Adaptation |
|----------|--------------|-------------------|
| Diagnostic stderr emit pattern (US1) | `.references/claude-code-sourcemap/restored-src/src/services/api/claude.ts:1184` (`extractDiscoveredToolNames(messages)` log line — diagnostic is additive, off by default) | Mirror pattern; add layer-tagged prefix `[CHAT_REQUEST_DUMP]` / `[REASONING_PREVIEW]` / `[CHAT_MESSAGES_BUILT]` for grep-ability |
| Two-turn scenario harness (US1 / US3) | `.references/claude-code-sourcemap/restored-src/src/screens/REPL.tsx` multi-turn paint cycle — CC has no canonical multi-turn smoke (developer harness assumes single dev session) | KOSMOS layer 5 tmux scenario adds `wait_for_pane <regex> <deadline>` between turns to handle K-EXAONE reasoning latency (per memory `feedback_debug_infra_rebuild`) |
| Hypothesis classification → fix layer (US2 / FR-008) | N/A (CC byte-copy methodology presumes no contamination class — KOSMOS-novel) | Spec 2521 procedure: if fix touches LLM client (H2), MUST cite CC line range + use byte-copy + swap commit pattern |
| Regression test pattern (US3 / FR-012) | CC test stack uses `bun:test` + `ink-testing-library` v4 across many TUI tests | KOSMOS extends with stub-bridge intercept of `ChatRequestFrame` payload; existing pattern, not new infrastructure |
| ADR pattern (US4 / FR-016) | `docs/adr/ADR-009-secureStorage-drop.md` (Spec 2643 most recent) | Same five sections; cite diagnostic-runs/ paths in Decision |

**Constitution gate: PASS** — proceed to Phase 0.

## Phase 0 — Research

### R-1: IPC envelope shape — `ChatRequestFrame.messages` is the canonical source-of-truth

**File**: `src/kosmos/ipc/frame_schema.py:222-310`. `ChatRequestFrame.messages: list[ChatMessage]` carries the full conversation history per turn. `ChatMessage` is a pydantic v2 frozen model with `role: Literal["system", "user", "assistant", "tool"]` + `content: str` + optional `name` / `tool_call_id` for tool-role messages. Validator on the frame asserts `role="tool"` messages MUST set both `name` AND `tool_call_id` (data-model invariant D4 — Spec 1978 ADR-0001).

**Implication**: If H1 (frontend race) is confirmed, the symptom would be `frame.messages` arriving at the backend with the wrong tail — the backend itself is innocent. If H3 (tool-result residue) is confirmed, the frontend correctly sends turn 2's user message but the backend's local `messages` list (mutated mid-loop) still carries turn 1's `role="tool"` payload positioned ambiguously. The diagnostic MUST log both the FRAME-AS-RECEIVED (FR-001 backend dump) AND the LOCAL-LIST-AS-FORWARDED (additional log inside the agentic-loop iteration) to discriminate H1 vs H3.

### R-2: K-EXAONE Hermes parser + `parallel_tool_calls=False` — H2 surface area

**Memory**: `feedback_llm_api_option_first_suspect` (Spec 2521, 2026-05-02) — Lead Opus + Codex collaboration confirmed `parallel_tool_calls=False` is the K-EXAONE multi-tool layout fix. That fix landed in `src/kosmos/llm/client.py`. **This Epic MUST verify the same flag is still set** (regression check) before suspecting H2. If `parallel_tool_calls` was silently re-enabled, the H2 verdict could be a false positive masking a Spec 2521 regression.

**FriendliAI Serverless OpenAI-compat behavior**: `enable_thinking=true` makes K-EXAONE emit `reasoning_content` SSE events ahead of `content` events. Per K-EXAONE 236B-A23B model card, `reasoning_content` is generated FRESH per request (no implicit cross-request KV-cache continuation). If H2 is the verdict, the contamination would be on the SAME request — i.e. the model is reasoning about the wrong message in the array we send. That points back to a content-ordering issue inside the array (H1 / H3), not true cross-request internal state, narrowing H2 to "K-EXAONE attention sink picks the wrong user message in a multi-message array".

**FriendliAI cache key collision** (H2 sub-hypothesis): FriendliAI's serverless tier may cache prompt prefixes by `session_id`. If KOSMOS reuses the same `session_id` across turns and FriendliAI's cache returns a stale completion, the turn-2 response would be a verbatim turn-1 re-emission. The diagnostic test (edge case "session_id rotation isolation test") rotates `session_id` per turn and observes whether contamination persists; persistence rules out FriendliAI cache, disappearance confirms it.

### R-3: Frontend message-array build — `tui/src/query/deps.ts:117-133`

**Code path** (extracted Read from spec authoring):

```typescript
// Convert CC `Message[]` → ChatRequestFrame.messages.
const chatMessages: ChatMessage[] = []
for (const m of messages) {
  const ma = m as { type?: string; message?: { role?: string; content?: unknown } }
  if (!ma || (ma.type !== 'user' && ma.type !== 'assistant')) continue
  const role: 'user' | 'assistant' = ma.type === 'user' ? 'user' : 'assistant'
  const content = extractText(ma.message?.content)
  if (!content) continue
  chatMessages.push({ role, content })
}
if (chatMessages.length === 0) {
  chatMessages.push({ role: 'user', content: '' })
}
```

**H1 surface**: `messages: Message[]` is passed in by the caller; if the React store updates synchronously before `callModel` is invoked AND `messages` is a snapshot reference, the build is correct. If the caller invokes `callModel` with a stale `messages` reference (e.g. the old reference predating the turn-2 push), the loop here will silently emit a 1-element array missing turn 2. The diagnostic FR-003 (`[CHAT_MESSAGES_BUILT] turn=N count=K tail_role=... tail_text_first256=...`) directly observes this.

**Note**: `extractText(ma.message?.content)` is the suspect for content-shape drift if turn 2 has a content shape the extractor doesn't recognize (e.g. an array of content blocks vs a string). Diagnostic dump MUST log the raw `ma.message.content` shape pre-extract too, to discriminate "missing turn" from "turn present but extracted as empty string".

### R-4: Backend agentic loop — `src/kosmos/ipc/stdio.py:_handle_chat_request`

**File**: `src/kosmos/ipc/stdio.py:1786-2900` (covers handler entry through max-turns termination). Backend takes `frame.messages`, augments the system prompt with `<available_adapters>` BM25 suffix (Spec 2521), then enters an agentic loop where each iteration:

1. Calls `LLMClient.stream(...)` with the CURRENT local `messages` list.
2. On streamed `tool_call` chunks, emits `ToolCallFrame`s, awaits each tool result via `_pending_calls` Future, INJECTS `role="tool"` messages into the LOCAL `messages` list, and re-iterates.
3. Bounded by `KOSMOS_AGENTIC_LOOP_MAX_TURNS=8`.

**H3 surface**: After turn 1 completes (assistant message + tool_use + tool_result), the local `messages` list grows. When turn 2 arrives as a NEW `ChatRequestFrame`, the handler re-enters with `frame.messages` (which IS the freshly-rebuilt array from the frontend). But: the local `messages` variable inside the LOOP body is per-invocation; cross-invocation residue is unlikely unless there's a module-level cache. The diagnostic MUST log both `frame.messages` (input) AND the FIRST `messages_for_llm` (after augmentation but before loop entry) to confirm there's no implicit prepend / append from a stale state.

**H3 sub-suspect**: The `<available_adapters>` BM25 suffix is computed from `latest_user_utt` extracted via:
```python
for m in reversed(frame.messages):
    if m.role == "user" and m.content:
        latest_user_utt = m.content
        break
```
This loop is correct IF `frame.messages` is correct. If `frame.messages` tail is turn 1 (H1 scenario), `latest_user_utt` is turn 1, BM25 surfaces turn-1-relevant adapters in the suffix, K-EXAONE is reasoning over a system prompt PRE-CONFIGURED for turn 1's intent. This compounds the contamination signature — the model is doubly-pulled toward turn 1 (wrong messages tail + wrong adapter suffix). Diagnostic MUST log `latest_user_utt` AND the resulting adapter suffix.

### R-5: Existing diagnostic infrastructure — extend, don't reinvent

`KOSMOS_QUERY_TRACE=1` is the existing TUI-side trace gate (`tui/src/query/deps.ts:113`). The backend has no equivalent gate; `logger.info` calls fire unconditionally. Per AGENTS.md "stdlib `logging` only", the backend gate MUST be a `logger.isEnabledFor(logging.DEBUG)` check OR a `KOSMOS_*` env-var check at handler entry. The latter is more discoverable (matches the existing TUI pattern) — choose `KOSMOS_CHAT_REQUEST_DUMP=1`.

The existing tmux capture harness (`scripts/tui-tmux-capture.sh`, AGENTS.md "Layer 5") already handles PTY + stderr capture; the new repro script just composes it.

**Phase 0 verdict**: Three hypotheses (H1 / H2 / H3) cannot be discriminated WITHOUT the diagnostic instrumentation. Phase 1 designs the instrumentation; Phase 2 reproduces; Phase 3 designs the fix from the verdict.

## Phase 1 — Diagnosis Design

### D-1: Diagnostic emit contracts

**Frontend (TUI side)** — extend `tui/src/query/deps.ts:117` `__t(...)` helper. Add ONE new emit call per turn:
```typescript
__t(`[CHAT_MESSAGES_BUILT] turn=${turnIndex} count=${chatMessages.length} ` +
   `tail_role=${chatMessages[chatMessages.length - 1]?.role} ` +
   `tail_text_first256=${JSON.stringify((chatMessages[chatMessages.length - 1]?.content || '').slice(0, 256))}`)
```
`turnIndex` source: a session-scoped monotonic counter on the `KosmosBridge` singleton (existing — `tui/src/ipc/bridgeSingleton.ts`). Increment on every `bridge.send(ChatRequestFrame)`.

**Backend (Python side)** — add ONE new emit at the top of `_handle_chat_request` and ONE inside the LLM-stream consumption path:

```python
if os.getenv("KOSMOS_CHAT_REQUEST_DUMP") == "1":
    turn_idx = _session_turn_counter.get(frame.session_id, 0) + 1
    _session_turn_counter[frame.session_id] = turn_idx
    payload = [
        {"role": m.role, "content": (m.content or "")[:256], "tool_call_id": m.tool_call_id}
        for m in frame.messages
    ]
    logger.info(
        "[CHAT_REQUEST_DUMP] turn=%d session=%s correlation=%s messages=%s",
        turn_idx, frame.session_id, frame.correlation_id, json.dumps(payload, ensure_ascii=False),
    )
```

For `[REASONING_PREVIEW]`, instrument the LLMClient stream consumer (existing path that accumulates `reasoning_content` into `accumulatedThinking` — KOSMOS already has this buffer per Spec 2521). Emit when the buffer first reaches 1024 bytes OR on stream completion (whichever first).

**Span attribute** (additive, OTEL): `kosmos.chat.turn_index` set on every `kosmos.chat.request` span (existing span from Spec 021). Lets Langfuse trace dashboards group by turn.

### D-2: Canonical two-turn scenario script

**File**: `specs/spec-multi-turn-contamination/scripts/repro-two-turn.sh`

Composition (calls into existing `scripts/tui-tmux-capture.sh`):

1. `tmux new-session -d -s kosmos-multi 'KOSMOS_CHAT_REQUEST_DUMP=1 KOSMOS_QUERY_TRACE=1 bun run tui 2>backend.log'`
2. `wait_for_pane "KOSMOS" 10` (boot)
3. `tmux send-keys -t kosmos-multi "강남역 근처 내과 찾아줘" Enter`
4. `wait_for_pane "lookup\|hospital\|병원" 90` (turn 1 completes — K-EXAONE reasoning latency 30-90s per memory `feedback_debug_infra_rebuild`)
5. `tmux capture-pane -t kosmos-multi -p > snap-001-turn1-done.txt`
6. `tmux send-keys -t kosmos-multi "재난 알림 구독해줘" Enter`
7. `wait_for_pane "subscribe\|disaster\|재난" 90` — OR — fallback `wait_for_pane ".+" 90` if contamination dispatches a wrong tool
8. `tmux capture-pane -t kosmos-multi -p > snap-002-turn2-done.txt`
9. `tmux send-keys -t kosmos-multi C-c C-c` (graceful exit)
10. Move `backend.log` + all `snap-*.txt` into `specs/spec-multi-turn-contamination/diagnostic-runs/<UTC-timestamp>/`

**Hardcoded `Sleep` is forbidden** per AGENTS.md `feedback_debug_infra_rebuild` — every wait MUST be `wait_for_pane <regex> <deadline>`.

### D-3: Discrimination matrix

Read the diagnostic-runs/ artefacts and apply this matrix to derive the verdict:

| Observation | H1 | H2 | H3 |
|-------------|-----|-----|-----|
| `[CHAT_MESSAGES_BUILT] turn=2 tail_role=user tail_text_first256` references "재난" | OK | NEED-NEXT-CHECK | NEED-NEXT-CHECK |
| `[CHAT_MESSAGES_BUILT] turn=2 tail_role=user tail_text_first256` references "강남역" | **CONFIRMED** | — | — |
| `[CHAT_REQUEST_DUMP] turn=2 messages` tail differs from `[CHAT_MESSAGES_BUILT] turn=2` tail | (IPC corruption — separate bug) | — | — |
| `[CHAT_REQUEST_DUMP] turn=2 messages` tail = "재난" AND `[REASONING_PREVIEW] turn=2 first1024` references hospital | — | NEED-NEXT-CHECK | NEED-NEXT-CHECK |
| Same as above AND `latest_user_utt` log line shows "재난" | — | **CONFIRMED** | — |
| Same as above AND `latest_user_utt` log line shows "강남역" | — | — | **CONFIRMED** (BM25 suffix is contaminating) |

`latest_user_utt` log line is added by D-1 backend emit explicitly so this matrix is decisive.

### D-4: Hypothesis isolation tests (run only if Phase 2 verdict is ambiguous)

- **H1 isolation**: Add a debug build flag that synchronously awaits the React message-store push BEFORE invoking `callModel`. If contamination disappears, H1 confirmed.
- **H2 isolation 1**: Rotate `session_id` per turn (debug-only). If contamination disappears, FriendliAI cache key (H2 sub-hypothesis) confirmed.
- **H2 isolation 2**: Set `KOSMOS_K_EXAONE_THINKING=false`. If reasoning blob disappears AND tool dispatch ALSO becomes correct, H2 confirmed (the reasoning was driving the wrong tool selection). If only the blob disappears, H3 (tool-result residue or BM25 suffix contamination) is still active.
- **H3 isolation**: Strip the `<available_adapters>` BM25 suffix entirely (debug-only) and observe whether contamination persists. If suffix is the contamination vector, contamination disappears.

These isolation tests live in tasks T005-T006 only if the Phase-2 reproduction's verdict is not unambiguous from the discrimination matrix alone.

## Phase 2 — Fix Design (post-diagnosis)

### F-1: Branching on verdict

```
US1 diagnostic verdict:
├── H1 (frontend race) → Fix in tui/src/query/deps.ts:117 area
│   • Snapshot `messages` AFTER React reconciliation, not before
│   • Likely: pass `messages` by getter callback; resolve at frame-assembly time
│   • CC reference: services/api/claude.ts:1080 normalizeMessagesForAPI(messages, ...)
├── H2 (K-EXAONE internal) → Fix in IPC contract / message ordering
│   • Most likely sub-cause: messages array contains assistant tool_use without matching tool_result for prior turn,
│     leaving K-EXAONE attention "incomplete" on prior turn
│   • Fix: ensure every assistant message with tool_use is followed by a tool message with matching tool_call_id
│     BEFORE the next user message lands in the array
│   • CC reference: services/api/claude.ts:957 yieldMissingToolResultBlocks (the canonical CC pattern)
└── H3 (tool-result residue / BM25 suffix) → Fix in backend
    • If BM25 suffix contaminating: re-build suffix from `frame.messages[-1]` not from any local cache
    • If tool-result residue: clear local agentic-loop messages list per ChatRequestFrame entry
    • Confirm no module-level mutable state crosses request boundaries
```

### F-2: Fix MUST follow CC byte-copy procedure if it touches LLM client

Per Spec 2521 + AGENTS.md `feedback_cc_source_migration_pattern`: any change to `src/kosmos/llm/client.py` MUST first verify the file's CC analog (`.references/claude-code-sourcemap/restored-src/src/services/...`) and any deviation MUST be a labeled `swap/<category>` commit (categories per Spec 2521).

For H2 in particular, the canonical CC pattern `yieldMissingToolResultBlocks` (`services/api/claude.ts:957`) is the well-known fix for "assistant has tool_use without matching tool_result" multi-turn drift. KOSMOS may need to port this directly.

### F-3: Fix MUST NOT change `ChatRequestFrame` shape

Per FR-009 + Spec 032 ADR cycle. If the fix is purely in how the array is BUILT or CONSUMED, the envelope is unchanged. If the fix requires a NEW field (e.g. explicit `turn_index` on the frame), an ADR is required before this Epic can merge.

## Phase 3 — Tasks Generation

`tasks.md` (separate file, this directory) enumerates:

- **T001-T003** — Diagnostic instrumentation (US1).
- **T004-T006** — Reproduction + verdict + isolation tests if needed.
- **T007-T010** — Fix implementation at the verdict-confirmed layer (US2).
- **T011-T012** — Regression test + ADR + diagnostic-runs/ commit (US3 + US4).

Per AGENTS.md "Dispatch unit": each Sonnet teammate gets ≤5 tasks AND ≤10 file changes. Lead Opus dispatches per the `dispatch-tree.md` (separate file, drawn before any Agent invocation per AGENTS.md).

## Project Structure

### Documentation (this feature)

```text
specs/spec-multi-turn-contamination/
├── plan.md                       # This file
├── spec.md                       # Feature specification
├── tasks.md                      # Phase 3 task list
├── intent-keyword-map.json       # Canonical intent → keyword map (FR-006 substring assertion)
├── scripts/
│   ├── repro-two-turn.sh         # FR-004 canonical reproduction
│   └── regress-multi-turn.sh     # FR-013 deterministic CI smoke
└── diagnostic-runs/
    └── <UTC-timestamp>/          # FR-005 committed reproduction artefacts
        ├── backend.log           # Stderr from KOSMOS_CHAT_REQUEST_DUMP=1
        ├── frontend.log          # Stderr from KOSMOS_QUERY_TRACE=1 (extracted from PTY)
        ├── snap-001-turn1-done.txt
        └── snap-002-turn2-done.txt
```

### Source Code (repository root)

```text
src/kosmos/ipc/
└── stdio.py                      # MODIFY: Add diagnostic emit at _handle_chat_request entry + LLM-stream consumer

src/kosmos/llm/
├── client.py                     # MODIFY (only if H2 confirmed and per Spec 2521 byte-copy)
└── ...                           # Otherwise untouched

tui/src/query/
└── deps.ts                       # MODIFY: Add [CHAT_MESSAGES_BUILT] emit at line 117 area

tui/src/ipc/
└── bridgeSingleton.ts            # MODIFY (minor): Add session-scoped turn counter

tui/src/__tests__/
└── multi-turn-contamination.test.ts  # NEW: FR-012 regression lock

tests/python/ipc/
└── test_chat_request_multi_turn.py   # NEW: pytest counterpart of FR-012

docs/adr/
└── ADR-NNN-multi-turn-contamination.md  # NEW: FR-016 verdict + decision

docs/testing.md                   # MODIFY: Document KOSMOS_CHAT_REQUEST_DUMP env var (FR-014 / SC-006)
```

**Structure Decision**: Hybrid Python backend + TS TUI + spec-deliverable directory. No new module boundaries; all diagnostic emits are in-place at the existing call sites. The fix's exact file-set is determined by the Phase-2 verdict (per F-1 branch).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations. Zero new dependencies. No new modules. No envelope shape changes. The diagnostic-before-fix methodology adds one extra phase (Phase 2 reproduction + verdict) compared to a flat fix-first approach, but this complexity is REQUIRED per AGENTS.md `feedback_partial_fix_revealed_by_better_infra` lesson — not a violation, but the proven correct procedure.

Table left empty intentionally.
