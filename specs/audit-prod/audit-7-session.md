# audit-prod § Audit 7 — Session lifecycle + Export PDF + History

**Date**: 2026-05-05
**Lead**: Lead Opus
**Scope**: Session storage (Epic 3), `/resume`, `/fork`, `/continue`, `/migrate-sessions`, `/history`, `/export`, JSONL schema integrity
**Verdict**: **NOT PRODUCTION-READY** — 3 P0 (export, history, migrate) + 1 P1 (resume)

## 0. Pre-audit reconnaissance

| Surface | Count / state | Path |
|---|---|---|
| KOSMOS sessions root (flat) | 152 files (151 are 330 B Python-stub metadata-only, 1 directory) | `~/.kosmos/memdir/user/sessions/` |
| KOSMOS sessions CC-shape (sanitized cwd) | ≥ 30 CC-native JSONL | `~/.kosmos/memdir/user/sessions/-Users-um-yunsang-KOSMOS-tui/` |
| CC-legacy projects | 24 dirs | `~/.claude/projects/` |
| TUI canonical write path | CC-shape `<sessions>/<sanitized-cwd>/<sessionId>.jsonl` (parentUuid/isSidechain/promptId/uuid/timestamp/sessionId/version/gitBranch/cwd) | `tui/src/utils/sessionStorage.ts:211 getProjectsDir()` |
| Backend write path | Flat `<sessions>/<sessionId>.jsonl`, schema `{timestamp, entry_type:"metadata", data:{session_id, ...}}` (NOT CC-native) | `~/.kosmos/memdir/user/sessions/<uuid>.jsonl` |

## 1. Captured artefacts

| Run | Output | Outcome |
|---|---|---|
| audit-7  | `snap-7-session/` (14 snaps) | Stage 1 turn ran (KMA `t1h:13.3°C` live). `/history` opened (151 sessions enumerated, "+143 more"). Esc didn't dismiss. All later commands typed into stuck dialog. |
| audit-7b | `snap-7b-session/` | tmux pane crashed mid-export. |
| audit-7c | `snap-7c-export/` | Fresh boot triggered "Allow external CLAUDE.md" consent modal — known-state conflict. |
| audit-7d | `snap-7d-full/` (12 snaps) | Full pass after handling consent modal. **First-class evidence for all P0/P1 below.** |

Scripts (committed):
- `scripts/audit-7-session.sh`
- `scripts/audit-7b-session-isolated.sh`
- `scripts/audit-7c-export-only.sh`
- `scripts/audit-7d-full.sh`

## 2. Per-surface verdict

