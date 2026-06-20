import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import { query } from '../../src/query.js'
import type { Message } from '../../src/types/message.js'
import type { Tools } from '../../src/Tool.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import {
  allAssistantText,
  createNamedTool,
  queryParams,
} from './query-loop-visible-progress.helpers.js'

const MOB002_PROMPT =
  '내일 부산에서 서울 가는데 날씨, 도로 위험, 대중교통 지연까지 보고 가장 안전한 이동 방법 추천해줘.'
const KAKAO_ADDRESS_TOOL_NAME = 'kakao_address_search'
const KAKAO_KEYWORD_TOOL_NAME = 'kakao_keyword_search'
const KMA_GRID_WEATHER_TOOL_CASES = [
  {
    name: 'kma_short_term_forecast',
    failureText:
      'Invalid parameters for tool kma_short_term_forecast. Missing or invalid fields: base_date, base_time, nx, ny.',
  },
  {
    name: 'kma_ultra_short_term_forecast',
    failureText:
      'LOCATE FIRST: KMA grid parameters nx/ny and base_date/base_time are required before forecast lookup.',
  },
] as const

type ProviderTurn = {
  readonly disabledProviderToolNames: readonly string[]
}

function createKakaoTool(onCall: (input: Record<string, unknown>) => void): Tools[number] {
  const inputSchema = z.object({ query: z.string() })
  return {
    ...createNamedTool(KAKAO_ADDRESS_TOOL_NAME),
    inputSchema,
    async call(input) {
      onCall(input)
      return {
        data: {
          ok: true,
          kind: 'location',
          query: input.query,
          lat: 35.17982,
          lon: 129.075087,
        },
      }
    },
  }
}

function createKmaGridWeatherTool(params: {
  readonly name: string
  readonly failureText: string
  readonly onCall: (input: Record<string, unknown>) => void
}): Tools[number] {
  return {
    ...createNamedTool(params.name),
    async call(input) {
      params.onCall(input)
      return { data: params.failureText }
    },
  }
}

