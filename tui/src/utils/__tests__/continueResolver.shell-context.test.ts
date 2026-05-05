// SPDX-License-Identifier: Apache-2.0
/**
 * G6 (F-alpha-13) — `--continue` resolver shell-context scoping.
 *
 * Spec ref: `specs/realuse-audit-2026-05-05/research/g6-session.md`.
 * Bug ref: `specs/realuse-audit-2026-05-05/findings/alpha/findings-alpha.md § F-alpha-13`.
 *
 * Verifies:
 *   1. Two cwd-equivalent sessions stamped with different `originalShellId`
 *      do not contaminate each other's `--continue` result.
 *   2. The resolver prefers the most recent log whose `originalShellId`
 *      matches the current shell context, even if a *globally* newer log
 *      from a different shell context exists in the same cwd.
 *   3. When NO log carries a matching `originalShellId` (cross-cwd reboot,
 *      legacy sessions, fresh shell), the resolver falls through to the
 *      global cwd-scoped recency winner. This preserves the common-case
 *      single-shell `--continue` UX.
 *   4. Legacy sessions with no `originalShellId` field are still considered
 *      in the fallback path and never crash the resolver.
 */

import { test, expect, beforeEach, afterEach } from 'bun:test'

import {
  pickByShellContextId,
  setShellContextIdForTesting,
  _resetShellContextIdForTesting,
  getShellContextId,
} from '../shellContext.js'

type FakeLog = {
  sessionId: string
  modified: Date
  originalShellId?: string
}

beforeEach(() => {
  _resetShellContextIdForTesting()
})

afterEach(() => {
  _resetShellContextIdForTesting()
})

// ---------------------------------------------------------------------------
// shellContext.ts core
// ---------------------------------------------------------------------------

test('getShellContextId honors KOSMOS_SHELL_CONTEXT_ID env override', () => {
  const originalEnv = process.env['KOSMOS_SHELL_CONTEXT_ID']
  try {
    process.env['KOSMOS_SHELL_CONTEXT_ID'] = 'test-shell-aaaa'
    _resetShellContextIdForTesting()
    expect(getShellContextId()).toBe('test-shell-aaaa')
  } finally {
    if (originalEnv === undefined) {
      delete process.env['KOSMOS_SHELL_CONTEXT_ID']
    } else {
      process.env['KOSMOS_SHELL_CONTEXT_ID'] = originalEnv
    }
    _resetShellContextIdForTesting()
  }
})

test('getShellContextId test injection wins over env', () => {
  const originalEnv = process.env['KOSMOS_SHELL_CONTEXT_ID']
  try {
    process.env['KOSMOS_SHELL_CONTEXT_ID'] = 'env-id'
    setShellContextIdForTesting('injected-id')
    expect(getShellContextId()).toBe('injected-id')
  } finally {
    if (originalEnv === undefined) {
      delete process.env['KOSMOS_SHELL_CONTEXT_ID']
    } else {
      process.env['KOSMOS_SHELL_CONTEXT_ID'] = originalEnv
    }
    _resetShellContextIdForTesting()
  }
})

test('getShellContextId is deterministic per-process when no override', () => {
  // Without override: two consecutive calls must return the same value.
  delete process.env['KOSMOS_SHELL_CONTEXT_ID']
  _resetShellContextIdForTesting()
  const id1 = getShellContextId()
  const id2 = getShellContextId()
  expect(id1).toBe(id2)
  expect(id1).toMatch(/^[0-9a-f]{16}$/) // 16 hex chars = SHA-256 prefix
})

test('getShellContextId differs across simulated shells (TMUX_PANE)', () => {
  delete process.env['KOSMOS_SHELL_CONTEXT_ID']
  const originalPane = process.env['TMUX_PANE']
  const originalTmux = process.env['TMUX']
  try {
    process.env['TMUX'] = '/tmp/tmux-1000/default,123,0'
    process.env['TMUX_PANE'] = '%0'
    _resetShellContextIdForTesting()
    const idA = getShellContextId()

    process.env['TMUX_PANE'] = '%99'
    _resetShellContextIdForTesting()
    const idB = getShellContextId()

    expect(idA).not.toBe(idB)
  } finally {
    if (originalPane === undefined) delete process.env['TMUX_PANE']
    else process.env['TMUX_PANE'] = originalPane
    if (originalTmux === undefined) delete process.env['TMUX']
    else process.env['TMUX'] = originalTmux
    _resetShellContextIdForTesting()
  }
})

// ---------------------------------------------------------------------------
// pickByShellContextId — the resolver primitive
// ---------------------------------------------------------------------------

test('pickByShellContextId returns most recent log with matching shell id', () => {
  // Logs are pre-sorted newest-first (matches loadMessageLogs contract).
  const logs: FakeLog[] = [
    { sessionId: 'newest-other-shell', modified: new Date(3000), originalShellId: 'shell-bbb' },
    { sessionId: 'mid-our-shell',      modified: new Date(2000), originalShellId: 'shell-aaa' },
    { sessionId: 'oldest-our-shell',   modified: new Date(1000), originalShellId: 'shell-aaa' },
  ]

  const picked = pickByShellContextId(logs, 'shell-aaa')
  expect(picked).toBeDefined()
  expect(picked!.sessionId).toBe('mid-our-shell')
})

