import { logEvent } from '../../../services/analytics/index.js'
import type { PermissionResult } from '../../../utils/permissions/PermissionResult.js'
import type { PermissionRuleValue } from '../../../utils/permissions/PermissionRule.js'
import { extractRules } from '../../../utils/permissions/PermissionUpdate.js'
import type { PermissionUpdate } from '../../../utils/permissions/PermissionUpdateSchema.js'
import { permissionRuleValueToString } from '../../../utils/permissions/permissionRuleParser.js'
import { bashCommandIsSafeAsync_DEPRECATED } from '../bashSecurity.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { MAX_SUGGESTED_RULES_FOR_COMPOUND } from './constants.js'
import { suggestionForExactCommand } from './prefixSuggestions.js'

const bashCommandIsSafeAsync = bashCommandIsSafeAsync_DEPRECATED

export function deniedSubcommandResult(
  input: BashToolInput,
  subcommands: readonly string[],
  subcommandPermissionDecisions: readonly PermissionResult[],
): PermissionResult {
  return {
    behavior: 'deny',
    message: `Permission to use ${BASH_TOOL_NAME} with command ${input.command} has been denied.`,
    decisionReason: {
      type: 'subcommandResults',
      reasons: new Map(
        subcommandPermissionDecisions.map((result, i) => [
          subcommands[i] ?? '',
          result,
        ]),
      ),
    },
  }
}

export function allowedSubcommandsResult(
  input: BashToolInput,
  subcommands: readonly string[],
  subcommandPermissionDecisions: readonly PermissionResult[],
): PermissionResult {
  return {
    behavior: 'allow',
    updatedInput: input,
    decisionReason: {
      type: 'subcommandResults',
      reasons: new Map(
        subcommandPermissionDecisions.map((result, i) => [
          subcommands[i] ?? '',
          result,
        ]),
      ),
    },
  }
}

export async function hasLegacyCommandInjection(
  subcommands: readonly string[],
): Promise<boolean> {
  let divergenceCount = 0
  const onDivergence = () => {
    divergenceCount++
  }
  const results = await Promise.all(
    subcommands.map(c => bashCommandIsSafeAsync(c, onDivergence)),
  )
  if (divergenceCount > 0) {
    logEvent('tengu_tree_sitter_security_divergence', {
      quoteContextDivergence: true,
      count: divergenceCount,
    })
  }
  return results.some(r => r.behavior !== 'passthrough')
}

export function collectSuggestedRuleUpdates(
  subcommandResults: Map<string, PermissionResult>,
): PermissionUpdate[] | undefined {
  const collectedRules: Map<string, PermissionRuleValue> = new Map()
  for (const [subcommand, permissionResult] of subcommandResults) {
    if (
      permissionResult.behavior !== 'ask' &&
      permissionResult.behavior !== 'passthrough'
    ) {
      continue
    }
    const updates =
      'suggestions' in permissionResult ? permissionResult.suggestions : undefined
    const rules = extractRules(updates)
    for (const rule of rules) {
      collectedRules.set(permissionRuleValueToString(rule), rule)
    }
    if (
      permissionResult.behavior === 'ask' &&
      rules.length === 0 &&
      permissionResult.decisionReason?.type !== 'rule'
    ) {
      for (const rule of extractRules(suggestionForExactCommand(subcommand))) {
        collectedRules.set(permissionRuleValueToString(rule), rule)
      }
    }
  }

  const cappedRules = Array.from(collectedRules.values()).slice(
    0,
    MAX_SUGGESTED_RULES_FOR_COMPOUND,
  )
  return cappedRules.length > 0
    ? [
        {
          type: 'addRules',
          rules: cappedRules,
          behavior: 'allow',
          destination: 'localSettings',
        },
      ]
    : undefined
}
