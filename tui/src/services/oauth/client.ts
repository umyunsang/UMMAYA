// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1633 P2 · stub-noop replacement for CC OAuth client.
//
// The original Anthropic OAuth client (authorization-code flow, PKCE, token
// exchange) has been removed. KOSMOS does not ship an OAuth surface in the
// TUI — authentication is the process-scoped FriendliAI /login session,
// exported as `KOSMOS_FRIENDLI_TOKEN` only for the Python backend.

/**
 * Returns the organization UUID for the current OAuth session. KOSMOS has
 * no OAuth surface — always null.
 */
export function getOrganizationUUID(): string | null {
  return null
}

/**
 * Returns the user UUID for the current OAuth session. KOSMOS has no OAuth
 * surface — always null.
 */
export function getUserUUID(): string | null {
  return null
}

/**
 * Returns the active OAuth access token. KOSMOS has no OAuth surface —
 * always null.
 */
export function getAccessToken(): string | null {
  return null
}

/**
 * Refreshes the OAuth access token. KOSMOS has no OAuth surface — no-op.
 */
export async function refreshAccessToken(): Promise<null> {
  return null
}

/**
 * Revokes the OAuth access token. KOSMOS has no OAuth surface — no-op.
 */
export async function revokeAccessToken(): Promise<void> {
  // Intentional no-op.
}

export async function createAndStoreApiKey(): Promise<null> {
  return null
}

export async function fetchAndStoreUserRoles(): Promise<void> {
  /* no-op */
}

export async function populateOAuthAccountInfoIfNeeded(): Promise<void> {
  /* no-op */
}

export async function refreshOAuthToken(): Promise<null> {
  return null
}

export function shouldUseClaudeAIAuth(): boolean {
  return false
}

export async function storeOAuthAccountInfo(): Promise<void> {
  /* no-op */
}

export default {
  getOrganizationUUID,
  getUserUUID,
  getAccessToken,
  refreshAccessToken,
  revokeAccessToken,
  createAndStoreApiKey,
  fetchAndStoreUserRoles,
  populateOAuthAccountInfoIfNeeded,
  refreshOAuthToken,
  shouldUseClaudeAIAuth,
  storeOAuthAccountInfo,
}
