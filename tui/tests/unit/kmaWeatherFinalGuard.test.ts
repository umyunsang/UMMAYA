import { afterEach, describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import { query } from '../../src/query.js'
import type { Message } from '../../src/types/message.js'
import type { Tools } from '../../src/Tool.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import {
  allAssistantText,
  createNamedTool,
  queryParams,
} from '../query/query-loop-visible-progress.helpers.js'

const PROMPT = '오늘 부산 사하구 날씨 알려줘'
const KST_OVERRIDE_ENV = 'UMMAYA_OVERRIDE_KST_TIME'

afterEach(() => {
  delete process.env[KST_OVERRIDE_ENV]
})

function createKmaCurrentObservationTool(): Tools[number] {
  const inputSchema = z.object({})
  return {
    ...createNamedTool('kma_current_observation'),
    inputSchema,
    async call() {
      return {
        data: {
          ok: true,
          result: {
            kind: 'record',
            item: {
              base_date: '20260620',
              base_time: '1100',
              t1h: 24.1,
              rn1: 0,
              reh: 89,
              wsd: 2.2,
              vec: 270,
              pty: 0,
            },
          },
        },
      }
    },
    mapToolResultToToolResultBlockParam(data, toolUseID) {
      return {
        type: 'tool_result',
        tool_use_id: toolUseID,
        content: JSON.stringify(data),
      }
    },
  }
}

function createKmaForecastTool(): Tools[number] {
  const inputSchema = z.object({})
  return {
    ...createNamedTool('kma_ultra_short_term_forecast'),
    inputSchema,
    async call() {
      return {
        data: {
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
                  category: 'SKY',
                  fcst_value: '1',
                },
                {
                  base_date: '20260620',
                  base_time: '1130',
                  fcst_date: '20260620',
                  fcst_time: '1200',
                  category: 'WSD',
                  fcst_value: '2.3',
                },
                {
                  base_date: '20260620',
                  base_time: '1130',
                  fcst_date: '20260620',
                  fcst_time: '1200',
                  category: 'VEC',
                  fcst_value: '230',
                },
              ],
            },
          },
        },
      }
    },
    mapToolResultToToolResultBlockParam(data, toolUseID) {
      return {
        type: 'tool_result',
        tool_use_id: toolUseID,
        content: JSON.stringify(data),
      }
    },
  }
}

function createKmaForecastFetchTimeseriesTool(): Tools[number] {
  const inputSchema = z.object({})
  return {
    ...createNamedTool('kma_forecast_fetch'),
    inputSchema,
    async call() {
      return {
        data: {
          ok: true,
          result: {
            kind: 'timeseries',
            points: [
              {
                timestamp_iso: '2026-06-20T15:00:00',
                temperature_c: 27,
                pop_pct: 30,
                precipitation_mm: '강수없음',
                sky_code: '4',
                base_date: '20260620',
                base_time: '1400',
              },
              {
                timestamp_iso: '2026-06-20T16:00:00',
                temperature_c: 27,
                pop_pct: 0,
                precipitation_mm: '강수없음',
                sky_code: '1',
                base_date: '20260620',
                base_time: '1400',
              },
            ],
          },
        },
      }
    },
    mapToolResultToToolResultBlockParam(data, toolUseID) {
      return {
        type: 'tool_result',
        tool_use_id: toolUseID,
        content: JSON.stringify(data),
      }
    },
  }
}

function createUnsupportedWeatherDeps(includeForecast: boolean) {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'text',
              text: '오늘 날짜는 2026년 4월 16일입니다. 오늘(2026년 3월 5일)의 현재 날씨를 확인하겠습니다. 오늘 날짜(2026년 1월 15일)와 현재 시간(14시 00분 기준)로 조회하겠습니다. 현재 시각이 14시 35경이므로 직전 정시인 14시를 기준 시간으로 하겠습니다. 현재 시스템 시각을 14시 이후로 가정하고, 1400 기준으로 확인하겠습니다.',
            },
            {
              type: 'tool_use',
              id: 'toolu-kma-current',
              name: 'kma_current_observation',
              input: {},
            },
          ],
        })
        return
      }
      if (includeForecast && callCount === 2) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-kma-forecast',
              name: 'kma_ultra_short_term_forecast',
              input: {},
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: [
          '현재 날씨 (2026년 6월 20일 11시 관측 기준):',
          '- 기온: 24.1°C',
          '- 하늘 상태: 맑음',
          '',
          '초단기예보:',
          '- 하늘 상태: 맑음',
        ].join('\n'),
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-kma-weather-final-guard-${callCount}`,
  }
}

function createForecastOnlySkyDeps() {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-kma-current',
              name: 'kma_current_observation',
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
              id: 'toolu-kma-forecast',
              name: 'kma_ultra_short_term_forecast',
              input: {},
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: [
          '현재 날씨:',
          '- 기온: 24.1°C',
          '- 습도: 89%',
          '',
          '초단기예보:',
          '- 하늘 상태: 맑음',
        ].join('\n'),
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-kma-weather-final-guard-forecast-only-${callCount}`,
  }
}

function createImplausibleWindDeps() {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-kma-current',
              name: 'kma_current_observation',
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
              id: 'toolu-kma-forecast',
              name: 'kma_ultra_short_term_forecast',
              input: {},
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: '예보 기준 풍속은 230m/s에서 333m/s 사이로 보통 바람입니다.',
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-kma-weather-final-guard-wind-${callCount}`,
  }
}

function createForecastFetchImplausibleWindDeps() {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-kma-current',
              name: 'kma_current_observation',
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
              id: 'toolu-kma-forecast-fetch',
              name: 'kma_forecast_fetch',
              input: {},
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: '예보 기준 풍속은 230m/s로 보통 바람입니다.',
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-kma-weather-final-guard-forecast-fetch-${callCount}`,
  }
}

