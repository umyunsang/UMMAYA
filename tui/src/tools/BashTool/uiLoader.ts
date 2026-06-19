import { createRequire } from 'node:module'

type BashUIRuntime = Pick<
  typeof import('./UI.js'),
  | 'BackgroundHint'
  | 'renderToolResultMessage'
  | 'renderToolUseErrorMessage'
  | 'renderToolUseMessage'
  | 'renderToolUseProgressMessage'
  | 'renderToolUseQueuedMessage'
>

const requireModule = createRequire(import.meta.url)
let cachedBashUI: BashUIRuntime | undefined

function isBashUIRuntime(value: unknown): value is BashUIRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<Record<keyof BashUIRuntime, unknown>>
  return (
    typeof module.BackgroundHint === 'function' &&
    typeof module.renderToolResultMessage === 'function' &&
    typeof module.renderToolUseErrorMessage === 'function' &&
    typeof module.renderToolUseMessage === 'function' &&
    typeof module.renderToolUseProgressMessage === 'function' &&
    typeof module.renderToolUseQueuedMessage === 'function'
  )
}

export function loadBashUI(): BashUIRuntime {
  if (cachedBashUI !== undefined) return cachedBashUI
  const loaded: unknown = requireModule('./UI.js')
  if (!isBashUIRuntime(loaded)) {
    throw new Error('Bash UI module did not expose the expected renderers')
  }
  cachedBashUI = loaded
  return loaded
}
