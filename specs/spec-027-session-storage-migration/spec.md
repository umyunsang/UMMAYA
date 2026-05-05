# Feature Specification: Session Storage Path Migration — Spec 027 Invariant Recovery

**Feature Branch**: `feat/spec-027-session-storage-migration`
**Created**: 2026-05-04
**Status**: Draft
**Input**: Lead-S10 Initiative #2290 Epic 3. KOSMOS-canonical session JSONL path (Spec 027 + `kosmos-migration-tree.md § L1-A A5`) is `~/.kosmos/memdir/user/sessions/`. Actual TUI runtime writes to `~/.claude/projects/-Users-um-yunsang-KOSMOS-tui/<uuid>.jsonl` (CC native `getClaudeConfigHomeDir() + '/projects'`). Backend Python writes 3,572 metadata-only stub JSONLs (330 B each, `message_count=0`) to `~/.kosmos/sessions/`. Result: citizen session content leaks into the CC config dir while two KOSMOS-tier paths remain wired but empty.

**Phase reference**: P4 UI L2 / cross-cuts P3 Tool-system wiring (session JSONL is the durability surface for both /resume and /fork).

**Canonical sources cited**:
- `docs/vision.md § Layer 1 (LLM harness) → A5 Session storage`
- `docs/requirements/kosmos-migration-tree.md § L1-A A5` — *"`~/.kosmos/memdir/user/sessions/` JSONL · --continue/--resume/--fork/new"*
- Spec 027 (`specs/027-agent-swarm-core/`) — memdir USER tier ownership.
- Spec 1635 P4 (`tui/src/utils/uiL2Memdir.ts`) — atomic-rename memdir helper precedent (`KOSMOS_MEMDIR_USER` env override pattern).
- `.references/claude-code-sourcemap/restored-src/` — CC `getProjectDir()` shape (we are *not* rewriting that — we are routing it to a KOSMOS root).

---

## Evidence chain (Lead-S10 audit, 2026-05-04)

| # | Surface | File / path | Symptom |
|---|---------|-------------|---------|
| E1 | TUI write | `tui/src/utils/sessionStorage.ts:204` | `getProjectsDir()` → `join(getClaudeConfigHomeDir(), 'projects')` |
| E2 | TUI write | `tui/src/utils/sessionStoragePortable.ts:325-327` | Same — `getProjectsDir()` returns `~/.claude/projects` |
| E3 | TUI read (correct, but disconnected) | `tui/src/commands/history.ts:25` | `SESSIONS_DIR = ~/.kosmos/memdir/user/sessions` — reads from canonical path that nobody writes to |
| E4 | TUI read (correct, but disconnected) | `tui/src/assistant/AssistantSessionChooser.tsx:7` | Comment claims sessions live in canonical KOSMOS path |
| E5 | Backend write | `src/kosmos/session/store.py:32` | `_DEFAULT_SESSION_DIR = ~/.kosmos/sessions` (also non-canonical, third location) |
| E6 | Disk reality (CC config dir) | `~/.claude/projects/-Users-um-yunsang-KOSMOS-tui/` | 35,463 JSONL files, real content (largest 384 KB; 374 specific to KOSMOS-tui workspace) |
| E7 | Disk reality (KOSMOS legacy) | `~/.kosmos/sessions/` | 3,572 stub JSONL files, all 330 B, `message_count=0` (Python backend boots, writes metadata, never appends content) |
| E8 | Disk reality (canonical, wired but empty) | `~/.kosmos/memdir/user/sessions/` | 0 files |

Three-way split: TUI writes → CC dir; backend writes stubs → `~/.kosmos/sessions/`; the only reader/UI surface that matches the spec → `~/.kosmos/memdir/user/sessions/` (empty). `/history`, `/resume`, `/fork` cannot find any real session content via the canonical path.

---

## Threat model — why this is a citizen-data leak (NON-NEGOTIABLE)

**Citizen session JSONL content includes:**
- All chat messages (citizen prompts + LLM replies, including PII like names, addresses, RRN fragments, hospital queries, ministry case numbers).
- Tool call inputs/outputs (e.g., resolved geocoding, NMC emergency-department lookups, KMA forecasts).
- Permission receipts and consent ledger correlation IDs.
- Reasoning content (when `KOSMOS_K_EXAONE_THINKING=true`).

