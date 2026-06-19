import { createRequire } from 'node:module'

type SearchReadClassification = {
  readonly isSearch: boolean
  readonly isRead: boolean
  readonly isList: boolean
}

type BashCommandClassificationRuntime = {
  readonly isSearchOrReadBashCommand: (
    command: string,
  ) => SearchReadClassification
  readonly detectBlockedSleepPattern: (command: string) => string | null
}

const requireModule = createRequire(import.meta.url)
let cachedRuntime: BashCommandClassificationRuntime | undefined

function isBashCommandClassificationRuntime(
  value: unknown,
): value is BashCommandClassificationRuntime {
  if (typeof value !== 'object' || value === null) return false
  const module = value as Partial<
    Record<keyof BashCommandClassificationRuntime, unknown>
  >
  return (
    typeof module.isSearchOrReadBashCommand === 'function' &&
    typeof module.detectBlockedSleepPattern === 'function'
  )
}

export function loadBashCommandClassificationRuntime(): BashCommandClassificationRuntime {
  if (cachedRuntime !== undefined) return cachedRuntime
  const loaded: unknown = requireModule('./commandClassification.js')
  if (!isBashCommandClassificationRuntime(loaded)) {
    throw new Error('Bash command classification module shape mismatch')
  }
  cachedRuntime = loaded
  return loaded
}