| Surface | Status | Evidence |
|---|---|---|
| First-turn JSONL canonical write | PASS | snap-002 — LLM responded with coords; CC-shape JSONL written to `~/.kosmos/memdir/user/sessions/-Users-um-yunsang-KOSMOS-tui/c4eac756-...jsonl` |
| `/resume` picker open | PASS | snap-008 — `Resume Session (1 of 33)`, current worktree, all 33 sessions enumerated with timestamp / branch / file size |
| `/resume` Ctrl+A/B/W/V/R footer | PASS | snap-008 line 59: `Ctrl+A to show all projects · Ctrl+B to toggle branch · Ctrl+W to show all worktrees · Ctrl+V to preview · Ctrl+R to rename · Type to search · Esc to cancel` |
| `/resume` Esc dismiss | **P1 FAIL** | snap-009 — Esc sent, overlay still on screen identical to snap-008. Subsequent `/history` typed into Resume search box. |
| `/resume` dual-path enumeration (KOSMOS + CC-legacy) | PASS by code | `tui/src/utils/listSessionsImpl.ts:412 gatherAllCandidates()` walks both roots, dedups by sessionId. 33 sessions visible in picker matches the recently-written CC-shape sessions from this audit. |
| `/fork audit-fork` | PASS | snap-007 — `❯ /branch audit-fork ⎿ Branched conversation "audit-fork". You are now in the branch.` Fork JSONL `c4eac756-...jsonl` header has `forkedFrom: { sessionId: "66d1ea39-...", messageUuid: "585f7ec0-..." }` — parent_session_id preserved as required by Epic3-S3. UX label says `/branch` not `/fork` (minor cosmetic). |
| `/continue` (legacy alias) | PARTIAL | `commands/resume.ts:31 aliases:['continue']` registered, but it requires explicit `<session-id>` arg (KOSMOS-original, NOT CC interactive picker). Bare `/continue` returns missing-id error. Bare `/resume` triggers CC interactive picker. **Two divergent code paths share the name `/resume`**. |
| `/migrate-sessions --dry-run` | **P0 FAIL** | snap-006 — `❯ Unknown skill: migrate-sessions ⏺ Args from unknown skill: --dry-run`. Command IS registered in `commands/index.ts:32` but **REPL.tsx slash dispatcher does not consult the KOSMOS registry** — only hardcodes arms for `export`, `history`, `consent`, `agents`, etc. |
| `/history` open | PASS | snap-002 (audit-7) — `과거 세션 검색`, 8 visible + `+143 more = 151 sessions`, layer/date/session filter hints visible. |
| `/history --date YYYY-MM-DD..YYYY-MM-DD --layer N` arg parse | PASS by code | `commands/history.ts:204-216` regex matches `/--date \d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}/`, `/--session [\w-]+/`, `/--layer [123]/`. `applyHistoryFilters()` AND-composes 3 filters. |
| `/history` source enumeration | **P1 FAIL** | `commands/history.ts:49 readdirSync(sessionsDir)` reads only the **flat root** (151 stale stub files), NOT the CC-shape `<sanitized-cwd>/` subdirectory where TUI actually writes. Real conversation sessions are invisible to `/history` — only Python backend stubs show up. The visible 151 in snap-002 are stub metadata, not real conversation sessions. |
| `/history` Esc dismiss | **P0 FAIL** | snap-002→snap-003 (audit-7) — Esc sent, overlay persists. All subsequent `/export`, `/migrate-sessions`, `/fork`, `/resume` typed into stuck History search box and silently dropped. Root cause: `REPL.tsx:3686 isLocalJSXCommand: true` deactivates parent prompt's `useInput` subtree per Infrastructure insight #3, so Dialog's own `useInput((_,k)=>k.escape&&onCancel())` at `HistorySearchDialog.tsx:179` never fires. The fix that worked for `/export`/`/consent` (`isLocalJSXCommand: false`) is not applied here. |
| `/export` dialog open | PASS (then errors) | snap-003 (audit-7d) — overlay opens, K-EXAONE model visible. Lead-Fix7 wiring (`REPL.tsx:3653 executeExport(exportTurns, toolInvocations, receipts)`) feeds real data. |
| `/export` PDF write to `~/Downloads` | **P0 FAIL** | snap-003 status line: `Export failed: WinAnsi cannot encode "대" (0xb300)`. `~/Downloads/kosmos-export*.pdf` never created. Root cause: `ExportPdfDialog.tsx:97-98` uses `StandardFonts.Helvetica` / `HelveticaBold` (WinAnsi 8-bit, no CJK). First Korean char drawn at line 134 (`대화 내보내기`) immediately fails. **Korean public-service platform's export is fundamentally broken for Korean.** |
| `/export` Esc dismiss | PASS | `REPL.tsx:3669 isLocalJSXCommand: false` + `ExportPdfDialog.tsx:219 useInput(...key.escape...)` — defense-in-depth Esc per Infrastructure insight #3 + #4. |
| Session JSONL CC-native schema | PASS | `head -1 c4eac756-...jsonl` shows `{sessionId, forkedFrom:{sessionId, messageUuid}, parentUuid:null, type:"user", timestamp, gitBranch}` — matches CC 2.1.88 byte-identical contract. |
| Backend ↔ TUI session-storage agreement | **P0 FAIL** | Two writers, two schemas, two paths: TUI writes CC-native to `<cwd>/<id>.jsonl`; Python backend writes `{entry_type:"metadata"}` stub to flat `<id>.jsonl`. The two never reconcile. Result: 151 root-level orphan stubs, 0 visible-to-user CC-shape sessions through `/history`. |

