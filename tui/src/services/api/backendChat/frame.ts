import type { ChatMessage, ChatRequestFrame } from '../../../ipc/frames.generated.js'

export function toNonEmptyMessages(
  messages: readonly ChatMessage[],
): ChatRequestFrame['messages'] {
  const [first, ...rest] = messages
  if (first === undefined) return [{ role: 'user', content: '' }]
  return [first, ...rest]
}
