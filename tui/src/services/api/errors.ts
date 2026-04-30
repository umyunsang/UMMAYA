// SPDX-License-Identifier: Apache-2.0
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/claude.ts which references CC's Anthropic-API error envelopes.
// KOSMOS surfaces errors via the IPC ErrorFrame (Spec 032) and never reaches
// these helpers. Stubs preserve the import shape only.

export const API_ERROR_MESSAGE_PREFIX = 'API Error'
export const CUSTOM_OFF_SWITCH_MESSAGE = 'Custom off-switch enabled'

export function getAssistantMessageFromError(_err: unknown): unknown {
  return null
}

export function getErrorMessageIfRefusal(_err: unknown): string | null {
  return null
}
