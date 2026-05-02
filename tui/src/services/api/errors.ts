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

// SWAP/anti-anthropic-1p(2521): byte-copied messages.ts imports this.
export function getImageTooLargeErrorMessage(..._args: unknown[]): string {
  return 'Image too large to process'
}

export function getPdfInvalidErrorMessage(..._args: unknown[]): string {
  return 'PDF invalid or unreadable'
}
export function getPdfPasswordProtectedErrorMessage(..._args: unknown[]): string {
  return 'PDF is password-protected'
}
export function getPdfTooLargeErrorMessage(..._args: unknown[]): string {
  return 'PDF too large to process'
}
export function getRequestTooLargeErrorMessage(..._args: unknown[]): string {
  return 'Request too large'
}
