import { describe, expect, test } from 'bun:test'
import {
  createStreamingThinkingLayoutMessage,
  getStreamingThinkingInsertIndex,
  insertStreamingThinkingLayoutMessage,
  isSameAssistantToolStack,
  isStreamingThinkingLayoutMessage,
} from '../../src/utils/multiToolLayout.js'
import { reorderMessagesInUI } from '../../src/utils/messageReorder.js'

const user = {
  type: 'user',
  message: { content: [{ type: 'text' }] },
}

function toolUse(id: string, messageId: string) {
  return {
    type: 'assistant',
    uuid: `${messageId}-${id}`,
    message: {
      id: messageId,
      content: [{ type: 'tool_use', id, name: 'lookup', input: {} }],
    },
  }
}

function toolResult(id: string) {
  return {
    type: 'user',
    uuid: `result-${id}`,
    message: {
      content: [{ type: 'tool_result', tool_use_id: id, content: '{}' }],
    },
    toolUseResult: { ok: true, result: {} },
  }
}

describe('multi-tool layout helpers', () => {
  test('suppresses margin for adjacent tool_use rows from one assistant message', () => {
    const first = toolUse('tool-1', 'assistant-message-1')
    const second = toolUse('tool-2', 'assistant-message-1')

    expect(isSameAssistantToolStack(first, second, new Set())).toBe(true)
  })

  test('suppresses margin for adjacent streaming tool_use rows before final message commit', () => {
    const first = toolUse('tool-1', 'streaming-a')
    const second = toolUse('tool-2', 'streaming-b')

    expect(isSameAssistantToolStack(first, second, new Set(['tool-1', 'tool-2']))).toBe(true)
  })

  test('does not suppress margin across unrelated assistant messages', () => {
    const first = toolUse('tool-1', 'assistant-message-1')
    const second = toolUse('tool-2', 'assistant-message-2')

    expect(isSameAssistantToolStack(first, second, new Set())).toBe(false)
  })

  test('inserts streaming thinking before the first tool_use after the latest user turn', () => {
    const messages = [user, toolUse('tool-1', 'assistant-message-1'), toolUse('tool-2', 'assistant-message-1')]

    expect(getStreamingThinkingInsertIndex(messages)).toBe(1)
  })

  test('appends streaming thinking when no tool_use has rendered yet', () => {
    expect(getStreamingThinkingInsertIndex([user])).toBe(1)
  })

  test('marks the synthetic streaming thinking row for layout-only rendering', () => {
    const row = createStreamingThinkingLayoutMessage('reasoning preview')

    expect(isStreamingThinkingLayoutMessage(row)).toBe(true)
    expect(row.type).toBe('system')
    expect(row.subtype).toBe('thinking')
  })

  test('inserts streaming thinking before the first tool row in the current turn', () => {
    const messages = [user, toolUse('tool-1', 'assistant-message-1'), toolResult('tool-1')]

    const withThinking = insertStreamingThinkingLayoutMessage(messages, 'reasoning preview')

    expect(withThinking).toHaveLength(4)
    expect(withThinking[0]).toBe(user)
    expect(isStreamingThinkingLayoutMessage(withThinking[1])).toBe(true)
    expect(withThinking[1]?.thinking).toBe('reasoning preview')
    expect(withThinking[2]).toBe(messages[1])
    expect(withThinking[3]).toBe(messages[2])
  })

  test('keeps tool_result visible when the matching tool_use is still streaming', () => {
    const result = toolResult('tool-1')
    const streamingTool = toolUse('tool-1', 'streaming-message')

    const reordered = reorderMessagesInUI([user, result] as never, [streamingTool] as never)

    expect(reordered).toHaveLength(3)
    expect(reordered[1]).toBe(streamingTool)
    expect(reordered[2]).toBe(result)
  })
})
