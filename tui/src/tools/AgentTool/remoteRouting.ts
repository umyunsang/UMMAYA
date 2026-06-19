import type { ToolUseContext } from '../../Tool.js'
import {
  checkRemoteAgentEligibility,
  formatPreconditionError,
  getRemoteTaskSessionUrl,
  registerRemoteAgentTask,
} from '../../tasks/RemoteAgentTask/RemoteAgentTask.js'
import { getTaskOutputPath } from '../../utils/task/diskOutput.js'
import { teleportToRemote } from '../../utils/teleport.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import type {
  AgentToolCallResult,
  RemoteLaunchedOutput,
} from './schemas.js'
import { isAntBuild } from './runtimeConfig.js'

export async function launchRemoteAgentIfRequested({
  effectiveIsolation,
  description,
  prompt,
  selectedAgent: _selectedAgent,
  toolUseContext,
}: {
  readonly effectiveIsolation?: 'worktree' | 'remote'
  readonly description: string
  readonly prompt: string
  readonly selectedAgent: AgentDefinition
  readonly toolUseContext: ToolUseContext
}): Promise<AgentToolCallResult | undefined> {
  if (!isAntBuild() || effectiveIsolation !== 'remote') return undefined
  const eligibility = await checkRemoteAgentEligibility()
  if ('errors' in eligibility) {
    const reasons = eligibility.errors.map(formatPreconditionError).join('\n')
    throw new Error(`Cannot launch remote agent:\n${reasons}`)
  }
  let bundleFailHint: string | undefined
  const session = await teleportToRemote({
    initialMessage: prompt,
    description,
    signal: toolUseContext.abortController.signal,
    onBundleFail: message => {
      bundleFailHint = message
    },
  })
  if (!session) throw new Error(bundleFailHint ?? 'Failed to create remote session')
  const { taskId, sessionId } = registerRemoteAgentTask({
    remoteTaskType: 'remote-agent',
    session: { id: session.id, title: session.title || description },
    command: prompt,
    context: toolUseContext,
    toolUseId: toolUseContext.toolUseId,
  })
  const remoteResult: RemoteLaunchedOutput = {
    status: 'remote_launched',
    taskId,
    sessionUrl: getRemoteTaskSessionUrl(sessionId),
    description,
    prompt,
    outputFile: getTaskOutputPath(taskId),
  }
  return { data: remoteResult }
}
