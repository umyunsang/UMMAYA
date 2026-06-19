import { createHash } from 'node:crypto'
import { execa, execaSync } from 'execa'
import memoize from 'lodash-es/memoize.js'
import { normalizeApiKeyForConfig } from './authPortable.js'
import { getGlobalConfig, saveGlobalConfig } from './config.js'
import { getClaudeConfigHomeDir } from './envUtils.js'

export const FRIENDLI_PRIMARY_ENV = 'UMMAYA_FRIENDLI_TOKEN'
export const FRIENDLI_LOGIN_REQUIRED_MESSAGE =
  'Not logged in to FriendliAI. Run /login and paste a FriendliAI API key before sending a request.'

export type ApiKeySource =
  | typeof FRIENDLI_PRIMARY_ENV
  | 'ANTHROPIC_API_KEY'
  | 'apiKeyHelper'
  | '/login managed key'
  | 'none'

export type AuthTokenSource =
  | 'ANTHROPIC_AUTH_TOKEN'
  | 'CLAUDE_CODE_OAUTH_TOKEN'
  | 'apiKeyHelper'
  | 'claude.ai'
  | 'none'

function normalizeFriendliApiKey(apiKey: string): string {
  const trimmed = apiKey.trim()
  if (trimmed.length === 0) {
    throw new Error('FriendliAI API key must not be empty.')
  }
  if (/[\u0000-\u001f\u007f]/.test(trimmed)) {
    throw new Error('FriendliAI API key must be a single line.')
  }
  return trimmed
}

type FriendliKeychainIdentity = {
  readonly account: string
  readonly service: string
}

function getFriendliKeychainIdentity(): FriendliKeychainIdentity {
  const configHash = createHash('sha256')
    .update(getClaudeConfigHomeDir())
    .digest('hex')
    .substring(0, 16)
  return {
    account: `ummaya-friendli:${configHash}`,
    service: `UMMAYA FriendliAI API Key (${configHash})`,
  }
}

async function saveApiKeyToMacOSKeychain(apiKey: string): Promise<boolean> {
  if (process.platform !== 'darwin') {
    return false
  }
  const identity = getFriendliKeychainIdentity()
  const hexValue = Buffer.from(apiKey, 'utf-8').toString('hex')
  const command = `add-generic-password -U -a "${identity.account}" -s "${identity.service}" -X "${hexValue}"\n`
  try {
    const result = await execa('security', ['-i'], {
      input: command,
      reject: false,
    })
    return result.exitCode === 0
  } catch (error) {
    if (error instanceof Error) {
      return false
    }
    throw error
  }
}

function getApiKeyFromMacOSKeychain(): null | string {
  if (process.platform !== 'darwin') {
    return null
  }
  const identity = getFriendliKeychainIdentity()
  try {
    const result = execaSync(
      'security',
      [
        'find-generic-password',
        '-a',
        identity.account,
        '-w',
        '-s',
        identity.service,
      ],
      { reject: false, stdio: ['ignore', 'pipe', 'pipe'] },
    )
    const stdout = result.stdout.trim()
    return result.exitCode === 0 && stdout.length > 0 ? stdout : null
  } catch (error) {
    if (error instanceof Error) {
      return null
    }
    throw error
  }
}

async function removeApiKeyFromMacOSKeychain(): Promise<void> {
  if (process.platform !== 'darwin') {
    return
  }
  const identity = getFriendliKeychainIdentity()
  try {
    await execa(
      'security',
      ['delete-generic-password', '-a', identity.account, '-s', identity.service],
      { reject: false },
    )
  } catch (error) {
    if (error instanceof Error) {
      return
    }
    throw error
  }
}

export async function getClaudeAIOAuthTokens(): Promise<null> { return null }

export function isClaudeAISubscriber(): boolean { return false }

export function isConsumerSubscriber(): boolean { return false }

export function isMaxSubscriber(): boolean { return false }

export function isProSubscriber(): boolean { return false }

export function isTeamSubscriber(): boolean { return false }

export function isTeamPremiumSubscriber(): boolean { return false }

export function isEnterpriseSubscriber(): boolean { return false }

export function isAnthropicAuthEnabled(): boolean { return false }

export function isFriendliAuthEnabled(): boolean { return false }

export function is1PApiCustomer(): boolean { return false }

export function isUsing3PServices(): boolean { return false }

export function isOverageProvisioningAllowed(): boolean { return false }

export function hasProfileScope(): boolean { return false }

export function getAccountInformation(): null { return null }

export function getOauthAccountInfo(): null { return null }

export function getOauthOrgUUID(): null { return null }

export function getSubscriptionType(): 'free' { return 'free' }

export function getSubscriptionName(): string { return '' }

export function getAuthTokenSource(): {
  source: AuthTokenSource
  hasToken: boolean
} {
  return { source: 'none', hasToken: false }
}

export function getRateLimitTier(): 0 { return 0 }

export function getAnthropicApiKey(): null | string {
  return getAnthropicApiKeyWithSource().key
}

export function getFriendliApiKey(): null | string {
  return getAnthropicApiKeyWithSource().key
}

