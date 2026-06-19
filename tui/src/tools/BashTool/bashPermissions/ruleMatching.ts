import type { ToolPermissionContext } from '../../../Tool.js'
import {
  extractOutputRedirections,
  splitCommand_DEPRECATED,
} from '../../../utils/bash/commands.js'
import type { PermissionRule } from '../../../utils/permissions/PermissionRule.js'
import { getRuleByContentsForToolName } from '../../../utils/permissions/permissions.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { bashPermissionRule, matchWildcardPattern } from './ruleDelegates.js'
import {
  stripAllLeadingEnvVars,
  stripSafeWrappers,
} from './wrapperStripping.js'

const splitCommand = splitCommand_DEPRECATED

function filterRulesByContentsMatchingInput(
  input: BashToolInput,
  rules: Map<string, PermissionRule>,
  matchMode: 'exact' | 'prefix',
  {
    stripAllEnvVars = false,
    skipCompoundCheck = false,
  }: { stripAllEnvVars?: boolean; skipCompoundCheck?: boolean } = {},
): PermissionRule[] {
  const command = input.command.trim()
  const commandWithoutRedirections =
    extractOutputRedirections(command).commandWithoutRedirections
  const commandsForMatching =
    matchMode === 'exact'
      ? [command, commandWithoutRedirections]
      : [commandWithoutRedirections]
  const commandsToTry = commandsForMatching.flatMap(cmd => {
    const strippedCommand = stripSafeWrappers(cmd)
    return strippedCommand !== cmd ? [cmd, strippedCommand] : [cmd]
  })

  if (stripAllEnvVars) {
    const seen = new Set(commandsToTry)
    let startIdx = 0
    while (startIdx < commandsToTry.length) {
      const endIdx = commandsToTry.length
      for (let i = startIdx; i < endIdx; i++) {
        const cmd = commandsToTry[i]
        if (!cmd) continue
        const envStripped = stripAllLeadingEnvVars(cmd)
        if (!seen.has(envStripped)) {
          commandsToTry.push(envStripped)
          seen.add(envStripped)
        }
        const wrapperStripped = stripSafeWrappers(cmd)
        if (!seen.has(wrapperStripped)) {
          commandsToTry.push(wrapperStripped)
          seen.add(wrapperStripped)
        }
      }
      startIdx = endIdx
    }
  }

  const isCompoundCommand = new Map<string, boolean>()
  if (matchMode === 'prefix' && !skipCompoundCheck) {
    for (const cmd of commandsToTry) {
      if (!isCompoundCommand.has(cmd)) {
        isCompoundCommand.set(cmd, splitCommand(cmd).length > 1)
      }
    }
  }

  return Array.from(rules.entries())
    .filter(([ruleContent]) => {
      const bashRule = bashPermissionRule(ruleContent)
      return commandsToTry.some(cmdToMatch => {
        switch (bashRule.type) {
          case 'exact':
            return bashRule.command === cmdToMatch
          case 'prefix':
            switch (matchMode) {
              case 'exact':
                return bashRule.prefix === cmdToMatch
              case 'prefix': {
                if (isCompoundCommand.get(cmdToMatch)) return false
                if (cmdToMatch === bashRule.prefix) return true
                if (cmdToMatch.startsWith(bashRule.prefix + ' ')) return true
                const xargsPrefix = 'xargs ' + bashRule.prefix
                if (cmdToMatch === xargsPrefix) return true
                return cmdToMatch.startsWith(xargsPrefix + ' ')
              }
            }
            break
          case 'wildcard':
            if (matchMode === 'exact') return false
            if (isCompoundCommand.get(cmdToMatch)) return false
            return matchWildcardPattern(bashRule.pattern, cmdToMatch)
        }
      })
    })
    .map(([, rule]) => rule)
}

export function matchingRulesForInput(
  input: BashToolInput,
  toolPermissionContext: ToolPermissionContext,
  matchMode: 'exact' | 'prefix',
  { skipCompoundCheck = false }: { skipCompoundCheck?: boolean } = {},
) {
  const denyRuleByContents = getRuleByContentsForToolName(
    toolPermissionContext,
    BASH_TOOL_NAME,
    'deny',
  )
  const matchingDenyRules = filterRulesByContentsMatchingInput(
    input,
    denyRuleByContents,
    matchMode,
    { stripAllEnvVars: true, skipCompoundCheck: true },
  )

  const askRuleByContents = getRuleByContentsForToolName(
    toolPermissionContext,
    BASH_TOOL_NAME,
    'ask',
  )
  const matchingAskRules = filterRulesByContentsMatchingInput(
    input,
    askRuleByContents,
    matchMode,
    { stripAllEnvVars: true, skipCompoundCheck: true },
  )

  const allowRuleByContents = getRuleByContentsForToolName(
    toolPermissionContext,
    BASH_TOOL_NAME,
    'allow',
  )
  const matchingAllowRules = filterRulesByContentsMatchingInput(
    input,
    allowRuleByContents,
    matchMode,
    { skipCompoundCheck },
  )

  return { matchingDenyRules, matchingAskRules, matchingAllowRules }
}
