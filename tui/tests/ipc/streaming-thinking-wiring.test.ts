// SPDX-License-Identifier: Apache-2.0
// Spec 2521 — verify thinking_delta stream event triggers setStreamingThinking
// (live thinking visibility per spec SC-001).

import { describe, it, expect, mock } from 'bun:test'
import { handleMessageFromStream, type StreamingThinking } from '../../src/utils/messages.js'

describe('thinking_delta wiring (Spec 2521 live-thinking SWAP/llm-provider)', () => {
  it('calls onStreamingThinking with isStreaming=true on each thinking_delta event', () => {
    const setStreamingThinking = mock(
      (f: (current: StreamingThinking | null) => StreamingThinking | null) => {
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        f(null)
      },
    )

    const event = {
      type: 'stream_event' as const,
      event: {
        type: 'content_block_delta' as const,
        index: 0,
        delta: {
          type: 'thinking_delta' as const,
          thinking: '사용자가 부산 날씨를 물어보고 있습니다.',
        },
      },
    }

    handleMessageFromStream(
      // @ts-expect-error — minimal event shape; messages.ts only inspects type + event fields
      event,
      mock(),
      mock(),
      mock(),
      mock(),
      undefined,
      setStreamingThinking,
    )

    expect(setStreamingThinking).toHaveBeenCalled()
    const lastCall = setStreamingThinking.mock.calls.at(-1)
    expect(lastCall).toBeDefined()
    const updaterFn = lastCall![0]
    const result = updaterFn(null)
    expect(result).toEqual({
      thinking: '사용자가 부산 날씨를 물어보고 있습니다.',
      isStreaming: true,
      streamingEndedAt: undefined,
    })
  })

  it('appends thinking text across consecutive thinking_delta events', () => {
    const updates: (StreamingThinking | null)[] = []

    const setStreamingThinking = mock(
      (f: (current: StreamingThinking | null) => StreamingThinking | null) => {
        const prev = updates.at(-1) ?? null
        const next = f(prev)
        updates.push(next)
      },
    )

    for (const chunk of ['먼저 ', '도구를 ', '검색합니다.']) {
      handleMessageFromStream(
        // @ts-expect-error — minimal shape
        {
          type: 'stream_event' as const,
          event: {
            type: 'content_block_delta' as const,
            index: 0,
            delta: { type: 'thinking_delta' as const, thinking: chunk },
          },
        },
        mock(),
        mock(),
        mock(),
        mock(),
        undefined,
        setStreamingThinking,
      )
    }

    expect(updates.length).toBe(3)
    expect(updates[2]).toEqual({
      thinking: '먼저 도구를 검색합니다.',
      isStreaming: true,
      streamingEndedAt: undefined,
    })
  })
})
