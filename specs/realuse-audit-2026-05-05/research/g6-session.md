# G6 — `--continue` cross-session contamination — research

> Wave-2 Lead Opus G6. F-alpha-13 root-cause analysis + fix design.
> Reproduction: `findings/alpha/snap/alpha8/snap-002-after-enter.txt:7,11` —
> α8's `--continue` resumed `b6765a77-...` ("서울 강남구 응급실 검색") instead of
> α6's "1부터 100까지의 합" session, with both files living in the same
> cwd-scoped project dir.

---

## 1. Resolver call-chain (today)

```
main.tsx:2204    options.continue → loadConversationForResume(undefined, undefined)
                                 (utils/conversationRecovery.ts:487)
                  └─ source === undefined branch
                     ├─ loadMessageLogs()                              (sessionStorage.ts:3962)
                     │   └─ fetchLogs()                                 (sessionStorage.ts:2582)
                     │       └─ projectDir = getProjectDir(getOriginalCwd())  ← cwd scope #1
                     │           = getProjectsDir() / sanitizePath(cwd)
                     │           = ~/.kosmos/memdir/user/sessions/-Users-…-KOSMOS-tui/
                     │       └─ getSessionFilesLite(projectDir)         (sessionStorage.ts:4998)
                     │           └─ stat all *.jsonl, sort by mtime DESC
                     ├─ enrichLogs() (reads first prompt, gitBranch, customTitle, …)
                     ├─ sortLogs()   (re-sort by .modified DESC, .created tiebreak)
                     └─ logs.find(skip BG_SESSIONS) → first hit wins
```

**Two scope axes already in play**:
- (a) `getProjectsDir()` root — `~/.kosmos/memdir/user/sessions/` (`KOSMOS_MEMDIR_USER` override).
- (b) `sanitizePath(getOriginalCwd())` — flattens `/Users/me/proj` into `-Users-me-proj` subdirectory.

**One scope axis CC keeps but KOSMOS dropped**:
- (c) `feature('BG_SESSIONS')` live-session filter — `tui/src/utils/conversationRecovery.ts:492`.
  The CC fast-path queries the UDS daemon (`udsClient.listAllLiveSessions`) and excludes any
  session-ID currently being written by a sibling background/daemon process. **In KOSMOS,
  `feature()` is a stub that returns `false` for every flag** (`tui/src/stubs/bun-bundle.ts:4`),
  so the entire concurrent-session protection is dead code at runtime.

## 2. Why F-alpha-13 fired

Timeline reconstructed from snapshot mtimes + JSONL session-headers under
`~/.kosmos/memdir/user/sessions/-Users-um-yunsang-KOSMOS-tui/`:

| t        | event                                                     | session id         | mtime |
|----------|-----------------------------------------------------------|--------------------|-------|
| 13:42    | α6 boot, asks "1부터 100까지의 합"                          | `e866f874-…`       | 13:43 |
| 13:43    | α7 `--continue` — RESUMES α6 correctly                    | (resumed e866f874) | —     |
| 13:43    | (parallel agent in same cwd) writes "강남구 응급실"         | `b6765a77-…`       | 13:43 |
| 13:43:30 | α8 `--continue` — picks `b6765a77` (≥ α6 mtime by ms)      | (wrong)            | —     |

Both sessions carry `cwd: "/Users/um-yunsang/KOSMOS/tui"` in their JSONL header,
so cwd-scope (b) cannot disambiguate them. The mtime tiebreaker is sub-second and
non-deterministic when multiple TUI instances write within the same second.

The triage hypothesis blamed δ's `mv ~/.kosmos.bak.delta.<pid> ~/.kosmos`
preserving mtimes — that's a contributing pollution source (the 60+ files at
13:30 in the same dir confirm a bulk rename), but the **dominant** cause is
unrelated: parallel α/β/δ agent processes operating in the same cwd write to
the same shared `(memdir-root, sanitized-cwd)` bucket, with no shell-context
separator. Even without δ's restore, two interactive REPL sessions in the same
directory would step on each other.

## 3. CC's resolver — what scope axis it relies on

CC restored-src paths:
- `restored-src/src/utils/sessionStorage.ts:2559` — `fetchLogs()`: identical to
  KOSMOS (cwd-sanitized project dir, mtime sort).