export function getAnthropicApiKeyWithSource(
  _opts: { skipRetrievingKeyFromApiKeyHelper?: boolean } = {},
): { key: null | string; source: ApiKeySource } {
  const envKey = process.env[FRIENDLI_PRIMARY_ENV]?.trim()
  if (envKey) {
    return { key: envKey, source: FRIENDLI_PRIMARY_ENV }
  }

  const saved = getApiKeyFromConfigOrMacOSKeychain()
  if (saved) {
    return { key: saved, source: '/login managed key' }
  }

  return { key: null, source: 'none' }
}

export function hasAnthropicApiKeyAuth(): boolean {
  return (
    getAnthropicApiKeyWithSource({
      skipRetrievingKeyFromApiKeyHelper: true,
    }).key !== null
  )
}

export async function saveApiKey(apiKey: string): Promise<void> {
  const normalized = normalizeFriendliApiKey(apiKey)
  process.env[FRIENDLI_PRIMARY_ENV] = normalized
  const savedToKeychain = await saveApiKeyToMacOSKeychain(normalized)
  saveGlobalConfig(current => {
    const truncated = normalizeApiKeyForConfig(normalized)
    const approved = current.customApiKeyResponses?.approved ?? []
    return {
      ...current,
      primaryApiKey: savedToKeychain ? undefined : normalized,
      customApiKeyResponses: {
        ...current.customApiKeyResponses,
        approved: approved.includes(truncated)
          ? approved
          : [...approved, truncated],
        rejected: current.customApiKeyResponses?.rejected ?? [],
      },
    }
  })
  getApiKeyFromConfigOrMacOSKeychain.cache?.clear?.()
}

export async function removeApiKey(): Promise<void> {
  delete process.env[FRIENDLI_PRIMARY_ENV]
  await removeApiKeyFromMacOSKeychain()
  saveGlobalConfig(current => ({
    ...current,
    primaryApiKey: undefined,
  }))
  getApiKeyFromConfigOrMacOSKeychain.cache?.clear?.()
}

export function getApiKeyFromApiKeyHelper(): null { return null }

export const getApiKeyFromConfigOrMacOSKeychain = memoize((): null | string => {
  const keychainKey = getApiKeyFromMacOSKeychain()
  if (keychainKey) {
    return keychainKey
  }

  const configKey = getGlobalConfig().primaryApiKey?.trim()
  return configKey && configKey.length > 0 ? configKey : null
})

export function getConfiguredApiKeyHelper(): null { return null }

export function getApiKeyHelperElapsedMs(): number { return 0 }

export async function checkAndRefreshOAuthTokenIfNeeded(): Promise<void> {}

export async function refreshAndGetAwsCredentials(): Promise<null> { return null }

export async function prefetchAwsCredentialsAndBedRockInfoIfSafe(): Promise<void> {}

export async function prefetchGcpCredentialsIfSafe(): Promise<void> {}

export async function prefetchApiKeyFromApiKeyHelperIfSafe(): Promise<void> {}

export function clearApiKeyHelperCache(): void {
  getApiKeyFromConfigOrMacOSKeychain.cache?.clear?.()
}

export function clearAwsCredentialsCache(): void {}

export function clearGcpCredentialsCache(): void {}

export function clearOAuthTokenCache(): void {}

export async function handleOAuth401Error(): Promise<void> {}

export async function saveOAuthTokensIfNeeded(): Promise<void> {}

export async function validateForceLoginOrg(): Promise<{ valid: true }> { return { valid: true } }

export function assertFriendliApiKeyForUse(
  env: Record<string, string | undefined> = process.env,
): string {
  const envKey = env[FRIENDLI_PRIMARY_ENV]?.trim()
  if (envKey) {
    return envKey
  }

  if (env === process.env) {
    const { key } = getAnthropicApiKeyWithSource()
    if (key) {
      env[FRIENDLI_PRIMARY_ENV] = key
      return key
    }
  }

  throw new Error(FRIENDLI_LOGIN_REQUIRED_MESSAGE)
}

export default {
  getClaudeAIOAuthTokens, isClaudeAISubscriber, isConsumerSubscriber, isMaxSubscriber, isProSubscriber, isTeamSubscriber, isTeamPremiumSubscriber, isEnterpriseSubscriber, isAnthropicAuthEnabled, is1PApiCustomer,
  isUsing3PServices, isOverageProvisioningAllowed, hasProfileScope, getAccountInformation, getOauthAccountInfo, getOauthOrgUUID, getSubscriptionType, getAuthTokenSource, getRateLimitTier,
  getAnthropicApiKey, getAnthropicApiKeyWithSource, hasAnthropicApiKeyAuth, saveApiKey, removeApiKey, getApiKeyFromApiKeyHelper, getApiKeyFromConfigOrMacOSKeychain, getConfiguredApiKeyHelper,
  getApiKeyHelperElapsedMs, checkAndRefreshOAuthTokenIfNeeded, refreshAndGetAwsCredentials, prefetchAwsCredentialsAndBedRockInfoIfSafe, prefetchGcpCredentialsIfSafe, prefetchApiKeyFromApiKeyHelperIfSafe,
  clearApiKeyHelperCache, clearAwsCredentialsCache, clearGcpCredentialsCache, clearOAuthTokenCache, handleOAuth401Error, saveOAuthTokensIfNeeded, validateForceLoginOrg, assertFriendliApiKeyForUse,
}
