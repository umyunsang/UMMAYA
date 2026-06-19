import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import { query } from '../../src/query.js'
import type { Message } from '../../src/types/message.js'
import type { Tools } from '../../src/Tool.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import {
  latestTextUserMessageIndex,
  messageText,
} from '../../src/query/messageGuards.js'
import {
  createNamedTool,
  queryParams,
} from './query-loop-visible-progress.helpers.js'

const TAX_TOOL_NAME = 'mock_lookup_module_hometax_simplified'
const VERIFY_TOOL_NAME = 'mock_verify_module_modid'
const TAX_PROMPT =
  '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.'

function createHometaxLookupTool(onCall: () => void): Tools[number] {
  return {
    ...createNamedTool(TAX_TOOL_NAME),
    inputSchema: z.object({
      year: z.number(),
      resident_id_prefix: z.string(),
    }),
    async call() {
      onCall()
      return {
        data: {
          ok: true,
          tool_id: TAX_TOOL_NAME,
          record: {
            year: 2025,
            filing_status: 'lookup_ready',
            scope: 'find:hometax.simplified',
          },
        },
      }
    },
  }
}

function createLookupRepeatDeps(
  toolName: string,
  onProviderTurn?: (params: {
    readonly toolNames: readonly string[]
    readonly disabledProviderToolNames: readonly string[]
  }) => void,
) {
  let callCount = 0
  return {
    async *callModel(request: {
      readonly tools: Tools
      readonly options: { readonly disabledProviderToolNames?: readonly string[] }
    }) {
      callCount += 1
      onProviderTurn?.({
        toolNames: request.tools.map(tool => tool.name),
        disabledProviderToolNames: request.options.disabledProviderToolNames ?? [],
      })
      if (callCount === 1) {
        yield createAssistantMessage({
          content: [
            {
              type: 'tool_use',
              id: 'toolu-tax001-first',
              name: toolName,
              input: { year: 2025, resident_id_prefix: '000000' },
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
              id: 'toolu-tax001-repeat',
              name: toolName,
              input: { year: 2025, resident_id_prefix: '000000' },
            },
          ],
        })
        return
      }
      yield createAssistantMessage({
        content: [{ type: 'text', text: '본인확인 후 다음 단계로 진행하겠습니다.' }],
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-tax-${callCount}`,
  }
}

async function runPromptWithDeps(params: {
  readonly prompt: string
  readonly tools: Tools
  readonly deps: ReturnType<typeof createLookupRepeatDeps>
  readonly messages?: readonly Message[]
}): Promise<readonly Message[]> {
  const emitted: Message[] = []
  for await (const message of query({
    ...queryParams(params.prompt, params.tools, params.deps),
    messages: params.messages
      ? [...params.messages]
      : [createUserMessage({ content: params.prompt })],
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

describe('TAX-001 Hometax lookup continuation guard', () => {
  test('keeps Hometax lookup in the provider surface while blocking immediate repeat dispatch', async () => {
    // Given: TAX-001 tools include both Hometax lookup and the required verify progression tool.
    const providerTurns: {
      readonly toolNames: readonly string[]
      readonly disabledProviderToolNames: readonly string[]
    }[] = []
    let lookupCallCount = 0
    const tools = [
      createHometaxLookupTool(() => {
        lookupCallCount += 1
      }),
      createNamedTool(VERIFY_TOOL_NAME),
    ]

    // When: the lookup succeeds and the model attempts the same lookup on the next provider turn.
    await runPromptWithDeps({
      prompt: TAX_PROMPT,
      tools,
      deps: createLookupRepeatDeps(TAX_TOOL_NAME, providerTurn => {
        providerTurns.push(providerTurn)
      }),
    })

    // Then: the provider schema remains available, but the repeated lookup is still not executed.
    expect(lookupCallCount).toBe(1)
    expect(providerTurns.length).toBeGreaterThanOrEqual(2)
    expect(providerTurns[0]?.toolNames).toContain(TAX_TOOL_NAME)
    expect(providerTurns[0]?.disabledProviderToolNames).not.toContain(TAX_TOOL_NAME)
    for (const providerTurn of providerTurns.slice(1)) {
      expect(providerTurn.toolNames).toContain(TAX_TOOL_NAME)
      expect(providerTurn.toolNames).toContain(VERIFY_TOOL_NAME)
      expect(providerTurn.disabledProviderToolNames).not.toContain(TAX_TOOL_NAME)
      expect(providerTurn.disabledProviderToolNames).not.toContain(VERIFY_TOOL_NAME)
    }
  })

  test('blocks repeated immediate Hometax lookup after successful TAX lookup until consent or verify progression', async () => {
    // Given: a fresh TAX-001 transcript and a model that repeats the same Hometax lookup.
    let lookupCallCount = 0
    const tools = [createHometaxLookupTool(() => {
      lookupCallCount += 1
    })]

    // When: the query loop handles a successful lookup and then the repeated lookup tool_use.
    const emitted = await runPromptWithDeps({
      prompt: TAX_PROMPT,
      tools,
      deps: createLookupRepeatDeps(TAX_TOOL_NAME),
    })

    // Then: the repeated lookup is not executed and the model sees the required progression block.
    expect(lookupCallCount).toBe(1)
    const resultText = toolResultText(emitted)
    expect(resultText).toContain('본인확인')
    expect(resultText).toContain('위임')
    expect(resultText).toContain('동의')
    expect(resultText).toContain('verify')
    expect(resultText).not.toContain('접수번호')
  })

  test('keeps meta repair prompts from resetting Hometax repeat history', async () => {
    // Given: a successful Hometax lookup already exists for the latest visible citizen prompt.
    let lookupCallCount = 0
    const priorToolUseID = 'toolu-tax001-prior-success'
    const priorToolUse = {
      type: 'tool_use',
      id: priorToolUseID,
      name: TAX_TOOL_NAME,
      input: { year: 2025, resident_id_prefix: '000000' },
    } as const
    const priorToolResult = {
      type: 'tool_result',
      tool_use_id: priorToolUseID,
      content: JSON.stringify({ ok: true }),
    } as const

    // When: an internal repair prompt is appended before the model repeats the same lookup.
    const emitted = await runPromptWithDeps({
      prompt: TAX_PROMPT,
      tools: [createHometaxLookupTool(() => {
        lookupCallCount += 1
      })],
      deps: createLookupRepeatDeps(TAX_TOOL_NAME),
      messages: [
        createUserMessage({ content: TAX_PROMPT }),
        createAssistantMessage({ content: [priorToolUse] }),
        createUserMessage({ content: [priorToolResult] }),
        createUserMessage({
          content: 'Final answer repair: answer from the original citizen tax request.',
          isMeta: true,
        }),
      ],
    })

    // Then: the repair prompt does not open a fresh citizen turn, so dispatch blocks the repeat.
    expect(lookupCallCount).toBe(0)
    const resultText = toolResultText(emitted)
    expect(resultText).toContain('Hometax lookup already returned')
    expect(resultText).toContain('verify')
  })

  test('allows repeated non-Hometax lookup tools to preserve unrelated tool behavior', async () => {
    // Given: a non-Hometax lookup-like tool that the model repeats.
    let lookupCallCount = 0
    const repeatedTool = {
      ...createNamedTool('mock_lookup_module_weather'),
      async call() {
        lookupCallCount += 1
        return { data: { ok: true, weather: 'clear' } }
      },
    }

    // When: the same non-Hometax tool_use appears on consecutive turns.
    await runPromptWithDeps({
      prompt: '오늘 날씨를 다시 확인해줘.',
      tools: [repeatedTool],
      deps: createLookupRepeatDeps('mock_lookup_module_weather'),
    })

    // Then: unrelated repeated lookups are not blocked by the TAX-001 guard.
    expect(lookupCallCount).toBe(2)
  })

  test('ignores stale Hometax lookup state before the latest citizen prompt', async () => {
    // Given: an older Hometax lookup exists before a new TAX-001 citizen prompt.
    let lookupCallCount = 0
    const previousAssistant = createAssistantMessage({
      content: [
        {
          type: 'tool_use',
          id: 'toolu-tax001-stale',
          name: TAX_TOOL_NAME,
          input: { year: 2024, resident_id_prefix: '000000' },
        },
      ],
    })

    // When: the current prompt performs its first Hometax lookup.
    await runPromptWithDeps({
      prompt: TAX_PROMPT,
      tools: [createHometaxLookupTool(() => {
        lookupCallCount += 1
      })],
      deps: createLookupRepeatDeps(TAX_TOOL_NAME),
      messages: [
        createUserMessage({ content: '작년 홈택스 자료를 조회해줘.' }),
        previousAssistant,
        createUserMessage({ content: TAX_PROMPT }),
      ],
    })

    // Then: stale state does not block the first lookup for the fresh prompt, but the immediate repeat is blocked.
    expect(lookupCallCount).toBe(1)
  })

  test('keeps hidden final-answer repair prompts out of latest TAX citizen context', () => {
    const priorToolUseID = 'toolu-tax001-meta-prior'
    const priorToolUse = { type: 'tool_use', id: priorToolUseID, name: TAX_TOOL_NAME, input: { year: 2025, resident_id_prefix: '000000' } } as const
    const priorToolResult = { type: 'tool_result', tool_use_id: priorToolUseID, content: '{"ok":true}' } as const
    const messages = [
      createUserMessage({ content: TAX_PROMPT }),
      createAssistantMessage({ content: [priorToolUse] }),
      createUserMessage({ content: [priorToolResult] }),
      createUserMessage({
        content: 'Final answer repair: answer from the original citizen tax request.',
        isMeta: true,
      }),
    ]

    const latestIndex = latestTextUserMessageIndex(messages)
    const latestMessage = messages[latestIndex]
    if (latestMessage === undefined) {
      throw new Error('Expected latest TAX citizen prompt message')
    }
    expect(messageText(latestMessage)).toBe(TAX_PROMPT)
  })
})
