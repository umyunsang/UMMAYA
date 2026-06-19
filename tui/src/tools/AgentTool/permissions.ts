import type { ToolUseContext } from '../../Tool.js'
import type { PermissionResult } from '../../utils/permissions/PermissionResult.js'
import type { AgentToolInput } from './schemas.js'
import { isAntBuild } from './runtimeConfig.js'

const NON_INHERITABLE_PERMISSION_MODES = new Set(['bypassPermissions', 'dontAsk'])

export async function checkAgentToolPermissions(
  input: AgentToolInput,
  context: ToolUseContext,
): Promise<PermissionResult> {
  const appState = context.getAppState()
  const requestedMode = input.mode
  if (
    (requestedMode && NON_INHERITABLE_PERMISSION_MODES.has(requestedMode)) ||
    NON_INHERITABLE_PERMISSION_MODES.has(appState.toolPermissionContext.mode)
  ) {
    return {
      behavior: 'deny',
      message:
        'Agent workers must use the coordinator parent permission round-trip; bypass and dontAsk modes are not inherited by subagents.',
      decisionReason: {
        type: 'asyncAgent',
        reason: 'Subagents cannot inherit bypass or dontAsk permission mode.',
      },
    }
  }

  if (isAntBuild() && appState.toolPermissionContext.mode === 'auto') {
    return {
      behavior: 'passthrough',
      message: 'Agent tool requires permission to spawn sub-agents.',
    }
  }
  return {
    behavior: 'allow',
    updatedInput: input,
  }
}
