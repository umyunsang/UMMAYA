// SPDX-License-Identifier: Apache-2.0
// Epic #2077 K-EXAONE tool wiring · T013
//
// 6 invariants from contracts/stream-event-projection.md § Test coverage:
//   I1 — tool_call frame yields two stream events, not SystemMessage
//   I2 — content_block_start carries id/name/input from frame fields
//   I3 — tool_result yields user-role tool_result content block
//   I4 — is_error: true set when envelope.kind === 'error'
//   I5 — multiple tool_calls produce sequential indices 1, 2, 3
//   I6 — terminal AssistantMessage content array contains text + N tool_use blocks
//
// Test harness: Bun mock.module() replaces bridgeSingleton and toolSerialization
// before deps.ts is loaded so queryModelWithStreaming (exposed via
// productionDeps().callModel) drives against a FakeBridge that captures the
// ChatRequestFrame's correlation_id from send() and yields pre-staged IPC
// frames tagged with that exact id.
//
// Module paths are absolute so Bun's module-specifier cache key matches the
// key used by deps.ts (which imports via relative paths that resolve to the
// same absolute paths). Using relative paths from a different directory caused
// cache-key mismatches in Bun v1.3.12.

import { describe, test, expect, mock } from 'bun:test'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TUI_ROOT = join(__dirname, '../..')

// ---------------------------------------------------------------------------
// FakeBridge factory
//
// send() captures the correlation_id from the ChatRequestFrame. The
// correlation_id is generated inside queryModelWithStreaming via randomUUID()
// and embedded in every outgoing ChatRequestFrame. deps.ts then filters
// incoming frames with `if (fa.correlation_id !== correlationId) continue`
// (line 156), so test frames MUST carry the exact same id.
//
// frames() spins-yields until send() has been called (which happens before
// the first for-await iteration inside deps.ts), then yields the staged
// frames built by the per-test factory function.
// ---------------------------------------------------------------------------

interface StagedFrame {
  kind: string
  correlation_id: string
  session_id: string
  ts: string
  role: string
  [k: string]: unknown
}

type FrameFactory = (correlationId: string) => StagedFrame[]

function makeFakeBridge(frameFactory: FrameFactory) {
  let capturedCorrelationId: string | null = null

  return {
    send(frame: unknown): boolean {
      const f = frame as { correlation_id?: string }
      capturedCorrelationId = f.correlation_id ?? null
      return true
    },
    async *frames(): AsyncIterable<unknown> {
      while (capturedCorrelationId === null) {
        await Promise.resolve()
      }
      const corrId = capturedCorrelationId
      for (const f of frameFactory(corrId)) {
        yield f
      }
    },
    close: async () => {},
    applied_frame_seqs: new Set<string>(),
    setSessionCredentials: (_sid: string, _tok: string) => {},
    lastSeenCorrelationId: null as string | null,
    lastSeenFrameSeq: null as number | null,
    signalDrop: () => {},
    // bridge.proc is read by crash-detector only; not exercised in unit tests.
    proc: {} as ReturnType<typeof Bun.spawn>,
  }
}

// ---------------------------------------------------------------------------
// Module mock setup
//
// mock.module() must be called BEFORE the module under test is imported.
// _currentBridge is swapped before each test via installBridge() and is
// returned by the mocked getOrCreateKosmosBridge() as a live closure,
// so each test sees its own fresh FakeBridge.
// ---------------------------------------------------------------------------

let _currentBridge: ReturnType<typeof makeFakeBridge> | null = null

function installBridge(factory: FrameFactory): void {
  _currentBridge = makeFakeBridge(factory)
}

// deps.ts statically imports `services/compact/autoCompact.js`, which itself
// `import { feature } from 'bun:bundle'`. Bun 1.2.x in CI does not honour
// preload plugin onResolve for `bun:bundle` under the test runner, so mocking
// autoCompact directly is the most reliable way to keep this test self-
// contained — productionDeps().callModel does not invoke autocompact() in
// any of these scenarios anyway.
// deps.ts statically imports from services/compact/{autoCompact,microCompact}.ts,
// both of which `import { feature } from 'bun:bundle'`. Bun 1.2.x in CI does
// not honour preload plugin onResolve for `bun:bundle` under the test runner,
// so mocking these compact modules directly is the most reliable way to keep
// this test self-contained — productionDeps().callModel does not invoke
// autocompact() or microcompact() in any of these scenarios.
mock.module(join(TUI_ROOT, 'src/services/compact/autoCompact.js'), () => ({
  autoCompactIfNeeded: async () => ({ messages: [], compacted: false }),
  getEffectiveContextWindowSize: () => 200_000,
  AUTOCOMPACT_BUFFER_TOKENS: 13_000,
  WARNING_THRESHOLD_BUFFER_TOKENS: 20_000,
  ERROR_THRESHOLD_BUFFER_TOKENS: 20_000,
  MANUAL_COMPACT_BUFFER_TOKENS: 3_000,
  getAutoCompactThreshold: () => 100_000,
  calculateTokenWarningState: () => null,
  isAutoCompactEnabled: () => false,
  shouldAutoCompact: async () => false,
}))

