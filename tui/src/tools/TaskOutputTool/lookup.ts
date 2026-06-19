import type { ToolResult, ToolUseContext, ValidationResult } from '../../Tool.js'
import type { TaskState } from '../../tasks/types.js'
import { AbortError } from '../../utils/errors.js'
import { extractTextContent } from '../../utils/messages.js'
import { sleep } from '../../utils/sleep.js'
import { getTaskOutput } from '../../utils/task/diskOutput.js'
import { updateTaskState } from '../../utils/task/framework.js'
import { buildAgentSupportMetadata } from '../AgentTool/orchestrationSupport.js'
import type {
  TaskOutputRecord,
  TaskOutputToolInput,
  TaskOutputToolOutput,
} from './schemas.js'

type TaskOutputProgressEvent = {
  readonly toolUseID: string
  readonly data: {
    readonly type: 'waiting_for_task'
    readonly taskDescription: string
    readonly taskType: string
    readonly evidenceJoinKey: string
    readonly parentToolUseId: string
    readonly resumeToken: string
    readonly permissionFlow: 'coordinator_parent_round_trip'
  }
}

type TaskOutputProgressCallback = (progress: TaskOutputProgressEvent) => void

export class TaskOutputLookupError extends Error {
  constructor(readonly taskId: string) {
    super(`No task found with ID: ${taskId}`)
    this.name = 'TaskOutputLookupError'
  }
}

function assertNeverTask(task: never): never {
  throw new TaskOutputLookupError(task)
}

async function readTaskOutput(task: TaskState): Promise<string> {
  if (task.type !== 'local_bash') return getTaskOutput(task.id)
  const taskOutput = task.shellCommand?.taskOutput
  if (!taskOutput) return getTaskOutput(task.id)

  const stdout = await taskOutput.getStdout()
  const stderr = await taskOutput.getStderr()
  return [stdout, stderr].filter(Boolean).join('\n')
}

export async function getTaskOutputData(
  task: TaskState,
): Promise<TaskOutputRecord> {
  const output = await readTaskOutput(task)
  const baseOutput = {
    task_id: task.id,
    task_type: task.type,
    status: task.status,
    description: task.description,
    output,
  }

  switch (task.type) {
    case 'local_bash':
      return { ...baseOutput, exitCode: task.result?.code ?? null }
    case 'local_agent': {
      const cleanResult = task.result
        ? extractTextContent(task.result.content, '\n')
        : undefined
      return {
        ...baseOutput,
        prompt: task.prompt,
        result: cleanResult || output,
        output: cleanResult || output,
        error: task.error,
      }
    }
    case 'remote_agent':
      return { ...baseOutput, prompt: task.command }
    case 'in_process_teammate':
    case 'local_workflow':
    case 'monitor_mcp':
    case 'dream':
      return baseOutput
    default:
      return assertNeverTask(task)
  }
}

export async function validateTaskOutputInput(
  { task_id }: TaskOutputToolInput,
  { getAppState }: Pick<ToolUseContext, 'getAppState'>,
): Promise<ValidationResult> {
  if (!task_id) {
    return { result: false, message: 'Task ID is required', errorCode: 1 }
  }

  const task = getAppState().tasks?.[task_id]
  if (!task) {
    return {
      result: false,
      message: `No task found with ID: ${task_id}`,
      errorCode: 2,
    }
  }
  return { result: true }
}

async function waitForTaskCompletion(
  taskId: string,
  getAppState: ToolUseContext['getAppState'],
  timeoutMs: number,
  abortController?: AbortController,
): Promise<TaskState | null> {
  const startTime = Date.now()
  while (Date.now() - startTime < timeoutMs) {
    if (abortController?.signal.aborted) throw new AbortError()

    const task = getAppState().tasks?.[taskId]
    if (!task) return null
    if (task.status !== 'running' && task.status !== 'pending') return task

    await sleep(100)
  }

  return getAppState().tasks?.[taskId] ?? null
}

function markTaskNotified(taskId: string, context: ToolUseContext): void {
  updateTaskState(taskId, context.setAppState, task => ({
    ...task,
    notified: true,
  }))
}

function isTaskStillActive(task: TaskState): boolean {
  return task.status === 'running' || task.status === 'pending'
}

export async function callTaskOutputTool(
  input: TaskOutputToolInput,
  context: ToolUseContext,
  onProgress?: TaskOutputProgressCallback,
): Promise<ToolResult<TaskOutputToolOutput>> {
  const task = context.getAppState().tasks?.[input.task_id]
  if (!task) throw new TaskOutputLookupError(input.task_id)

  const supportMetadata = buildAgentSupportMetadata({
    taskId: input.task_id,
    parentToolUseId: task.toolUseId ?? context.toolUseId,
  })

  if (!input.block) {
    if (!isTaskStillActive(task)) {
      markTaskNotified(input.task_id, context)
      return {
        data: {
          retrieval_status: 'success',
          task: await getTaskOutputData(task),
          ...supportMetadata,
        },
      }
    }
    return {
      data: {
        retrieval_status: 'not_ready',
        task: await getTaskOutputData(task),
        ...supportMetadata,
      },
    }
  }

  onProgress?.({
    toolUseID: `task-output-waiting-${Date.now()}`,
    data: {
      type: 'waiting_for_task',
      taskDescription: task.description,
      taskType: task.type,
      ...supportMetadata,
    },
  })

  const completedTask = await waitForTaskCompletion(
    input.task_id,
    context.getAppState,
    input.timeout,
    context.abortController,
  )
  if (!completedTask) {
    return {
      data: {
        retrieval_status: 'timeout',
        task: null,
        ...supportMetadata,
      },
    }
  }
  if (isTaskStillActive(completedTask)) {
    return {
      data: {
        retrieval_status: 'timeout',
        task: await getTaskOutputData(completedTask),
        ...supportMetadata,
      },
    }
  }

  markTaskNotified(input.task_id, context)
  return {
    data: {
      retrieval_status: 'success',
      task: await getTaskOutputData(completedTask),
      ...supportMetadata,
    },
  }
}