function createKakaoRepeatDeps(onProviderTurn: (turn: ProviderTurn) => void) {
  let callCount = 0
  return {
    async *callModel(request: {
      readonly messages: readonly Message[]
      readonly options: { readonly disabledProviderToolNames?: readonly string[] }
    }) {
      callCount += 1
      const disabledProviderToolNames =
        request.options.disabledProviderToolNames ?? []
      onProviderTurn({ disabledProviderToolNames })
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-mob002-first',
              name: KAKAO_ADDRESS_TOOL_NAME,
              input: {},
            },
          ],
        })
        return
      }
      if (toolResultText(request.messages).includes('Location lookup')) {
        yield createAssistantMessage({
          content: [
            {
              type: 'text',
              text:
                '위치 확인은 완료되었습니다. 날씨/도로/대중교통 실시간 연결은 제한되어 안전한 이동은 공식 교통 앱 확인 후 KTX를 우선 추천합니다.',
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: [
          {
            type: 'tool_use',
            id: `toolu-mob002-repeat-${callCount}`,
            name: KAKAO_ADDRESS_TOOL_NAME,
            input: {},
          },
        ],
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-mob002-${callCount}`,
  }
}

function createKakaoThenKmaGridRepeatDeps(params: {
  readonly kmaToolName: string
  readonly onProviderTurn: (turn: ProviderTurn) => void
}) {
  let callCount = 0
  return {
    async *callModel(request: {
      readonly options: { readonly disabledProviderToolNames?: readonly string[] }
    }) {
      callCount += 1
      const disabledProviderToolNames =
        request.options.disabledProviderToolNames ?? []
      params.onProviderTurn({ disabledProviderToolNames })
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-mob002-kakao-first',
              name: KAKAO_ADDRESS_TOOL_NAME,
              input: {},
            },
          ],
        })
        return
      }
      if (callCount === 2) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: `toolu-mob002-kma-first-${params.kmaToolName}`,
              name: params.kmaToolName,
              input: {},
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: [
          {
            type: 'text',
            text:
              '위치 확인은 완료됐지만 기상청 일반 예보 격자값이 없어 추가 입력 또는 공식 날씨/교통 채널 확인으로 넘깁니다.',
          },
        ],
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-mob002-kma-${callCount}`,
  }
}

function createKakaoThenKmaGridIgnoredDisableDeps(params: {
  readonly kmaToolName: string
  readonly onProviderTurn: (turn: ProviderTurn) => void
}) {
  let callCount = 0
  return {
    async *callModel(request: {
      readonly options: { readonly disabledProviderToolNames?: readonly string[] }
    }) {
      callCount += 1
      params.onProviderTurn({
        disabledProviderToolNames:
          request.options.disabledProviderToolNames ?? [],
      })
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-mob002-kakao-hardguard',
              name: KAKAO_ADDRESS_TOOL_NAME,
              input: {},
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: [
          {
            type: 'tool_use',
            id: `toolu-mob002-kma-hardguard-${callCount}`,
            name: params.kmaToolName,
            input: {},
          },
        ],
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-mob002-kma-hardguard-${callCount}`,
  }
}

function createKakaoThenSuccessfulKmaRepeatDeps(params: {
  readonly kmaToolName: string
  readonly onProviderTurn: (turn: ProviderTurn) => void
}) {
  let callCount = 0
  return {
    async *callModel(request: {
      readonly options: { readonly disabledProviderToolNames?: readonly string[] }
    }) {
      callCount += 1
      params.onProviderTurn({
        disabledProviderToolNames:
          request.options.disabledProviderToolNames ?? [],
      })
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-mob002-kakao-success-repeat',
              name: KAKAO_ADDRESS_TOOL_NAME,
              input: {},
            },
          ],
        })
        return
      }
      if (callCount <= 3) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: `toolu-mob002-kma-success-repeat-${callCount}`,
              name: params.kmaToolName,
              input: {},
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: [
          {
            type: 'text',
            text: '기상청 예보 결과를 확인했습니다.',
          },
        ],
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-mob002-kma-success-repeat-${callCount}`,
  }
}

async function runPromptWithDeps(params: {
  readonly tools: Tools
  readonly deps:
    | ReturnType<typeof createKakaoRepeatDeps>
    | ReturnType<typeof createKakaoThenKmaGridRepeatDeps>
    | ReturnType<typeof createKakaoThenKmaGridIgnoredDisableDeps>
    | ReturnType<typeof createKakaoThenSuccessfulKmaRepeatDeps>
}): Promise<readonly Message[]> {
  const emitted: Message[] = []
  for await (const message of query({
    ...queryParams(MOB002_PROMPT, params.tools, params.deps),
    messages: [createUserMessage({ content: MOB002_PROMPT })],
  })) {
    if (message.type === 'assistant' || message.type === 'user') {
      emitted.push(message)
    }
  }
  return emitted
}

function toolResultText(messages: readonly Message[]): string {
  return messages
    .flatMap(message => {
      const content = message.message.content
      if (!Array.isArray(content)) return []
      return content.flatMap(block => {
        if (
          typeof block !== 'object' ||
          block === null ||
          !('type' in block) ||
          block.type !== 'tool_result' ||
          !('content' in block) ||
          typeof block.content !== 'string'
        ) {
          return []
        }
        return [block.content]
      })
    })
    .join('\n')
}

describe('MOB-002 Kakao continuation guard', () => {
  test('keeps Kakao location adapters exposed while blocking same-query repeat dispatch', async () => {
    // Given: the provider repeats Kakao location after a same-query success.
    const providerTurns: ProviderTurn[] = []
    const toolInputs: Record<string, unknown>[] = []

    // When: a MOB-002 turn gets one successful Kakao location result.
    const emitted = await runPromptWithDeps({
      tools: [createKakaoTool(input => {
        toolInputs.push(input)
      })],
      deps: createKakaoRepeatDeps(turn => {
        providerTurns.push(turn)
      }),
    })

    // Then: the provider surface stays available, but the same-query repeat is blocked at dispatch.
    expect(toolInputs).toEqual([{ query: '부산' }])
    expect(providerTurns[1]?.disabledProviderToolNames).not.toContain(
      KAKAO_ADDRESS_TOOL_NAME,
    )
    expect(providerTurns[1]?.disabledProviderToolNames).not.toContain(
      KAKAO_KEYWORD_TOOL_NAME,
    )
    expect(toolResultText(emitted)).toContain('Location lookup')
    expect(allAssistantText(emitted)).toContain('위치 확인은 완료되었습니다')
  })

  test('allows same Kakao adapter for different origin and destination queries', async () => {
    const providerTurns: ProviderTurn[] = []
    const toolInputs: Record<string, unknown>[] = []
    let callCount = 0
    const deps = {
      async *callModel(request: {
        readonly options: { readonly disabledProviderToolNames?: readonly string[] }
      }) {
        callCount += 1
        providerTurns.push({
          disabledProviderToolNames:
            request.options.disabledProviderToolNames ?? [],
        })
        if (callCount === 1) {
          yield createAssistantMessage({
            content: [
              {
                type: 'tool_use',
                id: 'toolu-mob002-origin',
                name: KAKAO_ADDRESS_TOOL_NAME,
                input: { query: '부산역' },
              },
            ],
          })
          return
        }
        if (callCount === 2) {
          yield createAssistantMessage({
            content: [
              {
                type: 'tool_use',
                id: 'toolu-mob002-destination',
                name: KAKAO_ADDRESS_TOOL_NAME,
                input: { query: '해운대역' },
              },
            ],
          })
          return
        }
        yield createAssistantMessage({
          content: [
            {
              type: 'text',
              text: '부산역과 해운대역 위치를 각각 확인했습니다.',
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
      uuid: () => `uuid-mob002-origin-destination-${callCount}`,
    }

    const emitted = await runPromptWithDeps({
      tools: [createKakaoTool(input => {
        toolInputs.push(input)
      })],
      deps,
    })

    expect(toolInputs).toEqual([{ query: '부산역' }, { query: '해운대역' }])
    expect(providerTurns[1]?.disabledProviderToolNames).not.toContain(
      KAKAO_ADDRESS_TOOL_NAME,
    )
    expect(toolResultText(emitted)).not.toContain('Location lookup')
    expect(allAssistantText(emitted)).toContain('부산역과 해운대역')
  })

  for (const kmaCase of KMA_GRID_WEATHER_TOOL_CASES) {
    test(`keeps ${kmaCase.name} exposed after grid-missing result and finishes from repair prompt`, async () => {
      // Given: Kakao already resolved the route location, then ordinary KMA grid lookup fails.
      const providerTurns: ProviderTurn[] = []
      const kakaoInputs: Record<string, unknown>[] = []
      const kmaInputs: Record<string, unknown>[] = []

      // When: the provider would repeat the same ordinary KMA weather tool unless disabled.
      const emitted = await runPromptWithDeps({
        tools: [
          createKakaoTool(input => {
            kakaoInputs.push(input)
          }),
          createKmaGridWeatherTool({
            name: kmaCase.name,
            failureText: kmaCase.failureText,
            onCall: input => {
              kmaInputs.push(input)
            },
          }),
        ],
        deps: createKakaoThenKmaGridRepeatDeps({
          kmaToolName: kmaCase.name,
          onProviderTurn: turn => {
            providerTurns.push(turn)
          },
        }),
      })

      // Then: the next model turn still sees the tool surface and finishes without a second dispatch.
      expect(kakaoInputs).toEqual([{ query: '부산' }])
      expect(kmaInputs).toEqual([{}])
      expect(providerTurns).toHaveLength(3)
      expect(providerTurns[2]?.disabledProviderToolNames).not.toContain(kmaCase.name)
      expect(allAssistantText(emitted)).toContain('격자값이 없어')
    })
  }

  test('blocks repeated ordinary KMA dispatch after grid-missing even when provider retries', async () => {
    // Given: the provider ignores disabled-tool hints after Kakao and a KMA grid error.
    const providerTurns: ProviderTurn[] = []
    const kakaoInputs: Record<string, unknown>[] = []
    const kmaInputs: Record<string, unknown>[] = []

    // When: the provider asks for the same ordinary KMA forecast again.
    const emitted = await runPromptWithDeps({
      tools: [
        createKakaoTool(input => {
          kakaoInputs.push(input)
        }),
        createKmaGridWeatherTool({
          name: 'kma_short_term_forecast',
          failureText:
            'Missing or invalid fields: base_date, base_time, nx, ny',
          onCall: input => {
            kmaInputs.push(input)
          },
        }),
      ],
      deps: createKakaoThenKmaGridIgnoredDisableDeps({
        kmaToolName: 'kma_short_term_forecast',
        onProviderTurn: turn => {
          providerTurns.push(turn)
        },
      }),
    })

    // Then: the guard returns a stable Korean handoff instead of dispatching the repeated KMA call.
    expect(kakaoInputs).toEqual([{ query: '부산' }])
    expect(kmaInputs).toEqual([{}])
    expect(providerTurns).toHaveLength(3)
    expect(toolResultText(emitted)).toContain(
      'Do not repeat ordinary KMA current or forecast tools',
    )
    expect(allAssistantText(emitted)).toContain('KMA 일반 날씨 도구를 반복 호출하지 않습니다')
  })

  test('does not classify successful KMA base_date and base_time fields as grid failure', async () => {
    const providerTurns: ProviderTurn[] = []
    const kakaoInputs: Record<string, unknown>[] = []
    const kmaInputs: Record<string, unknown>[] = []

    const emitted = await runPromptWithDeps({
      tools: [
        createKakaoTool(input => {
          kakaoInputs.push(input)
        }),
        createKmaGridWeatherTool({
          name: 'kma_ultra_short_term_forecast',
          failureText: JSON.stringify({
            ok: true,
            result: {
              kind: 'record',
              item: {
                total_count: 1,
                items: [
                  {
                    base_date: '20260620',
                    base_time: '1130',
                    fcst_date: '20260620',
                    fcst_time: '1200',
                    nx: 97,
                    ny: 75,
                    category: 'TMP',
                    fcst_value: '24',
                  },
                ],
              },
            },
          }),
          onCall: input => {
            kmaInputs.push(input)
          },
        }),
      ],
      deps: createKakaoThenSuccessfulKmaRepeatDeps({
        kmaToolName: 'kma_ultra_short_term_forecast',
        onProviderTurn: turn => {
          providerTurns.push(turn)
        },
      }),
    })

    expect(kakaoInputs).toEqual([{ query: '부산' }])
    expect(kmaInputs).toHaveLength(2)
    expect(providerTurns).toHaveLength(4)
    expect(toolResultText(emitted)).not.toContain(
      'Do not repeat ordinary KMA current or forecast tools',
    )
    expect(allAssistantText(emitted)).toContain('기상청 adapter 결과 기준으로 확인된 값만 정리합니다')
    expect(allAssistantText(emitted)).toContain('2026-06-20 12:00: 기온 24°C')
  })
})