mock.module(join(TUI_ROOT, 'src/services/compact/microCompact.js'), () => ({
  microcompactMessages: async (messages: unknown[]) => messages,
  TIME_BASED_MC_CLEARED_MESSAGE: '[Old tool result content cleared]',
  consumePendingCacheEdits: () => null,
  getPinnedCacheEdits: () => [],
  pinCacheEdits: () => {},
  markToolsSentToAPIState: () => {},
  resetMicrocompactState: () => {},
  estimateMessageTokens: () => 0,
  evaluateTimeBasedTrigger: () => null,
}))

mock.module(join(TUI_ROOT, 'src/ipc/bridgeSingleton.js'), () => ({
  getOrCreateKosmosBridge: () => _currentBridge,
  getKosmosBridgeSessionId: () => 'test-session-handlers',
  closeKosmosBridge: async () => {},
}))

mock.module(join(TUI_ROOT, 'src/query/toolSerialization.js'), () => ({
  getToolDefinitionsForFrame: async () => [],
  toolToFunctionSchema: async () => ({}),
}))

mock.module(join(TUI_ROOT, 'src/utils/messages.js'), () => ({
  SYNTHETIC_MODEL: 'kosmos-test-model',
  createAssistantMessage: ({ content }: { content: unknown }) => ({
    type: 'assistant',
    uuid: 'assistant-message-stub',
    timestamp: new Date().toISOString(),
    message: {
      id: 'assistant-inner-stub',
      type: 'message',
      role: 'assistant',
      content:
        typeof content === 'string'
          ? [{ type: 'text', text: content }]
          : content,
      model: 'kosmos-test-model',
      stop_reason: null,
      stop_sequence: null,
      usage: {
        input_tokens: 0,
        output_tokens: 0,
        cache_creation_input_tokens: 0,
        cache_read_input_tokens: 0,
      },
    },
  }),
  createSystemMessage: (
    content: string,
    subtype = 'info',
    uuid = 'system-message-stub',
  ) => ({
    type: 'system',
    uuid,
    content,
    subtype,
    timestamp: new Date().toISOString(),
  }),
  createUserMessage: ({
    content,
    toolUseResult,
    sourceToolAssistantUUID,
  }: {
    content: unknown
    toolUseResult?: unknown
    sourceToolAssistantUUID?: string
  }) => ({
    type: 'user',
    uuid: 'user-message-stub',
    timestamp: new Date().toISOString(),
    message: { role: 'user', content },
    toolUseResult,
    sourceToolAssistantUUID,
  }),
}))

// Dynamic import AFTER mock.module() so the mocked bindings are in place
// when deps.ts resolves its own imports of bridgeSingleton / toolSerialization.
const { productionDeps } = await import(join(TUI_ROOT, 'src/query/deps.js'))

// ---------------------------------------------------------------------------
// Shared test runner
//
// Installs a fresh FakeBridge whose frames() yields the frames built by
// buildFrames(correlationId) — called after send() has captured the real
// correlation_id so every frame carries the correct id for deps.ts filtering.
// ---------------------------------------------------------------------------

function makeFrame(
  kind: string,
  corrId: string,
  extra: Record<string, unknown> = {},
): StagedFrame {
  return {
    kind,
    correlation_id: corrId,
    session_id: 'test-session-handlers',
    ts: new Date().toISOString(),
    role: 'backend',
    ...extra,
  }
}

