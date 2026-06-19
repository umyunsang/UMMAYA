import { describe, expect, test } from 'bun:test'
import type { Message } from '../../../src/types/message.js'
import { createAssistantMessage } from '../../../src/utils/messages.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  getToolNames,
  ingestHealthLocationManifest,
  ingestMetarManifest,
  ingestUtilitySurfaceManifest,
  serializedMessages,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'
import { selectionTextWithPriorLocationContext } from '../../../src/services/api/ummaya/selectionContext.js'

function priorDadaeLocationWeatherMessages(): readonly Message[] {
  return [
    createUserMessage({ content: '다대1동 지금 날씨알려줘' }),
    createAssistantMessage({
      content: [{
        type: 'tool_use',
        id: 'toolu-prior-dadae-locate',
        name: 'kakao_address_search',
        input: { query: '다대1동' },
      }],
    }),
    createUserMessage({
      content: [{
        type: 'tool_result',
        tool_use_id: 'toolu-prior-dadae-locate',
        content: JSON.stringify({
          ok: true,
          result: {
            kind: 'region',
            region_1depth_name: '부산',
            region_2depth_name: '사하구',
            region_3depth_name: '다대1동',
            rdd_da: '2638060100',
            rdd_da_name: '부산 사하구 다대1동',
            lat: 35.059152,
            lon: 128.971316,
          },
        }),
      }],
    }),
    createAssistantMessage({
      content: '부산 사하구 다대1동의 현재 날씨입니다. 기온은 25.6도입니다.',
    }),
  ]
}

function priorDadaeLocationWeatherMessagesWithDispatchEnvelope(): readonly Message[] {
  return [
    createUserMessage({ content: '다대1동 지금 날씨알려줘' }),
    createAssistantMessage({
      content: [{
        type: 'tool_use',
        id: 'toolu-prior-dadae-locate',
        name: 'kakao_address_search',
        input: { query: '다대1동' },
      }],
    }),
    createUserMessage({
      content: [{
        type: 'tool_result',
        tool_use_id: 'toolu-prior-dadae-locate',
        content: JSON.stringify({
          ok: true,
          data: {
            status: 'ok',
            result: {
              kind: 'region',
              region_1depth_name: '부산',
              region_2depth_name: '사하구',
              region_3depth_name: '다대1동',
              rdd_da: '2638060100',
              rdd_da_name: '부산 사하구 다대1동',
              lat: 35.059152,
              lon: 128.971316,
            },
          },
        }),
      }],
    }),
    createAssistantMessage({
      content: '부산 사하구 다대1동의 현재 날씨입니다. 기온은 25.6도입니다.',
    }),
  ]
}

function priorFailedDadaeLocationMessages(): readonly Message[] {
  return [
    createUserMessage({ content: '다대1동 지금 날씨알려줘' }),
    createAssistantMessage({
      content: [{
        type: 'tool_use',
        id: 'toolu-prior-dadae-failed-locate',
        name: 'kakao_address_search',
        input: { query: '다대1동' },
      }],
    }),
    createUserMessage({
      content: [{
        type: 'tool_result',
        tool_use_id: 'toolu-prior-dadae-failed-locate',
        content: JSON.stringify({
          ok: false,
          error: 'upstream_timeout',
          result: {
            rdd_da_name: '부산 사하구 다대1동',
            lat: 35.059152,
            lon: 128.971316,
          },
        }),
      }],
    }),
    createAssistantMessage({
      content: '위치 조회가 완료되지 않아 날씨를 확인하지 못했습니다.',
    }),
  ]
}

