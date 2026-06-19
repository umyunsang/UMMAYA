import {
  getInitialReasoningModeSetting,
  providerReasoningPayload,
  resolveKExaoneReasoningPolicy,
} from '../../../utils/kExaoneReasoning.js'

export function providerReasoningRequestPayload(): {
  readonly chat_template_kwargs: { readonly enable_thinking: boolean }
  readonly parse_reasoning: boolean
  readonly include_reasoning: boolean
} {
  const envResolvedPolicy = resolveKExaoneReasoningPolicy()
  if (
    envResolvedPolicy.source === 'env' ||
    envResolvedPolicy.source === 'legacy-env'
  ) {
    return providerReasoningPayload(envResolvedPolicy)
  }
  return providerReasoningPayload(
    resolveKExaoneReasoningPolicy({
      userSettingsMode: getInitialReasoningModeSetting(),
    }),
  )
}