async function run(buildFrames: (corrId: string) => StagedFrame[]): Promise<unknown[]> {
  const previousPrimary = process.env.KOSMOS_FRIENDLI_TOKEN
  const previousSession = process.env.KOSMOS_FRIENDLI_SESSION_ACTIVE
  process.env.KOSMOS_FRIENDLI_TOKEN = 'test-token-handlers'
  process.env.KOSMOS_FRIENDLI_SESSION_ACTIVE = '1'
  installBridge(buildFrames)
  try {
    const callModel = productionDeps().callModel
    const results: unknown[] = []
    for await (const ev of callModel({
      messages: [{ type: 'user', message: { role: 'user', content: 'hi' } }],
      systemPrompt: 'test system prompt',
    })) {
      results.push(ev)
    }
    return results
  } finally {
    if (previousPrimary === undefined) {
      delete process.env.KOSMOS_FRIENDLI_TOKEN
    } else {
      process.env.KOSMOS_FRIENDLI_TOKEN = previousPrimary
    }
    if (previousSession === undefined) {
      delete process.env.KOSMOS_FRIENDLI_SESSION_ACTIVE
    } else {
      process.env.KOSMOS_FRIENDLI_SESSION_ACTIVE = previousSession
    }
  }
}

// ---------------------------------------------------------------------------
// I1 — tool_call frame yields two stream events (content_block_start +
//       content_block_stop), not a SystemMessage.
// ---------------------------------------------------------------------------

describe('stream-event projection I1', () => {
  test('tool_call frame yields two stream events not SystemMessage', async () => {
    const results = await run((corrId) => [
      makeFrame('tool_call', corrId, {
        call_id: 'cid-001',
        name: 'lookup',
        arguments: { mode: 'fetch', tool_id: 'kma_forecast_fetch', query: 'test' },
      }),
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-001',
        delta: '',
        done: true,
      }),
    ])

    type StreamEventItem = {
      type: 'stream_event'
      event: { type: string; index?: number; content_block?: { type?: string } }
    }

    const streamEvents = results.filter(
      (r) => (r as { type?: string }).type === 'stream_event',
    ) as StreamEventItem[]

    // content_block_start with content_block.type === 'tool_use' must be present
    const toolUseStart = streamEvents.find(
      (e) =>
        e.event.type === 'content_block_start' &&
        e.event.content_block?.type === 'tool_use',
    )
    expect(toolUseStart).toBeDefined()

    // A matching content_block_stop must follow
    const hasStop = streamEvents.some((e) => e.event.type === 'content_block_stop')
    expect(hasStop).toBe(true)

    // No SystemMessage must be yielded for a tool_call frame
    const systemMessages = results.filter(
      (r) => (r as { type?: string }).type === 'system',
    )
    expect(systemMessages).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// I2 — content_block_start carries id/name/input from frame fields.
// ---------------------------------------------------------------------------

describe('stream-event projection I2', () => {
  test('content_block_start carries id, name, input from frame fields', async () => {
    const callId = 'call-abc-123'
    const toolName = 'lookup'
    const toolArgs = { mode: 'fetch', tool_id: 'hira_hospital_search' }

    const results = await run((corrId) => [
      makeFrame('tool_call', corrId, {
        call_id: callId,
        name: toolName,
        arguments: toolArgs,
      }),
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-002',
        delta: '',
        done: true,
      }),
    ])

    type StartEventItem = {
      type: 'stream_event'
      event: {
        type: string
        content_block?: { id?: string; name?: string; input?: unknown; type?: string }
      }
    }

    const streamEvents = results.filter(
      (r) => (r as { type?: string }).type === 'stream_event',
    ) as StartEventItem[]

    const toolUseStart = streamEvents.find(
      (e) =>
        e.event.type === 'content_block_start' &&
        e.event.content_block?.type === 'tool_use',
    )
    expect(toolUseStart).toBeDefined()

    const cb = toolUseStart!.event.content_block!
    expect(cb.id).toBe(callId)
    expect(cb.name).toBe(toolName)
    expect(cb.input).toEqual(toolArgs)
  })
})

// ---------------------------------------------------------------------------
// I3 — tool_result yields user-role message with tool_result content block.
// ---------------------------------------------------------------------------

