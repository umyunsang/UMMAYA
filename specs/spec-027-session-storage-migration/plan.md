# Implementation Plan — Spec 027 Session Storage Path Migration

**Spec**: `specs/spec-027-session-storage-migration/spec.md`
**Phase**: P4 UI L2 (also touches P3 Tool-system durability surface).
**Initiative**: #2290 Epic 3.
**Created**: 2026-05-04.

---

## Constitution check (gate before any implementation)

| Principle | Compliance | Note |
|-----------|------------|------|
| I — CC + 2 swaps thesis | PASS | We are routing CC's session-storage helper to a KOSMOS-owned root; not changing the JSONL schema, not changing function signatures (FR-013). |
| II — Permissions never lateral | N/A | Storage path Epic only. |
| III — Live tools cite agency policy | N/A | Internal storage. |
| IV — No KOSMOS-invented permission classifications | N/A | |
| V — Source text English | PASS | FR-015 + AGENTS.md hard rule. |
| AGENTS.md zero-new-deps | PASS | FR + SC-004 enforced. |

**Verdict**: GATE PASS. No ADR required (we are *implementing* the documented memdir USER-tier invariant, not changing it).

---

## Phase 0 — Research

### R-1 — Confirm CC native `getProjectDir()` shape (read-only reference)

**Question**: What is the exact CC layout we are leaving behind?

**Method**: Read `.references/claude-code-sourcemap/restored-src/utils/sessionStorage.ts` (or its current location) for `getProjectsDir()` + `getProjectDir(projectDir)` definitions. Compare to KOSMOS port at `tui/src/utils/sessionStorage.ts:203-205, 441-443`.

**Acceptance**: We have a confirmed reference for `<projects-root>/<sanitized-cwd>/<session_id>.jsonl`. The KOSMOS port at `sessionStorage.ts:441-443` (`getProjectDir`) and `sessionStoragePortable.ts:329-331` (same name) call `sanitizePath(projectDir)`. We will leave the per-cwd sanitization helper alone — it is only used for legacy-discovery in US2.

**Output**: `research.md § R-1`.

### R-2 — Map every read/write call-site of `getTranscriptPath` family

**Question**: Which files invoke `getTranscriptPath()`, `getTranscriptPathForSession()`, `getProjectsDir()`, `getProjectDir()`, `getSessionProjectDir()`, `getAgentTranscriptPath()`?

**Method**: `grep -rn "getTranscriptPath\|getProjectsDir\|getProjectDir\|getSessionProjectDir\|getAgentTranscriptPath" tui/src/ src/kosmos/`.

**Acceptance**: Categorize each call-site as **WRITE** (need to repoint) vs **READ** (legacy-discovery helper, leave alone for US2 dual-path). Document the count + file map.

**Output**: `research.md § R-2 — Call-site map`.

### R-3 — Decide US5 `~/.kosmos/sessions/` resolution

**Question**: For the 3,572 stub JSONLs at `~/.kosmos/sessions/`, which of {delete-only | symlink-to-canonical | repoint-Python-backend} is chosen?

**Method**: Inspect 5 random stub files for any non-metadata content (rule out partial-content). Inspect `src/kosmos/session/store.py` for write call-sites. Inspect IPC envelope (`src/kosmos/ipc/stdio.py:600,727`) for any callsite that depends on the legacy path.

**Acceptance**: One concrete decision documented with rationale. Default recommendation per spec.md Q3: **repoint Python `_DEFAULT_SESSION_DIR` to `~/.kosmos/memdir/user/sessions/`** + add a one-shot `kosmos --gc-empty-stubs` pass that audits each stub by reading its first JSON line and confirming `message_count == 0` *content-wise* before deletion (never by filename heuristic).

**Output**: `research.md § R-3 — Stub resolution decision`.

### R-4 — JSONL schema parity check

**Question**: Are the JSONL schemas written by the TUI (CC native shape — `uuid`, `entry_type`, `data`) and the Python backend (`SessionEntry` Pydantic model with `timestamp`, `entry_type`, `data`, `parent_id`) byte-compatible enough for the same reader to consume both?

**Method**: Read 1 sample line from `~/.claude/projects/-Users-um-yunsang-KOSMOS-tui/<largest>.jsonl` (TUI-written) vs `~/.kosmos/sessions/<any>.jsonl` (Python-written). Diff field names. Then read `tui/src/commands/history.ts:loadSessionEntries` (the canonical reader) — what fields does it require?

**Acceptance**: Either (a) the schemas are already compatible (both have `session_id` accessible from the first line), or (b) document the exact transform needed in the migration helper. Decision goes into `data-model.md`.

**Output**: `research.md § R-4 — Schema parity` + `data-model.md § Session JSONL envelope`.

### R-5 — Atomic-write + concurrency model

**Question**: Multiple concurrent writes to the same JSONL (worker + coordinator + REPL append) — what's the existing locking model? Is `appendEntryToFile` already crash-safe?

**Method**: Read `tui/src/utils/sessionStorage.ts:appendEntryToFile` definition. Compare to Spec 1635 `uiL2Memdir.ts:atomicWriteJson` (rename pattern).

