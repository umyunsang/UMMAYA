import type { ToolPermissionContext } from '../../../Tool.js'
import type { CommandPrefixResult } from '../../../utils/bash/commands.js'
import type { SimpleCommand } from '../../../utils/bash/ast.js'
import { getCwd } from '../../../utils/cwd.js'
import { isEnvTruthy } from '../../../utils/envUtils.js'
import type {
  PermissionDecisionReason,
  PermissionResult,
} from '../../../utils/permissions/PermissionResult.js'
import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import type { BashToolInput } from '../schemas.js'
import { bashCommandIsSafeAsync_DEPRECATED } from '../bashSecurity.js'
import { checkPermissionMode } from '../modeValidation.js'
import { checkPathConstraints } from '../pathValidation.js'
import { checkReadOnlyConstraints } from '../readOnlyValidation.js'
import { checkSedConstraints } from '../sedValidation.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { commandHasAnyCd } from './normalizedCommands.js'
import {
  suggestionForExactCommand,
  suggestionForPrefix,
} from './prefixSuggestions.js'
import { matchingRulesForInput } from './ruleMatching.js'

const bashCommandIsSafeAsync = bashCommandIsSafeAsync_DEPRECATED

export const bashToolCheckExactMatchPermission = (
  input: BashToolInput,
  toolPermissionContext: ToolPermissionContext,
): PermissionResult => {
  const command = input.command.trim()
  const { matchingDenyRules, matchingAskRules, matchingAllowRules } =
    matchingRulesForInput(input, toolPermissionContext, 'exact')

  if (matchingDenyRules[0] !== undefined) {
    return {
      behavior: 'deny',
      message: `Permission to use ${BASH_TOOL_NAME} with command ${command} has been denied.`,
      decisionReason: { type: 'rule', rule: matchingDenyRules[0] },
    }
  }
  if (matchingAskRules[0] !== undefined) {
    return {
      behavior: 'ask',
      message: createPermissionRequestMessage(BASH_TOOL_NAME),
      decisionReason: { type: 'rule', rule: matchingAskRules[0] },
    }
  }
  if (matchingAllowRules[0] !== undefined) {
    return {
      behavior: 'allow',
      updatedInput: input,
      decisionReason: { type: 'rule', rule: matchingAllowRules[0] },
    }
  }

  const decisionReason = {
    type: 'other' as const,
    reason: 'This command requires approval',
  }
  return {
    behavior: 'passthrough',
    message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
    decisionReason,
    suggestions: suggestionForExactCommand(command),
  }
}

export const bashToolCheckPermission = (
  input: BashToolInput,
  toolPermissionContext: ToolPermissionContext,
  compoundCommandHasCd?: boolean,
  astCommand?: SimpleCommand,
): PermissionResult => {
  const command = input.command.trim()
  const exactMatchResult = bashToolCheckExactMatchPermission(
    input,
    toolPermissionContext,
  )
  if (
    exactMatchResult.behavior === 'deny' ||
    exactMatchResult.behavior === 'ask'
  ) {
    return exactMatchResult
  }

  const { matchingDenyRules, matchingAskRules, matchingAllowRules } =
    matchingRulesForInput(input, toolPermissionContext, 'prefix', {
      skipCompoundCheck: astCommand !== undefined,
    })
  if (matchingDenyRules[0] !== undefined) {
    return {
      behavior: 'deny',
      message: `Permission to use ${BASH_TOOL_NAME} with command ${command} has been denied.`,
      decisionReason: { type: 'rule', rule: matchingDenyRules[0] },
    }
  }
  if (matchingAskRules[0] !== undefined) {
    return {
      behavior: 'ask',
      message: createPermissionRequestMessage(BASH_TOOL_NAME),
      decisionReason: { type: 'rule', rule: matchingAskRules[0] },
    }
  }

  const pathResult = checkPathConstraints(
    input,
    getCwd(),
    toolPermissionContext,
    compoundCommandHasCd,
    astCommand?.redirects,
    astCommand ? [astCommand] : undefined,
  )
  if (pathResult.behavior !== 'passthrough') return pathResult
  if (exactMatchResult.behavior === 'allow') return exactMatchResult
  if (matchingAllowRules[0] !== undefined) {
    return {
      behavior: 'allow',
      updatedInput: input,
      decisionReason: { type: 'rule', rule: matchingAllowRules[0] },
    }
  }

  const sedConstraintResult = checkSedConstraints(input, toolPermissionContext)
  if (sedConstraintResult.behavior !== 'passthrough') return sedConstraintResult
  const modeResult = checkPermissionMode(input, toolPermissionContext)
  if (modeResult.behavior !== 'passthrough') return modeResult
  if (checkReadOnlyConstraints(input, commandHasAnyCd(input.command)).behavior === 'allow') {
    return {
      behavior: 'allow',
      updatedInput: input,
      decisionReason: { type: 'other', reason: 'Read-only command is allowed' },
    }
  }

  const decisionReason = {
    type: 'other' as const,
    reason: 'This command requires approval',
  }
  return {
    behavior: 'passthrough',
    message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
    decisionReason,
    suggestions: suggestionForExactCommand(command),
  }
}

export async function checkCommandAndSuggestRules(
  input: BashToolInput,
  toolPermissionContext: ToolPermissionContext,
  commandPrefixResult: CommandPrefixResult | null | undefined,
  compoundCommandHasCd?: boolean,
  astParseSucceeded?: boolean,
): Promise<PermissionResult> {
  const exactMatchResult = bashToolCheckExactMatchPermission(
    input,
    toolPermissionContext,
  )
  if (exactMatchResult.behavior !== 'passthrough') return exactMatchResult

  const permissionResult = bashToolCheckPermission(
    input,
    toolPermissionContext,
    compoundCommandHasCd,
  )
  if (
    permissionResult.behavior === 'deny' ||
    permissionResult.behavior === 'ask'
  ) {
    return permissionResult
  }

  if (
    !astParseSucceeded &&
    !isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_COMMAND_INJECTION_CHECK)
  ) {
    const safetyResult = await bashCommandIsSafeAsync(input.command)
    if (safetyResult.behavior !== 'passthrough') {
      const decisionReason: PermissionDecisionReason = {
        type: 'other',
        reason:
          safetyResult.behavior === 'ask' && safetyResult.message
            ? safetyResult.message
            : 'This command contains patterns that could pose security risks and requires approval',
      }
      return {
        behavior: 'ask',
        message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
        decisionReason,
        suggestions: [],
      }
    }
  }

  if (permissionResult.behavior === 'allow') return permissionResult
  const suggestedUpdates = commandPrefixResult?.commandPrefix
    ? suggestionForPrefix(commandPrefixResult.commandPrefix)
    : suggestionForExactCommand(input.command)
  return { ...permissionResult, suggestions: suggestedUpdates }
}
