import type { Message } from '../../../types/message.js'
import type { SystemPrompt } from '../../../utils/systemPromptType.js'
import type { OpenAIMessage, OpenAIToolCall } from './types.js'

type CacheControl = {
  readonly type: 'ephemeral'
  readonly scope?: 'global' | 'org'
  readonly ttl?: '5m' | '1h'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function textFromContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .filter(isRecord)
    .filter(block => block.type === 'text' && typeof block.text === 'string')
    .map(block => String(block.text))
    .join('')
}

type ToolUseBlock = {
  readonly type: 'tool_use'
  readonly id: string
  readonly name: string
  readonly input?: unknown
}

type ToolResultBlock = {
  readonly type: 'tool_result'
  readonly tool_use_id: string
  readonly content?: unknown
}

function asToolUseBlock(value: unknown): ToolUseBlock | undefined {
  if (!isRecord(value)) return undefined
  if (value.type !== 'tool_use') return undefined
  if (typeof value.id !== 'string' || value.id.length === 0) return undefined
  if (typeof value.name !== 'string' || value.name.length === 0) return undefined
  return {
    type: 'tool_use',
    id: value.id,
    name: value.name,
    input: value.input,
  }
}

function asToolResultBlock(value: unknown): ToolResultBlock | undefined {
  if (!isRecord(value)) return undefined
  if (value.type !== 'tool_result') return undefined
  if (typeof value.tool_use_id !== 'string' || value.tool_use_id.length === 0) {
    return undefined
  }
  return {
    type: 'tool_result',
    tool_use_id: value.tool_use_id,
    content: value.content,
  }
}

function serializeToolUseInput(input: unknown): string {
  if (typeof input === 'string') return input
  if (input === undefined || input === null) return '{}'
  try {
    return JSON.stringify(input)
  } catch {
    return '{}'
  }
}

function serializeToolResultContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (content === undefined || content === null) return ''
  try {
    return JSON.stringify(content)
  } catch {
    return String(content)
  }
}

function findToolNameForResult(
  toolUseId: string,
  emittedMessages: readonly OpenAIMessage[],
): string | undefined {
  for (let index = emittedMessages.length - 1; index >= 0; index -= 1) {
    const message = emittedMessages[index]
    if (message?.role !== 'assistant') continue
    for (const toolCall of message.tool_calls ?? []) {
      if (toolCall.id === toolUseId) return toolCall.function.name
    }
  }
  return undefined
}

function collectToolResultIds(messages: readonly Message[]): ReadonlySet<string> {
  const toolResultIds = new Set<string>()
  for (const message of messages) {
    if (message.type !== 'user') continue
    const content = message.message.content
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const toolResult = asToolResultBlock(block)
      if (toolResult !== undefined) toolResultIds.add(toolResult.tool_use_id)
    }
  }
  return toolResultIds
}

function transcriptMessageToOpenAIMessages(
  message: Message,
  emittedMessages: readonly OpenAIMessage[],
  matchedToolResultIds: ReadonlySet<string>,
): readonly OpenAIMessage[] {
  if (message.type !== 'user' && message.type !== 'assistant') return []
  const content = message.message.content
  if (typeof content === 'string') {
    return content.length > 0 ? [{ role: message.type, content }] : []
  }
  if (!Array.isArray(content)) return []

  if (message.type === 'user') {
    const out: OpenAIMessage[] = []
    const textContent = textFromContent(content)
    for (const block of content) {
      const toolResult = asToolResultBlock(block)
      if (toolResult === undefined) continue
      const toolName = findToolNameForResult(toolResult.tool_use_id, emittedMessages)
      if (toolName === undefined) continue
      out.push({
        role: 'tool',
        name: toolName,
        tool_call_id: toolResult.tool_use_id,
        content: serializeToolResultContent(toolResult.content),
      })
    }
    if (textContent.length > 0) {
      out.push({ role: 'user', content: textContent })
    }
    return out
  }

  const toolCalls: OpenAIToolCall[] = []
  for (const block of content) {
    const toolUse = asToolUseBlock(block)
    if (toolUse === undefined) continue
    if (!matchedToolResultIds.has(toolUse.id)) continue
    toolCalls.push({
      id: toolUse.id,
      type: 'function',
      function: {
        name: toolUse.name,
        arguments: serializeToolUseInput(toolUse.input),
      },
    })
  }

  const textContent = textFromContent(content)
  if (toolCalls.length > 0) {
    return [{ role: 'assistant', content: textContent, tool_calls: toolCalls }]
  }
  return textContent.length > 0 ? [{ role: 'assistant', content: textContent }] : []
}

export function systemPromptText(systemPrompt: SystemPrompt): string {
  return Array.from(systemPrompt).join('\n')
}

export function latestUserText(messages: readonly Message[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message?.type === 'user' && message.isMeta !== true) {
      const text = textFromContent(message.message.content).trim()
      if (text.length > 0) return text
    }
  }
  return ''
}

export function transcriptToOpenAIMessages(
  messages: readonly Message[],
  systemPrompt: SystemPrompt,
  extraSystemInstruction?: string,
): readonly OpenAIMessage[] {
  const out: OpenAIMessage[] = [
    {
      role: 'system',
      content: [systemPromptText(systemPrompt), extraSystemInstruction]
        .filter(Boolean)
        .join('\n\n'),
    },
  ]
  const matchedToolResultIds = collectToolResultIds(messages)
  for (const message of messages) {
    out.push(...transcriptMessageToOpenAIMessages(message, out, matchedToolResultIds))
  }
  return out
}

export function getPromptCachingEnabled(_model: string): boolean {
  return false
}

export function getCacheControl(
  _params: { readonly scope?: 'global' | 'org'; readonly querySource?: string } = {},
): CacheControl {
  return { type: 'ephemeral' }
}

export function userMessageToMessageParam(
  message: Message,
  _addCache = false,
  _enablePromptCaching = false,
  _querySource?: string,
): OpenAIMessage {
  return { role: 'user', content: textFromContent(message.message.content) }
}

export function assistantMessageToMessageParam(
  message: Message,
  _addCache = false,
  _enablePromptCaching = false,
  _querySource?: string,
): OpenAIMessage {
  return { role: 'assistant', content: textFromContent(message.message.content) }
}

export function stripExcessMediaItems<T>(
  messages: readonly T[],
  _limit: number,
): readonly T[] {
  return messages
}

export function addCacheBreakpoints<T>(
  messages: readonly T[],
  _enablePromptCaching: boolean,
  _querySource?: string,
  _useCachedMC = false,
  _newCacheEdits?: unknown,
  _pinnedEdits?: unknown,
  _skipCacheWrite = false,
): readonly T[] {
  return messages
}

export function buildSystemPromptBlocks(
  systemPrompt: SystemPrompt,
  _enablePromptCaching: boolean,
  _options?: unknown,
): readonly { readonly text: string }[] {
  return [{ text: systemPromptText(systemPrompt) }]
}
