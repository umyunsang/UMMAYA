import { describe, expect, test } from 'bun:test'
import type { Message } from '../../src/types/message.js'
import { query } from '../../src/query.js'
import {
  createAssistantMessage,
  createUserMessage,
} from '../../src/utils/messages.js'
import {
  allAssistantText,
  createNamedTool,
  queryParams,
} from './query-loop-visible-progress.helpers.js'

const CIV002_PROMPT =
  '아기가 태어났어. 출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 등록까지 도와줘.'
const TAX001_PROMPT =
  '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.'
const ADAPTERLESS_FIND_FAILURE =
  "Error: find(mode='fetch') requires a concrete adapter tool_id from the current available adapter set. No concrete adapter was selected."
const MALFORMED_ADAPTERLESS_FIND_FAILURE =
  "Find failed: Invalid parameters for tool 'find'. Missing or invalid fields: tool_id. Field required."

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

function createTax001AdapterlessFindFailureHistory(
  nextPrompt: string,
  failureText = ADAPTERLESS_FIND_FAILURE,
): readonly Message[] {
  const assistant = createAssistantMessage({
    content: [
      {
        type: 'tool_use',
        id: 'toolu-tax001-adapterless-root-find',
        name: 'find',
        input: { mode: 'fetch' },
      },
    ],
  })
  return [
    createUserMessage({ content: TAX001_PROMPT }),
    assistant,
    createUserMessage({
      content: [
        {
          type: 'tool_result',
          tool_use_id: 'toolu-tax001-adapterless-root-find',
          content: failureText,
          is_error: true,
        },
      ],
      toolUseResult: failureText,
      sourceToolAssistantUUID: assistant.uuid,
    }),
    createUserMessage({ content: nextPrompt }),
  ]
}