**Acceptance**: Confirm we don't introduce a regression by changing only the path root. If the existing append-mode write is crash-safe (open-append-fsync), no atomicity change needed. If not, we add the same `tmp.<pid>.<ts>` rename pattern only for the *header* write; appends remain append-mode.

**Output**: `research.md § R-5 — Atomicity`.

---

## Phase 1 — Design artifacts

### data-model.md

```yaml
# Session JSONL envelope (read-only contract, NO schema change)
SessionHeader:           # First JSONL line
  session_id: string     # uuid
  started_at: string     # ISO 8601 UTC
  last_active_at: string
  preview: string?
  parent_session_id: string?  # FR-007 fork support

SessionEntry:            # Subsequent lines (CC-native shape, byte-identical)
  uuid: string
  entry_type: string     # 'user' | 'assistant' | 'tool_use' | 'tool_result' | ...
  data: object
  timestamp: string?     # CC populates; reader tolerates absence
  parent_id: string?

# Path resolution contract (NEW)
SessionPathRoot:
  KOSMOS_CANONICAL: ~/.kosmos/memdir/user/sessions  # FR-002
  CC_LEGACY:        ~/.claude/projects               # FR-005 read-only
  ENV_OVERRIDE:     $KOSMOS_MEMDIR_USER + /sessions  # FR-002

# Migration record (FR-008 OTEL span attribute set)
MigrationOp:
  source_path: string
  dest_path: string
  bytes: int
  action: 'copy' | 'prune' | 'skip-collision'
  fsync_succeeded: bool
```

### contracts/

- `contracts/session-path-resolver.md` — Markdown contract for `getKosmosSessionsDir()`, env override semantics, fail-closed behavior (FR-011).
- `contracts/dual-path-discovery.md` — Markdown contract for `/resume` enumeration: input = nothing, output = sorted deduplicated list of `{session_id, path_root, last_active_at, preview}`.
- `contracts/migrate-sessions-cli.md` — Markdown contract for `/migrate-sessions [--prune]`: exit codes, summary format, idempotency guarantee.

### quickstart.md

Step-by-step recipe for a contributor or test driver:

1. `export KOSMOS_MEMDIR_USER=/tmp/test-memdir-$RANDOM`
2. `bun run tui` → type a prompt → Ctrl-C
3. Verify `ls /tmp/test-memdir-$RANDOM/sessions/*.jsonl` shows exactly one new file.
4. Re-run `bun run tui` → `/resume` → verify the prior session appears.
5. Run `/migrate-sessions` → assert "0 copied, 0 already-present" (no legacy data in test env).
6. Pre-seed a fake legacy session at `~/.claude/projects/<sanitized-cwd>/<uuid>.jsonl`.
7. `/resume` → assert both real KOSMOS session + fake legacy session appear.
8. `/migrate-sessions` → assert "1 copied". Re-run → assert "0 copied, 1 already-present".
9. `/migrate-sessions --prune` → assert legacy file is gone.
10. `unset KOSMOS_MEMDIR_USER`.

### dispatch-tree.md

```
Phase 1 Setup (T001-T002): sonnet-foundational  (KOSMOS path helper + env override)
Phase 2 TUI write repoint (T003-T004): sonnet-tui-write  (sessionStorage.ts + sessionStoragePortable.ts)
Phase 3 Migration helper (T005-T006): sonnet-migration  (copy + prune + idempotency)
Phase 4 Stub resolution (T007): sonnet-backend  (Python _DEFAULT_SESSION_DIR repoint + gc)
Phase 5 Dual-path tests (T008-T009): sonnet-tests  (/resume + /fork pre-seeded fixtures)
Phase 6 Integration smoke (T010): Lead solo  (Layer 5 tmux + Layer 4 vhs + Layer 5c frame seq)
```

Phases 1 → 2 → 5 are sequential (T002 unblocks T003-T004 unblocks T008-T009). Phases 3, 4 run in parallel with Phase 2 (independent file sets).

---

## Phase 2 — Tasks (preview, fully fleshed in tasks.md)

10 tasks. Key design notes:

- **T001** — Add `KOSMOS_MEMDIR_USER` to `pydantic-settings` env catalog if it isn't already (Spec 027 may already have it; verify in R-2). Backend Python side.
- **T002** — Add `getKosmosSessionsDir()` helper to a new file `tui/src/utils/kosmosPaths.ts` (matching the Spec 1635 `uiL2Memdir.ts:25-26` pattern). TS side.
- **T003-T004** — Repoint `getProjectsDir()` *body* in `sessionStorage.ts` and `sessionStoragePortable.ts` to call `getKosmosSessionsDir()`. The function name + signature stay identical (FR-013). The CC-shape-mimicking helper `getProjectDir(projectDir)` stays as a *legacy-discovery* helper used only by FR-005 dual-path enumeration.
- **T005-T006** — Add migration helper module + `/migrate-sessions` slash command registration.
- **T007** — Resolve `~/.kosmos/sessions/` per R-3 decision. Most likely: change `src/kosmos/session/store.py:32` to `_DEFAULT_SESSION_DIR = Path.home() / ".kosmos" / "memdir" / "user" / "sessions"`. Add `--gc-empty-stubs` CLI flag.
- **T008-T009** — Pre-seeded dual-path tests under `tui/src/__tests__/sessionStorage.dual-path.test.ts` and `tui/src/__tests__/migrateSessions.test.ts`.
- **T010** — Layer 5 tmux scenario `specs/spec-027-session-storage-migration/scripts/smoke-resume-fork.sh` + Layer 4 vhs `.tape` + Layer 5c frame-sequence helper invocation.

