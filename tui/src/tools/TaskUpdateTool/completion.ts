import { feature } from 'bun:bundle'
import { getFeatureValue_CACHED_MAY_BE_STALE } from '../../services/analytics/growthbook.js'
import type { ToolUseContext } from '../../Tool.js'
import {
  executeTaskCompletedHooks,
  getTaskCompletedHookMessage,
} from '../../utils/hooks.js'
import { listTasks, type Task, type TaskStatus } from '../../utils/tasks.js'
import { getAgentName, getTeamName } from '../../utils/teammate.js'
import type { TaskUpdateToolInput } from './schemas.js'

export type CompletionStatusUpdate = {
  readonly status?: TaskStatus
}

export async function collectCompletedHookErrors(
  input: TaskUpdateToolInput,
  context: ToolUseContext,
  existingTask: Task,
): Promise<string[]> {
  const blockingErrors: string[] = []
  const generator = executeTaskCompletedHooks(
    input.taskId,
    existingTask.subject,
    existingTask.description,
    getAgentName(),
    getTeamName(),
    undefined,
    context.abortController.signal,
    undefined,
    context,
  )

  for await (const result of generator) {
    if (result.blockingError) {
      blockingErrors.push(getTaskCompletedHookMessage(result.blockingError))
    }
  }
  return blockingErrors
}

export async function needsVerificationNudge(
  taskListId: string,
  context: ToolUseContext,
  updates: CompletionStatusUpdate,
): Promise<boolean> {
  if (
    !feature('VERIFICATION_AGENT') ||
    !getFeatureValue_CACHED_MAY_BE_STALE('tengu_hive_evidence', false) ||
    context.agentId ||
    updates.status !== 'completed'
  ) {
    return false
  }

  const allTasks = await listTasks(taskListId)
  return (
    allTasks.every(task => task.status === 'completed') &&
    allTasks.length >= 3 &&
    !allTasks.some(task => /verif/i.test(task.subject))
  )
}
