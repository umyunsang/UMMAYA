import { describe, expect, test } from 'bun:test'
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

const MOB003_PROMPT =
  '내일 김해공항에서 제주로 가는 항공편이 있는데 항공기상, 지연 위험, 공항 이동까지 확인하고 알림 설정해줘.'
const KMA_METAR_TOOL_NAME = 'kma_apihub_url_air_metar_decoded'
const ROOT_FIND_TOOL_NAME = 'find'
const KMA_ORDINARY_WEATHER_TOOL_NAMES = [
  'kma_apihub_upp_mtly_info_service_get_max_wind',
  'kma_current_observation',
  'kma_forecast_fetch',
  'kma_short_term_forecast',
  'kma_ultra_short_term_forecast',
] as const

type ProviderTurn = {
  readonly disabledProviderToolNames: readonly string[]
}

function createKmaMetarTool(params: {
  readonly onCall: (input: Record<string, unknown>) => void
  readonly data: unknown
}): Tools[number] {
  return {
    ...createNamedTool(KMA_METAR_TOOL_NAME),
    async call(input) {
      params.onCall(input)
      return { data: params.data }
    },
  }
}

function createKmaRepeatDeps(onProviderTurn: (turn: ProviderTurn) => void) {
  let callCount = 0
  return {
    async *callModel(request: {
      readonly options: { readonly disabledProviderToolNames?: readonly string[] }
    }) {
      callCount += 1
      onProviderTurn({
        disabledProviderToolNames:
          request.options.disabledProviderToolNames ?? [],
      })
      if (callCount < 3) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: `toolu-mob003-kma-${callCount}`,
              name: KMA_METAR_TOOL_NAME,
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
              '항공기상 확인 결과를 바탕으로 지연 위험은 낮음으로 안내하고, 알림 설정은 현재 수동 확인이 필요합니다.',
          },
        ],
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-mob003-${callCount}`,
  }
}

async function runMob003Prompt(params: {
  readonly tools: Tools
  readonly deps: ReturnType<typeof createKmaRepeatDeps>
}): Promise<readonly Message[]> {
  const emitted: Message[] = []
  for await (const message of query({
    ...queryParams(MOB003_PROMPT, params.tools, params.deps),
    messages: [createUserMessage({ content: MOB003_PROMPT })],
    maxTurns: 3,
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

describe('MOB-003 KMA aviation repeat guard', () => {
  test('blocks repeated decoded METAR dispatch after a successful aviation result', async () => {
    const providerTurns: ProviderTurn[] = []
    const toolInputs: Record<string, unknown>[] = []

    const emitted = await runMob003Prompt({
      tools: [
        createKmaMetarTool({
          onCall: input => {
            toolInputs.push(input)
          },
          data: {
            kind: 'record',
            item: {
              operation_id: 'air_metar_decoded',
              summary: {
                decoded_report: 'METAR RKPK 160900Z 18004KT 9999 FEW030 24/16 Q1012',
              },
            },
          },
        }),
      ],
      deps: createKmaRepeatDeps(turn => {
        providerTurns.push(turn)
      }),
    })

    expect(toolInputs).toEqual([{}])
    expect(providerTurns[1]?.disabledProviderToolNames).not.toContain(
      KMA_METAR_TOOL_NAME,
    )
    expect(toolResultText(emitted)).toContain(
      'KMA aviation lookup already returned usable METAR evidence',
    )
    expect(allAssistantText(emitted)).toContain('항공기상 확인 결과')
  })

  test('blocks repeated decoded METAR dispatch after a blocked aviation result', async () => {
    const providerTurns: ProviderTurn[] = []
    const toolInputs: Record<string, unknown>[] = []

    const emitted = await runMob003Prompt({
      tools: [
        createKmaMetarTool({
          onCall: input => {
            toolInputs.push(input)
          },
          data: {
            ok: false,
            error: {
              code: 'CONFIGURATION_ERROR',
              message: 'Missing required environment variable: UMMAYA_KMA_API_HUB_AUTH_KEY',
            },
          },
        }),
      ],
      deps: createKmaRepeatDeps(turn => {
        providerTurns.push(turn)
      }),
    })

    expect(toolInputs).toEqual([{}])
    expect(providerTurns[1]?.disabledProviderToolNames).not.toContain(
      KMA_METAR_TOOL_NAME,
    )
    expect(toolResultText(emitted)).toContain(
      'KMA aviation lookup already returned a blocked result',
    )
    expect(allAssistantText(emitted)).toContain('항공기상 확인 결과')
  })

  for (const ordinaryWeatherToolName of KMA_ORDINARY_WEATHER_TOOL_NAMES) {
    test(`blocks ${ordinaryWeatherToolName} fallback after airport aviation evidence`, async () => {
      const providerTurns: ProviderTurn[] = []
      const systemPrompts: readonly string[][] = []
      const metarInputs: Record<string, unknown>[] = []
      const ordinaryWeatherInputs: Record<string, unknown>[] = []
      const forecastTool = {
        ...createNamedTool(ordinaryWeatherToolName),
        async call(input: Record<string, unknown>) {
          ordinaryWeatherInputs.push(input)
          return {
            data:
              `Invalid parameters for tool ${ordinaryWeatherToolName}: missing lat, lon, base_date, base_time.`,
          }
        },
      }
      let callCount = 0
      const deps = {
        async *callModel(request: {
          readonly systemPrompt: readonly string[]
          readonly options: { readonly disabledProviderToolNames?: readonly string[] }
        }) {
          callCount += 1
          systemPrompts.push(request.systemPrompt)
          providerTurns.push({
            disabledProviderToolNames:
              request.options.disabledProviderToolNames ?? [],
          })
          if (callCount === 1) {
            yield createAssistantMessage({
              content: [
                {
                  type: 'tool_use',
                  id: 'toolu-mob003-metar',
                  name: KMA_METAR_TOOL_NAME,
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
                  id: 'toolu-mob003-forecast',
                  name: ordinaryWeatherToolName,
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
                  '항공기상 근거를 바탕으로 지연 위험과 알림 한계를 안정적으로 안내합니다.',
              },
            ],
          })
        },
        microcompact: async (messages: readonly Message[]) => ({ messages }),
        autocompact: async () => ({
          compactionResult: null,
          consecutiveFailures: undefined,
        }),
        uuid: () => `uuid-mob003-forecast-${callCount}`,
      }

      const emitted = await runMob003Prompt({
        tools: [
          createKmaMetarTool({
            onCall: input => {
              metarInputs.push(input)
            },
            data: {
              kind: 'record',
              item: {
                operation_id: 'air_metar_decoded',
                summary: {
                  decoded_report: 'METAR RKPK 160900Z 18004KT 9999 FEW030 24/16 Q1012',
                },
              },
            },
          }),
          forecastTool,
        ],
        deps,
      })

      expect(metarInputs).toEqual([{}])
      expect(ordinaryWeatherInputs).toEqual([])
      expect(providerTurns[1]?.disabledProviderToolNames).not.toContain(
        ordinaryWeatherToolName,
      )
      expect(providerTurns[1]?.disabledProviderToolNames).not.toContain(
        ROOT_FIND_TOOL_NAME,
      )
      expect(systemPrompts[1]?.join('\n')).toContain(
        'Do not ask the user for KMA nx/ny grid coordinates',
      )
      expect(toolResultText(emitted)).toContain(
        `Do not call ${ordinaryWeatherToolName} as a fallback for airport aviation weather`,
      )
      expect(allAssistantText(emitted)).toContain('항공기상 근거')
    })
  }

  test('blocks root find wrapper for non-aviation KMA fallback after airport aviation evidence', async () => {
    const metarInputs: Record<string, unknown>[] = []
    const rootFindInputs: Record<string, unknown>[] = []
    let callCount = 0
    const deps = {
      async *callModel() {
        callCount += 1
        if (callCount === 1) {
          yield createAssistantMessage({
            content: [
              {
                type: 'tool_use',
                id: 'toolu-mob003-metar',
                name: KMA_METAR_TOOL_NAME,
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
                id: 'toolu-mob003-root-find',
                name: ROOT_FIND_TOOL_NAME,
                input: {
                  tool_id: 'kma_apihub_upp_mtly_info_service_get_max_wind',
                },
              },
            ],
          })
          return
        }
        yield createAssistantMessage({
          content: [
            {
              type: 'text',
              text: '항공 METAR 근거만으로 지연 위험과 한계를 안내합니다.',
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-mob003-root-find-${callCount}`,
    }

    const emitted = await runMob003Prompt({
      tools: [
        createKmaMetarTool({
          onCall: input => {
            metarInputs.push(input)
          },
          data: {
            kind: 'record',
            item: {
              operation_id: 'air_metar_decoded',
              summary: {
                decoded_report: 'METAR RKPK 160900Z 18004KT 9999 FEW030 24/16 Q1012',
              },
            },
          },
        }),
        {
          ...createNamedTool(ROOT_FIND_TOOL_NAME),
          async call(input: Record<string, unknown>) {
            rootFindInputs.push(input)
            return { data: 'unexpected root find dispatch' }
          },
        },
      ],
      deps,
    })

    expect(metarInputs).toEqual([{}])
    expect(rootFindInputs).toEqual([])
    expect(toolResultText(emitted)).toContain(
      'Do not call kma_apihub_upp_mtly_info_service_get_max_wind as a fallback for airport aviation weather',
    )
    expect(allAssistantText(emitted)).toContain('항공기상 근거')
  })
})
