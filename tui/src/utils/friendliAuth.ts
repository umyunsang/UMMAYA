// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — process-scoped FriendliAI API-key auth.
//
// Mirrors Claude Code's login/logout lifecycle shape, but KOSMOS does not use
// OAuth, keychain, or config-file persistence. A /login token lives only in the
// current TUI process environment and is inherited by the lazily spawned Python
// backend. /logout clears the process env and closes that backend.

export const FRIENDLI_PRIMARY_ENV = 'KOSMOS_FRIENDLI_TOKEN'
export const FRIENDLI_SESSION_ENV = 'KOSMOS_FRIENDLI_SESSION_ACTIVE'

export type FriendliCredentialSource =
  | typeof FRIENDLI_PRIMARY_ENV
  | 'none'

export const FRIENDLI_LOGIN_REQUIRED_MESSAGE =
  'Not logged in to FriendliAI. Run /login and paste a FriendliAI API key before sending a request.'

export function normalizeFriendliApiKey(value: string): string {
  const trimmed = value.trim()
  if (trimmed.length === 0) {
    throw new Error('FriendliAI API key must not be empty.')
  }
  return trimmed
}

export function getFriendliCredentialSource(
  env: Record<string, string | undefined> = process.env,
): FriendliCredentialSource {
  if (env[FRIENDLI_SESSION_ENV] !== '1') {
    return 'none'
  }

  const primary = env[FRIENDLI_PRIMARY_ENV]
  if (primary && primary.trim().length > 0) {
    return FRIENDLI_PRIMARY_ENV
  }

  return 'none'
}

export function hasFriendliCredential(
  env: Record<string, string | undefined> = process.env,
): boolean {
  return getFriendliCredentialSource(env) !== 'none'
}

export function installFriendliCredential(
  apiKey: string,
  env: Record<string, string | undefined> = process.env,
): void {
  const normalized = normalizeFriendliApiKey(apiKey)
  env[FRIENDLI_PRIMARY_ENV] = normalized
  env[FRIENDLI_SESSION_ENV] = '1'
}

export function clearFriendliCredential(
  env: Record<string, string | undefined> = process.env,
): void {
  delete env[FRIENDLI_PRIMARY_ENV]
  delete env[FRIENDLI_SESSION_ENV]
}

export function assertFriendliCredentialForUse(
  env: Record<string, string | undefined> = process.env,
): void {
  if (!hasFriendliCredential(env)) {
    throw new Error(FRIENDLI_LOGIN_REQUIRED_MESSAGE)
  }
}
