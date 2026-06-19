import { createRequire } from 'node:module'
import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import type { PermissionResult } from '../../utils/permissions/PermissionResult.js'
import type { BashToolInput } from './schemas.js'

type BashPermissionRuntime = {
  readonly validateBashInput: (
    input: BashToolInput,
  ) => Promise<ValidationResult>
  readonly isBashReadOnly: (input: BashToolInput) => boolean
  readonly prepareBashPermissionMatcher: (
    input: BashToolInput,
  ) => Promise<(pattern: string) => boolean>
  readonly checkBashPermissions: (
    input: BashToolInput,
    context: ToolUseContext,
  ) => Promise<PermissionResult>
}

const requireModule = createRequire(import.meta.url)
let cachedRuntime: BashPermissionRuntime | undefined

function isBashPermissionRuntime(
  value: unknown,
): value is BashPermissionRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<Record<keyof BashPermissionRuntime, unknown>>
  return (
    typeof module.validateBashInput === 'function' &&
    typeof module.isBashReadOnly === 'function' &&
    typeof module.prepareBashPermissionMatcher === 'function' &&
    typeof module.checkBashPermissions === 'function'
  )
}

export function loadBashPermissionRuntime(): BashPermissionRuntime {
  if (cachedRuntime !== undefined) return cachedRuntime
  const loaded: unknown = requireModule('./permissionClassification.js')
  if (!isBashPermissionRuntime(loaded)) {
    throw new Error('Bash permission module did not expose expected functions')
  }
  cachedRuntime = loaded
  return loaded
}
