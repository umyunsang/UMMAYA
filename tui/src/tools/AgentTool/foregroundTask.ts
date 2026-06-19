import type { AppState } from '../../state/AppState.js'
import type { ToolUseContext } from '../../Tool.js'
import {
  createProgressTracker,
  getProgressUpdate,
  registerAgentForeground,
} from '../../tasks/LocalAgentTask/LocalAgentTask.js'
import { enqueueSdkEvent } from '../../utils/sdkEventQueue.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import {
  getAutoBackgroundMs,
  isBackgroundTasksDisabled,
} from './runtimeConfig.js'

type SetAppState = (f: (prev: AppState) => AppState) => void

export type ForegroundTaskRuntime = {
  readonly taskId?: string
  readonly backgroundPromise?: Promise<{ readonly type: 'background' }>
  readonly cancelAutoBackground?: () => void
}

export function setupForegroundTask({
  syncAgentId,
  selectedAgent,
  description,
  prompt,
  rootSetAppState,
  toolUseContext,
}: {
  readonly syncAgentId: string
  readonly selectedAgent: AgentDefinition
  readonly description: string
  readonly prompt: string
  readonly rootSetAppState: SetAppState
  readonly toolUseContext: ToolUseContext
}): ForegroundTaskRuntime {
  if (isBackgroundTasksDisabled) return {}
  const registration = registerAgentForeground({
    agentId: syncAgentId,
    description,
    prompt,
    selectedAgent,
    setAppState: rootSetAppState,
    toolUseId: toolUseContext.toolUseId,
    autoBackgroundMs: getAutoBackgroundMs() || undefined,
  })
  return {
    taskId: registration.taskId,
    backgroundPromise: registration.backgroundSignal.then(() => ({
      type: 'background',
    })),
    cancelAutoBackground: registration.cancelAutoBackground,
  }
}

export function enqueueCompletionSdkEvent({
  foregroundTaskId,
  toolUseContext,
  syncTracker,
  syncAgentError,
  wasAborted,
  description,
  agentStartTime,
}: {
  readonly foregroundTaskId: string
  readonly toolUseContext: ToolUseContext
  readonly syncTracker: ReturnType<typeof createProgressTracker>
  readonly syncAgentError?: Error
  readonly wasAborted: boolean
  readonly description: string
  readonly agentStartTime: number
}): void {
  const progress = getProgressUpdate(syncTracker)
  enqueueSdkEvent({
    type: 'system',
    subtype: 'task_notification',
    task_id: foregroundTaskId,
    tool_use_id: toolUseContext.toolUseId,
    status: syncAgentError ? 'failed' : wasAborted ? 'stopped' : 'completed',
    output_file: '',
    summary: description,
    usage: {
      total_tokens: progress.tokenCount,
      tool_uses: progress.toolUseCount,
      duration_ms: Date.now() - agentStartTime,
    },
  })
}
