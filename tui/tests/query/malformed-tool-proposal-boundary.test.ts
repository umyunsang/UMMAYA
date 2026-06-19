import { describe, expect, test } from 'bun:test'
import { query } from '../../src/query.js'
import type { Message } from '../../src/types/message.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import {
  allAssistantText,
  queryParams,
} from './query-loop-visible-progress.helpers.js'

const PROMPT = '동네 전입신고에 필요한 서류를 확인해줘'

function createMalformedToolProposalDeps() {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      yield createAssistantMessage({
        content:
          '전입신고에 필요한 서류를 확인해 드리겠습니다.\n{"name": "check_sensitive_operation"',
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-malformed-tool-proposal-${callCount}`,
  }
}

describe('malformed textual tool proposal boundary', () => {
  test('blocks incomplete raw JSON tool proposals before visible rendering', async () => {
    const emitted: Message[] = []
    for await (const message of query({
      ...queryParams(PROMPT, [], createMalformedToolProposalDeps()),
      messages: [createUserMessage({ content: PROMPT })],
      maxTurns: 2,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    const visibleText = allAssistantText(emitted)
    expect(visibleText).not.toContain('{"name"')
    expect(visibleText).not.toContain('check_sensitive_operation')
    expect(visibleText).toContain('유효하지 않은 도구 호출 형식')
  })
})
