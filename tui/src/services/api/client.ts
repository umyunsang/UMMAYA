// SPDX-License-Identifier: Apache-2.0
// UMMAYA FriendliAI client shim for the CC-restored provider.
//
// services/api/claude.ts is the Claude Code streaming provider shape. This
// module supplies the one sanctioned swap: Anthropic SDK transport becomes
// FriendliAI's OpenAI-compatible /chat/completions endpoint. query.ts still
// owns the agentic loop; backend stdio remains only the tool executor for
// Korean public-service adapters and their operator-managed API keys.

import { randomUUID } from 'crypto'
import {
  APIConnectionError,
  APIError,
  APIUserAbortError,
  type BetaContentBlockParam,
  type BetaMessage,
  type BetaMessageParam,
  type BetaMessageStreamParams,
  type BetaRawMessageStreamEvent,
  type BetaToolChoiceAuto,
  type BetaToolChoiceTool,
  type BetaToolUnion,
  type BetaUsage,
  type ClientOptions,
  type Stream,
} from '../../sdk-compat.js'
import { assertFriendliApiKeyForUse } from '../../utils/auth.js'
import { getUserAgent } from '../../utils/http.js'
import {
  providerReasoningPayload,
  resolveKExaoneReasoningPolicy,
  type ReasoningMode,
} from '../../utils/kExaoneReasoning.js'
import { UMMAYA_K_EXAONE_MODEL } from '../../utils/model/constants.js'

export const CLIENT_REQUEST_ID_HEADER = 'x-client-request-id'

type FetchLike = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>

type RequestOptions = {
  signal?: AbortSignal
  timeout?: number
  headers?: Record<string, string>
}

type FriendliMessageStreamParams = BetaMessageStreamParams & {
  stream?: boolean
  reasoning_mode?: ReasoningMode
}

type FriendliClientArgs = {
  apiKey?: string
  maxRetries: number
  model?: string
  fetchOverride?: unknown
  source?: string
}

type OpenAIMessage =
  | { role: 'system' | 'user'; content: string }
  | {
      role: 'assistant'
      content: string | null
      tool_calls?: OpenAIToolCall[]
    }
  | { role: 'tool'; tool_call_id: string; content: string }

type OpenAIToolCall = {
  id: string
  type: 'function'
  function: {
    name: string
    arguments: string
  }
}

type OpenAITool = {
  type: 'function'
  function: {
    name: string
    description?: string
    parameters: Record<string, unknown>
  }
}

type OpenAIStreamChoice = {
  index?: number
  delta?: {
    content?: string | null
    reasoning_content?: string | null
    tool_calls?: Array<{
      index?: number
      id?: string
      type?: string
      function?: {
        name?: string
        arguments?: string
      }
    }>
  }
  finish_reason?: string | null
}

type OpenAIChunk = {
  id?: string
  model?: string
  choices?: OpenAIStreamChoice[]
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
  } | null
}

type ToolStreamState = {
  blockIndex?: number
  id?: string
  name?: string
  pendingArgs: string
}

export async function getAnthropicClient({
  apiKey,
  model,
  fetchOverride,
}: FriendliClientArgs): Promise<unknown> {
  return new FriendliMessagesCompatClient({
    apiKey: apiKey ?? assertFriendliApiKeyForUse(),
    model: model ?? UMMAYA_K_EXAONE_MODEL,
    fetchFn: resolveFetch(fetchOverride),
    baseUrl:
      process.env.UMMAYA_FRIENDLI_BASE_URL ??
      'https://api.friendli.ai/serverless/v1',
  })
}

class FriendliMessagesCompatClient {
  readonly beta: {
    messages: {
      create: (
        params: FriendliMessageStreamParams,
        options?: RequestOptions,
      ) => unknown
    }
  }

  constructor(
    private readonly opts: {
      apiKey: string
      model: string
      fetchFn: FetchLike
      baseUrl: string
    },
  ) {
    this.beta = {
      messages: {
        create: (params, options) => {
          if (params.stream) {
            return {
              withResponse: () => this.streamWithResponse(params, options),
            }
          }
          return this.complete(params, options)
        },
      },
    }
  }