## 3. P0 / P1 ledger

### P0-1 — `/export` cannot write Korean PDFs (CRITICAL)
- **Symptom**: `Export failed: WinAnsi cannot encode "대" (0xb300)`
- **File**: `tui/src/components/export/ExportPdfDialog.tsx:97-98`
- **Cause**: `StandardFonts.Helvetica` is WinAnsi 8-bit; cannot encode Hangul U+B300+
- **Fix**: Embed `Noto Sans KR` (or any CJK-capable font) via `pdf-lib` `pdfDoc.registerFontkit(fontkit)` + `pdfDoc.embedFont(notoSansKrBytes)`. Adds `@pdf-lib/fontkit` dep + ~9 MB Noto KR Regular/Bold subset.
- **Production impact**: 100 % of Korean conversations fail to export. Spec UI-E.4 ("대화+도구+영수증 포함") unfulfillable.

### P0-2 — `/history` overlay Esc-stuck blocks all subsequent commands (CRITICAL)
- **Symptom**: Overlay persists after Esc; every subsequent slash command is captured into the stuck search box and silently dropped.
- **File**: `tui/src/screens/REPL.tsx:3686 isLocalJSXCommand: true`
- **Cause**: AGENTS.md Infrastructure insight #3 — `isLocalJSXCommand: true` gates `~10 useInput` hooks via `PromptInput.tsx:244 isModalOverlayActive`, including the Dialog's own Esc watcher at `HistorySearchDialog.tsx:179`.
- **Fix**: One-line `true` → `false`, matching `/export` (REPL.tsx:3669) and `/consent` (REPL.tsx:3710).
- **Production impact**: One `/history` invocation traps the user; only `Ctrl+C × 2` recovers. Spec UI-E.5 unusable.

### P0-3 — `/migrate-sessions` not wired to REPL dispatcher (HIGH)
- **Symptom**: `❯ Unknown skill: migrate-sessions ⏺ Args from unknown skill: --dry-run`
- **Files**: Command exists in `tui/src/commands/migrate-sessions.ts` and is registered in `tui/src/commands/index.ts:32`; **but `tui/src/screens/REPL.tsx`'s slash dispatcher hardcodes only a fixed set (`export`, `history`, `consent`, `agents`, ...) and falls through to CC's "skill" lookup which has no `migrate-sessions`.**
- **Fix**: Either (a) add `if (_kosmosCmd === 'migrate-sessions') { ... }` arm in REPL.tsx alongside the others, OR (b) bridge the KOSMOS `commands/index.ts` registry into REPL's dispatch chain so all KOSMOS-original commands resolve from a single source.
- **Production impact**: Cannot drain the 24 CC-leaked workspace dirs into KOSMOS storage from inside the TUI; blocks Spec UI-E.5 / Lead-Diag-3 cleanup.

### P0-4 — Backend ↔ TUI session storage schema/path mismatch (HIGH)
- **Symptom**: 151 metadata-only stub files at `~/.kosmos/memdir/user/sessions/*.jsonl` from Python backend, never read by TUI; TUI's CC-native sessions live one tier deeper at `<sessions>/<sanitized-cwd>/<id>.jsonl` and are invisible to `/history` (which only reads the flat root).
- **Files**: Python backend writer (writes `{entry_type:"metadata", data:{...}}` stubs) vs `tui/src/commands/history.ts:49 readdirSync(sessionsDir)` vs `tui/src/utils/sessionStorage.ts:211 getProjectsDir()` (writes `<sessions>/<sanitized-cwd>/<id>.jsonl`)
- **Fix**: Pick one canonical layout. Recommended: TUI is the canonical writer (CC-native schema in `<sessions>/<sanitized-cwd>/<id>.jsonl`); Python backend stops writing flat stubs OR consumes from the CC-shape path. Update `commands/history.ts:loadSessionEntries()` to walk subdirectories (mirror `listSessionsImpl.ts:gatherFromRoot`).
- **Production impact**: `/history` shows fake stubs and never the user's real conversations.

