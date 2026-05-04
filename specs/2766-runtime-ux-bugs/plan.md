# Plan: Runtime UX Bug Fixes — Batch 2 (Epic #2766)

## Phase 0 — Reference materials & technical decisions

Per AGENTS.md spec-driven workflow Phase 0 mandate, every design decision is
mapped to a concrete reference.

### Canonical sources consulted
- `docs/vision.md § Reference materials` — Claude Code is first reference for
  any unclear UX decision; KOSMOS = CC + 2 swaps.
- `.references/claude-code-sourcemap/restored-src/` — CC 2.1.88 byte baseline
  for StreamGate / ChordInterceptor / `app:toggleTranscript`.
- `AGENTS.md § TUI verification methodology` — 5-layer chain + 7 anti-patterns,
  4 Infrastructure Insights post-2026-05-04.
- Memory `feedback_llm_api_option_first_suspect` — Spec 2521 Lead Opus 2-fix
  failure → Codex one-liner `parallel_tool_calls=False`. Defense-in-depth
  3-tier (LLM API + backend guard + frontend fallback).
- Memory `feedback_debug_infra_rebuild` — K-EXAONE thinking latency 30~90 s;
  hardcoded `Sleep` is forbidden in tmux scenarios.
- Memory `feedback_partial_fix_revealed_by_better_infra` — first fix is often
  partial; assume the next regression is hidden by debug infra.

### Decision matrix

| Issue | Root-cause hypothesis | Fix strategy | Reference |
|---|---|---|---|
| A KST | Multiple `datetime.now(tz=UTC)` callsites; envelope merger filters adapter `fetched_at` (good) but adapter still constructs UTC value | Apply KST patch (already in working-dir for 8 files) + extend to KMA forecast_fetch.py for consistency | `envelope.py` `_SYSTEM_META` filter logic |
| B order | StreamGate emits prose chunks before `<tool_call>` is detected because Hermes `<text>...<tool_call>...</tool_call>` arrives in sequence | Modify StreamGate to suppress ALL emission until end-of-turn when a `<tool_call>` appears OR until a fence (newline+timeout) confirms no tool_call follows | CC `StreamGate` reconstruction; memory anti-pattern `Final-state fallacy` |
| C HIRA | K-EXAONE thinking + HIRA HTTPS fetch can each take 30-90 s; current per-tool timeout may be too aggressive OR LLM stop reason swallows result | Add per-adapter timeout config + diagnostic span attribute `kosmos.tool.stage` (`{thinking,fetch,parse,emit}`); bump HIRA budget to 90 s; add 1 transient-retry on `httpx.ReadTimeout` | OTEL semantic conventions; memory `feedback_debug_infra_rebuild` |
| D Ctrl+O | `useKeybinding('app:toggleTranscript', handler, {context:'Global'})` already mounted; `defaultBindings.ts:125` has `'ctrl+o': 'app:toggleTranscript'`. Most likely chord-resolver returns `none` because Ink's Key.ctrl + input='o' shape mismatches resolver expectation | Verify with frame trace; if confirmed, add `useInput` fallback that triggers `dispatchAction('Global', 'app:toggleTranscript')` when chord registry misses | PR #2754 Insight #4 (`setToolJSX isLocalJSXCommand:false` was the prior chord-fallback pattern) |

### Stack
- Python 3.12+ (existing); TypeScript 5.6+ on Bun v1.2.x (existing).
- Zero new runtime dependencies (AGENTS.md hard rule).
- Stdlib `zoneinfo.ZoneInfo("Asia/Seoul")` (already imported by working-dir patch).

### Storage
- N/A — all in-memory; envelope is constructed per request.

## Phase 1 — Component design

### Issue A — KST consolidation
- **Touch list (8 files in working-dir + 1 new)**:
  - `src/kosmos/tools/envelope.py` (already patched)
  - `src/kosmos/tools/lookup.py` (already patched)
  - `src/kosmos/agents/worker.py` (already patched)
  - `src/kosmos/tools/mock/lookup_module_gov24_certificate.py`
  - `src/kosmos/tools/mock/lookup_module_hometax_simplified.py`
  - `src/kosmos/tools/mock/submit_module_gov24_minwon.py`
  - `src/kosmos/tools/mock/submit_module_hometax_taxreturn.py`
  - `src/kosmos/tools/mock/submit_module_public_mydata_action.py`
  - **NEW**: `src/kosmos/tools/kma/forecast_fetch.py` — `t_start = datetime.now(tz=_SEOUL_TZ)` (or keep UTC for elapsed math, but stamp KST in meta).
