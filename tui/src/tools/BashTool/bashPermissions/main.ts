import type { ToolUseContext } from '../../../Tool.js'
import {
  getCommandSubcommandPrefix,
  splitCommand_DEPRECATED,
} from '../../../utils/bash/commands.js'
import { getCwd } from '../../../utils/cwd.js'
import { logForDebugging } from '../../../utils/debug.js'
import { isEnvTruthy } from '../../../utils/envUtils.js'
import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import { getPlatform } from '../../../utils/platform.js'
import { SandboxManager } from '../../../utils/sandbox/sandbox-adapter.js'
import { windowsPathToPosixPath } from '../../../utils/windowsPaths.js'
import type { BashToolInput } from '../schemas.js'
import { shouldUseSandbox } from '../shouldUseSandbox.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import { prepareAstPermissionState } from './astPreflight.js'
import { checkSubcommandDirectoryGuards } from './compoundGuards.js'
import { MAX_SUBCOMMANDS_FOR_SECURITY_CHECK } from './constants.js'
import { checkLegacyMisparsing } from './legacyMisparsing.js'
import { resolveCommandOperatorPermission } from './operatorFlow.js'
import { bashToolCheckExactMatchPermission } from './permissionChecks.js'
import { checkPromptClassifierRules } from './promptClassifierRules.js'
import { checkSandboxAutoAllow } from './sandboxAutoAllow.js'
import { resolveSubcommandPermissionFlow } from './subcommandFlow.js'
import { filterCdCwdSubcommands } from './subcommandGuards.js'

const splitCommand = splitCommand_DEPRECATED

export async function bashToolHasPermission(
  input: BashToolInput,
  context: ToolUseContext,
  getCommandSubcommandPrefixFn = getCommandSubcommandPrefix,
) {
  let appState = context.getAppState()
  const astPreflight = await prepareAstPermissionState(
    input,
    appState.toolPermissionContext,
  )
  if (astPreflight.kind === 'return') return astPreflight.result
  const astState = astPreflight.state

  if (
    SandboxManager.isSandboxingEnabled() &&
    SandboxManager.isAutoAllowBashIfSandboxedEnabled() &&
    shouldUseSandbox(input)
  ) {
    const sandboxAutoAllowResult = checkSandboxAutoAllow(
      input,
      appState.toolPermissionContext,
    )
    if (sandboxAutoAllowResult.behavior !== 'passthrough') {
      return sandboxAutoAllowResult
    }
  }

  const exactMatchResult = bashToolCheckExactMatchPermission(
    input,
    appState.toolPermissionContext,
  )
  if (exactMatchResult.behavior === 'deny') return exactMatchResult

  const promptClassifierResult = await checkPromptClassifierRules(
    input,
    context,
    getCommandSubcommandPrefixFn,
  )
  if (promptClassifierResult !== null) return promptClassifierResult

  const operatorResult = await resolveCommandOperatorPermission(
    input,
    context,
    astState,
    getCommandSubcommandPrefixFn,
    bashToolHasPermission,
  )
  if (operatorResult !== null) return operatorResult

  if (
    astState.astSubcommands === null &&
    !isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_COMMAND_INJECTION_CHECK)
  ) {
    const legacyMisparsingResult = await checkLegacyMisparsing(input, context)
    if (legacyMisparsingResult !== null) return legacyMisparsingResult
  }

  const cwd = getCwd()
  const cwdMingw =
    getPlatform() === 'windows' ? windowsPathToPosixPath(cwd) : cwd
  const rawSubcommands =
    astState.astSubcommands ??
    astState.shadowLegacySubs ??
    splitCommand(input.command)
  const { subcommands, astCommandsByIdx } = filterCdCwdSubcommands(
    rawSubcommands,
    astState.astCommands,
    cwd,
    cwdMingw,
  )

  if (
    astState.astSubcommands === null &&
    subcommands.length > MAX_SUBCOMMANDS_FOR_SECURITY_CHECK
  ) {
    logForDebugging(
      `bashPermissions: ${subcommands.length} subcommands exceeds cap (${MAX_SUBCOMMANDS_FOR_SECURITY_CHECK}) — returning ask`,
      { level: 'debug' },
    )
    const decisionReason = {
      type: 'other' as const,
      reason: `Command splits into ${subcommands.length} subcommands, too many to safety-check individually`,
    }
    return {
      behavior: 'ask' as const,
      message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
      decisionReason,
    }
  }

  const directoryGuard = checkSubcommandDirectoryGuards(input, subcommands)
  if (directoryGuard.result !== null) return directoryGuard.result

  appState = context.getAppState()
  return resolveSubcommandPermissionFlow({
    input,
    context,
    exactMatchResult,
    subcommands,
    astCommandsByIdx,
    astRedirects: astState.astRedirects,
    astCommands: astState.astCommands,
    astSubcommands: astState.astSubcommands,
    compoundCommandHasCd: directoryGuard.compoundCommandHasCd,
    getCommandSubcommandPrefixFn,
  })
}
