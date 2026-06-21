import { afterEach, beforeEach, describe, expect, mock, test } from 'bun:test'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { ChatRequestFrame, IPCFrame } from '../../../src/ipc/frames.generated.js'

const testDir = dirname(fileURLToPath(import.meta.url))
const tuiRoot = join(testDir, '../../..')

const sentFrames: ChatRequestFrame[] = []
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
    yield {
      session_id: 'test-session-backend-chat-parity',
      correlation_id: requestFrame.correlation_id,
      ts: '2026-06-16T00:00:00.000Z',
      version: '1.0',
      role: 'backend',
      frame_seq: 1,
      kind: 'assistant_chunk',
      delta: '\n\n실제 K-EXAONE 응답을 그대로 표시합니다.',
      done: false,
    }
    yield {
      session_id: 'test-session-backend-chat-parity',
      correlation_id: requestFrame.correlation_id,
      ts: '2026-06-16T00:00:00.001Z',
      version: '1.0',
      role: 'backend',
      frame_seq: 2,
      kind: 'assistant_chunk',
      delta: ' 최종 프레임도 같은 문자열이어야 합니다.',
      done: true,
    }
  },
}

await mock.module(join(tuiRoot, 'src/ipc/bridgeSingleton.js'), () => ({
  getOrCreateUmmayaBridge: () => fakeBridge,
  getUmmayaBridgeSessionId: () => 'test-session-backend-chat-parity',
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

describe('backend chat stream final parity', () => {
  test('keeps streamed text deltas identical to the final assistant text block', async () => {
    const events = await collectBackendChatEvents()

    expect(streamedText(events)).toBe(assistantText(events).join(''))
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

function streamedText(events: readonly unknown[]): string {
  return events.map(event => {
    if (!isRecord(event) || event['type'] !== 'stream_event') return ''
    const streamEvent = event['event']
    if (!isRecord(streamEvent) || streamEvent['type'] !== 'content_block_delta') {
      return ''
    }
    const delta = streamEvent['delta']
    if (!isRecord(delta) || delta['type'] !== 'text_delta') return ''
    const text = delta['text']
    return typeof text === 'string' ? text : ''
  }).join('')
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