- `restored-src/src/utils/conversationRecovery.ts:492` — `BG_SESSIONS` filter
  is *active* in CC. The UDS daemon (`udsClient.listAllLiveSessions`) tracks
  every CC process actively writing a transcript. The recency-walk skips any
  session-id currently locked by a sibling process.

CC therefore does NOT solve "two foreground REPLs in the same cwd race for
`--continue`" — it only solves "background (`--bg`/daemon) sessions don't
clobber foreground continue". CC's UX ASSUMES at most one interactive REPL
per cwd at a time; its design takes for granted that the user does not run
two `claude` instances side-by-side in `~/proj`. KOSMOS inherits this
assumption but ALSO has the audit-time reality of multiple Lead Opus agents
operating in the same worktree.

**Verdict**: KOSMOS cannot copy CC byte-identically here — CC's scope is
"cwd plus single-instance assumption" and KOSMOS' real-world workload (parallel
agents, repeated audits, backup/restore drills) breaks the implicit assumption.

## 4. Scope candidates evaluated

| Candidate                                  | Disambiguates F-alpha-13? | Survives reboot? | Implementation cost | Verdict |
|--------------------------------------------|---------------------------|------------------|---------------------|---------|
| Process tree root PID                       | yes                       | NO (PIDs reused) | trivial             | reject — not durable |
| `tmux` session name (`$TMUX`)                | yes                       | NO (tmux dies)   | trivial             | reject |
| `$SSH_TTY` / `tty` device                   | partial (single shell)    | NO               | trivial             | reject |
| Persistent `$KOSMOS_SHELL_CONTEXT_ID` env   | yes if set                | yes              | low                 | feasible but opt-in only |
| **Per-shell-context sentinel file under cwd**| **yes**                   | **yes**          | **low**             | **selected** |
| Stamp `originalShellId` in JSONL header     | yes                       | yes              | low                 | selected (write-side) |
| Drop cwd-scope, switch to project hash      | no — same root cause      | n/a              | medium              | reject |

### Selected design: write-side stamp + read-side filter

1. **Write side**: at TUI boot, derive `originalShellId` deterministically from
   *(parent process tree, terminal, ssh, uid)* and stamp it into the FIRST
   JSONL line that gets appended for the session (the same line that today
   carries `cwd`, `userType`, `entrypoint`, `version`, `gitBranch`). New field:
   `originalShellId: string` (16-char hex prefix of SHA-256).

2. **Read side**: `--continue` resolver computes the current shell's
   `originalShellId` and prefers logs whose header `originalShellId` matches.
   Falls back to the global cwd-scoped recency winner if NO match exists
   (preserves the common-case UX: "I just ran one TUI, exit, re-enter, --continue").

3. **Backwards compat**: legacy sessions written before this change have no
   `originalShellId` field — they fall through to the global path naturally.
   No migration, no breaking change.

### How `originalShellId` is computed (deterministic)

Inputs (in priority order; later inputs only included if earlier are missing):

```ts
function computeShellContextId(): string {
  const parts: string[] = []
  // 1. parent PID (process group leader) — survives child fork-exec inside same shell
  parts.push(`ppid=${process.ppid ?? 'na'}`)
  // 2. tmux session — same tmux pane shares the context across re-entries
  if (process.env.TMUX) parts.push(`tmux=${process.env.TMUX}`)
  if (process.env.TMUX_PANE) parts.push(`pane=${process.env.TMUX_PANE}`)
  // 3. ssh tty — distinguishes ssh tunnels
  if (process.env.SSH_TTY) parts.push(`ssh=${process.env.SSH_TTY}`)
  // 4. terminal session id (macOS Terminal.app + most modern emulators)
  if (process.env.TERM_SESSION_ID) parts.push(`term=${process.env.TERM_SESSION_ID}`)
  // 5. controlling tty
  try {
    const tty = (process.stdin as any).isTTY ? require('tty').getRawTtyName?.() : undefined
    if (tty) parts.push(`tty=${tty}`)
  } catch {}
  // 6. uid — separate per-user even if everything else matches
  parts.push(`uid=${process.getuid?.() ?? 'na'}`)
  // 7. KOSMOS escape hatch: explicit override wins
  if (process.env.KOSMOS_SHELL_CONTEXT_ID)
    return process.env.KOSMOS_SHELL_CONTEXT_ID.slice(0, 32)

  return crypto.createHash('sha256').update(parts.join(' ')).digest('hex').slice(0, 16)
}
```

