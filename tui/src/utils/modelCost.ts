// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Spec 2521 byte-copy bridge stub (no live caller in KOSMOS).
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/claude.ts which references CC's USD-cost calculator for
// Anthropic API pricing. KOSMOS tracks usage via FriendliAI usage_tracker
// (Spec 022). Stub returns 0 — the byte-copy has zero callers in KOSMOS so
// no live cost-display surface depends on this module.

export function calculateUSDCost(..._args: unknown[]): number {
  return 0
}
