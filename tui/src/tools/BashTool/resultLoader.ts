import { createRequire } from 'node:module'
import type { ToolResultBlockParam } from '@anthropic-ai/sdk/resources/index.mjs'
import type { Out } from './schemas.js'

type BashResultRuntime = {
  readonly mapBashToolResultToBlock: (
    output: Out,
    toolUseID: string,
  ) => ToolResultBlockParam
}

const requireModule = createRequire(import.meta.url)
let cachedRuntime: BashResultRuntime | undefined

function isBashResultRuntime(value: unknown): value is BashResultRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<Record<keyof BashResultRuntime, unknown>>
  return typeof module.mapBashToolResultToBlock === 'function'
}

export function loadBashResultRuntime(): BashResultRuntime {
  if (cachedRuntime !== undefined) return cachedRuntime
  const loaded: unknown = requireModule('./resultMapping.js')
  if (!isBashResultRuntime(loaded)) {
    throw new Error('Bash result module did not expose expected mapper')
  }
  cachedRuntime = loaded
  return loaded
}
