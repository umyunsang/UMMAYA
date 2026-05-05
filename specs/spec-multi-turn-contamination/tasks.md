# Tasks: Multi-turn Message-State Contamination Diagnosis & Fix

**Input**: Design documents from `/specs/spec-multi-turn-contamination/`
**Prerequisites**: `spec.md` (mandatory) + `plan.md` (mandatory). Read AGENTS.md `feedback_partial_fix_revealed_by_better_infra` BEFORE T001.

**Tests**: Mandatory (FR-012, FR-013, FR-015) — diagnostic + fix + regression-lock are inseparable per spec methodology.

**Organization**: Tasks ordered by dependency. Tasks marked `[P]` may run in parallel; Lead Opus dispatches per `dispatch-tree.md` (drawn before any Agent invocation per AGENTS.md "Dispatch tree (NON-NEGOTIABLE)"). Each Sonnet teammate gets ≤5 tasks AND ≤10 file changes.

**Phase ordering rule**: Diagnostic phase (T001-T006) MUST complete BEFORE fix phase (T007-T010). The verdict from T004 directly determines T007-T010's file set. Skipping the diagnostic phase to "save time" violates the methodology and per spec FR-008 invalidates the Epic.

---

## Phase 1 — Diagnostic Instrumentation (US1, FR-001..FR-005)

**Goal**: Add three layered stderr emit points (frontend message-array build, backend frame ingest, K-EXAONE reasoning preview) gated by env vars, NO behavioral change to the agentic loop. Zero risk by default — emits OFF unless env var explicitly set.

### T001 — Backend `_handle_chat_request` diagnostic emit (FR-001 / FR-002)

**Files**: `src/kosmos/ipc/stdio.py`