**Storing that under `~/.claude/` violates:**
1. **Spec 027 memdir USER-tier scope** — the entire purpose of `~/.kosmos/memdir/user/` is a single, audited, KOSMOS-owned root for citizen state, sealed from external tooling.
2. **PIPA §26 trustee scope** — KOSMOS is the data trustee for citizen session content; co-locating with another vendor's config dir muddies the trustee boundary.
3. **CC compatibility risk** — if the user installs/uninstalls Claude Code, runs `claude --resume`, or its session migrator scans `~/.claude/projects/`, KOSMOS sessions can be enumerated, mis-rendered, exported, or deleted by an external tool that has no contract with KOSMOS.
4. **Brand trust** — `~/.claude/projects/...` literally contains the brand of an unaffiliated company; citizens auditing their data path see "Claude" not "KOSMOS".
5. **Spec 1635 P4 precedent already exists** — `uiL2Memdir.ts` uses `KOSMOS_MEMDIR_USER` env override + `~/.kosmos/memdir/user/<scope>/` layout. Sessions are the only Spec 027–owned surface that ignores it.

This is a **silent ongoing leak** — every interactive session writes citizen JSONL to the wrong directory until this Epic ships.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Citizen Session Persisted Under KOSMOS-Owned Path (Priority: P1)

A citizen launches `bun run tui`, types a query ("부산 인근 응급실 알려줘"), receives the LLM response with tool calls, then exits with Ctrl-C. On the next launch they run `/history` and see this session listed; selecting it via `/resume` restores the full transcript including tool calls.

**Why this priority**: Without P1, every Spec 027 invariant claim in `kosmos-migration-tree.md § L1-A A5` is false on disk. P0/P1/P2/P3/P4/P5/P6 phase claims that "KOSMOS sessions live under memdir USER tier" become untrue, and downstream specs (Spec 035 consent ledger, Spec 1635 P4 history search, Spec 1635 export PDF) read from an empty directory — silent regression.

**Independent test**: Drive a smoke session via Layer 5 tmux capture-pane — type a prompt, wait for assistant chunk, exit. Assert (a) no new JSONL appears under `~/.claude/projects/`, (b) exactly one new `<session_id>.jsonl` appears under `~/.kosmos/memdir/user/sessions/`, (c) the file's first line is the session metadata header readable by `tui/src/commands/history.ts:loadSessionEntries`, (d) subsequent JSONL lines decode as the same shape that CC's transcript reader parses (same `uuid` / `entry_type` / `data` schema — only the *root* path changes).

**Acceptance Scenarios**:

1. **Given** a fresh KOSMOS install with no `~/.kosmos/memdir/user/sessions/` directory, **When** the citizen sends one chat turn, **Then** `~/.kosmos/memdir/user/sessions/<session_id>.jsonl` is created (atomic write via parent `mkdir -p`) and contains at minimum: session header + user message entry + assistant chunk entry.
2. **Given** a session JSONL written under the canonical KOSMOS path, **When** `/history` lists sessions, **Then** the entry appears with the correct `session_id`, `started_at`, and `preview` (the existing `tui/src/commands/history.ts` reader already handles this — no change needed there).
3. **Given** a writable `~/.kosmos/memdir/user/sessions/` and a non-writable `~/.claude/projects/` (e.g., chmod 000 by an external tool), **When** the citizen launches a session, **Then** the session writes succeed (the KOSMOS path is independent of CC config dir permissions).
4. **Given** `KOSMOS_MEMDIR_USER=/tmp/test-memdir` env override, **When** the session writer resolves the path, **Then** it writes to `/tmp/test-memdir/sessions/<session_id>.jsonl` (test isolation precedent matches Spec 1635 `uiL2Memdir.ts` and Spec 027 mailbox `KOSMOS_AGENT_MAILBOX_ROOT`).

---

### User Story 2 — `/resume` Surfaces Sessions From Both KOSMOS Path and Legacy CC Path (Priority: P1)

A citizen who has used KOSMOS for weeks (sessions historically written to `~/.claude/projects/-Users-um-yunsang-KOSMOS-tui/`) upgrades to the post-migration build. On the first launch they run `/resume`. They see *both* their pre-migration sessions and any new post-migration sessions in the picker, ordered by `last_active_at`. Selecting any entry restores the transcript regardless of which path it lives at.

