# /fork command — surface decision

**Status**: Decided — Option A (standalone command).
**Date**: 2026-05-04.
**Owners**: UMMAYA Lead Opus (TUI Epic surface).
**References**:
- `docs/requirements/ummaya-migration-tree.md § L1-A · A5` ("--continue/--resume/--fork/new" promise).
- `tui/src/commands/branch/index.ts:8` (current alias gate).
- `tui/src/stubs/bun-bundle.ts:5` (`feature('FORK_SUBAGENT')` permanent stub returning `false`).
- `tui/src/tools/AgentTool/forkSubagent.ts` (CC's subagent fork — distinct feature, NOT what UMMAYA wants).
- `tui/src/commands/catalog.ts` (UI L2 autocomplete SSOT, Spec 1635).
- Historical S10 session-lifecycle capture (the old integration-verification artifact set has been retired by Evidence Fabric v2).

## Context — what `/fork` means in two different lineages

There are two unrelated concepts colliding under the word "fork":

1. **CC `FORK_SUBAGENT`** (`tui/src/tools/AgentTool/forkSubagent.ts`) — an experimental Claude Code feature where the parent agent spawns a child subagent that inherits the full conversation context as a prompt-cache-aligned prefix. The `/fork` slash command in CC takes a directive string and dispatches it to the child. **This feature is gated by `feature('FORK_SUBAGENT')`, which UMMAYA's `bun-bundle` stub hard-codes to `false`.** Subagent fork is mutually exclusive with coordinator mode and has no analogue in the UMMAYA migration plan — it is not part of the citizen-facing surface.

2. **CC `/branch`** (`tui/src/commands/branch/branch.ts`) — copies the current session's transcript JSONL to a new file with a new `sessionId`, preserves all messages (including content-replacement rewrites for prompt-cache continuity), then resumes into the new session. This is **session forking**: same conversation history, divergent future. `/fork` was registered as a CC alias of `/branch` ONLY when `FORK_SUBAGENT` was off, on the rationale that the noun "fork" is more colloquial than "branch" when the subagent feature is unavailable.

UMMAYA inherits both code paths byte-identical from CC restored-src. UMMAYA migration tree A5 promises `--continue/--resume/--fork/new` as four distinct citizen-facing session lifecycle modes. The contract A5 references is **session forking** (concept #2), not subagent forking (concept #1).

## The bug surfaced in S10

Integration scenario S10 (`scn-S10-session-lifecycle.sh:13`) types `/fork` then Enter. Observed:

- The **registry-level dispatch** (REPL.tsx:3700, alias lookup `cmd.aliases?.includes('fork')`) DOES route `/fork` to `branch`. Verified:
  ```
  $ bun -e "import('./src/commands.js').then(m => m.getCommands(process.cwd())).then(cmds => console.log(cmds.find(c => c.aliases?.includes('fork'))))"
  { name: "branch", aliases: ["fork"], … }
  ```
- The **autocomplete dropdown** (`commands/catalog.ts` UI L2 SSOT, consumed by `SlashCommandSuggestions.tsx`) does NOT contain `/fork`, `/branch`, or even `/resume`. As the citizen types `/fork`, `matchPrefix("/fork")` returns 0 entries → no dropdown suggestion → the surface looks dead.
- The user-facing observation ("`/fork` gets absorbed by `/resume` overlay") is consistent with: enter on no-match falls through to dispatch which finds branch via alias, branch then calls `setToolJSX` with the resume picker because `branch.tsx` mounts a confirmation flow. Either way, `/fork` is not a discoverable, first-class surface.

**Diagnosis: `/fork` is functionally alive (alias path works) but visually dead (catalog absent). The decision below treats both layers.**

## Options considered

### Option A — `/fork` becomes a standalone command (recommended)

- Add `tui/src/commands/fork/index.ts` as a first-class `Command` that delegates `load()` to `branch/branch.js`. The handler is identical to branch — both copy session JSONL with a new UUID and resume into the copy.
- Add `/fork`, `/branch`, `/resume`, `/continue` to `tui/src/commands/catalog.ts` so the autocomplete dropdown surfaces them.
- Keep the existing `branch` alias `['fork']` ONLY as belt-and-suspenders; the standalone `fork` command becomes the canonical surface.
- `feature('FORK_SUBAGENT')` stays `false` permanently — the subagent variant is dead in UMMAYA. The `forkCmd` slot in `commands.ts:112` is decoupled from the FORK_SUBAGENT gate and points at the new standalone command unconditionally.

**Pros**:
- Honors `ummaya-migration-tree.md § A5` literally (4 distinct modes).
- Surfaces `/fork` in the autocomplete dropdown so citizens can discover it.
- Reuses `branch.ts` implementation 100% — no duplicate session-fork logic to maintain.
- Spec 027 session lifecycle invariant preserved (one JSONL per session_id, append-only, immutable).

**Cons**:
- Two registry entries (`branch` + `fork`) point at the same handler. Mitigated by sharing the same `load()` target — they are byte-identical at runtime.

### Option B — drop `/fork` from the migration tree

- Remove the A5 mention of `/fork` from `docs/requirements/ummaya-migration-tree.md`. Keep `/branch` only (with its `['fork']` alias for muscle memory, decoupled from FORK_SUBAGENT gate).
- Document in the migration tree that "fork" and "branch" are synonyms in UMMAYA, both pointing at session JSONL copy.

**Pros**:
- Minimal change.
- Acknowledges that the noun "fork" doesn't carry CC's subagent meaning in UMMAYA.

**Cons**:
- Drops a citizen-facing affordance that A5 promised. Existing scenario captures (S10) expect `/fork` as a probe.
- Does not fix the autocomplete catalog gap — `/branch` is still missing from the UI L2 SSOT.

## Decision: Option A

A is chosen because:
1. A5 of the migration tree is canonical. Honoring it costs ~30 LOC (one new command file + 4 catalog entries + one test).
2. The Option A change is non-destructive. The CC subagent fork code path remains intact behind `feature('FORK_SUBAGENT')` and can be revived if UMMAYA ever introduces a citizen-facing parallel-execution surface (currently out of scope per AGENTS.md L1 pillars).
3. Spec 027 session lifecycle is preserved: forking creates a new `session_id` and a new `~/.ummaya/memdir/user/sessions/<new_id>.jsonl` (or current `~/.claude/projects/<...>` path until Spec 027 storage migration completes — see `tui/src/utils/sessionStorage.ts:getTranscriptPathForSession`). The path migration is tracked separately (P0 #11, "session storage path mismatch") and is **not** in scope of this decision.

## Implementation summary

1. New file `tui/src/commands/fork/index.ts` — registers `fork` as a `local-jsx` command, `description: 'Fork the current conversation into a new session'`, `argumentHint: '[name]'`, `load: () => import('../branch/branch.js')`.
2. `tui/src/commands.ts:112` — `const forkCmd = …` no longer reads the `FORK_SUBAGENT` flag; imports the new file unconditionally.
3. `tui/src/commands/branch/index.ts:8` — alias `['fork']` is preserved unconditionally (`['fork']` regardless of `feature('FORK_SUBAGENT')`); the registry deduplicates on canonical name.
4. `tui/src/commands/catalog.ts` — add `/fork`, `/branch`, `/resume`, `/continue` entries under `group: 'session'` so they show up in the autocomplete dropdown (FR-014, Spec 1635).
5. Unit test `tui/src/commands/fork/__tests__/fork.test.ts` — asserts the registry has a canonical `fork` command, that its handler is the same module as `branch`, and that the catalog now contains a `/fork` entry.

## Out of scope

- Spec 027 session storage path migration (P0 #11). Fork still uses the legacy `~/.claude/projects/...` path until that Epic ships.
- CC `FORK_SUBAGENT` revival. Subagent fork is a separate feature with its own Epic if/when UMMAYA pursues a parallel-execution surface.
- Worktree-scoped fork (CC `forkSubagent.ts:buildWorktreeNotice`). UMMAYA does not yet have a worktree story.
