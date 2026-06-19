import { clearInvokedSkillsForAgent, getSdkAgentProgressSummariesEnabled } from '../../bootstrap/state.js'
import { startAgentSummarization } from '../../services/AgentSummary/agentSummary.js'
import { clearDumpState } from '../../services/api/dumpPrompts.js'
import type { AppState } from '../../state/AppState.js'
import {
  createActivityDescriptionResolver,
  createProgressTracker,
  unregisterAgentForeground,
} from '../../tasks/LocalAgentTask/LocalAgentTask.js'
import type { ToolUseContext } from '../../Tool.js'
import { runWithAgentContext } from '../../utils/agentContext.js'
import { runWithCwdOverride } from '../../utils/cwd.js'
import { logForDebugging } from '../../utils/debug.js'
import { AbortError, errorMessage, toError } from '../../utils/errors.js'
import type { CacheSafeParams } from '../../utils/forkedAgent.js'
import { getParentSessionId } from '../../utils/teammate.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import { isBuiltInAgent } from './loadAgentsDir.js'
import { runAgent } from './runAgent.js'
import { drainForegroundMessages } from './foregroundDrain.js'
import { finalizeSyncAgent, logTermination } from './foregroundFinalize.js'
import { emitInitialProgress } from './foregroundProgress.js'
import {
  enqueueCompletionSdkEvent,
  setupForegroundTask,
} from './foregroundTask.js'
import type {
  AgentLifecycleMetadata,
  AgentToolCallResult,
  AgentToolProgressCallback,
  WorktreeResult,
} from './schemas.js'

type SetAppState = (f: (prev: AppState) => AppState) => void
type RunAgentParams = Parameters<typeof runAgent>[0]
type AssistantProgressSource = {
  readonly requestId?: string
  readonly message?: { readonly id?: string }
}

export async function launchSyncAgent({
  syncAgentId,
  selectedAgent,
  prompt,
  promptMessages,
  description,
  runAgentParams,
  toolUseContext,
  rootSetAppState,
  metadata,
  assistantMessage,
  cwdOverridePath,
  onProgress,
  getWorktreeResult,
}: {
  readonly syncAgentId: string
  readonly selectedAgent: AgentDefinition
  readonly prompt: string
  readonly promptMessages: RunAgentParams['promptMessages']
  readonly description: string
  readonly runAgentParams: RunAgentParams
  readonly toolUseContext: ToolUseContext
  readonly rootSetAppState: SetAppState
  readonly metadata: AgentLifecycleMetadata
  readonly assistantMessage?: AssistantProgressSource
  readonly cwdOverridePath?: string
  readonly onProgress?: AgentToolProgressCallback
  readonly getWorktreeResult: () => Promise<WorktreeResult>
}): Promise<AgentToolCallResult> {
  const syncAgentContext = {
    agentId: syncAgentId,
    parentSessionId: getParentSessionId(),
    agentType: 'subagent' as const,
    subagentName: selectedAgent.agentType,
    isBuiltIn: isBuiltInAgent(selectedAgent),
    invokingRequestId: assistantMessage?.requestId,
    invocationKind: 'spawn' as const,
    invocationEmitted: false,
  }
  return runWithAgentContext(syncAgentContext, () =>
    withCwd(cwdOverridePath, () =>
      runForegroundLoop({
        syncAgentId,
        selectedAgent,
        prompt,
        promptMessages,
        description,
        runAgentParams,
        toolUseContext,
        rootSetAppState,
        metadata,
        assistantMessage,
        onProgress,
        getWorktreeResult,
        syncAgentContext,
      }),
    ),
  )
}

