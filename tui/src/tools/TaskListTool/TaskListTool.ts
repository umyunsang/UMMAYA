import { z } from 'zod/v4'
import { buildTool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import {
  getTaskListId,
  isTodoV2Enabled,
  listTasks,
  TaskStatusSchema,
} from '../../utils/tasks.js'
import { buildAgentSupportMetadata } from '../AgentTool/orchestrationSupport.js'
import { TASK_LIST_TOOL_NAME } from './constants.js'
import { DESCRIPTION, getPrompt } from './prompt.js'

const inputSchema = lazySchema(() => z.strictObject({}))
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() =>
  z.object({
    tasks: z.array(
      z.object({
        id: z.string(),
        subject: z.string(),
        status: TaskStatusSchema(),
        owner: z.string().optional(),
        blockedBy: z.array(z.string()),
      }),
    ),
    evidenceJoinKey: z.string(),
    parentToolUseId: z.string(),
    resumeToken: z.string(),
    permissionFlow: z.literal('coordinator_parent_round_trip'),
  }),
)
type OutputSchema = ReturnType<typeof outputSchema>

export type Output = z.infer<OutputSchema>

export const TaskListTool = buildTool({
  name: TASK_LIST_TOOL_NAME,
  searchHint: 'list all tasks',
  maxResultSizeChars: 100_000,
  async description() {
    return DESCRIPTION
  },
  async prompt() {
    return getPrompt()
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  userFacingName() {
    return 'TaskList'
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
  renderToolUseMessage() {
    return null
  },
  async call(_input, context) {
    const taskListId = getTaskListId()

    const allTasks = (await listTasks(taskListId)).filter(
      t => !t.metadata?._internal,
    )

    // Build a set of resolved task IDs for filtering
    const resolvedTaskIds = new Set(
      allTasks.filter(t => t.status === 'completed').map(t => t.id),
    )

    const tasks = allTasks.map(task => ({
      id: task.id,
      subject: task.subject,
      status: task.status,
      owner: task.owner,
      blockedBy: task.blockedBy.filter(id => !resolvedTaskIds.has(id)),
    }))

    return {
      data: {
        tasks,
        ...buildAgentSupportMetadata({
          taskId: taskListId,
          parentToolUseId: context.toolUseId,
        }),
      },
    }
  },
  mapToolResultToToolResultBlockParam(content, toolUseID) {
    const { tasks, evidenceJoinKey, parentToolUseId, resumeToken, permissionFlow } =
      outputSchema().parse(content)
    if (tasks.length === 0) {
      return {
        tool_use_id: toolUseID,
        type: 'tool_result',
        content: `No tasks found
evidence_join_key: ${evidenceJoinKey}
parent_tool_use_id: ${parentToolUseId}
resume_token: ${resumeToken}
permission_flow: ${permissionFlow}`,
      }
    }

    const lines = tasks.map(task => {
      const owner = task.owner ? ` (${task.owner})` : ''
      const blocked =
        task.blockedBy.length > 0
          ? ` [blocked by ${task.blockedBy.map(id => `#${id}`).join(', ')}]`
          : ''
      return `#${task.id} [${task.status}] ${task.subject}${owner}${blocked}`
    })

    return {
      tool_use_id: toolUseID,
      type: 'tool_result',
      content: `${lines.join('\n')}
evidence_join_key: ${evidenceJoinKey}
parent_tool_use_id: ${parentToolUseId}
resume_token: ${resumeToken}
permission_flow: ${permissionFlow}`,
    }
  },
} satisfies ToolDef<InputSchema, Output>)
