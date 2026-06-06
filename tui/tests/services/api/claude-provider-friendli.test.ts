import { describe, expect, mock, test } from 'bun:test'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { assembleToolPool } from '../../../src/tools.js'
import { getEmptyToolPermissionContext } from '../../../src/Tool.js'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../../src/services/api/adapterManifest.js'
import { asSystemPrompt } from '../../../src/utils/systemPromptType.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TUI_ROOT = join(__dirname, '../../..')

mock.module(join(TUI_ROOT, 'src/services/vcr.js'), () => ({
  withStreamingVCR: async function* (_messages: unknown, f: () => AsyncGenerator<unknown>) {
    yield* f()
  },
  withVCR: async (_input: unknown, f: () => Promise<unknown>) => f(),
  withTokenCountVCR: async (_messages: unknown, f: () => Promise<unknown>) => f(),
}))

const { queryModelWithStreaming } = await import(
  join(TUI_ROOT, 'src/services/api/claude.js')
)

function responseForTextDelta(text: string): Response {
  const encoder = new TextEncoder()
  const lines = [
    `data: {"id":"chatcmpl_provider_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":${JSON.stringify(text)}}}]}`,
    'data: {"choices":[{"finish_reason":"stop","delta":{}}],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
    'data: [DONE]',
  ]
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const line of lines) {
          controller.enqueue(encoder.encode(`${line}\n\n`))
        }
        controller.close()
      },
    }),
    {
      status: 200,
      headers: { 'content-type': 'text/event-stream', 'x-request-id': 'req_provider_1' },
    },
  )
}

function responseForTextThenDocumentToolCall(): Response {
  const encoder = new TextEncoder()
  const lines = [
    'data: {"id":"chatcmpl_document_tool_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":"먼저 다운로드 폴더에서 HWPX 양식 파일을 찾고 문서 검사 도구를 사용하겠습니다.\\n"}}]}',
    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_document_1","type":"function","function":{"name":"document_inspect","arguments":"{\\"correlation_id\\":\\"doc-corr\\",\\"document\\":{\\"path\\":\\"/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지.hwpx\\",\\"expected_format\\":\\"hwpx\\"}}"}}]}}]}',
    'data: {"choices":[{"finish_reason":"tool_calls","delta":{}}],"usage":{"prompt_tokens":31,"completion_tokens":12}}',
    'data: [DONE]',
  ]
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const line of lines) {
          controller.enqueue(encoder.encode(`${line}\n\n`))
        }
        controller.close()
      },
    }),
    {
      status: 200,
      headers: { 'content-type': 'text/event-stream', 'x-request-id': 'req_document_1' },
    },
  )
}

