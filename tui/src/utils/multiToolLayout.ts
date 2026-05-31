type ContentBlockLike = {
  type: string
  id?: string
}

type LayoutMessageLike = {
  type: string
  isMeta?: boolean
  uuid?: string
  subtype?: string
  thinking?: string
  message?: {
    id?: string
    content: ContentBlockLike[]
  }
}

export const STREAMING_THINKING_LAYOUT_UUID = 'streaming-thinking'

export type StreamingThinkingLayoutMessage = LayoutMessageLike & {
  type: 'system'
  subtype: 'thinking'
  uuid: typeof STREAMING_THINKING_LAYOUT_UUID
  isMeta: true
  thinking: string
}

export function createStreamingThinkingLayoutMessage(thinking: string): StreamingThinkingLayoutMessage {
  return {
    type: 'system',
    subtype: 'thinking',
    uuid: STREAMING_THINKING_LAYOUT_UUID,
    isMeta: true,
    thinking,
  }
}

export function isStreamingThinkingLayoutMessage(
  msg: LayoutMessageLike | undefined,
): msg is StreamingThinkingLayoutMessage {
  return (
    msg?.type === 'system' &&
    msg.subtype === 'thinking' &&
    msg.uuid === STREAMING_THINKING_LAYOUT_UUID &&
    typeof msg.thinking === 'string'
  )
}

export function getAssistantToolUseBlock(msg: LayoutMessageLike | undefined): (ContentBlockLike & { type: 'tool_use'; id: string }) | null {
  if (msg?.type !== 'assistant') return null
  const block = msg.message?.content[0]
  return block?.type === 'tool_use' && typeof block.id === 'string'
    ? { ...block, type: 'tool_use', id: block.id }
    : null
}

export function isSameAssistantToolStack(
  prev: LayoutMessageLike | undefined,
  current: LayoutMessageLike,
  streamingToolUseIDs: ReadonlySet<string>,
): boolean {
  const prevTool = getAssistantToolUseBlock(prev)
  const currentTool = getAssistantToolUseBlock(current)
  if (!prevTool || !currentTool || prev?.type !== 'assistant' || current.type !== 'assistant') return false
  if (prev.message?.id && prev.message.id === current.message?.id) return true
  return streamingToolUseIDs.has(prevTool.id) && streamingToolUseIDs.has(currentTool.id)
}

function isUserTurnMessage(msg: LayoutMessageLike | undefined): boolean {
  if (msg?.type !== 'user' || msg.isMeta) return false
  return msg.message?.content[0]?.type !== 'tool_result'
}

function isToolUseLikeMessage(msg: LayoutMessageLike | undefined): boolean {
  return msg?.type === 'grouped_tool_use' || msg?.type === 'collapsed_read_search' || getAssistantToolUseBlock(msg) !== null
}

export function getStreamingThinkingInsertIndex(renderableMessages: readonly LayoutMessageLike[]): number {
  let lastUserIndex = -1
  for (let i = renderableMessages.length - 1; i >= 0; i--) {
    if (isUserTurnMessage(renderableMessages[i])) {
      lastUserIndex = i
      break
    }
  }
  for (let i = lastUserIndex + 1; i < renderableMessages.length; i++) {
    if (isToolUseLikeMessage(renderableMessages[i])) return i
  }
  return renderableMessages.length
}

export function insertStreamingThinkingLayoutMessage<T extends LayoutMessageLike>(
  renderableMessages: readonly T[],
  thinking: string | null | undefined,
): Array<T | StreamingThinkingLayoutMessage> {
  if (!thinking) return [...renderableMessages]
  const insertIndex = getStreamingThinkingInsertIndex(renderableMessages)
  return [
    ...renderableMessages.slice(0, insertIndex),
    createStreamingThinkingLayoutMessage(thinking),
    ...renderableMessages.slice(insertIndex),
  ]
}
