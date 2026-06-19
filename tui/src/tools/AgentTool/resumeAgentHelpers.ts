import { promises as fsp } from 'fs'
import { getSystemPrompt } from '../../constants/prompts.js'
import type { AppState } from '../../state/AppState.js'
import type { ToolUseContext } from '../../Tool.js'
import type { AgentId } from '../../types/ids.js'
import type { Message as MessageType } from '../../types/message.js'
import { logForDebugging } from '../../utils/debug.js'
import {
  filterOrphanedThinkingOnlyMessages,
  filterUnresolvedToolUses,
  filterWhitespaceOnlyAssistantMessages,
} from '../../utils/messages.js'
import {
  getAgentTranscript,
  readAgentMetadata,
  type AgentMetadata,
} from '../../utils/sessionStorage.js'
import { buildEffectiveSystemPrompt } from '../../utils/systemPrompt.js'
import type { SystemPrompt } from '../../utils/systemPromptType.js'
import type { ContentReplacementState } from '../../utils/toolResultStorage.js'
import { reconstructForSubagentResume } from '../../utils/toolResultStorage.js'
import { GENERAL_PURPOSE_AGENT } from './built-in/generalPurposeAgent.js'
import { FORK_AGENT } from './forkSubagent.js'
import type { AgentDefinition } from './loadAgentsDir.js'

export type ResumeTranscriptState = {
  readonly resumedMessages: MessageType[]
  readonly resumedReplacementState: ContentReplacementState | undefined
  readonly meta: AgentMetadata | null
}

export type ResumeAgentSelection = {
  readonly selectedAgent: AgentDefinition
  readonly isResumedFork: boolean
}

export async function loadResumeTranscriptState(
  agentId: AgentId,
  parentReplacementState: ContentReplacementState | undefined,
): Promise<ResumeTranscriptState> {
  const [transcript, meta] = await Promise.all([
    getAgentTranscript(agentId),
    readAgentMetadata(agentId),
  ])
  if (!transcript) {
    throw new Error(`No transcript found for agent ID: ${agentId}`)
  }

  const resumedMessages = filterWhitespaceOnlyAssistantMessages(
    filterOrphanedThinkingOnlyMessages(
      filterUnresolvedToolUses(transcript.messages),
    ),
  )
  const resumedReplacementState = reconstructForSubagentResume(
    parentReplacementState,
    resumedMessages,
    transcript.contentReplacements,
  )
  return { resumedMessages, resumedReplacementState, meta }
}

export async function resolveResumedWorktreePath(
  worktreePath: string | undefined,
): Promise<string | undefined> {
  if (!worktreePath) return undefined
  const stat = await fsp.stat(worktreePath).then(
    value => value,
    () => undefined,
  )
  if (!stat?.isDirectory()) {
    logForDebugging(
      `Resumed worktree ${worktreePath} no longer exists; falling back to parent cwd`,
    )
    return undefined
  }
  const now = new Date()
  await fsp.utimes(worktreePath, now, now)
  return worktreePath
}

export function selectResumeAgentDefinition({
  agentType,
  activeAgents,
}: {
  agentType: string | undefined
  activeAgents: readonly AgentDefinition[]
}): ResumeAgentSelection {
  if (agentType === FORK_AGENT.agentType) {
    return { selectedAgent: FORK_AGENT, isResumedFork: true }
  }
  const selectedAgent = agentType
    ? (activeAgents.find(agent => agent.agentType === agentType) ??
      GENERAL_PURPOSE_AGENT)
    : GENERAL_PURPOSE_AGENT
  return { selectedAgent, isResumedFork: false }
}

export async function buildForkParentSystemPrompt({
  toolUseContext,
  appState,
}: {
  toolUseContext: ToolUseContext
  appState: AppState
}): Promise<SystemPrompt> {
  if (toolUseContext.renderedSystemPrompt) {
    return toolUseContext.renderedSystemPrompt
  }
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
  const forkParentSystemPrompt = buildEffectiveSystemPrompt({
    mainThreadAgentDefinition,
    toolUseContext,
    customSystemPrompt: toolUseContext.options.customSystemPrompt,
    defaultSystemPrompt,
    appendSystemPrompt: toolUseContext.options.appendSystemPrompt,
  })
  if (!forkParentSystemPrompt) {
    throw new Error(
      'Cannot resume fork agent: unable to reconstruct parent system prompt',
    )
  }
  return forkParentSystemPrompt
}

function additionalWorkingDirectoryPaths(
  toolUseContext: Pick<ToolUseContext, 'getAppState'>,
): string[] {
  return Array.from(
    toolUseContext.getAppState().toolPermissionContext.additionalWorkingDirectories.keys(),
  ).filter(path => typeof path === 'string')
}
