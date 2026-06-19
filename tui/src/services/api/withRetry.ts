// SPDX-License-Identifier: Apache-2.0
// UMMAYA keeps Claude Code's query/provider boundary: query.ts owns the
// agentic loop and this helper preserves the SDK-shaped retry generator used
// by services/api/ummaya.ts. Provider-specific retry policy can be widened
// later, but the control-flow shape must stay generator-based so query.ts sees
// the same stream/system-message contract as the CC restored source.

import { APIError, APIUserAbortError } from '../../sdk-compat.js'
import type { QuerySource } from '../../constants/querySource.js'
import type { SystemAPIErrorMessage } from '../../types/message.js'
import type { ThinkingConfig } from '../../utils/thinking.js'

export class CannotRetryError extends Error {
  constructor(
    public readonly originalError: unknown,
    public readonly retryContext: RetryContext,
  ) {
    super(originalError instanceof Error ? originalError.message : String(originalError))
    this.name = 'RetryError'
    if (originalError instanceof Error && originalError.stack) {
      this.stack = originalError.stack
    }
  }
}

export class FallbackTriggeredError extends Error {
  constructor(
    public readonly originalModel: string,
    public readonly fallbackModel: string,
  ) {
    super(`Model fallback triggered: ${originalModel} -> ${fallbackModel}`)
    this.name = 'FallbackTriggeredError'
  }
}

const BASE_DELAY_MS = 500
const DEFAULT_MAX_RETRIES = 10

export type RetryContext = {
  maxTokensOverride?: number
  model: string
  thinkingConfig: ThinkingConfig
  fastMode?: boolean
}

type RetryOptions = {
  maxRetries?: number
  model: string
  fallbackModel?: string
  thinkingConfig: ThinkingConfig
  fastMode?: boolean
  signal?: AbortSignal
  querySource?: QuerySource
  initialConsecutive529Errors?: number
}

export async function* withRetry<Client, T>(
  getClient: () => Promise<Client>,
  operation: (
    client: Client,
    attempt: number,
    context: RetryContext,
  ) => Promise<T>,
  options: RetryOptions,
): AsyncGenerator<SystemAPIErrorMessage, T> {
  const retryContext: RetryContext = {
    model: options.model,
    thinkingConfig: options.thinkingConfig,
    ...(options.fastMode !== undefined ? { fastMode: options.fastMode } : {}),
  }
  const maxRetries = options.maxRetries ?? getDefaultMaxRetries()
  let lastError: unknown

  for (let attempt = 1; attempt <= maxRetries + 1; attempt++) {
    if (options.signal?.aborted) {
      throw new APIUserAbortError()
    }

    try {
      const client = await getClient()
      return await operation(client, attempt, retryContext)
    } catch (error) {
      lastError = error
      if (!(error instanceof APIError) || !shouldRetry(error) || attempt > maxRetries) {
        throw new CannotRetryError(error, retryContext)
      }
      const retryAfter = getRetryAfter(error)
      const delayMs = getRetryDelay(attempt, retryAfter)
      await sleep(delayMs, options.signal)
    }
  }

  throw new CannotRetryError(lastError, retryContext)
}

export function is529Error(err: unknown): boolean {
  return err instanceof APIError && err.status === 529
}

function shouldRetry(error: APIError): boolean {
  if (error instanceof APIUserAbortError) return false
  return error.status === 408 || error.status === 409 || error.status === 429 || (error.status !== undefined && error.status >= 500)
}

function getRetryAfter(error: APIError): string | null {
  const headers = error.headers as Headers | Record<string, string> | undefined
  if (!headers) return null
  if (typeof (headers as Headers).get === 'function') {
    return (headers as Headers).get('retry-after')
  }
  return (headers as Record<string, string>)['retry-after'] ?? null
}

export function getRetryDelay(
  attempt: number,
  retryAfterHeader?: string | null,
  maxDelayMs = 32_000,
): number {
  if (retryAfterHeader) {
    const seconds = parseInt(retryAfterHeader, 10)
    if (!Number.isNaN(seconds)) {
      return seconds * 1000
    }
  }

  const baseDelay = Math.min(
    BASE_DELAY_MS * Math.pow(2, attempt - 1),
    maxDelayMs,
  )
  const jitter = Math.random() * 0.25 * baseDelay
  return baseDelay + jitter
}

export function getDefaultMaxRetries(): number {
  if (process.env.CLAUDE_CODE_MAX_RETRIES) {
    return parseInt(process.env.CLAUDE_CODE_MAX_RETRIES, 10)
  }
  return DEFAULT_MAX_RETRIES
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return Promise.resolve()
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new APIUserAbortError())
      return
    }
    const timeout = setTimeout(resolve, ms)
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timeout)
        reject(new APIUserAbortError())
      },
      { once: true },
    )
  })
}
