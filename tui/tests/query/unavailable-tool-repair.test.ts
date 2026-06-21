import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import { query } from '../../src/query.js'
import {
  buildUnavailableToolFinalAnswerBlockedText,
} from '../../src/query/unavailableToolRepair.js'
import type { Tools } from '../../src/Tool.js'
import type { Message } from '../../src/types/message.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import {
  allAssistantText,
  createNamedTool,
  queryParams,
} from './query-loop-visible-progress.helpers.js'

const MOVE_IN_PROMPT = '동네 전입신고에 필요한 서류를 확인해줘'
const INTERCITY_PUBLIC_TRANSPORT_PROMPT =
  '서울에서 대전까지 대중교통으로 이동한다고 가정하고, 버스나 지하철 관련 공공 교통 정보를 찾아줘.'

type AssistantOrUserMessage = Message & {
  readonly type: 'assistant' | 'user'
}

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

function createAdapterNotFoundFindTool(): Tools[number] {
  return {
    ...createNamedTool('find'),
    inputSchema: z.object({
      tool_id: z.string(),
      params: z.record(z.string(), z.unknown()).optional(),
    }),
    async validateInput(input) {
      return {
        result: false,
        message: `AdapterNotFound: '${input.tool_id}' is not in the synced backend manifest or the internal tools list.`,
      }
    },
  }
}

