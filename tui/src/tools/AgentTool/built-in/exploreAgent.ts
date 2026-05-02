// SPDX-License-Identifier: Apache-2.0
// SWAP/anti-anthropic-1p(2521): byte-copied tui/src/utils/messages.ts imports
// EXPLORE_AGENT from this module (CC built-in subagent for read-only codebase
// exploration). KOSMOS does not ship subagent registry yet; stub returns inert
// metadata so messages.ts ESM link succeeds. The subagent surface is not
// reached at runtime in KOSMOS (no caller).
export const EXPLORE_AGENT = {
  agentType: 'explore' as const,
  description: 'Read-only codebase exploration subagent (CC parity stub)',
}