**Why this priority**: A drop-in cutover that hides historical sessions = data loss from the citizen's perspective. Dual-path discovery is the only safe rollout because Epic-3 ships before any explicit migration step (T005-T006 below). P1 because /resume is the canonical re-entry contract per `kosmos-migration-tree.md § L1-A A5`.

**Independent test**: Pre-seed two JSONLs with distinct `session_id`s — one under `~/.claude/projects/-Users-um-yunsang-KOSMOS-tui/` (legacy), one under `~/.kosmos/memdir/user/sessions/` (canonical). Launch /resume. Assert both appear in the picker, both restore correctly when selected, and the restored chat shows the original message content.

**Acceptance Scenarios**:

1. **Given** legacy sessions under `~/.claude/projects/<sanitized-cwd>/` AND new sessions under `~/.kosmos/memdir/user/sessions/`, **When** `/resume` enumerates available sessions, **Then** both sets appear merged (deduplicated by `session_id` if any collision exists, with the KOSMOS-tier copy preferred on tie).
2. **Given** a citizen selects a *legacy*-path session in /resume, **When** the session is restored, **Then** subsequent appends from that session are written to the canonical KOSMOS path (an in-place append-mode upgrade — see FR-008 below — *not* a silent in-flight migration that breaks the legacy file mid-write).
3. **Given** a citizen selects a *KOSMOS-tier* session in /resume, **When** the session is restored, **Then** appends continue at the same KOSMOS path (no path transition).
4. **Given** the legacy CC path does not exist (fresh install or post-prune machine), **When** `/resume` runs, **Then** it gracefully returns the KOSMOS-only set with no warning spam (only the `getProjectsDir()` ENOENT case is silently skipped).

---

### User Story 3 — `/fork` Branches a Legacy Session Into the KOSMOS Path (Priority: P2)

A citizen forks a long-running historical session (legacy CC path) at message N. The new fork is written under `~/.kosmos/memdir/user/sessions/<new_session_id>.jsonl` with the parent reference pointing at the legacy `session_id`.

**Why this priority**: P2 because /fork is a less-common interaction than /resume, but it is the cleanest natural opportunity to start moving citizens off legacy paths without explicit migration. Forks always create a *new* session_id, so there is no in-place mutation risk — the new file just lands at the canonical path.

**Independent test**: Pre-seed one 50-message legacy session. Run /fork at message 25. Assert the fork appears as a new file under the KOSMOS path, contains messages 1–25 of the parent, and its metadata header records `parent_session_id` pointing at the legacy `session_id`.

**Acceptance Scenarios**:

1. **Given** a legacy session at `~/.claude/projects/.../<parent_id>.jsonl` containing 50 messages, **When** the citizen runs `/fork` at message 25, **Then** a new file `~/.kosmos/memdir/user/sessions/<fork_id>.jsonl` is created containing 25 messages.
2. **Given** the fork JSONL header, **When** `/history` lists it, **Then** `parent_session_id` is preserved and equal to `<parent_id>` (UI may display it as "branched from <parent>" — out of scope for this Epic).
3. **Given** any subsequent appends to the fork, **When** writes flush, **Then** they go to the KOSMOS path file, not the legacy parent file.

---

### User Story 4 — Explicit `/migrate-sessions` Command for One-Shot Bulk Migration (Priority: P2)

A power user prefers a clean directory layout and runs `/migrate-sessions` to copy all legacy CC-path sessions into the KOSMOS path in one operation. The command is **idempotent** (re-running is safe), **non-destructive by default** (legacy files are *copied*, not moved, unless the citizen passes `--prune`), and prints a summary (N copied, M skipped due to `session_id` collision, K bytes total).

**Why this priority**: P2 because dual-path discovery (US2) makes this convenience-only, not blocking. Power users who care about a single source of truth get an explicit knob; everyone else gets the seamless dual-path read with new writes naturally accumulating in the canonical path over time.

