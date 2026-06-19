import { afterEach, beforeEach, describe, expect, mock, test } from 'bun:test'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { clearManifestCache } from '../../../src/services/api/adapterManifest.js'
import type { ProviderOptions } from '../../../src/services/api/ummaya/types.js'
import { assembleToolPool } from '../../../src/tools.js'
import { getEmptyToolPermissionContext } from '../../../src/Tool.js'
import { asSystemPrompt } from '../../../src/utils/systemPromptType.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'

const testDir = dirname(fileURLToPath(import.meta.url))
const tuiRoot = join(testDir, '../../..')
const TEST_MANIFEST_TIMEOUT_ENV =
  'UMMAYA_TEST_PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_MS'
const TAX_PROMPT =
  '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.'

type EnsureManifest = (timeoutMs?: number) => Promise<boolean>
type Deferred<T> = {
  readonly promise: Promise<T>
  readonly resolve: (value: T) => void
}

let ensureManifestImpl: EnsureManifest = async () => true
const ensureManifestMock = mock((timeoutMs?: number) =>
  ensureManifestImpl(timeoutMs),
)

await mock.module(join(tuiRoot, 'src/ipc/bridgeSingleton.js'), () => ({
  ensureUmmayaAdapterManifest: ensureManifestMock,
  getOrCreateUmmayaBridge: () => {
    throw new Error('getOrCreateUmmayaBridge must stay behind readiness helper')
  },
  getUmmayaBridgeSessionId: () => 'test-session-bridge-readiness',
  closeUmmayaBridge: async () => {},
}))

const { queryModelWithStreaming } = await import(
  '../../../src/services/api/ummaya/provider.js'
)

beforeEach(() => {
  clearManifestCache()
  ensureManifestImpl = async () => true
  ensureManifestMock.mockClear()
})

afterEach(() => {
  clearManifestCache()
  ensureManifestImpl = async () => true
  ensureManifestMock.mockClear()
  delete process.env[TEST_MANIFEST_TIMEOUT_ENV]
})

describe('UMMAYA provider bridge-starting adapter manifest readiness', () => {
  test('calls bridge readiness before TAX-001 repl_main_thread request is built or fetched', async () => {
    await withFriendliEnv(async () => {
      process.env[TEST_MANIFEST_TIMEOUT_ENV] = '5'
      const readiness = createDeferred<boolean>()
      const callOrder: string[] = []
      let fetchCallCount = 0
      let requestBody: BodyInit | null | undefined

      ensureManifestImpl = (timeoutMs?: number) => {
        callOrder.push(`ensure:${timeoutMs ?? 'default'}`)
        return readiness.promise
      }

      const providerRun = collectProviderEvents({
        querySource: 'repl_main_thread',
        userText: TAX_PROMPT,
        fetchOverride: async (_input, init) => {
          callOrder.push('fetch')
          fetchCallCount += 1
          requestBody = init?.body
          return responseForTextDelta('ok')
        },
      })

      try {
        await sleep(20)
        expect(ensureManifestMock).toHaveBeenCalledTimes(1)
        expect(callOrder).toEqual(['ensure:5'])
        expect(fetchCallCount).toBe(0)
        expect(requestBody).toBeUndefined()

        readiness.resolve(true)
        await providerRun

        expect(fetchCallCount).toBe(1)
        expect(typeof requestBody).toBe('string')
        expect(callOrder).toEqual(['ensure:5', 'fetch'])
      } finally {
        readiness.resolve(false)
        await providerRun.catch(() => [])
      }
    })
  })

  test('does not call bridge readiness for empty generate_session_title turns', async () => {
    await withFriendliEnv(async () => {
      let fetchCallCount = 0

      await collectProviderEvents({
        querySource: 'generate_session_title',
        userText: '',
        fetchOverride: async () => {
          fetchCallCount += 1
          return responseForTextDelta('ok')
        },
      })

      expect(ensureManifestMock).not.toHaveBeenCalled()
      expect(fetchCallCount).toBe(1)
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

function responseForTextDelta(text: string): Response {
  const encoder = new TextEncoder()
  const lines = [
    `data: {"id":"chatcmpl_bridge_readiness_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":${JSON.stringify(text)}}}]}`,
    'data: {"choices":[{"finish_reason":"stop","delta":{}}],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
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
      'x-request-id': 'req_bridge_readiness_1',
    },
  })
}

async function withFriendliEnv<T>(run: () => Promise<T>): Promise<T> {
  const previousToken = process.env.UMMAYA_FRIENDLI_TOKEN
  const previousDisableFallback =
    process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
  try {
    process.env.UMMAYA_FRIENDLI_TOKEN = 'friendli-token'
    process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = '1'
    return await run()
  } finally {
    restoreEnv('UMMAYA_FRIENDLI_TOKEN', previousToken)
    restoreEnv(
      'CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK',
      previousDisableFallback,
    )
  }
}

function restoreEnv(name: string, previousValue: string | undefined): void {
  if (previousValue === undefined) {
    delete process.env[name]
    return
  }
  process.env[name] = previousValue
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
