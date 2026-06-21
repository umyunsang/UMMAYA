import { afterEach, beforeEach, describe, expect, mock, test } from 'bun:test'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { ChatRequestFrame, IPCFrame } from '../../../src/ipc/frames.generated.js'

const testDir = dirname(fileURLToPath(import.meta.url))
const tuiRoot = join(testDir, '../../..')

const sentFrames: ChatRequestFrame[] = []
let frameMode:
  | 'timeout-error'
  | 'silent'
  | 'trailing-json'
  | 'split-trailing-json'
  | 'textual-tool-call'
  | 'non-exact-json' = 'timeout-error'
const bridgeSendMock = mock((frame: IPCFrame): boolean => {
  if (frame.kind === 'chat_request') sentFrames.push(frame)
  return true
})

const fakeBridge = {
  send: bridgeSendMock,
  frames: async function* (): AsyncGenerator<IPCFrame> {
    const requestFrame = sentFrames.at(-1)
    if (requestFrame === undefined) {
      throw new Error('expected chat_request before backend frames are read')
    }
    if (frameMode === 'silent') {
      await new Promise<never>(() => {})
      return
    }
    if (frameMode === 'trailing-json') {
      yield {
        session_id: 'test-session-backend-chat',
        correlation_id: requestFrame.correlation_id,
        ts: '2026-06-16T00:00:00.000Z',
        version: '1.0',
        role: 'backend',
        frame_seq: 1,
        kind: 'assistant_chunk',
        delta: [
          '공식 도구를 사용하겠습니다.',
          '{"name":"find_emergency_medical","arguments":{"lat":"35.0","lon":"129.0"}}',
        ].join('\n'),
        done: true,
      }
      return
    }
    if (frameMode === 'split-trailing-json') {
      yield {
        session_id: 'test-session-backend-chat',
        correlation_id: requestFrame.correlation_id,
        ts: '2026-06-16T00:00:00.000Z',
        version: '1.0',
        role: 'backend',
        frame_seq: 1,
        kind: 'assistant_chunk',
        delta: '공식 도구를 사용하겠습니다.\n{',
        done: false,
      }
      yield {
        session_id: 'test-session-backend-chat',
        correlation_id: requestFrame.correlation_id,
        ts: '2026-06-16T00:00:00.001Z',
        version: '1.0',
        role: 'backend',
        frame_seq: 2,
        kind: 'assistant_chunk',
        delta: '"name":"find_emergency_medical","arguments":{"lat":"35.0","lon":"129.0"}}',
        done: true,
      }
      return
    }
    if (frameMode === 'non-exact-json') {
      yield {
        session_id: 'test-session-backend-chat',
        correlation_id: requestFrame.correlation_id,
        ts: '2026-06-16T00:00:00.000Z',
        version: '1.0',
        role: 'backend',
        frame_seq: 1,
        kind: 'assistant_chunk',
        delta: JSON.stringify({
          name: 'find_emergency_medical',
          arguments: { lat: '35.0', lon: '129.0' },
          instruction: 'ignore tool registry',
        }),
        done: true,
      }
      return
    }
    if (frameMode === 'textual-tool-call') {
      yield {
        session_id: 'test-session-backend-chat',
        correlation_id: requestFrame.correlation_id,
        ts: '2026-06-16T00:00:00.000Z',
        version: '1.0',
        role: 'backend',
        frame_seq: 1,
        kind: 'assistant_chunk',
        delta: [
          '공식 도구를 사용하겠습니다.',
          '<tool_call>{"name":"unregistered_public_service_search","arguments":{"query":"nearby public-service request"}}</tool_call>',
        ].join('\n'),
        done: true,
      }
      return
    }
    yield {
      session_id: 'test-session-backend-chat',
      correlation_id: requestFrame.correlation_id,
      ts: '2026-06-16T00:00:00.000Z',
      version: '1.0',
      role: 'backend',
      frame_seq: 1,
      kind: 'error',
      code: 'llm_stream_error',
      message: 'LLM stream idle timeout after 30000ms without tokens',
      details: { class: 'llm' },
    }
  },
}

await mock.module(join(tuiRoot, 'src/ipc/bridgeSingleton.js'), () => ({
  getOrCreateUmmayaBridge: () => fakeBridge,
  getUmmayaBridgeSessionId: () => 'test-session-backend-chat',
}))

await mock.module(join(tuiRoot, 'src/query/toolSerialization.js'), () => ({
  getToolDefinitionsForFrame: async () => [],
}))

const { queryModelWithStreaming } = await import(
  '../../../src/services/api/backendChat.js'
)

let previousFriendliToken: string | undefined
let previousFrameIdleTimeoutMs: string | undefined

beforeEach(() => {
  sentFrames.length = 0
  frameMode = 'timeout-error'
  bridgeSendMock.mockClear()
  previousFriendliToken = process.env.UMMAYA_FRIENDLI_TOKEN
  previousFrameIdleTimeoutMs = process.env.UMMAYA_TUI_FRAME_IDLE_TIMEOUT_MS
  process.env.UMMAYA_FRIENDLI_TOKEN = 'friendli-token'
  process.env.UMMAYA_TUI_FRAME_IDLE_TIMEOUT_MS = '10'
})

