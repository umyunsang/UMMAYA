import { feature } from 'bun:bundle'
import { type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS, logEvent } from '../../services/analytics/index.js'
import {
  completeAgentTask as completeAsyncAgent,
  createProgressTracker,
  enqueueAgentNotification,
  failAgentTask as failAsyncAgent,
  getTokenCountFromTracker,
  killAsyncAgent,
} from '../../tasks/LocalAgentTask/LocalAgentTask.js'
import type { Message as MessageType } from '../../types/message.js'
import { AbortError, errorMessage } from '../../utils/errors.js'
import { extractTextContent } from '../../utils/messages.js'
import { classifyHandoffIfNeeded } from './agentToolHandoff.js'
import { extractPartialResult } from './agentToolPartialResult.js'
import { finalizeAgentTool } from './agentToolResult.js'
import { runAgent } from './runAgent.js'
import type { AgentLifecycleMetadata, WorktreeResult } from './schemas.js'

type SetAppState = Parameters<typeof completeAsyncAgent>[1]
type RunAgentParams = Parameters<typeof runAgent>[0]

export async function finishBackgroundedAgent({
  backgroundedTaskId,
  agentMessages,
  metadata,
  rootSetAppState,
  tracker,
  toolUseContext,
  abortController,
  description,
  getWorktreeResult,
}: {
  readonly backgroundedTaskId: string
  readonly agentMessages: MessageType[]
  readonly metadata: AgentLifecycleMetadata
  readonly rootSetAppState: SetAppState
  readonly tracker: ReturnType<typeof createProgressTracker>
  readonly toolUseContext: RunAgentParams['toolUseContext']
  readonly abortController: AbortController
  readonly description: string
  readonly getWorktreeResult: () => Promise<WorktreeResult>
}): Promise<void> {
  const agentResult = finalizeAgentTool(agentMessages, backgroundedTaskId, metadata)
  completeAsyncAgent(agentResult, rootSetAppState)
  let finalMessage = extractTextContent(agentResult.content, '\n')
  if (feature('TRANSCRIPT_CLASSIFIER')) {
    const handoffWarning = await classifyHandoffIfNeeded({
      agentMessages,
      tools: toolUseContext.options.tools,
      toolPermissionContext: toolUseContext.getAppState().toolPermissionContext,
      abortSignal: abortController.signal,
      subagentType: metadata.agentType,
      totalToolUseCount: agentResult.totalToolUseCount,
    })
    if (handoffWarning) finalMessage = `${handoffWarning}\n\n${finalMessage}`
  }
  enqueueAgentNotification({
    taskId: backgroundedTaskId,
    description,
    status: 'completed',
    setAppState: rootSetAppState,
    finalMessage,
    usage: {
      totalTokens: getTokenCountFromTracker(tracker),
      toolUses: agentResult.totalToolUseCount,
      durationMs: agentResult.totalDurationMs,
    },
    toolUseId: toolUseContext.toolUseId,
    ...(await getWorktreeResult()),
  })
}

export async function failBackgroundedAgent({
  error,
  backgroundedTaskId,
  rootSetAppState,
  metadata,
  description,
  agentMessages,
  getWorktreeResult,
  toolUseContext,
}: {
  readonly error: unknown
  readonly backgroundedTaskId: string
  readonly rootSetAppState: SetAppState
  readonly metadata: AgentLifecycleMetadata
  readonly description: string
  readonly agentMessages: MessageType[]
  readonly getWorktreeResult: () => Promise<WorktreeResult>
  readonly toolUseContext: RunAgentParams['toolUseContext']
}): Promise<void> {
  const worktreeResult = await getWorktreeResult()
  if (error instanceof AbortError) {
    killAsyncAgent(backgroundedTaskId, rootSetAppState)
    logEvent('tengu_agent_tool_terminated', {
      agent_type: metadata.agentType as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
      model: metadata.resolvedAgentModel as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
      duration_ms: Date.now() - metadata.startTime,
      is_async: true,
      is_built_in_agent: metadata.isBuiltInAgent,
      reason: 'user_cancel_background' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
    })
    enqueueAgentNotification({
      taskId: backgroundedTaskId,
      description,
      status: 'killed',
      setAppState: rootSetAppState,
      toolUseId: toolUseContext.toolUseId,
      finalMessage: extractPartialResult(agentMessages),
      ...worktreeResult,
    })
    return
  }
  const errMsg = errorMessage(error)
  failAsyncAgent(backgroundedTaskId, errMsg, rootSetAppState)
  enqueueAgentNotification({
    taskId: backgroundedTaskId,
    description,
    status: 'failed',
    error: errMsg,
    setAppState: rootSetAppState,
    toolUseId: toolUseContext.toolUseId,
    ...worktreeResult,
  })
}
