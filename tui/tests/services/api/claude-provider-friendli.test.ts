import { describe, expect, mock, test } from 'bun:test'
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
})
