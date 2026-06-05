import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import { query } from '../../src/query.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import type { QueryDeps } from '../../src/query/deps.js'
import type { Tool, ToolUseContext } from '../../src/Tool.js'
import type { AssistantMessage, Message } from '../../src/types/message.js'

const STATIC_QUERY_LOOP_PROGRESS_TEXTS = [
  '요청을 분석하고 선택된 도구를 호출하고 있습니다.',
  '도구 결과를 읽고 다음 단계를 판단하고 있습니다.',
]

const EMPTY_USAGE = {
  input_tokens: 0,
  output_tokens: 0,
  cache_creation_input_tokens: 0,
  cache_read_input_tokens: 0,
  server_tool_use: { web_search_requests: 0, web_fetch_requests: 0 },
  service_tier: null,
  cache_creation: {
    ephemeral_1h_input_tokens: 0,
    ephemeral_5m_input_tokens: 0,
  },
  inference_geo: null,
  iterations: null,
  speed: null,
}

function createAppState() {
  return {
    toolPermissionContext: {
      mode: 'default',
      additionalWorkingDirectories: new Map(),
      alwaysAllowRules: {},
      alwaysDenyRules: {},
      alwaysAskRules: {},
      isBypassPermissionsModeAvailable: false,
    },
    fastMode: false,
    mcp: { tools: [], clients: [] },
    effortValue: undefined,
    reasoningMode: undefined,
    advisorModel: undefined,
  }
}

function createLocateTool(): Tool {
  const inputSchema = z.object({
    query: z.string(),
  })
  return {
    name: 'locate',
    inputSchema,
    async description() {
      return 'Locate a public-service place or address.'
    },
    isEnabled: () => true,
    isConcurrencySafe: () => false,
    isReadOnly: () => true,
    isDestructive: () => false,
    checkPermissions: async input => ({ behavior: 'allow', updatedInput: input }),
    async call(args) {
      return {
        data: {
          ok: true,
          query: args.query,
          address: '부산 사하구 낙동대로550번길 37',
        },
      }
    },
    mapToolResultToToolResultBlockParam(data, toolUseID) {
      return {
        type: 'tool_result',
        tool_use_id: toolUseID,
        content: JSON.stringify(data),
      }
    },
    userFacingName: () => 'locate',
    toAutoClassifierInput: () => '',
  } as Tool
}

function createToolUseContext(tools: Tool[]): ToolUseContext {
  const appState = createAppState()
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
    readFileState: {} as ToolUseContext['readFileState'],
    getAppState: () => appState as never,
    setAppState: () => {},
    setInProgressToolUseIDs: () => {},
    setResponseLength: () => {},
    updateFileHistoryState: () => {},
    updateAttributionState: () => {},
    messages: [],
  } as ToolUseContext
}

type AssistantContent = Parameters<typeof createAssistantMessage>[0]['content']

function createDeps(firstContent: AssistantContent): QueryDeps {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      if (callCount === 1) {
        yield createAssistantMessage({
          content: firstContent,
        })
        return
      }
      yield createAssistantMessage({
        content: [{ type: 'text', text: '확인한 주소를 정리했습니다.' }],
      })
    },
    microcompact: async messages => ({ messages }),
    autocompact: async () => ({
      compactionResult: null,
      consecutiveFailures: undefined,
    }),
    uuid: () => `uuid-${callCount}`,
  } as QueryDeps
}

async function runQueryWithFirstAssistantContent(firstContent: AssistantContent) {
  const tools = [createLocateTool()]
  const messages: Message[] = [
    {
      type: 'user',
      uuid: 'user-1',
      timestamp: new Date().toISOString(),
      message: {
        role: 'user',
        content: [
          { type: 'text', text: '동아대학교 승학캠퍼스 위치를 확인해줘' },
        ],
      },
    },
  ] as Message[]

  const emitted: Message[] = []
  for await (const message of query({
    messages,
    systemPrompt: 'test system prompt' as never,
    userContext: '',
    systemContext: [],
    canUseTool: async (_tool, input) => ({
      behavior: 'allow',
      updatedInput: input,
    }),
    toolUseContext: createToolUseContext(tools),
    querySource: 'sdk',
    maxTurns: 4,
    fallbackModel: undefined,
    deps: createDeps(firstContent),
  })) {
    if (message.type === 'assistant' || message.type === 'user') {
      emitted.push(message)
    }
  }

  return emitted
}

function textOf(message: AssistantMessage): string {
  return message.message.content
    .filter(
      (block): block is { type: 'text'; text: string } =>
        block.type === 'text',
    )
    .map(block => block.text)
    .join('')
}

function assistantMessages(emitted: Message[]): AssistantMessage[] {
  return emitted.filter(
    (message): message is AssistantMessage => message.type === 'assistant',
  )
}

function allAssistantText(emitted: Message[]): string {
  return assistantMessages(emitted).map(textOf).join('\n')
}

describe('query loop static progress regression', () => {
  test('does not synthesize hardcoded assistant progress when the model emits tool_use only', async () => {
    const emitted = await runQueryWithFirstAssistantContent([
      {
        type: 'tool_use',
        id: 'call-locate-1',
        name: 'locate',
        input: { query: '동아대학교 승학캠퍼스' },
      },
    ])
    const assistants = assistantMessages(emitted)

    expect(assistants[0]?.isVirtual).toBeUndefined()
    expect(
      assistants[0]?.message.content.some(block => block.type === 'tool_use'),
    ).toBe(true)
    for (const text of STATIC_QUERY_LOOP_PROGRESS_TEXTS) {
      expect(allAssistantText(emitted)).not.toContain(text)
    }

    const toolResultIndex = emitted.findIndex(
      message =>
        message.type === 'user' &&
        Array.isArray(message.message.content) &&
        message.message.content.some(block => block.type === 'tool_result'),
    )
    expect(toolResultIndex).toBeGreaterThanOrEqual(0)

    const finalAssistant = emitted
      .slice(toolResultIndex + 1)
      .find(
        (message): message is AssistantMessage => message.type === 'assistant',
      )
    expect(finalAssistant?.isVirtual).toBeUndefined()
    expect(textOf(finalAssistant!)).toContain('확인한 주소를 정리했습니다.')
  })

  test('preserves model-authored intermediate text without replacing it with static progress', async () => {
    const dynamicPrelude =
      '동아대학교 승학캠퍼스의 위치를 확인하기 위해 주소 검색을 먼저 진행하겠습니다.'
    const emitted = await runQueryWithFirstAssistantContent([
      {
        type: 'text',
        text: dynamicPrelude,
      },
      {
        type: 'tool_use',
        id: 'call-locate-1',
        name: 'locate',
        input: { query: '동아대학교 승학캠퍼스' },
      },
    ])

    const firstAssistant = assistantMessages(emitted)[0]

    expect(firstAssistant?.isVirtual).toBeUndefined()
    expect(textOf(firstAssistant!)).toContain(dynamicPrelude)
    for (const text of STATIC_QUERY_LOOP_PROGRESS_TEXTS) {
      expect(allAssistantText(emitted)).not.toContain(text)
    }
  })
})
