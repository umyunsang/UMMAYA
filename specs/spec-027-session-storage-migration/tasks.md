# Tasks — Spec 027 Session Storage Path Migration

**Spec**: `specs/spec-027-session-storage-migration/spec.md`
**Plan**: `specs/spec-027-session-storage-migration/plan.md`
**Initiative**: #2290 Epic 3.

10 tasks. Dependency-ordered. `[P]` markers identify parallel-safe groups for `/speckit-implement` Sonnet teammate dispatch (per AGENTS.md Agent Teams rules; ≤5 tasks AND ≤10 file changes per teammate).

---

## Phase 1 — Foundational (sonnet-foundational)

### T001 — Add canonical KOSMOS path env var to backend pydantic-settings catalog

**Files**:
- `src/kosmos/config.py` (or wherever `BaseSettings` lives — verify in R-2 mapping).

**Action**:
- Confirm `KOSMOS_MEMDIR_USER` is declared in the pydantic-settings env catalog. If absent (Spec 027 may have added it; otherwise Spec 1635 P4 introduced it for `uiL2Memdir.ts:25`), add it as `KOSMOS_MEMDIR_USER: Path = Path.home() / ".kosmos" / "memdir" / "user"` with description: `"USER-tier memdir root (Spec 027). Sessions, consent, ministry-scope, plugins, onboarding, preferences live here."`
- Confirm `KOSMOS_SESSION_DIR` continues to exist for back-compat with the existing Python override at `src/kosmos/session/store.py:42`.

**Acceptance**:
- `uv run python -c "from kosmos.config import settings; print(settings.kosmos_memdir_user)"` prints the expected default.
- Setting `KOSMOS_MEMDIR_USER=/tmp/test` env then re-running prints `/tmp/test`.

**Reference**: Spec 1635 P4 `tui/src/utils/uiL2Memdir.ts:25-26` (pattern to mirror).

---

### T002 — Create `tui/src/utils/kosmosPaths.ts` with `getKosmosSessionsDir()` helper [P]

**Files**:
- `tui/src/utils/kosmosPaths.ts` (NEW, ~40 LOC).

**Action**:
- New module exporting:
  - `getKosmosUserTierRoot()`: returns `process.env['KOSMOS_MEMDIR_USER'] ?? join(homedir(), '.kosmos', 'memdir', 'user')` (string).
  - `getKosmosSessionsDir()`: returns `join(getKosmosUserTierRoot(), 'sessions')`.
  - `getKosmosTranscriptPath(sessionId)`: returns `join(getKosmosSessionsDir(), '<sessionId>.jsonl')`.
- Each helper memoized via `lodash-es/memoize` keyed off `process.env['KOSMOS_MEMDIR_USER']` (matches `getClaudeConfigHomeDir` pattern at `tui/src/utils/envUtils.ts:7-14`).
- Fail-closed: import-time check is NOT done (helpers are called per-request); the actual `mkdir -p` happens at write time inside the existing `appendEntryToFile` machinery.
- File header comment cites Spec 027 + Spec 1635 P4 precedent.

**Acceptance**:
- `bun test tui/src/utils/__tests__/kosmosPaths.test.ts` — 3 tests pass: default path, env override, memoization clears on env change.

**Reference**: `tui/src/utils/uiL2Memdir.ts:25-26`.

**Parallel-safe**: YES — new file, no existing edits.

---

## Phase 2 — TUI write path repoint (sonnet-tui-write)

### T003 — Repoint `getProjectsDir()` body in `sessionStorage.ts`

**Files**:
- `tui/src/utils/sessionStorage.ts` (single-line behavior change at line 203-205, plus 2-line comment update).

**Action**:
- Change `getProjectsDir()` body from `return join(getClaudeConfigHomeDir(), 'projects')` to `return getKosmosSessionsDir()`. Add `import { getKosmosSessionsDir } from './kosmosPaths.js'` at top.
- Add comment block above the function: `// KOSMOS Spec 027 path migration: returns the canonical USER-tier sessions dir. The CC native '<config-home>/projects' layout is now legacy-discovery only via getCCLegacyProjectsDir() below.`
- Add a new helper `getCCLegacyProjectsDir(): string` that returns the *old* `join(getClaudeConfigHomeDir(), 'projects')` value for FR-005 dual-path read-only enumeration.
- Audit lines 4122-4173 and 3986-4031 (existing `readdir(projectsDir, ...)` enumeration call-sites) — those become *legacy*-readers; add a new sibling enumeration that walks the KOSMOS path, then merge results (T008 covers tests).
- Keep `getProjectDir(projectDir)` (memoized cwd-sanitizer) intact — it is now used ONLY by the legacy-discovery surface.

