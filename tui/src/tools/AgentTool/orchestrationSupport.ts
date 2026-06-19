import type { ToolPermissionContext } from '../../Tool.js'
import type { PermissionMode } from '../../types/permissions.js'

export const COORDINATOR_PERMISSION_FLOW =
  'coordinator_parent_round_trip' as const

export type CoordinatorPermissionFlow = typeof COORDINATOR_PERMISSION_FLOW

export type AgentSupportMetadata = {
  evidenceJoinKey: string
  parentToolUseId: string
  resumeToken: string
  permissionFlow: CoordinatorPermissionFlow
}

const UNKNOWN_PARENT_TOOL_USE_ID = 'parent-tool-use:unknown'

const PROTECTED_WORKER_TOOLS = new Set([
  'document',
  'send',
  'check',
  'workspace_write',
  'workspace_edit',
])

function stableJoinPart(part: string): string {
  const sanitized = part.replace(/[^A-Za-z0-9_.:-]/g, '_')
  return sanitized.length > 0 ? sanitized : 'unknown'
}

export function buildAgentSupportMetadata({
  agentId,
  taskId,
  parentToolUseId,
}: {
  agentId?: string
  taskId?: string
  parentToolUseId?: string
}): AgentSupportMetadata {
  const childId = stableJoinPart(agentId ?? taskId ?? 'unknown')
  const parentId = stableJoinPart(parentToolUseId ?? UNKNOWN_PARENT_TOOL_USE_ID)
  return {
    evidenceJoinKey: `${parentId}:${childId}`,
    parentToolUseId: parentId,
    resumeToken: `resume:${childId}`,
    permissionFlow: COORDINATOR_PERMISSION_FLOW,
  }
}

export function isProtectedWorkerTool(toolName: string): boolean {
  return PROTECTED_WORKER_TOOLS.has(toolName)
}

function workerMode(requestedMode: PermissionMode | undefined): PermissionMode {
  return requestedMode === 'plan' ? 'plan' : 'default'
}

export function buildCoordinatorWorkerPermissionContext(
  parent: ToolPermissionContext,
  requestedMode: PermissionMode | undefined,
): ToolPermissionContext {
  return {
    ...parent,
    mode: workerMode(requestedMode),
    alwaysAllowRules: {},
    isBypassPermissionsModeAvailable: false,
    shouldAvoidPermissionPrompts: false,
    awaitAutomatedChecksBeforeDialog: true,
  }
}
