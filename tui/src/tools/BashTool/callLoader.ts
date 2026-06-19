import { createRequire } from 'node:module'
import type { CanUseToolFn } from 'src/hooks/useCanUseTool.js'
import type { ToolCallProgress, ToolUseContext } from '../../Tool.js'
import type { AssistantMessage } from '../../types/message.js'
import type { BashProgress } from '../../types/tools.js'
import type { BashToolInput, Out } from './schemas.js'

type BashCallRuntime = {
  readonly callBashTool: (
    input: BashToolInput,
    toolUseContext: ToolUseContext,
    canUseTool?: CanUseToolFn,
    parentMessage?: AssistantMessage,
    onProgress?: ToolCallProgress<BashProgress>,
  ) => Promise<{ readonly data: Out }>
}

const requireModule = createRequire(import.meta.url)
let cachedRuntime: BashCallRuntime | undefined

function isBashCallRuntime(value: unknown): value is BashCallRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<Record<keyof BashCallRuntime, unknown>>
  return typeof module.callBashTool === 'function'
}

export function loadBashCallRuntime(): BashCallRuntime {
  if (cachedRuntime !== undefined) return cachedRuntime
  const loaded: unknown = requireModule('./call.js')
  if (!isBashCallRuntime(loaded)) {
    throw new Error('Bash call module did not expose expected lifecycle')
  }
  cachedRuntime = loaded
  return loaded
}
