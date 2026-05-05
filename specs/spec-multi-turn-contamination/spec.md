# Feature Specification: Multi-turn Message-State Contamination Diagnosis & Fix

**Feature Branch**: `spec-multi-turn-contamination`
**Created**: 2026-05-04
**Status**: Draft
**Input**: Lead Opus directive 2026-05-04 — Lead-S2 evidence (`snap-S2-006` thinking blob first line: `"The user is asking for 강남역 근처 내과 which means..."`) demonstrates K-EXAONE on FriendliAI is NOT reasoning over the most-recent user turn (turn 2: "재난 알림 구독해줘"); instead it re-reasons over a stale prior turn (turn 1: "강남역 근처 내과") and even hallucinates an unrelated `resolve_location(query="강남구")` call. Subscribe-primitive smoke is blocked and ALL multi-turn UX is at risk.

## Problem Statement

In a clean session, the citizen sends two consecutive turns:
1. **Turn 1** — "강남역 근처 내과 찾아줘" (lookup hospital, succeeds).
2. **Turn 2** — "재난 알림 구독해줘" (subscribe-primitive request).

K-EXAONE's response to turn 2 begins its `reasoning_content` (thinking blob, captured in `snap-S2-006` of the integration-verification frame stream) with literal text "The user is asking for 강남역 근처 내과 which means..." — i.e. the model is reasoning over turn 1's payload, not turn 2's. Subsequently it emits `resolve_location(query="강남구")`, a query string that appears in **neither** turn 1 nor turn 2 (turn 1 contained "강남역", not "강남구"; turn 2 contained no location at all). The hallucinated location-name shape rules out a simple "off-by-one indexing" (which would have replayed turn 1 verbatim); something in the messages-array serialization, the K-EXAONE Hermes parser, or the parallel-tool-call accumulator is contaminating the per-turn prompt-state in a non-trivial way.

This contamination blocks the subscribe-primitive Layer 5 smoke (the second turn never gets a `subscribe(...)` call), and — more importantly — it threatens every multi-turn citizen scenario KOSMOS demos: any second turn risks being either silently dropped or replayed with a stale prior-turn payload. Single-turn flows (which is what every prior smoke captured) cannot detect this regression.

## Methodology — diagnosis before fix

Per AGENTS.md `feedback_partial_fix_revealed_by_better_infra` (Spec 2521 lesson): the FIRST commit MUST be a diagnostic instrumentation that proves WHICH layer is contaminating the message state. Three hypotheses are open and the spec MUST NOT pre-commit to one:

