import { createRequire } from 'node:module'
import type { ToolPermissionContext } from '../../Tool.js'

type CwdResetRuntime = {
  readonly resetCwdIfOutsideProject: (
    toolPermissionContext: ToolPermissionContext,
  ) => boolean
}

const requireModule = createRequire(import.meta.url)
let cachedRuntime: CwdResetRuntime | undefined

function isCwdResetRuntime(value: unknown): value is CwdResetRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<Record<keyof CwdResetRuntime, unknown>>
  return typeof module.resetCwdIfOutsideProject === 'function'
}

function loadCwdResetRuntime(): CwdResetRuntime {
  if (cachedRuntime !== undefined) return cachedRuntime
  const loaded: unknown = requireModule('./utils.js')
  if (!isCwdResetRuntime(loaded)) {
    throw new Error('Bash utility module did not expose cwd reset helper')
  }
  cachedRuntime = loaded
  return loaded
}

export function resetShellCwdIfOutsideProject(
  toolPermissionContext: ToolPermissionContext,
): boolean {
  return loadCwdResetRuntime().resetCwdIfOutsideProject(toolPermissionContext)
}