- **Test**: extend existing envelope test to assert tz `+09:00`.

### Issue B — StreamGate render-order
- **Touch**: `src/kosmos/llm/tool_call_parser.py` (`StreamGate.feed` + `flush`)
- Approach: track `_seen_open` flag. When `<tool_call>` appears, retroactively
  buffer the prose emitted earlier in the same chunk. Concretely: defer
  emission until either (a) a `<tool_call>` is seen → buffer + drop earlier
  prose so it can be re-emitted AFTER tool result, or (b) end-of-stream with
  no `<tool_call>` → flush all buffered prose.
- **Subtler alternative**: keep StreamGate as-is and instead have the engine
  buffer assistant-prose chunks until tool-loop iteration completes. Less
  invasive to StreamGate.
- **Pre-emit diagnostic**: capture exact order in a debug log to validate the
  hypothesis BEFORE patching.

### Issue C — HIRA timeout
- **Touch**: `src/kosmos/tools/executor.py` (per-tool timeout) +
  `src/kosmos/tools/hira/hospital_search.py` (`httpx.AsyncClient(timeout=...)`
  override) + `tui/src/services/llm/timeoutConfig.ts` (spinner label).
- **Diagnostic**: add `kosmos.tool.stage` span attribute via
  `trace.get_current_span().set_attribute(...)` at fetch / parse boundaries.

### Issue D — Ctrl+O
- **Touch**: `tui/src/hooks/useGlobalKeybindings.tsx` (add `useInput` fallback
  AFTER `useKeybinding('app:toggleTranscript', ...)`, gated to fire only when
  the chord resolver did NOT consume the event in the same render).
- Or: simpler — add direct `useInput` listener registered separately that
  invokes the same `handleToggleTranscript` callback when `key.ctrl && input === 'o'`.

## Phase 2 — Test strategy

- **pytest (Python)**:
  - Unit: envelope.normalize asserts KST tz on `meta.fetched_at`.
  - Unit: StreamGate.feed with synthetic Hermes input
    `"answer text<tool_call>...</tool_call>"` returns prose AFTER tool boundary.
- **bun test (TS)**:
  - Snapshot: useGlobalKeybindings registers handler for `app:toggleTranscript`.
  - Frame: Messages renders streaming tool_use → result → assistant text in
    expected child order.
- **Layer 4 vhs**:
  - `weather.tape` — weather flow with order verification.
  - `hospital.tape` — HIRA hospital with timeout assertion.
  - `ctrlO.tape` — Ctrl+O expand visual proof.
- **Layer 5 Bun PTY** (`scripts/bun-pty-capture.ts`): same scenarios, ASCII
  golden file diff.

## Phase 3 — Risk register

- **Risk R1**: StreamGate change drops legitimate prose. Mitigation: unit test
  with prose-only stream MUST pass through unchanged.
- **Risk R2**: HIRA timeout bump masks genuine network outage. Mitigation:
  retry only on `ReadTimeout`, not on connection errors; surface error
  envelope after retry exhaustion.
- **Risk R3**: Ctrl+O fallback double-fires when chord registry already
  consumed. Mitigation: `event.stopImmediatePropagation()` from the fallback
  AND check `event.defaultPrevented` before firing.
- **Risk R4** (MOST LIKELY per `feedback_partial_fix_revealed_by_better_infra`):
  Issue B has a deeper backend cause (engine emits assistant message before
  tool_use_block in conversation history). Mitigation: capture full IPC trace
  via `KOSMOS_LOG_LEVEL=debug` and log every `assistant_chunk` ↔ `tool_call`
  envelope timestamp.

## Phase 4 — Rollout

1. KST batch (low risk) — commit + push first.
2. Ctrl+O (low risk, isolated) — commit + push.
3. StreamGate (medium risk) — diagnostic first, then fix, then frame proof.
4. HIRA timeout (medium risk) — diagnostic first, then fix.
5. Open PR with `Closes #2766`.
6. Monitor CI + Codex P1 reply.
