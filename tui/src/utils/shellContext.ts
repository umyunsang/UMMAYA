// SPDX-License-Identifier: Apache-2.0
/**
 * Shell-context identification for `--continue` resolver scoping.
 *
 * Spec ref: `specs/realuse-audit-2026-05-05/research/g6-session.md` (F-alpha-13).
 *
 * Problem: KOSMOS' `--continue` resolver sorts cwd-scoped sessions by mtime
 * and picks the global recent winner. When two interactive REPLs run in the
 * same cwd (parallel agents, audit drills, sibling tmux panes), they
 * contaminate each other's continue-history.
 *
 * Solution: stamp every session's first JSONL line with `originalShellId` —
 * a deterministic 16-hex-char hash of the current shell context (parent PID,
 * tmux pane, ssh tty, terminal session, controlling tty, uid). At
 * `--continue` time, the resolver prefers logs whose `originalShellId`
 * matches the current shell. Falls back to the global recent winner when no
 * shell-id-scoped match exists, preserving the common-case UX.
 *
 * Backwards compat: legacy sessions without `originalShellId` participate in
 * the fallback path naturally (no migration required).
 */

import { createHash } from 'node:crypto'

/**
 * Maximum length of the resolved shell-context id. Keep small to bound
 * the per-line JSONL header cost; 16 hex chars = 8 bytes of entropy is
 * ample for the dozen-process ceiling we expect in practice.
 */
const SHELL_CONTEXT_ID_LEN = 16

/**
 * Module-level cache. Computing requires a syscall (process.getuid) and an
 * env walk; safe to memoize for the lifetime of the TUI process because none
 * of the inputs (parent PID, tmux pane, ssh tty, term session, uid) mutate
 * mid-process.
 */
let cachedShellContextId: string | undefined

/**
 * Test-only override. When set, `getShellContextId()` returns this value
 * directly without recomputing. Used by `__tests__/...` to inject
 * deterministic ids without polluting `process.env`.
 */
let overrideForTesting: string | undefined

/**
 * Internal: assemble the deterministic input string from the shell context.
 * Order matters — every input is prefixed with its key so partial overlap
 * cannot collide (e.g. `tmux=foo` cannot collide with `pane=foo`).
 */
function gatherShellContextInputs(): string {
  const parts: string[] = []

  // 1. Parent PID — the process group leader. Stable across child fork-exec
  //    inside the same shell, distinct between two side-by-side terminals
  //    (each has its own bash/zsh process).
  parts.push(`ppid=${process.ppid ?? 'na'}`)

  // 2. tmux session/pane — same tmux pane shares the context across
  //    re-entries; different panes have different `$TMUX_PANE`.
  if (process.env['TMUX']) parts.push(`tmux=${process.env['TMUX']}`)
  if (process.env['TMUX_PANE']) parts.push(`pane=${process.env['TMUX_PANE']}`)

  // 3. ssh tty — distinguishes ssh tunnels.
  if (process.env['SSH_TTY']) parts.push(`ssh=${process.env['SSH_TTY']}`)

  // 4. Terminal session id — set by macOS Terminal.app, iTerm2, VS Code,
  //    most modern emulators. Survives shell respawn inside the same window.
  if (process.env['TERM_SESSION_ID']) {
    parts.push(`term=${process.env['TERM_SESSION_ID']}`)
  }

  // 5. uid — separate per-user even if everything else matches (e.g. su).
  parts.push(
    `uid=${typeof process.getuid === 'function' ? process.getuid() : 'na'}`,
  )

  return parts.join(' ')
}

/**
 * Returns the current shell-context id. Computed once per process and
 * cached. Consumers that need a fresh value (test cleanup) call
 * `_resetShellContextIdForTesting()`.
 *
 * Override priority:
 *   1. `setShellContextIdForTesting()` — test injection, never set in prod.
 *   2. `KOSMOS_SHELL_CONTEXT_ID` env var — explicit user/CI escape hatch.
 *   3. Computed hash from process attributes.
 */
export function getShellContextId(): string {
  if (overrideForTesting !== undefined) return overrideForTesting
  if (cachedShellContextId !== undefined) return cachedShellContextId

  const envOverride = process.env['KOSMOS_SHELL_CONTEXT_ID']
  if (envOverride) {
    cachedShellContextId = envOverride.slice(0, SHELL_CONTEXT_ID_LEN)
    return cachedShellContextId
  }

  const inputs = gatherShellContextInputs()
  cachedShellContextId = createHash('sha256')
    .update(inputs)
    .digest('hex')
    .slice(0, SHELL_CONTEXT_ID_LEN)
  return cachedShellContextId
}

/**
 * Test-only: inject a fixed shell-context id. Pass `undefined` to clear.
 */
export function setShellContextIdForTesting(id: string | undefined): void {
  overrideForTesting = id
}

/**
 * Test-only: clear the module-level cache so subsequent calls recompute
 * from current `process.env`.
 */
export function _resetShellContextIdForTesting(): void {
  cachedShellContextId = undefined
  overrideForTesting = undefined
}

/**
 * Resolver helper: given a list of cwd-scoped logs sorted by recency
 * (newest first) and a target `shellContextId`, return the first log whose
 * header contains that id. Returns `undefined` if no log matches — caller
 * should fall back to the global recent winner.
 *
 * `originalShellId` is read from the lite-metadata layer
 * (`readLiteMetadata`), so callers MUST pass logs that have already been
 * enriched (i.e. `isLite === false`).
 */
export function pickByShellContextId<T extends { originalShellId?: string }>(
  enrichedLogs: readonly T[],
  shellContextId: string,
): T | undefined {
  for (const log of enrichedLogs) {
    if (log.originalShellId && log.originalShellId === shellContextId) {
      return log
    }
  }
  return undefined
}
