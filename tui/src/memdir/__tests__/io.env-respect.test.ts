// SPDX-License-Identifier: Apache-2.0
// P0-3 regression test — memdir env-override respect.
//
// Verifies that `writeConsentRecord` and `writeScopeRecord` write to the path
// derived from `KOSMOS_MEMDIR_USER` (and `KOSMOS_MEMDIR_ROOT`) rather than
// the module-load constant `~/.kosmos/memdir/`.
//
// Because `getDefaultUserTierRoot()` reads `process.env` at call-time (no
// module-level cache), we can mutate the env before each test and observe the
// correct path without dynamic re-imports.
//
// Layer 1a (bun:test — filesystem write into a temp directory, no PTY).

import { afterEach, beforeEach, describe, expect, it } from 'bun:test'
import { mkdirSync, readdirSync, rmSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'

// Top-level imports are resolved once — the functions read process.env at
// call-time so env mutations are visible without module cache invalidation.
import {
  writeConsentRecord,
  writeScopeRecord,
  consentDir,
  scopeDir,
  getDefaultUserTierRoot,
} from '../io.js'
import type { PIPAConsentRecord } from '../consent.js'
import type { MinistryScopeAcknowledgment } from '../ministry-scope.js'

// ---------------------------------------------------------------------------
// Env-var save / restore
// ---------------------------------------------------------------------------

const ORIG_KOSMOS_MEMDIR_USER = process.env['KOSMOS_MEMDIR_USER']
const ORIG_KOSMOS_MEMDIR_ROOT = process.env['KOSMOS_MEMDIR_ROOT']

let testDir: string

beforeEach(() => {
  // Fresh isolated tmp directory per test.
  testDir = join(require('node:os').tmpdir(), `kosmos-io-env-test-${randomUUID()}`)
  mkdirSync(testDir, { recursive: true })

  // Clear both env vars so tests start from a clean state.
  delete process.env['KOSMOS_MEMDIR_USER']
  delete process.env['KOSMOS_MEMDIR_ROOT']
})

afterEach(() => {
  // Restore original env state to avoid cross-test pollution.
  if (ORIG_KOSMOS_MEMDIR_USER === undefined) {
    delete process.env['KOSMOS_MEMDIR_USER']
  } else {
    process.env['KOSMOS_MEMDIR_USER'] = ORIG_KOSMOS_MEMDIR_USER
  }
  if (ORIG_KOSMOS_MEMDIR_ROOT === undefined) {
    delete process.env['KOSMOS_MEMDIR_ROOT']
  } else {
    process.env['KOSMOS_MEMDIR_ROOT'] = ORIG_KOSMOS_MEMDIR_ROOT
  }

  // Remove the temp directory.
  try {
    rmSync(testDir, { recursive: true, force: true })
  } catch {
    // Non-fatal — OS cleanup will handle it.
  }
})

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeConsentRecord(sessionId: string): PIPAConsentRecord {
  return {
    consent_version: 'v1',
    timestamp: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    aal_gate: 'AAL1',
    session_id: sessionId,
    citizen_confirmed: true,
    schema_version: '1',
  }
}

function makeScopeRecord(sessionId: string): MinistryScopeAcknowledgment {
  return {
    scope_version: 'v1',
    timestamp: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    session_id: sessionId,
    ministries: [
      { ministry_code: 'KOROAD', opt_in: true },
      { ministry_code: 'KMA', opt_in: true },
      { ministry_code: 'HIRA', opt_in: false },
      { ministry_code: 'NMC', opt_in: false },
    ],
    schema_version: '1',
  }
}

// ---------------------------------------------------------------------------
// P0-3: Default path (no env override)
// ---------------------------------------------------------------------------

describe('P0-3 — default path when no env override', () => {
  it('getDefaultUserTierRoot returns ~/.kosmos/memdir/user when no env override', () => {
    delete process.env['KOSMOS_MEMDIR_USER']
    delete process.env['KOSMOS_MEMDIR_ROOT']

    const expected = join(homedir(), '.kosmos', 'memdir', 'user')
    expect(getDefaultUserTierRoot()).toBe(expected)
  })
})

// ---------------------------------------------------------------------------
// P0-3: KOSMOS_MEMDIR_USER override
// ---------------------------------------------------------------------------

describe('P0-3 — KOSMOS_MEMDIR_USER env override', () => {
  it('getDefaultUserTierRoot returns KOSMOS_MEMDIR_USER value', () => {
    const userTierRoot = join(testDir, 'user-tier')
    process.env['KOSMOS_MEMDIR_USER'] = userTierRoot

    expect(getDefaultUserTierRoot()).toBe(userTierRoot)
  })

  it('writeConsentRecord writes to $KOSMOS_MEMDIR_USER/consent/', () => {
    const userTierRoot = join(testDir, 'user-tier')
    process.env['KOSMOS_MEMDIR_USER'] = userTierRoot

    // writeConsentRecord() with no second arg uses getDefaultUserTierRoot()
    // which now reads KOSMOS_MEMDIR_USER at call time.
    const sessionId = randomUUID()
    const writtenPath = writeConsentRecord(makeConsentRecord(sessionId))

    // Verify the file landed under $KOSMOS_MEMDIR_USER/consent/.
    const expectedConsentDir = consentDir(userTierRoot)
    expect(writtenPath.startsWith(expectedConsentDir)).toBe(true)

    // Confirm at least one .json file exists in the consent directory.
    const files = readdirSync(expectedConsentDir).filter(f => f.endsWith('.json'))
    expect(files.length).toBeGreaterThanOrEqual(1)
  })

  it('writeScopeRecord writes to $KOSMOS_MEMDIR_USER/ministry-scope/', () => {
    const userTierRoot = join(testDir, 'user-tier')
    process.env['KOSMOS_MEMDIR_USER'] = userTierRoot

    const sessionId = randomUUID()
    const writtenPath = writeScopeRecord(makeScopeRecord(sessionId))

    const expectedScopeDir = scopeDir(userTierRoot)
    expect(writtenPath.startsWith(expectedScopeDir)).toBe(true)

    const files = readdirSync(expectedScopeDir).filter(f => f.endsWith('.json'))
    expect(files.length).toBeGreaterThanOrEqual(1)
  })

  it('does NOT write to the real ~/.kosmos/memdir/ when KOSMOS_MEMDIR_USER is set', () => {
    const userTierRoot = join(testDir, 'user-tier')
    process.env['KOSMOS_MEMDIR_USER'] = userTierRoot

    const sessionId = randomUUID()
    const writtenPath = writeConsentRecord(makeConsentRecord(sessionId))

    // The real home directory path must not appear in the written path.
    const realRoot = join(homedir(), '.kosmos', 'memdir')
    expect(writtenPath.startsWith(realRoot)).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// P0-3: KOSMOS_MEMDIR_ROOT fallback (no KOSMOS_MEMDIR_USER)
// ---------------------------------------------------------------------------

describe('P0-3 — KOSMOS_MEMDIR_ROOT fallback', () => {
  it('getDefaultUserTierRoot appends /user to KOSMOS_MEMDIR_ROOT', () => {
    delete process.env['KOSMOS_MEMDIR_USER']
    const memdirRoot = join(testDir, 'memdir-root')
    process.env['KOSMOS_MEMDIR_ROOT'] = memdirRoot

    expect(getDefaultUserTierRoot()).toBe(join(memdirRoot, 'user'))
  })

  it('writeConsentRecord goes into $KOSMOS_MEMDIR_ROOT/user/consent/', () => {
    delete process.env['KOSMOS_MEMDIR_USER']
    const memdirRoot = join(testDir, 'memdir-root')
    process.env['KOSMOS_MEMDIR_ROOT'] = memdirRoot

    const sessionId = randomUUID()
    const writtenPath = writeConsentRecord(makeConsentRecord(sessionId))

    const expectedUserTierRoot = join(memdirRoot, 'user')
    const expectedConsentDir = consentDir(expectedUserTierRoot)
    expect(writtenPath.startsWith(expectedConsentDir)).toBe(true)
  })
})
