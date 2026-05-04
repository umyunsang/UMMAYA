# Tasks: Runtime UX Bug Fixes — Batch 2 (Epic #2766)

> 4 user stories, 4 task-groups (US1 KST, US2 StreamGate, US3 HIRA, US4 Ctrl+O).
> All US1-US4 are independent → `[P]` parallel-safe sonnet teammate dispatch.

## Phase 1 — Setup (Lead solo)

- [ ] **T001** — Verify worktree and branch state. `git status` clean except
      uncommitted KST patch already staged in working dir.

## Phase 2 — Foundational diagnostics (Lead solo)

- [ ] **T002** — Capture baseline frames: run weather + hospital + Ctrl+O
      scenarios on current HEAD; save under
      `specs/2766-runtime-ux-bugs/frames/before/`.

## Phase 3 — User Story 1: KST timezone (sonnet-A)

- [P] **T010** — Apply KST patch to envelope.py (already in working-dir).
- [P] **T011** — Apply KST patch to lookup.py (already in working-dir).
- [P] **T012** — Apply KST patch to worker.py (already in working-dir).
- [P] **T013** — Apply KST patch to 5 mock adapters (already in working-dir).
- [P] **T014** — Patch `src/kosmos/tools/kma/forecast_fetch.py` so that `meta.fetched_at`
      uses KST. Keep `t_start = datetime.now(tz=UTC)` for elapsed math but
      construct `LookupMeta(fetched_at=datetime.now(tz=_SEOUL_TZ))` (or
      `t_start.astimezone(_SEOUL_TZ)`).
- [P] **T015** — Add unit test asserting `envelope.normalize()` returns
      `meta.fetched_at.tzinfo == ZoneInfo("Asia/Seoul")`.
- [ ] **T016** — Run `uv run pytest src/kosmos/tools/` — zero regression.

## Phase 4 — User Story 2: StreamGate render order (sonnet-B)

- [P] **T020** — Reproduce: instrument StreamGate.feed/flush with debug log
      capturing every chunk before/after; run weather scenario; capture trace
      to `specs/2766-runtime-ux-bugs/research-streamgate.md`.
- [P] **T021** — Decide fix path (StreamGate buffer vs engine reorder vs LLM
      prompt rule). Document choice in research-streamgate.md.
- [P] **T022** — Implement chosen fix.
- [P] **T023** — Unit test: StreamGate with synthetic Hermes
      `"answer<tool_call>{...}</tool_call>"` → assert prose emission deferred.
- [P] **T024** — Frame proof: weather scenario shows `tool_call → result →
      prose` order in PNG keyframe under
      `specs/2766-runtime-ux-bugs/frames/after/`.

## Phase 5 — User Story 3: HIRA timeout (sonnet-C)

- [P] **T030** — Reproduce: run hospital scenario via Bun PTY; capture stderr
      + OTLP trace; identify which stage exceeds budget. Document in
      `specs/2766-runtime-ux-bugs/research-hira.md`.
- [P] **T031** — Add `kosmos.tool.stage` span attribute (thinking/fetch/parse).
- [P] **T032** — Bump per-tool timeout for HIRA (or generic per-adapter
      `timeout_ms` in GovAPITool with adapter override).
- [P] **T033** — Add 1 transient retry on `httpx.ReadTimeout` only.
- [P] **T034** — Update spinner label so the citizen sees current stage.
- [P] **T035** — Frame proof: hospital scenario completes within ≤ 90 s with
      Markdown table.

## Phase 6 — User Story 4: Ctrl+O keybinding (sonnet-D)

- [P] **T040** — Diagnose: capture key event for Ctrl+O via
      `useInput((input,key)=>console.log(JSON.stringify({input,key})))` smoke
      script; confirm whether chord resolver fires `match` or `none`.
- [P] **T041** — If chord registry returns `none`: add `useInput` fallback in
      `useGlobalKeybindings.tsx` that triggers `handleToggleTranscript` on
      `key.ctrl && input === 'o'`.
- [P] **T042** — If chord registry returns `match` but handler doesn't fire:
      trace context activation order (KeybindingProviderSetup ordering).
- [P] **T043** — Snapshot test: render REPL → press Ctrl+O → assert transcript
      mode toggles.
- [P] **T044** — Frame proof: Ctrl+O scenario shows expanded vs collapsed.

## Phase 7 — Polish (Lead solo)

- [ ] **T050** — Run full `uv run pytest` + `bun test` suites.
- [ ] **T051** — Author `specs/2766-runtime-ux-bugs/dispatch-tree.md`.
- [ ] **T052** — Capture final frame matrices (4 issues, before/after).
- [ ] **T053** — `git add` + Conventional Commit + push.
- [ ] **T054** — `gh pr create --body "Closes #2766"` (no Task sub-issues).
- [ ] **T055** — `gh pr checks --watch` until green.
- [ ] **T056** — Codex review fetch + reply to P1/P2 inline comments.