describe('stream-event projection I3', () => {
  test('tool_result frame yields user-role tool_result content block', async () => {
    const callId = 'call-res-001'
    const envelope = { kind: 'lookup', data: [{ name: '서울대병원' }] }

    const results = await run((corrId) => [
      makeFrame('tool_call', corrId, {
        call_id: callId,
        name: 'lookup',
        arguments: {},
      }),
      makeFrame('tool_result', corrId, {
        call_id: callId,
        envelope,
      }),
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-003',
        delta: '',
        done: true,
      }),
    ])

    type UserMsgItem = {
      type: 'user'
      message: {
        role: string
        content: Array<{ type?: string; tool_use_id?: string; content?: string }>
      }
      toolUseResult?: { ok?: boolean; result?: unknown }
    }

    const userMessages = results.filter(
      (r) => (r as { type?: string }).type === 'user',
    ) as UserMsgItem[]

    expect(userMessages.length).toBeGreaterThan(0)

    const toolResultMsg = userMessages[0]!
    expect(toolResultMsg.message.role).toBe('user')

    const block = toolResultMsg.message.content[0]!
    expect(block.type).toBe('tool_result')
    expect(block.tool_use_id).toBe(callId)
    expect(toolResultMsg.toolUseResult?.ok).toBe(true)
    expect(toolResultMsg.toolUseResult?.result).toEqual(envelope)
  })
})

// ---------------------------------------------------------------------------
// I4 — is_error: true set when envelope.kind === 'error'.
// ---------------------------------------------------------------------------

describe('stream-event projection I4', () => {
  test('is_error: true set when envelope.kind === error', async () => {
    const callId = 'call-err-001'
    const errorEnvelope = { kind: 'error', message: 'adapter returned 500' }

    const results = await run((corrId) => [
      makeFrame('tool_call', corrId, {
        call_id: callId,
        name: 'lookup',
        arguments: {},
      }),
      makeFrame('tool_result', corrId, {
        call_id: callId,
        envelope: errorEnvelope,
      }),
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-004',
        delta: '',
        done: true,
      }),
    ])

    type UserMsgItem = {
      type: 'user'
      toolUseResult?: { ok?: boolean; error?: { message?: string } }
      message: { role: string; content: Array<{ type?: string; is_error?: boolean }> }
    }

    const userMessages = results.filter(
      (r) => (r as { type?: string }).type === 'user',
    ) as UserMsgItem[]

    expect(userMessages.length).toBeGreaterThan(0)
    const toolResultMsg = userMessages[0]!
    const block = toolResultMsg.message.content[0]!
    expect(block.is_error).toBe(true)
    expect(toolResultMsg.toolUseResult?.ok).toBe(false)
    expect(toolResultMsg.toolUseResult?.error?.message).toBe('adapter returned 500')
  })

  test('is_error: true set when primitive result carries nested error', async () => {
    const callId = 'call-err-primitive-001'
    const errorEnvelope = {
      kind: 'lookup',
      tool_id: 'kma_forecast_fetch',
      result: {
        kind: 'error',
        reason: 'invalid_params',
        message: 'Missing lat/lon; resolve_location must run first',
      },
      outbound_traces: [
        {
          method: 'GET',
          url: 'https://api.example.invalid/weather',
          status_code: 400,
        },
      ],
    }

    const results = await run((corrId) => [
      makeFrame('tool_call', corrId, {
        call_id: callId,
        name: 'lookup',
        arguments: {
          mode: 'fetch',
          tool_id: 'kma_forecast_fetch',
          params: {},
        },
      }),
      makeFrame('tool_result', corrId, {
        call_id: callId,
        envelope: errorEnvelope,
      }),
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-004-nested',
        delta: '',
        done: true,
      }),
    ])

    type UserMsgItem = {
      type: 'user'
      toolUseResult?: {
        ok?: boolean
        error?: { kind?: string; message?: string }
        outbound_traces?: unknown[]
      }
      message: {
        role: string
        content: Array<{ type?: string; is_error?: boolean; content?: string }>
      }
    }

    const userMessages = results.filter(
      (r) => (r as { type?: string }).type === 'user',
    ) as UserMsgItem[]

    expect(userMessages.length).toBeGreaterThan(0)
    const toolResultMsg = userMessages[0]!
    const block = toolResultMsg.message.content[0]!
    expect(block.is_error).toBe(true)
    expect(toolResultMsg.toolUseResult?.ok).toBe(false)
    expect(toolResultMsg.toolUseResult?.error?.kind).toBe('invalid_params')
    expect(toolResultMsg.toolUseResult?.error?.message).toBe(
      'Missing lat/lon; resolve_location must run first',
    )
    expect(toolResultMsg.toolUseResult?.outbound_traces).toHaveLength(1)

    const llmFacing = JSON.parse(block.content ?? '{}') as Record<string, unknown>
    expect(llmFacing).not.toHaveProperty('outbound_traces')
  })
})

// ---------------------------------------------------------------------------
// I5 — multiple tool_calls produce sequential indices 1, 2, 3.
//
// The text block opens at index 0 on the first assistant_chunk delta.
// Each subsequent tool_use block claims the next available index (blockIndex
// is pre-incremented before content_block_start per the spec contract).
// ---------------------------------------------------------------------------

