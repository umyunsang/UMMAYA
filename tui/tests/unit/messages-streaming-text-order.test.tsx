import { describe, expect, test } from 'bun:test'
import type { UUID } from 'crypto'
import {
  createSyntheticStreamingTextMessages,
} from '../../src/components/Messages.js'
import {
  createAssistantMessage,
  deriveUUID,
  normalizeMessages,
  reorderMessagesInUI,
  type StreamingToolUse,
} from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'

function createSyntheticStreamingToolUseMessages(
  streamingToolUses: StreamingToolUse[],
) {
  return streamingToolUses.flatMap(streamingToolUse => {
    const msg = createAssistantMessage({
      content: [streamingToolUse.contentBlock],
    })
    msg.uuid = deriveUUID(streamingToolUse.contentBlock.id as UUID, 0)
    return normalizeMessages([msg])
  })
}

describe('Messages streaming text order', () => {
  test('places streaming assistant text before the streaming tool card', () => {
    const baseMessages = normalizeMessages([
      createUserMessage({ content: '오늘 부산 사하구 날씨를 확인해줘.' }),
    ])
    const streamingTextMessages = createSyntheticStreamingTextMessages(
      '날씨 정보를 먼저 확인하겠습니다.',
    )
    const streamingToolMessages = createSyntheticStreamingToolUseMessages([
      {
        index: 1,
        contentBlock: {
          type: 'tool_use',
          id: 'call-streaming-weather',
          name: 'find',
          input: { tool_id: 'kma_current_observation' },
        },
        unparsedToolInput: '',
      },
    ])

    const ordered = reorderMessagesInUI(baseMessages, [
      ...streamingTextMessages,
      ...streamingToolMessages,
    ])

    const textIndex = ordered.findIndex(
      message =>
        message.type === 'assistant' &&
        message.message.content[0]?.type === 'text' &&
        message.message.content[0].text === '날씨 정보를 먼저 확인하겠습니다.',
    )
    const toolIndex = ordered.findIndex(
      message =>
        message.type === 'assistant' &&
        message.message.content[0]?.type === 'tool_use' &&
        message.message.content[0].id === 'call-streaming-weather',
    )

    expect(textIndex).toBeGreaterThanOrEqual(0)
    expect(toolIndex).toBeGreaterThanOrEqual(0)
    expect(textIndex).toBeLessThan(toolIndex)
  })
})