  private async streamWithResponse(
    params: FriendliMessageStreamParams,
    options?: RequestOptions,
  ): Promise<{
    data: Stream<BetaRawMessageStreamEvent>
    response: Response
    request_id: string
  }> {
    const controller = linkedAbortController(options?.signal)
    const response = await this.fetchChatCompletion(
      {
        ...params,
        stream: true,
      },
      {
        ...options,
        signal: controller.signal,
      },
    )
    const requestId = response.headers.get('x-request-id') ?? randomUUID()
    const data = this.openAIStreamToAnthropicEvents(
      response,
      params,
      controller,
    ) as Stream<BetaRawMessageStreamEvent>
    data.controller = controller
    return { data, response, request_id: requestId }
  }

  private async complete(
    params: FriendliMessageStreamParams,
    options?: RequestOptions,
  ): Promise<BetaMessage> {
    const response = await this.fetchChatCompletion(
      { ...params, stream: false },
      options,
    )
    const raw = (await response.json()) as {
      id?: string
      model?: string
      choices?: Array<{
        message?: {
          content?: string | null
          reasoning_content?: string | null
          tool_calls?: OpenAIToolCall[]
        }
        finish_reason?: string | null
      }>
      usage?: {
        prompt_tokens?: number
        completion_tokens?: number
      }
    }
    const choice = raw.choices?.[0]
    const message = choice?.message ?? {}
    const content: BetaContentBlockParam[] = []
    if (message.reasoning_content) {
      content.push({ type: 'thinking', thinking: message.reasoning_content })
    }
    if (message.content) {
      content.push({ type: 'text', text: message.content })
    }
    for (const toolCall of message.tool_calls ?? []) {
      content.push({
        type: 'tool_use',
        id: toolCall.id,
        name: toolCall.function.name,
        input: safeJsonObject(toolCall.function.arguments),
      })
    }

    return {
      id: raw.id ?? randomUUID(),
      role: 'assistant',
      model: raw.model ?? params.model,
      content,
      stop_reason: mapFinishReason(choice?.finish_reason),
      usage: usageFromOpenAI(raw.usage),
    }
  }