describe('stream-event projection I5', () => {
  test('three tool_calls produce content_block_start indices 1, 2, 3', async () => {
    const results = await run((corrId) => [
      // Opens text block at index 0
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-005',
        delta: 'hello',
        done: false,
      }),
      makeFrame('tool_call', corrId, {
        call_id: 'tc-1',
        name: 'lookup',
        arguments: { mode: 'fetch', tool_id: 'kma_forecast_fetch', query: 'q1' },
      }),
      makeFrame('tool_call', corrId, {
        call_id: 'tc-2',
        name: 'submit',
        arguments: { tool_id: 'foo', params: {} },
      }),
      makeFrame('tool_call', corrId, {
        call_id: 'tc-3',
        name: 'verify',
        arguments: { tool_id: 'bar', params: {} },
      }),
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-005',
        delta: '',
        done: true,
      }),
    ])

    type StartEventItem = {
      type: 'stream_event'
      event: { type: string; index?: number; content_block?: { type?: string } }
    }

    const streamEvents = results.filter(
      (r) => (r as { type?: string }).type === 'stream_event',
    ) as StartEventItem[]

    const toolUseStarts = streamEvents.filter(
      (e) =>
        e.event.type === 'content_block_start' &&
        e.event.content_block?.type === 'tool_use',
    )

    expect(toolUseStarts).toHaveLength(3)
    expect(toolUseStarts[0]!.event.index).toBe(1)
    expect(toolUseStarts[1]!.event.index).toBe(2)
    expect(toolUseStarts[2]!.event.index).toBe(3)
  })
})

// ---------------------------------------------------------------------------
// I6 — terminal AssistantMessage content array = text + N tool_use blocks.
//
// Sequence: assistant_chunk(delta='hello'), tool_call(id=A), tool_call(id=B),
//           assistant_chunk(done=true).
// Expected content array: 3 elements —
//   [{type:'text', text:'hello'}, {type:'tool_use', id:'A', name:'lookup'},
//    {type:'tool_use', id:'B', name:'submit'}]
// ---------------------------------------------------------------------------

describe('stream-event projection I6', () => {
  test('terminal AssistantMessage content array contains text + N tool_use blocks', async () => {
    const results = await run((corrId) => [
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-006',
        delta: 'hello',
        done: false,
      }),
      makeFrame('tool_call', corrId, {
        call_id: 'A',
        name: 'lookup',
        arguments: { mode: 'fetch', tool_id: 'kma_forecast_fetch', query: 'test' },
      }),
      makeFrame('tool_call', corrId, {
        call_id: 'B',
        name: 'submit',
        arguments: { tool_id: 'abc', params: {} },
      }),
      makeFrame('assistant_chunk', corrId, {
        message_id: 'mid-006',
        delta: '',
        done: true,
      }),
    ])

    type AssistantMsgItem = {
      type: 'assistant'
      message: {
        role: string
        content: Array<{ type?: string; id?: string; name?: string; text?: string }>
      }
    }

    const assistantMessages = results.filter(
      (r) => (r as { type?: string }).type === 'assistant',
    ) as AssistantMsgItem[]

    expect(assistantMessages.length).toBeGreaterThan(0)

    // The last assistant message is the terminal one (yielded on done=true)
    const terminal = assistantMessages[assistantMessages.length - 1]!
    const content = terminal.message.content

    // 2 tool_use blocks + text block = 3 elements total
    // Epic #2766 follow-up — render-order fix v2 (deps.ts root-cause):
    // tool_use blocks render BEFORE the text block so the citizen sees the
    // tool calls (chronologically first) before the synthesis. CC's order
    // looked like [text, tool_use[]] only because each CC turn carries at
    // most one block-type; KOSMOS' multi-turn-into-one-message assembly
    // makes the relative order load-bearing.
    expect(content).toHaveLength(3)

    expect(content[0]!.type).toBe('tool_use')
    expect(content[0]!.id).toBe('A')
    expect(content[0]!.name).toBe('lookup')

    expect(content[1]!.type).toBe('tool_use')
    expect(content[1]!.id).toBe('B')
    expect(content[1]!.name).toBe('submit')

    expect(content[2]!.type).toBe('text')
    // Leading whitespace is trimmed by deps.ts (accumulated.trimStart())
    expect(content[2]!.text).toBe('hello')
  })
})
