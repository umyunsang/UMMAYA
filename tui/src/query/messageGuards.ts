import type {
  AssistantMessage,
  Message,
  UserMessage,
} from '../types/message.js'

export type TextBlock = {
  readonly type: 'text'
  readonly text: string
}

export type ToolUseBlock = {
  readonly type: 'tool_use'
  readonly id: string
  readonly name: string
  readonly input: Record<string, unknown>
}

type ContentBlock = TextBlock | ToolUseBlock | Record<string, unknown>
type MessageContentCarrier = {
  readonly message?: {
    readonly content?: unknown
  }
  readonly content?: unknown
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function contentBlocks(message: Message): readonly ContentBlock[] {
  const content = messageContent(message)
  return Array.isArray(content) ? content.filter(isRecord) : []
}

export function messageText(message: Message): string {
  const content = messageContent(message)
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .filter(isRecord)
    .filter((block): block is TextBlock => block.type === 'text')
    .map(block => block.text)
    .join('')
}

function messageContent(message: Message): unknown {
  const candidate = message as MessageContentCarrier
  return candidate.message?.content ?? candidate.content
}

export function toolUseBlocks(message: Message): readonly ToolUseBlock[] {
  return contentBlocks(message).filter(
    (block): block is ToolUseBlock =>
      block.type === 'tool_use' &&
      typeof block.id === 'string' &&
      typeof block.name === 'string' &&
      isRecord(block.input),
  )
}

export function isAssistantMessage(message: Message): message is AssistantMessage {
  return message.type === 'assistant'
}

export function isUserMessage(message: Message): message is UserMessage {
  return message.type === 'user'
}

function hasVisibleUserText(message: Message): boolean {
  return isUserMessage(message) && message.isMeta !== true &&
    messageText(message).trim().length > 0
}

export function latestTextUserMessageIndex(messages: readonly Message[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message && hasVisibleUserText(message)) return index
  }
  return -1
}

export function hasAssistantToolUseNamedAfterLatestTextUser(
  messages: readonly Message[],
  toolName: string,
): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  return messages.slice(latestUserIndex + 1).some(
    message =>
      isAssistantMessage(message) &&
      toolUseBlocks(message).some(block => block.name === toolName),
  )
}

export function cloneAssistantWithoutText(
  message: AssistantMessage,
): AssistantMessage {
  const blocks = contentBlocks(message).filter(block => block.type !== 'text')
  return {
    ...message,
    message: {
      ...message.message,
      content: blocks,
    },
  }
}