  private async fetchChatCompletion(
    params: BetaMessageStreamParams & { stream?: boolean },
    options?: RequestOptions,
  ): Promise<Response> {
    if (options?.signal?.aborted) throw new APIUserAbortError()

    const response = await this.opts.fetchFn(`${trimSlash(this.opts.baseUrl)}/chat/completions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.opts.apiKey}`,
        'Content-Type': 'application/json',
        'User-Agent': getUserAgent(),
        ...(options?.headers ?? {}),
      },
      body: JSON.stringify(buildOpenAIPayload(params)),
      signal: options?.signal,
    })

    if (!response.ok) {
      await throwAPIError(response)
    }

    return response
  }

  private async *openAIStreamToAnthropicEvents(
    response: Response,
    params: BetaMessageStreamParams,
    controller: AbortController,
  ): AsyncGenerator<BetaRawMessageStreamEvent> {
    let messageId = randomUUID()
    let responseModel = params.model
    let messageStarted = false
    let nextBlockIndex = 0
    let textBlockIndex: number | undefined
    let thinkingBlockIndex: number | undefined
    const openedBlocks = new Set<number>()
    const toolStates = new Map<number, ToolStreamState>()
    let finalUsage: BetaUsage | undefined
    let stopReason: BetaMessage['stop_reason'] = 'end_turn'
    const allowReasoning = resolveKExaoneReasoningPolicy({
      explicitSessionMode: params.reasoning_mode,
    }).includeReasoning

    const ensureMessageStart = function* () {
      if (messageStarted) return
      messageStarted = true
      yield {
        type: 'message_start' as const,
        message: {
          id: messageId,
          type: 'message',
          role: 'assistant',
          content: [],
          model: responseModel,
          stop_reason: null,
          stop_sequence: null,
          usage: usageFromOpenAI(null),
        },
      }
    }

    const ensureTextBlock = function* () {
      yield* ensureMessageStart()
      if (textBlockIndex === undefined) {
        if (
          thinkingBlockIndex !== undefined &&
          openedBlocks.has(thinkingBlockIndex)
        ) {
          yield* closeNonToolBlocks()
        }
        textBlockIndex = nextBlockIndex++
        openedBlocks.add(textBlockIndex)
        yield {
          type: 'content_block_start' as const,
          index: textBlockIndex,
          content_block: { type: 'text' as const, text: '' },
        }
      }
    }

    const ensureThinkingBlock = function* () {
      yield* ensureMessageStart()
      if (thinkingBlockIndex === undefined) {
        if (textBlockIndex !== undefined && openedBlocks.has(textBlockIndex)) {
          yield* closeNonToolBlocks()
        }
        thinkingBlockIndex = nextBlockIndex++
        openedBlocks.add(thinkingBlockIndex)
        yield {
          type: 'content_block_start' as const,
          index: thinkingBlockIndex,
          content_block: { type: 'thinking' as const, thinking: '' },
        }
      }
    }

    const closeNonToolBlocks = function* () {
      const indexes = [thinkingBlockIndex, textBlockIndex]
        .filter(
          (index): index is number =>
            index !== undefined && openedBlocks.has(index),
        )
        .sort((a, b) => a - b)

      for (const index of indexes) {
        openedBlocks.delete(index)
        yield { type: 'content_block_stop' as const, index }
        if (index === thinkingBlockIndex) thinkingBlockIndex = undefined
        if (index === textBlockIndex) textBlockIndex = undefined
      }
    }

    const ensureToolBlock = function* (state: ToolStreamState) {
      yield* ensureMessageStart()
      if (state.blockIndex === undefined) {
        // CC streams one finalized content block before starting the next.
        // Close text/thinking first so claude.ts can commit mid-loop text.
        yield* closeNonToolBlocks()
        state.blockIndex = nextBlockIndex++
        openedBlocks.add(state.blockIndex)
        yield {
          type: 'content_block_start' as const,
          index: state.blockIndex,
          content_block: {
            type: 'tool_use' as const,
            id: state.id ?? randomUUID(),
            name: state.name ?? '(unknown tool)',
            input: {},
          },
        }
      }
      if (state.pendingArgs.length > 0) {
        yield {
          type: 'content_block_delta' as const,
          index: state.blockIndex,
          delta: {
            type: 'input_json_delta' as const,
            partial_json: state.pendingArgs,
          },
        }
        state.pendingArgs = ''
      }
    }

    try {
      for await (const payload of readSSEPayloads(response)) {
        if (controller.signal.aborted) throw new APIUserAbortError()
        if (payload === '[DONE]') break

        const chunk = parseOpenAIChunk(payload)
        if (!chunk) continue
        if (chunk.id) messageId = chunk.id
        if (chunk.model) responseModel = chunk.model
        if (chunk.usage) finalUsage = usageFromOpenAI(chunk.usage)

        for (const choice of chunk.choices ?? []) {
          const delta = choice.delta ?? {}
          if (delta.reasoning_content && allowReasoning) {
            yield* ensureThinkingBlock()
            yield {
              type: 'content_block_delta' as const,
              index: thinkingBlockIndex!,
              delta: {
                type: 'thinking_delta' as const,
                thinking: delta.reasoning_content,
              },
            }
          }

          if (delta.content) {
            yield* ensureTextBlock()
            yield {
              type: 'content_block_delta' as const,
              index: textBlockIndex!,
              delta: { type: 'text_delta' as const, text: delta.content },
            }
          }

          for (const toolCall of delta.tool_calls ?? []) {
            const openAIIndex = toolCall.index ?? 0
            const state =
              toolStates.get(openAIIndex) ?? { pendingArgs: '' }
            if (toolCall.id) state.id = toolCall.id
            if (toolCall.function?.name) state.name = toolCall.function.name
            if (toolCall.function?.arguments) {
              state.pendingArgs += toolCall.function.arguments
            }
            toolStates.set(openAIIndex, state)
            if (state.name) {
              yield* ensureToolBlock(state)
            }
          }

          if (choice.finish_reason) {
            stopReason = mapFinishReason(choice.finish_reason)
          }
        }
      }

      for (const state of toolStates.values()) {
        if (state.blockIndex === undefined) {
          yield* ensureToolBlock(state)
        }
      }

      for (const index of [...openedBlocks].sort((a, b) => a - b)) {
        yield { type: 'content_block_stop' as const, index }
      }

      if (messageStarted) {
        yield {
          type: 'message_delta' as const,
          delta: { stop_reason: stopReason, stop_sequence: null },
          usage: finalUsage ?? usageFromOpenAI(null),
        }
        yield { type: 'message_stop' as const }
      }
    } finally {
      if (!controller.signal.aborted) {
        controller.abort()
      }
    }
  }
}

