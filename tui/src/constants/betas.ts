// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Spec 2521 byte-copy bridge stub (no live caller in KOSMOS).
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/claude.ts which references CC's beta-header constant set.
// All headers are inert string constants — KOSMOS sends none of them to
// FriendliAI; they exist only so byte-copied claude.ts compiles.

export const ADVISOR_BETA_HEADER = 'advisor-2025-04-01'
export const AFK_MODE_BETA_HEADER = 'afk-2025-08-01'
export const CONTEXT_1M_BETA_HEADER = 'context-1m-2025-08-07'
export const CONTEXT_MANAGEMENT_BETA_HEADER = 'context-management-2025-06-27'
export const EFFORT_BETA_HEADER = 'interleaved-thinking-2025-05-14'
export const FAST_MODE_BETA_HEADER = 'fast-mode-2025-04-01'
export const PROMPT_CACHING_SCOPE_BETA_HEADER = 'prompt-caching-2024-07-31'
export const REDACT_THINKING_BETA_HEADER = 'redact-thinking-2025-05-14'
export const STRUCTURED_OUTPUTS_BETA_HEADER = 'structured-outputs-2025-04-01'
export const TASK_BUDGETS_BETA_HEADER = 'task-budgets-2026-03-13'
