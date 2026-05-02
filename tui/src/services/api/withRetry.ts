// SPDX-License-Identifier: Apache-2.0
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/claude.ts which references CC's 529-overload retry harness.
// KOSMOS handles backpressure via stdio IPC backpressure signals (Spec 032);
// this Anthropic-API-specific retry layer is unused. Stubs preserve the
// import shape — the byte-copy has zero callers in KOSMOS so the retry
// helper invokes the wrapped function once and forwards its result.

export class CannotRetryError extends Error {}
export class FallbackTriggeredError extends Error {}

export function is529Error(_err: unknown): boolean {
  return false
}

export type RetryContext = {
  attempt?: number
  maxAttempts?: number
  delayMs?: number
  // CC's RetryContext exposes additional telemetry fields; the byte-copied
  // claude.ts reads `model` off the context inside the streaming dispatcher.
  model?: string
}

export async function withRetry<T>(
  fn: (_ctx: RetryContext) => Promise<T>,
  _opts?: unknown,
): Promise<T> {
  return fn({ attempt: 1, maxAttempts: 1, delayMs: 0 })
}