function messageText(message: Message): string {
  const content = message.message.content
  if (typeof content === 'string') return content
  return content
    .map(block => {
      if (block.type === 'text') return block.text
      if (block.type === 'tool_result' && typeof block.content === 'string') {
        return block.content
      }
      return ''
    })
    .filter(text => text.length > 0)
    .join('\n')
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

function textDeltaEvent(text: string): StreamTextDeltaEvent {
  return {
    type: 'stream_event',
    event: {
      type: 'content_block_delta',
      delta: { type: 'text_delta', text },
    },
  }
}

function createAdapterNotFoundDeps(
  onModelInput: (messages: readonly Message[]) => void,
) {
  let callCount = 0
  return {
    async *callModel(request: { readonly messages: readonly Message[] }) {
      callCount += 1
      onModelInput(request.messages)
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-gov-portal',
              name: 'find',
              input: {
                tool_id: 'gov_portal',
                params: { query: '전입신고 필요 서류' },
              },
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content:
          '전입신고에는 신분증, 임대차계약서, 세대주 확인서가 필요합니다. 주민센터에서 처리할 수 있습니다.',
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-unavailable-${callCount}`,
  }
}

function createPostUnavailableStreamingCandidateDeps(
  onModelInput: (messages: readonly Message[]) => void,
) {
  let callCount = 0
  const ungroundedCandidate =
    '사용 가능한 공공 서비스 안내: 서울고속버스터미널에서 대전복합터미널로 이동하면 됩니다.'
  return {
    async *callModel(request: { readonly messages: readonly Message[] }) {
      callCount += 1
      onModelInput(request.messages)
      yield textDeltaEvent(ungroundedCandidate)
      yield createAssistantMessage({ content: ungroundedCandidate })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-post-unavailable-stream-${callCount}`,
  }
}

function createInitialUnavailableIntercityDeps(
  onModelInput: (messages: readonly Message[]) => void,
) {
  let callCount = 0
  const ungroundedCandidate =
    '공공 교통 정보를 찾기 위해 먼저 서울의 출발지와 대전의 도착지 위치를 확인해야 합니다.'
  return {
    async *callModel(request: { readonly messages: readonly Message[] }) {
      callCount += 1
      onModelInput(request.messages)
      yield textDeltaEvent(ungroundedCandidate)
      yield createAssistantMessage({
        content: [
          { type: 'text', text: ungroundedCandidate },
          {
            type: 'tool_use',
            id: 'toolu-root-find',
            name: 'find',
            input: {
              tool_id: 'tago_bus_route_search',
              params: { query: '서울 대전 대중교통' },
            },
          },
        ],
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-initial-unavailable-intercity-${callCount}`,
  }
}

describe('unavailable tool repair boundary', () => {
  test('uses intercity transport handoff text for unavailable city-to-city public transport', () => {
    const visibleText = buildUnavailableToolFinalAnswerBlockedText(
      INTERCITY_PUBLIC_TRANSPORT_PROMPT,
    )

    expect(visibleText).toContain('서울-대전 같은 도시 간 대중교통')
    expect(visibleText).toContain('TAGO 고속버스정보')
    expect(visibleText).toContain('TAGO 시외버스정보')
    expect(visibleText).not.toContain('서류 목록')
  })

  test('blocks unverified final answers after primitive AdapterNotFound tool results', async () => {
    const mutableModelInputs: Message[][] = []
    const deps = createAdapterNotFoundDeps(messages => {
      mutableModelInputs.push([...messages])
    })

    const emitted: Message[] = []
    for await (const message of query({
      ...queryParams(MOVE_IN_PROMPT, [createAdapterNotFoundFindTool()], deps),
      messages: [createUserMessage({ content: MOVE_IN_PROMPT })],
      maxTurns: 4,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const modelInputText = mutableModelInputs
      .map(input => input.map(messageText).join('\n'))
      .join('\n')
    const visibleText = allAssistantText(emitted)
    expect(modelInputText).toContain("AdapterNotFound: 'gov_portal'")
    expect(modelInputText).toContain('Unavailable tool boundary')
    expect(visibleText).not.toContain('임대차계약서')
    expect(visibleText).toContain('현재 등록된 UMMAYA 도구로는')
  })

  test('withholds streamed unavailable-tool repair candidates until guard verdict', async () => {
    const mutableModelInputs: Message[][] = []
    const deps = createPostUnavailableStreamingCandidateDeps(messages => {
      mutableModelInputs.push([...messages])
    })
    const unavailableAssistant = createAssistantMessage({
      content: [
        {
          type: 'tool_use',
          id: 'toolu-tago-city-bus',
          name: 'find',
          input: {
            tool_id: 'tago_bus_route_search',
            params: { query: '서울 대전 대중교통' },
          },
        },
      ],
    })
    const messages = [
      createUserMessage({ content: INTERCITY_PUBLIC_TRANSPORT_PROMPT }),
      unavailableAssistant,
      createUserMessage({
        content: [
          {
            type: 'tool_result',
            tool_use_id: 'toolu-tago-city-bus',
            content: "AdapterNotFound: 'tago_bus_route_search' is not in the synced backend manifest or the internal tools list.",
            is_error: true,
          },
        ],
        sourceToolAssistantUUID: unavailableAssistant.uuid,
      }),
    ]

    const emitted: unknown[] = []
    for await (const message of query({
      ...queryParams(
        INTERCITY_PUBLIC_TRANSPORT_PROMPT,
        [createAdapterNotFoundFindTool()],
        deps,
      ),
      messages,
      maxTurns: 5,
    })) {
      if (isAssistantOrUserMessage(message) || isStreamTextDeltaEvent(message)) {
        emitted.push(message)
      }
    }

    const emittedMessages = emitted.filter(isAssistantOrUserMessage)
    const visibleText = allAssistantText(emittedMessages)
    const streamedPreview = emitted
      .filter(isStreamTextDeltaEvent)
      .map(event => event.event.delta.text)
      .join('')
    const modelInputText = mutableModelInputs
      .map(input => input.map(messageText).join('\n'))
      .join('\n')

    expect(modelInputText).toContain("AdapterNotFound: 'tago_bus_route_search'")
    expect(modelInputText).toContain('Unavailable tool boundary')
    expect(visibleText).not.toContain('서울고속버스터미널')
    expect(streamedPreview).not.toContain('서울고속버스터미널')
    expect(visibleText).toContain('서울-대전 같은 도시 간 대중교통')
  })

  test('blocks initial intercity tool-use when no intercity adapter is registered', async () => {
    const mutableModelInputs: Message[][] = []
    const deps = createInitialUnavailableIntercityDeps(messages => {
      mutableModelInputs.push([...messages])
    })

    const emitted: unknown[] = []
    for await (const message of query({
      ...queryParams(
        INTERCITY_PUBLIC_TRANSPORT_PROMPT,
        [createAdapterNotFoundFindTool()],
        deps,
      ),
      messages: [createUserMessage({ content: INTERCITY_PUBLIC_TRANSPORT_PROMPT })],
      maxTurns: 3,
    })) {
      if (isAssistantOrUserMessage(message) || isStreamTextDeltaEvent(message)) {
        emitted.push(message)
      }
    }

    const emittedMessages = emitted.filter(isAssistantOrUserMessage)
    const visibleText = allAssistantText(emittedMessages)
    const streamedPreview = emitted
      .filter(isStreamTextDeltaEvent)
      .map(event => event.event.delta.text)
      .join('')

    expect(mutableModelInputs).toHaveLength(1)
    expect(visibleText).not.toContain('Tool find is unavailable')
    expect(visibleText).not.toContain('출발지와 대전의 도착지')
    expect(streamedPreview).not.toContain('출발지와 대전의 도착지')
    expect(visibleText).toContain('서울-대전 같은 도시 간 대중교통')
  })
})
