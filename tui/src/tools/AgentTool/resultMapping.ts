import type { ToolResultBlockParam } from '@anthropic-ai/sdk/resources/index.mjs'
import { BASH_TOOL_NAME } from '../BashTool/toolName.js'
import { FILE_READ_TOOL_NAME } from '../FileReadTool/prompt.js'
import { formatSourceVerificationForModel } from '../WebFetchTool/sourceVerification.js'
import { ONE_SHOT_BUILTIN_AGENT_TYPES } from './constants.js'
import type { AgentToolOutput } from './schemas.js'

function assertNever(value: never): never {
  throw new Error(`Unexpected agent tool result status: ${JSON.stringify(value)}`)
}

export function mapAgentToolResultToToolResultBlockParam(
  data: AgentToolOutput,
  toolUseID: string,
): ToolResultBlockParam {
  switch (data.status) {
    case 'teammate_spawned':
      return {
        tool_use_id: toolUseID,
        type: 'tool_result',
        content: [
          {
            type: 'text',
            text: `Spawned successfully.
agent_id: ${data.teammate_id}
name: ${data.name}
team_name: ${data.team_name}
evidence_join_key: ${data.evidenceJoinKey}
parent_tool_use_id: ${data.parentToolUseId}
resume_token: ${data.resumeToken}
permission_flow: ${data.permissionFlow}
The agent is now running and will receive instructions via mailbox.`,
          },
        ],
      }
    case 'remote_launched':
      return {
        tool_use_id: toolUseID,
        type: 'tool_result',
        content: [
          {
            type: 'text',
            text: `Remote agent launched in CCR.\ntaskId: ${data.taskId}\nsession_url: ${data.sessionUrl}\noutput_file: ${data.outputFile}\nThe agent is running remotely. You will be notified automatically when it completes.\nBriefly tell the user what you launched and end your response.`,
          },
        ],
      }
    case 'async_launched':
      return mapAsyncAgentResult(data, toolUseID)
    case 'completed':
      return mapCompletedAgentResult(data, toolUseID)
    default:
      return assertNever(data)
  }
}

function mapAsyncAgentResult(
  data: Extract<AgentToolOutput, { readonly status: 'async_launched' }>,
  toolUseID: string,
): ToolResultBlockParam {
  const supportMetadata = `evidence_join_key: ${data.evidenceJoinKey}\nparent_tool_use_id: ${data.parentToolUseId}\nresume_token: ${data.resumeToken}\npermission_flow: ${data.permissionFlow}`
  const prefix = `Async agent launched successfully.\nagentId: ${data.agentId} (internal ID - do not mention to user. Use SendMessage with to: '${data.agentId}' to continue this agent.)\n${supportMetadata}\nThe agent is working in the background. You will be notified automatically when it completes.`
  const instructions = data.canReadOutputFile
    ? `Do not duplicate this agent's work — avoid working with the same files or topics it is using. Work on non-overlapping tasks, or briefly tell the user what you launched and end your response.\noutput_file: ${data.outputFile}\nIf asked, you can check progress before completion by using ${FILE_READ_TOOL_NAME} or ${BASH_TOOL_NAME} tail on the output file.`
    : `Briefly tell the user what you launched and end your response. Do not generate any other text — agent results will arrive in a subsequent message.`
  return {
    tool_use_id: toolUseID,
    type: 'tool_result',
    content: [{ type: 'text', text: `${prefix}\n${instructions}` }],
  }
}

function mapCompletedAgentResult(
  data: Extract<AgentToolOutput, { readonly status: 'completed' }>,
  toolUseID: string,
): ToolResultBlockParam {
  const worktreeInfoText = data.worktreePath
    ? `\nworktreePath: ${data.worktreePath}\nworktreeBranch: ${data.worktreeBranch}`
    : ''
  const sourceVerificationText = formatSourceVerificationForModel(
    data.sourceVerification,
  )
  const sourceVerificationSuffix = sourceVerificationText
    ? `\n${sourceVerificationText}`
    : ''
  const contentOrMarker =
    data.content.length > 0
      ? data.content
      : [{ type: 'text' as const, text: '(Subagent completed but returned no output.)' }]

  if (
    data.agentType &&
    ONE_SHOT_BUILTIN_AGENT_TYPES.has(data.agentType) &&
    !worktreeInfoText
  ) {
    return { tool_use_id: toolUseID, type: 'tool_result', content: contentOrMarker }
  }

  return {
    tool_use_id: toolUseID,
    type: 'tool_result',
    content: [
      ...contentOrMarker,
      {
        type: 'text',
        text: `agentId: ${data.agentId} (use SendMessage with to: '${data.agentId}' to continue this agent)${worktreeInfoText}
evidence_join_key: ${data.evidenceJoinKey}
parent_tool_use_id: ${data.parentToolUseId}
resume_token: ${data.resumeToken}
permission_flow: ${data.permissionFlow}
<usage>total_tokens: ${data.totalTokens}
tool_uses: ${data.totalToolUseCount}
duration_ms: ${data.totalDurationMs}</usage>${sourceVerificationSuffix}`,
      },
    ],
  }
}