**Surface**:
1. Add module-level `_session_turn_counter: dict[str, int] = {}` near other module-level state in stdio.py (NOT a singleton — process-lifetime per-session counter, in-memory only, AGENTS.md hard rule preserved).
2. At the top of `_handle_chat_request` (after the `isinstance(frame, ChatRequestFrame)` guard, BEFORE any other logic):
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
           turn_idx, frame.session_id, frame.correlation_id,
           json.dumps(payload, ensure_ascii=False),
       )
   ```
3. After the `latest_user_utt` extraction loop (existing code at `stdio.py:~1980`), add:
   ```python
   if os.getenv("KOSMOS_CHAT_REQUEST_DUMP") == "1":
       logger.info(
           "[LATEST_USER_UTT] turn=%d utt_first256=%s",
           _session_turn_counter.get(frame.session_id, 0),
           (latest_user_utt or "")[:256],
       )
   ```
4. In the LLM-stream consumer where `accumulatedThinking` (or its Python equivalent — `accumulated_reasoning`) is built, emit when buffer first reaches 1024 bytes OR on stream completion:
   ```python
   if os.getenv("KOSMOS_CHAT_REQUEST_DUMP") == "1" and not _reasoning_preview_emitted:
       if len(accumulated_reasoning) >= 1024 or stream_done:
           logger.info(
               "[REASONING_PREVIEW] turn=%d first1024=%s",
               _session_turn_counter.get(frame.session_id, 0),
               accumulated_reasoning[:1024],
           )
           _reasoning_preview_emitted = True
   ```
5. Add OTEL span attribute `kosmos.chat.turn_index` on the existing `kosmos.chat.request` span (Spec 021 extension — additive, no new span):
   ```python
   span.set_attribute("kosmos.chat.turn_index", turn_idx)
   ```

**Verification**: `pytest tests/python/ipc/test_chat_request_diagnostic.py::test_emit_off_by_default` (NEW small unit test) confirms NO `[CHAT_REQUEST_DUMP]` lines in caplog when env unset; confirms 3 lines when env set + two-turn flow simulated against fake LLM.

**Acceptance**: Backend builds + boots. `bun run tui` smoke (single turn) leaves the diagnostic OFF by default — no log lines. With `KOSMOS_CHAT_REQUEST_DUMP=1`, single-turn flow emits exactly one `[CHAT_REQUEST_DUMP] turn=1 ...` + one `[LATEST_USER_UTT] turn=1 ...` + one `[REASONING_PREVIEW] turn=1 ...` line. Performance: <1ms when off, <10ms when on.

---

### T002 — Frontend `tui/src/query/deps.ts` diagnostic emit (FR-003) **[P with T001]**

**Files**: `tui/src/query/deps.ts`, `tui/src/ipc/bridgeSingleton.ts`

**Surface**:
1. In `tui/src/ipc/bridgeSingleton.ts`: add `private _turnCounters: Map<string, number> = new Map()` and a `nextTurnIndex(sessionId: string): number` method that increments and returns the per-session counter.
2. In `tui/src/query/deps.ts:117` area (after `chatMessages` array construction at line 130, BEFORE the `bridge.send(frame)` at line 189):
   ```typescript
   const turnIndex = bridge.nextTurnIndex(sessionId)
   __t(
     `[CHAT_MESSAGES_BUILT] turn=${turnIndex} count=${chatMessages.length} ` +
     `tail_role=${chatMessages[chatMessages.length - 1]?.role} ` +
     `tail_text_first256=${JSON.stringify((chatMessages[chatMessages.length - 1]?.content || '').slice(0, 256))}`
   )
   ```
3. Pre-extraction raw-shape log (one line) for shape-drift discrimination per plan.md R-3:
   ```typescript
   if (process.env.KOSMOS_QUERY_TRACE === '1') {
     for (let i = 0; i < messages.length; i++) {
       const ma = messages[i] as { type?: string; message?: { content?: unknown } }
       __t(`[RAW_MESSAGE] idx=${i} type=${ma?.type} content_typeof=${typeof ma?.message?.content} content_isArray=${Array.isArray(ma?.message?.content)}`)
     }
   }
   ```
4. The existing `__t` helper already gates on `KOSMOS_QUERY_TRACE` — do NOT add a new env var. Per AGENTS.md hard rule "stdlib `logging` only", the TUI uses `require('fs').writeSync(2, ...)` already (existing pattern at `deps.ts:113-115`).

**Verification**: `bun test tui/src/__tests__/multi-turn-contamination.test.ts::test_diagnostic_emit_gated` confirms emit OFF by default, ON when env set, exactly one `[CHAT_MESSAGES_BUILT]` line per `callModel` invocation.

**Acceptance**: `bun run tui` boots cleanly. With `KOSMOS_QUERY_TRACE=1`, every TUI-side `callModel` emits one `[CHAT_MESSAGES_BUILT]` line + N `[RAW_MESSAGE]` lines.

---

### T003 — Canonical reproduction script `repro-two-turn.sh` (FR-004)

**Files**: `specs/spec-multi-turn-contamination/scripts/repro-two-turn.sh` (NEW)

**Surface**: Wrap `scripts/tui-tmux-capture.sh` per `plan.md § D-2`. Hard requirements:
- All waits via `wait_for_pane <regex> <deadline>` — NO `Sleep` (AGENTS.md `feedback_debug_infra_rebuild`).
- Both env vars set: `KOSMOS_CHAT_REQUEST_DUMP=1 KOSMOS_QUERY_TRACE=1`.
- Captures: `backend.log` (stderr from backend) + `snap-001-turn1-done.txt` (post-turn-1 pane) + `snap-002-turn2-done.txt` (post-turn-2 pane) + `final.txt` (final pane state).
- Output directory: `specs/spec-multi-turn-contamination/diagnostic-runs/$(date -u +%Y-%m-%dT%H-%M-%SZ)/`.
- Per-turn deadline: 90 seconds (K-EXAONE reasoning latency budget per memory).
- Two scenarios baked-in:
  - Scenario A (canonical): turn 1 = "강남역 근처 내과 찾아줘", turn 2 = "재난 알림 구독해줘".
  - Scenario B (negative control): turn 1 = "강남역 근처 내과 찾아줘", turn 2 = "강남역 근처 내과 찾아줘" (same text — should NOT show contamination).
  - Run mode controlled by `--scenario A|B` flag; default A.
- Graceful exit via `tmux send-keys C-c C-c` after final snap.

**Acceptance**: Run `specs/spec-multi-turn-contamination/scripts/repro-two-turn.sh --scenario A` against current main (pre-fix) → captures the contamination. Run `--scenario B` → captures the negative control. Both produce the directory layout expected by T005/T006.

---

## Phase 2 — Reproduction + Verdict (US1 / FR-005)

### T004 — Execute canonical reproduction + apply discrimination matrix

**Files**: `specs/spec-multi-turn-contamination/diagnostic-runs/<UTC-timestamp>/` (NEW directories)

**Surface**:
1. Run `specs/spec-multi-turn-contamination/scripts/repro-two-turn.sh --scenario A` against current main, against a real K-EXAONE-on-FriendliAI session (this is `@pytest.mark.live`-equivalent — manual local execution, NOT in CI).
2. Read the captured `backend.log` + `snap-NNN-*.txt` IN FULL per AGENTS.md anti-pattern #5 (skim-and-summarize forbidden) AND anti-pattern #1 (final-state fallacy forbidden).
3. Apply `plan.md § D-3` discrimination matrix to the captured logs and write the verdict into `specs/spec-multi-turn-contamination/diagnostic-runs/<timestamp>/VERDICT.md`. Format:
   ```markdown
   # Verdict: H<N>_<NAME> CONFIRMED
   Evidence:
   - backend.log line <L>: <quoted excerpt>
   - snap-002-turn2-done.txt line <L>: <quoted excerpt>
   - [LATEST_USER_UTT] turn=2 ... : <quoted text>
   Discriminated against:
   - H1: ruled out because <evidence>
   - H2: ruled out because <evidence>
   ```
4. ALSO run `--scenario B` (negative control) and confirm zero contamination signals — this isolates the bug from "any two-turn flow" to "two-turn flow with semantically-different turns".
5. Commit BOTH run directories (A scenario + B scenario) into the spec.

**Acceptance**: `VERDICT.md` exists. The named hypothesis (H1 / H2 / H3) has at least 3 cited evidence lines. The 2 rejected hypotheses each have ≥1 ruling-out evidence line. Negative-control directory confirms scenario B does NOT trigger the bug.

**Dependency**: T001 + T002 + T003 must be DONE.

---

### T005 — Hypothesis isolation tests (CONDITIONAL on T004 ambiguity) **[P with T006 only if both needed]**

**Files**: `specs/spec-multi-turn-contamination/diagnostic-runs/isolation-<H>/` (per H tested)

**Trigger**: ONLY if T004's discrimination matrix is ambiguous (e.g. two hypotheses still in play). If T004 yields a clean verdict, SKIP this task and document the skip in VERDICT.md.

**Surface**: Per `plan.md § D-4`, run the isolation tests for whichever hypotheses remain in play:
- **H1 isolation**: Add a debug build flag (env `KOSMOS_DEBUG_AWAIT_RECONCILE=1`) that synchronously awaits React reconciliation before `callModel`. Run scenario A. Capture results.
- **H2-cache isolation**: Rotate `session_id` per turn (env `KOSMOS_DEBUG_ROTATE_SESSION=1`). Run scenario A. Capture results.
- **H2-thinking isolation**: Set `KOSMOS_K_EXAONE_THINKING=false`. Run scenario A. Capture results.
- **H3-suffix isolation**: Skip BM25 suffix injection (env `KOSMOS_DEBUG_SKIP_BM25_SUFFIX=1`). Run scenario A. Capture results.

Each isolation test's debug flag is a single-line guard in the relevant code; remove all flags after T010 (do not ship debug flags to main).

**Acceptance**: All triggered isolation tests committed under `diagnostic-runs/isolation-<H>/`. T004's VERDICT.md updated to cite the isolation evidence and now name the SINGLE confirmed hypothesis.

---

### T006 — Update VERDICT.md + write fix-design appendix

**Files**: `specs/spec-multi-turn-contamination/diagnostic-runs/<verdict-run>/VERDICT.md`, `specs/spec-multi-turn-contamination/fix-design.md` (NEW)

**Surface**:
1. Finalize `VERDICT.md` with the unambiguous hypothesis verdict (after T004 + optional T005).
2. Write `fix-design.md` per `plan.md § F-1 / F-2 / F-3`:
   - Cite the verdict's H<N>.
   - Cite the file:line ranges to be modified.
   - If H2 (LLM client touch): cite the CC analog file:line range AND the swap category per Spec 2521 procedure.
   - Enumerate the swap commit sequence (byte-copy commit → labeled swap commits).
   - State explicitly: NO `ChatRequestFrame` shape changes (per FR-009).

**Acceptance**: `fix-design.md` is complete enough that any Sonnet teammate dispatched against T007-T010 can implement WITHOUT rereading the diagnostic logs.

**Dependency**: T004 (and T005 if triggered) must be DONE.

---

## Phase 3 — Fix Implementation (US2, FR-006..FR-011)

### T007 — Implement fix per verdict (file set determined by T006)

**Files**: Determined by `fix-design.md` from T006. Possibilities per `plan.md § F-1`:
- **H1 fix**: `tui/src/query/deps.ts:117-133` (snapshot `messages` correctly).
- **H2 fix**: `src/kosmos/ipc/stdio.py` agentic-loop message ordering (port CC's `yieldMissingToolResultBlocks` pattern from `services/api/claude.ts:957`).
- **H3 fix**: `src/kosmos/ipc/stdio.py` BM25 suffix or local message-list lifecycle.

**Surface**: Implement EXACTLY the change cited in `fix-design.md`. Cite the CC reference line in the commit message per AGENTS.md `feedback_cc_source_migration_pattern`. Do NOT change `ChatRequestFrame` shape (FR-009). Do NOT add runtime dependencies (FR-010).

**Verification (in-task)**: `pytest tests/python/ipc/` + `bun test tui/src/__tests__/` both green.

**Acceptance**: Re-run `repro-two-turn.sh --scenario A`. The captured `snap-002-turn2-done.txt` shows the citizen-correct turn-2 reasoning + tool dispatch (per spec US2 acceptance scenarios 1-3).

**Dependency**: T006 must be DONE.

---

### T008 — Verify fix at K-EXAONE-real layer (manual `@pytest.mark.live` smoke)

**Files**: `specs/spec-multi-turn-contamination/diagnostic-runs/post-fix/<UTC-timestamp>/` (NEW)

**Surface**:
1. Re-run `repro-two-turn.sh --scenario A` against the rebuilt branch with real FriendliAI K-EXAONE.
2. Capture all 3 diagnostic-run artefact types (backend.log + snaps).
3. Apply the discrimination matrix in REVERSE — confirm zero contamination signals across all matrix rows.
4. Run scenario B (negative control) again — confirm still no contamination (must not have been broken).
5. Run a NEW 4-turn scenario per spec US2 acceptance #4: turn 1 hospital → turn 2 disaster → turn 3 weather → turn 4 route-safety verify. Confirm zero contamination across all 4 turns.

**Acceptance**: All 3 directories committed under `diagnostic-runs/post-fix/`. Each directory's snaps demonstrate per-turn correctness. **This is the citizen-visible-correctness check that takes the methodology from "diagnosis + fix" to "verified fix".**

**Dependency**: T007 must be DONE.

---

### T009 — Remove debug isolation flags (only if T005 ran) **[P with T010]**

**Files**: Wherever T005 added flags (typically 1-2 files).

**Surface**: Strip the debug-only env flags introduced in T005. Confirm no flag survives into shipped code. Permanent diagnostic emits from T001/T002 remain (per FR-014).

**Acceptance**: `git grep KOSMOS_DEBUG_` returns 0 hits in `src/` and `tui/src/`.

**Dependency**: T007 (fix done first so isolation tests no longer needed).

---

### T010 — Build `intent-keyword-map.json` (FR-006 substring assertion source) **[P with T009]**

**Files**: `specs/spec-multi-turn-contamination/intent-keyword-map.json` (NEW)

**Surface**: Author the canonical mapping per spec "Key Entities → IntentKeywordMap". Initial seed:
```json
{
  "disaster": ["재난", "알림", "긴급", "subscribe", "구독", "경보"],
  "hospital": ["병원", "내과", "의원", "응급실", "hospital"],
  "weather": ["날씨", "기온", "비", "예보", "weather"],
  "route_safety": ["사고", "도로", "안전", "교통", "route"],
  "location_lookup": ["근처", "주변", "여기", "강남", "강남역"]
}
```
This is consumed by FR-012 unit test + FR-013 regression smoke. Korean is the only exception to AGENTS.md "all source text in English" — per the rule itself (Korean domain data).

**Acceptance**: JSON is valid. Loaded by both bun-test and pytest fixtures without error.

**Dependency**: T007 (the fix needs to know what shape of assertion to support).

---

## Phase 4 — Regression Lock + Documentation (US3 + US4, FR-012..FR-017)

### T011 — Regression test (Bun + pytest) (FR-012, FR-015)

**Files**: `tui/src/__tests__/multi-turn-contamination.test.ts` (NEW), `tests/python/ipc/test_chat_request_multi_turn.py` (NEW)

**Surface**:
1. **Bun side** (`tui/src/__tests__/multi-turn-contamination.test.ts`):
   - Stub bridge captures emitted `ChatRequestFrame` payloads.
   - Simulate two-turn `callModel` flow.
   - Assert: `frames[0].messages` tail content references turn-1 intent keywords; `frames[1].messages` tail content references turn-2 intent keywords; `frames[1].messages.length > frames[0].messages.length`.
   - Assert: NO frame's tail-user message has content matching any non-current-turn intent keyword.
   - On assertion failure, dump the captured `frames` JSON to test output (FR-015).
2. **Python side** (`tests/python/ipc/test_chat_request_multi_turn.py`):
   - Use a fake `LLMClient` returning canned reasoning_content.
   - Construct two consecutive `ChatRequestFrame`s (turn 1 + turn 2 per scenario A).
   - Invoke `_handle_chat_request` against both.
   - Assert: backend's `latest_user_utt` for turn 2 matches the turn-2 user message exactly.
   - Assert: when the fake LLM returns reasoning_content tagged with intent-keyword-map, the test correctly classifies turn-2 reasoning vs turn-1 contamination.
3. **Mutation-test gate** (FR-013 / SC-007 ): add a comment in BOTH test files documenting the verified mutation: "If `tui/src/query/deps.ts:117` is mutated to `messages.slice(0, -1)`, this test MUST fail."

**Acceptance**: Both tests PASS on the rebuilt branch. A throwaway commit reverting the fix from T007 causes BOTH tests to FAIL. Test output on failure includes the captured frames (FR-015).

**Dependency**: T007 + T010 done.

---

### T012 — ADR + diagnostic-runs commit + docs/testing.md update (FR-014, FR-016, SC-006) **[P with T011]**

**Files**: `docs/adr/ADR-NNN-multi-turn-contamination.md` (NEW), `docs/testing.md` (MODIFY), `specs/spec-multi-turn-contamination/scripts/regress-multi-turn.sh` (NEW)

**Surface**:
1. **ADR**: Five-section ADR (Status: Accepted / Context / Decision / Consequences / Alternatives) per `docs/adr/ADR-009-secureStorage-drop.md` template (Spec 2643). Decision section MUST cite specific log file paths under `specs/spec-multi-turn-contamination/diagnostic-runs/`. Alternatives section MUST enumerate H1/H2/H3 with the evidence that ruled out the rejected ones.
2. **`docs/testing.md` update**: Add a subsection under "TUI verification methodology" titled "Multi-turn diagnostic env vars" documenting `KOSMOS_CHAT_REQUEST_DUMP=1` and the existing-extended `KOSMOS_QUERY_TRACE=1`. Cite `specs/spec-multi-turn-contamination/scripts/repro-two-turn.sh` as the canonical scenario.
3. **`regress-multi-turn.sh`**: Layer 5 tmux smoke against `KOSMOS_LLM_PROVIDER=fake-multi-turn` deterministic stub backend (fake LLM returns canned per-turn reasoning matching the user message). `wait_for_pane <regex> <deadline>` per turn. Asserts via `grep` on captured pane that turn-2's reasoning blob references turn-2 keywords AND not turn-1 keywords.
4. **Commit** the diagnostic-runs/ pre-fix and post-fix directories together so the before/after demonstration lives in repo history.

**Acceptance**: ADR is complete (5 sections). `docs/testing.md` cites the new env vars + script. `regress-multi-turn.sh` runs green against the rebuilt branch + against a deliberately-reverted-fix throwaway commit it FAILS (per SC-007). All diagnostic-runs/ artefacts committed.

**Dependency**: T011 (regression assertions must already exist so the ADR's Decision section can cite them).

---

## Dependencies

```text
T001 (backend emit)  ─┐
T002 (frontend emit) ─┼─→ T003 (repro script) ─→ T004 (run + verdict) ─→ T005 (isolation, optional) ─→ T006 (fix-design)
                                                                    └────────────────────────────────────────┘
