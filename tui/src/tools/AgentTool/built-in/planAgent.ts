// SPDX-License-Identifier: Apache-2.0
// SWAP/anti-anthropic-1p(2521): byte-copied tui/src/utils/messages.ts imports
// PLAN_AGENT from this module (CC built-in subagent for plan composition).
// Stub mirrors EXPLORE_AGENT pattern.
export const PLAN_AGENT = {
  agentType: 'plan' as const,
  description: 'Planning subagent (CC parity stub)',
}