- **H1 — Frontend race condition.** `tui/src/query/deps.ts:122-130` walks `messages: Message[]` (CC's loose-typed transcript) and pushes `{role, content}` into `chatMessages: ChatMessage[]`. If turn 2's user message is appended to the React store AFTER `callModel` already snapshotted `messages`, the emitted `ChatRequestFrame.messages` tail would still be turn 1, and K-EXAONE is correctly reasoning over the only user message it received.
- **H2 — K-EXAONE thinking-state contamination.** FriendliAI's K-EXAONE 236B-A23B with `enable_thinking=true` may carry its own internal reasoning state across requests in some way (KV cache, attention sink, or the FriendliAI serverless multi-turn cache key collision); even with a correct `messages` array on the wire, the model's first reasoning token may anchor on whichever user-turn the FriendliAI-side cache keyed against this `session_id`.
- **H3 — Tool-call accumulation residue.** The agentic loop in `_handle_chat_request` (`src/kosmos/ipc/stdio.py:1786+`) accumulates `role="tool"` messages between turns. If turn 1's tool-result block is left in the local history and turn 2 prepends new user text without first re-anchoring the prompt, K-EXAONE's tail-attention may correctly identify turn 2's user message but its reasoning prelude may still be paraphrasing the most-recent assistant-turn that referenced "강남역 근처 내과".

The diagnostic phase (US1 / FR-001..FR-005) MUST collect evidence sufficient to discriminate among H1/H2/H3 BEFORE any fix is committed. Memory: `feedback_systematic_debugging`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Diagnostic instrumentation surfaces the contamination layer (Priority: P1)

A KOSMOS engineer, on encountering a multi-turn contamination bug report, can run a single PTY scenario script that reproduces the two-turn flow AND emits, to backend stderr, the byte-exact `ChatRequestFrame.messages` array as it arrives at `_handle_chat_request`, AND the byte-exact `messages: list[ChatMessage]` actually forwarded to the LLM client, AND the first 1024 bytes of K-EXAONE's `reasoning_content`. The engineer cross-correlates the three logs and concludes within minutes which of H1/H2/H3 is responsible.

**Why this priority**: Per AGENTS.md `feedback_partial_fix_revealed_by_better_infra`, fixing the symptom without the diagnostic infrastructure (which the existing tmux-capture harness lacks for IPC envelope dumps) leaves the next regression hidden behind the same blind spot. Diagnosis is mandatory before fix.

**Independent Test**: Run `specs/spec-multi-turn-contamination/scripts/repro-two-turn.sh`. Verify that `<outdir>/backend.log` contains:
1. one `[CHAT_REQUEST_DUMP] turn=1 messages=...` line whose tail message is `{role:'user', content:'강남역 근처 내과 찾아줘'}`,
2. one `[CHAT_REQUEST_DUMP] turn=2 messages=...` line whose tail message is `{role:'user', content:'재난 알림 구독해줘'}` AND whose preceding messages include turn 1's user text and the assistant tool-call result,
3. one `[REASONING_PREVIEW] turn=2 first1024=...` line capturing K-EXAONE's reasoning prelude.

**Acceptance Scenarios**:

1. **Given** a clean session and the diagnostic build, **When** the citizen sends turn 1 + turn 2, **Then** backend stderr shows exactly two `[CHAT_REQUEST_DUMP]` lines with monotonically growing `messages` arrays (turn 2 contains turn 1 in slots 0..N).
2. **Given** the diagnostic dumps from scenario 1, **When** the engineer compares `[CHAT_REQUEST_DUMP] turn=2`'s tail-user-content to `[REASONING_PREVIEW] turn=2`'s first 1024 bytes, **Then** mismatch → H2 or H3 confirmed; if `turn=2`'s tail-user-content is actually turn 1's text → H1 confirmed.
3. **Given** the diagnostic logs, **When** committed alongside the repro script under `specs/spec-multi-turn-contamination/diagnostic-runs/<timestamp>/`, **Then** the run is reproducible by any future maintainer + the committed log set discriminates the active hypothesis without re-running the bug.

---

### User Story 2 — Citizen's second turn is reasoned over second-turn payload (Priority: P1)

A citizen sends two unrelated requests in one session — turn 1 lookup-style (hospital), turn 2 subscribe-style (disaster alert). K-EXAONE's response to turn 2 reasons exclusively over turn 2's payload (no thinking-blob lines paraphrasing turn 1, no tool calls whose parameters originate in turn 1's text, no hallucinated parameters not in turn 2). Tool dispatch matches the turn-2 intent.

**Why this priority**: This is the citizen-visible correctness invariant. Without it, KOSMOS cannot demo any multi-turn flow — the second turn is non-deterministically replaced by a stale prior turn. P1 because it blocks the subscribe-primitive Layer 5 smoke AND every roadmap scenario beyond single-turn (proposal-iv 5-state Ministry Agent, /agents flow, every UI L2 acceptance scenario above one prompt).

**Independent Test**: After fix, replay `specs/spec-multi-turn-contamination/scripts/repro-two-turn.sh`. Assert in `<outdir>/snap-NNN-*.txt`:
1. Turn 2's reasoning blob first 256 chars contain "재난" or "구독" or "subscribe" — NOT "강남역" or "내과" or "병원".
2. Turn 2's primary tool call is `subscribe(...)`, not `resolve_location(...)` or `lookup(...)`.
3. No tool call in turn 2 has a `params.query` field whose value appears verbatim in turn 1 OR is not present in turn 2.

**Acceptance Scenarios**:

1. **Given** a clean session, **When** citizen sends turn 1 "강남역 근처 내과 찾아줘" and waits for completion, then sends turn 2 "재난 알림 구독해줘", **Then** turn 2's `assistant_chunk` thinking-content opens with text that references disaster-alert / subscribe semantics, not hospital / location semantics.
2. **Given** the same flow, **When** the agentic loop dispatches turn 2's first tool call, **Then** the tool name is one of `{subscribe, lookup}` with parameters semantically bound to turn 2's "재난 알림" intent.
3. **Given** the contamination is fixed, **When** the regression test (US3 / FR-013) runs in CI, **Then** PASS for both turn-1-only-substring rule AND turn-2-tool-name rule.
4. **Given** a deeper 4-turn scenario (turn 1 lookup hospital, turn 2 subscribe disaster, turn 3 lookup weather, turn 4 verify route safety), **When** the same fix is in place, **Then** turn 3 and turn 4 are reasoned over their own payloads without contamination from any prior turn (no upper bound on turn count required for THIS spec; the fix MUST be O(1)-correct per turn).

---

### User Story 3 — Multi-turn regression test locks the fix permanently (Priority: P1)

A maintainer adds an automated test that fails if any future change re-introduces multi-turn contamination. The test runs in `bun test` (Layer 1b Ink snapshot via `ink-testing-library`) AND in a Layer 5 tmux smoke (`scripts/tui-tmux-capture.sh`) and is enumerated in CI. Diagnostic stderr lines are still emitted (under env-var gate `KOSMOS_CHAT_REQUEST_DUMP=1`) so future investigations skip re-instrumenting the backend.

**Why this priority**: AGENTS.md anti-pattern #1 ("final-state fallacy") + memory `feedback_pty_log_full_inspection` — the existing single-turn smokes literally cannot catch this regression. Without a multi-turn lock test, the fix decays at the next refactor. P1 because the diagnostic + fix without a lock is two-thirds of the work.

**Independent Test**: Two regression assets MUST exist after this Epic merges:
1. `tui/src/__tests__/multi-turn-contamination.test.ts` — `ink-testing-library` simulates turn 1 + turn 2, intercepts the emitted `ChatRequestFrame` payloads via a stub bridge, asserts message-array tail invariants.
2. `specs/spec-multi-turn-contamination/scripts/regress-multi-turn.sh` — Layer 5 tmux scenario that runs against a real backend (with `KOSMOS_LLM_PROVIDER=fake-multi-turn` deterministic stub, NOT FriendliAI) and asserts turn-2's tool-call name / params via `wait_for_pane <regex> <deadline>`.

Live FriendliAI E2E verification is run manually under `@pytest.mark.live` per AGENTS.md "Never call live `data.go.kr` APIs from CI tests" + the LLM equivalent.

**Acceptance Scenarios**:

1. **Given** the regression test in `tui/src/__tests__/`, **When** `bun test` runs, **Then** PASS on the rebuilt branch + FAIL on a synthetic regression that re-introduces an off-by-one in `chatMessages` construction (verified by mutation-testing one-liner: replace `messages` with `messages.slice(0, -1)` in `tui/src/query/deps.ts:117`).
2. **Given** the Layer 5 smoke script under `specs/spec-multi-turn-contamination/scripts/`, **When** executed, **Then** every committed `snap-*.txt` keyframe demonstrates turn-2 → turn-2 reasoning without turn-1 leakage.
3. **Given** `KOSMOS_CHAT_REQUEST_DUMP=1` in env, **When** any subsequent multi-turn run executes, **Then** backend stderr re-emits the diagnostic lines from US1 — opt-in, zero overhead by default (AGENTS.md hard rule: stdlib `logging` only, KOSMOS_-prefixed env, no `print()`).

---

### User Story 4 — Hypothesis verdict + ADR is written into the repo (Priority: P2)

After diagnosis converges, the active hypothesis (H1 / H2 / H3) is documented as an ADR under `docs/adr/` with: the diagnostic evidence cited from US1 commits, the fix design, and the rejected alternatives. Future maintainers reading a similar bug report can reach the verdict + the rationale without re-running the diagnostic.

**Why this priority**: Knowledge persistence. Without the ADR, the next person hitting a similar symptom will re-instrument from scratch, despite the diagnostic + fix already being committed. P2 because the regression test (US3) prevents recurrence operationally; the ADR prevents conceptual drift.

**Independent Test**: After Epic merge, `ls docs/adr/ADR-NNN-multi-turn-contamination*.md` returns one file containing exactly the five ADR sections (Status / Context / Decision / Consequences / Alternatives) with citations into `specs/spec-multi-turn-contamination/diagnostic-runs/`.

**Acceptance Scenarios**:

1. **Given** the diagnostic logs from US1, **When** the ADR is written, **Then** the "Decision" section names the confirmed hypothesis (H1 OR H2 OR H3) and points to the specific log line that confirms it.
2. **Given** the ADR exists, **When** a maintainer reads it cold, **Then** they can independently re-derive the fix from the diagnostic evidence without external context.

---

### Edge Cases

- **Tool-result re-injection between turns** — The agentic loop injects synthetic `role="tool"` messages mid-turn. Does the count of tool-result messages between turn 1's user message and turn 2's user message change the contamination? (Likely H3 signal.)
- **`session_id` collision on FriendliAI side** — Does the contamination disappear if the TUI rotates `session_id` on every `ChatRequestFrame`? (H2 isolation test — but breaks Spec 027 session continuity, so ONLY a diagnostic, never a fix.)
- **`enable_thinking=false` flag** — Does setting `KOSMOS_K_EXAONE_THINKING=false` eliminate the contamination, or merely hide the reasoning blob while the tool calls remain wrong? (Discriminates H2 from H3.)
- **First-turn-only sessions** — Does a session with only one turn ever show this symptom? (Negative control — should always be NO; if YES, the bug is unrelated to multi-turn and is in single-turn message ordering.)
- **Three-or-more-turn drift** — Does the contamination amplify with turn count, or is it strictly turn-2-replays-turn-1? (Discriminates O(1) state from accumulating residue.)
- **Tool-result-only second turn** — If turn 1 errors and the user retries identically, does the same contamination shape appear? (Isolates user-text-content from tool-result-state.)
- **Same-text two turns** — If the citizen sends "강남역 근처 내과" twice in a row, can we still detect the bug? (Negative control — would silently appear correct under H1, would still emit a thinking blob anomaly under H2/H3 if any.)

## Requirements *(mandatory)*

### Functional Requirements — Diagnosis Phase (US1)

- **FR-001**: Backend `_handle_chat_request` MUST emit a `[CHAT_REQUEST_DUMP] turn=<N> ...` stderr line on every invocation when `KOSMOS_CHAT_REQUEST_DUMP=1`. The line MUST contain: the full `frame.messages` array (each entry's role + content first 256 chars + tool_call_id if present), the `correlation_id`, the `session_id`, and a turn counter scoped to the session.
- **FR-002**: Backend MUST emit a `[REASONING_PREVIEW] turn=<N> first1024=<...>` stderr line containing the first 1024 bytes of K-EXAONE's `reasoning_content` for that turn, on the same env gate. Truncate at 1024 to bound log size; mark truncation explicitly.
- **FR-003**: Frontend `tui/src/query/deps.ts:122-130` MUST emit a `[CHAT_MESSAGES_BUILT] turn=<N> count=<K> tail_role=<...> tail_text_first256=<...>` stderr line on every `callModel` invocation when `KOSMOS_QUERY_TRACE=1` (the existing trace gate — extend, do not add a new env var).
- **FR-004**: A new `specs/spec-multi-turn-contamination/scripts/repro-two-turn.sh` MUST execute the canonical two-turn scenario (hospital → disaster-alert) inside the tmux capture harness, capture all three diagnostic streams (FR-001/FR-002/FR-003), and snapshot `snap-NNN-*.txt` per turn.
- **FR-005**: Diagnostic logs from one canonical reproduction run MUST be committed under `specs/spec-multi-turn-contamination/diagnostic-runs/<timestamp>/` so the verdict in US4's ADR is reproducible by reading repo state alone.

### Functional Requirements — Fix Phase (US2)

- **FR-006**: K-EXAONE's `reasoning_content` first 256 bytes for turn N MUST contain at least one substring matching the user's turn-N intent (subscribe / disaster / weather / hospital / etc., per a small canonical intent-keyword map maintained alongside this spec). MUST NOT contain any substring uniquely identifying any prior turn (per the same map).
- **FR-007**: Tool calls dispatched in response to turn N MUST have parameter values either (a) extractable from turn N's text via simple substring match, (b) standard derived values (e.g. resolve_location output for a place name in turn N), or (c) tool-internal defaults. MUST NOT contain values uniquely traceable to a prior turn AND not derivable from turn N.
- **FR-008**: The fix MUST be at the layer the diagnostic phase confirms (FR-001..FR-005). The spec deliberately does NOT pre-commit to the fix layer; tasks.md derives the fix surface from the diagnostic verdict.
- **FR-009**: If the fix involves changing the IPC `ChatRequestFrame` envelope (Spec 032), the change MUST follow Spec 032 ADR cycle — no silent envelope mutation. If the fix is purely Python or purely TS, the change MUST cite the file + line range under `.references/claude-code-sourcemap/restored-src/` (CC analog) per AGENTS.md `feedback_cc_source_migration_pattern`.
- **FR-010**: The fix MUST NOT introduce any new runtime dependency (AGENTS.md hard rule — Python or TS).
- **FR-011**: The fix MUST NOT touch the K-EXAONE / FriendliAI client surface (`src/kosmos/llm/client.py` and adjacent) unless the diagnostic phase confirms H2 (K-EXAONE itself), in which case the fix MUST cite Spec 2521's strict CC byte-copy procedure for any LLM-client-layer changes.

### Functional Requirements — Regression Lock (US3)

- **FR-012**: A `tui/src/__tests__/multi-turn-contamination.test.ts` Bun unit test MUST exist that asserts: given a stub bridge, a two-turn `callModel` flow emits two `ChatRequestFrame`s where the second frame's `messages` array tail is the second user message AND the first frame's `messages` array tail is the first user message.
- **FR-013**: A `specs/spec-multi-turn-contamination/scripts/regress-multi-turn.sh` Layer 5 tmux smoke MUST exist that runs against a deterministic fake LLM backend (`KOSMOS_LLM_PROVIDER=fake-multi-turn`) and asserts via `wait_for_pane <regex> <deadline>` that turn-2's reasoning blob references turn-2's intent, NOT turn-1's. (Real FriendliAI verification stays out of CI per AGENTS.md.)
- **FR-014**: The diagnostic stderr emitters from FR-001/FR-002/FR-003 MUST remain in production code, gated by env var, with documented activation in `docs/testing.md § TUI verification methodology` so future contamination diagnoses skip re-instrumentation.
- **FR-015**: Regression test failures MUST report enough detail to discriminate among H1/H2/H3 directly from the test output (e.g. log the captured `messages` array on assertion failure).

### Functional Requirements — Documentation (US4)

- **FR-016**: One ADR MUST exist under `docs/adr/ADR-NNN-multi-turn-contamination.md` with the five mandatory sections (Status / Context / Decision / Consequences / Alternatives). The Decision section MUST cite the specific diagnostic log line confirming the hypothesis. The Alternatives section MUST enumerate all three hypotheses (H1/H2/H3) with the evidence that ruled out the rejected ones.
- **FR-017**: AGENTS.md memory entry SHOULD be added (manual user-facing step, not a code change in this spec) capturing the systematic-debugging pattern (diagnostic → fix → regression-lock) for multi-turn LLM contamination class of bugs.

### Key Entities

- **TurnContext** — Per-turn snapshot of `(turn_index, user_text, ChatRequestFrame.messages, K-EXAONE reasoning_content first 1024 bytes, dispatched tool calls)`. Diagnostic envelope; lives in stderr logs and (after this Epic) in the regression test fixtures.
- **ContaminationVerdict** — Enum `{H1_FRONTEND_RACE, H2_KEXAONE_INTERNAL, H3_TOOL_RESULT_RESIDUE, NONE}`. Output of US1 diagnosis; input to US2 fix design.
- **IntentKeywordMap** — Small canonical mapping `{intent_class → set[keyword]}` (e.g. `disaster → {재난, 알림, 긴급, subscribe}`, `hospital → {병원, 내과, 의원}`). Used by FR-006 reasoning-content substring assertion. Lives at `specs/spec-multi-turn-contamination/intent-keyword-map.json`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of `bun test` and `pytest` passes after the fix lands. Multi-turn regression tests (FR-012) added — green on first run after fix.
- **SC-002**: The canonical two-turn repro (FR-004) executed against the fixed branch shows: turn-2 reasoning-blob first 256 chars contain ≥1 disaster-intent keyword AND zero hospital-intent keywords. Pre-fix run (committed under `diagnostic-runs/`) shows the inverse, providing a black-box before/after demonstration.
- **SC-003**: A 4-turn scenario (US2 acceptance #4) shows zero contamination across all four turns. Per-turn reasoning-blob keyword check passes for turns 2 / 3 / 4.
- **SC-004**: One ADR + ≥3 diagnostic-run log directories are committed under `docs/adr/` and `specs/spec-multi-turn-contamination/diagnostic-runs/`. The Decision section of the ADR cites a specific log file path + line in those directories.
- **SC-005**: Zero new runtime dependencies introduced (Python `pyproject.toml` and TS `tui/package.json` lockfile diff = 0 lines).
- **SC-006**: Diagnostic env vars `KOSMOS_CHAT_REQUEST_DUMP=1` and `KOSMOS_QUERY_TRACE=1` documented in `docs/testing.md § TUI verification methodology`. Manual run instructions reproduce the diagnostic-runs/ artefacts byte-identically (modulo timestamps).
- **SC-007**: Regression test in CI catches a synthetic re-introduction of the bug — verified by deliberately reverting the fix in a throwaway commit and observing the test fail.

## Assumptions

- **A1** — The contamination is reproducible on demand with the canonical two-turn scenario (hospital → disaster-alert). If the bug turns out to be flaky / non-deterministic under reproduction, the spec's diagnostic phase MUST escalate to capturing N consecutive runs and reporting the failure rate before proceeding to fix.
- **A2** — K-EXAONE on FriendliAI Tier 1 is the operative LLM (per AGENTS.md L1-A pillar A1 + memory `project_friendli_tier_wait`). The fix MUST hold for that exact LLM + provider combination; behavior on alternative providers is out of scope.
- **A3** — The existing Spec 032 IPC envelope is correct in shape; the contamination is at the message-content layer or below (frontend assembly, backend forwarding, or LLM internal state), NOT at the envelope-discrimination layer.
- **A4** — The agentic loop's bound (`KOSMOS_AGENTIC_LOOP_MAX_TURNS=8`) is unrelated to this bug; the contamination occurs on turn 2 well below that bound.
- **A5** — The TUI's React message store correctly accumulates user messages across turns (verified by Spec 287 + Spec 1635 acceptance smokes); if H1 is confirmed, the contamination is in the snapshot timing of `messages` BY `callModel`, not in the store itself.
- **A6** — `parallel_tool_calls=False` (Spec 2521 hotfix, memory `feedback_llm_api_option_first_suspect`) is in effect; this spec does NOT re-litigate that decision.
- **A7** — A deterministic fake LLM backend (`fake-multi-turn`) suitable for CI smoke (FR-013) either exists or can be added as a tiny extension to the existing test infra without introducing a new dependency.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- **Full conversation summarization / compaction redesign** — Spec 026 owns prompt-cache + compaction. This spec touches multi-turn message ordering only, not summarization.
- **K-EXAONE model fine-tuning or system-prompt re-engineering** — KOSMOS does not control the K-EXAONE model. If H2 confirms, the fix is workaround at the IPC / client layer, not a model-side change.
- **Cross-session contamination** — This spec is scoped to multi-turn WITHIN ONE session. Cross-session leakage is a separate (and so-far unobserved) failure mode tracked separately if it ever surfaces.
- **Performance optimization of the agentic loop** — The fix MUST be O(1)-per-turn correct, but speedups beyond that are not in scope.
- **TUI / Ink UI changes for displaying turn boundaries** — Citizen-facing UI is unchanged. The fix is invisible-when-correct (which is the point).

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Real-FriendliAI E2E live test of multi-turn contamination | AGENTS.md hard rule: no live LLM in CI | `@pytest.mark.live` manual smoke | NEEDS TRACKING |
| Other K-EXAONE-on-FriendliAI multi-turn pathology classes (e.g. cross-tool reasoning leak, KV-cache stale-prompt) | Unknown until US1 diagnosis runs; if observed, file separate bug | TBD | NEEDS TRACKING |
| ADR update if a future K-EXAONE / FriendliAI release changes the underlying behavior | Speculative — only if upstream releases break this fix | TBD | NEEDS TRACKING |
| Generalize the diagnostic harness (FR-001/FR-002/FR-003) into a reusable IPC envelope dump for ALL frame arms (not just chat_request) | Out of scope for this contamination-specific Epic | Spec 032 follow-up | NEEDS TRACKING |
