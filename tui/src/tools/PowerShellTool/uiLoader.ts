import { createRequire } from 'node:module'

type PowerShellUIRuntime = Pick<
  typeof import('./UI.js'),
  | 'renderToolResultMessage'
  | 'renderToolUseErrorMessage'
  | 'renderToolUseMessage'
  | 'renderToolUseProgressMessage'
  | 'renderToolUseQueuedMessage'
>

const requireModule = createRequire(import.meta.url)
let cachedPowerShellUI: PowerShellUIRuntime | undefined

function isPowerShellUIRuntime(
  value: unknown,
): value is PowerShellUIRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<Record<keyof PowerShellUIRuntime, unknown>>
  return (
    typeof module.renderToolResultMessage === 'function' &&
    typeof module.renderToolUseErrorMessage === 'function' &&
    typeof module.renderToolUseMessage === 'function' &&
    typeof module.renderToolUseProgressMessage === 'function' &&
    typeof module.renderToolUseQueuedMessage === 'function'
  )
}

export function loadPowerShellUI(): PowerShellUIRuntime {
  if (cachedPowerShellUI !== undefined) return cachedPowerShellUI
  const loaded: unknown = requireModule('./UI.js')
  if (!isPowerShellUIRuntime(loaded)) {
    throw new Error('PowerShell UI module did not expose expected renderers')
  }
  cachedPowerShellUI = loaded
  return loaded
}