**Acceptance**:
- `bun test tui/src/utils/__tests__/sessionStorage.test.ts` passes (existing snapshots; FR-013 backward-compat).
- Manual smoke: launch TUI, type a prompt, exit, verify new JSONL appears under `~/.kosmos/memdir/user/sessions/` not `~/.claude/projects/`.

**Reference**: `.references/claude-code-sourcemap/restored-src/utils/sessionStorage.ts` (CC native shape we are leaving in place for legacy reads).

**Depends on**: T002.

---

### T004 — Repoint `getProjectsDir()` body in `sessionStoragePortable.ts` [P with T003 only after T002]

**Files**:
- `tui/src/utils/sessionStoragePortable.ts` (single-line behavior change at line 325-327).

**Action**:
- Identical change to T003 but for the portable variant. Add `import { getKosmosSessionsDir } from './kosmosPaths.js'`.
- Add `getCCLegacyProjectsDir()` sibling here too (the portable variant is consumed by the SDK + agent-sdk path; both need dual-path discovery).

**Acceptance**:
- `bun test tui/src/utils/__tests__/sessionStoragePortable.test.ts` passes.
- `bun test tui/src/utils/__tests__/listSessionsImpl.test.ts` passes (covers `listSessionsImpl()` consumer of `getProjectsDir`).

**Depends on**: T002. May run in parallel with T003 (different file, no shared state).

---

## Phase 3 — Migration helper (sonnet-migration)

### T005 — Implement migration helper module `migrateSessions.ts`

**Files**:
- `tui/src/utils/migrateSessions.ts` (NEW, ~120 LOC).
- `tui/src/utils/__tests__/migrateSessions.test.ts` (NEW, ~80 LOC).

**Action**:
- Export `async function migrateSessions(opts: { prune?: boolean }): Promise<MigrationSummary>`.
- Behavior: enumerate every `<sanitized-cwd>/<session_id>.jsonl` under `getCCLegacyProjectsDir()`. For each:
  - Compute KOSMOS dest = `getKosmosTranscriptPath(sessionId)`.
  - If dest exists → skip with `action: 'skip-collision'`.
  - Else → byte-copy with `fs.copyFile(src, dest, COPYFILE_EXCL)`, then explicit `fsync` on dest.
  - If `opts.prune === true` AND copy succeeded → `fs.unlink(src)`.
- Aggregate `MigrationSummary { copied: number, skipped: number, pruned: number, bytes: number, errors: Array<{path, errno}> }`.
- Emit OTEL spans per FR-012 with attributes `kosmos.session.path_root`, `kosmos.session.migration_action`.
- Crash-safety: never unlink before fsync resolves. Abort entire batch on any non-EEXIST/ENOENT error to avoid partial-prune state.

**Acceptance**:
- 8 unit tests (Bun `bun:test`):
  1. Empty legacy dir → summary `{copied: 0, ...}`.
  2. 3 legacy files, no collisions → 3 copied, KOSMOS dir contains 3.
  3. 3 legacy files, 1 collision (same `session_id` already at KOSMOS) → 2 copied, 1 skip-collision.
  4. Idempotent re-run → second invocation returns `{copied: 0, skipped: 3, ...}`.
  5. `prune: true` → legacy files unlinked after fsync.
  6. `prune: true` + simulated fsync error → no files unlinked, summary contains error entry.
  7. EACCES on legacy dir → graceful return with error in summary, no crash.
  8. ENOENT on legacy dir → returns empty summary silently (FR-010).

**Reference**: Spec 1635 `uiL2Memdir.ts:atomicWriteJson` (rename pattern, adapted for copyFile).

**Depends on**: T002.

---

### T006 — Register `/migrate-sessions` slash command [P with T005]

**Files**:
- `tui/src/commands/migrate-sessions.ts` (NEW, ~60 LOC).
- `tui/src/commands/index.ts` (registration entry, +3 lines).
- `tui/src/components/MigrateSessionsResult.tsx` (NEW, ~50 LOC; renders `MigrationSummary`).

**Action**:
- Slash command parses `--prune` flag.
- Invokes `migrateSessions({prune})`.
- Renders summary via the new Ink component: `<Box><Text>{copied} copied · {skipped} already-present · {pruned} pruned · {formatBytes(bytes)} total</Text>{errors.length > 0 && <Text color="red">{errors.length} error(s) — see logs</Text>}</Box>`.
- Shift+Tab for confirmation prompt before `--prune` runs (defense-in-depth; `--prune` is destructive even if guarded by fsync ordering).

