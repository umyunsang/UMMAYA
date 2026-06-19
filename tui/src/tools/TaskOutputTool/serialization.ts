import type { ToolResultBlockParam } from '@anthropic-ai/sdk/resources/index.mjs'
import { formatTaskOutput } from '../../utils/task/outputFormatting.js'
import type { TaskOutputToolOutput } from './schemas.js'

export function mapTaskOutputResultToToolResultBlockParam(
  data: TaskOutputToolOutput,
  toolUseID: string,
): ToolResultBlockParam {
  const parts: string[] = []
  parts.push(`<retrieval_status>${data.retrieval_status}</retrieval_status>`)
  parts.push(`<evidence_join_key>${data.evidenceJoinKey}</evidence_join_key>`)
  parts.push(`<parent_tool_use_id>${data.parentToolUseId}</parent_tool_use_id>`)
  parts.push(`<resume_token>${data.resumeToken}</resume_token>`)
  parts.push(`<permission_flow>${data.permissionFlow}</permission_flow>`)
  if (data.task) {
    parts.push(`<task_id>${data.task.task_id}</task_id>`)
    parts.push(`<task_type>${data.task.task_type}</task_type>`)
    parts.push(`<status>${data.task.status}</status>`)
    if (data.task.exitCode !== undefined && data.task.exitCode !== null) {
      parts.push(`<exit_code>${data.task.exitCode}</exit_code>`)
    }
    if (data.task.output?.trim()) {
      const { content } = formatTaskOutput(
        data.task.output,
        data.task.task_id,
      )
      parts.push(`<output>\n${content.trimEnd()}\n</output>`)
    }
    if (data.task.error) parts.push(`<error>${data.task.error}</error>`)
  }
  return {
    tool_use_id: toolUseID,
    type: 'tool_result',
    content: parts.join('\n\n'),
  }
}
