import type { AssistantMessage, Message as MessageType } from 'src/types/message.js'
import { getQuerySourceForAgent } from 'src/utils/promptCategory.js'
import { enhanceSystemPromptWithEnvDetails, getSystemPrompt } from '../../constants/prompts.js'
import type { ToolUseContext, Tools } from '../../Tool.js'
import { type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS, logEvent } from '../../services/analytics/index.js'
import { createUserMessage } from '../../utils/messages.js'
import { logForDebugging } from '../../utils/debug.js'
import { errorMessage } from '../../utils/errors.js'
import { buildEffectiveSystemPrompt } from '../../utils/systemPrompt.js'
import { asSystemPrompt } from '../../utils/systemPromptType.js'
import { buildForkedMessages } from './forkSubagent.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import { isBuiltInAgent } from './loadAgentsDir.js'
import { runAgent } from './runAgent.js'
import {
  additionalWorkingDirectoryPaths,
  isAntBuild,
} from './runtimeConfig.js'

type RunAgentParams = Parameters<typeof runAgent>[0]

export type PromptSetup = {
  readonly promptMessages: MessageType[]
  readonly override?: RunAgentParams['override']
  readonly forkContextMessages?: MessageType[]
  readonly useExactTools?: true
  readonly querySource: RunAgentParams['querySource']
}

export async function buildAgentPromptSetup({
  prompt,
  selectedAgent,
  toolUseContext,
  assistantMessage,
  resolvedAgentModel,
  isForkPath,
  hasWorktree,
  cwd,
}: {
  readonly prompt: string
  readonly selectedAgent: AgentDefinition
  readonly toolUseContext: ToolUseContext
  readonly assistantMessage?: AssistantMessage
  readonly resolvedAgentModel: string
  readonly isForkPath: boolean
  readonly hasWorktree: boolean
  readonly cwd?: string
}): Promise<PromptSetup> {
  if (isForkPath) {
    const systemPrompt =
      toolUseContext.renderedSystemPrompt ??
      (await buildFallbackParentSystemPrompt(toolUseContext))
    return {
      promptMessages: buildForkedMessages(prompt, assistantMessage),
      override: { systemPrompt },
      forkContextMessages: toolUseContext.messages,
      useExactTools: true,
      querySource:
        toolUseContext.options.querySource ??
        getQuerySourceForAgent(selectedAgent.agentType, isBuiltInAgent(selectedAgent)),
    }
  }

  const enhancedSystemPrompt = await buildSelectedAgentSystemPrompt({
    selectedAgent,
    toolUseContext,
    resolvedAgentModel,
  })
  return {
    promptMessages: [createUserMessage({ content: prompt })],
    override:
      enhancedSystemPrompt && !hasWorktree && !cwd
        ? { systemPrompt: asSystemPrompt(enhancedSystemPrompt) }
        : undefined,
    querySource:
      toolUseContext.options.querySource ??
      getQuerySourceForAgent(selectedAgent.agentType, isBuiltInAgent(selectedAgent)),
  }
}

export function buildRunAgentParams({
  selectedAgent,
  promptSetup,
  toolUseContext,
  canUseTool,
  shouldRunAsync,
  isForkPath,
  model,
  workerTools,
  worktreePath,
  description,
}: {
  readonly selectedAgent: AgentDefinition
  readonly promptSetup: PromptSetup
  readonly toolUseContext: ToolUseContext
  readonly canUseTool: RunAgentParams['canUseTool']
  readonly shouldRunAsync: boolean
  readonly isForkPath: boolean
  readonly model?: string
  readonly workerTools: Tools
  readonly worktreePath?: string
  readonly description: string
}): RunAgentParams {
  return {
    agentDefinition: selectedAgent,
    promptMessages: promptSetup.promptMessages,
    toolUseContext,
    canUseTool,
    isAsync: shouldRunAsync,
    querySource: promptSetup.querySource,
    model: isForkPath ? undefined : model,
    override: promptSetup.override,
    availableTools: isForkPath ? toolUseContext.options.tools : workerTools,
    forkContextMessages: promptSetup.forkContextMessages,
    ...(promptSetup.useExactTools ? { useExactTools: true as const } : {}),
    worktreePath,
    description,
  }
}

async function buildFallbackParentSystemPrompt(
  toolUseContext: ToolUseContext,
): Promise<ReturnType<typeof buildEffectiveSystemPrompt>> {
  const appState = toolUseContext.getAppState()
  const mainThreadAgentDefinition = appState.agent
    ? appState.agentDefinitions.activeAgents.find(
        agent => agent.agentType === appState.agent,
      )
    : undefined
  const defaultSystemPrompt = await getSystemPrompt(
    toolUseContext.options.tools,
    toolUseContext.options.mainLoopModel,
    additionalWorkingDirectoryPaths(toolUseContext),
    toolUseContext.options.mcpClients,
  )
  return buildEffectiveSystemPrompt({
    mainThreadAgentDefinition,
    toolUseContext,
    customSystemPrompt: toolUseContext.options.customSystemPrompt,
    defaultSystemPrompt,
    appendSystemPrompt: toolUseContext.options.appendSystemPrompt,
  })
}

async function buildSelectedAgentSystemPrompt({
  selectedAgent,
  toolUseContext,
  resolvedAgentModel,
}: {
  readonly selectedAgent: AgentDefinition
  readonly toolUseContext: ToolUseContext
  readonly resolvedAgentModel: string
}): Promise<string[] | undefined> {
  try {
    const agentPrompt = selectedAgent.getSystemPrompt({ toolUseContext })
    if (selectedAgent.memory) {
      logEvent('tengu_agent_memory_loaded', {
        ...(isAntBuild()
          ? {
              agent_type:
                selectedAgent.agentType as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
            }
          : {}),
        scope: selectedAgent.memory as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
        source: 'subagent' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
      })
    }
    return enhanceSystemPromptWithEnvDetails(
      [agentPrompt],
      resolvedAgentModel,
      additionalWorkingDirectoryPaths(toolUseContext),
    )
  } catch (error) {
    const promptError =
      error instanceof Error ? error : new Error(errorMessage(error))
    logForDebugging(
      `Failed to get system prompt for agent ${selectedAgent.agentType}: ${errorMessage(promptError)}`,
    )
    return undefined
  }
}
