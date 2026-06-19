import { afterEach, beforeEach, describe, expect, test } from 'bun:test'
import { readFileSync } from 'node:fs'
import { z } from 'zod/v4'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../../src/services/api/adapterManifest.js'
import type { ProviderOptions } from '../../../src/services/api/ummaya/types.js'
import { hashRouteDiagnosticText } from '../../../src/tools/AdapterTool/routeDiagnostics.js'
import { assembleToolPool } from '../../../src/tools.js'
import { getEmptyToolPermissionContext } from '../../../src/Tool.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import { asSystemPrompt } from '../../../src/utils/systemPromptType.js'
import {
  createDiagnosticsTarget,
  ingestTaxManifest,
  responseForTextDelta,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

const { queryModelWithStreaming } = await import('../../../src/services/api/ummaya.js')

const TAX_PROMPT =
  '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.'

const providerRequestSchema = z.object({
  tools: z
    .array(z.object({
      function: z.object({ name: z.string().optional() }).optional(),
    }).passthrough())
    .optional(),
}).passthrough()

const routeAdapterSelectionSchema = z.object({
  event: z.literal('adapter_selection'),
  manifest_hash: z.string().nullable(),
  query_source: z.string(),
  selected_tools: z.array(z.string()),
  final_adapter_tools: z.array(z.string()),
  query_hash: z.string(),
}).passthrough()

type RouteAdapterSelection = z.infer<typeof routeAdapterSelectionSchema>

type Deferred<T> = {
  readonly promise: Promise<T>
  readonly resolve: (value: T) => void
}

beforeEach(() => {
  clearManifestCache()
})

afterEach(() => {
  clearManifestCache()
  delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
  delete process.env.UMMAYA_TEST_PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_MS
})

describe('UMMAYA provider adapter manifest wait', () => {
  test('yields visible adapter manifest timeout and never fetches when TAX-001 main turn manifest is missing', async () => {
    await withFriendliEnv(async () => {
      process.env.UMMAYA_TEST_PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_MS = '25'
      let fetchCallCount = 0

      const events = await collectProviderEvents({
        querySource: 'repl_main_thread',
        userText: TAX_PROMPT,
        fetchOverride: async () => {
          fetchCallCount += 1
          throw new Error('fetch must not be called before adapter manifest sync')
        },
      })

      expect(fetchCallCount).toBe(0)
      const serializedEvents = JSON.stringify(events)
      expect(serializedEvents).toContain('"isApiErrorMessage":true')
      expect(serializedEvents).toContain('public-service adapter manifest')
      expect(serializedEvents).toContain('25ms')
      expect(serializedEvents).toContain('backend readiness')
      expect(serializedEvents).not.toContain('fetch must not be called')
    })
  })

  test('does not call fetch at 2600ms while a TAX-001 repl_main_thread manifest is still pending', async () => {
    await withFriendliEnv(async () => {
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      const events: string[] = []
      let fetchCallCount = 0
      let providerRun: Promise<readonly unknown[]> | undefined
      let capturedRequest: z.infer<typeof providerRequestSchema> | undefined

      try {
        providerRun = collectProviderEvents({
          querySource: 'repl_main_thread',
          userText: TAX_PROMPT,
          fetchOverride: async (_input, init) => {
            events.push('fetch')
            fetchCallCount += 1
            capturedRequest = parseProviderRequestBody(init?.body)
            return responseForTextDelta('ok')
          },
        })

        await sleep(2_600)
        expect(fetchCallCount).toBe(0)
        expect(capturedRequest).toBeUndefined()

        events.push('manifest:delayed')
        ingestDelayedTaxManifest('d')
        events.push('manifest:done')
        await providerRun

        expect(events.indexOf('manifest:done')).toBeGreaterThanOrEqual(0)
        expect(events.indexOf('fetch')).toBeGreaterThan(events.indexOf('manifest:done'))
        expect(fetchCallCount).toBe(1)
        expect(requestToolNames(capturedRequest)).toContain(
          'mock_lookup_module_hometax_simplified',
        )

        const selections = readRouteAdapterSelections(diagnostics.path)
          .filter(selection =>
            selection.query_source === 'repl_main_thread' &&
            selection.query_hash === hashRouteDiagnosticText(TAX_PROMPT)
          )
        expect(selections).not.toHaveLength(0)
        expect(selections.every(selection => selection.manifest_hash !== null)).toBe(true)
        expect(selections.flatMap(selection => selection.selected_tools)).toContain(
          'mock_lookup_module_hometax_simplified',
        )
      } finally {
        if (fetchCallCount > 0) {
          await providerRun
        }
        diagnostics.cleanup()
      }
    })
  })

  test('does not wait for empty generate_session_title turns', async () => {
    await withFriendliEnv(async () => {
      const manifestStarted = createDeferred<void>()
      const fetchStarted = createDeferred<void>()
      const manifestTimer = setTimeout(() => {
        manifestStarted.resolve()
        ingestTaxManifest('e')
      }, 20)

      try {
        const providerRun = collectProviderEvents({
          querySource: 'generate_session_title',
          userText: '',
          fetchOverride: async () => {
            fetchStarted.resolve()
            return responseForTextDelta('ok')
          },
        })

        const firstObserved = await Promise.race([
          fetchStarted.promise.then(() => 'fetch' as const),
          manifestStarted.promise.then(() => 'manifest' as const),
        ])
        expect(firstObserved).toBe('fetch')
        await providerRun
      } finally {
        clearTimeout(manifestTimer)
      }
    })
  })
})

function createDeferred<T>(): Deferred<T> {
  let resolveDeferred: (value: T) => void = () => {}
  const promise = new Promise<T>(resolve => {
    resolveDeferred = resolve
  })
  return { promise, resolve: resolveDeferred }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => {
    setTimeout(resolve, ms)
  })
}

