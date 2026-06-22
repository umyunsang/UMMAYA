import { query } from '../../src/query.js'
import type { Message } from '../../src/types/message.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import {
  allAssistantText,
  queryParams,
} from './query-loop-visible-progress.helpers.js'

type StreamTextDeltaEvent = {
  readonly type: 'stream_event'
  readonly event: {
    readonly type: 'content_block_delta'
    readonly delta: {
      readonly type: 'text_delta'
      readonly text: string
    }
  }
}

type AssistantOrUserMessage = Message & {
  readonly type: 'assistant' | 'user'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isAssistantOrUserMessage(value: unknown): value is AssistantOrUserMessage {
  return isRecord(value) &&
    (value.type === 'assistant' || value.type === 'user')
}

function isStreamTextDeltaEvent(value: unknown): value is StreamTextDeltaEvent {
  if (!isRecord(value) || value.type !== 'stream_event') return false
  const event = value.event
  if (!isRecord(event) || event.type !== 'content_block_delta') return false
  const delta = event.delta
  return isRecord(delta) &&
    delta.type === 'text_delta' &&
    typeof delta.text === 'string'
}

function createRawFinalStreamDeps(rawUnsafeFinal: string) {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      yield {
        type: 'stream_event',
        event: {
          type: 'content_block_delta',
          delta: { type: 'text_delta', text: rawUnsafeFinal },
        },
      } satisfies StreamTextDeltaEvent
      yield createAssistantMessage({ content: rawUnsafeFinal })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-terminal-replacement-stream-${callCount}`,
    callCount: () => callCount,
  }
}

export function toolUse(params: {
  readonly id: string
  readonly name: string
  readonly input: Record<string, unknown>
}) {
  return createAssistantMessage({
    content: [
      {
        type: 'tool_use',
        id: params.id,
        name: params.name,
        input: params.input,
      },
    ],
  })
}

export function toolResult(params: {
  readonly assistant: ReturnType<typeof createAssistantMessage>
  readonly id: string
  readonly content: unknown
  readonly isError?: boolean
}) {
  return createUserMessage({
    content: [
      {
        type: 'tool_result',
        tool_use_id: params.id,
        content: JSON.stringify(params.content),
        is_error: params.isError,
      },
    ],
    sourceToolAssistantUUID: params.assistant.uuid,
  })
}

export async function collectStream(params: {
  readonly prompt: string
  readonly messages: readonly Message[]
  readonly rawUnsafeFinal: string
}) {
  const deps = createRawFinalStreamDeps(params.rawUnsafeFinal)
  const previousPreviewDelay = process.env.UMMAYA_TUI_SYNTHETIC_STREAM_DELAY_MS
  process.env.UMMAYA_TUI_SYNTHETIC_STREAM_DELAY_MS = '0'
  const emitted: unknown[] = []
  try {
    for await (const message of query({
      ...queryParams(params.prompt, [], deps),
      messages: params.messages,
      maxTurns: 1,
    })) {
      if (isAssistantOrUserMessage(message) || isStreamTextDeltaEvent(message)) {
        emitted.push(message)
      }
    }
  } finally {
    if (previousPreviewDelay === undefined) {
      delete process.env.UMMAYA_TUI_SYNTHETIC_STREAM_DELAY_MS
    } else {
      process.env.UMMAYA_TUI_SYNTHETIC_STREAM_DELAY_MS = previousPreviewDelay
    }
  }
  return { deps, emitted }
}

export function visibleAndStreamedText(emitted: readonly unknown[]) {
  const visible = allAssistantText(emitted.filter(isAssistantOrUserMessage))
  const streamed = emitted
    .filter(isStreamTextDeltaEvent)
    .map(event => event.event.delta.text)
    .join('')
  return { visible, streamed }
}
