import { feature } from 'bun:bundle'
import type { ToolUseContext } from '../../../Tool.js'
import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import { bashCommandIsSafeAsync_DEPRECATED, stripSafeHeredocSubstitutions } from '../bashSecurity.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { buildPendingClassifierCheck } from './classifierChecks.js'
import { bashToolCheckExactMatchPermission } from './permissionChecks.js'

const bashCommandIsSafeAsync = bashCommandIsSafeAsync_DEPRECATED

export async function checkLegacyMisparsing(
  input: BashToolInput,
  context: ToolUseContext,
) {
  const originalCommandSafetyResult = await bashCommandIsSafeAsync(input.command)
  if (
    originalCommandSafetyResult.behavior !== 'ask' ||
    !originalCommandSafetyResult.isBashSecurityCheckForMisparsing
  ) {
    return null
  }

  const remainder = stripSafeHeredocSubstitutions(input.command)
  const remainderResult =
    remainder !== null ? await bashCommandIsSafeAsync(remainder) : null
  if (
    remainder !== null &&
    !(
      remainderResult?.behavior === 'ask' &&
      remainderResult.isBashSecurityCheckForMisparsing
    )
  ) {
    return null
  }

  const appState = context.getAppState()
  const exactMatchResult = bashToolCheckExactMatchPermission(
    input,
    appState.toolPermissionContext,
  )
  if (exactMatchResult.behavior === 'allow') return exactMatchResult

  const decisionReason = {
    type: 'other' as const,
    reason: originalCommandSafetyResult.message,
  }
  return {
    behavior: 'ask' as const,
    message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
    decisionReason,
    suggestions: [],
    ...(feature('BASH_CLASSIFIER')
      ? {
          pendingClassifierCheck: buildPendingClassifierCheck(
            input.command,
            appState.toolPermissionContext,
          ),
        }
      : {}),
  }
}
