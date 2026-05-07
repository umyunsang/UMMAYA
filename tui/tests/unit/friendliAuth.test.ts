// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — process-scoped FriendliAI auth helper tests.

import { describe, expect, it } from 'bun:test'
import {
  FRIENDLI_LOGIN_REQUIRED_MESSAGE,
  FRIENDLI_PRIMARY_ENV,
  FRIENDLI_SESSION_ENV,
  assertFriendliCredentialForUse,
  clearFriendliCredential,
  getFriendliCredentialSource,
  hasFriendliCredential,
  installFriendliCredential,
  normalizeFriendliApiKey,
} from '../../src/utils/friendliAuth.js'

describe('friendliAuth', () => {
  it('normalizes non-empty API keys and rejects blanks', () => {
    expect(normalizeFriendliApiKey('  key-123  ')).toBe('key-123')
    expect(() => normalizeFriendliApiKey('   ')).toThrow('must not be empty')
  })

  it('requires an active session before treating a key as usable', () => {
    expect(getFriendliCredentialSource({})).toBe('none')
    expect(getFriendliCredentialSource({ [FRIENDLI_PRIMARY_ENV]: 'primary' })).toBe('none')
    expect(
      getFriendliCredentialSource({
        [FRIENDLI_PRIMARY_ENV]: 'primary',
        [FRIENDLI_SESSION_ENV]: '1',
      }),
    ).toBe(FRIENDLI_PRIMARY_ENV)
  })

  it('installs and clears credentials only in the provided env object', () => {
    const env: Record<string, string | undefined> = {}
    installFriendliCredential('  session-token  ', env)
    expect(env[FRIENDLI_PRIMARY_ENV]).toBe('session-token')
    expect(env[FRIENDLI_SESSION_ENV]).toBe('1')
    expect(hasFriendliCredential(env)).toBe(true)

    clearFriendliCredential(env)
    expect(env[FRIENDLI_PRIMARY_ENV]).toBeUndefined()
    expect(env[FRIENDLI_SESSION_ENV]).toBeUndefined()
    expect(hasFriendliCredential(env)).toBe(false)
  })

  it('fails closed before model/backend use when not logged in', () => {
    expect(() => assertFriendliCredentialForUse({})).toThrow(FRIENDLI_LOGIN_REQUIRED_MESSAGE)
    expect(() => assertFriendliCredentialForUse({ [FRIENDLI_PRIMARY_ENV]: 'ok' })).toThrow(
      FRIENDLI_LOGIN_REQUIRED_MESSAGE,
    )
    expect(() =>
      assertFriendliCredentialForUse({
        [FRIENDLI_PRIMARY_ENV]: 'ok',
        [FRIENDLI_SESSION_ENV]: '1',
      }),
    ).not.toThrow()
  })
})
