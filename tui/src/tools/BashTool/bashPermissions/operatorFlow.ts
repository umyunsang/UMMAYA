import { feature } from 'bun:bundle'
import type { ToolUseContext } from '../../../Tool.js'
import { getCwd } from '../../../utils/cwd.js'
import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import { checkCommandOperatorPermissions } from '../bashCommandHelpers.js'
import { bashCommandIsSafeAsync_DEPRECATED } from '../bashSecurity.js'
import { checkPathConstraints } from '../pathValidation.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { buildPendingClassifierCheck } from './classifierChecks.js'
import {
  commandHasAnyCd,
  isNormalizedCdCommand,
  isNormalizedGitCommand,
} from './normalizedCommands.js'
import type {
  BashAstPermissionState,
  CommandPrefixResolver,
  PermissionRunner,
} from './types.js'

const bashCommandIsSafeAsync = bashCommandIsSafeAsync_DEPRECATED

export async function resolveCommandOperatorPermission(
  input: BashToolInput,
  context: ToolUseContext,
  astState: BashAstPermissionState,
  getCommandSubcommandPrefixFn: CommandPrefixResolver,
  runPermissionCheck: PermissionRunner,
) {
  const commandOperatorResult = await checkCommandOperatorPermissions(
    input,
    (i: BashToolInput) =>
      runPermissionCheck(i, context, getCommandSubcommandPrefixFn),
    { isNormalizedCdCommand, isNormalizedGitCommand },
    astState.astRoot,
  )
  if (commandOperatorResult.behavior === 'passthrough') return null

  if (commandOperatorResult.behavior === 'allow') {
    const safetyResult =
      astState.astSubcommands === null
        ? await bashCommandIsSafeAsync(input.command)
        : null
    if (
      safetyResult !== null &&
      safetyResult.behavior !== 'passthrough' &&
      safetyResult.behavior !== 'allow'
    ) {
      const appState = context.getAppState()
      const reason =
        safetyResult.message ?? 'Command contains patterns that require approval'
      return {
        behavior: 'ask' as const,
        message: createPermissionRequestMessage(BASH_TOOL_NAME, {
          type: 'other',
          reason,
        }),
        decisionReason: { type: 'other' as const, reason },
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

    const appState = context.getAppState()
    const pathResult = checkPathConstraints(
      input,
      getCwd(),
      appState.toolPermissionContext,
      commandHasAnyCd(input.command),
      astState.astRedirects,
      astState.astCommands,
    )
    if (pathResult.behavior !== 'passthrough') return pathResult
  }

  if (commandOperatorResult.behavior === 'ask') {
    const appState = context.getAppState()
    return {
      ...commandOperatorResult,
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
  return commandOperatorResult
}