### P1-1 — `/resume` picker Esc dismiss (MEDIUM)
- **Symptom**: snap-009 — picker overlay persists after Esc; the next slash command (`/history`) was typed into the stuck Resume search box.
- **Cause**: Likely the same `isLocalJSXCommand: true` defect (CC LogSelector path mounts via a different code path; needs grep verification).
- **Fix**: Audit ResumeConversation.tsx + LogSelector.tsx mount path the same way, ensure `isLocalJSXCommand: false` is set on whatever `setToolJSX` invocation backs `/resume`.

### P1-2 — `/fork` UX label says `/branch` (LOW)
- **Symptom**: snap-007 ack text: `Branched conversation "audit-fork".` — spec UI says `/fork`.
- **Fix**: Either rename the user-visible label to `Forked conversation` OR document `/fork` as alias of `/branch`.

## 4. Production Y/N

**N — NOT production-ready.** Three P0 surface bugs:

1. **PDF export breaks on the very first Korean character** (Helvetica vs CJK). KOSMOS is a Korean public-service platform; this is a release-blocker.
2. **`/history` Esc-stuck** softlocks subsequent commands. UX-fatal.
3. **`/migrate-sessions` not wired** into REPL dispatch. The Lead-Diag-3 leakage cleanup path is unreachable from the TUI.

Plus one P0 architectural issue (backend/TUI session-storage schema mismatch) and one P1 (Resume Esc-stuck likely sharing P0-2's root cause).

**Minimum cuts to reach Production-Y**:

| ETA | Task |
|---|---|
| 30 min | P0-2 + P1-1 — flip `isLocalJSXCommand: true → false` at REPL.tsx:3686 and any analogous Resume/LogSelector mount sites |
| 60 min | P0-3 — add `if (_kosmosCmd === 'migrate-sessions')` arm in REPL.tsx that calls `migrateSessionsCommand.handle({ args: _kosmosArgs, ... })` and renders `MigrateSessionsResult` |
| 4 h | P0-1 — Vendor `Noto Sans KR Regular/Bold` (subset to ~3 MB), wire `pdfDoc.registerFontkit(fontkit) + pdfDoc.embedFont(...)` in `ExportPdfDialog.tsx:97`; add `@pdf-lib/fontkit` to `tui/package.json`. Re-run audit-7d, verify `~/Downloads/kosmos-export_*.pdf` opens with Korean glyphs intact. |
| 1 day | P0-4 — Decide canonical layout, migrate one writer, drain stubs, repoint `/history` to walk subdirectories |
| 30 min | P1-2 — Rename `/branch` ack text → "Forked conversation" |

## 5. Positives (what works as-spec'd)

- Session JSONL canonical write path (`tui/src/utils/sessionStorage.ts:211 getProjectsDir()` returns `~/.kosmos/memdir/user/sessions/`).
- CC-native schema preserved byte-identical (parentUuid / isSidechain / promptId / uuid / timestamp / sessionId / version / gitBranch / cwd).
- `/fork` lineage preservation works — `forkedFrom: { sessionId, messageUuid }` captured at the fork session header.
- `/resume` interactive picker mirrors CC byte-identical (Ctrl+A/B/W/V/R + Esc/Enter footer hints, "current worktree" header, timestamp + branch + size per row).
- Dual-path enumeration code path (`listSessionsImpl.ts:412 gatherAllCandidates()`) walks both KOSMOS + CC-legacy roots and dedupes by sessionId.
- `/migrate-sessions` core util (`utils/migrateSessions.ts`) is correctly implemented (COPYFILE_EXCL + fsync + abort-on-prune-failure invariants honoured); only the REPL wire is missing.
- `/export` Lead-Fix7 wiring is in place (`REPL.tsx:3653 executeExport(exportTurns, toolInvocations, receipts)` feeds real data; `isLocalJSXCommand: false` honours Infrastructure insight #3).
- `/history` 3-filter AND-composition logic is correct (`commands/history.ts:204-216` + `applyHistoryFilters`).
