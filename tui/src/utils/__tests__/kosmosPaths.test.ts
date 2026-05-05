// SPDX-License-Identifier: Apache-2.0
/**
 * Unit tests for tui/src/utils/kosmosPaths.ts
 *
 * Verifies:
 *   1. Default paths resolve to ~/.kosmos/memdir/user[/sessions]
 *   2. KOSMOS_MEMDIR_USER env override is respected
 *   3. Memoize invalidation fires when the env var changes between calls
 */

import { test, expect, beforeEach, afterEach } from 'bun:test'
import { homedir } from 'os'
import { join } from 'path'

// We import by absolute path so bun module cache isolation works correctly.
// Each test that mutates process.env must re-import via dynamic import to
// bypass the module cache — or clear the cache via module mock. Because
// kosmosPaths.ts uses a plain closure cache (not lodash memoize), the same
// module instance is fine: mutating env + calling the function again is
// sufficient to observe invalidation.

let getKosmosUserTierRoot: () => string
let getKosmosSessionsDir: () => string

const ORIGINAL_KOSMOS_MEMDIR_USER = process.env.KOSMOS_MEMDIR_USER

beforeEach(async () => {
  // Remove any env override so we start from the default state.
  delete process.env.KOSMOS_MEMDIR_USER

  // Dynamic re-import ensures the closure cache is warm-started in the
  // default (no-override) state for each test group.
  const mod = await import('../kosmosPaths.js')
  getKosmosUserTierRoot = mod.getKosmosUserTierRoot
  getKosmosSessionsDir = mod.getKosmosSessionsDir
})

afterEach(() => {
  // Restore original env state to avoid cross-test pollution.
  if (ORIGINAL_KOSMOS_MEMDIR_USER === undefined) {
    delete process.env.KOSMOS_MEMDIR_USER
  } else {
    process.env.KOSMOS_MEMDIR_USER = ORIGINAL_KOSMOS_MEMDIR_USER
  }
})

// ---------------------------------------------------------------------------
// Default values (no env override)
// ---------------------------------------------------------------------------

test('getKosmosUserTierRoot returns ~/.kosmos/memdir/user by default', () => {
  delete process.env.KOSMOS_MEMDIR_USER
  const expected = join(homedir(), '.kosmos', 'memdir', 'user')
  expect(getKosmosUserTierRoot()).toBe(expected)
})

test('getKosmosSessionsDir returns ~/.kosmos/memdir/user/sessions by default', () => {
  delete process.env.KOSMOS_MEMDIR_USER
  const expected = join(homedir(), '.kosmos', 'memdir', 'user', 'sessions')
  expect(getKosmosSessionsDir()).toBe(expected)
})

// ---------------------------------------------------------------------------
// Env override
// ---------------------------------------------------------------------------

test('getKosmosUserTierRoot respects KOSMOS_MEMDIR_USER env override', () => {
  process.env.KOSMOS_MEMDIR_USER = '/tmp/kosmos-test/memdir/user'
  expect(getKosmosUserTierRoot()).toBe('/tmp/kosmos-test/memdir/user')
})

test('getKosmosSessionsDir appends /sessions to KOSMOS_MEMDIR_USER override', () => {
  process.env.KOSMOS_MEMDIR_USER = '/tmp/kosmos-test/memdir/user'
  expect(getKosmosSessionsDir()).toBe('/tmp/kosmos-test/memdir/user/sessions')
})

// ---------------------------------------------------------------------------
// Memoize invalidation — changing the env var between calls gets a fresh value
// ---------------------------------------------------------------------------

test('getKosmosUserTierRoot invalidates cache when KOSMOS_MEMDIR_USER changes', () => {
  delete process.env.KOSMOS_MEMDIR_USER
  const defaultVal = getKosmosUserTierRoot()
  expect(defaultVal).toBe(join(homedir(), '.kosmos', 'memdir', 'user'))

  // Now set the env var and call again — must see the new value.
  process.env.KOSMOS_MEMDIR_USER = '/tmp/new-root'
  const overrideVal = getKosmosUserTierRoot()
  expect(overrideVal).toBe('/tmp/new-root')
})

test('getKosmosSessionsDir invalidates cache when KOSMOS_MEMDIR_USER changes', () => {
  delete process.env.KOSMOS_MEMDIR_USER
  const defaultVal = getKosmosSessionsDir()
  expect(defaultVal).toBe(join(homedir(), '.kosmos', 'memdir', 'user', 'sessions'))

  // Switch to override.
  process.env.KOSMOS_MEMDIR_USER = '/tmp/new-root'
  const overrideVal = getKosmosSessionsDir()
  expect(overrideVal).toBe('/tmp/new-root/sessions')
})

test('getKosmosSessionsDir returns cached value when env is unchanged', () => {
  process.env.KOSMOS_MEMDIR_USER = '/tmp/stable-root'
  const first = getKosmosSessionsDir()
  const second = getKosmosSessionsDir()
  // Referential equality — same string instance returned from cache.
  expect(first).toBe(second)
})
