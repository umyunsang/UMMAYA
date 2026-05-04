# Spec: Runtime UX Bug Fixes — Batch 2 (Epic #2766)

> Date: 2026-05-04
> Initiative: #2636 follow-up (post-PR #2754)
> Epic: #2766
> Spec-driven cycle: /speckit-specify (autonomous)

## Background

PR #2754 (Initiative #2636 Layer 5 verification) shipped 6 runtime fixes. After
merge, citizen interactive testing surfaced 4 additional UX bugs that block
trust in the citizen-facing surface:

1. KST timezone: `meta.fetched_at` shown in UTC → "어제 호출"
2. Tool-call rendering order inverted → answer ABOVE tool result
3. HIRA "Baked/Brewed for 1m 5s" timeout → no result
4. Ctrl+O expand keybinding silent

All four are first-encounter user impressions; they make the system look broken
even when the underlying tool chain is sound.

## Goals (in scope)

- Fix all 4 issues with minimal blast radius. Defense-in-depth, not band-aid.
- Preserve byte-identical CC behavior wherever the bug is upstream of the swap
  surface. Modify KOSMOS swap layers only.
- Keep AGENTS.md hard rules: zero new runtime deps, English source, KST only
  on citizen-facing strings (OTEL/audit ledger stays UTC).

## Non-goals

- Refactoring the broader render pipeline.
- Restructuring the K-EXAONE thinking budget across all adapters (only diagnose
  the HIRA path).
- Adding new shortcut UX (only restore Ctrl+O working state).

## User Stories

### US1 — KST timezone in citizen-facing metadata
**As a** citizen calling `lookup(mode='fetch')` against a KMA / HIRA / KOROAD
adapter,
**I see** `meta.fetched_at` in Asia/Seoul timezone (KST, +09:00) so the
displayed time matches my local clock.

**Acceptance**:
- [ ] `envelope.normalize()` stamps KST.
- [ ] `lookup.py` resolve_location wrapper stamps KST.
- [ ] `worker.py` text-response synthetic envelope stamps KST.
- [ ] All adapter-level `LookupMeta(fetched_at=...)` stamps use KST (KMA, mocks).
- [ ] Existing pytest suite still PASS.
- [ ] OTEL spans + audit ledger keep their existing UTC stamping (orthogonal).

### US2 — Tool call renders BEFORE assistant answer
**As a** citizen reading the assistant response,
**I see** the tool invocation (`⏺ tool(...)` + `⎿ result`) BEFORE the prose
answer that interprets the result, matching CC convention.

**Acceptance**:
- [ ] On a `weather` query, frame snapshot shows `⏺ kma_short_term_forecast(…)
      → ⎿ record(...) → ⏺ <assistant prose>` order.
- [ ] StreamGate verified to suppress assistant prose chunks emitted in the
      same Hermes message that contains a `<tool_call>` block.
- [ ] LLM-side `parallel_tool_calls=False` is preserved (already shipped).
- [ ] No regression on plain conversational turns (no tool_call → prose still
      streams as before).

### US3 — HIRA hospital search completes within budget
**As a** citizen asking `동아대학교 근처 내과 병원 알려줘`,
**I see** a result (Markdown table or Korean error toast) within ≤ 90 s; the
spinner reflects what stage is in progress (LLM thinking vs HTTP fetch vs
parsing).

**Acceptance**:
- [ ] Backend stderr trace captured; root-cause stage identified (logged in
      `specs/2766-runtime-ux-bugs/research.md`).
- [ ] If LLM thinking budget — adjust K-EXAONE timeout or retry strategy.
- [ ] If HIRA HTTP latency — bump per-adapter timeout in `executor.py` or add
      one transient retry.
- [ ] If parser failure — surface as graceful error envelope.
- [ ] Spinner label updated when known stage is identifiable.
- [ ] `@pytest.mark.live` HIRA hospital test still skipped by default but
      passes when enabled (no regression).

### US4 — Ctrl+O expands long output / thinking
**As a** citizen viewing a long response or hidden thinking block,
**I press** Ctrl+O and the transcript expands as documented in CC.

**Acceptance**:
- [ ] Ctrl+O resolves to `app:toggleTranscript` and the handler runs.
- [ ] If chord-resolver path is broken, `useInput` fallback gates Ctrl+O
      directly (PR #2754 Insight #4 pattern).
- [ ] Layer 4 vhs scenario shows expand visible-state change.

## Constraints (FRs)

- **FR-001**: Asia/Seoul timezone applied ONLY to citizen-visible
  `LookupMeta.fetched_at`; OTEL spans / audit ledger keep UTC.
- **FR-002**: Zero new Python or TS runtime dependencies.
- **FR-003**: All source text in English; comments may explain Korean
  citizen-facing UX (memory rule).
- **FR-004**: Render-order fix MUST NOT block plain conversational turns.
- **FR-005**: HIRA timeout fix MUST NOT mask genuine network failures (still
  surface error envelope).
- **FR-006**: Ctrl+O fix preserves CC chord-registry semantics; fallback only
  activates if chord registry returns `none` for a Ctrl+O keypress.

## Verification

- Layer 1: `uv run pytest` + `bun test` — zero regression.
- Layer 5: Bun PTY harness (existing `scripts/bun-pty-capture.ts`) for
  weather + hospital + Ctrl+O scenarios.
- Layer 4: vhs `.tape` for each issue with PNG keyframes (before/after where
  feasible).
- 4 issue artefacts under `specs/2766-runtime-ux-bugs/frames/`.

## References

- `docs/vision.md § Reference materials`
- `AGENTS.md § TUI verification methodology` (5 layers + 7 anti-patterns)
- `specs/integration-verification/RUNTIME-BUGS.md` (PR #2754 fix history)
- `specs/integration-verification/PROMPTS.md` (33 vhs scenarios)
- `.references/claude-code-sourcemap/restored-src/` (CC 2.1.88 byte baseline)
- Memory: `feedback_llm_api_option_first_suspect`, `feedback_debug_infra_rebuild`