**Acceptance**:
- `bun test tui/src/commands/__tests__/migrate-sessions.test.ts` — 4 tests (no-arg, --prune-with-confirm, --prune-cancel, error-render).
- Manual smoke: run `/migrate-sessions` in tmux scenario, see summary frame.

**Reference**: Existing slash command pattern in `tui/src/commands/history.ts:1-30`.

**Depends on**: T005 for the helper. Parallel-safe with T005 (different files).

---

## Phase 4 — Stub resolution (sonnet-backend)

### T007 — Repoint Python `_DEFAULT_SESSION_DIR` + add `--gc-empty-stubs` CLI flag

**Files**:
- `src/kosmos/session/store.py` (lines 32, 42 — change default + comment).
- `src/kosmos/cli/app.py` (add CLI flag handler).
- `tests/session/test_store_path.py` (NEW, ~80 LOC).

**Action**:
- Change `_DEFAULT_SESSION_DIR = Path.home() / ".kosmos" / "sessions"` → `_DEFAULT_SESSION_DIR = Path.home() / ".kosmos" / "memdir" / "user" / "sessions"`.
- Update docstring at line 4 to cite Spec 027 invariant + this Epic.
- `KOSMOS_SESSION_DIR` env override stays for back-compat (some tests rely on it; verify in R-2 grep).
- Add `kosmos --gc-empty-stubs` CLI flag: enumerates `~/.kosmos/sessions/` (the NOW-legacy path), reads each `<uuid>.jsonl`, parses first line, asserts `entry_type == 'metadata'` AND `data.message_count == 0` AND total file lines == 1, then `unlink` only those that pass all three checks. Logs `N stubs collected, M bytes freed`. Refuses to delete any file that does not pass content inspection.

**Acceptance**:
- `uv run pytest tests/session/test_store_path.py -v` — 6 tests pass (default path, env override, write succeeds at new path, gc identifies stubs by content, gc refuses non-stubs, gc handles missing legacy dir).
- Smoke: `kosmos --gc-empty-stubs` reports the expected stub count from the audited dev machine (≈3,572 if no stubs have been added since).

**Reference**: spec.md US5 + plan.md R-3.

---

## Phase 5 — Dual-path test coverage (sonnet-tests)

### T008 — Dual-path enumeration test for `/resume` [P with T009]

**Files**:
- `tui/src/__tests__/sessionStorage.dual-path.test.ts` (NEW, ~120 LOC).
- `tui/src/test-utils/dualPathFixtures.ts` (NEW, ~40 LOC; helper to seed both legacy + KOSMOS paths from a temp dir).

**Action**:
- Use `KOSMOS_MEMDIR_USER` + `CLAUDE_CONFIG_DIR` env redirects to point at temp dirs.
- Pre-seed: 1 JSONL at legacy CC path, 1 at KOSMOS path, 1 with colliding `session_id` at both.
- Invoke `listSessionsImpl()` (or whichever surface `/resume` ultimately calls — verify in R-2).
- Assert: 2 unique entries (collision deduplicated), KOSMOS-tier copy preferred on tie, sorted by `last_active_at` desc.

**Acceptance**: 5 tests pass (legacy-only, KOSMOS-only, both, collision, ENOENT-on-legacy).

**Depends on**: T003, T004.

**Parallel-safe**: YES with T009.

---

### T009 — `/fork` writes new JSONL to KOSMOS path regardless of parent path [P with T008]

**Files**:
- `tui/src/__tests__/forkSession.dual-path.test.ts` (NEW, ~80 LOC).

**Action**:
- Pre-seed parent JSONL at legacy CC path with 50 entries.
- Invoke fork command at message 25.
- Assert: new file appears under KOSMOS path, contains 25 entries, header includes `parent_session_id == <legacy parent uuid>`.
- Assert: subsequent appends to the fork go to the KOSMOS path (mock 3 follow-up appends, re-inspect file).

**Acceptance**: 3 tests pass (fork-from-legacy, fork-from-kosmos, follow-up-appends-stay-kosmos).

**Depends on**: T003, T004.

---

## Phase 6 — Integration smoke (Lead solo)

### T010 — Layer 5 tmux + Layer 4 vhs + Layer 5c frame-sequence end-to-end

