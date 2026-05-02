// SPDX-License-Identifier: Apache-2.0
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/claude.ts which references CC's Anthropic prompt-cache-break
// detection (1h TTL gating + cache-prefix invalidation tracking). KOSMOS
// runs FriendliAI's prompt cache via different headers (Spec 026 manifest
// SHA), so this CC helper is irrelevant. Stubs preserve the import shape.

export const CACHE_TTL_1HOUR_MS = 60 * 60 * 1000

export function checkResponseForCacheBreak(..._args: unknown[]): void {}
export function recordPromptState(..._args: unknown[]): void {}
