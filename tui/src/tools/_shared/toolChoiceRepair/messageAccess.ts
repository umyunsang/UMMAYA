import type { Message } from '../../../types/message.js'

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function messageRecord(
  message: unknown,
): Record<string, unknown> | undefined {
  if (!isRecord(message)) return undefined
  return isRecord(message.message) ? message.message : undefined
}

export function messageRole(message: unknown): string | undefined {
  const outer = isRecord(message) ? message : undefined
  const inner = messageRecord(message)
  if (typeof inner?.role === 'string') return inner.role
  if (typeof outer?.role === 'string') return outer.role
  return typeof outer?.type === 'string' ? outer.type : undefined
}

export function messageContent(message: unknown): unknown {
  return messageRecord(message)?.content ?? (isRecord(message) ? message.content : undefined)
}

export function textFromContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map(block => {
      if (typeof block === 'string') return block
      if (!isRecord(block)) return ''
      if (block.type !== 'text') return ''
      return typeof block.text === 'string' ? block.text : ''
    })
    .filter(text => text.length > 0)
    .join('\n')
}

export function latestUserText(messages: readonly unknown[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messageRole(messages[index]) !== 'user') continue
    const text = textFromContent(messageContent(messages[index])).trim()
    if (text.length > 0) return text
  }
  return ''
}

export function latestUserMessageIndex(messages: readonly unknown[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messageRole(messages[index]) !== 'user') continue
    const text = textFromContent(messageContent(messages[index])).trim()
    if (text.length > 0) return index
  }
  return -1
}

export function toolUseNames(messages: readonly unknown[]): ReadonlySet<string> {
  const names = new Set<string>()
  for (const candidate of messages) {
    const content = messageContent(candidate)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      if (isRecord(block) && block.type === 'tool_use' && typeof block.name === 'string') {
        const input = isRecord(block.input) ? block.input : undefined
        names.add(typeof input?.tool_id === 'string' ? input.tool_id : block.name)
      }
    }
  }
  return names
}

export function latestAssistantText(messages: readonly Message[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messageRole(messages[index]) !== 'assistant') continue
    const text = textFromContent(messageContent(messages[index]))
    if (text.trim().length > 0) return text
  }
  return ''
}
