import { describe, expect, test } from 'bun:test'
import {
  finalizeStreamingAssistantMessage,
  handleMessageFromStream,
  type StreamingToolUse,
  createAssistantMessage,
  createUserMessage,
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

  test('keeps CC thinking_delta handling length-only in the stream handler', () => {
    let thinkingCallbackCalled = false
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
      () => {
        thinkingCallbackCalled = true
        return null
      },
    )

    expect(responseLength).toBe('checking weather risk')
    expect(streamMode).toBe('requesting')
    expect(streamingTools).toEqual([])
    expect(thinkingCallbackCalled).toBe(false)
  })

  test('clears streaming text when a tool_use block starts, matching CC', () => {
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

    expect(streamingText).toBeNull()
  })

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

  test('finalizes streamed provider text into a committed assistant when the turn ends without one', () => {
    const messages = [
      createUserMessage({ content: '이전 질문입니다.' }),
      createAssistantMessage({ content: '이전 답변입니다.' }),
      createUserMessage({ content: '지금 종합소득세 상태를 요약해줘.' }),
    ]

    const finalized = finalizeStreamingAssistantMessage({
      messages,
      streamingText: '종합소득세 신고 상태를 확인했고 다음 단계만 남았습니다.\n',
      turnStartMessageCount: messages.length,
    })

    expect(finalized).toHaveLength(messages.length + 1)
    const appended = finalized.at(-1)
    expect(appended?.type).toBe('assistant')
    if (appended?.type !== 'assistant') {
      throw new Error('expected synthesized assistant message')
    }
    expect(
      appended.message.content.some(
        block =>
          block.type === 'text' &&
          block.text === '종합소득세 신고 상태를 확인했고 다음 단계만 남았습니다.\n',
      ),
    ).toBe(true)
  })

  test('does not duplicate a finalized assistant when the current turn already committed one', () => {
    const messages = [
      createUserMessage({ content: '이전 질문입니다.' }),
      createAssistantMessage({ content: '이전 답변입니다.' }),
      createUserMessage({ content: '지금 종합소득세 상태를 요약해줘.' }),
      createAssistantMessage({ content: '종합소득세 신고 상태를 확인했고 다음 단계만 남았습니다.' }),
    ]

    const finalized = finalizeStreamingAssistantMessage({
      messages,
      streamingText: '스트리밍 미리보기 텍스트입니다.\n',
      turnStartMessageCount: 3,
    })

    expect(finalized).toEqual(messages)
  })
})
