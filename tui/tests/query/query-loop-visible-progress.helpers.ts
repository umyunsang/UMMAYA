import { z } from 'zod/v4'
import { query } from '../../src/query.js'
import type { Tools } from '../../src/Tool.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import type { AssistantMessage, Message } from '../../src/types/message.js'
import { asSystemPrompt } from '../../src/utils/systemPromptType.js'

export function createNamedTool(name: string): Tools[number] {
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

function createLocateTool(): Tools[number] {
  const inputSchema = z.object({ query: z.string() })
  return {
    ...createNamedTool('locate'),
    inputSchema,
    async description() {
      return 'Locate a public-service place or address.'
    },
    async call(args) {
      return { data: { ok: true, query: args.query, address: '부산 사하구 낙동대로550번길 37' } }
    },
  }
}

function createToolUseContext(tools: Tools) {
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
    readFileState: {},
    getAppState: () => ({
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
    }),
    setAppState: () => {},
    setInProgressToolUseIDs: () => {},
    setResponseLength: () => {},
    updateFileHistoryState: () => {},
    updateAttributionState: () => {},
    messages: [],
  }
}

function createDeps(firstContent: readonly Record<string, unknown>[]) {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      yield createAssistantMessage({
        content:
          callCount === 1
            ? firstContent
            : [{ type: 'text', text: '확인한 주소를 정리했습니다.' }],
      })
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => `uuid-${callCount}`,
  }
}

function createDeferred() {
  let resolveDeferred = () => {}
  const promise = new Promise<void>(resolve => {
    resolveDeferred = resolve
  })
  return { promise, resolve: resolveDeferred }
}

function createStalledDeps(firstContent: readonly Record<string, unknown>[], release: Promise<void>) {
  let callCount = 0
  return {
    async *callModel() {
      callCount += 1
      yield createAssistantMessage({
        content:
          callCount === 1
            ? firstContent
            : [{ type: 'text', text: '확인한 주소를 정리했습니다.' }],
      })
      await release
    },
    microcompact: async (messages: readonly Message[]) => ({ messages }),
    autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
    uuid: () => 'uuid-stalled',
  }
}

export async function runQueryWithFirstAssistantContent(firstContent: readonly Record<string, unknown>[]): Promise<Message[]> {
  return runQueryForPromptWithFirstAssistantContent({
    prompt: '동아대학교 승학캠퍼스 위치를 확인해줘',
    firstContent,
    tools: [createLocateTool()],
  })
}

export async function runQueryForPromptWithFirstAssistantContent(params: {
  readonly prompt: string
  readonly firstContent: readonly Record<string, unknown>[]
  readonly tools: Tools
}): Promise<Message[]> {
  const emitted: Message[] = []
  for await (const message of query(queryParams(params.prompt, params.tools, createDeps(params.firstContent)))) {
    if (message.type === 'assistant' || message.type === 'user') emitted.push(message)
  }
  return emitted
}

export async function runStalledMcpStreamUntilFirstAssistant(params: {
  readonly prompt: string
  readonly firstContent: readonly Record<string, unknown>[]
  readonly tools: Tools
  readonly timeoutMs: number
  readonly messages?: readonly Message[]
}): Promise<AssistantMessage | undefined> {
  const release = createDeferred()
  const stream = query({
    ...queryParams(params.prompt, params.tools, createStalledDeps(params.firstContent, release.promise)),
    messages: params.messages ?? [createUserMessage({ content: params.prompt })],
  })
  try {
    return await nextAssistantWithin(stream, params.timeoutMs)
  } finally {
    release.resolve()
    await stream.return({ reason: 'completed' })
  }
}

export function queryParams(prompt: string, tools: Tools, deps: unknown) {
  return {
    messages: [createUserMessage({ content: prompt })],
    systemPrompt: asSystemPrompt(['test system prompt']),
    userContext: {},
    systemContext: {},
    canUseTool: async (_tool: unknown, input: Record<string, unknown>) => ({ behavior: 'allow', updatedInput: input }),
    toolUseContext: createToolUseContext(tools),
    querySource: 'sdk',
    maxTurns: 4,
    fallbackModel: undefined,
    deps,
  }
}

async function nextAssistantWithin(stream: ReturnType<typeof query>, timeoutMs: number): Promise<AssistantMessage | undefined> {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    const remainingMs = Math.max(1, timeoutMs - (Date.now() - startedAt))
    const timeoutResult = { type: 'timeout' }
    const result = await Promise.race([
      stream.next(),
      new Promise<typeof timeoutResult>(resolve => setTimeout(() => resolve(timeoutResult), remainingMs)),
    ])
    if (result === timeoutResult) return undefined
    if (result.done) return undefined
    if (result.value.type === 'assistant') return result.value
  }
  return undefined
}

export function textOf(message: AssistantMessage): string {
  return message.message.content
    .filter(block => block.type === 'text')
    .map(block => block.text)
    .join('')
}

export function assistantMessages(emitted: readonly Message[]): AssistantMessage[] {
  return emitted.filter((message): message is AssistantMessage => message.type === 'assistant')
}

export function allAssistantText(emitted: readonly Message[]): string {
  return assistantMessages(emitted).map(textOf).join('\n')
}
