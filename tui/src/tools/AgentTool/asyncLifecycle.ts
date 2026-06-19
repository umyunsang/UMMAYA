import type { AppState } from '../../state/AppState.js'
import type { ToolUseContext, Tools } from '../../Tool.js'
import { getSdkAgentProgressSummariesEnabled } from '../../bootstrap/state.js'
import {
  registerAsyncAgent,
} from '../../tasks/LocalAgentTask/LocalAgentTask.js'
import { asAgentId } from '../../types/ids.js'
import type { AssistantMessage } from '../../types/message.js'
import { runWithAgentContext } from '../../utils/agentContext.js'
import { runWithCwdOverride } from '../../utils/cwd.js'
import { getParentSessionId } from '../../utils/teammate.js'
import { getTaskOutputPath } from '../../utils/task/diskOutput.js'
import { toolMatchesName } from '../../Tool.js'
import { BASH_TOOL_NAME } from '../BashTool/toolName.js'
import { FILE_READ_TOOL_NAME } from '../FileReadTool/prompt.js'
import { isForkSubagentEnabled } from './forkSubagent.js'
import { buildAgentSupportMetadata } from './orchestrationSupport.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import { isBuiltInAgent } from './loadAgentsDir.js'
import { runAgent } from './runAgent.js'
import type {
  AgentLifecycleMetadata,
  AsyncLaunchedOutput,
  WorktreeResult,
} from './schemas.js'

type SetAppState = (f: (prev: AppState) => AppState) => void
type RunAgentParams = Parameters<typeof runAgent>[0]

export function canReadAgentOutputFile(tools: Tools): boolean {
  return tools.some(
    tool => toolMatchesName(tool, FILE_READ_TOOL_NAME) || toolMatchesName(tool, BASH_TOOL_NAME),
  )
}

export function registerAgentName({
  name,
  agentId,
  rootSetAppState,
}: {
  readonly name?: string
  readonly agentId: string
  readonly rootSetAppState: SetAppState
}): void {
  if (!name) return
  rootSetAppState(prev => {
    const next = new Map(prev.agentNameRegistry)
    next.set(name, asAgentId(agentId))
    return { ...prev, agentNameRegistry: next }
  })
}

export function launchAsyncAgent({
  asyncAgentId,
  description,
  prompt,
  selectedAgent,
  rootSetAppState,
  toolUseContext,
  runAgentParams,
  metadata,
  assistantMessage,
  cwdOverridePath,
  isCoordinator,
  getWorktreeResult,
}: {
  readonly asyncAgentId: string
  readonly description: string
  readonly prompt: string
  readonly selectedAgent: AgentDefinition
  readonly rootSetAppState: SetAppState
  readonly toolUseContext: ToolUseContext
  readonly runAgentParams: RunAgentParams
  readonly metadata: AgentLifecycleMetadata
  readonly assistantMessage?: AssistantMessage
  readonly cwdOverridePath?: string
  readonly isCoordinator: boolean
  readonly getWorktreeResult: () => Promise<WorktreeResult>
}): AsyncLaunchedOutput {
  const agentBackgroundTask = registerAsyncAgent({
    agentId: asyncAgentId,
    description,
    prompt,
    selectedAgent,
    setAppState: rootSetAppState,
    toolUseId: toolUseContext.toolUseId,
  })
  const abortController = agentBackgroundTask.abortController
  if (!abortController) {
    throw new Error(
      `Cannot launch agent ${agentBackgroundTask.agentId}: missing abort controller`,
    )
  }
  void runWithAgentContext(
    {
      agentId: asyncAgentId,
      parentSessionId: getParentSessionId(),
      agentType: 'subagent',
      subagentName: selectedAgent.agentType,
      isBuiltIn: isBuiltInAgent(selectedAgent),
      invokingRequestId: assistantMessage?.requestId,
      invocationKind: 'spawn',
      invocationEmitted: false,
    },
    async () =>
      withCwd(cwdOverridePath, () =>
        import('./asyncAgentLifecycle.js').then(
          ({ runAsyncAgentLifecycle }) =>
            runAsyncAgentLifecycle({
              taskId: agentBackgroundTask.agentId,
              abortController,
              makeStream: onCacheSafeParams =>
                runAgent({
                  ...runAgentParams,
                  override: {
                    ...runAgentParams.override,
                    agentId: asAgentId(agentBackgroundTask.agentId),
                    abortController,
                  },
                  onCacheSafeParams,
                }),
              metadata,
              description,
              toolUseContext,
              rootSetAppState,
              agentIdForCleanup: asyncAgentId,
              enableSummarization:
                isCoordinator ||
                isForkSubagentEnabled() ||
                getSdkAgentProgressSummariesEnabled(),
              getWorktreeResult,
            }),
        ),
      ),
  )
  return {
    isAsync: true,
    status: 'async_launched',
    agentId: agentBackgroundTask.agentId,
    description,
    prompt,
    outputFile: getTaskOutputPath(agentBackgroundTask.agentId),
    canReadOutputFile: canReadAgentOutputFile(toolUseContext.options.tools),
    ...buildAgentSupportMetadata({
      agentId: agentBackgroundTask.agentId,
      parentToolUseId: toolUseContext.toolUseId,
    }),
  }
}

function withCwd<T>(cwdOverridePath: string | undefined, fn: () => T): T {
  return cwdOverridePath ? runWithCwdOverride(cwdOverridePath, fn) : fn()
}
