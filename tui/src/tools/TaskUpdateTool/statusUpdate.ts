import type { ToolResult, ToolUseContext } from '../../Tool.js'
import { isAgentSwarmsEnabled } from '../../utils/agentSwarmsEnabled.js'
import {
  blockTask,
  deleteTask,
  getTask,
  getTaskListId,
  type Task,
  type TaskStatus,
  updateTask,
} from '../../utils/tasks.js'
import { getAgentName, getTeammateColor } from '../../utils/teammate.js'
import { writeToMailbox } from '../../utils/teammateMailbox.js'
import { buildAgentSupportMetadata } from '../AgentTool/orchestrationSupport.js'
import {
  collectCompletedHookErrors,
  needsVerificationNudge,
} from './completion.js'
import type { Output, TaskUpdateToolInput } from './schemas.js'

type TaskUpdates = {
  subject?: string
  description?: string
  activeForm?: string
  status?: TaskStatus
  owner?: string
  metadata?: Record<string, unknown>
}

function expandTaskList(context: ToolUseContext): void {
  context.setAppState(prev => {
    if (prev.expandedView === 'tasks') return prev
    return { ...prev, expandedView: 'tasks' }
  })
}

function addChangedTextField(
  updates: TaskUpdates,
  updatedFields: string[],
  field: 'subject' | 'description' | 'activeForm' | 'owner',
  nextValue: string | undefined,
  currentValue: string | undefined,
): void {
  if (nextValue === undefined || nextValue === currentValue) return
  updates[field] = nextValue
  updatedFields.push(field)
}

function applyMetadataUpdate(
  updates: TaskUpdates,
  updatedFields: string[],
  existingTask: Task,
  metadata: Record<string, unknown> | undefined,
): void {
  if (metadata === undefined) return

  const merged = { ...(existingTask.metadata ?? {}) }
  for (const [key, value] of Object.entries(metadata)) {
    if (value === null) {
      delete merged[key]
    } else {
      merged[key] = value
    }
  }
  updates.metadata = merged
  updatedFields.push('metadata')
}

function applyImplicitOwner(
  updates: TaskUpdates,
  updatedFields: string[],
  input: TaskUpdateToolInput,
  existingTask: Task,
): void {
  if (
    !isAgentSwarmsEnabled() ||
    input.status !== 'in_progress' ||
    input.owner !== undefined ||
    existingTask.owner
  ) {
    return
  }

  const agentName = getAgentName()
  if (!agentName) return
  updates.owner = agentName
  updatedFields.push('owner')
}

async function notifyNewOwner(
  taskListId: string,
  updates: TaskUpdates,
  input: TaskUpdateToolInput,
  existingTask: Task,
): Promise<void> {
  if (!updates.owner || !isAgentSwarmsEnabled()) return

  const senderName = getAgentName() || 'team-lead'
  const assignmentMessage = JSON.stringify({
    type: 'task_assignment',
    taskId: input.taskId,
    subject: existingTask.subject,
    description: existingTask.description,
    assignedBy: senderName,
    timestamp: new Date().toISOString(),
  })
  await writeToMailbox(
    updates.owner,
    {
      from: senderName,
      text: assignmentMessage,
      timestamp: new Date().toISOString(),
      color: getTeammateColor(),
    },
    taskListId,
  )
}

async function applyDependencyUpdates(
  taskListId: string,
  input: TaskUpdateToolInput,
  existingTask: Task,
  updatedFields: string[],
): Promise<void> {
  if (input.addBlocks && input.addBlocks.length > 0) {
    const newBlocks = input.addBlocks.filter(
      id => !existingTask.blocks.includes(id),
    )
    for (const blockId of newBlocks) {
      await blockTask(taskListId, input.taskId, blockId)
    }
    if (newBlocks.length > 0) updatedFields.push('blocks')
  }

  if (input.addBlockedBy && input.addBlockedBy.length > 0) {
    const newBlockedBy = input.addBlockedBy.filter(
      id => !existingTask.blockedBy.includes(id),
    )
    for (const blockerId of newBlockedBy) {
      await blockTask(taskListId, blockerId, input.taskId)
    }
    if (newBlockedBy.length > 0) updatedFields.push('blockedBy')
  }
}

function supportFailure(
  input: TaskUpdateToolInput,
  context: ToolUseContext,
): Output {
  return {
    success: false,
    taskId: input.taskId,
    updatedFields: [],
    error: 'Task not found',
    ...buildAgentSupportMetadata({
      taskId: input.taskId,
      parentToolUseId: context.toolUseId,
    }),
  }
}

export async function callTaskUpdateTool(
  input: TaskUpdateToolInput,
  context: ToolUseContext,
): Promise<ToolResult<Output>> {
  const taskListId = getTaskListId()
  const supportMetadata = buildAgentSupportMetadata({
    taskId: input.taskId,
    parentToolUseId: context.toolUseId,
  })
  expandTaskList(context)

  const existingTask = await getTask(taskListId, input.taskId)
  if (!existingTask) return { data: supportFailure(input, context) }

  if (input.status === 'deleted') {
    const deleted = await deleteTask(taskListId, input.taskId)
    return {
      data: {
        success: deleted,
        taskId: input.taskId,
        updatedFields: deleted ? ['deleted'] : [],
        error: deleted ? undefined : 'Failed to delete task',
        statusChange: deleted
          ? { from: existingTask.status, to: 'deleted' }
          : undefined,
        ...supportMetadata,
      },
    }
  }

  const updatedFields: string[] = []
  const updates: TaskUpdates = {}
  addChangedTextField(updates, updatedFields, 'subject', input.subject, existingTask.subject)
  addChangedTextField(updates, updatedFields, 'description', input.description, existingTask.description)
  addChangedTextField(updates, updatedFields, 'activeForm', input.activeForm, existingTask.activeForm)
  addChangedTextField(updates, updatedFields, 'owner', input.owner, existingTask.owner)
  applyImplicitOwner(updates, updatedFields, input, existingTask)
  applyMetadataUpdate(updates, updatedFields, existingTask, input.metadata)

  if (input.status !== undefined && input.status !== existingTask.status) {
    if (input.status === 'completed') {
      const blockingErrors = await collectCompletedHookErrors(
        input,
        context,
        existingTask,
      )
      if (blockingErrors.length > 0) {
        return {
          data: {
            success: false,
            taskId: input.taskId,
            updatedFields: [],
            error: blockingErrors.join('\n'),
            ...supportMetadata,
          },
        }
      }
    }
    updates.status = input.status
    updatedFields.push('status')
  }

  if (Object.keys(updates).length > 0) {
    await updateTask(taskListId, input.taskId, updates)
  }
  await notifyNewOwner(taskListId, updates, input, existingTask)
  await applyDependencyUpdates(taskListId, input, existingTask, updatedFields)

  return {
    data: {
      success: true,
      taskId: input.taskId,
      updatedFields,
      statusChange:
        updates.status !== undefined
          ? { from: existingTask.status, to: updates.status }
          : undefined,
      verificationNudgeNeeded: await needsVerificationNudge(
        taskListId,
        context,
        updates,
      ),
      ...supportMetadata,
    },
  }
}
