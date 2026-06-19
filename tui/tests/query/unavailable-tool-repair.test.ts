import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import { query } from '../../src/query.js'
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

describe('unavailable tool repair boundary', () => {
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
})