**Independent test**: Pre-seed 10 legacy JSONLs. Run `/migrate-sessions`. Assert 10 new files exist at the KOSMOS path, the 10 legacy files still exist (default behavior). Re-run; assert nothing changes (already-migrated files detected by `session_id` match). Run `/migrate-sessions --prune`; assert legacy files are deleted, KOSMOS files retained.

**Acceptance Scenarios**:

1. **Given** N legacy session JSONLs under the CC path, **When** `/migrate-sessions` runs, **Then** N files are byte-copied into `~/.kosmos/memdir/user/sessions/` preserving their `session_id` and content; the command exits with a one-line summary.
2. **Given** a re-run of `/migrate-sessions`, **When** every legacy `session_id` already exists at the KOSMOS path, **Then** zero copies happen and the summary reads `0 copied, N already-present`.
3. **Given** `/migrate-sessions --prune`, **When** the operation succeeds, **Then** legacy files are unlinked **only after** the KOSMOS-tier copy is fsync'd to disk (no half-prune state on crash).
4. **Given** a path-resolution error (e.g., disk full at the KOSMOS path), **When** the command runs, **Then** it aborts before any `--prune` deletion, prints the offending path + errno, exits non-zero.

---

### User Story 5 — Stub-Only `~/.kosmos/sessions/` Files Are Resolved (Priority: P3)

The 3,572 metadata-only JSONLs at `~/.kosmos/sessions/` (Python backend write that never receives appends) are either deleted or wired into the canonical path — no third location remains.

**Why this priority**: P3 because these stubs are 330 bytes each (≈1.2 MB total), don't contain real citizen content, and don't break any visible UX. But leaving them creates a third "session-shaped" directory that confuses future audits and contradicts the Spec 027 single-source claim. Resolution is a one-time decision documented in `research.md`.

**Independent test**: After resolution, assert `~/.kosmos/sessions/` either does not exist OR is a symlink to `~/.kosmos/memdir/user/sessions/`. Assert the Python backend (`src/kosmos/session/store.py`) writes to the same canonical KOSMOS path going forward.

**Acceptance Scenarios**:

1. **Given** the resolution decision documented in `research.md` (delete | symlink | repoint), **When** the chosen action is applied, **Then** there is exactly one disk location for KOSMOS session JSONLs: `~/.kosmos/memdir/user/sessions/`.
2. **Given** the post-resolution state, **When** the Python backend (`kosmos.session.store`) creates a new session, **Then** it writes to `~/.kosmos/memdir/user/sessions/<session_id>.jsonl` (or honors `KOSMOS_SESSION_DIR` if explicitly overridden, matching the existing override semantics).
3. **Given** the existing 3,572 stub files, **When** the resolution chosen is "delete", **Then** the deletion is logged with file count + total bytes freed; if "symlink/repoint", no deletion happens and the directory becomes a symlink with metadata preserved.

---

## Functional Requirements

