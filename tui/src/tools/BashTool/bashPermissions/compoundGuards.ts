import { createPermissionRequestMessage } from '../../../utils/permissions/permissions.js'
import type { PermissionResult } from '../../../utils/permissions/PermissionResult.js'
import type { BashToolInput } from '../schemas.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import {
  isNormalizedCdCommand,
  isNormalizedGitCommand,
} from './normalizedCommands.js'

export function checkSubcommandDirectoryGuards(
  input: BashToolInput,
  subcommands: readonly string[],
): { result: PermissionResult | null; compoundCommandHasCd: boolean } {
  const cdCommands = subcommands.filter(subCommand =>
    isNormalizedCdCommand(subCommand),
  )
  if (cdCommands.length > 1) {
    const decisionReason = {
      type: 'other' as const,
      reason:
        'Multiple directory changes in one command require approval for clarity',
    }
    return {
      result: {
        behavior: 'ask',
        decisionReason,
        message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
      },
      compoundCommandHasCd: false,
    }
  }

  const compoundCommandHasCd = cdCommands.length > 0
  if (
    compoundCommandHasCd &&
    subcommands.some(cmd => isNormalizedGitCommand(cmd.trim()))
  ) {
    const decisionReason = {
      type: 'other' as const,
      reason:
        'Compound commands with cd and git require approval to prevent bare repository attacks',
    }
    return {
      result: {
        behavior: 'ask',
        decisionReason,
        message: createPermissionRequestMessage(BASH_TOOL_NAME, decisionReason),
      },
      compoundCommandHasCd,
    }
  }
  return { result: null, compoundCommandHasCd }
}
