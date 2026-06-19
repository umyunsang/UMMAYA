import { feature } from 'bun:bundle'
import { z } from 'zod/v4'
import type { AgentToolProgress, ShellProgress } from '../../types/tools.js'
import type { PermissionMode } from '../../types/permissions.js'
import { lazySchema } from '../../utils/lazySchema.js'
import { permissionModeSchema } from '../../utils/permissions/PermissionMode.js'
import { isForkSubagentEnabled } from './forkSubagentGate.js'
import type { AgentSupportMetadata } from './orchestrationSupport.js'
import { agentToolResultSchema, type AgentToolResult } from './agentToolResult.js'
import { isAntBuild, isBackgroundTasksDisabled } from './runtimeConfig.js'

const baseInputSchema = lazySchema(() =>
  z.object({
    description: z.string().describe('A short (3-5 word) description of the task'),
    prompt: z.string().describe('The task for the agent to perform'),
    subagent_type: z
      .string()
      .optional()
      .describe('The type of specialized agent to use for this task'),
    model: z
      .enum(['sonnet', 'opus', 'haiku'])
      .optional()
      .describe(
        "Optional model override for this agent. Takes precedence over the agent definition's model frontmatter. If omitted, uses the agent definition's model, or inherits from the parent.",
      ),
    run_in_background: z
      .boolean()
      .optional()
      .describe(
        'Set to true to run this agent in the background. You will be notified when it completes.',
      ),
  }),
)

const fullInputSchema = lazySchema(() => {
  const multiAgentInputSchema = z.object({
    name: z
      .string()
      .optional()
      .describe(
        'Name for the spawned agent. Makes it addressable via SendMessage({to: name}) while running.',
      ),
    team_name: z
      .string()
      .optional()
      .describe('Team name for spawning. Uses current team context if omitted.'),
    mode: permissionModeSchema()
      .optional()
      .describe('Permission mode for spawned teammate (e.g., "plan" to require plan approval).'),
  })
  return baseInputSchema()
    .merge(multiAgentInputSchema)
    .extend({
      isolation: (isAntBuild()
        ? z.enum(['worktree', 'remote'])
        : z.enum(['worktree'])
      )
        .optional()
        .describe(
          isAntBuild()
            ? 'Isolation mode. "worktree" creates a temporary git worktree so the agent works on an isolated copy of the repo. "remote" launches the agent in a remote CCR environment (always runs in background).'
            : 'Isolation mode. "worktree" creates a temporary git worktree so the agent works on an isolated copy of the repo.',
        ),
      cwd: z
        .string()
        .optional()
        .describe(
          'Absolute path to run the agent in. Overrides the working directory for all filesystem and shell operations within this agent. Mutually exclusive with isolation: "worktree".',
        ),
    })
})

export const inputSchema = () => {
  const schema = feature('KAIROS')
    ? fullInputSchema()
    : fullInputSchema().omit({ cwd: true })

  // Keep the final feature-gated view uncached. Fork availability depends on
  // session state, and memoizing this wrapper lets the first schema access
  // leak field visibility into later accesses in the same process.
  return isBackgroundTasksDisabled || isForkSubagentEnabled()
    ? schema.omit({ run_in_background: true })
    : schema
}

export type InputSchema = ReturnType<typeof inputSchema>

export type AgentToolInput = z.infer<ReturnType<typeof baseInputSchema>> & {
  readonly name?: string
  readonly team_name?: string
  readonly mode?: PermissionMode
  readonly isolation?: 'worktree' | 'remote'
  readonly cwd?: string
}

export const outputSchema = lazySchema(() => {
  const syncOutputSchema = agentToolResultSchema().extend({
    status: z.literal('completed'),
    prompt: z.string(),
    evidenceJoinKey: z.string(),
    parentToolUseId: z.string(),
    resumeToken: z.string(),
    permissionFlow: z.literal('coordinator_parent_round_trip'),
  })
  const asyncOutputSchema = z.object({
    status: z.literal('async_launched'),
    agentId: z.string().describe('The ID of the async agent'),
    description: z.string().describe('The description of the task'),
    prompt: z.string().describe('The prompt for the agent'),
    outputFile: z.string().describe('Path to the output file for checking agent progress'),
    canReadOutputFile: z
      .boolean()
      .optional()
      .describe('Whether the calling agent has Read/Bash tools to check progress'),
    evidenceJoinKey: z.string(),
    parentToolUseId: z.string(),
    resumeToken: z.string(),
    permissionFlow: z.literal('coordinator_parent_round_trip'),
  })
  return z.union([syncOutputSchema, asyncOutputSchema])
})

export type OutputSchema = ReturnType<typeof outputSchema>
export type Progress = AgentToolProgress | ShellProgress

export type AgentToolProgressCallback = (event: {
  readonly toolUseID: string
  readonly data: Progress
}) => void

export type WorktreeResult = {
  readonly worktreePath?: string
  readonly worktreeBranch?: string
}

export type CompletedAgentOutput = AgentToolResult &
  AgentSupportMetadata &
  WorktreeResult & {
    readonly status: 'completed'
    readonly prompt: string
  }

export type AsyncLaunchedOutput = AgentSupportMetadata & {
  readonly isAsync?: true
  readonly status: 'async_launched'
  readonly agentId: string
  readonly description: string
  readonly prompt: string
  readonly outputFile: string
  readonly canReadOutputFile?: boolean
}

export type TeammateSpawnedOutput = AgentSupportMetadata & {
  readonly status: 'teammate_spawned'
  readonly prompt: string
  readonly teammate_id: string
  readonly agent_id: string
  readonly agent_type?: string
  readonly model?: string
  readonly name: string
  readonly color?: string
  readonly tmux_session_name: string
  readonly tmux_window_name: string
  readonly tmux_pane_id: string
  readonly team_name?: string
  readonly is_splitpane?: boolean
  readonly plan_mode_required?: boolean
}

export type RemoteLaunchedOutput = {
  readonly status: 'remote_launched'
  readonly taskId: string
  readonly sessionUrl: string
  readonly description: string
  readonly prompt: string
  readonly outputFile: string
}

export type AgentToolOutput =
  | CompletedAgentOutput
  | AsyncLaunchedOutput
  | TeammateSpawnedOutput
  | RemoteLaunchedOutput

export type AgentToolCallResult = {
  readonly data: AgentToolOutput
}

export type AgentLifecycleMetadata = {
  readonly prompt: string
  readonly resolvedAgentModel: string
  readonly isBuiltInAgent: boolean
  readonly startTime: number
  readonly agentType: string
  readonly isAsync: boolean
}
