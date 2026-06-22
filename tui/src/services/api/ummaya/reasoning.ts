import {
  getInitialReasoningModeSetting,
  providerReasoningPayload,
  resolveKExaoneReasoningPolicy,
  type ResolvedReasoningPolicy,
} from '../../../utils/kExaoneReasoning.js'

export function resolveProviderReasoningPolicy(): ResolvedReasoningPolicy {
  const envResolvedPolicy = resolveKExaoneReasoningPolicy()
  if (
    envResolvedPolicy.source === 'env' ||
    envResolvedPolicy.source === 'legacy-env'
  ) {
    return envResolvedPolicy
  }
  return resolveKExaoneReasoningPolicy({
    userSettingsMode: getInitialReasoningModeSetting(),
  })
}

export function providerReasoningRequestPayload(
  policy: ResolvedReasoningPolicy = resolveProviderReasoningPolicy(),
): {
  readonly chat_template_kwargs: { readonly enable_thinking: boolean }
  readonly parse_reasoning: boolean
  readonly include_reasoning: boolean
} {
  return providerReasoningPayload(policy)
}
