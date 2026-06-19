import { createAssistantMessage } from '../../../utils/assistantMessageFactories.js'
import type { PendingToolUseBlock } from './types.js'

type FinalAssistantBlock =
  | { readonly type: 'thinking'; readonly thinking: string }
  | { readonly type: 'text'; readonly text: string }
  | PendingToolUseBlock

export function createFinalAssistantMessage({
  accumulated,
  accumulatedThinking,
  messageUuid,
  innerMessageId,
  pendingContentBlocks,
  persistThinking,
}: {
  readonly accumulated: string
  readonly accumulatedThinking: string
  readonly messageUuid: string
  readonly innerMessageId: string
  readonly pendingContentBlocks: readonly PendingToolUseBlock[]
  readonly persistThinking: boolean
}): unknown {
  const trimmedText = accumulated.trimStart()
  const blocks: FinalAssistantBlock[] = []
  if (persistThinking && accumulatedThinking.length > 0) {
    blocks.push({ type: 'thinking', thinking: accumulatedThinking })
  }
  if (trimmedText.length > 0) {
    blocks.push({ type: 'text', text: trimmedText })
  }
  blocks.push(...pendingContentBlocks)

  const finalMessage = createAssistantMessage({
    content: blocks.length > 0 ? blocks : trimmedText,
  })
  finalMessage.uuid = messageUuid
  finalMessage.message.id = innerMessageId
  return finalMessage
}
