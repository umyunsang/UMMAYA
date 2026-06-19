import { describe, expect, test } from 'bun:test'
import { query } from '../../src/query.js'
import type { Message } from '../../src/types/message.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import {
  allAssistantText,
  queryParams,
} from './query-loop-visible-progress.helpers.js'

const MOVE_IN_PROMPT = '동네 전입신고에 필요한 서류를 확인해줘'
const MALFORMED_TOOL_PROMPT =
  '잘못된 json {"tool":"lookup" 만 입력하면 어떻게 처리해?'

function createStaleMoveInDeps() {
  let callCount = 0
  return {
    async *callModel(request: { readonly messages: readonly Message[] }) {
      callCount += 1
      void request
      yield createAssistantMessage({
        content:
          '전입신고에는 신분증, 전입신고서, 세대주 확인 서류가 필요합니다.',
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-malformed-user-${callCount}`,
    callCount: () => callCount,
  }
}

function createAbortIgnoringDeps() {
  return {
    async *callModel(request: { readonly messages: readonly Message[] }) {
      void request
      yield createAssistantMessage({
        content: '이 응답은 취소 전에 생성되지 않아야 합니다.',
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => 'uuid-aborted-query',
  }
}

describe('query boundary cancellation and malformed tool text', () => {
  test('blocks malformed user-side tool JSON before stale prior context can answer', async () => {
    const deps = createStaleMoveInDeps()
    const emitted: Message[] = []

    for await (const message of query({
      ...queryParams(MALFORMED_TOOL_PROMPT, [], deps),
      messages: [
        createUserMessage({ content: MOVE_IN_PROMPT }),
        createAssistantMessage({
          content:
            '등록된 도구의 정상 tool_use 경계와 검증된 tool_result 없이 서류 목록이나 처리 결과를 단정하지 않겠습니다.',
        }),
        createUserMessage({ content: MALFORMED_TOOL_PROMPT }),
      ],
      maxTurns: 2,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const visibleText = allAssistantText(emitted)
    expect(deps.callCount()).toBe(0)
    expect(visibleText).toContain('유효하지 않은 도구 호출 형식')
    expect(visibleText).not.toContain('신분증')
    expect(visibleText).not.toContain('세대주 확인')
  })

  test('stops emitting provider events when the query abort signal is already tripped', async () => {
    const params = queryParams(
      '전국 응급실과 야간 약국을 가능한 한 많이 모두 찾아서 100개 표로 정리해줘',
      [],
      createAbortIgnoringDeps(),
    )
    const stream = query(params)

    const first = await stream.next()
    expect(first.done).toBe(false)
    params.toolUseContext.abortController.abort('user-cancel')

    const second = await stream.next()
    expect(second.done).toBe(true)
    expect(second.value).toEqual({ reason: 'aborted_streaming' })
  })
})
