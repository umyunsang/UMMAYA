// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — FriendliAI boot warning guard tests.

import { describe, expect, it, mock } from 'bun:test'
import {
  ENV_GUARD_MESSAGE,
  enforceFriendliCredential,
  hasFriendliCredential,
  warnIfMissingFriendliCredential,
} from '../../src/entrypoints/envGuard.js'

describe('envGuard', () => {
  it('requires the TUI login session marker', () => {
    expect(hasFriendliCredential({})).toBe(false)
    expect(hasFriendliCredential({ KOSMOS_FRIENDLI_TOKEN: 'primary' })).toBe(false)
    expect(
      hasFriendliCredential({
        KOSMOS_FRIENDLI_TOKEN: 'primary',
        KOSMOS_FRIENDLI_SESSION_ACTIVE: '1',
      }),
    ).toBe(true)
  })

  it('warns without exiting when credential is missing', () => {
    const writeError = mock(() => {})
    warnIfMissingFriendliCredential({}, { writeError })
    expect(writeError).toHaveBeenCalledWith(ENV_GUARD_MESSAGE)
  })

  it('keeps enforceFriendliCredential as a non-exiting compatibility wrapper', () => {
    const writeError = mock(() => {})
    const exit = mock((code: number) => {
      throw new Error(`unexpected exit ${code}`)
    })

    enforceFriendliCredential({}, { writeError, exit })
    expect(writeError).toHaveBeenCalledWith(ENV_GUARD_MESSAGE)
    expect(exit).not.toHaveBeenCalled()
  })
})
