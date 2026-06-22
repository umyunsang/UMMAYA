import { describe, expect, test } from 'bun:test'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import {
  collectStream,
  toolResult,
  toolUse,
  visibleAndStreamedText,
} from './terminal-replacement-stream-deferral.helpers.js'

const WEATHER_PROMPT =
  '오늘 부산 사하구 날씨랑 미세먼지 상태를 확인해줘. 날씨와 대기질 출처를 나눠서 알려줘.'
const WELFARE_PROMPT =
  '부산 사하구에서 받을 수 있는 복지 지원이나 상담 창구를 확인해줘. 내가 1인 가구라고 가정해줘.'
const AED_PROMPT = '다대포해수욕장 근처 AED 위치를 찾아줘. 가장 가까운 곳부터 알려줘.'

function expectVisibleAndStreamed(params: {
  readonly emitted: readonly unknown[]
  readonly includes: readonly string[]
  readonly excludes: readonly string[]
}) {
  const { visible, streamed } = visibleAndStreamedText(params.emitted)
  for (const expected of params.includes) {
    expect(visible).toContain(expected)
    expect(streamed).toContain(expected)
  }
  for (const forbidden of params.excludes) {
    expect(visible).not.toContain(forbidden)
    expect(streamed).not.toContain(forbidden)
  }
}

describe('terminal replacement stream deferral', () => {
  test('withholds unsafe failed-tool final stream before guarded failure summary', async () => {
    const lookup = toolUse({
      id: 'toolu-welfare-find-failed-stream',
      name: 'mohw_welfare_eligibility_search',
      input: { search_wrd: '부산 사하구 복지 지원 상담' },
    })
    const { deps, emitted } = await collectStream({
      prompt: WELFARE_PROMPT,
      rawUnsafeFinal: [
        '복지 서비스 데이터베이스 검색에서 현재 데이터를 찾지 못하고 있습니다.',
        '권장 조치: 부산 사하구청 복지과 직접 문의, 복지로 사이트 방문, 부산광역시 복지통합콜센터 051-120.',
        '부산 사하구 1인 가구를 위한 일반적인 복지 지원 항목: 기초생활보장, 주거급여, 긴급복지지원.',
      ].join('\n\n'),
      messages: [
        createUserMessage({ content: WELFARE_PROMPT }),
        lookup,
        toolResult({
          assistant: lookup,
          id: 'toolu-welfare-find-failed-stream',
          isError: true,
          content: {
            ok: false,
            error: { message: "SSIS API error: resultCode='40' resultMessage='NO DATA FOUND'" },
          },
        }),
      ],
    })

    expect(deps.callCount()).toBe(1)
    expectVisibleAndStreamed({
      emitted,
      includes: ['mohw_welfare_eligibility_search 조회는 이번 턴에서 실패했습니다', 'NO DATA FOUND'],
      excludes: ['051-120', '기초생활보장'],
    })
  })

  test('withholds unsafe AED final stream before guarded NMC evidence summary', async () => {
    const lookup = toolUse({
      id: 'toolu-aed-success-stream',
      name: 'nmc_aed_site_locate',
      input: { origin_lat: 35.104448, origin_lon: 128.974933 },
    })
    const { deps, emitted } = await collectStream({
      prompt: AED_PROMPT,
      rawUnsafeFinal: '다대포해수욕장 근처 AED를 찾았습니다.\n1. 임의건물 AED (0.2km)\n- 연락처: 051-000-0000',
      messages: [
        createUserMessage({ content: AED_PROMPT }),
        lookup,
        toolResult({
          assistant: lookup,
          id: 'toolu-aed-success-stream',
          content: {
            ok: true,
            result: {
              kind: 'collection',
              items: [{
                record: {
                  org: '다대2동행정복지센터',
                  distance_km: '0.42',
                  buildAddress: '부산광역시 사하구 다대로530번길 7',
                  buildPlace: '1층 민원실',
                  clerkTel: '051-220-5361',
                },
              }],
            },
          },
        }),
      ],
    })

    expect(deps.callCount()).toBe(1)
    expectVisibleAndStreamed({
      emitted,
      includes: ['NMC AED adapter 결과 기준으로 확인된 값만 정리합니다', '다대2동행정복지센터 (0.42km)'],
      excludes: ['임의건물 AED', '051-000-0000'],
    })
  })

  test('withholds unsafe raw weather final stream before guarded evidence summary', async () => {
    const air = toolUse({ id: 'toolu-air', name: 'airkorea_ctprvn_air_quality', input: { sido_name: '부산' } })
    const kma = toolUse({ id: 'toolu-kma', name: 'kma_current_observation', input: { base_date: '20260620' } })
    const { deps, emitted } = await collectStream({
      prompt: WEATHER_PROMPT,
      rawUnsafeFinal: '부산 사하구 날씨 및 미세먼지 상태\n- 체감온도: -2.2°C\n- 시정: 1.5km\n대연동 측정소 PM10 24 (좋음)',
      messages: [
        createUserMessage({ content: WEATHER_PROMPT }),
        air,
        toolResult({
          assistant: air,
          id: 'toolu-air',
          content: {
            ok: true,
            result: {
              kind: 'collection',
              items: [{
                record: {
                  stationName: '광복동',
                  dataTime: '2026-06-15 18:00',
                  pm10Value: '23',
                  pm10GradeLabelKo: '좋음',
                  pm25Value: '11',
                  pm25GradeLabelKo: '좋음',
                },
              }],
            },
          },
        }),
        kma,
        toolResult({
          assistant: kma,
          id: 'toolu-kma',
          content: {
            ok: true,
            result: {
              kind: 'record',
              item: {
                base_date: '20260620',
                base_time: '1900',
                t1h: '23.9',
                rn1: '0',
                reh: '76',
                wsd: '3',
                vec: '274',
                pty: '0',
              },
            },
          },
        }),
      ],
    })

    expect(deps.callCount()).toBe(1)
    expectVisibleAndStreamed({
      emitted,
      includes: ['기상청 adapter 결과 기준으로 확인된 값만 정리합니다', 'AirKorea adapter 결과 기준으로 확인된 값만 정리합니다'],
      excludes: ['체감온도: -2.2°C', '시정: 1.5km', '대연동 측정소'],
    })
  })
})
