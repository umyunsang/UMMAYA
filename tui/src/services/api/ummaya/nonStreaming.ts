import { createAssistantMessage } from '../../../utils/messages.js'
import { createUserMessage } from '../../../utils/userMessageFactories.js'
import { asSystemPrompt } from '../../../utils/systemPromptType.js'
import { EMPTY_USAGE } from './types.js'
import type { QueryModelParams } from './types.js'

export const MAX_NON_STREAMING_TOKENS = 64_000

export function adjustParamsForNonStreaming<T>(
  params: T,
  _maxTokensCap: number,
): T {
  return params
}

export async function* executeNonStreamingRequest(
  _clientOptions: unknown,
  _retryOptions: unknown,
  _paramsFromContext: unknown,
  _onAttempt?: unknown,
  _captureRequest?: unknown,
): AsyncGenerator<unknown> {
  yield createAssistantMessage({ content: '' })
}

export async function queryModelWithoutStreaming(
  params: QueryModelParams,
): Promise<unknown> {
  const events: unknown[] = []
  const { queryModelWithStreaming } = await import('./provider.js')
  for await (const event of queryModelWithStreaming(params)) {
    events.push(event)
  }
  return events.find(
    event =>
      typeof event === 'object' &&
      event !== null &&
      'type' in event &&
      event.type === 'assistant',
  )
}

export async function queryHaiku(params: {
  readonly systemPrompt?: ReturnType<typeof asSystemPrompt>
  readonly userPrompt: string
  readonly outputFormat?: unknown
  readonly signal?: AbortSignal
  readonly options: QueryModelParams['options']
}): Promise<unknown> {
  return queryModelWithoutStreaming({
    messages: [createUserMessage({ content: params.userPrompt })],
    systemPrompt: params.systemPrompt ?? asSystemPrompt([]),
    thinkingConfig: { type: 'disabled' },
    tools: [],
    signal: params.signal ?? new AbortController().signal,
    options: params.options,
  })
}

export async function queryWithModel(params: Parameters<typeof queryHaiku>[0]): Promise<unknown> {
  return queryHaiku(params)
}

export function getMaxOutputTokensForModel(_model: string): number {
  return EMPTY_USAGE.output_tokens + MAX_NON_STREAMING_TOKENS
}
