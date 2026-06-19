import { splitCommand_DEPRECATED } from '../../../utils/bash/commands.js'
import { tryParseShellCommand } from '../../../utils/bash/shellQuote.js'
import { stripSafeWrappers } from './wrapperStripping.js'

const splitCommand = splitCommand_DEPRECATED

export function isNormalizedGitCommand(command: string): boolean {
  if (command.startsWith('git ') || command === 'git') return true
  const stripped = stripSafeWrappers(command)
  const parsed = tryParseShellCommand(stripped)
  if (parsed.success && parsed.tokens.length > 0) {
    if (parsed.tokens[0] === 'git') return true
    if (parsed.tokens[0] === 'xargs' && parsed.tokens.includes('git')) {
      return true
    }
    return false
  }
  return /^git(?:\s|$)/.test(stripped)
}

export function isNormalizedCdCommand(command: string): boolean {
  const stripped = stripSafeWrappers(command)
  const parsed = tryParseShellCommand(stripped)
  if (parsed.success && parsed.tokens.length > 0) {
    const cmd = parsed.tokens[0]
    return cmd === 'cd' || cmd === 'pushd' || cmd === 'popd'
  }
  return /^(?:cd|pushd|popd)(?:\s|$)/.test(stripped)
}

export function commandHasAnyCd(command: string): boolean {
  return splitCommand(command).some(subcmd => isNormalizedCdCommand(subcmd.trim()))
}
