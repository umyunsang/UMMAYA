import { describe, expect, mock, test } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { z } from 'zod/v4'
import { TerminalSizeContext } from '../../src/ink/components/TerminalSizeContext.js'
import { TerminalWriteProvider } from '../../src/ink/useTerminalNotification.js'
import { Text } from '../../src/ink.js'
import { ThemeProvider } from '../../src/theme/provider.js'
import type { Tools } from '../../src/Tool.js'
import {
  createAssistantMessage,
} from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'

mock.module(new URL('../../src/components/Markdown.js', import.meta.url).pathname, () => ({
  Markdown: ({ children }: { readonly children: React.ReactNode }) => <Text>{children}</Text>,
  StreamingMarkdown: ({ children }: { readonly children: React.ReactNode }) => <Text>{children}</Text>,
}))

const { Messages } = await import('../../src/components/Messages.js')

function createNamedTool(name: string): Tools[number] {
  const inputSchema = z.object({})
  return {
    name,
    inputSchema,
    async description() {
      return name
    },
    isEnabled: () => true,
    isConcurrencySafe: () => false,
    isReadOnly: () => true,
    isDestructive: () => false,
    checkPermissions: async input => ({ behavior: 'allow', updatedInput: input }),
    async call() {
      return { data: {} }
    },
    mapToolResultToToolResultBlockParam(_data, toolUseID) {
      return { type: 'tool_result', tool_use_id: toolUseID, content: name }
    },
    userFacingName: () => name,
    toAutoClassifierInput: () => '',
  }
}

describe('Messages streaming text order', () => {
  test('renders active streaming text outside reordered completed messages', () => {
    const { lastFrame } = render(
      <ThemeProvider>
        <TerminalWriteProvider value={() => {}}>
          <TerminalSizeContext.Provider value={{ columns: 100, rows: 30 }}>
            <Messages
              messages={[
                createUserMessage({ content: '오늘 부산 사하구 날씨를 확인해줘.' }),
                createAssistantMessage({
                  content: [
                    {
                      type: 'tool_use',
                      id: 'call-weather',
                      name: 'find',
                      input: { tool_id: 'kma_current_observation' },
                    },
                  ],
                }),
                createUserMessage({
                  content: [
                    {
                      type: 'tool_result',
                      tool_use_id: 'call-weather',
                      content: '기온 24.5도',
                    },
                  ],
                }),
              ]}
              tools={[]}
              commands={[]}
              verbose={false}
              toolJSX={null}
              toolUseConfirmQueue={[]}
              inProgressToolUseIDs={new Set()}
              isMessageSelectorVisible={false}
              conversationId="streaming-text-test"
              screen="prompt"
              streamingToolUses={[]}
              showAllInTranscript={false}
              hideLogo={true}
              isLoading={true}
              streamingText="기상청 adapter 결과 기준으로 확인된 값만 정리합니다.\n현재관측을 정리하는 중입니다."
            />
          </TerminalSizeContext.Provider>
        </TerminalWriteProvider>
      </ThemeProvider>,
    )

    const frame = lastFrame() ?? ''
    expect(frame).toContain('기상청 adapter 결과 기준으로 확인된 값만 정리합니다.')
    expect(frame).toContain('현재관측을 정리하는 중입니다.')
  })

  test('renders active streaming text before an active streaming tool card', () => {
    const { lastFrame } = render(
      <ThemeProvider>
        <TerminalWriteProvider value={() => {}}>
          <TerminalSizeContext.Provider value={{ columns: 100, rows: 30 }}>
            <Messages
              messages={[
                createUserMessage({ content: '오늘 부산 사하구 날씨를 확인해줘.' }),
              ]}
              tools={[createNamedTool('find')]}
              commands={[]}
              verbose={false}
              toolJSX={null}
              toolUseConfirmQueue={[]}
              inProgressToolUseIDs={new Set()}
              isMessageSelectorVisible={false}
              conversationId="streaming-text-tool-order-test"
              screen="prompt"
              streamingToolUses={[
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
              ]}
              showAllInTranscript={false}
              hideLogo={true}
              isLoading={true}
              streamingText="날씨 정보를 먼저 확인하겠습니다."
            />
          </TerminalSizeContext.Provider>
        </TerminalWriteProvider>
      </ThemeProvider>,
    )

    const frame = lastFrame() ?? ''
    const textIndex = frame.indexOf('날씨 정보를 먼저 확인하겠습니다.')
    const toolIndex = frame.indexOf('find')
    expect(textIndex).toBeGreaterThanOrEqual(0)
    expect(toolIndex).toBeGreaterThanOrEqual(0)
    expect(textIndex).toBeLessThan(toolIndex)
  })
})
