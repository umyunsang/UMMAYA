import type { UUID } from 'crypto'
import type {
  AssistantMessage,
  Message,
  NormalizedAssistantMessage,
  NormalizedMessage,
  NormalizedUserMessage,
  UserMessage,
} from '../types/message.js'
import { createUserMessage } from './userMessageFactories.js'

export function deriveUUID(parentUUID: UUID, index: number): UUID {
  const hex = index.toString(16).padStart(12, '0')
  return `${parentUUID.slice(0, 24)}${hex}` as UUID
}

export function normalizeMessages(
  messages: AssistantMessage[],
): NormalizedAssistantMessage[]
export function normalizeMessages(
  messages: UserMessage[],
): NormalizedUserMessage[]
export function normalizeMessages(
  messages: (AssistantMessage | UserMessage)[],
): (NormalizedAssistantMessage | NormalizedUserMessage)[]
export function normalizeMessages(messages: Message[]): NormalizedMessage[]
export function normalizeMessages(messages: Message[]): NormalizedMessage[] {
  let isNewChain = false
  return messages.flatMap(message => {
    switch (message.type) {
      case 'assistant': {
        isNewChain = isNewChain || message.message.content.length > 1
        return message.message.content.map((content, index) => {
          const uuid = isNewChain
            ? deriveUUID(message.uuid, index)
            : message.uuid
          return {
            type: 'assistant' as const,
            timestamp: message.timestamp,
            message: {
              ...message.message,
              content: [content],
              context_management: message.message.context_management ?? null,
            },
            isMeta: message.isMeta,
            isVirtual: message.isVirtual,
            requestId: message.requestId,
            uuid,
            error: message.error,
            isApiErrorMessage: message.isApiErrorMessage,
            advisorModel: message.advisorModel,
          } as NormalizedAssistantMessage
        })
      }
      case 'attachment':
        return [message]
      case 'progress':
        return [message]
      case 'system':
        return [message]
      case 'user': {
        if (typeof message.message.content === 'string') {
          const uuid = isNewChain ? deriveUUID(message.uuid, 0) : message.uuid
          return [
            {
              ...message,
              uuid,
              message: {
                ...message.message,
                content: [{ type: 'text', text: message.message.content }],
              },
            } as NormalizedMessage,
          ]
        }

        isNewChain = isNewChain || message.message.content.length > 1
        let imageIndex = 0
        return message.message.content.map((content, index) => {
          const isImage = content.type === 'image'
          const imageId =
            isImage && message.imagePasteIds
              ? message.imagePasteIds[imageIndex]
              : undefined
          if (isImage) imageIndex++
          return {
            ...createUserMessage({
              content: [content],
              toolUseResult: message.toolUseResult,
              mcpMeta: message.mcpMeta,
              isMeta: message.isMeta,
              isVisibleInTranscriptOnly: message.isVisibleInTranscriptOnly,
              isVirtual: message.isVirtual,
              timestamp: message.timestamp,
              imagePasteIds: imageId !== undefined ? [imageId] : undefined,
              origin: message.origin,
            }),
            uuid: isNewChain ? deriveUUID(message.uuid, index) : message.uuid,
          } as NormalizedMessage
        })
      }
    }
  })
}
