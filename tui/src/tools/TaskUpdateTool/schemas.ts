import { z } from 'zod/v4'
import { lazySchema } from '../../utils/lazySchema.js'
import { TaskStatusSchema } from '../../utils/tasks.js'

export const inputSchema = lazySchema(() => {
  const taskUpdateStatusSchema = TaskStatusSchema().or(z.literal('deleted'))

  return z.strictObject({
    taskId: z.string().describe('The ID of the task to update'),
    subject: z.string().optional().describe('New subject for the task'),
    description: z.string().optional().describe('New description for the task'),
    activeForm: z
      .string()
      .optional()
      .describe(
        'Present continuous form shown in spinner when in_progress (e.g., "Running tests")',
      ),
    status: taskUpdateStatusSchema.optional().describe(
      'New status for the task',
    ),
    addBlocks: z
      .array(z.string())
      .optional()
      .describe('Task IDs that this task blocks'),
    addBlockedBy: z
      .array(z.string())
      .optional()
      .describe('Task IDs that block this task'),
    owner: z.string().optional().describe('New owner for the task'),
    metadata: z
      .record(z.string(), z.unknown())
      .optional()
      .describe(
        'Metadata keys to merge into the task. Set a key to null to delete it.',
      ),
  })
})

export const outputSchema = lazySchema(() =>
  z.object({
    success: z.boolean(),
    taskId: z.string(),
    updatedFields: z.array(z.string()),
    error: z.string().optional(),
    statusChange: z
      .object({
        from: z.string(),
        to: z.string(),
      })
      .optional(),
    verificationNudgeNeeded: z.boolean().optional(),
    evidenceJoinKey: z.string(),
    parentToolUseId: z.string(),
    resumeToken: z.string(),
    permissionFlow: z.literal('coordinator_parent_round_trip'),
  }),
)

export type InputSchema = ReturnType<typeof inputSchema>
export type OutputSchema = ReturnType<typeof outputSchema>
export type TaskUpdateToolInput = z.infer<InputSchema>
export type Output = z.infer<OutputSchema>
