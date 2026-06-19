import { describe, expect, test } from 'bun:test'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { z } from 'zod/v4'
import { query } from '../../src/query.js'
import { queryModelWithStreaming } from '../../src/services/api/ummaya.js'
import { hashRouteDiagnosticText } from '../../src/tools/AdapterTool/routeDiagnostics.js'
import type { Message } from '../../src/types/message.js'
import type { Tools } from '../../src/Tool.js'
import {
  createAssistantMessage,
  createTurnDurationMessage,
  createUserMessage,
} from '../../src/utils/messages.js'
import type { QueryModelParams } from '../../src/services/api/ummaya/types.js'
import {
  ingestTaxManifest,
  withFriendliEnv,
} from '../services/api/ummaya-provider-friendli.helpers.js'
import {
  createNamedTool,
  queryParams,
  textOf,
} from './query-loop-visible-progress.helpers.js'

const TAX_LOOKUP_TOOL_NAME = 'mock_lookup_module_hometax_simplified'
const TAX002_PROMPT =
  '2025년 부가가치세 신고 준비를 위해 매출 자료 조회부터 진행해줘.'
const TAX003_PROMPT =
  '아파트 팔았는데 양도소득세 얼마나 나오는지 계산하고 신고 절차까지 안내해줘.'
const SYNTHETIC_TAX002_TOOL_USE_ID = 'vat-lookup'
const TAX003_SUBMIT_TOOL_NAME = 'mock_submit_module_hometax_taxreturn'

function createTaxLookupTool(onCall: () => void): Tools[number] {
  return {
    ...createNamedTool(TAX_LOOKUP_TOOL_NAME),
    inputSchema: z.object({
      year: z.number(),
    }),
    async call(args) {
      onCall()
      return {
        data: {
          ok: true,
          tool_id: TAX_LOOKUP_TOOL_NAME,
          tax_type: 'vat',
          year: args.year,
        },
      }
    },
  }
}

function responseForTextThenTaxLookupToolCall(): Response {
  const encoder = new TextEncoder()
  const lines = [
    'data: {"id":"chatcmpl_tax002_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":"네."}}]}',
    `data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"${SYNTHETIC_TAX002_TOOL_USE_ID}","type":"function","function":{"name":"${TAX_LOOKUP_TOOL_NAME}","arguments":"{\\"year\\":2025}"}}]}}]}`,
    'data: {"choices":[{"finish_reason":"tool_calls","delta":{}}],"usage":{"prompt_tokens":13,"completion_tokens":4}}',
    'data: [DONE]',
  ]
  return new Response(new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(`${line}\n\n`))
      }
      controller.close()
    },
  }), {
    status: 200,
    headers: {
      'content-type': 'text/event-stream',
      'x-request-id': 'req_tax002_gap',
    },
  })
}

