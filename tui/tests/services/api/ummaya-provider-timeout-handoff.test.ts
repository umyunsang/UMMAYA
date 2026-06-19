import { afterEach, beforeEach, describe, expect, test } from 'bun:test'
import { readFileSync } from 'node:fs'
import { assembleToolPool } from '../../../src/tools.js'
import { getEmptyToolPermissionContext } from '../../../src/Tool.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import { asSystemPrompt } from '../../../src/utils/systemPromptType.js'
import {
  captureProviderExchange,
  createDiagnosticsTarget,
  responseForEmptyStop,
  responseForTextDelta,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

const { queryModelWithStreaming } = await import('../../../src/services/api/ummaya.js')

let previousProviderEventIdleTimeoutMs: string | undefined

beforeEach(() => {
  previousProviderEventIdleTimeoutMs =
    process.env.UMMAYA_TUI_PROVIDER_EVENT_IDLE_TIMEOUT_MS
  process.env.UMMAYA_TUI_PROVIDER_EVENT_IDLE_TIMEOUT_MS = '10'
})

afterEach(() => {
  restoreEnv(
    'UMMAYA_TUI_PROVIDER_EVENT_IDLE_TIMEOUT_MS',
    previousProviderEventIdleTimeoutMs,
  )
})

describe('UMMAYA provider stream timeout handoff', () => {
  test('shows stable Korean citizen handoff when FriendliAI fetch never resolves', async () => {
    await withFriendliEnv(async () => {
      const exchange = await collectWithTestTimeout(captureProviderExchange({
        messages: [createUserMessage({ content: '한 문장으로 인사만 해줘.' })],
        response: undefined,
        fetchNeverResolves: true,
      }))
      const visibleText = JSON.stringify(exchange.events)

      expect(visibleText).toContain('응답이 지연되어')
      expect(visibleText).toContain('잠시 후 다시 시도')
      expect(visibleText).not.toContain('timed out waiting')
    })
  })

  test('shows stable Korean citizen handoff when FriendliAI stream emits no data', async () => {
    await withFriendliEnv(async () => {
      const exchange = await collectWithTestTimeout(captureProviderExchange({
        messages: [createUserMessage({ content: '한 문장으로 인사만 해줘.' })],
        response: neverClosingSseResponse(),
      }))
      const visibleText = JSON.stringify(exchange.events)

      expect(visibleText).toContain('응답이 지연되어')
      expect(visibleText).toContain('잠시 후 다시 시도')
      expect(visibleText).not.toContain('FriendliAI response did not contain stream data')
      expect(visibleText).not.toContain('LLM stream idle timeout')
    })
  })

  test('shows stable Korean citizen handoff when FriendliAI finishes with empty content', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({ content: '한 문장으로 인사만 해줘.' })],
        response: responseForEmptyStop(),
      })
      const visibleText = JSON.stringify(exchange.events)

      expect(visibleText).toContain('응답이 비어')
      expect(visibleText).toContain('잠시 후 다시 시도')
      expect(visibleText).not.toContain('"content":[]')
    })
  })

  test('records provider_turn_complete when the query loop stops after first assistant message', async () => {
    await withFriendliEnv(async () => {
      const diagnostics = createDiagnosticsTarget()
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      try {
        process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
        for await (const event of queryModelWithStreaming({
          messages: [createUserMessage({ content: '한 문장으로 인사만 해줘.' })],
          systemPrompt: asSystemPrompt(['System prompt']),
          thinkingConfig: { type: 'disabled' },
          tools: assembleToolPool(getEmptyToolPermissionContext(), []),
          signal: new AbortController().signal,
          options: {
            getToolPermissionContext: async () => getEmptyToolPermissionContext(),
            model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
            isNonInteractiveSession: false,
            querySource: 'repl_main_thread',
            agents: [],
            allowedAgentTypes: [],
            mcpTools: [],
            fetchOverride: async () => responseForTextDelta('ok'),
          },
        })) {
          if (JSON.stringify(event).includes('"type":"assistant"')) break
        }

        const diagnosticsText = readFileSync(diagnostics.path, 'utf8')
        expect(diagnosticsText).toContain('"event":"provider_turn_start"')
        expect(diagnosticsText).toContain('"event":"provider_turn_complete"')
      } finally {
        restoreEnv('UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE', previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })
})

function neverClosingSseResponse(): Response {
  const encoder = new TextEncoder()
  return new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(': keep-alive\n\n'))
    },
  }), {
    status: 200,
    headers: {
      'content-type': 'text/event-stream',
      'x-request-id': 'req_provider_idle',
    },
  })
}

async function collectWithTestTimeout<T>(promise: Promise<T>): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error('timed out waiting for provider idle handoff')), 150)
    }),
  ])
}

function restoreEnv(name: string, previousValue: string | undefined): void {
  if (previousValue === undefined) {
    delete process.env[name]
    return
  }
  process.env[name] = previousValue
}