Properties:
- Deterministic for the lifetime of a single shell process.
- Stable across child re-execs inside the same shell (ppid identical).
- Differs across two side-by-side terminals (ppid differs OR tmux pane differs OR ssh tty differs).
- 16-char hex (8 bytes entropy) — collision space ample for the dozen-process ceiling.
- `KOSMOS_SHELL_CONTEXT_ID` env override gives test fixtures + advanced users
  an explicit isolation knob.

### Memoization

Compute once at TUI boot, cache in module-level constant. Worktree switches
do NOT change shell-context — the ppid is stable. This is exactly the
opposite trade-off of `getOriginalCwd()` which CAN change mid-session under
worktree commands.

## 5. Risk analysis vs. existing UX

| Common-case UX                               | Pre-fix behaviour | Post-fix behaviour | Drift? |
|----------------------------------------------|-------------------|--------------------|--------|
| Single user, single terminal: exit + `--continue` | resumes last         | resumes last (shell-id match)            | NONE |
| Same user opens 2nd terminal in same dir      | resumes whichever was newer | resumes 2nd terminal's own session     | **fix** |
| Reboot → re-launch shell → `--continue`        | resumes last (mtime)  | shell-id mismatch → falls back to mtime   | NONE (graceful) |
| `claude --resume <uuid>`                      | direct lookup by uuid | direct lookup by uuid                    | NONE (untouched code path) |
| `/resume` interactive picker                   | shows full cwd-scoped list | shows full cwd-scoped list             | NONE (picker untouched) |
| Existing session created before fix           | mtime sort              | falls through to mtime sort              | NONE |

The only change is `--continue`'s tie-breaking rule when multiple sessions
share the same cwd. Single-shell users see no behaviour change.

## 6. Test strategy

### Layer 1a — pytest is N/A (TS-only surface).

### Layer 2 — bun test, synthetic mixed-shell-id memdir
- New `tui/src/utils/__tests__/continueResolver.shell-context.test.ts`.
- Setup: write 3 sessions into a temp `KOSMOS_MEMDIR_USER` dir, all sharing
  the same `cwd`. Header `originalShellId` differs: `aaa`, `bbb`, `aaa`.
- Set `KOSMOS_SHELL_CONTEXT_ID=aaa`. Call `pickContinueLog(logs)`.
- Assert: it picks the *most recent of the two `aaa` sessions*, not the `bbb`.
- Set `KOSMOS_SHELL_CONTEXT_ID=ccc` (no match). Assert: falls back to global
  most-recent (the `bbb` if it's newest, or `aaa` if older).
- Add a fourth fixture: legacy session with NO `originalShellId` field.
  Assert: under `ccc`, this legacy session participates in the global
  fallback ordering correctly.

### Layer 5 — tmux capture-pane (manual sign-off recipe in fix doc)
- Recipe: spawn TUI in cwd A → exit → spawn TUI in cwd A from a *second*
  terminal/tmux pane → exit → first terminal `--continue` → must restore
  first terminal's session, not second's.
- Re-run α7 (single-shell `--continue` happy path) — must still pass.

## 7. Out of scope (deferred)

- Migrating already-on-disk legacy sessions to add `originalShellId`. Not
  needed: the read-side fallback handles them.
- UDS daemon-based live-session filter (`feature('BG_SESSIONS')` activation).
  Tracked separately under L1-A background-sessions epic.
- `/resume` picker filtering by shell context. Picker is interactive and
  user-driven — global cwd-scoped list is preferred UX.
- Cross-host (`SSH_TTY` aliasing) edge cases. Single-host only for now.

## 8. References

- `tui/src/utils/conversationRecovery.ts:456-512` — current `--continue` resolver.
- `tui/src/utils/sessionStorage.ts:2582-2589` — `fetchLogs` cwd scope.
- `tui/src/utils/sessionStorage.ts:4762-4836` — `readLiteMetadata` (where new field is parsed).
- `tui/src/utils/sessionStorage.ts:1062-1087` — TranscriptMessage header (where new field is stamped).
- `.references/claude-code-sourcemap/restored-src/src/utils/conversationRecovery.ts:486-512` — CC reference (BG_SESSIONS gated).
- `tui/src/stubs/bun-bundle.ts:4` — `feature()` returns `false` always (BG_SESSIONS dead in KOSMOS).
- `findings/alpha/findings-alpha.md § F-alpha-13` — bug source-of-truth.
- `triage.md § Pattern P-G` — pattern classification.