async function runForegroundLoop({
  syncAgentId,
  selectedAgent,
  prompt,
  promptMessages,
  description,
  runAgentParams,
  toolUseContext,
  rootSetAppState,
  metadata,
  assistantMessage,
  onProgress,
  getWorktreeResult,
  syncAgentContext,
}: {
  readonly syncAgentId: string
  readonly selectedAgent: AgentDefinition
  readonly prompt: string
  readonly promptMessages: RunAgentParams['promptMessages']
  readonly description: string
  readonly runAgentParams: RunAgentParams
  readonly toolUseContext: ToolUseContext
  readonly rootSetAppState: SetAppState
  readonly metadata: AgentLifecycleMetadata
  readonly assistantMessage?: { readonly message?: { readonly id?: string } }
  readonly onProgress?: AgentToolProgressCallback
  readonly getWorktreeResult: () => Promise<WorktreeResult>
  readonly syncAgentContext: Parameters<typeof runWithAgentContext>[0]
}): Promise<AgentToolCallResult> {
  const agentMessages: RunAgentParams['promptMessages'] = []
  const agentStartTime = Date.now()
  const syncTracker = createProgressTracker()
  const syncResolveActivity = createActivityDescriptionResolver(toolUseContext.options.tools)
  const foreground = setupForegroundTask({
    syncAgentId,
    selectedAgent,
    description,
    prompt,
    rootSetAppState,
    toolUseContext,
  })
  let wasBackgrounded = false
  let wasAborted = false
  let syncAgentError: Error | undefined
  let worktreeResult: WorktreeResult = {}
  let stopForegroundSummarization: (() => void) | undefined
  emitInitialProgress(promptMessages, prompt, syncAgentId, assistantMessage, onProgress)
  const agentIterator = runAgent({
    ...runAgentParams,
    override: { ...runAgentParams.override, agentId: syncAgentId },
    onCacheSafeParams:
      foreground.taskId && getSdkAgentProgressSummariesEnabled()
        ? (params: CacheSafeParams) => {
            const { stop } = startAgentSummarization(
              foreground.taskId,
              syncAgentId,
              params,
              rootSetAppState,
            )
            stopForegroundSummarization = stop
          }
        : undefined,
  })[Symbol.asyncIterator]()

  try {
    const backgrounded = await drainForegroundMessages({
      agentIterator,
      agentMessages,
      agentStartTime,
      syncTracker,
      syncResolveActivity,
      foreground,
      toolUseContext,
      rootSetAppState,
      description,
      prompt,
      syncAgentId,
      selectedAgent,
      runAgentParams,
      metadata,
      assistantMessage,
      onProgress,
      getWorktreeResult,
      syncAgentContext,
      stopForegroundSummarization: () => stopForegroundSummarization?.(),
    })
    if (backgrounded) {
      wasBackgrounded = true
      return { data: backgrounded }
    }
  } catch (error) {
    const syncError = error instanceof Error ? error : toError(error)
    if (syncError instanceof AbortError) {
      wasAborted = true
      logTermination(metadata, false, 'user_cancel_sync')
      throw syncError
    }
    logForDebugging(`Sync agent error: ${errorMessage(syncError)}`, { level: 'error' })
    syncAgentError = syncError
  } finally {
    toolUseContext.setToolJSX?.(null)
    stopForegroundSummarization?.()
    if (foreground.taskId) {
      unregisterAgentForeground(foreground.taskId, rootSetAppState)
      if (!wasBackgrounded) {
        enqueueCompletionSdkEvent({
          foregroundTaskId: foreground.taskId,
          toolUseContext,
          syncTracker,
          syncAgentError,
          wasAborted,
          description,
          agentStartTime,
        })
      }
    }
    clearInvokedSkillsForAgent(syncAgentId)
    if (!wasBackgrounded) clearDumpState(syncAgentId)
    foreground.cancelAutoBackground?.()
    if (!wasBackgrounded) worktreeResult = await getWorktreeResult()
  }

  return finalizeSyncAgent({
    agentMessages,
    syncAgentError,
    metadata,
    selectedAgent,
    toolUseContext,
    prompt,
    syncAgentId,
    worktreeResult,
  })
}

function withCwd<T>(cwdOverridePath: string | undefined, fn: () => T): T {
  return cwdOverridePath ? runWithCwdOverride(cwdOverridePath, fn) : fn()
}
