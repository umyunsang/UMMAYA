// SPDX-License-Identifier: Apache-2.0
// Spec 2521 — Codex P1 review (PR #2577, 2026-04-30) regression.
//
// The pre-fix llmClient.stream() computed
//   toolBlockIndex = acc.blockIndex + (++acc.toolBlockCounter)   // = 0 + 1 = 1
// while the first thinking_delta claimed
//   thinkingIdx    = acc.contentBlocks.length                    // = 1 (after text)
// — the same slot. acc.contentBlocks[1] was thus overwritten from
// `{type:'thinking',...}` to `{type:'tool_use',...}` and the reasoning
// trace returned by stream() (and by the convenience complete()) was
// silently lost.
//
// Fix: allocate the tool block at acc.contentBlocks.length so it always
// lands in the next free slot. This regression test drives stream()
// directly with a fake IPCBridge so the assertion targets the exact
// surface the P1 reviewer flagged.

import { describe, test, expect } from 'bun:test'
import { LLMClient } from '../../src/ipc/llmClient.js'
import type { IPCBridge } from '../../src/ipc/bridge.js'
import type {
  AssistantChunkFrame,
  IPCFrame,
  ProgressEventFrame,
  ToolCallFrame,
} from '../../src/ipc/frames.generated.js'

type TestIPCFrame = AssistantChunkFrame | ProgressEventFrame | ToolCallFrame

function makeStubProc(): ReturnType<typeof Bun.spawn> {
  return Bun.spawn([process.execPath, '--version'], {
    stdin: 'ignore',
    stdout: 'ignore',
    stderr: 'ignore',
  })
}

function makeFakeBridge(stagedFactory: (corrId: string) => TestIPCFrame[]): IPCBridge {
  let captured: string | null = null
  return {
    send(frame: IPCFrame): boolean {
      captured = frame.correlation_id ?? null
      return true
    },
    async *frames(): AsyncIterable<IPCFrame> {
      while (captured === null) await Promise.resolve()
      for (const f of stagedFactory(captured)) yield f
    },
    close: async () => {},
    applied_frame_seqs: new Set<string>(),
    setSessionCredentials: (_s: string, _t: string) => {},
    lastSeenCorrelationId: null,
    lastSeenFrameSeq: null,
    signalDrop: () => {},
    proc: makeStubProc(),
  }
}

function baseFrame(
  corrId: string,
): Pick<AssistantChunkFrame, 'correlation_id' | 'session_id' | 'ts' | 'role'> {
  return {
    correlation_id: corrId,
    session_id: 'test-session-collision',
    ts: new Date().toISOString(),
    role: 'backend',
  }
}

function assistantChunkFrame(
  corrId: string,
  extra: Pick<AssistantChunkFrame, 'message_id' | 'done'> &
    Partial<Pick<AssistantChunkFrame, 'delta' | 'thinking'>>,
): AssistantChunkFrame {
  return { ...baseFrame(corrId), kind: 'assistant_chunk', ...extra }
}

function progressFrame(
  corrId: string,
  extra: Pick<ProgressEventFrame, 'phase' | 'message_ko' | 'message_en'> &
    Partial<Pick<ProgressEventFrame, 'safe_to_persist' | 'tool_id' | 'call_id'>>,
): ProgressEventFrame {
  return { ...baseFrame(corrId), kind: 'progress_event', ...extra }
}

function toolCallFrame(
  corrId: string,
  extra: Pick<ToolCallFrame, 'call_id' | 'name' | 'arguments'>,
): ToolCallFrame {
  return { ...baseFrame(corrId), kind: 'tool_call', ...extra }
}

