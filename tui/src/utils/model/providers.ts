import type { AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS } from '../../services/analytics/index.js'
import { isEnvTruthy } from '../envUtils.js'

export type APIProvider = 'firstParty' | 'bedrock' | 'vertex' | 'foundry'

export function getAPIProvider(): APIProvider {
  return isEnvTruthy(process.env.CLAUDE_CODE_USE_BEDROCK)
    ? 'bedrock'
    : isEnvTruthy(process.env.CLAUDE_CODE_USE_VERTEX)
      ? 'vertex'
      : isEnvTruthy(process.env.CLAUDE_CODE_USE_FOUNDRY)
        ? 'foundry'
        : 'firstParty'
}

export function getAPIProviderForStatsig(): AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS {
  return getAPIProvider() as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
}

/** Check if ANTHROPIC_BASE_URL points to an operator-approved first-party API. */
export function isFirstPartyAnthropicBaseUrl(): boolean {
  const baseUrl = process.env.ANTHROPIC_BASE_URL
  if (!baseUrl) {
    return false
  }
  try {
    const host = new URL(baseUrl).host
    const allowedHosts = (process.env.UMMAYA_FIRST_PARTY_API_HOSTS ?? '')
      .split(',')
      .map(value => value.trim())
      .filter(Boolean)
    return allowedHosts.includes(host)
  } catch {
    return false
  }
}
