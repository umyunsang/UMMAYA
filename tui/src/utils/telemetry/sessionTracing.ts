// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Spec 2521 byte-copy bridge stub (no live caller in KOSMOS).
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/claude.ts which references CC's per-request telemetry-tracing
// span helpers. KOSMOS uses Spec 021 OTEL spans emitted from llmClient.ts
// directly, not from this code path. Stub returns inert no-ops; the byte-copy
// has zero callers in KOSMOS so no live tracing surface depends on this file.

export function isBetaTracingEnabled(): boolean {
  return false
}

export type LLMRequestNewContext = Record<string, unknown>

export function startLLMRequestSpan(..._args: unknown[]): {
  setAttribute: (..._a: unknown[]) => void
  end: () => void
} {
  return {
    setAttribute: () => {},
    end: () => {},
  }
}