**Files**:
- `specs/spec-027-session-storage-migration/scripts/smoke-resume-fork-tmux.sh` (NEW; uses `scripts/tui-tmux-capture.sh`).
- `specs/spec-027-session-storage-migration/scripts/smoke-resume-fork.tape` (NEW; vhs scenario emitting `.gif` + `.txt` + `.ascii` per AGENTS.md insight #1).
- `specs/spec-027-session-storage-migration/frames/snap-NNN-*.txt` (output, generated by Layer 5).
- `specs/spec-027-session-storage-migration/smoke-keyframe-{boot,after-prompt,migrate-summary,resume-picker}.png` (output, vhs `Screenshot` directive).
- `tui/src/__tests__/migrateSessionsFrames.test.ts` (NEW, ~50 LOC; uses `tui/src/test-utils/frameStreamSnapshot.ts:assertFrameSequence`).

**Action**:
- tmux scenario:
  1. Pre-seed 2 fake legacy sessions under `~/.claude/projects/-Users-um-yunsang-KOSMOS-tui/`.
  2. `bun run tui` in tmux pane.
  3. `wait_for_pane "tool_registry: \d+ entries verified" 30`
  4. Type `/resume\r`. `wait_for_pane "Resume session" 5`. Snapshot.
  5. Press Esc to dismiss. Type `안녕\r`. `wait_for_pane "안녕" 5`. Snapshot.
  6. Send Ctrl-C twice. Snapshot final state.
  7. Re-launch. Type `/migrate-sessions\r`. `wait_for_pane "copied" 10`. Snapshot.
  8. Inspect `~/.kosmos/memdir/user/sessions/` — assert exactly 3 files (1 from the new chat + 2 migrated).
- vhs `.tape`:
  - `Output specs/spec-027-session-storage-migration/smoke-resume-fork.gif`
  - `Output specs/spec-027-session-storage-migration/smoke-resume-fork.txt` (mandatory per AGENTS.md insight #1)
  - `Output specs/spec-027-session-storage-migration/smoke-resume-fork.ascii` (mandatory)
  - 4× `Screenshot` directives at the canonical stages.
- Layer 5c Ink frame-sequence test asserts the `/migrate-sessions` summary frame matches an expected hash sequence.

**Acceptance**:
- `frames/` directory exists with ≥10 numbered text snapshots.
- All 4 PNG keyframes present and visually coherent (Lead reads each via Read tool — multimodal verification per AGENTS.md anti-pattern #1 countermeasure).
- `bun test tui/src/__tests__/migrateSessionsFrames.test.ts` — 1 test passes (frame sequence assertion).
- `bun typecheck` clean (KOSMOS narrows to `src/stubs/**` only — verify no new TS errors leak in).
- `bun test` total: green delta vs main (no new failures; 1 pre-existing PdfInlineViewer Kitty intermittent acceptable per recent change history).
- `uv run pytest` total: green delta vs main.

**Depends on**: T001-T009.

**Parallel-safe**: NO — Lead runs solo per AGENTS.md ("push/PR/CI = Lead").

---

## Task summary

| Phase | Tasks | Teammate | Files touched |
|-------|-------|----------|---------------|
| 1 Foundational | T001, T002 | sonnet-foundational | 2 (1 backend, 1 TUI new) |
| 2 TUI write | T003, T004 | sonnet-tui-write | 2 |
| 3 Migration | T005, T006 | sonnet-migration | 5 (2 new + 1 edit + 2 new tests) |
| 4 Backend | T007 | sonnet-backend | 3 |
| 5 Tests | T008, T009 | sonnet-tests | 3 (2 tests + 1 fixture) |
| 6 Smoke | T010 | Lead solo | 5 (4 artefacts + 1 test) |
| **Total** | **10 tasks** | **5 teammates + Lead** | **20 files** |

All teammate task-groups within ≤5 tasks AND ≤10 files (AGENTS.md NON-NEGOTIABLE dispatch unit rule).

---

## Out-of-band reminders

- Per AGENTS.md Agent Teams: Sonnet teammates do NOT push/PR/CI. They WIP-commit + mark `[X]` in this file. Lead picks up after every teammate completes.
- Per AGENTS.md TUI verification mandate: T010 is REQUIRED before push. No bypass available.
- Per AGENTS.md PR closing rule: PR body uses `Closes #<EPIC>` only. Sub-issue closes are manual after merge.
- Per AGENTS.md Copilot Review Gate: monitor gate transitions; if stuck `in_progress` 2+ min, re-request via GraphQL; if that fails, inform user re: bypass label.
- Per `/speckit-implement` skill: this tasks.md is the dispatch source-of-truth. Lead reads `[P]` markers + groups them per the dispatch tree in `plan.md`.