describe('CC provider wired to FriendliAI client shim', () => {
  test('streams through services/api/claude.ts without backend chat_request', async () => {
    let requestBody: Record<string, unknown> | undefined
    const previousToken = process.env.UMMAYA_FRIENDLI_TOKEN
    const previousDisableFallback = process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
    process.env.UMMAYA_FRIENDLI_TOKEN = 'friendli-token'
    process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = '1'

    try {
      const events: unknown[] = []
      for await (const event of queryModelWithStreaming({
        messages: [createUserMessage({ content: 'hello' })],
        systemPrompt: asSystemPrompt(['System prompt']),
        thinkingConfig: { type: 'disabled' },
        tools: [],
        signal: new AbortController().signal,
        options: {
          getToolPermissionContext: async () => getEmptyToolPermissionContext(),
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          isNonInteractiveSession: false,
          querySource: 'repl_main_thread',
          agents: [],
          allowedAgentTypes: [],
          mcpTools: [],
          fetchOverride: async (_input: string | URL | Request, init?: RequestInit) => {
            requestBody = JSON.parse(String(init?.body))
            return responseForTextDelta('Hello from K-EXAONE')
          },
        },
      })) {
        events.push(event)
      }

      expect(requestBody?.['messages']).toEqual([
        { role: 'system', content: expect.stringContaining('System prompt') },
        { role: 'user', content: 'hello' },
      ])
      expect(requestBody).not.toHaveProperty('kind', 'chat_request')
      expect(events.some(event => (event as { type?: string }).type === 'assistant')).toBe(true)
      expect(
        events.some(event => {
          const streamEvent = event as { type?: string; event?: { type?: string } }
          return streamEvent.type === 'stream_event' && streamEvent.event?.type === 'message_start'
        }),
      ).toBe(true)
    } finally {
      if (previousToken === undefined) {
        delete process.env.UMMAYA_FRIENDLI_TOKEN
      } else {
        process.env.UMMAYA_FRIENDLI_TOKEN = previousToken
      }
      if (previousDisableFallback === undefined) {
        delete process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
      } else {
        process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = previousDisableFallback
      }
    }
  })

  test('forced tool choice keeps a deferred adapter schema in the provider request', async () => {
    let requestBody: Record<string, unknown> | undefined
    const previousToken = process.env.UMMAYA_FRIENDLI_TOKEN
    const previousDisableFallback = process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
    process.env.UMMAYA_FRIENDLI_TOKEN = 'friendli-token'
    process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = '1'
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9EF',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'METAR SPECI decoded airport weather',
          llm_description: 'Decoded METAR airport weather.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'a'.repeat(64),
      emitter_pid: 12345,
    })

    try {
      const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
      for await (const _event of queryModelWithStreaming({
        messages: [createUserMessage({ content: 'hello' })],
        systemPrompt: asSystemPrompt(['System prompt']),
        thinkingConfig: { type: 'disabled' },
        tools,
        signal: new AbortController().signal,
        options: {
          getToolPermissionContext: async () => getEmptyToolPermissionContext(),
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          isNonInteractiveSession: false,
          querySource: 'repl_main_thread',
          agents: [],
          allowedAgentTypes: [],
          mcpTools: [],
          toolChoice: {
            type: 'tool',
            name: 'kma_apihub_url_air_metar_decoded',
          },
          fetchOverride: async (_input: string | URL | Request, init?: RequestInit) => {
            requestBody = JSON.parse(String(init?.body))
            return responseForTextDelta('ok')
          },
        },
      })) {
        // Drain the stream so the provider request is built and sent.
      }

      const toolsPayload = requestBody?.['tools'] as
        | Array<{ function?: { name?: string } }>
        | undefined
      expect(toolsPayload?.map(tool => tool.function?.name)).toContain(
        'kma_apihub_url_air_metar_decoded',
      )
      expect(requestBody?.['tool_choice']).toEqual({
        type: 'function',
        function: { name: 'kma_apihub_url_air_metar_decoded' },
      })
      expect(JSON.stringify(requestBody?.['messages'])).toContain(
        'Mandatory tool call: the host selected kma_apihub_url_air_metar_decoded',
      )
    } finally {
      clearManifestCache()
      if (previousToken === undefined) {
        delete process.env.UMMAYA_FRIENDLI_TOKEN
      } else {
        process.env.UMMAYA_FRIENDLI_TOKEN = previousToken
      }
      if (previousDisableFallback === undefined) {
        delete process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
      } else {
        process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = previousDisableFallback
      }
    }
  })

  test('records turn-local adapter selection diagnostics for provider requests', async () => {
    let requestBody: Record<string, unknown> | undefined
    const previousToken = process.env.UMMAYA_FRIENDLI_TOKEN
    const previousDisableFallback = process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
    const previousDiagnosticsFile = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
    const diagnosticsDir = mkdtempSync(join(tmpdir(), 'ummaya-route-diagnostics-'))
    const diagnosticsPath = join(diagnosticsDir, 'route.jsonl')
    process.env.UMMAYA_FRIENDLI_TOKEN = 'friendli-token'
    process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = '1'
    process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnosticsPath
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9EF',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'METAR SPECI decoded airport weather aviation',
          llm_description: 'Decoded METAR airport weather.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'b'.repeat(64),
      emitter_pid: 12345,
    })

    try {
      const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
      for await (const _event of queryModelWithStreaming({
        messages: [createUserMessage({ content: 'METAR airport weather 확인해줘' })],
        systemPrompt: asSystemPrompt(['System prompt']),
        thinkingConfig: { type: 'disabled' },
        tools,
        signal: new AbortController().signal,
        options: {
          getToolPermissionContext: async () => getEmptyToolPermissionContext(),
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          isNonInteractiveSession: false,
          querySource: 'repl_main_thread',
          agents: [],
          allowedAgentTypes: [],
          mcpTools: [],
          fetchOverride: async (_input: string | URL | Request, init?: RequestInit) => {
            requestBody = JSON.parse(String(init?.body))
            return responseForTextDelta('ok')
          },
        },
      })) {
      }

      const diagnosticLines = readFileSync(diagnosticsPath, 'utf8')
        .trim()
        .split('\n')
        .map(line => JSON.parse(line) as Record<string, unknown>)
      const selection = diagnosticLines.find(record => record.event === 'adapter_selection')
      expect(selection).toEqual(
        expect.objectContaining({
          manifest_hash: 'b'.repeat(64),
          query_source: 'repl_main_thread',
          schema_projection_level: 'top_k_concrete_adapter_schemas',
        }),
      )
      expect(selection?.selected_tools).toContain('kma_apihub_url_air_metar_decoded')
      expect(selection?.final_adapter_tools).toContain('kma_apihub_url_air_metar_decoded')
      expect(selection?.query_hash).toMatch(/^[a-f0-9]{64}$/)
      const toolsPayload = requestBody?.['tools'] as
        | Array<{ function?: { name?: string } }>
        | undefined
      expect(toolsPayload?.map(tool => tool.function?.name)).toContain(
        'kma_apihub_url_air_metar_decoded',
      )
    } finally {
      clearManifestCache()
      rmSync(diagnosticsDir, { recursive: true, force: true })
      if (previousToken === undefined) {
        delete process.env.UMMAYA_FRIENDLI_TOKEN
      } else {
        process.env.UMMAYA_FRIENDLI_TOKEN = previousToken
      }
      if (previousDisableFallback === undefined) {
        delete process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
      } else {
        process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = previousDisableFallback
      }
      if (previousDiagnosticsFile === undefined) {
        delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      } else {
        process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = previousDiagnosticsFile
      }
    }
  })

  test('streams CC-style document intent prose before a document tool call', async () => {
    const previousToken = process.env.UMMAYA_FRIENDLI_TOKEN
    const previousDisableFallback = process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
    process.env.UMMAYA_FRIENDLI_TOKEN = 'friendli-token'
    process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = '1'

    try {
      const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
      const events: unknown[] = []
      for await (const event of queryModelWithStreaming({
        messages: [
          createUserMessage({
            content:
              '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식을 13주차 활동일지로 작성해줘. 활동기간은 2026.06.01부터 2026.06.07까지고, 작성이 끝나면 원본과 달라진 부분을 문서 화면으로 비교해서 내가 바로 확인할 수 있게 보여줘.',
          }),
        ],
        systemPrompt: asSystemPrompt(['System prompt']),
        thinkingConfig: { type: 'disabled' },
        tools,
        signal: new AbortController().signal,
        options: {
          getToolPermissionContext: async () => getEmptyToolPermissionContext(),
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          isNonInteractiveSession: false,
          querySource: 'repl_main_thread',
          agents: [],
          allowedAgentTypes: [],
          mcpTools: [],
          fetchOverride: async () => responseForTextThenDocumentToolCall(),
        },
      })) {
        events.push(event)
      }

      const assistantMessages = events.filter(
        event => (event as { type?: string }).type === 'assistant',
      ) as Array<{ message: { content: Array<{ type?: string; text?: string; name?: string }> } }>
      const visibleText = JSON.stringify(events)
      expect(visibleText).toContain('먼저 다운로드 폴더')
      expect(
        events.some(event => {
          const streamEvent = event as {
            type?: string
            event?: { type?: string; delta?: { type?: string } }
          }
          return (
            streamEvent.type === 'stream_event' &&
            streamEvent.event?.type === 'content_block_delta' &&
            streamEvent.event.delta?.type === 'text_delta'
          )
        }),
      ).toBe(true)
      expect(
        assistantMessages.some(message =>
          message.message.content.some(block =>
            block.type === 'text' &&
            block.text?.includes('먼저 다운로드 폴더'),
          ),
        ),
      ).toBe(true)
      expect(
        assistantMessages.some(message =>
          message.message.content.some(block =>
            block.type === 'tool_use' &&
            block.name === 'document_inspect',
          ),
        ),
      ).toBe(true)
      expect(
        assistantMessages.flatMap(message => message.message.content),
      ).toContainEqual(
        expect.objectContaining({
          type: 'tool_use',
          name: 'document_inspect',
        }),
      )
    } finally {
      if (previousToken === undefined) {
        delete process.env.UMMAYA_FRIENDLI_TOKEN
      } else {
        process.env.UMMAYA_FRIENDLI_TOKEN = previousToken
      }
      if (previousDisableFallback === undefined) {
        delete process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
      } else {
        process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = previousDisableFallback
      }
    }
  })
})
