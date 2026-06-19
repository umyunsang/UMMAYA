import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import {
  getTask,
  getTaskListId,
  isTodoV2Enabled,
  TaskStatusSchema,
} from '../../utils/tasks.js'
import { buildAgentSupportMetadata } from '../AgentTool/orchestrationSupport.js'
import { TASK_GET_TOOL_NAME } from './constants.js'
import { DESCRIPTION, PROMPT } from './prompt.js'

const inputSchema = lazySchema(() =>
  z.strictObject({
    taskId: z.string().describe('The ID of the task to retrieve'),
  }),
)
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() =>
  z.object({
    task: z
      .object({
        id: z.string(),
        subject: z.string(),
        description: z.string(),
        status: TaskStatusSchema(),
        blocks: z.array(z.string()),
        blockedBy: z.array(z.string()),
      })
      .nullable(),
    evidenceJoinKey: z.string(),
    parentToolUseId: z.string(),
    resumeToken: z.string(),
    permissionFlow: z.literal('coordinator_parent_round_trip'),
  }),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

export const TaskGetTool = buildTool({
  name: TASK_GET_TOOL_NAME,
  searchHint: 'retrieve a task by ID',
  maxResultSizeChars: 100_000,
  async description() {
    return DESCRIPTION
  },
  async prompt() {
    return PROMPT
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  userFacingName() {
    return 'TaskGet'
  },
  shouldDefer: true,
  isEnabled() {
    return isTodoV2Enabled()
  },
  isConcurrencySafe() {
    return true
  },
  isReadOnly() {
    return true
  },
  toAutoClassifierInput(input) {
    return input.taskId
  },
  renderToolUseMessage() {
    return null
  },
  async call({ taskId }, context) {
    const taskListId = getTaskListId()
    const supportMetadata = buildAgentSupportMetadata({
      taskId,
      parentToolUseId: context.toolUseId,
    })

    const task = await getTask(taskListId, taskId)

    if (!task) {
      return {
        data: {
          task: null,
          ...supportMetadata,
        },
      }
    }

    return {
      data: {
        task: {
          id: task.id,
          subject: task.subject,
          description: task.description,
          status: task.status,
          blocks: task.blocks,
          blockedBy: task.blockedBy,
        },
        ...supportMetadata,
      },
    }
  },
  mapToolResultToToolResultBlockParam(content, toolUseID) {
    const { task, evidenceJoinKey, parentToolUseId, resumeToken, permissionFlow } =
      outputSchema().parse(content)
    if (!task) {
      return {
        tool_use_id: toolUseID,
        type: 'tool_result',
        content: `Task not found
evidence_join_key: ${evidenceJoinKey}
parent_tool_use_id: ${parentToolUseId}
resume_token: ${resumeToken}
permission_flow: ${permissionFlow}`,
      }
    }

    const lines = [
      `Task #${task.id}: ${task.subject}`,
      `Status: ${task.status}`,
      `Description: ${task.description}`,
      `Evidence join key: ${evidenceJoinKey}`,
      `Parent tool use ID: ${parentToolUseId}`,
      `Resume token: ${resumeToken}`,
      `Permission flow: ${permissionFlow}`,
    ]

    if (task.blockedBy.length > 0) {
      lines.push(`Blocked by: ${task.blockedBy.map(id => `#${id}`).join(', ')}`)
    }
    if (task.blocks.length > 0) {
      lines.push(`Blocks: ${task.blocks.map(id => `#${id}`).join(', ')}`)
    }

    return {
      tool_use_id: toolUseID,
      type: 'tool_result',
      content: lines.join('\n'),
    }
  },
} satisfies ToolDef<InputSchema, Output>)
