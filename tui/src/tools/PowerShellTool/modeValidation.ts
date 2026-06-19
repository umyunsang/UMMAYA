/**
 * PowerShell permission mode validation.
 *
 * Checks if commands should be auto-allowed based on the current permission mode.
 * In acceptEdits mode, filesystem-modifying PowerShell cmdlets are auto-allowed.
 * Follows the same patterns as BashTool/modeValidation.ts.
 */

import type { ToolPermissionContext } from '../../Tool.js'
import type { PermissionResult } from '../../utils/permissions/PermissionResult.js'
import type { ParsedPowerShellCommand } from '../../utils/powershell/parser.js'
import { deriveSecurityFlags } from '../../utils/powershell/parser.js'
import { getBypassImmuneShellPermissionResult } from '../BashTool/shellPermissionGauntlet.js'
import { checkAcceptEditsCommands } from './acceptEditsCommandValidation.js'
import { getDestructiveCommandWarning } from './destructiveCommandWarning.js'
import { POWERSHELL_TOOL_NAME } from './toolName.js'

export { isSymlinkCreatingCommand } from './symlinkModeValidation.js'

/**
 * Checks if commands should be handled differently based on the current permission mode.
 *
 * In acceptEdits mode, auto-allows filesystem-modifying PowerShell cmdlets.
 * Uses the AST to resolve aliases before checking the allowlist.
 *
 * @param input - The PowerShell command input
 * @param parsed - The parsed AST of the command
 * @param toolPermissionContext - Context containing mode and permissions
 * @returns
 * - 'allow' if the current mode permits auto-approval
 * - 'passthrough' if no mode-specific handling applies
 */
export function checkPermissionMode(
  input: { command: string },
  parsed: ParsedPowerShellCommand,
  toolPermissionContext: ToolPermissionContext,
): PermissionResult {
  if (toolPermissionContext.mode === 'bypassPermissions') {
    const bypassImmuneResult = getBypassImmuneShellPermissionResult(
      input.command,
      POWERSHELL_TOOL_NAME,
      toolPermissionContext,
      getDestructiveCommandWarning,
    )
    if (bypassImmuneResult !== null) {
      return bypassImmuneResult
    }

    return {
      behavior: 'passthrough',
      message: 'Mode is handled in main permission flow',
    }
  }

  if (toolPermissionContext.mode === 'dontAsk') {
    return {
      behavior: 'passthrough',
      message: 'Mode is handled in main permission flow',
    }
  }

  if (toolPermissionContext.mode !== 'acceptEdits') {
    return {
      behavior: 'passthrough',
      message: 'No mode-specific validation required',
    }
  }

  // acceptEdits mode: check if all commands are filesystem-modifying cmdlets
  if (!parsed.valid) {
    return {
      behavior: 'passthrough',
      message: 'Cannot validate mode for unparsed command',
    }
  }

  // SECURITY: Check for subexpressions, script blocks, or member invocations
  // that could be used to smuggle arbitrary code through acceptEdits mode.
  const securityFlags = deriveSecurityFlags(parsed)
  if (
    securityFlags.hasSubExpressions ||
    securityFlags.hasScriptBlocks ||
    securityFlags.hasMemberInvocations ||
    securityFlags.hasSplatting ||
    securityFlags.hasAssignments ||
    securityFlags.hasStopParsing ||
    securityFlags.hasExpandableStrings
  ) {
    return {
      behavior: 'passthrough',
      message:
        'Command contains subexpressions, script blocks, or member invocations that require approval',
    }
  }

  return checkAcceptEditsCommands(input, parsed)
}
