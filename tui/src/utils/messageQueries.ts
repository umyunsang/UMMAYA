import type { AssistantMessage, Message } from '../types/message.js'

export function getLastAssistantMessage(
  messages: Message[],
): AssistantMessage | undefined {
  // Match the CC messages.ts helper while avoiding the large messages module
  // in Bun's Linux test loader.
  return messages.findLast(
    (msg): msg is AssistantMessage => msg.type === 'assistant',
  )
}
