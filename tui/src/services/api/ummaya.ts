import { randomUUID } from 'crypto'
import { APIUserAbortError } from 'src/sdk-compat.js'
import {
  getOrCreateUmmayaBridge,
  getUmmayaBridgeSessionId,
} from '../../ipc/bridgeSingleton.js'
import type {
  ChatRequestFrame,
  IPCFrame,
} from '../../ipc/frames.generated.js'
import { getToolDefinitionsForFrame } from '../../query/toolSerialization.js'
import { SYNTHETIC_MODEL } from '../../utils/messageText.js'
import { createAssistantMessage } from '../../utils/assistantMessageFactories.js'
import { buildChatMessagesFromTranscript } from '../../query/chatMessagesBuilder.js'
import { assertFriendliApiKeyForUse } from '../../utils/auth.js'

export async function* queryModelWithStreaming(params: {
  messages: readonly unknown[]
  systemPrompt: unknown
  thinkingConfig?: unknown
  tools?: unknown
  signal?: AbortSignal
  options?: { model?: string; querySource?: string; [k: string]: unknown }
}): AsyncGenerator<unknown> {
  const { messages, signal } = params
  assertFriendliApiKeyForUse()

  const correlationId = randomUUID()
  const messageUuid = randomUUID()
  const innerMessageId = randomUUID()
  const turnStartedAt = performance.now()
  const chatMessages = buildChatMessagesFromTranscript(messages)
  const bridge = getOrCreateUmmayaBridge()
  const sessionId = getUmmayaBridgeSessionId()
  const tools = await getToolDefinitionsForFrame()

  const frame: ChatRequestFrame = {
    session_id: sessionId,
    correlation_id: correlationId,
    ts: new Date().toISOString(),
    role: 'tui',
    kind: 'chat_request',
    messages: chatMessages as ChatRequestFrame['messages'],
    tools: tools as ChatRequestFrame['tools'],
  }

  yield { type: 'stream_request_start' as const }

  const sent = bridge.send(frame as unknown as IPCFrame)
  if (!sent) {
    throw new Error('UMMAYA bridge send failed (backend exited)')
  }

  let accumulated = ''
  const persistThinking = process.env.UMMAYA_PERSIST_THINKING === '1'
  let accumulatedThinking = ''
  let messageStartEmitted = false
  let nextContentBlockIndex = 0
  let textBlockIndex: number | null = null
  let textBlockStopped = false
  let thinkingBlockIndex: number | null = null
  let thinkingBlockStopped = false
  const pendingContentBlocks: Array<{
    type: 'tool_use'
    id: string
    name: string
    input: unknown
  }> = []

  const hasAssistantPayload = (): boolean =>
    accumulated.trimStart().length > 0 ||
    pendingContentBlocks.length > 0 ||
    (persistThinking && accumulatedThinking.length > 0)

  for await (const f of bridge.frames()) {
    if (signal?.aborted) {
      throw new APIUserAbortError()
    }

    const frameAny = f as {
      kind?: string
      correlation_id?: string
      delta?: string
      thinking?: string
      done?: boolean
      message?: string
      call_id?: string
      name?: string
      arguments?: unknown
      envelope?: { kind?: string; [k: string]: unknown }
    }

    if (frameAny.correlation_id !== correlationId) continue

    if (frameAny.kind === 'assistant_chunk') {
      const deltaText = frameAny.delta ?? ''
      const thinkingText = frameAny.thinking ?? ''

      if (!messageStartEmitted) {
        const ttftMs = performance.now() - turnStartedAt
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'message_start' as const,
            message: {
              id: innerMessageId,
              type: 'message',
              role: 'assistant',
              content: [],
              model: SYNTHETIC_MODEL,
              stop_reason: null,
              stop_sequence: null,
              usage: {
                input_tokens: 0,
                output_tokens: 0,
                cache_creation_input_tokens: 0,
                cache_read_input_tokens: 0,
              },
            },
          },
          ttftMs,
        }
        messageStartEmitted = true
      }
      if (thinkingText.length > 0 && thinkingBlockIndex === null) {
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'content_block_start' as const,
            index: nextContentBlockIndex,
            content_block: { type: 'thinking' as const, thinking: '' },
          },
        }
        thinkingBlockIndex = nextContentBlockIndex
        nextContentBlockIndex += 1
      }

      if (thinkingText.length > 0) {
        if (persistThinking) {
          accumulatedThinking += thinkingText
        }
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'content_block_delta' as const,
            index: thinkingBlockIndex ?? 0,
            delta: { type: 'thinking_delta' as const, thinking: thinkingText },
          },
        }
      }

      accumulated += deltaText
      if (deltaText.length > 0) {
        if (thinkingBlockIndex !== null && !thinkingBlockStopped) {
          yield {
            type: 'stream_event' as const,
            event: {
              type: 'content_block_stop' as const,
              index: thinkingBlockIndex,
            },
          }
          thinkingBlockStopped = true
        }
        if (textBlockIndex === null) {
          yield {
            type: 'stream_event' as const,
            event: {
              type: 'content_block_start' as const,
              index: nextContentBlockIndex,
              content_block: { type: 'text' as const, text: '' },
            },
          }
          textBlockIndex = nextContentBlockIndex
          nextContentBlockIndex += 1
        }
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'content_block_delta' as const,
            index: textBlockIndex,
            delta: { type: 'text_delta' as const, text: deltaText },
          },
        }
      }

      if (frameAny.done) {
        if (thinkingBlockIndex !== null && !thinkingBlockStopped) {
          yield {
            type: 'stream_event' as const,
            event: { type: 'content_block_stop' as const, index: thinkingBlockIndex },
          }
          thinkingBlockStopped = true
        }
        if (textBlockIndex !== null && !textBlockStopped) {
          yield {
            type: 'stream_event' as const,
            event: { type: 'content_block_stop' as const, index: textBlockIndex },
          }
          textBlockStopped = true
        }
        if (hasAssistantPayload() || !messageStartEmitted) {
          const finalMessage = createFinalAssistantMessage({
            accumulated,
            accumulatedThinking,
            messageUuid,
            innerMessageId,
            pendingContentBlocks,
            persistThinking,
          })
          yield finalMessage
        }
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'message_delta' as const,
            delta: { stop_reason: 'end_turn', stop_sequence: null },
            usage: { output_tokens: 0 },
          },
        }
        yield {
          type: 'stream_event' as const,
          event: { type: 'message_stop' as const },
        }
        return
      }
    } else if (frameAny.kind === 'tool_call') {
      if (!messageStartEmitted) {
        const ttftMs = performance.now() - turnStartedAt
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'message_start' as const,
            message: {
              id: innerMessageId,
              type: 'message',
              role: 'assistant',
              content: [],
              model: SYNTHETIC_MODEL,
              stop_reason: null,
              stop_sequence: null,
              usage: {
                input_tokens: 0,
                output_tokens: 0,
                cache_creation_input_tokens: 0,
                cache_read_input_tokens: 0,
              },
            },
          },
          ttftMs,
        }
        messageStartEmitted = true
      }
      if (thinkingBlockIndex !== null && !thinkingBlockStopped) {
        yield {
          type: 'stream_event' as const,
          event: { type: 'content_block_stop' as const, index: thinkingBlockIndex },
        }
        thinkingBlockStopped = true
      }
      if (textBlockIndex !== null && !textBlockStopped) {
        yield {
          type: 'stream_event' as const,
          event: { type: 'content_block_stop' as const, index: textBlockIndex },
        }
        textBlockStopped = true
      }
      const toolUseBlock = {
        type: 'tool_use' as const,
        id: frameAny.call_id ?? '',
        name: frameAny.name ?? '(unknown tool)',
        input: frameAny.arguments ?? {},
      }

      pendingContentBlocks.push(toolUseBlock)
      const toolBlockIndex = nextContentBlockIndex
      nextContentBlockIndex += 1

      yield {
        type: 'stream_event' as const,
        event: {
          type: 'content_block_start' as const,
          index: toolBlockIndex,
          content_block: toolUseBlock,
        },
      }
      yield {
        type: 'stream_event' as const,
        event: { type: 'content_block_stop' as const, index: toolBlockIndex },
      }

      yield createFinalAssistantMessage({
        accumulated,
        accumulatedThinking,
        messageUuid,
        innerMessageId,
        pendingContentBlocks,
        persistThinking,
      })
      yield {
        type: 'stream_event' as const,
        event: {
          type: 'message_delta' as const,
          delta: { stop_reason: 'tool_use', stop_sequence: null },
          usage: { output_tokens: 0 },
        },
      }
      yield {
        type: 'stream_event' as const,
        event: { type: 'message_stop' as const },
      }
      return
    } else if (frameAny.kind === 'error') {
      const reason = frameAny.message ?? 'UMMAYA backend error'
      yield createAssistantMessage({ content: `[UMMAYA backend error] ${reason}` })
      if (thinkingBlockIndex !== null && !thinkingBlockStopped) {
        yield {
          type: 'stream_event' as const,
          event: { type: 'content_block_stop' as const, index: thinkingBlockIndex },
        }
        thinkingBlockStopped = true
      }
      if (textBlockIndex !== null && !textBlockStopped) {
        yield {
          type: 'stream_event' as const,
          event: { type: 'content_block_stop' as const, index: textBlockIndex },
        }
        textBlockStopped = true
      }
      if (messageStartEmitted) {
        yield {
          type: 'stream_event' as const,
          event: { type: 'message_stop' as const },
        }
      }
      return
    }
  }

  if (hasAssistantPayload() || !messageStartEmitted) {
    yield createFinalAssistantMessage({
      accumulated,
      accumulatedThinking,
      messageUuid,
      innerMessageId,
      pendingContentBlocks,
      persistThinking,
    })
  }
  if (messageStartEmitted) {
    if (thinkingBlockIndex !== null && !thinkingBlockStopped) {
      yield {
        type: 'stream_event' as const,
        event: { type: 'content_block_stop' as const, index: thinkingBlockIndex },
      }
    }
    if (textBlockIndex !== null && !textBlockStopped) {
      yield {
        type: 'stream_event' as const,
        event: { type: 'content_block_stop' as const, index: textBlockIndex },
      }
    }
    yield {
      type: 'stream_event' as const,
      event: { type: 'message_stop' as const },
    }
  }
}