function createProviderBackedDeps(response: Response) {
  let callCount = 0
  return {
    async *callModel(params: QueryModelParams) {
      callCount += 1
      if (callCount === 1) {
        yield* queryModelWithStreaming({
          ...params,
          options: {
            ...params.options,
            querySource: 'repl_main_thread',
            fetchOverride: async () => response,
          },
        })
        return
      }
      yield createAssistantMessage({
        content: '부가세 조회 결과를 확인했고 다음 단계를 이어가겠습니다.',
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-tax002-${callCount}`,
  }
}

function createPriorTax001Messages(): readonly Message[] {
  return [
    createUserMessage({
      content: '작년 종합소득세 신고를 진행하려고 해. 본인확인부터 도와줘.',
    }),
    createAssistantMessage({
      content: [
        {
          type: 'tool_use',
          id: 'tax001-verify',
          name: 'mock_verify_module_modid',
          input: { purpose: 'income_tax' },
        },
      ],
    }),
    createUserMessage({
      content: [
        {
          type: 'tool_result',
          tool_use_id: 'tax001-verify',
          content: 'permission_denied',
          is_error: true,
        },
      ],
      toolUseResult: 'permission_denied',
    }),
    createAssistantMessage({
      content:
        '본인확인 승인이 없어 이전 TAX-001 요청은 계속 진행할 수 없습니다.',
    }),
    createUserMessage({ content: TAX002_PROMPT }),
  ]
}

function toolResultContents(messages: readonly Message[]): readonly string[] {
  return messages.flatMap(message => {
    if (message.type !== 'user' || !Array.isArray(message.message.content)) {
      return []
    }
    return message.message.content.flatMap(block => {
      if (
        typeof block !== 'object' ||
        block === null ||
        !('type' in block) ||
        block.type !== 'tool_result' ||
        !('content' in block)
      ) {
        return []
      }
      return [typeof block.content === 'string' ? block.content : JSON.stringify(block.content)]
    })
  })
}

function readDiagnosticsForQuery(path: string, queryHash: string): readonly Record<string, unknown>[] {
  if (!existsSync(path)) return []
  return readFileSync(path, 'utf8')
    .split('\n')
    .filter(line => line.trim().length > 0)
    .map(line => JSON.parse(line) as Record<string, unknown>)
    .filter(record => record.query_hash === queryHash)
}

describe('TAX-002 provider-final-assistant query gap', () => {
  test('emits query_assistant_yield and tool_result for a mixed provider final assistant after stale TAX-001 state', async () => {
    await withFriendliEnv(async () => {
      const previousRoutePath = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const tempRoot = mkdtempSync(join(tmpdir(), 'tax002-query-gap-'))
      const diagnosticsPath =
        previousRoutePath ?? join(tempRoot, 'route.jsonl')
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnosticsPath

      let lookupCallCount = 0
      const emitted: Array<Message | { type: 'stream_event'; event: Record<string, unknown> }> = []
      const tools: Tools = [
        createTaxLookupTool(() => {
          lookupCallCount += 1
        }),
      ]

      ingestTaxManifest('q')
      try {
        for await (const event of query({
          ...queryParams(
            TAX002_PROMPT,
            tools,
            createProviderBackedDeps(responseForTextThenTaxLookupToolCall()),
          ),
          querySource: 'repl_main_thread',
          messages: [...createPriorTax001Messages()],
        })) {
          if (
            event.type === 'assistant' ||
            event.type === 'user' ||
            event.type === 'stream_event'
          ) {
            emitted.push(event)
          }
        }

        const queryHash = hashRouteDiagnosticText(TAX002_PROMPT)
        const diagnostics = readDiagnosticsForQuery(diagnosticsPath, queryHash)
        const assistantMessages = emitted.filter(
          (event): event is Message =>
            event.type === 'assistant' || event.type === 'user',
        )
        const firstAssistant = assistantMessages.find(
          (message): message is Message =>
            message.type === 'assistant' &&
            Array.isArray(message.message.content) &&
            message.message.content.some(block => block.type === 'tool_use'),
        )

        expect(
          emitted.some(
            event =>
              event.type === 'stream_event' &&
              event.event.type === 'message_start',
          ),
        ).toBe(true)
        expect(
          emitted.some(
            event =>
              event.type === 'stream_event' &&
              event.event.type === 'content_block_delta',
          ),
        ).toBe(true)
        expect(firstAssistant).toBeDefined()
        if (!firstAssistant || firstAssistant.type !== 'assistant') {
          throw new Error('expected assistant tool_use message for TAX-002')
        }
        expect(textOf(firstAssistant)).toBe('네.')
        expect(toolResultContents(assistantMessages).join('\n')).toContain(
          `"tool_id":"${TAX_LOOKUP_TOOL_NAME}"`,
        )
        expect(toolResultContents(assistantMessages).join('\n')).toContain('"tax_type":"vat"')
        expect(assistantMessages.at(-1)?.type).toBe('assistant')
        if (assistantMessages.at(-1)?.type === 'assistant') {
          expect(textOf(assistantMessages.at(-1)!)).toContain('다음 단계를 이어가겠습니다')
        }
        expect(lookupCallCount).toBe(1)
        expect(
          diagnostics.some(record => record.event === 'query_assistant_yield'),
        ).toBe(true)
        expect(
          diagnostics.some(record => record.event === 'query_completed_without_assistant'),
        ).toBe(false)
        expect(
          diagnostics.some(
            record =>
              record.event === 'query_assistant_yield' &&
              record.assistant_text_chars === 2 &&
              record.assistant_tool_use_count === 1,
          ),
        ).toBe(true)
      } finally {
        if (previousRoutePath === undefined) {
          delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
        } else {
          process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = previousRoutePath
        }
        if (previousRoutePath === undefined) {
          rmSync(tempRoot, { recursive: true, force: true })
        }
      }
    })
  })

  test('keeps tool-use assistant visible after a system turn-duration message in REPL history', async () => {
    let submitCallCount = 0
    let providerCallCount = 0
    const deps = {
      async *callModel() {
        providerCallCount += 1
        if (providerCallCount > 1) {
          yield createAssistantMessage({
            content: '양도소득세 신고 절차를 확인한 도구 결과 기준으로 안내합니다.',
          })
          return
        }
        yield createAssistantMessage({
          content: [
            { type: 'text', text: '\n\n' },
            {
              type: 'tool_use',
              id: 'tax003-submit',
              name: TAX003_SUBMIT_TOOL_NAME,
              input: {},
            },
          ],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({
        compactionResult: null,
        consecutiveFailures: undefined,
      }),
      uuid: () => 'uuid-tax003-system-history',
    }
    const submitTool = {
      ...createNamedTool(TAX003_SUBMIT_TOOL_NAME),
      async call() {
        submitCallCount += 1
        return {
          data: {
            ok: true,
            tool_id: TAX003_SUBMIT_TOOL_NAME,
          },
        }
      },
    }
    const prior = createPriorTax001Messages()
    const tax002User = prior.at(-1)
    if (tax002User === undefined) {
      throw new Error('expected prior TAX-002 user message')
    }
    const messages = [
      ...prior.slice(0, -1),
      createTurnDurationMessage(54_814),
      tax002User,
      createAssistantMessage({
        content:
          '개인사업자의 부가가치세 신고와 납부 절차는 공식 홈택스 채널 확인으로 안내합니다.',
      }),
      createUserMessage({ content: TAX003_PROMPT }),
    ]
    const emitted: Message[] = []

    for await (const event of query({
      ...queryParams(TAX003_PROMPT, [submitTool], deps),
      querySource: 'repl_main_thread',
      messages,
    })) {
      if (event.type === 'assistant' || event.type === 'user') {
        emitted.push(event)
      }
    }

    expect(submitCallCount).toBe(1)
    expect(
      emitted.some(
        event =>
          event.type === 'assistant' &&
          Array.isArray(event.message.content) &&
          event.message.content.some(
            block =>
              block.type === 'tool_use' &&
              block.name === TAX003_SUBMIT_TOOL_NAME,
          ),
      ),
    ).toBe(true)
    expect(toolResultContents(emitted).join('\n')).toContain(
      `"tool_id":"${TAX003_SUBMIT_TOOL_NAME}"`,
    )
  })
})
