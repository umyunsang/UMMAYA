import type { Tools } from '../Tool.js'
import type { AssistantMessage, Message, UserMessage } from '../types/message.js'
import * as messagesModule from './messages.js'

export function normalizeMessagesForAPI(
  messages: Message[],
  tools: Tools = [],
): (UserMessage | AssistantMessage)[] {
  return messagesModule.normalizeMessagesForAPI(messages, tools)
}
