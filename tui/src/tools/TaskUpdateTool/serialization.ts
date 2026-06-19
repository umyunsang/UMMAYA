import type { ToolResultBlockParam } from '@anthropic-ai/sdk/resources/index.mjs'
import { isAgentSwarmsEnabled } from '../../utils/agentSwarmsEnabled.js'
import { getAgentId } from '../../utils/teammate.js'
import { VERIFICATION_AGENT_TYPE } from '../AgentTool/constants.js'
import type { Output } from './schemas.js'

function supportMetadataText(content: Output): string {
  return `evidence_join_key: ${content.evidenceJoinKey}
parent_tool_use_id: ${content.parentToolUseId}
resume_token: ${content.resumeToken}
permission_flow: ${content.permissionFlow}`
}

function completedTaskReminder(content: Output): string {
  if (content.statusChange?.to !== 'completed') return ''
  if (!getAgentId() || !isAgentSwarmsEnabled()) return ''
  return '\n\nTask completed. Call TaskList now to find your next available task or see if your work unblocked others.'
}

function verificationReminder(content: Output): string {
  if (!content.verificationNudgeNeeded) return ''
  return `\n\nNOTE: You just closed out 3+ tasks and none of them was a verification step. Before writing your final summary, spawn the verification agent (subagent_type="${VERIFICATION_AGENT_TYPE}"). You cannot self-assign PARTIAL by listing caveats in your summary — only the verifier issues a verdict.`
}

export function mapTaskUpdateResultToToolResultBlockParam(
  content: Output,
  toolUseID: string,
): ToolResultBlockParam {
  const metadata = supportMetadataText(content)
  if (!content.success) {
    return {
      tool_use_id: toolUseID,
      type: 'tool_result',
      content: `${content.error || `Task #${content.taskId} not found`}\n${metadata}`,
    }
  }

  const resultContent = `Updated task #${content.taskId} ${content.updatedFields.join(', ')}
${metadata}${completedTaskReminder(content)}${verificationReminder(content)}`

  return {
    tool_use_id: toolUseID,
    type: 'tool_result',
    content: resultContent,
  }
}
