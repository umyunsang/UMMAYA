// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'bun:test'
import { resolveControlLoginWithFriendliAi } from '../../src/cli/controlAuth.js'

describe('control-channel auth compatibility', () => {
  it('prefers the UMMAYA auth field when present', () => {
    expect(
      resolveControlLoginWithFriendliAi({
        loginWithFriendliAi: false,
        loginWithClaudeAi: true,
      }),
    ).toBe(false)
  })

  it('honors the legacy auth field from older control clients', () => {
    expect(
      resolveControlLoginWithFriendliAi({ loginWithClaudeAi: false }),
    ).toBe(false)
  })

  it('defaults to managed account auth for omitted or malformed values', () => {
    expect(resolveControlLoginWithFriendliAi({})).toBe(true)
    expect(
      resolveControlLoginWithFriendliAi({ loginWithFriendliAi: 'false' }),
    ).toBe(true)
    expect(
      resolveControlLoginWithFriendliAi({ loginWithClaudeAi: 'false' }),
    ).toBe(true)
  })
})
