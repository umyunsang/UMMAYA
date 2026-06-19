import type { AssistantMessage } from 'src/types/message.js'
import type { AppState } from '../../state/AppState.js'
import type { ToolPermissionContext, Tools, ToolUseContext } from '../../Tool.js'
import { filterDeniedAgents, getDenyRuleForAgent } from '../../utils/permissions/permissions.js'
import { isAgentSwarmsEnabled } from '../../utils/agentSwarmsEnabled.js'
import { isInProcessTeammate } from '../../utils/teammateContext.js'
import { isTeammate } from '../../utils/teammate.js'
import { setAgentColor } from './agentColorManager.js'
import { buildAgentSupportMetadata } from './orchestrationSupport.js'
import { GENERAL_PURPOSE_AGENT } from './built-in/generalPurposeAgent.js'
import { AGENT_TOOL_NAME } from './constants.js'
import {
  FORK_AGENT,
  isForkSubagentEnabled,
  isInForkChild,
} from './forkSubagent.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import { filterAgentsByMcpRequirements } from './loadAgentsDir.js'
import { mcpServersWithTools, waitForRequiredMcpServers } from './mcpRouting.js'
import { getPrompt } from './prompt.js'
import type {
  AgentToolCallResult,
  AgentToolInput,
  TeammateSpawnedOutput,
} from './schemas.js'
import { isCoordinatorEnvMode } from './runtimeConfig.js'

export type SelectedAgentRoute = {
  readonly selectedAgent: AgentDefinition
  readonly isForkPath: boolean
}

export async function buildAgentToolPrompt({
  agents,
  tools,
  getToolPermissionContext,
  allowedAgentTypes,
}: {
  readonly agents: readonly AgentDefinition[]
  readonly tools: Tools
  readonly getToolPermissionContext: () => Promise<ToolPermissionContext>
  readonly allowedAgentTypes?: readonly string[]
}): Promise<string> {
  const toolPermissionContext = await getToolPermissionContext()
  const filteredAgents = filterDeniedAgents(
    filterAgentsByMcpRequirements(agents, mcpServersWithTools(tools)),
    toolPermissionContext,
    AGENT_TOOL_NAME,
  )
  return getPrompt(filteredAgents, isCoordinatorEnvMode(), allowedAgentTypes)
}

export function resolveTeamName(
  input: Pick<AgentToolInput, 'team_name'>,
  appState: Pick<AppState, 'teamContext'>,
): string | undefined {
  if (!isAgentSwarmsEnabled()) return undefined
  return input.team_name ?? appState.teamContext?.teamName
}

export function assertAgentLaunchAllowed({
  input,
  selectedAgent,
  teamName,
}: {
  readonly input: AgentToolInput
  readonly selectedAgent?: AgentDefinition
  readonly teamName?: string
}): void {
  if (input.team_name && !isAgentSwarmsEnabled()) {
    throw new Error('Agent Teams is not yet available on your plan.')
  }
  if (isTeammate() && teamName && input.name) {
    throw new Error(
      'Teammates cannot spawn other teammates — the team roster is flat. To spawn a subagent instead, omit the `name` parameter.',
    )
  }
  if (isInProcessTeammate() && teamName && input.run_in_background === true) {
    throw new Error(
      'In-process teammates cannot spawn background agents. Use run_in_background=false for synchronous subagents.',
    )
  }
  if (isInProcessTeammate() && teamName && selectedAgent?.background === true) {
    throw new Error(
      `In-process teammates cannot spawn background agents. Agent '${selectedAgent.agentType}' has background: true in its definition.`,
    )
  }
}

export async function launchTeammateIfRequested({
  input,
  teamName,
  model,
  toolUseContext,
  assistantMessage,
}: {
  readonly input: AgentToolInput
  readonly teamName?: string
  readonly model?: string
  readonly toolUseContext: ToolUseContext
  readonly assistantMessage?: AssistantMessage
}): Promise<AgentToolCallResult | undefined> {
  if (!teamName || !input.name) return undefined
  const agentDef = input.subagent_type
    ? toolUseContext.options.agentDefinitions.activeAgents.find(
        agent => agent.agentType === input.subagent_type,
      )
    : undefined
  if (agentDef?.color) {
    setAgentColor(input.subagent_type, agentDef.color)
  }
  const { spawnTeammate } = await import('../shared/spawnMultiAgent.js')
  const result = await spawnTeammate(
    {
      name: input.name,
      prompt: input.prompt,
      description: input.description,
      team_name: teamName,
      use_splitpane: true,
      plan_mode_required: input.mode === 'plan',
      model: model ?? agentDef?.model,
      agent_type: input.subagent_type,
      invokingRequestId: assistantMessage?.requestId,
    },
    toolUseContext,
  )
  const spawnResult: TeammateSpawnedOutput = {
    status: 'teammate_spawned',
    prompt: input.prompt,
    ...result.data,
    ...buildAgentSupportMetadata({
      agentId: result.data.agent_id,
      parentToolUseId: toolUseContext.toolUseId,
    }),
  }
  return { data: spawnResult }
}

export async function resolveSelectedAgentRoute({
  input,
  toolUseContext,
  appState,
}: {
  readonly input: AgentToolInput
  readonly toolUseContext: ToolUseContext
  readonly appState: AppState
}): Promise<SelectedAgentRoute> {
  const effectiveType =
    input.subagent_type ??
    (isForkSubagentEnabled() ? undefined : GENERAL_PURPOSE_AGENT.agentType)
  const isForkPath = effectiveType === undefined
  const selectedAgent = isForkPath
    ? resolveForkAgent(toolUseContext)
    : resolveNamedAgent(effectiveType, toolUseContext, appState)

  await waitForRequiredMcpServers(selectedAgent, toolUseContext, appState)
  if (selectedAgent.color) setAgentColor(selectedAgent.agentType, selectedAgent.color)
  return { selectedAgent, isForkPath }
}

function resolveForkAgent(toolUseContext: ToolUseContext): AgentDefinition {
  if (
    toolUseContext.options.querySource === `agent:builtin:${FORK_AGENT.agentType}` ||
    isInForkChild(toolUseContext.messages)
  ) {
    throw new Error(
      'Fork is not available inside a forked worker. Complete your task directly using your tools.',
    )
  }
  return FORK_AGENT
}

function resolveNamedAgent(
  effectiveType: string,
  toolUseContext: ToolUseContext,
  appState: AppState,
): AgentDefinition {
  const allAgents = toolUseContext.options.agentDefinitions.activeAgents
  const allowedAgentTypes = toolUseContext.options.agentDefinitions.allowedAgentTypes
  const visibleAgents = filterDeniedAgents(
    allowedAgentTypes
      ? allAgents.filter(agent => allowedAgentTypes.includes(agent.agentType))
      : allAgents,
    appState.toolPermissionContext,
    AGENT_TOOL_NAME,
  )
  const found = visibleAgents.find(agent => agent.agentType === effectiveType)
  if (found) return found
  const denied = allAgents.find(agent => agent.agentType === effectiveType)
  if (denied) {
    const denyRule = getDenyRuleForAgent(
      appState.toolPermissionContext,
      AGENT_TOOL_NAME,
      effectiveType,
    )
    throw new Error(
      `Agent type '${effectiveType}' has been denied by permission rule '${AGENT_TOOL_NAME}(${effectiveType})' from ${denyRule?.source ?? 'settings'}.`,
    )
  }
  throw new Error(
    `Agent type '${effectiveType}' not found. Available agents: ${visibleAgents.map(agent => agent.agentType).join(', ')}`,
  )
}
