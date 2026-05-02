// SPDX-License-Identifier: Apache-2.0
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/claude.ts which references CC's Anthropic-API request/response
// telemetry. KOSMOS uses OTEL spans (Spec 021) and audit ledger (Spec 024)
// instead. Stubs preserve the import shape; functions are no-ops because the
// byte-copy has zero callers in KOSMOS.

export const EMPTY_USAGE = {
  input_tokens: 0,
  cache_creation_input_tokens: 0,
  cache_read_input_tokens: 0,
  output_tokens: 0,
}

export type GlobalCacheStrategy = 'none' | 'ephemeral' | 'persistent'

export type NonNullableUsage = NonNullable<typeof EMPTY_USAGE>

export function logAPIError(..._args: unknown[]): void {}
export function logAPIQuery(..._args: unknown[]): void {}
export function logAPISuccessAndDuration(..._args: unknown[]): void {}
