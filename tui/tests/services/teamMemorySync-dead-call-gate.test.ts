// SPDX-License-Identifier: Apache-2.0
// Spec 2641 · T004 — teamMemorySync dead-call gate unit tests.
//
// Verifies the four public entry-points throw when the
// KOSMOS_ENABLE_DEAD_TEAM_MEM_SYNC env override is unset (the production
// state). This enforces, at unit-test time, that no axios call to
// claude.ai's `/api/claude_code/team_memory` endpoint can ever leave a
// KOSMOS process unintentionally — defense-in-depth atop the
// `feature('TEAMMEM')=false` gate at tui/src/setup.ts:358.

import { afterEach, beforeEach, describe, expect, test } from 'bun:test'
import {
  createSyncState,
  hashContent,
  isTeamMemorySyncAvailable,
  pullTeamMemory,
  pushTeamMemory,
  syncTeamMemory,
} from '../../src/services/teamMemorySync/index'

const ENV_KEY = 'KOSMOS_ENABLE_DEAD_TEAM_MEM_SYNC'

describe('teamMemorySync dead-call gate (Spec 2641)', () => {
  let originalEnv: string | undefined

  beforeEach(() => {
    originalEnv = process.env[ENV_KEY]
    delete process.env[ENV_KEY]
  })

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env[ENV_KEY]
    } else {
      process.env[ENV_KEY] = originalEnv
    }
  })

  test('isTeamMemorySyncAvailable throws without env override', () => {
    expect(() => isTeamMemorySyncAvailable()).toThrow(
      /isTeamMemorySyncAvailable: dead in KOSMOS/,
    )
  })

  test('pullTeamMemory throws without env override', async () => {
    const state = createSyncState()
    await expect(pullTeamMemory(state)).rejects.toThrow(
      /pullTeamMemory: dead in KOSMOS/,
    )
  })

  test('pushTeamMemory throws without env override', async () => {
    const state = createSyncState()
    await expect(pushTeamMemory(state)).rejects.toThrow(
      /pushTeamMemory: dead in KOSMOS/,
    )
  })

  test('syncTeamMemory throws without env override', async () => {
    const state = createSyncState()
    await expect(syncTeamMemory(state)).rejects.toThrow(
      /syncTeamMemory: dead in KOSMOS/,
    )
  })

  test('pure helpers (createSyncState, hashContent) remain callable', () => {
    const state = createSyncState()
    expect(state.lastKnownChecksum).toBeNull()
    expect(state.serverChecksums.size).toBe(0)
    expect(state.serverMaxEntries).toBeNull()

    const hash = hashContent('hello kosmos')
    expect(hash).toMatch(/^sha256:[0-9a-f]{64}$/)
  })

  test('env override unblocks the gate (escape hatch for audit replay)', async () => {
    process.env[ENV_KEY] = '1'
    // With the gate disabled, isTeamMemorySyncAvailable should return false
    // (no OAuth tokens) rather than throw the dead-call error.
    expect(() => isTeamMemorySyncAvailable()).not.toThrow(
      /dead in KOSMOS/,
    )
  })

  // Codex P2 hardening (PR #2688): only the literal '1' opens the gate.
  // Any other truthy-looking string (`0`, `false`, `yes`, ...) MUST keep
  // the gate closed so CI/shell boolean templating cannot reactivate the
  // dead path by accident.
  test('env override "0" keeps the gate closed (rejects truthy fallthrough)', () => {
    process.env[ENV_KEY] = '0'
    expect(() => isTeamMemorySyncAvailable()).toThrow(/dead in KOSMOS/)
  })

  test('env override "false" keeps the gate closed', () => {
    process.env[ENV_KEY] = 'false'
    expect(() => isTeamMemorySyncAvailable()).toThrow(/dead in KOSMOS/)
  })

  test('env override "true" keeps the gate closed (only "1" is valid)', () => {
    process.env[ENV_KEY] = 'true'
    expect(() => isTeamMemorySyncAvailable()).toThrow(/dead in KOSMOS/)
  })
})
