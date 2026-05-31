export const REASONING_MODES = [
  'fast',
  'balanced',
  'deep',
  'diagnostic',
  'auto',
] as const

export type ReasoningMode = (typeof REASONING_MODES)[number]

export type ReasoningModeSource =
  | 'env'
  | 'session'
  | 'settings'
  | 'legacy-env'
  | 'default'

export type ResolvedReasoningPolicy = {
  mode: ReasoningMode
  source: ReasoningModeSource
  enableThinking: boolean
  parseReasoning: boolean
  includeReasoning: boolean
  persistThinking: boolean
}

type ReasoningEnv = Record<string, string | undefined>

export function isReasoningMode(value: unknown): value is ReasoningMode {
  return (
    typeof value === 'string' &&
    (REASONING_MODES as readonly string[]).includes(value)
  )
}

export function parseReasoningMode(value: unknown): ReasoningMode | undefined {
  if (value === undefined || value === null || value === '') return undefined
  const normalized = String(value).toLowerCase()
  return isReasoningMode(normalized) ? normalized : undefined
}

export function getReasoningModeEnvOverride(
  env: ReasoningEnv = process.env,
): ReasoningMode | undefined {
  return parseReasoningMode(env.UMMAYA_K_EXAONE_REASONING_MODE)
}

export function getLegacyThinkingEnvMode(
  env: ReasoningEnv = process.env,
): ReasoningMode | undefined {
  const raw = env.UMMAYA_K_EXAONE_THINKING
  if (raw === undefined) return undefined
  const normalized = raw.toLowerCase()
  if (normalized === '1' || normalized === 'true' || normalized === 'yes') {
    return 'deep'
  }
  if (normalized === '0' || normalized === 'false' || normalized === 'no') {
    return 'fast'
  }
  return undefined
}

export function resolveKExaoneReasoningPolicy({
  explicitSessionMode,
  userSettingsMode,
  env = process.env,
}: {
  explicitSessionMode?: ReasoningMode
  userSettingsMode?: ReasoningMode
  env?: ReasoningEnv
} = {}): ResolvedReasoningPolicy {
  const envMode = getReasoningModeEnvOverride(env)
  if (envMode !== undefined) return policyFor(envMode, 'env')
  if (explicitSessionMode !== undefined) {
    return policyFor(explicitSessionMode, 'session')
  }
  if (userSettingsMode !== undefined) {
    return policyFor(userSettingsMode, 'settings')
  }
  const legacyMode = getLegacyThinkingEnvMode(env)
  if (legacyMode !== undefined) return policyFor(legacyMode, 'legacy-env')
  return policyFor('balanced', 'default')
}

export function providerReasoningPayload(
  policy: ResolvedReasoningPolicy,
): {
  chat_template_kwargs: { enable_thinking: boolean }
  parse_reasoning: boolean
  include_reasoning: boolean
} {
  return {
    chat_template_kwargs: { enable_thinking: policy.enableThinking },
    parse_reasoning: policy.parseReasoning,
    include_reasoning: policy.includeReasoning,
  }
}

export function getInitialReasoningModeSetting(): ReasoningMode | undefined {
  return parseReasoningMode(
    // Lazy require would avoid this dependency, but settings already imports
    // this utility only for schema constants. Keep the read side cycle-free by
    // requiring at call time.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    (require('./settings/settings.js') as typeof import('./settings/settings.js'))
      .getInitialSettings().reasoningMode,
  )
}

export function getReasoningModeDescription(mode: ReasoningMode): string {
  switch (mode) {
    case 'fast':
      return 'latency-first answers with deterministic progress painting'
    case 'balanced':
      return 'default production policy with reasoning parsing but no raw trace'
    case 'deep':
      return 'provider thinking enabled and streamed when K-EXAONE emits it'
    case 'diagnostic':
      return 'deep provider thinking for local diagnostic inspection'
    case 'auto':
      return 'adaptive placeholder; currently resolves to the balanced payload'
  }
}

function policyFor(
  mode: ReasoningMode,
  source: ReasoningModeSource,
): ResolvedReasoningPolicy {
  const enableThinking = mode === 'deep' || mode === 'diagnostic'
  return {
    mode,
    source,
    enableThinking,
    parseReasoning: true,
    includeReasoning: enableThinking,
    persistThinking: false,
  }
}