Task-level WRITE budget per teammate: ≤5 tasks AND ≤10 file changes (AGENTS.md NON-NEGOTIABLE).

---

## Phase 3 — Verification matrix (all layers per AGENTS.md TUI verification mandate)

| Layer | Artefact | Required for this Epic |
|-------|----------|------------------------|
| 1a — pytest | `tests/test_session_store_path.py` | YES (covers Python `_DEFAULT_SESSION_DIR` repoint, `KOSMOS_SESSION_DIR` env override, `--gc-empty-stubs`). |
| 1b — bun test + ink-testing-library | `sessionStorage.dual-path.test.ts`, `migrateSessions.test.ts` | YES (covers helper + dual-path enumeration). |
| 2 — stdio JSONL probe | `specs/spec-027-session-storage-migration/scripts/probe-write-path.sh` | YES (asserts a tool-call session writes to KOSMOS path, not CC path). |
| 3 — interactive PTY text-log | `scripts/smoke-resume-fork.expect` + `*.txt` capture | YES. |
| 4 — vhs visual + 3+ PNG keyframes | `scripts/smoke-resume-fork.tape` + `smoke-keyframe-{boot,after-prompt,resume-picker}.png` | YES (FR-005 picker rendering). |
| 5 — tmux capture-pane | `scripts/smoke-resume-fork-tmux.sh` + `snap-NNN-*.txt` | YES (preferred over PTY for keystroke timing per AGENTS.md insight #2). |
| 5c — Ink frame sequence | `tui/src/__tests__/migrateSessionsFrames.test.ts` using `assertFrameSequence` | YES (renders `/migrate-sessions` summary; cf. final-state-fallacy anti-pattern). |

**Bypass declaration**: This Epic touches `tui/src/**` extensively (sessionStorage.ts, sessionStoragePortable.ts, new kosmosPaths.ts, new migrateSessions command). NO bypass available — all verification layers required.

---

## Phase 4 — Reference materials (mandatory consult per AGENTS.md spec-driven workflow rule)

- `docs/vision.md § Layer 1 → A5 Session storage` — invariant we are restoring.
- `docs/requirements/kosmos-migration-tree.md § L1-A A5` — same invariant from the requirements tree.
- `.references/claude-code-sourcemap/restored-src/` — read-only reference for `getProjectDir`/`getProjectsDir` shape (we mirror it minus the path root).
- `.specify/memory/constitution.md` — reviewed (no specific session-storage clause; general "CC + 2 swaps" thesis applies).
- Spec 027 `specs/027-agent-swarm-core/spec.md` — memdir USER tier owner.
- Spec 1635 P4 `tui/src/utils/uiL2Memdir.ts` — env-override pattern + atomic-write precedent (reused).
- Spec 035 `~/.kosmos/memdir/user/consent/` — sibling dir under same root.
- Spec 1633 — confirmed claude.ai sessionIngress is dead, no remote sync break risk.

---

## Phase 5 — Open architectural questions (escalate if unresolved before /speckit-tasks)

- **Q1 (resolved by spec.md Q1)**: Auto-migration on launch? **No** — opt-in only.
- **Q2 (resolved by spec.md Q2)**: Per-cwd subdirs at the KOSMOS path? **No** — flat layout per FR-014.
- **Q3 (resolved by R-3 decision in research.md)**: `~/.kosmos/sessions/` action? **Repoint + gc**.
- **Q4 (NEW, escalate if blocking)**: Should `getKosmosSessionsDir()` live in a new `tui/src/utils/kosmosPaths.ts` (preferred — single helper file for all canonical KOSMOS paths) OR be inlined into `envUtils.ts` next to `getClaudeConfigHomeDir()` (simpler diff)? **Recommendation**: new file. `kosmosPaths.ts` becomes the home for any future `getKosmosConsentDir()` / `getKosmosPluginsDir()` factoring (DRY across Spec 035 / Spec 1636 helpers).

---

## Phase 6 — PR closure plan

- PR title: `feat(spec-027-session-storage-migration): route citizen sessions to ~/.kosmos/memdir/user/sessions/ (closes Epic 3)`
- PR body cites: Spec 027 + `kosmos-migration-tree.md § L1-A A5` + this plan.
- `Closes #<EPIC_NUM>` only — Task sub-issues closed manually after merge per AGENTS.md PR close rule.
- Layer 1a/1b/3/4/5/5c artefacts attached under `specs/spec-027-session-storage-migration/` (the directory is the durable record).
- Codex P1 reply gate: any `chatgpt-codex-connector[bot]` P1 comment must be addressed in a follow-up commit before merge.
- Copilot Gate: monitor; bypass label only with user instruction.
