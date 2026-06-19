import * as React from 'react'
import { getSdkAgentProgressSummariesEnabled } from '../../bootstrap/state.js'
import {
  createActivityDescriptionResolver,
  createProgressTracker,
  getProgressUpdate,
  updateAgentProgress as updateAsyncAgentProgress,
  updateProgressFromMessage,
} from '../../tasks/LocalAgentTask/LocalAgentTask.js'
import type { ToolUseContext } from '../../Tool.js'
import type { Message as MessageType } from '../../types/message.js'
import { normalizeMessages } from '../../utils/messages.js'
import { getAssistantMessageContentLength } from '../../utils/tokens.js'
import { BackgroundHint } from '../BashTool/UI.js'
import { emitTaskProgress, getLastToolUseName } from './agentToolProgress.js'
import {
  isBackgroundTasksDisabled,
  PROGRESS_THRESHOLD_MS,
} from './runtimeConfig.js'
import type { AgentToolProgressCallback } from './schemas.js'

type SetAppState = Parameters<typeof updateAsyncAgentProgress>[2]
export type AssistantProgressSource = {
  readonly requestId?: string
  readonly message?: { readonly id?: string }
}

export function emitInitialProgress(
  promptMessages: MessageType[],
  prompt: string,
  syncAgentId: string,
  assistantMessage: AssistantProgressSource | undefined,
  onProgress: AgentToolProgressCallback | undefined,
): void {
  if (promptMessages.length === 0 || !onProgress) return
  const normalizedFirstMessage = normalizeMessages(promptMessages).find(
    message => message.type === 'user',
  )
  if (!normalizedFirstMessage) return
  onProgress({
    toolUseID: `agent_${assistantMessage?.message?.id}`,
    data: {
      message: normalizedFirstMessage,
      type: 'agent_progress',
      prompt,
      agentId: syncAgentId,
    },
  })
}

export function showBackgroundHintIfNeeded(
  backgroundHintShown: boolean,
  agentStartTime: number,
  toolUseContext: ToolUseContext,
): boolean {
  if (
    isBackgroundTasksDisabled ||
    backgroundHintShown ||
    Date.now() - agentStartTime < PROGRESS_THRESHOLD_MS ||
    !toolUseContext.setToolJSX
  ) {
    return backgroundHintShown
  }
  toolUseContext.setToolJSX({
    jsx: React.createElement(BackgroundHint),
    shouldHidePromptInput: false,
    shouldContinueAnimation: true,
    showSpinner: true,
  })
  return true
}

export function emitMessageProgress({
  message,
  syncTracker,
  syncResolveActivity,
  foregroundTaskId,
  toolUseContext,
  rootSetAppState,
  description,
  agentStartTime,
  syncAgentId,
  assistantMessage,
  onProgress,
}: {
  readonly message: MessageType
  readonly syncTracker: ReturnType<typeof createProgressTracker>
  readonly syncResolveActivity: ReturnType<typeof createActivityDescriptionResolver>
  readonly foregroundTaskId?: string
  readonly toolUseContext: ToolUseContext
  readonly rootSetAppState: SetAppState
  readonly description: string
  readonly agentStartTime: number
  readonly syncAgentId: string
  readonly assistantMessage: AssistantProgressSource | undefined
  readonly onProgress: AgentToolProgressCallback | undefined
}): void {
  updateProgressFromMessage(
    syncTracker,
    message,
    syncResolveActivity,
    toolUseContext.options.tools,
  )
  if (foregroundTaskId) {
    const lastToolName = getLastToolUseName(message)
    if (lastToolName) {
      emitTaskProgress(
        syncTracker,
        foregroundTaskId,
        toolUseContext.toolUseId,
        description,
        agentStartTime,
        lastToolName,
      )
      if (getSdkAgentProgressSummariesEnabled()) {
        updateAsyncAgentProgress(
          foregroundTaskId,
          getProgressUpdate(syncTracker),
          rootSetAppState,
        )
      }
    }
  }
  if (
    message.type === 'progress' &&
    (message.data.type === 'bash_progress' ||
      message.data.type === 'powershell_progress') &&
    onProgress
  ) {
    onProgress({ toolUseID: message.toolUseID, data: message.data })
  }
  if (message.type !== 'assistant' && message.type !== 'user') return
  if (message.type === 'assistant') {
    const contentLength = getAssistantMessageContentLength(message)
    if (contentLength > 0) {
      toolUseContext.setResponseLength(length => length + contentLength)
    }
  }
  emitNormalizedToolProgress(
    message,
    {
      syncAgentId,
      toolUseID: `agent_${assistantMessage?.message?.id}`,
    },
    onProgress,
  )
}

function emitNormalizedToolProgress(
  message: MessageType,
  progressTarget: { readonly syncAgentId: string; readonly toolUseID: string },
  onProgress: AgentToolProgressCallback | undefined,
): void {
  if (!onProgress) return
  for (const normalizedMessage of normalizeMessages([message])) {
    for (const content of normalizedMessage.message.content) {
      if (content.type !== 'tool_use' && content.type !== 'tool_result') continue
      onProgress({
        toolUseID: progressTarget.toolUseID,
        data: {
          message: normalizedMessage,
          type: 'agent_progress',
          prompt: '',
          agentId: progressTarget.syncAgentId,
        },
      })
    }
  }
}
