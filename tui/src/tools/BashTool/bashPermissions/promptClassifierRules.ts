import { feature } from 'bun:bundle'
import type { ToolUseContext } from '../../../Tool.js'
import { getCommandSubcommandPrefix } from '../../../utils/bash/commands.js'
import { getCwd } from '../../../utils/cwd.js'
import { AbortError } from '../../../utils/errors.js'
import {
  classifyBashCommand,
  getBashPromptAskDescriptions,
  getBashPromptDenyDescriptions,
  isClassifierPermissionsEnabled,
} from '../../../utils/permissions/bashClassifier.js'
import type { PermissionResult } from '../../../utils/permissions/PermissionResult.js'
import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import type { PermissionUpdate } from '../../../utils/permissions/PermissionUpdateSchema.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import {
  buildPendingClassifierCheck,
  logClassifierResultForAnts,
} from './classifierChecks.js'
import {
  suggestionForExactCommand,
  suggestionForPrefix,
} from './prefixSuggestions.js'
import type { CommandPrefixResolver } from './types.js'

export async function checkPromptClassifierRules(
  input: BashToolInput,
  context: ToolUseContext,
  getCommandSubcommandPrefixFn: CommandPrefixResolver,
): Promise<PermissionResult | null> {
  const appState = context.getAppState()
  if (
    !isClassifierPermissionsEnabled() ||
    (feature('TRANSCRIPT_CLASSIFIER') &&
      appState.toolPermissionContext.mode === 'auto')
  ) {
    return null
  }

  const denyDescriptions = getBashPromptDenyDescriptions(
    appState.toolPermissionContext,
  )
  const askDescriptions = getBashPromptAskDescriptions(
    appState.toolPermissionContext,
  )
  const hasDeny = denyDescriptions.length > 0
  const hasAsk = askDescriptions.length > 0
  if (!hasDeny && !hasAsk) return null

  const [denyResult, askResult] = await Promise.all([
    hasDeny
      ? classifyBashCommand(
          input.command,
          getCwd(),
          denyDescriptions,
          'deny',
          context.abortController.signal,
          context.options.isNonInteractiveSession,
        )
      : null,
    hasAsk
      ? classifyBashCommand(
          input.command,
          getCwd(),
          askDescriptions,
          'ask',
          context.abortController.signal,
          context.options.isNonInteractiveSession,
        )
      : null,
  ])
  if (context.abortController.signal.aborted) throw new AbortError()

  if (denyResult) {
    logClassifierResultForAnts(input.command, 'deny', denyDescriptions, denyResult)
  }
  if (askResult) {
    logClassifierResultForAnts(input.command, 'ask', askDescriptions, askResult)
  }
  if (denyResult?.matches && denyResult.confidence === 'high') {
    return {
      behavior: 'deny',
      message: `Denied by Bash prompt rule: "${denyResult.matchedDescription}"`,
      decisionReason: {
        type: 'other',
        reason: `Denied by Bash prompt rule: "${denyResult.matchedDescription}"`,
      },
    }
  }
  if (askResult?.matches && askResult.confidence === 'high') {
    let suggestions: PermissionUpdate[]
    if (getCommandSubcommandPrefixFn === getCommandSubcommandPrefix) {
      suggestions = suggestionForExactCommand(input.command)
    } else {
      const commandPrefixResult = await getCommandSubcommandPrefixFn(
        input.command,
        context.abortController.signal,
        context.options.isNonInteractiveSession,
      )
      if (context.abortController.signal.aborted) throw new AbortError()
      suggestions = commandPrefixResult?.commandPrefix
        ? suggestionForPrefix(commandPrefixResult.commandPrefix)
        : suggestionForExactCommand(input.command)
    }
    return {
      behavior: 'ask',
      message: createPermissionRequestMessage(BASH_TOOL_NAME),
      decisionReason: {
        type: 'other',
        reason: `Required by Bash prompt rule: "${askResult.matchedDescription}"`,
      },
      suggestions,
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
  return null
}
