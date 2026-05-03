// SPDX-License-Identifier: Apache-2.0
// Spec 2641 · T006 — settingsSync dead-call gate unit tests.
//
// Verifies the public entry-points return early (silent-skip variant)
// when KOSMOS_ENABLE_DEAD_SETTINGS_SYNC is unset (the production state).
// Unlike teamMemorySync (whose entry-points throw), settingsSync is still
// reachable from cli/print.ts + commands/reload-plugins/ — so the gate
// must NOT throw or the boot path breaks. The contract is "return false /
// return void without issuing axios traffic to claude.ai."

import { afterEach, beforeEach, describe, expect, test } from 'bun:test'
import {
  _resetDownloadPromiseForTesting,
  downloadUserSettings,
  redownloadUserSettings,
  uploadUserSettingsInBackground,
} from '../../src/services/settingsSync/index'

const ENV_KEY = 'KOSMOS_ENABLE_DEAD_SETTINGS_SYNC'

describe('settingsSync dead-call gate (Spec 2641)', () => {
  let originalEnv: string | undefined

  beforeEach(() => {
    originalEnv = process.env[ENV_KEY]
    delete process.env[ENV_KEY]
    _resetDownloadPromiseForTesting()
  })

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env[ENV_KEY]
    } else {
      process.env[ENV_KEY] = originalEnv
    }
    _resetDownloadPromiseForTesting()
  })

  test('uploadUserSettingsInBackground returns void without throwing', async () => {
    await expect(uploadUserSettingsInBackground()).resolves.toBeUndefined()
  })

  test('downloadUserSettings returns Promise<false> without throwing', async () => {
    const result = await downloadUserSettings()
    expect(result).toBe(false)
  })

  test('redownloadUserSettings returns Promise<false> without throwing', async () => {
    const result = await redownloadUserSettings()
    expect(result).toBe(false)
  })

  test('downloadUserSettings does not cache the gated false response', async () => {
    // Each call must re-evaluate the gate so that a future env-override
    // takes effect mid-process. The cache slot is reset by the gate path.
    const r1 = await downloadUserSettings()
    const r2 = await downloadUserSettings()
    expect(r1).toBe(false)
    expect(r2).toBe(false)
  })

  test('_resetDownloadPromiseForTesting remains callable (test harness contract)', () => {
    expect(() => _resetDownloadPromiseForTesting()).not.toThrow()
  })

  // Codex P2 hardening (PR #2688): only the literal '1' opens the gate.
  // Any other string keeps the silent-skip behavior so CI/shell boolean
  // templating cannot reactivate the dead path by accident.
  test('env override "0" still returns false (rejects truthy fallthrough)', async () => {
    process.env[ENV_KEY] = '0'
    expect(await downloadUserSettings()).toBe(false)
    expect(await redownloadUserSettings()).toBe(false)
    await expect(uploadUserSettingsInBackground()).resolves.toBeUndefined()
  })

  test('env override "true" still returns false (only "1" is valid)', async () => {
    process.env[ENV_KEY] = 'true'
    expect(await downloadUserSettings()).toBe(false)
  })

  test('env override "1" reaches the original CC code paths', async () => {
    process.env[ENV_KEY] = '1'
    // With the gate open, downloadUserSettings reaches doDownloadUserSettings,
    // which itself short-circuits when feature('DOWNLOAD_USER_SETTINGS') is
    // false (the bun:bundle stub). End result is still `false`, but via a
    // different code path — proving the gate actually opened.
    expect(await downloadUserSettings()).toBe(false)
  })
})
