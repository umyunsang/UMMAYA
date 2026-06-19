import { feature } from 'bun:bundle'
import { getFeatureValue_CACHED_MAY_BE_STALE } from '../../../services/analytics/growthbook.js'
import { logEvent } from '../../../services/analytics/index.js'
import type { ToolPermissionContext } from '../../../Tool.js'
import {
  checkSemantics,
  nodeTypeId,
  parseForSecurityFromAst,
  type ParseForSecurityResult,
} from '../../../utils/bash/ast.js'
import { splitCommand_DEPRECATED } from '../../../utils/bash/commands.js'
import { parseCommandRaw } from '../../../utils/bash/parser.js'
import { tryParseShellCommand } from '../../../utils/bash/shellQuote.js'
import { logForDebugging } from '../../../utils/debug.js'
import { isEnvTruthy } from '../../../utils/envUtils.js'
import type { PermissionDecisionReason } from '../../../utils/permissions/PermissionResult.js'
import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { buildPendingClassifierCheck } from './classifierChecks.js'
import {
  checkEarlyExitDeny,
  checkSemanticsDeny,
} from './subcommandGuards.js'
import type { AstPreflightResult } from './types.js'

const splitCommand = splitCommand_DEPRECATED

export async function prepareAstPermissionState(
  input: BashToolInput,
  toolPermissionContext: ToolPermissionContext,
): Promise<AstPreflightResult> {
  const injectionCheckDisabled = isEnvTruthy(
    process.env.CLAUDE_CODE_DISABLE_COMMAND_INJECTION_CHECK,
  )
  const shadowEnabled = feature('TREE_SITTER_BASH_SHADOW')
    ? getFeatureValue_CACHED_MAY_BE_STALE('tengu_birch_trellis', true)
    : false
  let astRoot = injectionCheckDisabled
    ? null
    : feature('TREE_SITTER_BASH_SHADOW') && !shadowEnabled
      ? null
      : await parseCommandRaw(input.command)
  let astResult: ParseForSecurityResult = astRoot
    ? parseForSecurityFromAst(input.command, astRoot)
    : { kind: 'parse-unavailable' }
  let astSubcommands: string[] | null = null
  let astRedirects
  let astCommands
  let shadowLegacySubs: string[] | undefined

  if (feature('TREE_SITTER_BASH_SHADOW')) {
    const available = astResult.kind !== 'parse-unavailable'
    let tooComplex = false
    let semanticFail = false
    let subsDiffer = false
    if (available) {
      tooComplex = astResult.kind === 'too-complex'
      semanticFail =
        astResult.kind === 'simple' && !checkSemantics(astResult.commands).ok
      const tsSubs =
        astResult.kind === 'simple'
          ? astResult.commands.map(c => c.text)
          : undefined
      const legacySubs = splitCommand(input.command)
      shadowLegacySubs = legacySubs
      subsDiffer =
        tsSubs !== undefined &&
        (tsSubs.length !== legacySubs.length ||
          tsSubs.some((s, i) => s !== legacySubs[i]))
    }
    logEvent('tengu_tree_sitter_shadow', {
      available,
      astTooComplex: tooComplex,
      astSemanticFail: semanticFail,
      subsDiffer,
      injectionCheckDisabled,
      killswitchOff: !shadowEnabled,
      cmdOverLength: input.command.length > 10000,
    })
    astResult = { kind: 'parse-unavailable' }
    astRoot = null
  }

  if (astResult.kind === 'too-complex') {
    const earlyExit = checkEarlyExitDeny(input, toolPermissionContext)
    if (earlyExit !== null) return { kind: 'return', result: earlyExit }
    const decisionReason: PermissionDecisionReason = {
      type: 'other',
      reason: astResult.reason,
    }
    logEvent('tengu_bash_ast_too_complex', {
      nodeTypeId: nodeTypeId(astResult.nodeType),
    })
    return {
      kind: 'return',
      result: {
        behavior: 'ask',
        decisionReason,
        message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
        suggestions: [],
        ...(feature('BASH_CLASSIFIER')
          ? {
              pendingClassifierCheck: buildPendingClassifierCheck(
                input.command,
                toolPermissionContext,
              ),
            }
          : {}),
      },
    }
  }

  if (astResult.kind === 'simple') {
    const sem = checkSemantics(astResult.commands)
    if (!sem.ok) {
      const earlyExit = checkSemanticsDeny(
        input,
        toolPermissionContext,
        astResult.commands,
      )
      if (earlyExit !== null) return { kind: 'return', result: earlyExit }
      const decisionReason: PermissionDecisionReason = {
        type: 'other',
        reason: sem.reason,
      }
      return {
        kind: 'return',
        result: {
          behavior: 'ask',
          decisionReason,
          message: createPermissionRequestMessage(
            BASH_TOOL_NAME,
            decisionReason,
          ),
          suggestions: [],
        },
      }
    }
    astSubcommands = astResult.commands.map(c => c.text)
    astRedirects = astResult.commands.flatMap(c => c.redirects)
    astCommands = astResult.commands
  }

  if (astResult.kind === 'parse-unavailable') {
    logForDebugging(
      'bashToolHasPermission: tree-sitter unavailable, using legacy shell-quote path',
    )
    const parseResult = tryParseShellCommand(input.command)
    if (!parseResult.success) {
      const decisionReason = {
        type: 'other' as const,
        reason: `Command contains malformed syntax that cannot be parsed: ${parseResult.error}`,
      }
      return {
        kind: 'return',
        result: {
          behavior: 'ask',
          decisionReason,
          message: createPermissionRequestMessage(
            BASH_TOOL_NAME,
            decisionReason,
          ),
        },
      }
    }
  }

  return {
    kind: 'continue',
    state: { astRoot, astSubcommands, astRedirects, astCommands, shadowLegacySubs },
  }
}
