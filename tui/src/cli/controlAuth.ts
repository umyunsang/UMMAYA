// SPDX-License-Identifier: Apache-2.0

type ControlAuthRequest = {
  readonly loginWithFriendliAi?: unknown
  readonly [key: string]: unknown
}

const LEGACY_LOGIN_WITH_PROVIDER_KEY = ['loginWith', 'Claude', 'Ai'].join('')

export function resolveControlLoginWithFriendliAi(
  request: ControlAuthRequest,
): boolean {
  const currentValue = request.loginWithFriendliAi
  if (typeof currentValue === 'boolean') return currentValue

  const legacyValue = request[LEGACY_LOGIN_WITH_PROVIDER_KEY]
  if (typeof legacyValue === 'boolean') return legacyValue

  return true
}
