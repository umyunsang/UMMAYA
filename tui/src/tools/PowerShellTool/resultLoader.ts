import { createRequire } from 'node:module'
import type { ToolResultBlockParam } from '@anthropic-ai/sdk/resources/index.mjs'
import type { Out } from './schemas.js'

type PowerShellResultRuntime = {
  readonly mapPowerShellToolResultToBlock: (
    output: Out,
    toolUseID: string,
  ) => ToolResultBlockParam
}

const requireModule = createRequire(import.meta.url)
let cachedRuntime: PowerShellResultRuntime | undefined

function isPowerShellResultRuntime(
  value: unknown,
): value is PowerShellResultRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<Record<keyof PowerShellResultRuntime, unknown>>
  return typeof module.mapPowerShellToolResultToBlock === 'function'
}

export function loadPowerShellResultRuntime(): PowerShellResultRuntime {
  if (cachedRuntime !== undefined) return cachedRuntime
  const loaded: unknown = requireModule('./resultMapping.js')
  if (!isPowerShellResultRuntime(loaded)) {
    throw new Error('PowerShell result module did not expose expected mapper')
  }
  cachedRuntime = loaded
  return loaded
}
