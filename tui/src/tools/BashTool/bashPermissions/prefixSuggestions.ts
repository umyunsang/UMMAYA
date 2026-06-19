import type { PermissionUpdate } from '../../../utils/permissions/PermissionUpdateSchema.js'
import {
  suggestionForExactCommand as sharedSuggestionForExactCommand,
  suggestionForPrefix as sharedSuggestionForPrefix,
} from '../../../utils/permissions/shellRuleMatching.js'
import { BASH_TOOL_NAME } from '../toolName.js'
import {
  ANT_ONLY_SAFE_ENV_VARS,
  BARE_SHELL_PREFIXES,
  ENV_VAR_ASSIGN_RE,
  SAFE_ENV_VARS,
} from './constants.js'

function safeEnvPrefixEnd(tokens: readonly string[]): number | null {
  let i = 0
  while (i < tokens.length) {
    const token = tokens[i]
    if (token === undefined || !ENV_VAR_ASSIGN_RE.test(token)) break
    const varName = token.split('=')[0]
    if (varName === undefined) return null
    const isAntOnlySafe =
      process.env.USER_TYPE === 'ant' && ANT_ONLY_SAFE_ENV_VARS.has(varName)
    if (!SAFE_ENV_VARS.has(varName) && !isAntOnlySafe) return null
    i++
  }
  return i
}

export function getSimpleCommandPrefix(command: string): string | null {
  const tokens = command.trim().split(/\s+/).filter(Boolean)
  if (tokens.length === 0) return null

  const prefixEnd = safeEnvPrefixEnd(tokens)
  if (prefixEnd === null) return null
  const remaining = tokens.slice(prefixEnd)
  if (remaining.length < 2) return null
  const subcmd = remaining[1]
  if (subcmd === undefined) return null
  if (!/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(subcmd)) return null
  return remaining.slice(0, 2).join(' ')
}

export function getFirstWordPrefix(command: string): string | null {
  const tokens = command.trim().split(/\s+/).filter(Boolean)
  const prefixEnd = safeEnvPrefixEnd(tokens)
  if (prefixEnd === null) return null
  const cmd = tokens[prefixEnd]
  if (!cmd) return null
  if (!/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(cmd)) return null
  if (BARE_SHELL_PREFIXES.has(cmd)) return null
  return cmd
}

export function suggestionForExactCommand(command: string): PermissionUpdate[] {
  const heredocPrefix = extractPrefixBeforeHeredoc(command)
  if (heredocPrefix) {
    return sharedSuggestionForPrefix(BASH_TOOL_NAME, heredocPrefix)
  }

  if (command.includes('\n')) {
    const firstLine = command.split('\n')[0]?.trim() ?? ''
    if (firstLine) return sharedSuggestionForPrefix(BASH_TOOL_NAME, firstLine)
  }

  const prefix = getSimpleCommandPrefix(command)
  if (prefix) return sharedSuggestionForPrefix(BASH_TOOL_NAME, prefix)
  return sharedSuggestionForExactCommand(BASH_TOOL_NAME, command)
}

function extractPrefixBeforeHeredoc(command: string): string | null {
  if (!command.includes('<<')) return null
  const idx = command.indexOf('<<')
  if (idx <= 0) return null
  const before = command.substring(0, idx).trim()
  if (!before) return null

  const prefix = getSimpleCommandPrefix(before)
  if (prefix) return prefix

  const tokens = before.split(/\s+/).filter(Boolean)
  const prefixEnd = safeEnvPrefixEnd(tokens)
  if (prefixEnd === null || prefixEnd >= tokens.length) return null
  return tokens.slice(prefixEnd, prefixEnd + 2).join(' ') || null
}

export function suggestionForPrefix(prefix: string): PermissionUpdate[] {
  return sharedSuggestionForPrefix(BASH_TOOL_NAME, prefix)
}
