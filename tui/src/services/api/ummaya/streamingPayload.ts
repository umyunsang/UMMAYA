import type { OpenAIToolCall } from './types.js'

export type ToolCallDelta = {
  readonly index: number
  readonly id?: string
  readonly name?: string
  readonly argumentsDelta?: string
}

export type ParsedChunk = {
  readonly text: string
  readonly reasoning: string
  readonly toolCallDeltas: readonly ToolCallDelta[]
  readonly done: boolean
}

type ToolCallState = {
  id?: string
  name?: string
  arguments: string
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function parseJsonLine(
  line: string,
): Record<string, unknown> | undefined {
  try {
    const parsed: unknown = JSON.parse(line)
    return isRecord(parsed) ? parsed : undefined
  } catch (error) {
    if (error instanceof SyntaxError) return undefined
    throw error
  }
}

export function providerFailureMessage(
  response: Response,
  body: string,
): string {
  const status = [String(response.status), response.statusText]
    .filter(part => part.trim().length > 0)
    .join(' ')
  const requestId = response.headers.get('x-request-id')
  const detail = providerErrorDetail(body)
  return [
    `FriendliAI request failed (${status}).`,
    detail ? `Provider message: ${detail}.` : undefined,
    requestId ? `Request ID: ${requestId}.` : undefined,
    'Check /login or UMMAYA_FRIENDLI_TOKEN before sending another request.',
  ]
    .filter(Boolean)
    .join(' ')
}

export function chunkFromPayload(
  payload: Record<string, unknown>,
): ParsedChunk {
  const choices = Array.isArray(payload.choices) ? payload.choices : []
  const firstChoice = choices.find(isRecord)
  const delta = isRecord(firstChoice?.delta) ? firstChoice.delta : {}
  const text = typeof delta.content === 'string' ? delta.content : ''
  const reasoning =
    typeof delta.reasoning_content === 'string' ? delta.reasoning_content : ''
  const toolCallDeltas = Array.isArray(delta.tool_calls)
    ? delta.tool_calls.filter(isRecord).map(toolCallDeltaFromPayload)
    : []
  return {
    text,
    reasoning,
    toolCallDeltas,
    done:
      firstChoice?.finish_reason === 'stop' ||
      firstChoice?.finish_reason === 'tool_calls',
  }
}

export function parseToolArguments(value: string): Record<string, unknown> {
  const parsed = parseJsonLine(value)
  return parsed ?? {}
}

export function completedToolCalls(
  states: ReadonlyMap<number, ToolCallState>,
): readonly OpenAIToolCall[] {
  return Array.from(states.entries())
    .sort(([left], [right]) => left - right)
    .flatMap(([, state]) => {
      if (state.id === undefined || state.name === undefined) return []
      return [{
        id: state.id,
        type: 'function' as const,
        function: {
          name: state.name,
          arguments: state.arguments.length > 0 ? state.arguments : '{}',
        },
      }]
    })
}

function textField(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0
    ? value.trim()
    : undefined
}

function providerErrorDetail(body: string): string | undefined {
  const parsed = parseJsonLine(body.trim())
  const topLevelMessage = textField(parsed?.message)
  if (topLevelMessage) return topLevelMessage
  const error = parsed?.error
  if (typeof error === 'string') return textField(error)
  if (!isRecord(error)) return undefined
  return textField(error.message) ?? textField(error.detail)
}

function toolCallDeltaFromPayload(
  delta: Record<string, unknown>,
): ToolCallDelta {
  const fn = isRecord(delta.function) ? delta.function : {}
  return {
    index: typeof delta.index === 'number' ? delta.index : 0,
    id: typeof delta.id === 'string' ? delta.id : undefined,
    name: typeof fn.name === 'string' ? fn.name : undefined,
    argumentsDelta: typeof fn.arguments === 'string' ? fn.arguments : undefined,
  }
}