describe('UMMAYA provider follow-up ER location context', () => {
  test('routes emergency follow-up to nmc_emergency_search and hira_hospital_search after a prior successful location turn', async () => {
    await withFriendliEnv(async () => {
      ingestHealthLocationManifest('t')
      try {
        const exchange = await captureProviderExchange({
          messages: [
            ...priorDadaeLocationWeatherMessages(),
            createUserMessage({
              content: '주위에 지금 바로 갈수있는 응급실 알려줘',
            }),
          ],
        })
        const toolNames = getToolNames(exchange.request)
        expect(toolNames).not.toContain('kakao_keyword_search')
        expect(toolNames).not.toContain('kakao_address_search')
        expect(toolNames).toContain('nmc_emergency_search')
        expect(toolNames).toContain('hira_hospital_search')
        expect(toolNames).not.toContain('find_hospital_by_location_rdd_da')
        expect(toolNames).not.toContain('emergency_facilities_search')
        expect(serializedMessages(exchange.request)).not.toContain(
          '[prior_location_context]',
        )
      } finally {
        ingestMetarManifest(undefined)
      }
    })
  })

  test('routes emergency follow-up to nmc_emergency_search and hira_hospital_search after a real dispatch-envelope prior result', async () => {
    await withFriendliEnv(async () => {
      ingestHealthLocationManifest('t')
      try {
        const exchange = await captureProviderExchange({
          messages: [
            ...priorDadaeLocationWeatherMessagesWithDispatchEnvelope(),
            createUserMessage({
              content: '주위에 지금 바로 갈수있는 응급실 알려줘',
            }),
          ],
        })
        const toolNames = getToolNames(exchange.request)
        expect(toolNames).not.toContain('kakao_keyword_search')
        expect(toolNames).not.toContain('kakao_address_search')
        expect(toolNames).toContain('nmc_emergency_search')
        expect(toolNames).toContain('hira_hospital_search')
        expect(toolNames).not.toContain('find_hospital_nearby')
        expect(toolNames).not.toContain('find_hospital_by_location_rdd_da')
        expect(toolNames).not.toContain('emergency_facilities_search')
        expect(serializedMessages(exchange.request)).not.toContain(
          '[prior_location_context]',
        )
      } finally {
        ingestMetarManifest(undefined)
      }
    })
  })

  test('stale_state keeps prior location out of unrelated relative utility follow-ups', async () => {
    await withFriendliEnv(async () => {
      ingestUtilitySurfaceManifest('u')
      try {
        const messages = [
          ...priorDadaeLocationWeatherMessages(),
          createUserMessage({
            content: '주위 전기요금 이번 달 고지서 확인해줘',
          }),
        ]
        expect(selectionTextWithPriorLocationContext(messages)).toBe(
          '주위 전기요금 이번 달 고지서 확인해줘',
        )
        const exchange = await captureProviderExchange({ messages })
        const toolNames = getToolNames(exchange.request)
        expect(toolNames).toContain('kepco_contract_power_usage')
        expect(toolNames).not.toContain('kakao_keyword_search')
        expect(toolNames).not.toContain('kakao_address_search')
        expect(toolNames).not.toContain('nmc_emergency_search')
        expect(toolNames).not.toContain('hira_hospital_search')
        expect(serializedMessages(exchange.request)).not.toContain(
          '[prior_location_context]',
        )
      } finally {
        ingestMetarManifest(undefined)
      }
    })
  })

  test('misleading_success_output does not reuse location-shaped failed results', () => {
    const messages = [
      ...priorFailedDadaeLocationMessages(),
      createUserMessage({
        content: '주위에 지금 바로 갈수있는 응급실 알려줘',
      }),
    ]

    expect(selectionTextWithPriorLocationContext(messages)).toBe(
      '주위에 지금 바로 갈수있는 응급실 알려줘',
    )
  })

  test('is_error tool_result wrapper does not seed prior_location_context from location-shaped JSON', () => {
    const messages: readonly Message[] = [
      createUserMessage({ content: '다대1동 지금 날씨알려줘' }),
      createAssistantMessage({
        content: [{
          type: 'tool_use',
          id: 'toolu-prior-dadae-wrapper-error-locate',
          name: 'kakao_address_search',
          input: { query: '다대1동' },
        }],
      }),
      createUserMessage({
        content: [{
          type: 'tool_result',
          tool_use_id: 'toolu-prior-dadae-wrapper-error-locate',
          is_error: true,
          content: JSON.stringify({
            ok: true,
            result: {
              rdd_da_name: '부산 사하구 다대1동',
              lat: 35.059152,
              lon: 128.971316,
            },
          }),
        }],
      }),
      createAssistantMessage({ content: '위치 조회가 완료되지 않아 날씨를 확인하지 못했습니다.' }),
      createUserMessage({ content: '주위에 지금 바로 갈수있는 응급실 알려줘' }),
    ]

    expect(selectionTextWithPriorLocationContext(messages)).toBe(
      '주위에 지금 바로 갈수있는 응급실 알려줘',
    )
  })
})
