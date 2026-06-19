import type { PermissionResult } from '../../utils/permissions/PermissionResult.js'
import type { ParsedPowerShellCommand } from '../../utils/powershell/parser.js'
import { getPipelineSegments } from '../../utils/powershell/parser.js'
import {
  argLeaksValue,
  isAllowlistedPipelineTail,
  isCwdChangingCmdlet,
  isSafeOutputCommand,
  resolveToCanonical,
} from './readOnlyValidation.js'
import { isSymlinkCreatingCommand } from './symlinkModeValidation.js'

const ACCEPT_EDITS_ALLOWED_CMDLETS = new Set([
  'set-content',
  'add-content',
  'remove-item',
  'clear-content',
])

export function isAcceptEditsAllowedCmdlet(name: string): boolean {
  return ACCEPT_EDITS_ALLOWED_CMDLETS.has(resolveToCanonical(name))
}

function checkCompoundGuards(
  segments: ReturnType<typeof getPipelineSegments>,
): PermissionResult | null {
  const totalCommands = segments.reduce(
    (sum, segment) => sum + segment.commands.length,
    0,
  )
  if (totalCommands <= 1) return null

  let hasCdCommand = false
  let hasSymlinkCreate = false
  let hasWriteCommand = false
  for (const segment of segments) {
    for (const cmd of segment.commands) {
      if (cmd.elementType !== 'CommandAst') continue
      if (isCwdChangingCmdlet(cmd.name)) hasCdCommand = true
      if (isSymlinkCreatingCommand(cmd)) hasSymlinkCreate = true
      if (isAcceptEditsAllowedCmdlet(cmd.name)) hasWriteCommand = true
    }
  }

  if (hasCdCommand && hasWriteCommand) {
    return {
      behavior: 'passthrough',
      message:
        'Compound command contains a directory-changing command with a write operation; path validation would use a stale cwd',
    }
  }
  if (hasSymlinkCreate) {
    return {
      behavior: 'passthrough',
      message:
        'Compound command creates a filesystem link; path validation cannot follow just-created links',
    }
  }
  return null
}

function checkCommandAst(
  cmd: ReturnType<typeof getPipelineSegments>[number]['commands'][number],
  command: string,
  nested: boolean,
): PermissionResult | null {
  if (cmd.elementType !== 'CommandAst') {
    return {
      behavior: 'passthrough',
      message: `${nested ? 'Nested expression' : 'Pipeline source'} element (${cmd.elementType}) cannot be statically validated`,
    }
  }
  if (cmd.nameType === 'application') {
    return {
      behavior: 'passthrough',
      message: `${nested ? 'Nested command' : 'Command'} '${cmd.name}' resolved from a path-like name and requires approval`,
    }
  }
  if (isSafeOutputCommand(cmd.name) || isAllowlistedPipelineTail(cmd, command)) {
    return null
  }
  if (!isAcceptEditsAllowedCmdlet(cmd.name)) {
    return {
      behavior: 'passthrough',
      message: `No mode-specific handling for '${cmd.name}' in acceptEdits mode`,
    }
  }
  if (argLeaksValue(cmd.name, cmd)) {
    return {
      behavior: 'passthrough',
      message: `Arguments in '${cmd.name}' cannot be statically validated in acceptEdits mode`,
    }
  }
  return null
}

function checkCommandArguments(
  cmd: ReturnType<typeof getPipelineSegments>[number]['commands'][number],
): PermissionResult | null {
  if (cmd.elementType !== 'CommandAst' || !cmd.elementTypes) return null

  for (let index = 1; index < cmd.elementTypes.length; index++) {
    const elementType = cmd.elementTypes[index]
    if (elementType !== 'StringConstant' && elementType !== 'Parameter') {
      return {
        behavior: 'passthrough',
        message: `Command argument has unvalidatable type (${elementType})`,
      }
    }
    if (elementType !== 'Parameter') continue

    const arg = cmd.args[index - 1] ?? ''
    const colonIdx = arg.indexOf(':')
    if (colonIdx > 0 && /[$(@{[]/.test(arg.slice(colonIdx + 1))) {
      return {
        behavior: 'passthrough',
        message:
          'Colon-bound parameter contains an expression that cannot be statically validated',
      }
    }
  }
  return null
}

export function checkAcceptEditsCommands(
  input: { command: string },
  parsed: ParsedPowerShellCommand,
): PermissionResult {
  const segments = getPipelineSegments(parsed)
  if (segments.length === 0) {
    return {
      behavior: 'passthrough',
      message: 'No commands found to validate for acceptEdits mode',
    }
  }

  const compoundResult = checkCompoundGuards(segments)
  if (compoundResult !== null) return compoundResult

  for (const segment of segments) {
    for (const cmd of segment.commands) {
      const argumentResult = checkCommandArguments(cmd)
      if (argumentResult !== null) return argumentResult
      const commandResult = checkCommandAst(cmd, input.command, false)
      if (commandResult !== null) return commandResult
    }

    for (const cmd of segment.nestedCommands ?? []) {
      const commandResult = checkCommandAst(cmd, input.command, true)
      if (commandResult !== null) return commandResult
    }
  }

  return {
    behavior: 'allow',
    updatedInput: input,
    decisionReason: {
      type: 'mode',
      mode: 'acceptEdits',
    },
  }
}
