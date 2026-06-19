import { feature } from 'bun:bundle'
import { isCoordinatorMode } from '../../coordinator/coordinatorMode.js'
import { type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS, logEvent } from '../../services/analytics/index.js'
import type { AppState } from '../../state/AppState.js'
import type { ToolUseContext, Tools } from '../../Tool.js'
import { getAgentModel } from '../../utils/model/agent.js'
import { createAgentId } from '../../utils/uuid.js'
import { buildCoordinatorWorkerPermissionContext } from './orchestrationSupport.js'
import { isBuiltInAgent } from './loadAgentsDir.js'
import { isForkSubagentEnabled } from './forkSubagent.js'
import { runAgent } from './runAgent.js'
import {
  assertAgentLaunchAllowed,
  launchTeammateIfRequested,
  resolveSelectedAgentRoute,
  resolveTeamName,
} from './launchRouting.js'
import { launchRemoteAgentIfRequested } from './remoteRouting.js'
import {
  buildAgentPromptSetup,
  buildRunAgentParams,
} from './promptSetup.js'
import {
  appendForkWorktreeNotice,
  buildWorktreeCleanup,
  createWorktreeState,
} from './worktreeLifecycle.js'
import {
  isBackgroundTasksDisabled,
  isCoordinatorEnvMode,
  isProactiveAgentActive,
} from './runtimeConfig.js'
import {
  launchAsyncAgent,
  registerAgentName,
} from './asyncLifecycle.js'
import { launchSyncAgent } from './foregroundLifecycle.js'
import type {
  AgentLifecycleMetadata,
  AgentToolCallResult,
  AgentToolInput,
  AgentToolProgressCallback,
} from './schemas.js'

type SetAppState = (f: (prev: AppState) => AppState) => void
type RunAgentParams = Parameters<typeof runAgent>[0]
type AssistantProgressSource = {
  readonly requestId?: string
  readonly message?: { readonly id?: string }
}

