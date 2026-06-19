import type { ToolUseBlock } from '@anthropic-ai/sdk/resources/index.mjs'
import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import type { CanUseToolFn } from '../../src/hooks/useCanUseTool.js'
import type { ToolUseContext, Tools } from '../../src/Tool.js'
import { buildTool, getEmptyToolPermissionContext } from '../../src/Tool.js'
import { runToolUse, type MessageUpdateLazy } from '../../src/services/tools/toolExecution.js'
import { getDefaultAppState, type AppState } from '../../src/state/AppStateStore.js'
import { assembleToolPool, getTools } from '../../src/tools.js'
import { ToolSearchTool } from '../../src/tools/ToolSearchTool/ToolSearchTool.js'
import { isDeferredTool } from '../../src/tools/ToolSearchTool/prompt.js'
import { selectRecoveredSupportToolNamesForQuery } from '../../src/tools/ToolSearchTool/supportIntentHints.js'
import {
  WORKSPACE_GLOB_TOOL_NAME,
  WORKSPACE_GREP_TOOL_NAME,
  WORKSPACE_READ_TOOL_NAME,
} from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import type { Message } from '../../src/types/message.js'
import {
  createFileStateCacheWithSizeLimit,
  READ_FILE_STATE_CACHE_SIZE,
} from '../../src/utils/fileStateCache.js'
import { createAssistantMessage, createUserMessage } from '../../src/utils/messages.js'

const WEB_FETCH_DISCOVERY_QUERY = 'select:WebFetch'
const GOV24_LOOKUP_TOOL_NAME = 'mock_lookup_module_gov24_certificate'
const GOV24_READ_ONLY_PROMPT =
  '정부24 주민등록등본 발급 가능 여부와 준비물을 확인해줘.'
const FILE_EVIDENCE_TOOL_NAMES = [
  WORKSPACE_GLOB_TOOL_NAME,
  WORKSPACE_GREP_TOOL_NAME,
  WORKSPACE_READ_TOOL_NAME,
] as const

function textFromBlock(block: unknown): string {
  if (typeof block === 'string') return block
  if (typeof block !== 'object' || block === null) return ''
  if ('text' in block && typeof block.text === 'string') return block.text
  if ('content' in block) {
    const content = block.content
    if (typeof content === 'string') return content
    return JSON.stringify(content)
  }
  return ''
}

function textFromMessageUpdate(update: MessageUpdateLazy): string {
  const content = update.message.message.content
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content.map(textFromBlock).join('\n')
}

function discoveredToolMessages(toolName: string): Message[] {
  const toolReferenceResult = ToolSearchTool.mapToolResultToToolResultBlockParam(
    {
      matches: [toolName],
      query: `select:${toolName}`,
      total_deferred_tools: 1,
    },
    'toolu-task17-search',
  )

  return [
    createUserMessage({
      content: [toolReferenceResult],
      uuid: '00000000-0000-4000-8000-000000000017',
    }),
  ]
}

function makeToolUseContext(tools: Tools, messages: Message[]): ToolUseContext {
  let appState: AppState = getDefaultAppState()
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
      agentDefinitions: { activeAgents: [], allAgents: [] },
    },
    abortController: new AbortController(),
    readFileState: createFileStateCacheWithSizeLimit(READ_FILE_STATE_CACHE_SIZE),
    getAppState: () => appState,
    setAppState: update => {
      appState = update(appState)
    },
    setInProgressToolUseIDs: () => {},
    setResponseLength: () => {},
    updateFileHistoryState: () => {},
    updateAttributionState: () => {},
    messages,
  } satisfies ToolUseContext
}

const denyRecoveredSupportTool: CanUseToolFn = async () => ({
  behavior: 'deny',
  message: 'Task 17 recovered support tool permission boundary rendered.',
  decisionReason: {
    type: 'other',
    reason: 'Task 17 test denial',
  },
})
const allowToolUse: CanUseToolFn = async (_tool, input) => ({
  behavior: 'allow',
  updatedInput: input,
})

function gov24FindTool(capture: (input: Record<string, unknown>) => void) {
  return buildTool({
    name: 'find',
    inputSchema: z.object({
      tool_id: z.string(),
      params: z.record(z.string(), z.unknown()),
    }),
    maxResultSizeChars: 1000,
    description: async () => 'find',
    prompt: async () => 'find',
    isReadOnly: () => true,
    isConcurrencySafe: () => true,
    call: async input => {
      capture(input)
      return { data: { ok: true, result: input } }
    },
    mapToolResultToToolResultBlockParam: (data, toolUseID) => ({
      type: 'tool_result',
      tool_use_id: toolUseID,
      content: JSON.stringify(data),
    }),
  })
}

