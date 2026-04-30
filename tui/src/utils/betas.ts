// SPDX-License-Identifier: Apache-2.0
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/claude.ts which expects the CC 2.1.88 utils/betas.ts surface.
// CC's betas.ts gates Anthropic-1P beta-API headers (AFK mode, 1M context,
// thinking signature, etc.) — none of which apply to KOSMOS's FriendliAI
// single provider. All getters return empty so byte-copied claude.ts compiles
// and any beta-header gating in its dead-code path is a no-op at runtime.

export function getBedrockExtraBodyParamsBetas(
  ..._args: unknown[]
): Record<string, unknown> {
  return {}
}

export function getMergedBetas(..._args: unknown[]): string[] {
  return []
}

export function getModelBetas(..._args: unknown[]): string[] {
  return []
}

export function shouldIncludeFirstPartyOnlyBetas(): boolean {
  return false
}

// Additional named exports the byte-copied claude.ts imports from this module.
// All return inert defaults — KOSMOS doesn't gate any of these at runtime
// (the byte-copied claude.ts has zero callers, so these stubs only need to
// exist for ESM link-time resolvability).
export function getToolSearchBetaHeader(..._args: unknown[]): string | null {
  return null
}

export function modelSupportsStructuredOutputs(_model?: string): boolean {
  return false
}

export function shouldUseGlobalCacheScope(..._args: unknown[]): boolean {
  return false
}
