// SPDX-License-Identifier: Apache-2.0
// SWAP/anti-anthropic-1p(2521): minimal stub for the byte-copied
// services/api/ummaya.ts which references CC's Anthropic-API error envelopes.
// UMMAYA surfaces errors via the IPC ErrorFrame (Spec 032) and never reaches
// these helpers. Stubs preserve the import shape only.

import { randomUUID } from 'crypto'

export const API_ERROR_MESSAGE_PREFIX = 'API Error'
export const API_TIMEOUT_ERROR_MESSAGE = `${API_ERROR_MESSAGE_PREFIX}: request timed out`
export const CREDIT_BALANCE_TOO_LOW_ERROR_MESSAGE = `${API_ERROR_MESSAGE_PREFIX}: credit balance too low`
export const CUSTOM_OFF_SWITCH_MESSAGE = 'Custom off-switch enabled'
export const INVALID_API_KEY_ERROR_MESSAGE = `${API_ERROR_MESSAGE_PREFIX}: invalid API key`
export const INVALID_API_KEY_ERROR_MESSAGE_EXTERNAL = INVALID_API_KEY_ERROR_MESSAGE
export const ORG_DISABLED_ERROR_MESSAGE_ENV_KEY = `${API_ERROR_MESSAGE_PREFIX}: organization disabled`
export const ORG_DISABLED_ERROR_MESSAGE_ENV_KEY_WITH_OAUTH = ORG_DISABLED_ERROR_MESSAGE_ENV_KEY
export const PROMPT_TOO_LONG_ERROR_MESSAGE = `${API_ERROR_MESSAGE_PREFIX}: prompt too long`
export const TOKEN_REVOKED_ERROR_MESSAGE = `${API_ERROR_MESSAGE_PREFIX}: token revoked`

export function getAssistantMessageFromError(err: unknown): unknown {
  const content =
    err instanceof Error
      ? `${API_ERROR_MESSAGE_PREFIX}: ${err.message}`
      : `${API_ERROR_MESSAGE_PREFIX}: ${String(err)}`
  return {
    type: 'assistant',
    uuid: randomUUID(),
    timestamp: new Date().toISOString(),
    message: {
      id: randomUUID(),
      type: 'message',
      role: 'assistant',
      content: [{ type: 'text', text: content }],
      model: 'UMMAYA',
      stop_reason: 'end_turn',
      stop_sequence: null,
      usage: {
        input_tokens: 0,
        output_tokens: 0,
        cache_creation_input_tokens: 0,
        cache_read_input_tokens: 0,
      },
    },
  }
}

export function getErrorMessageIfRefusal(_err: unknown): string | null {
  return null
}

export function startsWithApiErrorPrefix(value: string): boolean {
  return value.startsWith(API_ERROR_MESSAGE_PREFIX)
}

export function isPromptTooLongMessage(_msg: unknown): boolean {
  return false
}

export function parsePromptTooLongTokenCounts(
  _rawMessage: string,
):
  | {
      actualTokens: number
      limitTokens: number
    }
  | undefined {
  return undefined
}

export function getPromptTooLongTokenGap(_msg: unknown): number | undefined {
  return undefined
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
