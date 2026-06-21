import { describe, expect, test } from 'bun:test'
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

const PROMPT = '다대포해수욕장 근처 AED 위치를 찾아줘. 가장 가까운 곳부터 알려줘.'
const NMC_AED_TOOL_NAME = 'nmc_aed_site_locate'

function createKakaoKeywordTool(): Tools[number] {
  const inputSchema = z.object({ query: z.string() })
  return {
    ...createNamedTool('kakao_keyword_search'),
    inputSchema,
    async call() {
      return {
        data: {
          ok: true,
          result: {
            kind: 'poi',
            name: '다대포해수욕장',
            lat: 35.0465263488422,
            lon: 128.962741189119,
            source: 'kakao',
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

function createNmcAedTool(): Tools[number] {
  const inputSchema = z.object({
    q0: z.string(),
    q1: z.string(),
    origin_lat: z.number().optional(),
    origin_lon: z.number().optional(),
  })
  return {
    ...createNamedTool(NMC_AED_TOOL_NAME),
    inputSchema,
    async call() {
      return {
        data: {
          ok: true,
          result: {
            kind: 'collection',
            items: [
              {
                record: {
                  org: '다대성원아파트',
                  buildAddress: '부산광역시 사하구 다대낙조1길 42(다대동, 성원아파트)',
                  buildPlace: '102동 경비실앞',
                  clerkTel: '051-264-2820',
                  monSttTme: '0700',
                  monEndTme: '2200',
                  model: 'NT-3810',
                  distance_km: 0.543,
                },
              },
              {
                record: {
                  org: '도시몰운대아파트',
                  buildAddress: '부산광역시 사하구 다대낙조2길 12(다대동, 도시몰운대아파트)',
                  buildPlace: '105동 경비실 입구',
                  clerkTel: '2623585',
                  monSttTme: '0000',
                  monEndTme: '2400',
                  model: 'HeartOn A16-GF',
                  distance_km: 0.645,
                },
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

function createBadFinalDeps() {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-kakao-dadaepo',
              name: 'kakao_keyword_search',
              input: {
                query: '다대포해수욕장',
              },
            },
          ],
        })
        return
      }
      yield callCount === 2
        ? createAssistantMessage({
            content: [
              {
                type: 'tool_use',
                id: 'toolu-nmc-aed',
                name: NMC_AED_TOOL_NAME,
                input: {
                  q0: '부산광역시',
                  q1: '사하구',
                },
              },
            ],
          })
        : createAssistantMessage({
            content: '도시몰운대아파트가 가장 가깝고 다대성원아파트는 6.12km입니다.',
          })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-nmc-aed-final-guard-${callCount}`,
  }
}

describe('NMC AED final answer guard', () => {
  test('replaces model prose with tool-result distance order', async () => {
    const emitted: Message[] = []
    for await (const message of query(
      queryParams(PROMPT, [createKakaoKeywordTool(), createNmcAedTool()], createBadFinalDeps()),
    )) {
      if (message.type === 'assistant' || message.type === 'user') emitted.push(message)
    }

    const text = allAssistantText(emitted)
    expect(text).toContain('NMC AED adapter 결과 기준으로 확인된 값만 정리합니다')
    expect(text).toContain('1. 다대성원아파트 (0.543km)')
    expect(text).toContain('2. 도시몰운대아파트 (0.645km)')
    expect(text).not.toContain('6.12km')
    expect(text.indexOf('다대성원아파트')).toBeLessThan(text.indexOf('도시몰운대아파트'))
  })
})