function ingestDelayedTaxManifest(hashChar: string): void {
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9TX',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kakao_address_search',
        name: 'Kakao address search',
        primitive: 'find',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '주소 위치 검색 kakao address',
        llm_description: 'Address lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_current_observation',
        name: 'KMA current observation',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '날씨 기상 관측 현재 기온',
        llm_description: 'Weather observation adapter.',
        input_schema_json: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mock_lookup_module_hometax_simplified',
        name: 'Mock Hometax simplified lookup',
        primitive: 'find',
        policy_authority_url: 'https://www.hometax.go.kr/',
        source_mode: 'mock',
        search_hint: '홈택스 종합소득세 소득세 신고 환급 환급계좌 국세청',
        llm_description: 'Mock Hometax income-tax lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            year: { type: 'integer' },
            resident_id_prefix: { type: 'string' },
          },
          required: ['year', 'resident_id_prefix'],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

async function collectProviderEvents(params: {
  readonly querySource: string
  readonly userText: string
  readonly fetchOverride: ProviderOptions['fetchOverride']
}): Promise<readonly unknown[]> {
  const events: unknown[] = []
  const messages = params.userText
    ? [createUserMessage({ content: params.userText })]
    : []
  for await (const event of queryModelWithStreaming({
    messages,
    systemPrompt: asSystemPrompt(['System prompt']),
    thinkingConfig: { type: 'disabled' },
    tools: assembleToolPool(getEmptyToolPermissionContext(), []),
    signal: new AbortController().signal,
    options: {
      getToolPermissionContext: async () => getEmptyToolPermissionContext(),
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      isNonInteractiveSession: false,
      querySource: params.querySource,
      agents: [],
      allowedAgentTypes: [],
      mcpTools: [],
      fetchOverride: params.fetchOverride,
    },
  })) {
    events.push(event)
  }
  return events
}

function parseProviderRequestBody(
  body: BodyInit | null | undefined,
): z.infer<typeof providerRequestSchema> {
  if (typeof body !== 'string') throw new Error('Expected string provider request body')
  const parsed: unknown = JSON.parse(body)
  return providerRequestSchema.parse(parsed)
}

function requestToolNames(
  request: z.infer<typeof providerRequestSchema> | undefined,
): string[] {
  return request?.tools?.flatMap(tool => {
    const name = tool.function?.name
    return name === undefined ? [] : [name]
  }) ?? []
}

function readRouteAdapterSelections(path: string): RouteAdapterSelection[] {
  return readFileSync(path, 'utf8')
    .trim()
    .split('\n')
    .flatMap(line => {
      const parsed: unknown = JSON.parse(line)
      const record = routeAdapterSelectionSchema.safeParse(parsed)
      return record.success ? [record.data] : []
    })
}
