import { describe, expect, test } from 'bun:test'
import { query } from '../../src/query.js'
import type { Message, UserMessage } from '../../src/types/message.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import {
  createNamedTool,
  queryParams,
} from './query-loop-visible-progress.helpers.js'

const ID001_PROMPT =
  '모바일 신분증 발급하고 정부24랑 홈택스에서 쓸 수 있게 인증 수단도 연결해줘.'
const VERIFY_TOOL_NAME = 'mock_verify_module_modid'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function toolResultText(messages: readonly Message[]): string {
  return messages
    .flatMap(message => {
      if (message.type !== 'user') return []
      const content = message.message.content
      if (!Array.isArray(content)) return []
      return content.flatMap(block => {
        if (!isRecord(block) || block.type !== 'tool_result') return []
        return typeof block.content === 'string' ? [block.content] : []
      })
    })
    .join('\n')
}

function assistantText(messages: readonly Message[]): string {
  return messages
    .flatMap(message => {
      if (message.type !== 'assistant') return []
      const content = message.message.content
      if (!Array.isArray(content)) return []
      return content.flatMap(block => {
        if (!isRecord(block) || block.type !== 'text') return []
        return typeof block.text === 'string' ? [block.text] : []
      })
    })
    .join('\n')
}

describe('ID-001 permission-denied verify loop guard', () => {
  test('does not redispatch the same permission-denied verify tool', async () => {
    let providerCallCount = 0
    let verifyToolCallCount = 0
    const disabledProviderToolNamesByCall: string[][] = []
    const verifyTool = {
      ...createNamedTool(VERIFY_TOOL_NAME),
      async call() {
        verifyToolCallCount += 1
        return { data: 'Authentication rejected: permission_denied' }
      },
    }
    const deps = {
      async *callModel(params: {
        readonly options?: {
          readonly disabledProviderToolNames?: readonly string[]
        }
      }) {
        providerCallCount += 1
        disabledProviderToolNamesByCall.push([
          ...(params.options?.disabledProviderToolNames ?? []),
        ])
        yield createAssistantMessage({
          content:
            providerCallCount < 3
              ? [
                  {
                    type: 'tool_use',
                    id: `toolu-id001-verify-${providerCallCount}`,
                    name: VERIFY_TOOL_NAME,
                    input: {},
                  },
                ]
              : [
                  {
                    type: 'text',
                    text:
                      '인증이 거부되어 모바일 신분증 연결을 계속 진행할 수 없습니다. 사용자가 인증을 승인해야 합니다.',
                  },
                ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-id001-denied-${providerCallCount}`,
    }
    const emitted: Message[] = []

    for await (const message of query({
      ...queryParams(ID001_PROMPT, [verifyTool], deps),
      maxTurns: 3,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }
    const userMessages = emitted.filter(
      (message): message is UserMessage => message.type === 'user',
    )

    expect(verifyToolCallCount).toBe(1)
    expect(toolResultText(userMessages)).toContain(
      'Permission boundary blocked',
    )
    expect(disabledProviderToolNamesByCall[1]).toContain(VERIFY_TOOL_NAME)
    expect(assistantText(emitted)).toContain('인증이 거부되어')
  })
})
