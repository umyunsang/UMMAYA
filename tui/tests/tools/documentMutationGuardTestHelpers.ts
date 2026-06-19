import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { Tool, ToolUseContext } from '../../src/Tool.js'
import { getEmptyToolPermissionContext } from '../../src/Tool.js'
import { getDefaultAppState, type AppState } from '../../src/state/AppStateStore.js'
import type { AssistantMessage } from '../../src/types/message.js'
import { createFileStateCacheWithSizeLimit } from '../../src/utils/fileStateCache.js'

export const DOCUMENT_EXTENSIONS = [
  'hwp',
  'hwpx',
  'docx',
  'pdf',
  'xlsx',
  'pptx',
] as const

export function makeContext(): ToolUseContext {
  const initialState = getDefaultAppState()
  let appState: AppState = {
    ...initialState,
    toolPermissionContext: getEmptyToolPermissionContext(),
    mcp: { ...initialState.mcp, tools: [], clients: [] },
  }

  return {
    options: {
      commands: [],
      debug: false,
      mainLoopModel: 'test-model',
      tools: [],
      verbose: false,
      thinkingConfig: { type: 'disabled' },
      mcpClients: [],
      mcpResources: {},
      isNonInteractiveSession: false,
      agentDefinitions: { activeAgents: [], allAgents: [] },
    },
    abortController: new AbortController(),
    readFileState: createFileStateCacheWithSizeLimit(16),
    getAppState: () => appState,
    setAppState: updater => {
      appState = updater(appState)
    },
    setInProgressToolUseIDs: () => {},
    setResponseLength: () => {},
    updateFileHistoryState: () => {},
    updateAttributionState: () => {},
    messages: [],
  }
}

export async function withTempRoot<T>(
  callback: (root: string) => Promise<T>,
): Promise<T> {
  const root = await mkdtemp(join(tmpdir(), 'ummaya-document-policy-'))
  try {
    return await callback(root)
  } finally {
    await rm(root, { recursive: true, force: true })
  }
}

export function parentMessage(): AssistantMessage {
  return {
    uuid: 'assistant-document-mutation-guard-test',
    role: 'assistant',
    content: [{ type: 'text', text: 'document mutation guard test' }],
  }
}

export function fileState(content: string) {
  return {
    content,
    timestamp: Date.now(),
    offset: undefined,
    limit: undefined,
  }
}

export function notebookContent(source: string): string {
  return JSON.stringify(
    {
      cells: [
        {
          cell_type: 'code',
          id: 'cell-1',
          source,
          metadata: {},
          execution_count: null,
          outputs: [],
        },
      ],
      metadata: { language_info: { name: 'python' } },
      nbformat: 4,
      nbformat_minor: 5,
    },
    null,
    1,
  )
}

export async function workspaceTool(name: string): Promise<Tool> {
  const { getWorkspaceTools } = await import(
    '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
  )
  const tool = getWorkspaceTools().find(candidate => candidate.name === name)
  if (!tool) throw new Error(`Missing workspace tool: ${name}`)
  return tool
}