| ID | Requirement | Priority | Reference |
|----|-------------|----------|-----------|
| FR-001 | TUI session writers MUST write all session JSONLs to `~/.kosmos/memdir/user/sessions/<session_id>.jsonl` by default. | P0 | US1 |
| FR-002 | A new helper `getKosmosSessionsDir()` MUST be the single source of truth for the canonical session path; it MUST honor `KOSMOS_MEMDIR_USER` env override (matching Spec 1635 P4 `uiL2Memdir.ts:25-26` precedent). | P0 | US1 |
| FR-003 | `getTranscriptPathForSession(sessionId)` and `getTranscriptPath()` MUST return paths rooted at `getKosmosSessionsDir()` for all newly created sessions. | P0 | US1 |
| FR-004 | `getProjectsDir()` (CC native helper) MUST NOT be invoked from any KOSMOS write path; remaining call-sites are read-only legacy-discovery (FR-005). | P0 | US1 |
| FR-005 | `/resume` and the assistant session chooser MUST enumerate session candidates from BOTH `~/.kosmos/memdir/user/sessions/` AND the legacy CC project dir (read-only). Results MUST be merged, deduplicated by `session_id` (KOSMOS path wins on tie), and sorted by `last_active_at` desc. | P0 | US2 |
| FR-006 | When the citizen selects a legacy-path session via /resume, subsequent appends from that resumed session MUST be written to the KOSMOS path (in-place upgrade, never mutating the legacy file mid-flight). | P1 | US2 |
| FR-007 | `/fork` MUST always create the new fork JSONL at the KOSMOS path, regardless of the parent session's path. The fork header MUST preserve `parent_session_id`. | P1 | US3 |
| FR-008 | A new `/migrate-sessions` slash command MUST byte-copy legacy JSONLs from the CC project dir to the KOSMOS path. Default behavior is non-destructive (copy, not move). Idempotent on re-run. Optional `--prune` flag deletes legacy files only after fsync of the KOSMOS-tier copy. | P2 | US4 |
| FR-009 | The `~/.kosmos/sessions/` legacy stub directory MUST be resolved per the Phase-0 research decision (delete | symlink | repoint Python backend). The Python `_DEFAULT_SESSION_DIR` constant in `src/kosmos/session/store.py:32` MUST then point at the canonical KOSMOS path (or remain at `~/.kosmos/sessions/` only if it is a symlink to the canonical path). | P2 | US5 |
| FR-010 | All path-resolution helpers MUST treat ENOENT on the legacy CC path as "no legacy sessions present" (silent), NOT as an error. | P0 | US2 |
| FR-011 | All path-resolution helpers MUST fail-closed (raise/log) on EACCES, EPERM, or any non-ENOENT error encountered against the canonical KOSMOS path. | P0 | US1 |
| FR-012 | The migration helper (FR-008) and the path resolver (FR-002) MUST emit OTEL spans matching Spec 021 schema with attributes `kosmos.session.path_root` (`memdir-user` \| `cc-legacy`) and `kosmos.session.migration_action` (`copy` \| `prune` \| `skip-collision`). | P1 | US4 |
| FR-013 | Backward compatibility: any `tui/src/utils/sessionStorage.ts` and `tui/src/utils/sessionStoragePortable.ts` external surface (function name + signature) MUST be preserved. The change is internal to `getProjectsDir()` / `getTranscriptPathForSession()` body, not the API. | P0 | All |
| FR-014 | The CC `getProjectDir(projectDir)` per-cwd subdirectory layout (`<sanitized-cwd>/<session_id>.jsonl`) MUST NOT be reproduced under the KOSMOS path. KOSMOS sessions live as flat files: `~/.kosmos/memdir/user/sessions/<session_id>.jsonl` (matching the existing reader at `tui/src/commands/history.ts:25-89` and the Python backend layout). | P0 | US1 |
| FR-015 | All Korean-domain test fixtures MUST remain Korean (per AGENTS.md hard rule). Source code text introduced by this Epic MUST be English. | P0 | All |

---

## Success Criteria

| ID | Metric | Target |
|----|--------|--------|
| SC-001 | New citizen session JSONLs landing at `~/.kosmos/memdir/user/sessions/` | 100% (tmux smoke-capture asserts zero new files under `~/.claude/projects/-Users-um-yunsang-KOSMOS-tui/`). |
| SC-002 | `/resume` enumerates legacy + KOSMOS sessions | Both sets visible in the picker; tested with 1 of each pre-seeded. |
| SC-003 | `/migrate-sessions` idempotency | Second invocation reports `0 copied, N already-present`. |
| SC-004 | Zero new runtime dependencies | `bun pm ls` and `uv pip tree` diff vs main: 0 additions. AGENTS.md hard rule. |
| SC-005 | OTEL span emission | `kosmos.session.path_root` attribute present on every transcript-write span (verified via Langfuse trace replay). |
| SC-006 | `~/.kosmos/sessions/` resolved | Either deleted, symlinked, or actively-written-to per research.md decision; no third location. |
| SC-007 | Layer 5 tmux + Layer 5c frame-sequence + Layer 4 vhs + Layer 1b ink-snapshot all green for /resume picker rendering | Per AGENTS.md TUI verification mandate. |
| SC-008 | All existing TUI snapshot tests pass without modification | Validates FR-013 backward-compat. |

---

## Out of Scope (explicit)

