import { textFromContent } from './nmcAedGuard.js'

const TEXT_TOOL_CALL_RE =
  /<tool_call>|<\/tool_call>|"name"\s*:\s*"[^"]+"[\s\S]*"arguments"\s*:\s*\{/iu
const TEXT_TOOL_CALL_BLOCK_RE = /\s*<tool_call>[\s\S]*?<\/tool_call>\s*/giu
const TEXT_TOOL_CALL_REPAIR_MARKER = 'Textual tool-call final-answer repair'
const TEXT_TOOL_CALL_REPAIR_PROMPT =
  'Textual tool-call final-answer repair: the previous assistant message was invalid because it printed a tool call as text. Never emit <tool_call> text, JSON tool-call text, or a JSON object with name/arguments in prose. If a tool is still needed, call it only through the native structured tool_use interface. If the needed tool has already been attempted, do not call or print any tool; write one Korean prose answer from the actual tool results already in this conversation. If the available result is no-data, upstream failure, approval-required, or insufficient for the requested detail, state that directly and give the official handoff or next action.'

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : undefined
}

function messageRecord(message: unknown): Record<string, unknown> | undefined {
  return asRecord(asRecord(message)?.message)
}

function messageRole(message: unknown): string | undefined {
  const outer = asRecord(message)
  const inner = messageRecord(message)
  if (typeof inner?.role === 'string') return inner.role
  if (typeof outer?.role === 'string') return outer.role
  return typeof outer?.type === 'string' ? outer.type : undefined
}

function messageContent(message: unknown): unknown {
  return messageRecord(message)?.content ?? asRecord(message)?.content
}

function contentBlocks(message: unknown): readonly unknown[] {
  const content = messageContent(message)
  return Array.isArray(content) ? content : []
}

function hasToolUseBlock(message: unknown): boolean {
  return contentBlocks(message).some(block => asRecord(block)?.type === 'tool_use')
}

function assistantTextContainsToolCall(message: unknown): boolean {
  if (messageRole(message) !== 'assistant') return false
  if (hasToolUseBlock(message)) return false
  return TEXT_TOOL_CALL_RE.test(textFromContent(messageContent(message)))
}

function hasRepairPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message =>
    textFromContent(messageContent(message)).includes(TEXT_TOOL_CALL_REPAIR_MARKER),
  )
}

function latestAssistantMessage(messages: readonly unknown[]): unknown | undefined {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    if (messageRole(messages[idx]) === 'assistant') return messages[idx]
  }
  return undefined
}

export function buildTextToolCallFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  if (hasRepairPrompt(messages)) return undefined
  const latestAssistant = latestAssistantMessage(messages)
  if (!assistantTextContainsToolCall(latestAssistant)) return undefined
  return TEXT_TOOL_CALL_REPAIR_PROMPT
}

export function shouldWithholdTextToolCallFinalAnswer({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasRepairPrompt(messages)) return false
  return assistantTextContainsToolCall(candidate)
}

export function textContainsToolCall(text: string): boolean {
  return TEXT_TOOL_CALL_RE.test(text)
}

export function stripTextToolCallBlocks(text: string): string {
  return text
    .replace(TEXT_TOOL_CALL_BLOCK_RE, '\n')
    .replace(/\n{3,}/gu, '\n\n')
    .trim()
}