export async function callAgentTool(
  input: AgentToolInput,
  toolUseContext: ToolUseContext,
  canUseTool: RunAgentParams['canUseTool'],
  assistantMessage: AssistantProgressSource | undefined,
  onProgress?: AgentToolProgressCallback,
): Promise<AgentToolCallResult> {
  const startTime = Date.now()
  const model = isCoordinatorMode() ? undefined : input.model
  const appState = toolUseContext.getAppState()
  const rootSetAppState =
    toolUseContext.setAppStateForTasks ?? toolUseContext.setAppState
  const teamName = resolveTeamName(input, appState)
  assertAgentLaunchAllowed({ input, teamName })

  const teammateResult = await launchTeammateIfRequested({
    input,
    teamName,
    model,
    toolUseContext,
    assistantMessage,
  })
  if (teammateResult) return teammateResult

  const { selectedAgent, isForkPath } = await resolveSelectedAgentRoute({
    input,
    toolUseContext,
    appState,
  })
  assertAgentLaunchAllowed({ input, selectedAgent, teamName })
  const permissionMode = appState.toolPermissionContext.mode
  const resolvedAgentModel = getAgentModel(
    selectedAgent.model,
    toolUseContext.options.mainLoopModel,
    isForkPath ? undefined : model,
    permissionMode,
  )
  const shouldRunAsync = shouldRunAgentAsync({
    input,
    selectedAgent,
    appState,
  })
  const metadata: AgentLifecycleMetadata = {
    prompt: input.prompt,
    resolvedAgentModel,
    isBuiltInAgent: isBuiltInAgent(selectedAgent),
    startTime,
    agentType: selectedAgent.agentType,
    isAsync: shouldRunAsync,
  }
  logSelectedAgent(selectedAgent, resolvedAgentModel, metadata, isForkPath)

  const effectiveIsolation = input.isolation ?? selectedAgent.isolation
  const remoteResult = await launchRemoteAgentIfRequested({
    effectiveIsolation,
    description: input.description,
    prompt: input.prompt,
    selectedAgent,
    toolUseContext,
  })
  if (remoteResult) return remoteResult

  const earlyAgentId = createAgentId()
  const promptSetup = await buildAgentPromptSetup({
    prompt: input.prompt,
    selectedAgent,
    toolUseContext,
    assistantMessage,
    resolvedAgentModel,
    isForkPath,
    hasWorktree: effectiveIsolation === 'worktree',
    cwd: input.cwd,
  })
  const worktreeState = await createWorktreeState({
    isolation: effectiveIsolation,
    earlyAgentId,
  })
  appendForkWorktreeNotice({
    isForkPath,
    worktreePath: worktreeState.current?.worktreePath,
    promptMessages: promptSetup.promptMessages,
  })

  const workerPermissionContext = buildCoordinatorWorkerPermissionContext(
    appState.toolPermissionContext,
    selectedAgent.permissionMode ?? 'acceptEdits',
  )
  const workerTools = await assembleWorkerTools(
    workerPermissionContext,
    appState.mcp.tools,
  )
  const runAgentParams = buildRunAgentParams({
    selectedAgent,
    promptSetup,
    toolUseContext,
    canUseTool,
    shouldRunAsync,
    isForkPath,
    model,
    workerTools,
    worktreePath: worktreeState.current?.worktreePath,
    description: input.description,
  })
  const cwdOverridePath = input.cwd ?? worktreeState.current?.worktreePath
  const getWorktreeResult = buildWorktreeCleanup({
    state: worktreeState,
    earlyAgentId,
    selectedAgent,
    description: input.description,
  })

  if (shouldRunAsync) {
    const data = launchAsyncAgent({
      asyncAgentId: earlyAgentId,
      description: input.description,
      prompt: input.prompt,
      selectedAgent,
      rootSetAppState,
      toolUseContext,
      runAgentParams,
      metadata,
      assistantMessage,
      cwdOverridePath,
      isCoordinator: isCoordinatorEnvMode(),
      getWorktreeResult,
    })
    registerAgentName({ name: input.name, agentId: earlyAgentId, rootSetAppState })
    return { data }
  }

  return launchSyncAgent({
    syncAgentId: earlyAgentId,
    selectedAgent,
    prompt: input.prompt,
    promptMessages: promptSetup.promptMessages,
    description: input.description,
    runAgentParams,
    toolUseContext,
    rootSetAppState,
    metadata,
    assistantMessage,
    cwdOverridePath,
    onProgress,
    getWorktreeResult,
  })
}

async function assembleWorkerTools(
  workerPermissionContext: AppState['toolPermissionContext'],
  mcpTools: AppState['mcp']['tools'],
): Promise<Tools> {
  const { assembleToolPool } = await import('../../tools.js')
  return assembleToolPool(workerPermissionContext, mcpTools)
}

function shouldRunAgentAsync({
  input,
  selectedAgent,
  appState,
}: {
  readonly input: AgentToolInput
  readonly selectedAgent: { readonly background?: boolean }
  readonly appState: Pick<AppState, 'kairosEnabled'>
}): boolean {
  const assistantForceAsync = feature('KAIROS') ? appState.kairosEnabled : false
  return (
    (input.run_in_background === true ||
      selectedAgent.background === true ||
      isCoordinatorEnvMode() ||
      isForkSubagentEnabled() ||
      assistantForceAsync ||
      isProactiveAgentActive()) &&
    !isBackgroundTasksDisabled
  )
}

function logSelectedAgent(
  selectedAgent: { readonly agentType: string; readonly source?: string; readonly color?: string },
  resolvedAgentModel: string,
  metadata: Pick<AgentLifecycleMetadata, 'isAsync' | 'isBuiltInAgent'>,
  isForkPath: boolean,
): void {
  logEvent('tengu_agent_tool_selected', {
    agent_type: selectedAgent.agentType as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
    model: resolvedAgentModel as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
    source: selectedAgent.source as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
    color: selectedAgent.color as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
    is_built_in_agent: metadata.isBuiltInAgent,
    is_resume: false,
    is_async: metadata.isAsync,
    is_fork: isForkPath,
  })
}
