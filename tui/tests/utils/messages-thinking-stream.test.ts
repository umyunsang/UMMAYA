import { describe, expect, test } from 'bun:test'
import {
  handleMessageFromStream,
  type StreamingThinking,
  type StreamingToolUse,
} from '../../src/utils/messages.js'
import type { SpinnerMode } from '../../src/components/Spinner.js'
import type { Message } from '../../src/types/message.js'

describe('handleMessageFromStream CC-compatible stream contract', () => {
  test('paints provider-adapted progress as normal text_delta streaming text', () => {
    let responseLength = ''
    let streamingText: string | null = null
    let streamMode: SpinnerMode = 'requesting'
    let streamingTools: StreamingToolUse[] = []

    handleMessageFromStream(
      {
        type: 'stream_event',
        event: {
          type: 'content_block_delta',
          index: 0,
          delta: {
            type: 'text_delta',
            text: '도구 후보를 정리하고 있습니다.\n',
          },
        },
      } as never,
      (_message: Message) => {},
      delta => {
        responseLength += delta
      },
      mode => {
        streamMode = mode
      },
      update => {
        streamingTools = update(streamingTools)
      },
      undefined,
      undefined,
      undefined,
      update => {
        streamingText = update(streamingText)
      },
    )

    expect(responseLength).toBe('도구 후보를 정리하고 있습니다.\n')
    expect(streamMode).toBe('requesting')
    expect(streamingText).toBe('도구 후보를 정리하고 있습니다.\n')
    expect(streamingTools).toEqual([])
  })

  test('streams thinking_delta into live streaming thinking state', () => {
    let streamingThinking: StreamingThinking | null = null
    let responseLength = ''
    let streamMode: SpinnerMode = 'requesting'
    let streamingTools: StreamingToolUse[] = []

    handleMessageFromStream(
      {
        type: 'stream_event',
        event: {
          type: 'content_block_delta',
          index: 0,
          delta: {
            type: 'thinking_delta',
            thinking: 'checking weather risk',
          },
        },
      } as never,
      (_message: Message) => {},
      delta => {
        responseLength += delta
      },
      mode => {
        streamMode = mode
      },
      update => {
        streamingTools = update(streamingTools)
      },
      undefined,
      update => {
        streamingThinking = update(streamingThinking)
      },
    )

    expect(responseLength).toBe('checking weather risk')
    expect(streamMode).toBe('requesting')
    expect(streamingTools).toEqual([])
    expect(streamingThinking).toEqual({
      thinking: 'checking weather risk',
      isStreaming: true,
    })
  })

  test('marks live streaming thinking complete when its content block stops', () => {
    const beforeStop = Date.now()
    let streamingThinking: StreamingThinking | null = {
      thinking: 'checking weather risk',
      isStreaming: true,
    }
    const stopEvent: Parameters<typeof handleMessageFromStream>[0] = {
      type: 'stream_event',
      event: {
        type: 'content_block_stop',
        index: 0,
      },
    }

    handleMessageFromStream(
      stopEvent,
      (_message: Message) => {},
      () => {},
      () => {},
      update => update([]),
      undefined,
      update => {
        streamingThinking = update(streamingThinking)
      },
    )

    if (streamingThinking === null) {
      throw new Error('expected streaming thinking to be retained until auto-hide')
    }
    expect(streamingThinking.isStreaming).toBe(false)
    expect(streamingThinking.streamingEndedAt).toBeGreaterThanOrEqual(beforeStop)
  })

  test('clears completed streaming thinking when a new provider request starts', () => {
    let streamingThinking: StreamingThinking | null = {
      thinking: 'previous turn reasoning',
      isStreaming: false,
      streamingEndedAt: Date.now(),
    }

    handleMessageFromStream(
      {
        type: 'stream_request_start',
      },
      (_message: Message) => {},
      () => {},
      () => {},
      update => update([]),
      undefined,
      update => {
        streamingThinking = update(streamingThinking)
      },
    )

    expect(streamingThinking).toBeNull()
  })

  test('preserves streaming text when a tool_use block starts', () => {
    let streamingText: string | null = '도구 후보를 정리하고 있습니다.\n'

    handleMessageFromStream(
      {
        type: 'stream_event',
        event: {
          type: 'content_block_start',
          index: 1,
          content_block: {
            type: 'tool_use',
            id: 'tool-use-1',
            name: 'locate',
            input: {},
          } as never,
        },
      } as never,
      () => {},
      () => {},
      () => {},
      update => update([]),
      undefined,
      undefined,
      undefined,
      update => {
        streamingText = update(streamingText)
      },
    )

    expect(streamingText).toBe('도구 후보를 정리하고 있습니다.\n')
  })

  test('clears stale streaming text when a new text block starts', () => {
    let streamingText: string | null = '이전 답변입니다.\n'

    handleMessageFromStream(
      {
        type: 'stream_event',
        event: {
          type: 'content_block_start',
          index: 0,
          content_block: {
            type: 'text',
            text: '',
          },
        },
      } as never,
      (_message: Message) => {},
      () => {},
      () => {},
      update => update([]),
      undefined,
      undefined,
      undefined,
      update => {
        streamingText = update(streamingText)
      },
    )

    expect(streamingText).toBeNull()
  })

})