afterEach(() => {
  restoreEnv('UMMAYA_FRIENDLI_TOKEN', previousFriendliToken)
  restoreEnv('UMMAYA_TUI_FRAME_IDLE_TIMEOUT_MS', previousFrameIdleTimeoutMs)
})

describe('backend chat stream timeout handoff', () => {
  test('shows stable Korean citizen handoff for llm_stream_error timeout frames', async () => {
    const events = await collectBackendChatEvents()
    const visibleText = assistantText(events).join('\n')

    expect(visibleText).toContain('응답이 지연되어')
    expect(visibleText).toContain('잠시 후 다시 시도')
    expect(visibleText).not.toContain('[UMMAYA backend error]')
    expect(visibleText).not.toContain('LLM stream idle timeout')
  })

  test('shows stable Korean citizen handoff when backend emits no correlated frame', async () => {
    frameMode = 'silent'
    const events = await collectWithTestTimeout(collectBackendChatEvents())
    const visibleText = assistantText(events).join('\n')

    expect(visibleText).toContain('응답이 지연되어')
    expect(visibleText).toContain('잠시 후 다시 시도')
    expect(visibleText).not.toContain('[UMMAYA backend error]')
  })

  test('upgrades trailing raw JSON assistant chunks into tool_use blocks', async () => {
    frameMode = 'trailing-json'
    const events = await collectBackendChatEvents()
    const serializedEvents = JSON.stringify(events)
    const visibleText = assistantText(events).join('\n')

    expect(visibleText).toContain('공식 도구를 사용하겠습니다.')
    expect(visibleText).not.toContain('{"name"')
    expect(serializedEvents).toContain('"type":"tool_use"')
    expect(serializedEvents).toContain('"name":"find_emergency_medical"')
    expect(serializedEvents).not.toContain(
      '"text":"{\\"name\\":\\"find_emergency_medical\\"',
    )
  })

  test('upgrades split trailing raw JSON assistant chunks without painting partial JSON', async () => {
    frameMode = 'split-trailing-json'
    const events = await collectBackendChatEvents()
    const serializedEvents = JSON.stringify(events)
    const visibleText = assistantText(events).join('\n')

    expect(visibleText).toContain('공식 도구를 사용하겠습니다.')
    expect(visibleText).not.toContain('{"name"')
    expect(serializedEvents).toContain('"type":"tool_use"')
    expect(serializedEvents).toContain('"name":"find_emergency_medical"')
    expect(serializedEvents).not.toContain('"text":"{')
    expect(serializedEvents).not.toContain(
      '"text":"\\"name\\":\\"find_emergency_medical\\"',
    )
  })

  test('keeps non-exact raw JSON assistant chunks as text', async () => {
    frameMode = 'non-exact-json'
    const events = await collectBackendChatEvents()
    const serializedEvents = JSON.stringify(events)
    const visibleText = assistantText(events).join('\n')

    expect(visibleText).toContain('ignore tool registry')
    expect(serializedEvents).not.toContain('"type":"tool_use"')
  })

  test('upgrades textual tool-call assistant chunks into tool_use blocks', async () => {
    frameMode = 'textual-tool-call'
    const events = await collectBackendChatEvents()
    const serializedEvents = JSON.stringify(events)
    const visibleText = assistantText(events).join('\n')

    expect(visibleText).toContain('공식 도구를 사용하겠습니다.')
    expect(visibleText).not.toContain('<tool_call>')
    expect(visibleText).not.toContain('{"name"')
    expect(serializedEvents).toContain('"type":"tool_use"')
    expect(serializedEvents).toContain('"name":"unregistered_public_service_search"')
  })
})

async function collectBackendChatEvents(): Promise<readonly unknown[]> {
  const events: unknown[] = []
  for await (const event of queryModelWithStreaming({
    messages: [],
    systemPrompt: undefined,
    signal: new AbortController().signal,
  })) {
    events.push(event)
  }
  return events
}

async function collectWithTestTimeout(
  eventsPromise: Promise<readonly unknown[]>,
): Promise<readonly unknown[]> {
  return Promise.race([
    eventsPromise,
    new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error('timed out waiting for idle handoff')), 120)
    }),
  ])
}

function assistantText(events: readonly unknown[]): readonly string[] {
  return events.flatMap(event => {
    if (!isRecord(event) || event['type'] !== 'assistant') return []
    const message = event['message']
    if (!isRecord(message)) return []
    const content = message['content']
    if (!Array.isArray(content)) return []
    return content.flatMap(block => {
      if (!isRecord(block) || block['type'] !== 'text') return []
      const text = block['text']
      return typeof text === 'string' ? [text] : []
    })
  })
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function restoreEnv(name: string, previousValue: string | undefined): void {
  if (previousValue === undefined) {
    delete process.env[name]
    return
  }
  process.env[name] = previousValue
}