function buildOpenAIPayload(
  params: FriendliMessageStreamParams,
): Record<string, unknown> {
  const messages = convertMessages(params.messages, params.system)
  const tools = convertTools(params.tools)
  const reasoning = providerReasoningPayload(
    resolveKExaoneReasoningPolicy({
      explicitSessionMode: params.reasoning_mode,
    }),
  )
  const payload: Record<string, unknown> = {
    model: params.model || UMMAYA_K_EXAONE_MODEL,
    messages,
    max_tokens: params.max_tokens,
    ...reasoning,
    ...(params.temperature !== undefined ? { temperature: params.temperature } : {}),
    ...(tools.length > 0
      ? {
          tools,
          tool_choice: convertToolChoice(params.tool_choice),
          parallel_tool_calls: false,
        }
      : {}),
  }

  if (params.stream) {
    payload.stream = true
    payload.stream_options = { include_usage: true }
  }

  return payload
}

function convertMessages(
  messages: BetaMessageParam[],
  system: BetaMessageStreamParams['system'],
): OpenAIMessage[] {
  const converted: OpenAIMessage[] = []
  const systemText = systemToText(system)
  if (systemText) {
    converted.push({ role: 'system', content: systemText })
  }

  for (const message of messages) {
    if (typeof message.content === 'string') {
      converted.push({ role: message.role, content: message.content })
      continue
    }

    if (message.role === 'assistant') {
      const text = message.content
        .filter(block => block.type === 'text')
        .map(block => block.text)
        .join('')
      const toolCalls = message.content
        .filter(block => block.type === 'tool_use')
        .map(block => ({
          id: block.id,
          type: 'function' as const,
          function: {
            name: block.name,
            arguments: JSON.stringify(block.input ?? {}),
          },
        }))
      converted.push({
        role: 'assistant',
        content: text.length > 0 ? text : toolCalls.length > 0 ? null : '',
        ...(toolCalls.length > 0 ? { tool_calls: toolCalls } : {}),
      })
      continue
    }

    const userText = message.content
      .filter(block => block.type === 'text')
      .map(block => block.text)
      .join('')
    if (userText.length > 0) {
      converted.push({ role: 'user', content: userText })
    }
    for (const block of message.content.filter(
      item => item.type === 'tool_result',
    )) {
      converted.push({
        role: 'tool',
        tool_call_id: block.tool_use_id,
        content: toolResultContentToString(block.content),
      })
    }
  }

  return converted.length > 0
    ? converted
    : [{ role: 'user', content: '' }]
}

function convertTools(tools: BetaMessageStreamParams['tools']): OpenAITool[] {
  if (!tools) return []
  return tools.flatMap(tool => {
    const maybeTool = tool as BetaToolUnion & {
      input_schema?: Record<string, unknown>
      description?: string
      name?: string
    }
    if (!maybeTool.name || !maybeTool.input_schema) return []
    return [
      {
        type: 'function' as const,
        function: {
          name: maybeTool.name,
          ...(maybeTool.description ? { description: maybeTool.description } : {}),
          parameters: sanitizeSchema(maybeTool.input_schema),
        },
      },
    ]
  })
}

function convertToolChoice(
  toolChoice: BetaToolChoiceAuto | BetaToolChoiceTool | undefined,
): 'auto' | { type: 'function'; function: { name: string } } | undefined {
  if (!toolChoice) return undefined
  if (toolChoice.type === 'auto') return 'auto'
  return { type: 'function', function: { name: toolChoice.name } }
}