- Spec 027 mailbox infrastructure (`~/.kosmos/mailbox/`) — separate Epic.
- Renaming `~/.claude/projects/` per-cwd subdirectory format under the KOSMOS path (FR-014 keeps KOSMOS flat; CC layout is read-only legacy).
- Multi-machine session sync, encryption-at-rest, cloud backup — separate ADRs.
- A "show parent" badge in /history for /fork sessions (US3 only requires the metadata to be persisted, not rendered).
- Changing the JSONL schema itself (entry shape, `uuid` field, etc.) — this Epic only changes the *root path*, never the file contents.
- Backporting writes to claude.ai sync surface — claude.ai backend is dead per Spec 1633 (sessionIngress.ts deleted; `tui/src/utils/sessionStorage.ts:36`).

---

## Dependencies

| Dep | What | Status |
|-----|------|--------|
| Spec 027 | Memdir USER tier owner contract (`~/.kosmos/memdir/user/`) | Shipped (Initiative #1631). |
| Spec 1635 P4 | `uiL2Memdir.ts` env-override + atomic-write precedent reused for the new path helper | Shipped. |
| Spec 1633 | claude.ai sessionIngress deletion (no remote sync to break) | Shipped. |
| Spec 035 | Consent ledger at `~/.kosmos/memdir/user/consent/` (sibling dir; no cross-cutting writes here) | Shipped. |
| Spec 287 | Ink + Bun TUI runtime (where /resume + /fork + /migrate-sessions live) | Shipped. |

No new dependencies introduced (AGENTS.md hard rule).

---

## Constitution Compliance

- **Principle I — CC + 2 swaps thesis**: This Epic does NOT swap behavior — it routes CC's existing session-storage helper (byte-identical surface) to a KOSMOS-owned root. No behavior change beyond the `getProjectsDir()` body.
- **Principle II — Permissions never flow laterally**: N/A; this is a storage path Epic, not a permission Epic.
- **Principle III — Live tools cite agency policy**: N/A; this is internal storage.
- **Principle IV — No KOSMOS-invented permission classifications**: N/A.
- **Principle V — All source text English**: Enforced (FR-015).
- **AGENTS.md hard rules satisfied**: zero new deps, no print() outside CLI, pydantic v2 for any new schemas, no live data.go.kr in tests, no `--force` push, source English, no requirements.txt/setup.py/Pipfile, no >1 MB file commits, no Go/Rust.

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Citizens lose access to historical CC-path sessions on cutover | High | FR-005 dual-path discovery — historical sessions remain visible. |
| In-place mutation of legacy JSONL during /resume corrupts it for any external CC tool | Medium | FR-006 — appends from a resumed legacy session route to the KOSMOS path; legacy file is read-only after the fork point. |
| `/migrate-sessions --prune` deletes a file that wasn't actually copied | High | FR-008 — fsync-then-unlink ordering; `--prune` aborts on any copy error. |
| 3,572 stub JSONLs at `~/.kosmos/sessions/` cause confusion if left | Low | FR-009 + research.md decision documents the chosen action. |
| Python backend continues to write to `~/.kosmos/sessions/` after TUI cutover | Medium | FR-009 forces backend to follow the same path resolution. |
| `KOSMOS_MEMDIR_USER` set to an invalid path silently drops writes | High | FR-011 fail-closed on EACCES/EPERM; helper raises at boot if path is unwritable. |

---

## Open Questions

> Resolved during /speckit-clarify. Listed here for traceability.

- **Q1**: Should `/migrate-sessions` be auto-triggered on first launch post-upgrade, or strictly opt-in? **A**: Opt-in (US4 P2). Auto-migration breaks rollback; dual-path discovery (US2) provides the seamless UX without forcing a one-way move.
- **Q2**: Should the KOSMOS path mirror CC's per-cwd subdirectory layout (`<sanitized-cwd>/<session_id>.jsonl`) for forward-compat with multi-project use? **A**: No (FR-014). The existing canonical reader (`tui/src/commands/history.ts:25`) and Python backend (`src/kosmos/session/store.py`) both use a flat layout; introducing per-cwd subdirs at the KOSMOS path would require changing those readers too — out of scope.
- **Q3**: For US5, which of {delete | symlink | repoint Python} is chosen? **A**: Resolved in `research.md § Phase 0 R3`. The default recommendation is **repoint Python** (`_DEFAULT_SESSION_DIR` → canonical path) + a one-time `kosmos --gc-empty-stubs` cleanup pass that removes only the 330-byte metadata-only files (verified by content inspection, never by filename pattern alone).
