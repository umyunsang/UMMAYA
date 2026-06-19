import { createRequire } from 'node:module'
import type { CanUseToolFn } from 'src/hooks/useCanUseTool.js'
import type { ToolCallProgress, ToolUseContext } from '../../Tool.js'
import type { AssistantMessage } from '../../types/message.js'
import type { PowerShellProgress } from '../../types/tools.js'
import type { Out, PowerShellToolInput } from './schemas.js'

type PowerShellCallRuntime = {
  readonly callPowerShellTool: (
    input: PowerShellToolInput,
    toolUseContext: ToolUseContext,
    canUseTool?: CanUseToolFn,
    parentMessage?: AssistantMessage,
    onProgress?: ToolCallProgress<PowerShellProgress>,
  ) => Promise<{ readonly data: Out }>
}

const requireModule = createRequire(import.meta.url)
let cachedRuntime: PowerShellCallRuntime | undefined

function isPowerShellCallRuntime(
  value: unknown,
): value is PowerShellCallRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<Record<keyof PowerShellCallRuntime, unknown>>
  return typeof module.callPowerShellTool === 'function'
}

export function loadPowerShellCallRuntime(): PowerShellCallRuntime {
  if (cachedRuntime !== undefined) return cachedRuntime
  const loaded: unknown = requireModule('./call.js')
  if (!isPowerShellCallRuntime(loaded)) {
    throw new Error('PowerShell call module did not expose expected lifecycle')
  }
  cachedRuntime = loaded
  return loaded
}