function sanitizeSchema(schema: Record<string, unknown>): Record<string, unknown> {
  const clone = { ...schema }
  delete clone.cache_control
  delete clone.defer_loading
  delete clone.eager_input_streaming
  if (clone.type !== 'object') clone.type = 'object'
  return clone
}

function systemToText(system: BetaMessageStreamParams['system']): string {
  if (!system) return ''
  if (typeof system === 'string') return system
  if (Array.isArray(system)) {
    return system
      .map(block => {
        if (typeof block === 'string') return block
        if (
          block &&
          typeof block === 'object' &&
          'text' in block &&
          typeof block.text === 'string'
        ) {
          return block.text
        }
        return ''
      })
      .filter(Boolean)
      .join('\n\n')
  }
  return String(system)
}

function toolResultContentToString(
  content: string | BetaContentBlockParam[],
): string {
  if (typeof content === 'string') return content
  return content
    .map(block => {
      if (block.type === 'text') return block.text
      return JSON.stringify(block)
    })
    .join('\n')
}

function usageFromOpenAI(
  usage: OpenAIChunk['usage'] | undefined,
): BetaUsage {
  return {
    input_tokens: usage?.prompt_tokens ?? 0,
    output_tokens: usage?.completion_tokens ?? 0,
    cache_creation_input_tokens: 0,
    cache_read_input_tokens: 0,
    server_tool_use: {
      web_search_requests: 0,
      web_fetch_requests: 0,
    },
    service_tier: null,
    cache_creation: {
      ephemeral_1h_input_tokens: 0,
      ephemeral_5m_input_tokens: 0,
    },
    inference_geo: null,
    iterations: 0,
    speed: null,
  } as BetaUsage
}

function mapFinishReason(reason: string | null | undefined): BetaMessage['stop_reason'] {
  switch (reason) {
    case 'tool_calls':
      return 'tool_use'
    case 'length':
      return 'max_tokens'
    case 'stop':
    default:
      return 'end_turn'
  }
}

function safeJsonObject(raw: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(raw || '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {}
  } catch {
    return {}
  }
}

async function* readSSEPayloads(response: Response): AsyncGenerator<string> {
  const body = response.body
  if (!body) throw new APIConnectionError('FriendliAI response had no body.')
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let newlineIndex = buffer.indexOf('\n')
      while (newlineIndex >= 0) {
        const line = buffer.slice(0, newlineIndex).trimEnd()
        buffer = buffer.slice(newlineIndex + 1)
        if (line.startsWith('data: ')) {
          yield line.slice('data: '.length).trim()
        }
        newlineIndex = buffer.indexOf('\n')
      }
    }
    const tail = buffer.trim()
    if (tail.startsWith('data: ')) {
      yield tail.slice('data: '.length).trim()
    }
  } finally {
    reader.releaseLock()
  }
}

function parseOpenAIChunk(payload: string): OpenAIChunk | null {
  try {
    return JSON.parse(payload) as OpenAIChunk
  } catch {
    return null
  }
}

async function throwAPIError(response: Response): Promise<never> {
  const requestId = response.headers.get('x-request-id') ?? undefined
  const text = await response.text()
  let parsed: unknown = text
  try {
    parsed = JSON.parse(text)
  } catch {
    // Keep the raw text body.
  }
  const message =
    typeof parsed === 'object' && parsed !== null && 'error' in parsed
      ? JSON.stringify((parsed as { error: unknown }).error)
      : text || response.statusText
  const error = new APIError(response.status, parsed, message, response.headers)
  error.requestID = requestId
  throw error
}

function linkedAbortController(signal?: AbortSignal): AbortController {
  const controller = new AbortController()
  if (!signal) return controller
  if (signal.aborted) {
    controller.abort()
    return controller
  }
  signal.addEventListener('abort', () => controller.abort(), { once: true })
  return controller
}

function resolveFetch(fetchOverride: unknown): FetchLike {
  return (typeof fetchOverride === 'function' ? fetchOverride : fetch) as FetchLike
}

function trimSlash(value: string): string {
  return value.replace(/\/+$/, '')
}
