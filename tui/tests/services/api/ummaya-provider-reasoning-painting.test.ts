import { describe, expect, test } from 'bun:test'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  ingestHealthLocationManifest,
  ingestMetarManifest,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

type ReasoningRawJsonToolResponseParams = {
  readonly name: string
  readonly arguments: Record<string, unknown>
  readonly reasoning: string
}

function responseForReasoningThenRawJsonToolCallText(
  params: ReasoningRawJsonToolResponseParams,
): Response {
  const encoder = new TextEncoder()
  const rawToolText = JSON.stringify({
    name: params.name,
    arguments: params.arguments,
  })
  const lines = [
    `data: {"id":"chatcmpl_reasoning_tool_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"reasoning_content":${JSON.stringify(params.reasoning)}}}]}`,
    `data: {"choices":[{"delta":{"content":${JSON.stringify(rawToolText)}}}]}`,
    'data: {"choices":[{"finish_reason":"stop","delta":{}}],"usage":{"prompt_tokens":11,"completion_tokens":7}}',
    'data: [DONE]',
  ]
  return new Response(new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(`${line}\n\n`))
      }
      controller.close()
    },
  }), {
    status: 200,
    headers: { 'content-type': 'text/event-stream', 'x-request-id': 'req_reasoning_tool_1' },
  })
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function eventText(event: unknown): string {
  return JSON.stringify(event)
}

function textDeltaFromEvent(event: unknown): string | undefined {
  if (!isRecord(event) || event.type !== 'stream_event') return undefined
  const payload = event.event
  if (!isRecord(payload) || payload.type !== 'content_block_delta') {
    return undefined
  }
  const delta = payload.delta
  if (!isRecord(delta) || delta.type !== 'text_delta') return undefined
  return typeof delta.text === 'string' ? delta.text : undefined
}

function expectReasoningBeforeRecoveredToolUse(params: {
  readonly events: readonly unknown[]
  readonly toolName: string
  readonly reasoning: string
  readonly rawToolText: string
}): void {
  const eventTexts = params.events.map(eventText)
  const reasoningIndex = eventTexts.findIndex(text =>
    text.includes('"type":"thinking_delta"') &&
    text.includes(params.reasoning),
  )
  const toolUseIndex = eventTexts.findIndex(text =>
    text.includes('"type":"assistant"') &&
    text.includes('"type":"tool_use"') &&
    text.includes(`"name":"${params.toolName}"`),
  )
  expect(reasoningIndex).toBeGreaterThanOrEqual(0)
  expect(toolUseIndex).toBeGreaterThan(reasoningIndex)
  expect(eventTexts.join('\n')).toContain('"type":"thinking"')
  expect(params.events.map(textDeltaFromEvent)).not.toContain(params.rawToolText)
}

async function withReasoningMode<T>(mode: string, run: () => Promise<T>): Promise<T> {
  const previous = process.env.UMMAYA_K_EXAONE_REASONING_MODE
  try {
    process.env.UMMAYA_K_EXAONE_REASONING_MODE = mode
    return await run()
  } finally {
    if (previous === undefined) {
      delete process.env.UMMAYA_K_EXAONE_REASONING_MODE
    } else {
      process.env.UMMAYA_K_EXAONE_REASONING_MODE = previous
    }
  }
}

describe('UMMAYA provider reasoning painting', () => {
  test('streams deep reasoning before recovered raw JSON tool calls', async () => {
    await withFriendliEnv(async () => {
      await withReasoningMode('deep', async () => {
        ingestHealthLocationManifest('u')
        const toolName = 'kakao_address_search'
        const toolArguments = { query: '동아대학교' }
        const reasoning = '위치 맥락을 먼저 확인합니다.'
        const rawToolText = JSON.stringify({
          name: toolName,
          arguments: toolArguments,
        })
        try {
          const exchange = await captureProviderExchange({
            messages: [createUserMessage({
              content: '동아대학교 승학캠퍼스 주위 야간 응급실을 알려줘',
            })],
            response: responseForReasoningThenRawJsonToolCallText({
              name: toolName,
              arguments: toolArguments,
              reasoning,
            }),
          })
          const requestText = JSON.stringify(exchange.request)
          expect(requestText).toContain('"enable_thinking":true')
          expect(requestText).toContain('"include_reasoning":true')

          expectReasoningBeforeRecoveredToolUse({
            events: exchange.events,
            toolName,
            reasoning,
            rawToolText,
          })
        } finally {
          ingestMetarManifest(undefined)
        }
      })
    })
  })

  test('streams deep reasoning before recovered unregistered raw JSON tool calls', async () => {
    await withFriendliEnv(async () => {
      await withReasoningMode('deep', async () => {
        ingestHealthLocationManifest('u')
        const toolName = 'find_hospital_by_location_rdd_da'
        const toolArguments = {
          location: '동아대학교 승학캠퍼스',
          radius_m: 5000,
        }
        const reasoning = '응급실 검색 도구 경계를 먼저 점검합니다.'
        const rawToolText = JSON.stringify({
          name: toolName,
          arguments: toolArguments,
        })
        try {
          const exchange = await captureProviderExchange({
            messages: [createUserMessage({
              content: '동아대학교 승학캠퍼스 주위 야간 응급실을 알려줘',
            })],
            response: responseForReasoningThenRawJsonToolCallText({
              name: toolName,
              arguments: toolArguments,
              reasoning,
            }),
          })
          const requestText = JSON.stringify(exchange.request)
          expect(requestText).toContain('"enable_thinking":true')
          expect(requestText).toContain('"include_reasoning":true')
          expect(requestText).not.toContain(toolName)

          expectReasoningBeforeRecoveredToolUse({
            events: exchange.events,
            toolName,
            reasoning,
            rawToolText,
          })
        } finally {
          ingestMetarManifest(undefined)
        }
      })
    })
  })

  test('does not fabricate thinking when reasoning mode is disabled', async () => {
    await withFriendliEnv(async () => {
      await withReasoningMode('fast', async () => {
        ingestHealthLocationManifest('u')
        const toolName = 'find_hospital_by_location_rdd_da'
        const toolArguments = {
          location: '동아대학교 승학캠퍼스',
          radius_m: 5000,
        }
        const rawToolText = JSON.stringify({
          name: toolName,
          arguments: toolArguments,
        })
        try {
          const exchange = await captureProviderExchange({
            messages: [createUserMessage({
              content: '동아대학교 승학캠퍼스 주위 야간 응급실을 알려줘',
            })],
            response: responseForReasoningThenRawJsonToolCallText({
              name: toolName,
              arguments: toolArguments,
              reasoning: '이 추론은 비활성 모드에서 표시되면 안 됩니다.',
            }),
          })
          const requestText = JSON.stringify(exchange.request)
          expect(requestText).toContain('"enable_thinking":false')
          expect(requestText).toContain('"include_reasoning":false')

          const eventTexts = exchange.events.map(eventText)
          expect(eventTexts.join('\n')).not.toContain('"type":"thinking_delta"')
          expect(eventTexts.join('\n')).not.toContain('"type":"thinking"')
          expect(eventTexts.join('\n')).toContain(`"name":"${toolName}"`)
          expect(exchange.events.map(textDeltaFromEvent)).not.toContain(rawToolText)
        } finally {
          ingestMetarManifest(undefined)
        }
      })
    })
  })
})
