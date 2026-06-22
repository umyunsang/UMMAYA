import { describe, expect, test } from 'bun:test'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  getToolNames,
  serializedMessages,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

describe('UMMAYA provider support intent selection', () => {
  test('does not force workspace_bash for terminal streaming discussion', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [
          createUserMessage({
            content:
              '터미널 LLM 답변 스트리밍이 사용자에게 실시간처럼 느껴져야 하는 이유를 한국어로 설명해줘.',
          }),
        ],
      })

      expect(getToolNames(exchange.request)).not.toContain('workspace_bash')
      expect(exchange.request.tool_choice).toBeUndefined()
      expect(serializedMessages(exchange.request)).not.toContain(
        'Mandatory tool call: the host selected workspace_bash',
      )
    })
  })

  test('still forces workspace_bash for explicit git execution requests', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [
          createUserMessage({
            content: '현재 저장소의 git 상태를 확인해줘.',
          }),
        ],
      })

      expect(getToolNames(exchange.request)).toContain('workspace_bash')
      expect(exchange.request.tool_choice).toEqual({
        type: 'function',
        function: { name: 'workspace_bash' },
      })
      expect(serializedMessages(exchange.request)).toContain(
        'Mandatory tool call: the host selected workspace_bash',
      )
      expect(serializedMessages(exchange.request)).toContain(
        'brief user-visible prelude',
      )
      expect(serializedMessages(exchange.request)).not.toContain(
        'Do not answer with prose',
      )
    })
  })
})
