// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #1633 stub restoration · Epic #2077 surface preservation.
// Research use — adapted from Claude Code 2.1.88 src/services/claudeAiLimits.ts
// permissive no-op for CC compatibility. KOSMOS has no claude.ai subscription
// quota; adapter-layer rate limiting is enforced by Spec 022 `usage_tracker`
// and the per-API `KOSMOS_*` env vars. Type aliases remain so the
// `rateLimitMessages.ts` and `mockRateLimits.ts` consumers compile.

export type ClaudeAILimits = {
  readonly tier?: string
  readonly resetAtSeconds?: number
  readonly remaining?: number
  readonly [extraField: string]: unknown
}

export type OverageDisabledReason =
  | 'kosmos_no_overage'
  | 'unknown'
  | string

// SWAP/anti-anthropic-1p(2521): the byte-copied tui/src/services/api/claude.ts
// imports `currentLimits` + `extractQuotaStatusFromError` + `extractQuotaStatusFromHeaders`
// from this module (CC 2.1.88 surface). KOSMOS deleted the live quota-tracker
// in Spec 1633 P1+P2; these inert exports preserve ESM link-time resolvability
// so Bun's `linkAndEvaluateModule` doesn't throw "Export named ... not found"
// at boot when claude.ts enters the import graph (via awaySummary.ts →
// queryModelWithoutStreaming). Values are zero/empty — claude.ts's quota gates
// fall through to the not-overage branch which the GrowthBook allowlist
// already keeps passable for KOSMOS's FriendliAI single provider.
export const currentLimits: { isUsingOverage: boolean } = {
  isUsingOverage: false,
}

export function extractQuotaStatusFromError(_err: unknown): null {
  return null
}

export function extractQuotaStatusFromHeaders(_headers: unknown): null {
  return null
}
