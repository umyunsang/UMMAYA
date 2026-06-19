import type { ToolUseContext } from '../../src/Tool.js'
import { WebFetchTool } from '../../src/tools/WebFetchTool/WebFetchTool.js'
import { getDefaultAppState } from '../../src/state/AppStateStore.js'
import { createFileStateCacheWithSizeLimit } from '../../src/utils/fileStateCache.js'

type TextBlock = {
  readonly text: string
}

function blockText(block: TextBlock): string {
  return block.text
}

export function toolResultText(
  result: ReturnType<typeof WebFetchTool.mapToolResultToToolResultBlockParam>,
): string {
  if (typeof result.content === 'string') {
    return result.content
  }
  if (Array.isArray(result.content)) {
    return result.content
      .map(item => {
        if (
          typeof item === 'object' &&
          item !== null &&
          'text' in item &&
          typeof item.text === 'string'
        ) {
          return blockText(item)
        }
        return JSON.stringify(item)
      })
      .join('\n')
  }
  return JSON.stringify(result.content)
}

export function sourceVerification(
  toolId: string,
  blockedOrUsed: 'blocked' | 'needs_input' = 'needs_input',
) {
  return {
    mutationAllowed: false,
    userApprovalRequired: true,
    secretEgress: false,
    evidence: [
      {
        toolId,
        sourceUrl: 'https://policy.example/source',
        title: 'Public AX source',
        observedAt: '2026-06-12T00:00:00.000Z',
        citationHandle: 'src-task14-policy',
        blockedOrUsed,
        trust: 'untrusted_source',
        promptInjection: 'not_detected',
        redacted: false,
      },
    ],
  }
}

export function completedAgentResult() {
  return {
    status: 'completed',
    agentId: 'agent-source-14',
    agentType: 'general-purpose',
    evidenceJoinKey: 'toolu-source:agent-source-14',
    parentToolUseId: 'toolu-source',
    resumeToken: 'resume:agent-source-14',
    permissionFlow: 'coordinator_parent_round_trip',
    content: [
      { type: 'text', text: 'Research result needs provenance approval.' },
    ],
    totalToolUseCount: 2,
    totalDurationMs: 15,
    totalTokens: 42,
    usage: {
      input_tokens: 10,
      output_tokens: 12,
      cache_creation_input_tokens: null,
      cache_read_input_tokens: null,
      server_tool_use: { web_search_requests: 1, web_fetch_requests: 1 },
      service_tier: 'standard',
      cache_creation: null,
    },
    sourceVerification: sourceVerification('Agent'),
  }
}

export function makeWebSearchToolUseContext(): ToolUseContext {
  let appState = getDefaultAppState()
  return {
    options: {
      commands: [],
      debug: false,
      mainLoopModel: 'test-model',
      tools: [],
      verbose: false,
      thinkingConfig: { enabled: false },
      mcpClients: [],
      mcpResources: {},
      isNonInteractiveSession: true,
      agentDefinitions: {
        activeAgents: [],
        allAgents: [],
      },
    },
    abortController: new AbortController(),
    readFileState: createFileStateCacheWithSizeLimit(1),
    getAppState() {
      return appState
    },
    setAppState(updater) {
      appState = updater(appState)
    },
    setInProgressToolUseIDs() {},
    setResponseLength() {},
    updateFileHistoryState() {},
    updateAttributionState() {},
    messages: [],
  }
}

export function makeWebSearchParentMessage() {
  return {
    type: 'assistant',
    message: {
      id: 'msg-parent',
      role: 'assistant',
      content: [],
      model: 'test-model',
      stop_reason: null,
      stop_sequence: null,
      usage: {
        input_tokens: 0,
        output_tokens: 0,
        cache_creation_input_tokens: null,
        cache_read_input_tokens: null,
        server_tool_use: null,
        service_tier: null,
        cache_creation: null,
      },
    },
  }
}
