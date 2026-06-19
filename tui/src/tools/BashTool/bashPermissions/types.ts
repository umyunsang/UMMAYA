import type { ToolUseContext } from '../../../Tool.js'
import type { Redirect, SimpleCommand } from '../../../utils/bash/ast.js'
import type { getCommandSubcommandPrefix } from '../../../utils/bash/commands.js'
import { PARSE_ABORTED, type Node } from '../../../utils/bash/parser.js'
import type { PermissionResult } from '../../../utils/permissions/PermissionResult.js'
import type { BashToolInput } from '../schemas.js'

export type CommandPrefixResolver = typeof getCommandSubcommandPrefix

export type PermissionRunner = (
  input: BashToolInput,
  context: ToolUseContext,
  getCommandSubcommandPrefixFn: CommandPrefixResolver,
) => Promise<PermissionResult>

export type BashAstPermissionState = {
  readonly astRoot: Node | null | typeof PARSE_ABORTED
  readonly astSubcommands: string[] | null
  readonly astRedirects?: Redirect[]
  readonly astCommands?: SimpleCommand[]
  readonly shadowLegacySubs?: string[]
}

export type AstPreflightResult =
  | { readonly kind: 'return'; readonly result: PermissionResult }
  | { readonly kind: 'continue'; readonly state: BashAstPermissionState }
