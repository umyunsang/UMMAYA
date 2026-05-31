import { describe, expect, test } from 'bun:test'
import {
  providerReasoningPayload,
  resolveKExaoneReasoningPolicy,
} from '../../src/utils/kExaoneReasoning.js'

describe('K-EXAONE reasoning policy resolver', () => {
  test('defaults to balanced without exposing raw reasoning', () => {
    const policy = resolveKExaoneReasoningPolicy({ env: {} })

    expect(policy).toMatchObject({
      mode: 'balanced',
      source: 'default',
      enableThinking: false,
      parseReasoning: true,
      includeReasoning: false,
      persistThinking: false,
    })
    expect(providerReasoningPayload(policy)).toEqual({
      chat_template_kwargs: { enable_thinking: false },
      parse_reasoning: true,
      include_reasoning: false,
    })
  })

  test('maps the legacy thinking env flag to deep reasoning', () => {
    const policy = resolveKExaoneReasoningPolicy({
      env: { UMMAYA_K_EXAONE_THINKING: 'true' },
    })

    expect(policy).toMatchObject({
      mode: 'deep',
      source: 'legacy-env',
      enableThinking: true,
      parseReasoning: true,
      includeReasoning: true,
      persistThinking: false,
    })
  })

  test('uses valid new env mode as the hard session override', () => {
    const policy = resolveKExaoneReasoningPolicy({
      explicitSessionMode: 'deep',
      userSettingsMode: 'diagnostic',
      env: { UMMAYA_K_EXAONE_REASONING_MODE: 'fast' },
    })

    expect(policy).toMatchObject({
      mode: 'fast',
      source: 'env',
      enableThinking: false,
      includeReasoning: false,
    })
  })

  test('falls back from auto to the balanced P0 policy', () => {
    const policy = resolveKExaoneReasoningPolicy({
      explicitSessionMode: 'auto',
      env: {},
    })

    expect(policy).toMatchObject({
      mode: 'auto',
      source: 'session',
      enableThinking: false,
      parseReasoning: true,
      includeReasoning: false,
    })
  })
})