function createFinalAssistantMessage({
  accumulated,
  accumulatedThinking,
  messageUuid,
  innerMessageId,
  pendingContentBlocks,
  persistThinking,
}: {
  accumulated: string
  accumulatedThinking: string
  messageUuid: string
  innerMessageId: string
  pendingContentBlocks: Array<{
    type: 'tool_use'
    id: string
    name: string
    input: unknown
  }>
  persistThinking: boolean
}): unknown {
  const trimmedText = accumulated.trimStart()
  type AssistantBlock =
    | { type: 'thinking'; thinking: string }
    | { type: 'text'; text: string }
    | { type: 'tool_use'; id: string; name: string; input: unknown }

  const blocks: AssistantBlock[] = []
  if (persistThinking && accumulatedThinking.length > 0) {
    blocks.push({ type: 'thinking', thinking: accumulatedThinking })
  }
  if (trimmedText.length > 0) {
    blocks.push({ type: 'text', text: trimmedText })
  }
  for (const toolUse of pendingContentBlocks) {
    blocks.push(toolUse)
  }

  const finalContent =
    blocks.length > 0
      ? (blocks as Parameters<typeof createAssistantMessage>[0]['content'])
      : trimmedText

  const finalMessage = createAssistantMessage({ content: finalContent }) as {
    uuid: string
    message: { id: string }
  }
  finalMessage.uuid = messageUuid
  finalMessage.message.id = innerMessageId
  return finalMessage
}
