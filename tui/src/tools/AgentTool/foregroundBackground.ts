import {
  isLocalAgentTask,
  updateAgentProgress as updateAsyncAgentProgress,
} from '../../tasks/LocalAgentTask/LocalAgentTask.js'
import type { ToolUseContext } from '../../Tool.js'
import type { Message as MessageType } from '../../types/message.js'
import { getTaskOutputPath } from '../../utils/task/diskOutput.js'
import { buildAgentSupportMetadata } from './orchestrationSupport.js'
import { continueForegroundAgentInBackground } from './backgroundedLifecycle.js'
import { canReadAgentOutputFile } from './asyncLifecycle.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import { runAgent } from './runAgent.js'
import type {
  AgentLifecycleMetadata,
  AsyncLaunchedOutput,
  WorktreeResult,
} from './schemas.js'

type SetAppState = Parameters<typeof updateAsyncAgentProgress>[2]
type RunAgentParams = Parameters<typeof runAgent>[0]
type SyncAgentContext = Parameters<typeof continueForegroundAgentInBackground>[0]['syncAgentContext']

export function maybeBackgroundAgent({
  foregroundTaskId,
  agentIterator,
  agentMessages,
  toolUseContext,
  rootSetAppState,
  description,
  prompt,
  syncAgentId,
  runAgentParams,
  metadata,
  getWorktreeResult,
  syncAgentContext,
  stopForegroundSummarization,
}: {
  readonly foregroundTaskId: string
  readonly agentIterator: AsyncIterator<MessageType>
  readonly agentMessages: MessageType[]
  readonly toolUseContext: ToolUseContext
  readonly rootSetAppState: SetAppState
  readonly description: string
  readonly prompt: string
  readonly syncAgentId: string
  readonly selectedAgent: AgentDefinition
  readonly runAgentParams: RunAgentParams
  readonly metadata: AgentLifecycleMetadata
  readonly getWorktreeResult: () => Promise<WorktreeResult>
  readonly syncAgentContext: SyncAgentContext
  readonly stopForegroundSummarization: () => void
}): AsyncLaunchedOutput | undefined {
  const task = toolUseContext.getAppState().tasks[foregroundTaskId]
  if (!isLocalAgentTask(task) || !task.isBackgrounded) return undefined
  stopForegroundSummarization()
  continueForegroundAgentInBackground({
    backgroundedTaskId: foregroundTaskId,
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
  })
  return {
    isAsync: true,
    status: 'async_launched',
    agentId: foregroundTaskId,
    description,
    prompt,
    outputFile: getTaskOutputPath(foregroundTaskId),
    canReadOutputFile: canReadAgentOutputFile(toolUseContext.options.tools),
    ...buildAgentSupportMetadata({
      agentId: foregroundTaskId,
      parentToolUseId: toolUseContext.toolUseId,
    }),
  }
}
