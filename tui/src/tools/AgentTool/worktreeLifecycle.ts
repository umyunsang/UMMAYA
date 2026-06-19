import type { AgentId } from '../../types/ids.js'
import { asAgentId } from '../../types/ids.js'
import { getCwd } from '../../utils/cwd.js'
import { logForDebugging } from '../../utils/debug.js'
import { writeAgentMetadata } from '../../utils/sessionStorage.js'
import {
  createAgentWorktree,
  hasWorktreeChanges,
  removeAgentWorktree,
} from '../../utils/worktree.js'
import { buildWorktreeNotice } from './forkSubagent.js'
import { createUserMessage } from '../../utils/messages.js'
import type { Message as MessageType } from 'src/types/message.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import type { WorktreeResult } from './schemas.js'

export type AgentWorktreeInfo = {
  readonly worktreePath: string
  readonly worktreeBranch?: string
  readonly headCommit?: string
  readonly gitRoot?: string
  readonly hookBased?: boolean
}

/** Mutable cleanup guard; cleanup must become idempotent after the first call. */
export type MutableWorktreeState = {
  current: AgentWorktreeInfo | null
}

export async function createWorktreeState({
  isolation,
  earlyAgentId,
}: {
  readonly isolation?: 'worktree' | 'remote'
  readonly earlyAgentId: string
}): Promise<MutableWorktreeState> {
  if (isolation !== 'worktree') return { current: null }
  return {
    current: await createAgentWorktree(`agent-${earlyAgentId.slice(0, 8)}`),
  }
}

export function appendForkWorktreeNotice({
  isForkPath,
  worktreePath,
  promptMessages,
}: {
  readonly isForkPath: boolean
  readonly worktreePath?: string
  readonly promptMessages: MessageType[]
}): void {
  if (!isForkPath || !worktreePath) return
  promptMessages.push(
    createUserMessage({ content: buildWorktreeNotice(getCwd(), worktreePath) }),
  )
}

export function buildWorktreeCleanup({
  state,
  earlyAgentId,
  selectedAgent,
  description,
}: {
  readonly state: MutableWorktreeState
  readonly earlyAgentId: string
  readonly selectedAgent: AgentDefinition
  readonly description: string
}): () => Promise<WorktreeResult> {
  return async () => {
    const worktreeInfo = state.current
    if (!worktreeInfo) return {}
    state.current = null
    const { worktreePath, worktreeBranch, headCommit, gitRoot, hookBased } =
      worktreeInfo
    if (hookBased) {
      logForDebugging(`Hook-based agent worktree kept at: ${worktreePath}`)
      return { worktreePath }
    }
    if (headCommit) {
      const changed = await hasWorktreeChanges(worktreePath, headCommit)
      if (!changed) {
        await removeAgentWorktree(worktreePath, worktreeBranch, gitRoot)
        clearWorktreeMetadata(asAgentId(earlyAgentId), selectedAgent, description)
        return {}
      }
    }
    logForDebugging(`Agent worktree has changes, keeping: ${worktreePath}`)
    return { worktreePath, worktreeBranch }
  }
}

function clearWorktreeMetadata(
  agentId: AgentId,
  selectedAgent: AgentDefinition,
  description: string,
): void {
  void writeAgentMetadata(agentId, {
    agentType: selectedAgent.agentType,
    description,
  }).then(
    () => undefined,
    error =>
      logForDebugging(`Failed to clear worktree metadata: ${String(error)}`),
  )
}
