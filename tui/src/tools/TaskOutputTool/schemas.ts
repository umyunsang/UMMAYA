import { z } from 'zod/v4'
import type { TaskType } from '../../Task.js'
import { lazySchema } from '../../utils/lazySchema.js'
import { semanticBoolean } from '../../utils/semanticBoolean.js'

export const inputSchema = lazySchema(() =>
  z.strictObject({
    task_id: z.string().describe('The task ID to get output from'),
    block: semanticBoolean(z.boolean().default(true)).describe(
      'Whether to wait for completion',
    ),
    timeout: z
      .number()
      .min(0)
      .max(600000)
      .default(30000)
      .describe('Max wait time in ms'),
  }),
)

const taskTypeSchema = z.enum([
  'local_bash',
  'local_agent',
  'remote_agent',
  'in_process_teammate',
  'local_workflow',
  'monitor_mcp',
  'dream',
] satisfies readonly TaskType[])

export const taskOutputSchema = z.object({
  task_id: z.string(),
  task_type: taskTypeSchema,
  status: z.string(),
  description: z.string(),
  output: z.string(),
  exitCode: z.number().nullable().optional(),
  error: z.string().optional(),
  prompt: z.string().optional(),
  result: z.string().optional(),
})

export const taskOutputToolOutputSchema = z.object({
  retrieval_status: z.enum(['success', 'timeout', 'not_ready']),
  task: taskOutputSchema.nullable(),
  evidenceJoinKey: z.string(),
  parentToolUseId: z.string(),
  resumeToken: z.string(),
  permissionFlow: z.literal('coordinator_parent_round_trip'),
})

export type InputSchema = ReturnType<typeof inputSchema>
export type TaskOutputToolInput = z.infer<InputSchema>
export type TaskOutputRecord = z.infer<typeof taskOutputSchema>
export type TaskOutputToolOutput = z.infer<typeof taskOutputToolOutputSchema>
