import {
  createActivityDescriptionResolver,
  createProgressTracker,
  updateAgentProgress as updateAsyncAgentProgress,
} from '../../tasks/LocalAgentTask/LocalAgentTask.js'
import type { ToolUseContext } from '../../Tool.js'
import type { Message as MessageType } from '../../types/message.js'
import type { ForegroundTaskRuntime } from './foregroundTask.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import { runAgent } from './runAgent.js'
import { maybeBackgroundAgent } from './foregroundBackground.js'
import {
  emitMessageProgress,
  showBackgroundHintIfNeeded,
  type AssistantProgressSource,
} from './foregroundProgress.js'
import type {
  AgentLifecycleMetadata,
  AgentToolProgressCallback,
  AsyncLaunchedOutput,
  WorktreeResult,
} from './schemas.js'

type SetAppState = Parameters<typeof updateAsyncAgentProgress>[2]
type RunAgentParams = Parameters<typeof runAgent>[0]
type SyncAgentContext = Parameters<typeof maybeBackgroundAgent>[0]['syncAgentContext']

export async function drainForegroundMessages({
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
  stopForegroundSummarization,
}: {
  readonly agentIterator: AsyncIterator<MessageType>
  readonly agentMessages: MessageType[]
  readonly agentStartTime: number
  readonly syncTracker: ReturnType<typeof createProgressTracker>
  readonly syncResolveActivity: ReturnType<typeof createActivityDescriptionResolver>
  readonly foreground: ForegroundTaskRuntime
  readonly toolUseContext: ToolUseContext
  readonly rootSetAppState: SetAppState
  readonly description: string
  readonly prompt: string
  readonly syncAgentId: string
  readonly selectedAgent: AgentDefinition
  readonly runAgentParams: RunAgentParams
  readonly metadata: AgentLifecycleMetadata
  readonly assistantMessage: AssistantProgressSource | undefined
  readonly onProgress: AgentToolProgressCallback | undefined
  readonly getWorktreeResult: () => Promise<WorktreeResult>
  readonly syncAgentContext: SyncAgentContext
  readonly stopForegroundSummarization: () => void
}): Promise<AsyncLaunchedOutput | undefined> {
  let backgroundHintShown = false
  while (true) {
    backgroundHintShown = showBackgroundHintIfNeeded(
      backgroundHintShown,
      agentStartTime,
      toolUseContext,
    )
    const raceResult = await nextForegroundRace(agentIterator, foreground)
    if (raceResult.type === 'background' && foreground.taskId) {
      const backgrounded = maybeBackgroundAgent({
        foregroundTaskId: foreground.taskId,
        agentIterator,
        agentMessages,
        toolUseContext,
        rootSetAppState,
        description,
        prompt,
        syncAgentId,
        selectedAgent,
        runAgentParams,
        metadata,
        getWorktreeResult,
        syncAgentContext,
        stopForegroundSummarization,
      })
      if (backgrounded) return backgrounded
      continue
    }
    if (raceResult.type !== 'message') continue
    if (raceResult.result.done) break
    const message = raceResult.result.value
    agentMessages.push(message)
    emitMessageProgress({
      message,
      syncTracker,
      syncResolveActivity,
      foregroundTaskId: foreground.taskId,
      toolUseContext,
      rootSetAppState,
      description,
      agentStartTime,
      syncAgentId,
      assistantMessage,
      onProgress,
    })
  }
  return undefined
}

async function nextForegroundRace(
  agentIterator: AsyncIterator<MessageType>,
  foreground: ForegroundTaskRuntime,
): Promise<
  | { readonly type: 'background' }
  | { readonly type: 'message'; readonly result: IteratorResult<MessageType, void> }
> {
  const nextMessagePromise = agentIterator.next()
  if (!foreground.backgroundPromise) {
    return { type: 'message', result: await nextMessagePromise }
  }
  return Promise.race([
    nextMessagePromise.then(result => ({ type: 'message' as const, result })),
    foreground.backgroundPromise,
  ])
}
