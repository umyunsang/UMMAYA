import { describe, expect, test } from 'bun:test'
import { runWithCwdOverride } from '../../src/utils/cwd.js'
import { query } from '../../src/query.js'
import { runToolUseBlocks } from '../../src/query/toolRunner.js'
import { getWorkspaceTools } from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import type { Message } from '../../src/types/message.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import { asSystemPrompt } from '../../src/utils/systemPromptType.js'
import {
  createFileStateCacheWithSizeLimit,
  READ_FILE_STATE_CACHE_SIZE,
} from '../../src/utils/fileStateCache.js'

const REPO_ROOT = '/Users/um-yunsang/UMMAYA'

type ModelParams = {
  readonly messages: readonly Message[]
}

function createToolUseContext(messages: Message[]) {
  const tools = getWorkspaceTools()
  const toolPermissionContext = {
    mode: 'default',
    additionalWorkingDirectories: new Map(),
    alwaysAllowRules: {},
    alwaysDenyRules: {},
    alwaysAskRules: {},
    isBypassPermissionsModeAvailable: false,
  }
  return {
    options: {
      commands: [],
      debug: false,
      mainLoopModel: 'test-model',
      tools,
      verbose: false,
      thinkingConfig: { type: 'disabled' },
      mcpClients: [],
      mcpResources: {},
      isNonInteractiveSession: false,
      agentDefinitions: { activeAgents: [], allowedAgentTypes: [] },
    },
    abortController: new AbortController(),
    readFileState: createFileStateCacheWithSizeLimit(
      READ_FILE_STATE_CACHE_SIZE,
    ),
    getAppState: () => ({
      toolPermissionContext,
      fastMode: false,
      mcp: { tools: [], clients: [] },
    }),
    setAppState: () => {},
    setInProgressToolUseIDs: () => {},
    setResponseLength: () => {},
    updateFileHistoryState: () => {},
    updateAttributionState: () => {},
    messages,
  }
}

function hasToolResult(
  messages: readonly Message[],
  toolUseId: string,
): boolean {
  return toolResultIds(messages).includes(toolUseId)
}

function toolResultIds(messages: readonly Message[]): readonly string[] {
  return messages.flatMap(message =>
    message.type === 'user' && Array.isArray(message.message.content)
      ? message.message.content
          .filter(block => block.type === 'tool_result')
          .map(block => block.tool_use_id)
      : [],
  )
}

function messageSummary(messages: readonly Message[]): string {
  return messages
    .map(message => {
      const content = message.message.content
      if (!Array.isArray(content)) {
        return `${message.type}:text:${content.slice(0, 80)}`
      }
      const blockSummary = content
        .map(block => {
          if (block.type === 'tool_use') return `tool_use:${block.name}:${block.id}`
          if (block.type === 'tool_result') return `tool_result:${block.tool_use_id}`
          return block.type
        })
        .join(',')
      return `${message.type}:${blockSummary}`
    })
    .join(' | ')
}