describe('adapterless root find repeat guard', () => {
  test('blocks workspace read summary when CIV-002 follows TAX-001 adapterless find failure', async () => {
    // Given: a session has already seen a root find failure without a concrete adapter.
    let providerCallCount = 0
    const deps = {
      async *callModel() {
        providerCallCount += 1
        yield createAssistantMessage({
          content: [
            {
              type: 'text',
              text:
                'Read 1 file (ctrl+o to expand)\n정부24 주민등록등본 발급 절차를 정리했습니다.',
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-multiprompt-leak-${providerCallCount}`,
    }
    const emitted: Message[] = []

    // When: the next prompt is a fresh CIV-002 public-service request.
    for await (const message of query({
      ...queryParams(CIV002_PROMPT, [], deps),
      messages: createTax001AdapterlessFindFailureHistory(CIV002_PROMPT),
      maxTurns: 1,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    // Then: workspace-support summary text is blocked across the prompt boundary.
    expect(providerCallCount).toBe(1)
    expect(allAssistantText(emitted)).not.toContain('Read 1 file')
    expect(allAssistantText(emitted)).toContain(
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    )
  })

  test('blocks workspace read summary when CIV-002 follows malformed TAX-001 adapterless find failure', async () => {
    // Given: a previous public-service turn failed root find parameter validation before a fresh citizen prompt.
    let providerCallCount = 0
    const deps = {
      async *callModel() {
        providerCallCount += 1
        yield createAssistantMessage({
          content: [
            {
              type: 'text',
              text:
                'Read 1 file (ctrl+o to expand)\n정부24 주민등록등본 발급 절차를 정리했습니다.',
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-malformed-multiprompt-leak-${providerCallCount}`,
    }
    const emitted: Message[] = []

    // When: the next prompt is CIV-002 and the assistant tries to reuse workspace-read summary text.
    for await (const message of query({
      ...queryParams(CIV002_PROMPT, [], deps),
      messages: createTax001AdapterlessFindFailureHistory(
        CIV002_PROMPT,
        MALFORMED_ADAPTERLESS_FIND_FAILURE,
      ),
      maxTurns: 1,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    // Then: malformed adapterless state is treated like the canonical root-find failure.
    expect(providerCallCount).toBe(1)
    expect(allAssistantText(emitted)).not.toContain('Read 1 file')
    expect(allAssistantText(emitted)).toContain(
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    )
  })

  test('allows explicit workspace read after stale TAX-001 adapterless find failure', async () => {
    // Given: adapterless public-service state exists before a later local workspace prompt.
    let providerCallCount = 0
    const workspacePrompt = '이 작업공간 README 파일을 읽어줘.'
    const deps = {
      async *callModel() {
        providerCallCount += 1
        yield createAssistantMessage({
          content: [
            {
              type: 'text',
              text:
                'Read 1 file (ctrl+o to expand)\nREADME 내용을 확인했습니다.',
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-stale-workspace-${providerCallCount}`,
    }
    const emitted: Message[] = []

    // When: the latest user prompt explicitly asks for local workspace reading.
    for await (const message of query({
      ...queryParams(workspacePrompt, [], deps),
      messages: createTax001AdapterlessFindFailureHistory(workspacePrompt),
      maxTurns: 1,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    // Then: the stale public-service failure does not suppress the requested local support result.
    expect(providerCallCount).toBe(1)
    expect(allAssistantText(emitted)).toContain('Read 1 file')
    expect(allAssistantText(emitted)).not.toContain(
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    )
  })

  test('does not redispatch find without a concrete adapter after adapterless find failed', async () => {
    let providerCallCount = 0
    let findCallCount = 0
    const disabledProviderToolNamesByCall: string[][] = []
    const findTool = {
      ...createNamedTool('find'),
      async call() {
        findCallCount += 1
        return {
          data:
            "Error: find(mode='fetch') requires a concrete adapter tool_id from the current available adapter set. No concrete adapter was selected.",
        }
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
        if (providerCallCount < 3) {
          yield createAssistantMessage({
            content: [
              {
                type: 'tool_use',
                id: `toolu-adapterless-find-${providerCallCount}`,
                name: 'find',
                input: { mode: 'fetch' },
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
                '출생신고와 수당 신청은 공식 신청 경로 확인이 필요하므로 필요한 서류와 인증 준비를 먼저 안내합니다.',
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-adapterless-find-${providerCallCount}`,
    }
    const emitted: Message[] = []

    for await (const message of query({
      ...queryParams(CIV002_PROMPT, [findTool], deps),
      maxTurns: 3,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    expect(findCallCount).toBe(1)
    expect(disabledProviderToolNamesByCall[1]).toContain('find')
    expect(toolResultText(emitted)).toContain(
      'Root find wrapper already failed because no concrete adapter tool_id was selected.',
    )
    expect(providerCallCount).toBe(2)
    expect(allAssistantText(emitted)).toContain(
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    )
  })

  test('blocks workspace read summary text after adapterless citizen find failed', async () => {
    let providerCallCount = 0
    const findTool = {
      ...createNamedTool('find'),
      async call() {
        return {
          data:
            "Error: find(mode='fetch') requires a concrete adapter tool_id from the current available adapter set. No concrete adapter was selected.",
        }
      },
    }
    const deps = {
      async *callModel() {
        providerCallCount += 1
        if (providerCallCount === 1) {
          yield createAssistantMessage({
            content: [
              {
                type: 'tool_use',
                id: 'toolu-adapterless-find-once',
                name: 'find',
                input: { mode: 'fetch' },
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
                'Read 1 file (ctrl+o to expand)\n출생신고와 아동수당 신청 방법을 정리했습니다.',
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-adapterless-summary-${providerCallCount}`,
    }
    const emitted: Message[] = []

    for await (const message of query({
      ...queryParams(CIV002_PROMPT, [findTool], deps),
      maxTurns: 2,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    expect(allAssistantText(emitted)).not.toContain('Read 1 file')
    expect(allAssistantText(emitted)).toContain(
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    )
  })

  test('terminates with Korean handoff after repeated adapterless find attempts', async () => {
    let providerCallCount = 0
    let findCallCount = 0
    const findTool = {
      ...createNamedTool('find'),
      async call() {
        findCallCount += 1
        return {
          data:
            "Error: find(mode='fetch') requires a concrete adapter tool_id from the current available adapter set. No concrete adapter was selected.",
        }
      },
    }
    const deps = {
      async *callModel() {
        providerCallCount += 1
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: `toolu-adapterless-repeat-${providerCallCount}`,
              name: 'find',
              input: { mode: 'fetch' },
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-adapterless-repeat-${providerCallCount}`,
    }
    const emitted: Message[] = []

    for await (const message of query({
      ...queryParams(CIV002_PROMPT, [findTool], deps),
      maxTurns: 5,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    expect(findCallCount).toBe(1)
    expect(providerCallCount).toBe(2)
    expect(toolResultText(emitted).match(/Root find wrapper already failed/g))
      .toHaveLength(1)
    expect(allAssistantText(emitted)).toContain(
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    )
    expect(allAssistantText(emitted)).toContain('공식 공공서비스 adapter')
  })

  test('terminates with Korean handoff after malformed adapterless find repeats', async () => {
    let providerCallCount = 0
    let findCallCount = 0
    const findTool = {
      ...createNamedTool('find'),
      async call() {
        findCallCount += 1
        return {
          data:
            "Find failed: Invalid parameters for tool 'find'. Missing or invalid fields: tool_id. Field required.",
        }
      },
    }
    const deps = {
      async *callModel() {
        providerCallCount += 1
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: `toolu-adapterless-malformed-${providerCallCount}`,
              name: 'find',
              input: { mode: 'fetch' },
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-adapterless-malformed-${providerCallCount}`,
    }
    const emitted: Message[] = []

    for await (const message of query({
      ...queryParams(CIV002_PROMPT, [findTool], deps),
      maxTurns: 5,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    expect(findCallCount).toBe(1)
    expect(providerCallCount).toBe(2)
    expect(allAssistantText(emitted)).toContain(
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    )
    expect(allAssistantText(emitted)).toContain('공식 공공서비스 adapter')
  })

  test('terminates with Korean handoff after same-turn malformed adapterless find batch', async () => {
    // Given: one provider turn emits two root find calls before any tool_result exists.
    let providerCallCount = 0
    let findCallCount = 0
    const findTool = {
      ...createNamedTool('find'),
      async call() {
        findCallCount += 1
        return {
          data:
            "Find failed: Invalid parameters for tool 'find'. Missing or invalid fields: tool_id. Field required.",
        }
      },
    }
    const deps = {
      async *callModel() {
        providerCallCount += 1
        if (providerCallCount === 1) {
          yield createAssistantMessage({
            content: [
              {
                type: 'tool_use',
                id: 'toolu-adapterless-same-turn-1',
                name: 'find',
                input: { mode: 'fetch' },
              },
              {
                type: 'tool_use',
                id: 'toolu-adapterless-same-turn-2',
                name: 'find',
                input: { mode: 'fetch' },
              },
            ],
          })
          return
        }
        yield createAssistantMessage({
          content: [
            {
              type: 'text',
              text: '출생신고와 아동수당 정보를 검색하겠습니다.',
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => `uuid-adapterless-same-turn-${providerCallCount}`,
    }
    const emitted: Message[] = []

    // When: the query loop executes the same-turn tool batch.
    for await (const message of query({
      ...queryParams(CIV002_PROMPT, [findTool], deps),
      maxTurns: 4,
    })) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    // Then: only one malformed root find result is exposed, and the turn hard-handoffs.
    const results = toolResultText(emitted)
    expect(findCallCount).toBe(1)
    expect(providerCallCount).toBe(1)
    expect(
      results.match(/Missing or invalid fields:\s*tool_id/g)?.length ?? 0,
    ).toBe(1)
    expect(results.match(/Root find wrapper already failed/g)?.length ?? 0)
      .toBe(1)
    expect(allAssistantText(emitted)).not.toContain('검색하겠습니다')
    expect(allAssistantText(emitted)).toContain(
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    )
    expect(allAssistantText(emitted)).toContain('공식 공공서비스 adapter')
  })
})
