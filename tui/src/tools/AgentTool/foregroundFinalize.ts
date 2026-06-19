import { feature } from 'bun:bundle'
import { type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS, logEvent } from '../../services/analytics/index.js'
import type { ToolUseContext } from '../../Tool.js'
import type { Message as MessageType } from '../../types/message.js'
import { AbortError } from '../../utils/errors.js'
import { logForDebugging } from '../../utils/debug.js'
import { isSyntheticMessage } from '../../utils/messages.js'
import { classifyHandoffIfNeeded } from './agentToolHandoff.js'
import { finalizeAgentTool } from './agentToolResult.js'
import { buildAgentSupportMetadata } from './orchestrationSupport.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import type {
  AgentLifecycleMetadata,
  AgentToolCallResult,
  WorktreeResult,
} from './schemas.js'

export function logTermination(
  metadata: AgentLifecycleMetadata,
  isAsync: boolean,
  reason: 'user_cancel_sync' | 'user_cancel_background',
): void {
  logEvent('tengu_agent_tool_terminated', {
    agent_type: metadata.agentType as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
    model: metadata.resolvedAgentModel as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
    duration_ms: Date.now() - metadata.startTime,
    is_async: isAsync,
    is_built_in_agent: metadata.isBuiltInAgent,
    reason: reason as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
  })
}

export async function finalizeSyncAgent({
  agentMessages,
  syncAgentError,
  metadata,
  selectedAgent,
  toolUseContext,
  prompt,
  syncAgentId,
  worktreeResult,
}: {
  readonly agentMessages: MessageType[]
  readonly syncAgentError?: Error
  readonly metadata: AgentLifecycleMetadata
  readonly selectedAgent: AgentDefinition
  readonly toolUseContext: ToolUseContext
  readonly prompt: string
  readonly syncAgentId: string
  readonly worktreeResult: WorktreeResult
}): Promise<AgentToolCallResult> {
  const lastMessage = agentMessages.findLast(
    message => message.type !== 'system' && message.type !== 'progress',
  )
  if (lastMessage && isSyntheticMessage(lastMessage)) {
    logTermination(metadata, false, 'user_cancel_sync')
    throw new AbortError()
  }

  if (syncAgentError) {
    const hasAssistantMessages = agentMessages.some(
      message => message.type === 'assistant',
    )
    if (!hasAssistantMessages) throw syncAgentError
    logForDebugging(
      `Sync agent recovering from error with ${agentMessages.length} messages`,
    )
  }
  const agentResult = finalizeAgentTool(agentMessages, syncAgentId, metadata)
  if (feature('TRANSCRIPT_CLASSIFIER')) {
    const handoffWarning = await classifyHandoffIfNeeded({
      agentMessages,
      tools: toolUseContext.options.tools,
      toolPermissionContext: toolUseContext.getAppState().toolPermissionContext,
      abortSignal: toolUseContext.abortController.signal,
      subagentType: selectedAgent.agentType,
      totalToolUseCount: agentResult.totalToolUseCount,
    })
    if (handoffWarning) {
      agentResult.content = [
        { type: 'text', text: handoffWarning },
        ...agentResult.content,
      ]
    }
  }
  return {
    data: {
      status: 'completed',
      prompt,
      ...agentResult,
      ...worktreeResult,
      ...buildAgentSupportMetadata({
        agentId: syncAgentId,
        parentToolUseId: toolUseContext.toolUseId,
      }),
    },
  }
}