describe('S1 workspace support continuation', () => {
  test('returns recoverable tool_result when workspace_grep input misses required pattern', async () => {
    await runWithCwdOverride(REPO_ROOT, async () => {
      const messages = [
        createUserMessage({
          content: '작업공간에서 관련 파일을 찾아줘.',
        }),
      ]
      const assistantMessage = createAssistantMessage({
        content: [
          {
            type: 'tool_use',
            id: 'call-malformed-workspace-grep-s1',
            name: 'workspace_grep',
            input: {},
          },
        ],
      })

      const resultMessages = await runToolUseBlocks({
        blocks: [
          {
            type: 'tool_use',
            id: 'call-malformed-workspace-grep-s1',
            name: 'workspace_grep',
            input: {},
          },
        ],
        assistantMessage,
        messages,
        toolUseContext: createToolUseContext(messages),
        canUseTool: async (_tool, input) => ({
          behavior: 'allow',
          updatedInput: input,
        }),
      })

      expect(resultMessages).toHaveLength(1)
      const content = resultMessages[0]?.message.content
      if (!Array.isArray(content)) {
        throw new Error('Expected malformed workspace_grep to return a tool_result block.')
      }
      const toolResult = content.find(block => block.type === 'tool_result')
      if (toolResult?.type !== 'tool_result') {
        throw new Error('Expected malformed workspace_grep to return a tool_result block.')
      }

      expect(toolResult.tool_use_id).toBe('call-malformed-workspace-grep-s1')
      expect(toolResult.is_error).toBe(true)
      expect(String(toolResult.content)).toContain('InputValidationError')
      expect(String(toolResult.content)).toContain('pattern')
    })
  })

  test('continues from real workspace_grep result into workspace_read and final answer', async () => {
    await runWithCwdOverride(REPO_ROOT, async () => {
      const prompt =
        '이 작업공간에서 docs/configuration.md와 docs/vision.md를 찾아서 설정 관련 핵심만 요약해줘. 파일은 수정하지 마.'
      const messages = [createUserMessage({ content: prompt })]
      let providerCallCount = 0
      const providerMessageCounts: number[] = []

      const deps = {
        async *callModel(params: ModelParams) {
          providerCallCount += 1
          providerMessageCounts.push(params.messages.length)
          if (providerCallCount === 1) {
            yield createAssistantMessage({
              content: [
                {
                  type: 'text',
                  text: '먼저 요청하신 두 파일을 찾아 내용을 확인하겠습니다.',
                },
                {
                  type: 'tool_use',
                  id: 'call-workspace-grep-s1',
                  name: 'workspace_grep',
                  input: {
                    pattern: 'Codex Continuation Setup',
                    path: 'docs/onboarding/codex-continuation.md',
                  },
                },
              ],
            })
            return
          }
          expect(hasToolResult(params.messages, 'call-workspace-grep-s1')).toBe(
            true,
          )
          if (providerCallCount === 2) {
            yield createAssistantMessage({
              content: [
                {
                  type: 'text',
                  text: '설정 파일을 더 찾아보겠습니다.',
                },
                {
                  type: 'tool_use',
                  id: 'call-workspace-read-s1',
                  name: 'workspace_read',
                  input: { file_path: 'docs/configuration.md' },
                },
              ],
            })
            return
          }
          if (!hasToolResult(params.messages, 'call-workspace-read-s1')) {
            throw new Error(messageSummary(params.messages))
          }
          yield createAssistantMessage({
            content: '설정 관련 핵심 요약입니다.',
          })
        },
        microcompact: async (currentMessages: readonly Message[]) => ({
          messages: currentMessages,
        }),
        autocompact: async () => ({
          compactionResult: null,
          consecutiveFailures: undefined,
        }),
        uuid: () => `uuid-s1-workspace-${providerCallCount}`,
      }

      const emitted: Message[] = []
      for await (const event of query({
        messages,
        systemPrompt: asSystemPrompt(['test system prompt']),
        userContext: {},
        systemContext: {},
        canUseTool: async (_tool, input) => ({
          behavior: 'allow',
          updatedInput: input,
        }),
        toolUseContext: createToolUseContext(messages),
        querySource: 'sdk',
        maxTurns: 5,
        deps,
      })) {
        if (event.type === 'assistant' || event.type === 'user') {
          emitted.push(event)
        }
      }

      expect(providerCallCount).toBe(3)
      expect(providerMessageCounts).toEqual([1, 3, 5])
      expect(hasToolResult(emitted, 'call-workspace-grep-s1')).toBe(true)
      expect(hasToolResult(emitted, 'call-workspace-read-s1')).toBe(true)
      expect(
        emitted.some(
          message =>
            message.type === 'assistant' &&
            message.message.content.some(
              block =>
                block.type === 'text' &&
                block.text.includes('설정 관련 핵심 요약입니다.'),
            ),
        ),
      ).toBe(true)
    })
  })
})
