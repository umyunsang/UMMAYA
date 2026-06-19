import type { Message as MessageType } from '../../types/message.js'
import { extractTextContent } from '../../utils/messages.js'

export function extractPartialResult(
  messages: MessageType[],
): string | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages.at(i)
    if (message?.type !== 'assistant') continue
    const text = extractTextContent(message.message.content, '\n')
    if (text) {
      return text
    }
  }
  return undefined
}