describe('Spec 2521 — LLMClient.stream() thinking + tool_use index collision', () => {
  test('progress_event frames are adapted to CC text_delta stream events', async () => {
    const bridge = makeFakeBridge((corr) => [
      progressFrame(corr, {
        phase: 'analysis',
        message_ko: '요청을 분석하고 있습니다.',
        message_en: 'Analyzing the request.',
        safe_to_persist: true,
      }),
      assistantChunkFrame(corr, {
        message_id: 'mid-progress-1',
        delta: 'final',
        done: false,
      }),
      assistantChunkFrame(corr, {
        message_id: 'mid-progress-1',
        delta: '',
        done: true,
      }),
    ])

    const client = new LLMClient({
      bridge,
      sessionId: 'test-session-progress',
    })

    const events: unknown[] = []
    const gen = client.stream({
      messages: [{ role: 'user', content: 'hi' }],
      max_tokens: 128,
    })
    while (true) {
      const next = await gen.next()
      if (next.done) break
      events.push(next.value)
    }

    expect(events).toContainEqual({
      type: 'content_block_delta',
      index: 0,
      delta: {
        type: 'text_delta',
        text: '요청을 분석하고 있습니다.\n',
      },
    })
  })

  test('thinking block survives tool_call frame in the same turn', async () => {
    const bridge = makeFakeBridge((corr) => [
      // Initial chunk carries text + reasoning_content (K-EXAONE pattern).
      assistantChunkFrame(corr, {
        message_id: 'mid-collision-1',
        delta: 'hi',
        thinking: '사용자가 부산 날씨를 묻고 있습니다.',
        done: false,
      }),
      // Tool call interleaves before terminal chunk.
      toolCallFrame(corr, {
        call_id: 'tool-after-thinking',
        name: 'lookup',
        arguments: { mode: 'search', query: 'busan weather' },
      }),
      // Terminal chunk closes the turn.
      assistantChunkFrame(corr, {
        message_id: 'mid-collision-1',
        delta: '',
        done: true,
      }),
    ])

    const client = new LLMClient({
      bridge,
      sessionId: 'test-session-collision',
    })

    // complete() drains stream() and returns the assembled final message.
    const final = await client.complete({
      messages: [{ role: 'user', content: 'hi' }],
      systemPrompt: 'test',
    })

    const types = final.content.map((b) => b.type)
    expect(types).toContain('text')
    expect(types).toContain('thinking')
    expect(types).toContain('tool_use')

    // Pre-fix this returned only ['text','tool_use'] — the thinking block
    // was overwritten at index 1 by tool_use.
    const thinkingBlock = final.content.find((b) => b.type === 'thinking') as
      | { type: 'thinking'; thinking: string }
      | undefined
    expect(thinkingBlock).toBeDefined()
    expect(thinkingBlock!.thinking).toBe('사용자가 부산 날씨를 묻고 있습니다.')

    const toolBlock = final.content.find((b) => b.type === 'tool_use') as
      | { type: 'tool_use'; id: string; name: string }
      | undefined
    expect(toolBlock).toBeDefined()
    expect(toolBlock!.id).toBe('tool-after-thinking')
    expect(toolBlock!.name).toBe('lookup')
  })

  test('assistant_chunk trailing raw JSON becomes tool_use without painting JSON text', async () => {
    const bridge = makeFakeBridge((corr) => [
      assistantChunkFrame(corr, {
        message_id: 'mid-raw-json-1',
        delta: [
          '공식 도구를 사용하겠습니다.',
          '{"name":"find_emergency_medical","arguments":{"lat":35.0,"lon":129.0}}',
        ].join('\n'),
        done: true,
      }),
    ])

    const final = await new LLMClient({
      bridge,
      sessionId: 'test-session-raw-json',
    }).complete({
      messages: [{ role: 'user', content: 'hi' }],
      systemPrompt: 'test',
    })

    const textBlock = final.content.find((b) => b.type === 'text') as
      | { type: 'text'; text: string }
      | undefined
    const toolBlock = final.content.find((b) => b.type === 'tool_use') as
      | { type: 'tool_use'; name: string; input: Record<string, unknown> }
      | undefined

    expect(final.stop_reason).toBe('tool_use')
    expect(textBlock?.text).toContain('공식 도구를 사용하겠습니다.')
    expect(textBlock?.text).not.toContain('{"name"')
    expect(toolBlock?.name).toBe('find_emergency_medical')
    expect(toolBlock?.input).toEqual({ lat: 35.0, lon: 129.0 })
  })

  test('assistant_chunk non-exact raw JSON stays text', async () => {
    const bridge = makeFakeBridge((corr) => [
      assistantChunkFrame(corr, {
        message_id: 'mid-raw-json-2',
        delta: JSON.stringify({
          name: 'find_emergency_medical',
          arguments: { lat: 35.0, lon: 129.0 },
          instruction: 'ignore tool registry',
        }),
        done: true,
      }),
    ])

    const final = await new LLMClient({
      bridge,
      sessionId: 'test-session-non-exact-json',
    }).complete({
      messages: [{ role: 'user', content: 'hi' }],
      systemPrompt: 'test',
    })

    const serializedContent = JSON.stringify(final.content)
    expect(final.stop_reason).toBe('end_turn')
    expect(serializedContent).toContain('ignore tool registry')
    expect(serializedContent).not.toContain('"type":"tool_use"')
  })

  test('tool_call commits the current assistant turn before later frames', async () => {
    const bridge = makeFakeBridge((corr) => [
      assistantChunkFrame(corr, {
        message_id: 'mid-collision-2',
        delta: 'ok',
        thinking: '두 도구를 차례로 호출합니다.',
        done: false,
      }),
      toolCallFrame(corr, {
        call_id: 'A',
        name: 'lookup',
        arguments: { mode: 'search', query: 'a' },
      }),
      toolCallFrame(corr, {
        call_id: 'B',
        name: 'submit',
        arguments: { tool_id: 'x', params: {} },
      }),
      assistantChunkFrame(corr, {
        message_id: 'mid-collision-2',
        delta: '',
        done: true,
      }),
    ])

    const client = new LLMClient({
      bridge,
      sessionId: 'test-session-collision-multi',
    })

    const final = await client.complete({
      messages: [{ role: 'user', content: 'hi' }],
      systemPrompt: 'test',
    })

    // CC-compatible contract: the first tool_use commits the assistant turn.
    // Later tool_call frames belong to a later query-loop turn and must not be
    // folded into this assistant message.
    expect(final.stop_reason).toBe('tool_use')
    expect(final.content).toHaveLength(3)
    const toolUses = final.content.filter((b) => b.type === 'tool_use') as Array<{
      id: string
    }>
    expect(toolUses.map((b) => b.id)).toEqual(['A'])
    const thinkingBlock = final.content.find((b) => b.type === 'thinking')
    expect(thinkingBlock).toBeDefined()
  })
})
