import { clearInvokedSkillsForAgent, getSdkAgentProgressSummariesEnabled } from '../../bootstrap/state.js'
import { startAgentSummarization } from '../../services/AgentSummary/agentSummary.js'
import { clearDumpState } from '../../services/api/dumpPrompts.js'
import {
  completeAgentTask as completeAsyncAgent,
  createActivityDescriptionResolver,
  createProgressTracker,
  getProgressUpdate,
  type LocalAgentTaskState,
  updateAgentProgress as updateAsyncAgentProgress,
  updateProgressFromMessage,
} from '../../tasks/LocalAgentTask/LocalAgentTask.js'
import { asAgentId } from '../../types/ids.js'
import type { Message as MessageType } from '../../types/message.js'
import { runWithAgentContext } from '../../utils/agentContext.js'
import { errorMessage } from '../../utils/errors.js'
import type { CacheSafeParams } from '../../utils/forkedAgent.js'
import { logForDebugging } from '../../utils/debug.js'
import { sleep } from '../../utils/sleep.js'
import {
  emitTaskProgress,
  getLastToolUseName,
} from './agentToolProgress.js'
import type { AgentLifecycleMetadata, WorktreeResult } from './schemas.js'
import { runAgent } from './runAgent.js'
import {
  failBackgroundedAgent,
  finishBackgroundedAgent,
} from './backgroundedCompletion.js'

type SetAppState = Parameters<typeof completeAsyncAgent>[1]
type RunAgentParams = Parameters<typeof runAgent>[0]
type AgentContextCallback = Parameters<typeof runWithAgentContext>[0]

export function continueForegroundAgentInBackground({
  backgroundedTaskId,
  task,
  syncAgentContext,
  agentIterator,
  agentMessages,
  runAgentParams,
  rootSetAppState,
  toolUseContext,
  metadata,
  description,
  syncAgentId,
  getWorktreeResult,
}: {
  readonly backgroundedTaskId: string
  readonly task: LocalAgentTaskState
  readonly syncAgentContext: AgentContextCallback
  readonly agentIterator: AsyncIterator<MessageType>
  readonly agentMessages: MessageType[]
  readonly runAgentParams: RunAgentParams
  readonly rootSetAppState: SetAppState
  readonly toolUseContext: RunAgentParams['toolUseContext']
  readonly metadata: AgentLifecycleMetadata
  readonly description: string
  readonly syncAgentId: string
  readonly getWorktreeResult: () => Promise<WorktreeResult>
}): void {
  const abortController = task.abortController
  if (!abortController) {
    throw new Error(
      `Cannot background agent ${backgroundedTaskId}: missing abort controller`,
    )
  }

  void runWithAgentContext(syncAgentContext, async () => {
    let stopBackgroundedSummarization: (() => void) | undefined
    try {
      await closeIterator(agentIterator)
      const tracker = createProgressTracker()
      const resolveActivity = createActivityDescriptionResolver(
        toolUseContext.options.tools,
      )
      for (const existingMsg of agentMessages) {
        updateProgressFromMessage(
          tracker,
          existingMsg,
          resolveActivity,
          toolUseContext.options.tools,
        )
      }
      for await (const msg of runAgent({
        ...runAgentParams,
        isAsync: true,
        override: {
          ...runAgentParams.override,
          agentId: asAgentId(backgroundedTaskId),
          abortController,
        },
        onCacheSafeParams: getSdkAgentProgressSummariesEnabled()
          ? (params: CacheSafeParams) => {
              const { stop } = startAgentSummarization(
                backgroundedTaskId,
                asAgentId(backgroundedTaskId),
                params,
                rootSetAppState,
              )
              stopBackgroundedSummarization = stop
            }
          : undefined,
      })) {
        agentMessages.push(msg)
        updateProgressFromMessage(
          tracker,
          msg,
          resolveActivity,
          toolUseContext.options.tools,
        )
        updateAsyncAgentProgress(
          backgroundedTaskId,
          getProgressUpdate(tracker),
          rootSetAppState,
        )
        const lastToolName = getLastToolUseName(msg)
        if (lastToolName) {
          emitTaskProgress(
            tracker,
            backgroundedTaskId,
            toolUseContext.toolUseId,
            description,
            metadata.startTime,
            lastToolName,
          )
        }
      }
      await finishBackgroundedAgent({
        backgroundedTaskId,
        agentMessages,
        metadata,
        rootSetAppState,
        tracker,
        toolUseContext,
        abortController,
        description,
        getWorktreeResult,
      })
    } catch (error) {
      const handledError =
        error instanceof Error ? error : new Error(errorMessage(error))
      await failBackgroundedAgent({
        error: handledError,
        backgroundedTaskId,
        rootSetAppState,
        metadata,
        description,
        agentMessages,
        getWorktreeResult,
        toolUseContext,
      })
    } finally {
      stopBackgroundedSummarization?.()
      clearInvokedSkillsForAgent(syncAgentId)
      clearDumpState(syncAgentId)
    }
  })
}

async function closeIterator(agentIterator: AsyncIterator<MessageType>): Promise<void> {
  const close = agentIterator.return
    ? agentIterator.return(undefined).then(
        () => undefined,
        error => {
          logForDebugging(
            `Agent iterator cleanup failed: ${errorMessage(error)}`,
            { level: 'warn' },
          )
        },
      )
    : Promise.resolve()
  await Promise.race([close, sleep(1000)])
}