test('pickByShellContextId rejects newer log from different shell', () => {
  // F-alpha-13 reproduction: this is exactly the bug — the cross-shell log
  // is globally newer (modified=3000) but it must NOT be picked when our
  // shell id is "shell-aaa" and we have an older "shell-aaa" log available.
  const logs: FakeLog[] = [
    { sessionId: 'b6765a77-cross-shell', modified: new Date(3000), originalShellId: 'shell-bbb' },
    { sessionId: 'e866f874-our-shell',   modified: new Date(2900), originalShellId: 'shell-aaa' },
  ]

  const picked = pickByShellContextId(logs, 'shell-aaa')
  expect(picked!.sessionId).toBe('e866f874-our-shell')
  expect(picked!.sessionId).not.toBe('b6765a77-cross-shell')
})

test('pickByShellContextId returns undefined when no match, signaling fallback', () => {
  const logs: FakeLog[] = [
    { sessionId: 'a', modified: new Date(2000), originalShellId: 'shell-bbb' },
    { sessionId: 'b', modified: new Date(1000), originalShellId: 'shell-ccc' },
  ]

  const picked = pickByShellContextId(logs, 'shell-aaa')
  expect(picked).toBeUndefined()
})

test('pickByShellContextId ignores logs without originalShellId', () => {
  // Legacy sessions written before G6 carry no originalShellId. They must
  // not match against the current shell — but must NOT crash the resolver.
  const logs: FakeLog[] = [
    { sessionId: 'legacy', modified: new Date(2000) }, // no originalShellId
    { sessionId: 'new',    modified: new Date(1000), originalShellId: 'shell-aaa' },
  ]

  const picked = pickByShellContextId(logs, 'shell-aaa')
  expect(picked!.sessionId).toBe('new')
})

test('pickByShellContextId on all-legacy list returns undefined', () => {
  const logs: FakeLog[] = [
    { sessionId: 'legacy-a', modified: new Date(3000) },
    { sessionId: 'legacy-b', modified: new Date(2000) },
    { sessionId: 'legacy-c', modified: new Date(1000) },
  ]

  const picked = pickByShellContextId(logs, 'shell-anything')
  // Nothing matches — caller falls back to candidates[0].
  expect(picked).toBeUndefined()
})

test('pickByShellContextId empty list returns undefined', () => {
  expect(pickByShellContextId([], 'shell-aaa')).toBeUndefined()
})

// ---------------------------------------------------------------------------
// End-to-end fallback contract — mirrors the resolver's
// `pickByShellContextId(candidates, currentShellId) ?? candidates[0] ?? null`
// expression in conversationRecovery.ts
// ---------------------------------------------------------------------------

function resolveContinue<T extends { originalShellId?: string }>(
  candidates: readonly T[],
  shellId: string,
): T | null {
  return pickByShellContextId(candidates, shellId) ?? candidates[0] ?? null
}

test('resolveContinue fallback: no shell match falls through to global recent', () => {
  const logs: FakeLog[] = [
    { sessionId: 'most-recent', modified: new Date(3000), originalShellId: 'shell-bbb' },
    { sessionId: 'older',       modified: new Date(2000), originalShellId: 'shell-ccc' },
  ]

  const picked = resolveContinue(logs, 'shell-aaa')
  // No "shell-aaa" exists → fall through to global recent (logs[0]).
  expect(picked!.sessionId).toBe('most-recent')
})

test('resolveContinue F-alpha-13 scenario: shell-aaa picks older shell-aaa over newer cross-shell', () => {
  const logs: FakeLog[] = [
    { sessionId: 'b6765a77-cross', modified: new Date(3000), originalShellId: 'shell-bbb' },
    { sessionId: 'e866f874-ours',  modified: new Date(2900), originalShellId: 'shell-aaa' },
    { sessionId: 'older-cross',    modified: new Date(2000), originalShellId: 'shell-bbb' },
  ]

  const picked = resolveContinue(logs, 'shell-aaa')
  expect(picked!.sessionId).toBe('e866f874-ours')
})

test('resolveContinue mixed legacy + new: legacy session NOT preferred under any shell', () => {
  const logs: FakeLog[] = [
    { sessionId: 'mid-legacy', modified: new Date(2500) },
    { sessionId: 'new-aaa',    modified: new Date(2000), originalShellId: 'shell-aaa' },
  ]

  const picked = resolveContinue(logs, 'shell-aaa')
  // shell-aaa exists → pick it even though legacy is globally newer.
  expect(picked!.sessionId).toBe('new-aaa')
})

test('resolveContinue empty candidate list returns null', () => {
  const picked = resolveContinue([] as FakeLog[], 'shell-aaa')
  expect(picked).toBeNull()
})
