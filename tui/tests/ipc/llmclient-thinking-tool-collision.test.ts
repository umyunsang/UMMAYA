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

type CapturedSend = { correlation_id?: string }

function makeFakeBridge(stagedFactory: (corrId: string) => unknown[]) {
  let captured: string | null = null
  return {
    send(frame: unknown): boolean {
      captured = (frame as CapturedSend).correlation_id ?? null
      return true
    },
    async *frames(): AsyncIterable<unknown> {
      while (captured === null) await Promise.resolve()
      for (const f of stagedFactory(captured)) yield f
    },
    close: async () => {},
    applied_frame_seqs: new Set<string>(),
    setSessionCredentials: (_s: string, _t: string) => {},
    lastSeenCorrelationId: null as string | null,
    lastSeenFrameSeq: null as number | null,
    signalDrop: () => {},
    proc: {} as unknown,
  }
}

function frame(
  kind: string,
  corrId: string,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    kind,
    correlation_id: corrId,
    session_id: 'test-session-collision',
    ts: new Date().toISOString(),
    role: 'backend',
    ...extra,
  }
}

describe('Spec 2521 — LLMClient.stream() thinking + tool_use index collision', () => {
  test('progress_event frames are adapted to CC text_delta stream events', async () => {
    const bridge = makeFakeBridge((corr) => [
      frame('progress_event', corr, {
        phase: 'analysis',
        message_ko: '요청을 분석하고 있습니다.',
        message_en: 'Analyzing the request.',
        safe_to_persist: true,
      }),
      frame('assistant_chunk', corr, {
        message_id: 'mid-progress-1',
        delta: 'final',
        done: false,
      }),
      frame('assistant_chunk', corr, {
        message_id: 'mid-progress-1',
        delta: '',
        done: true,
      }),
    ])

    const client = new LLMClient({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      bridge: bridge as any,
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
      frame('assistant_chunk', corr, {
        message_id: 'mid-collision-1',
        delta: 'hi',
        thinking: '사용자가 부산 날씨를 묻고 있습니다.',
        done: false,
      }),
      // Tool call interleaves before terminal chunk.
      frame('tool_call', corr, {
        call_id: 'tool-after-thinking',
        name: 'lookup',
        arguments: { mode: 'search', query: 'busan weather' },
      }),
      // Terminal chunk closes the turn.
      frame('assistant_chunk', corr, {
        message_id: 'mid-collision-1',
        delta: '',
        done: true,
      }),
    ])

    const client = new LLMClient({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      bridge: bridge as any,
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

  test('tool_call commits the current assistant turn before later frames', async () => {
    const bridge = makeFakeBridge((corr) => [
      frame('assistant_chunk', corr, {
        message_id: 'mid-collision-2',
        delta: 'ok',
        thinking: '두 도구를 차례로 호출합니다.',
        done: false,
      }),
      frame('tool_call', corr, {
        call_id: 'A',
        name: 'lookup',
        arguments: { mode: 'search', query: 'a' },
      }),
      frame('tool_call', corr, {
        call_id: 'B',
        name: 'submit',
        arguments: { tool_id: 'x', params: {} },
      }),
      frame('assistant_chunk', corr, {
        message_id: 'mid-collision-2',
        delta: '',
        done: true,
      }),
    ])

    const client = new LLMClient({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      bridge: bridge as any,
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