T006 ─→ T007 (implement fix) ─→ T008 (live smoke) ─→ T009 (debug-flag cleanup, P with T010)
                            └─→ T010 (intent-keyword-map, P with T009)
T010 + T007 ─→ T011 (regression tests)
T011 ─→ T012 (ADR + docs + regress script + commit diagnostic-runs)
```

## Parallelization

`[P]` markers: T001 ∥ T002 (independent files); T009 ∥ T010 (after T007); T011 ∥ T012 (after T010 + T011's test files exist).

User Story phases per AGENTS.md "Dispatch unit": US1 = T001-T006 (one Sonnet teammate, ≤6 tasks ≤8 file changes); US2 = T007-T010 (one Sonnet teammate, ≤4 tasks ≤6 file changes); US3+US4 = T011-T012 (one Sonnet teammate, ≤2 tasks ≤6 file changes). Lead Opus draws `dispatch-tree.md` BEFORE invoking any Agent per AGENTS.md hard rule.

## Independent Test Criteria

- **US1 (T001-T006)**: Diagnostic emit visible + verdict committed. Tested by reading `diagnostic-runs/<timestamp>/VERDICT.md` and confirming each rejected hypothesis has ≥1 ruling-out evidence line.
- **US2 (T007-T010)**: Two-turn scenario A turn-2 reasoning references disaster keywords + zero hospital keywords. Tested by `repro-two-turn.sh --scenario A` against rebuilt branch.
- **US3 (T011)**: `bun test` + `pytest` regression tests catch a synthetic re-introduction. Tested by deliberately reverting T007 in a throwaway commit and observing test failure.
- **US4 (T012)**: ADR + docs cite the concrete diagnostic evidence. Tested by reading the ADR cold and confirming the verdict + fix design are independently re-derivable.