async function runDiscoveredWebFetch(tools: Tools): Promise<string> {
  const toolUse = {
    type: 'tool_use',
    id: 'toolu-task17-webfetch',
    name: 'WebFetch',
    input: {
      url: 'https://example.com/task-17-source',
      prompt: 'Return only source verification status.',
    },
  } satisfies ToolUseBlock
  const assistantMessage = createAssistantMessage({ content: [toolUse] })
  const messages = discoveredToolMessages('WebFetch')
  const updates: MessageUpdateLazy[] = []

  for await (const update of runToolUse(
    toolUse,
    assistantMessage,
    denyRecoveredSupportTool,
    makeToolUseContext(tools, messages),
  )) {
    updates.push(update)
  }

  return updates.map(textFromMessageUpdate).join('\n')
}

describe('Task 17 recovered support tool dispatch', () => {
  test('repairs Gov24 root find params before legacy toolExecution dispatch', async () => {
    let capturedInput: Record<string, unknown> | undefined
    const toolUse = {
      type: 'tool_use',
      id: 'toolu-gov24-find',
      name: 'find',
      input: {
        tool_id: GOV24_LOOKUP_TOOL_NAME,
        params: {},
      },
    } satisfies ToolUseBlock
    const assistantMessage = createAssistantMessage({ content: [toolUse] })
    const messages = [createUserMessage({ content: GOV24_READ_ONLY_PROMPT })]
    const updates: MessageUpdateLazy[] = []

    for await (const update of runToolUse(
      toolUse,
      assistantMessage,
      allowToolUse,
      makeToolUseContext([
        gov24FindTool(input => {
          capturedInput = input
        }),
      ], messages),
    )) {
      updates.push(update)
    }

    expect(updates.map(textFromMessageUpdate).join('\n')).not.toContain(
      'Missing or invalid fields',
    )
    expect(capturedInput).toEqual({
      tool_id: GOV24_LOOKUP_TOOL_NAME,
      params: {
        certificate_type: 'resident_registration',
        purpose: '주민등록등본 발급 가능 여부와 준비물 확인',
      },
    })
  })

  test('routes_ordinary_korean_repository_file_lookup_to_workspace_read_search_not_web', () => {
    const selectedSupportTools = selectRecoveredSupportToolNamesForQuery(
      '이 저장소에서 웹 조사 도구 관련 파일을 찾아줘. 파일을 찾은 뒤 한 파일의 첫 줄도 읽어줘.',
    )

    expect(selectedSupportTools).toEqual(
      expect.arrayContaining([
        WORKSPACE_GREP_TOOL_NAME,
        WORKSPACE_READ_TOOL_NAME,
      ]),
    )
    expect(selectedSupportTools).not.toContain('WebSearch')
    expect(selectedSupportTools).not.toContain('WebFetch')
  })

  test('keeps_raw_support_tools_out_of_default_model_facing_catalog', () => {
    const modelFacingNames = getTools(getEmptyToolPermissionContext()).map(
      tool => tool.name,
    )

    expect(modelFacingNames).toContain('ToolSearch')
    expect(modelFacingNames).toContain('workspace_read')
    expect(modelFacingNames).not.toContain('WebFetch')
  })

  test('keeps_file_read_search_schemas_loaded_for_first_turn_evidence', () => {
    const modelFacingTools = getTools(getEmptyToolPermissionContext())

    for (const toolName of FILE_EVIDENCE_TOOL_NAMES) {
      const tool = modelFacingTools.find(candidate => candidate.name === toolName)
      expect(tool?.name).toBe(toolName)
      expect(tool ? isDeferredTool(tool) : true).toBe(false)
    }
  })

  test('dispatches_toolsearch_discovered_support_tools_instead_of_adapter_not_found', async () => {
    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
    const renderedBoundary = await runDiscoveredWebFetch(tools)

    expect(renderedBoundary).toContain(
      'Task 17 recovered support tool permission boundary rendered.',
    )
    expect(renderedBoundary).not.toContain('No such tool available: WebFetch')
    expect(WEB_FETCH_DISCOVERY_QUERY).not.toContain('workspace_')
  })
})
