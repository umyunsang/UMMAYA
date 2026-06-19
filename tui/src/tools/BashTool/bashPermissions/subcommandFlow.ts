import { feature } from 'bun:bundle'
import type { ToolUseContext } from '../../../Tool.js'
import type { Redirect, SimpleCommand } from '../../../utils/bash/ast.js'
import { getCommandSubcommandPrefix } from '../../../utils/bash/commands.js'
import { getCwd } from '../../../utils/cwd.js'
import { isEnvTruthy } from '../../../utils/envUtils.js'
import { AbortError } from '../../../utils/errors.js'
import type { PermissionResult } from '../../../utils/permissions/PermissionResult.js'
import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import { count } from '../../../utils/array.js'
import { checkPathConstraints } from '../pathValidation.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { buildPendingClassifierCheck } from './classifierChecks.js'
import {
  bashToolCheckPermission,
  checkCommandAndSuggestRules,
} from './permissionChecks.js'
import {
  allowedSubcommandsResult,
  collectSuggestedRuleUpdates,
  deniedSubcommandResult,
  hasLegacyCommandInjection,
} from './subcommandResultHelpers.js'
import type { CommandPrefixResolver } from './types.js'

type ResolveSubcommandPermissionFlowParams = {
  readonly input: BashToolInput
  readonly context: ToolUseContext
  readonly exactMatchResult: PermissionResult
  readonly subcommands: readonly string[]
  readonly astCommandsByIdx: readonly (SimpleCommand | undefined)[]
  readonly astRedirects?: Redirect[]
  readonly astCommands?: SimpleCommand[]
  readonly astSubcommands: readonly string[] | null
  readonly compoundCommandHasCd: boolean
  readonly getCommandSubcommandPrefixFn: CommandPrefixResolver
}

export async function resolveSubcommandPermissionFlow({
  input,
  context,
  exactMatchResult,
  subcommands,
  astCommandsByIdx,
  astRedirects,
  astCommands,
  astSubcommands,
  compoundCommandHasCd,
  getCommandSubcommandPrefixFn,
}: ResolveSubcommandPermissionFlowParams): Promise<PermissionResult> {
  let appState = context.getAppState()
  const subcommandPermissionDecisions = subcommands.map((command, i) =>
    bashToolCheckPermission(
      { command },
      appState.toolPermissionContext,
      compoundCommandHasCd,
      astCommandsByIdx[i],
    ),
  )
  if (subcommandPermissionDecisions.some(_ => _.behavior === 'deny')) {
    return deniedSubcommandResult(input, subcommands, subcommandPermissionDecisions)
  }

  const pathResult = checkPathConstraints(
    input,
    getCwd(),
    appState.toolPermissionContext,
    compoundCommandHasCd,
    astRedirects,
    astCommands,
  )
  if (pathResult.behavior === 'deny') return pathResult
  const askSubresult = subcommandPermissionDecisions.find(
    _ => _.behavior === 'ask',
  )
  const nonAllowCount = count(
    subcommandPermissionDecisions,
    _ => _.behavior !== 'allow',
  )
  if (pathResult.behavior === 'ask' && askSubresult === undefined) {
    return pathResult
  }
  if (askSubresult !== undefined && nonAllowCount === 1) {
    return {
      ...askSubresult,
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
  if (exactMatchResult.behavior === 'allow') return exactMatchResult

  const hasPossibleCommandInjection =
    astSubcommands === null &&
    !isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_COMMAND_INJECTION_CHECK)
      ? await hasLegacyCommandInjection(subcommands)
      : false
  if (
    subcommandPermissionDecisions.every(_ => _.behavior === 'allow') &&
    !hasPossibleCommandInjection
  ) {
    return allowedSubcommandsResult(
      input,
      subcommands,
      subcommandPermissionDecisions,
    )
  }

  let commandSubcommandPrefix: Awaited<
    ReturnType<typeof getCommandSubcommandPrefixFn>
  > = null
  if (getCommandSubcommandPrefixFn !== getCommandSubcommandPrefix) {
    commandSubcommandPrefix = await getCommandSubcommandPrefixFn(
      input.command,
      context.abortController.signal,
      context.options.isNonInteractiveSession,
    )
    if (context.abortController.signal.aborted) throw new AbortError()
  }

  appState = context.getAppState()
  if (subcommands.length === 1) {
    const onlySubcommand = subcommands[0]
    if (onlySubcommand === undefined) {
      return {
        behavior: 'deny',
        message: `Permission to use ${BASH_TOOL_NAME} with command ${input.command} has been denied.`,
      }
    }
    const result = await checkCommandAndSuggestRules(
      { command: onlySubcommand },
      appState.toolPermissionContext,
      commandSubcommandPrefix,
      compoundCommandHasCd,
      astSubcommands !== null,
    )
    if (result.behavior === 'ask' || result.behavior === 'passthrough') {
      return {
        ...result,
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
    return result
  }

  const subcommandResults: Map<string, PermissionResult> = new Map()
  for (const subcommand of subcommands) {
    subcommandResults.set(
      subcommand,
      await checkCommandAndSuggestRules(
        { ...input, command: subcommand },
        appState.toolPermissionContext,
        commandSubcommandPrefix?.subcommandPrefixes.get(subcommand),
        compoundCommandHasCd,
        astSubcommands !== null,
      ),
    )
  }
  if (
    subcommands.every(
      subcommand => subcommandResults.get(subcommand)?.behavior === 'allow',
    )
  ) {
    return {
      behavior: 'allow',
      updatedInput: input,
      decisionReason: {
        type: 'subcommandResults',
        reasons: subcommandResults,
      },
    }
  }

  const decisionReason = {
    type: 'subcommandResults' as const,
    reasons: subcommandResults,
  }
  return {
    behavior: askSubresult !== undefined ? 'ask' : 'passthrough',
    message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
    decisionReason,
    suggestions: collectSuggestedRuleUpdates(subcommandResults),
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
