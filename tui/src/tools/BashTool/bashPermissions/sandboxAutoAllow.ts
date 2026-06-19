import type { ToolPermissionContext } from '../../../Tool.js'
import { splitCommand_DEPRECATED } from '../../../utils/bash/commands.js'
import type { PermissionRule } from '../../../utils/permissions/PermissionRule.js'
import type { PermissionResult } from '../../../utils/permissions/PermissionResult.js'
import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { matchingRulesForInput } from './ruleMatching.js'

const splitCommand = splitCommand_DEPRECATED

function denyResult(
  input: BashToolInput,
  rule: PermissionRule,
): PermissionResult {
  return {
    behavior: 'deny',
    message: `Permission to use ${BASH_TOOL_NAME} with command ${input.command.trim()} has been denied.`,
    decisionReason: { type: 'rule', rule },
  }
}

export function checkSandboxAutoAllow(
  input: BashToolInput,
  toolPermissionContext: ToolPermissionContext,
): PermissionResult {
  const command = input.command.trim()
  const { matchingDenyRules, matchingAskRules } = matchingRulesForInput(
    input,
    toolPermissionContext,
    'prefix',
  )
  if (matchingDenyRules[0] !== undefined) {
    return denyResult(input, matchingDenyRules[0])
  }

  const subcommands = splitCommand(command)
  if (subcommands.length > 1) {
    let firstAskRule: PermissionRule | undefined
    for (const sub of subcommands) {
      const subResult = matchingRulesForInput(
        { command: sub },
        toolPermissionContext,
        'prefix',
      )
      if (subResult.matchingDenyRules[0] !== undefined) {
        return denyResult(input, subResult.matchingDenyRules[0])
      }
      firstAskRule ??= subResult.matchingAskRules[0]
    }
    if (firstAskRule) {
      return {
        behavior: 'ask',
        message: createPermissionRequestMessage(BASH_TOOL_NAME),
        decisionReason: { type: 'rule', rule: firstAskRule },
      }
    }
  }

  if (matchingAskRules[0] !== undefined) {
    return {
      behavior: 'ask',
      message: createPermissionRequestMessage(BASH_TOOL_NAME),
      decisionReason: { type: 'rule', rule: matchingAskRules[0] },
    }
  }
  return {
    behavior: 'allow',
    updatedInput: input,
    decisionReason: {
      type: 'other',
      reason: 'Auto-allowed with sandbox (autoAllowBashIfSandboxed enabled)',
    },
  }
}
