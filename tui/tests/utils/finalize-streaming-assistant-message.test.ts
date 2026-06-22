import { describe, expect, test } from 'bun:test'
import {
  createAssistantMessage,
  createUserMessage,
  finalizeStreamingAssistantMessage,
} from '../../src/utils/messages.js'

describe('finalizeStreamingAssistantMessage', () => {
  test('commits streamed provider text when the turn ends without an assistant message', () => {
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
      createAssistantMessage({
        content: '종합소득세 신고 상태를 확인했고 다음 단계만 남았습니다.',
      }),
    ]

    const finalized = finalizeStreamingAssistantMessage({
      messages,
      streamingText: '스트리밍 미리보기 텍스트입니다.\n',
      turnStartMessageCount: 3,
    })

    expect(finalized).toEqual(messages)
  })
})
