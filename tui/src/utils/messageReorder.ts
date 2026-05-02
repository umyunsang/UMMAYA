import type { ToolResultBlockParam, ToolUseBlockParam } from '../sdk-compat.js'
import type {
  AttachmentMessage,
  Message,
  NormalizedAssistantMessage,
  NormalizedUserMessage,
  SystemMessage,
} from '../types/message.js'

type ReorderableMessage =
  | NormalizedUserMessage
  | NormalizedAssistantMessage
  | AttachmentMessage
  | SystemMessage

type ToolUseRequestMessage = NormalizedAssistantMessage & {
  message: { content: [ToolUseBlockParam] }
}

type ToolUseResultMessage = NormalizedUserMessage & {
  message: { content: [ToolResultBlockParam] }
}

type HookAttachmentMessage = AttachmentMessage & {
  attachment: {
    type:
      | 'hook_blocking_error'
      | 'hook_cancelled'
      | 'hook_error_during_execution'
      | 'hook_non_blocking_error'
      | 'hook_success'
      | 'hook_system_message'
      | 'hook_additional_context'
      | 'hook_stopped_continuation'
    hookEvent: 'PreToolUse' | 'PostToolUse' | string
    toolUseID: string
  }
}

export function isToolUseRequestMessage(
  message: Message,
): message is ToolUseRequestMessage {
  return (
    message.type === 'assistant' &&
    // Note: stop_reason === 'tool_use' is unreliable -- it's not always set correctly.
    message.message.content.some(_ => _.type === 'tool_use')
  )
}

export function isToolUseResultMessage(
  message: Message,
): message is ToolUseResultMessage {
  return (
    message.type === 'user' &&
    ((Array.isArray(message.message.content) &&
      message.message.content[0]?.type === 'tool_result') ||
      Boolean(message.toolUseResult))
  )
}

function isHookAttachmentMessage(message: Message): message is HookAttachmentMessage {
  return (
    message.type === 'attachment' &&
    (message.attachment.type === 'hook_blocking_error' ||
      message.attachment.type === 'hook_cancelled' ||
      message.attachment.type === 'hook_error_during_execution' ||
      message.attachment.type === 'hook_non_blocking_error' ||
      message.attachment.type === 'hook_success' ||
      message.attachment.type === 'hook_system_message' ||
      message.attachment.type === 'hook_additional_context' ||
      message.attachment.type === 'hook_stopped_continuation')
  )
}

// Re-order, to move result messages to be after their tool use messages.
export function reorderMessagesInUI(
  messages: ReorderableMessage[],
  syntheticStreamingToolUseMessages: NormalizedAssistantMessage[],
): ReorderableMessage[] {
  const orderedMessages =
    syntheticStreamingToolUseMessages.length > 0
      ? [...messages, ...syntheticStreamingToolUseMessages]
      : messages

  // Maps tool use ID to its related messages.
  const toolUseGroups = new Map<
    string,
    {
      toolUse: ToolUseRequestMessage | null
      preHooks: AttachmentMessage[]
      toolResult: NormalizedUserMessage | null
      postHooks: AttachmentMessage[]
    }
  >()

  // First pass: group messages by tool use ID.
  for (const message of orderedMessages) {
    if (isToolUseRequestMessage(message)) {
      const toolUseID = message.message.content[0]?.id
      if (toolUseID) {
        if (!toolUseGroups.has(toolUseID)) {
          toolUseGroups.set(toolUseID, {
            toolUse: null,
            preHooks: [],
            toolResult: null,
            postHooks: [],
          })
        }
        toolUseGroups.get(toolUseID)!.toolUse = message
      }
      continue
    }

    if (
      isHookAttachmentMessage(message) &&
      message.attachment.hookEvent === 'PreToolUse'
    ) {
      const toolUseID = message.attachment.toolUseID
      if (!toolUseGroups.has(toolUseID)) {
        toolUseGroups.set(toolUseID, {
          toolUse: null,
          preHooks: [],
          toolResult: null,
          postHooks: [],
        })
      }
      toolUseGroups.get(toolUseID)!.preHooks.push(message)
      continue
    }

    if (
      message.type === 'user' &&
      message.message.content[0]?.type === 'tool_result'
    ) {
      const toolUseID = message.message.content[0].tool_use_id
      if (!toolUseGroups.has(toolUseID)) {
        toolUseGroups.set(toolUseID, {
          toolUse: null,
          preHooks: [],
          toolResult: null,
          postHooks: [],
        })
      }
      toolUseGroups.get(toolUseID)!.toolResult = message
      continue
    }

    if (
      isHookAttachmentMessage(message) &&
      message.attachment.hookEvent === 'PostToolUse'
    ) {
      const toolUseID = message.attachment.toolUseID
      if (!toolUseGroups.has(toolUseID)) {
        toolUseGroups.set(toolUseID, {
          toolUse: null,
          preHooks: [],
          toolResult: null,
          postHooks: [],
        })
      }
      toolUseGroups.get(toolUseID)!.postHooks.push(message)
      continue
    }
  }

  // Second pass: reconstruct the message list in the correct order.
  const result: ReorderableMessage[] = []
  const processedToolUses = new Set<string>()

  for (const message of orderedMessages) {
    if (isToolUseRequestMessage(message)) {
      const toolUseID = message.message.content[0]?.id
      if (toolUseID && !processedToolUses.has(toolUseID)) {
        processedToolUses.add(toolUseID)
        const group = toolUseGroups.get(toolUseID)
        if (group && group.toolUse) {
          result.push(group.toolUse)
          result.push(...group.preHooks)
          if (group.toolResult) {
            result.push(group.toolResult)
          }
          result.push(...group.postHooks)
        }
      }
      continue
    }

    if (
      isHookAttachmentMessage(message) &&
      (message.attachment.hookEvent === 'PreToolUse' ||
        message.attachment.hookEvent === 'PostToolUse')
    ) {
      continue
    }

    if (
      message.type === 'user' &&
      message.message.content[0]?.type === 'tool_result'
    ) {
      continue
    }

    if (message.type === 'system' && message.subtype === 'api_error') {
      const last = result.at(-1)
      if (last?.type === 'system' && last.subtype === 'api_error') {
        result[result.length - 1] = message
      } else {
        result.push(message)
      }
      continue
    }

    result.push(message)
  }

  const last = result.at(-1)
  return result.filter(
    _ => _.type !== 'system' || _.subtype !== 'api_error' || _ === last,
  )
}
