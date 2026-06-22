import { describe, expect, test } from 'bun:test'
import { handleMessageFromStream } from '../../src/utils/messages.js'

describe('handleMessageFromStream complete assistant thinking blocks', () => {
  test('captures complete assistant thinking blocks for transcript display', () => {
    let capturedThinking: string | null = null

    handleMessageFromStream(
      {
        type: 'assistant',
        uuid: 'assistant-1',
        timestamp: 0,
        message: {
          id: 'assistant-1',
          content: [
            {
              type: 'thinking',
              thinking: '도구 호출 전 추론입니다.',
            },
            {
              type: 'tool_use',
              id: 'call-1',
              name: 'lookup',
              input: {},
            },
          ],
        },
      } as never,
      () => {},
      () => {},
      () => {},
      update => update([]),
      undefined,
      update => {
        const next = update(null)
        capturedThinking = next?.thinking ?? null
      },
      undefined,
      () => null,
    )

    expect(capturedThinking).toBe('도구 호출 전 추론입니다.')
  })
})