function createNoEvidenceWeatherDeps() {
  return {
    async *callModel() {
      yield createAssistantMessage({
        content:
          '시간대별 예보는 어제 기준 시각 09:30이 맞는데 09:00 플랫폼 테스트로 내려갑니다. 1400 기준으로 확인하겠습니다.',
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => 'uuid-kma-weather-no-evidence',
  }
}

describe('KMA current-observation final answer guard', () => {
  test('replaces unsupported sky prose with current-observation-only answer', async () => {
    process.env[KST_OVERRIDE_ENV] = '2026-06-20T11:00:00+09:00'
    const emitted: Message[] = []
    for await (const message of query({
      ...queryParams(
        PROMPT,
        [createKmaCurrentObservationTool()],
        createUnsupportedWeatherDeps(false),
      ),
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const text = allAssistantText(emitted)
    expect(text).toContain('오늘 날짜는 2026년 6월 20일입니다')
    expect(text).toContain('오늘(2026년 6월 20일)의 현재 날씨')
    expect(text).toContain('오늘 날짜(2026년 6월 20일)와 현재 시간(11시 00분 기준)')
    expect(text).toContain('현재 시각은 11시 00분이므로 최근 발표 시각을 기준 시간')
    expect(text).toContain('현재 KST 시각 기준으로 최근 발표 기준으로 확인하겠습니다')
    expect(text).not.toContain('2026년 4월 16일')
    expect(text).not.toContain('2026년 3월 5일')
    expect(text).not.toContain('2026년 1월 15일')
    expect(text).not.toContain('14시 35')
    expect(text).not.toContain('14시 00분 기준')
    expect(text).not.toContain('현재 시스템 시각을 14시 이후로 가정')
    expect(text).not.toContain('1400 기준으로 확인하겠습니다')
    expect(text).not.toContain('직전 정시인 14시')
    expect(text).toContain('현재관측(2026-06-20 11:00)')
    expect(text).toContain('기온: 24.1°C')
    expect(text).toContain('하늘상태, 구름, 맑음/흐림, 강수확률')
    expect(text).not.toContain('약간 구름')
  })

  test('blocks unsupported sky prose in current section even when forecast exists', async () => {
    process.env[KST_OVERRIDE_ENV] = '2026-06-20T11:00:00+09:00'
    const emitted: Message[] = []
    for await (const message of query({
      ...queryParams(
        PROMPT,
        [createKmaCurrentObservationTool(), createKmaForecastTool()],
        createUnsupportedWeatherDeps(true),
      ),
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const text = allAssistantText(emitted)
    expect(text).toContain('현재관측(2026-06-20 11:00)')
    expect(text).toContain('예보 주요 시간대')
    expect(text).toContain('기온: 24.1°C')
    expect(text).not.toContain('- 하늘 상태: 맑음')
  })

  test('replaces implausible wind-speed prose with category-safe evidence summary', async () => {
    const emitted: Message[] = []
    for await (const message of query({
      ...queryParams(
        PROMPT,
        [createKmaCurrentObservationTool(), createKmaForecastTool()],
        createImplausibleWindDeps(),
      ),
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const text = allAssistantText(emitted)
    expect(text).toContain('기상청 adapter 결과 기준으로 확인된 값만 정리합니다')
    expect(text).toContain('풍속 2.3m/s')
    expect(text).toContain('KMA VEC는 풍향 각도이며 풍속으로 해석하지 않습니다')
    expect(text).not.toContain('230m/s')
    expect(text).not.toContain('333m/s')
  })

  test('summarizes kma_forecast_fetch timeseries evidence when replacing unsafe prose', async () => {
    const emitted: Message[] = []
    for await (const message of query({
      ...queryParams(
        PROMPT,
        [createKmaCurrentObservationTool(), createKmaForecastFetchTimeseriesTool()],
        createForecastFetchImplausibleWindDeps(),
      ),
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const text = allAssistantText(emitted)
    expect(text).toContain('예보 주요 시간대')
    expect(text).toContain(
      '2026-06-20 15:00: 기온 27°C, 강수확률 30%, 하늘 흐림, 강수량 강수없음',
    )
    expect(text).toContain(
      '2026-06-20 16:00: 기온 27°C, 강수확률 0%, 하늘 맑음, 강수량 강수없음',
    )
    expect(text).not.toContain('230m/s')
  })

  test('summarizes forecast evidence instead of yielding model forecast prose', async () => {
    const emitted: Message[] = []
    for await (const message of query({
      ...queryParams(
        PROMPT,
        [createKmaCurrentObservationTool(), createKmaForecastTool()],
        createForecastOnlySkyDeps(),
      ),
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const text = allAssistantText(emitted)
    expect(text).toContain('기상청 adapter 결과 기준으로 확인된 값만 정리합니다')
    expect(text).toContain('예보 주요 시간대')
    expect(text).toContain('하늘 맑음')
    expect(text).toContain('풍속 2.3m/s')
    expect(text).not.toContain('초단기예보:')
    expect(text).not.toContain('- 하늘 상태: 맑음')
    expect(text).not.toContain('하늘상태, 구름, 맑음/흐림, 강수확률')
  })

  test('blocks weather final answers when no KMA evidence exists in the current turn', async () => {
    const emitted: Message[] = []
    for await (const message of query({
      ...queryParams(PROMPT, [], createNoEvidenceWeatherDeps()),
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const text = allAssistantText(emitted)
    expect(text).toContain('KMA adapter 결과 없이 날씨/예보를 단정하지 않습니다')
    expect(text).not.toContain('어제 기준 시각 09:30')
    expect(text).not.toContain('1400 기준')
  })
})
