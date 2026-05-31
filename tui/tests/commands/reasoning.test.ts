import { describe, expect, test } from 'bun:test'
import {
  executeReasoning,
  isReasoningStatusQuestion,
  showCurrentReasoning,
} from '../../src/commands/reasoning/reasoning.js'

describe('/reasoning command helpers', () => {
  test('reports current default policy without touching permission mode', () => {
    expect(showCurrentReasoning(undefined, {})).toEqual({
      message:
        'Reasoning mode: balanced (source: default) - default production policy with reasoning parsing but no raw trace',
    })
  })

  test('reports env override source in current policy', () => {
    expect(
      showCurrentReasoning('deep', {
        UMMAYA_K_EXAONE_REASONING_MODE: 'fast',
      }),
    ).toEqual({
      message:
        'Reasoning mode: fast (source: env) - latency-first answers with deterministic progress painting',
    })
  })

  test('rejects unknown modes with the valid mode list', () => {
    expect(executeReasoning('maximum')).toEqual({
      message:
        'Invalid argument: maximum. Valid options are: fast, balanced, deep, diagnostic, auto, unset',
    })
  })

  test('detects ordinary Korean status questions about current reasoning mode', () => {
    expect(
      isReasoningStatusQuestion('너 지금 추론 모드가 어떻게 설정돼 있는지 확인해줘'),
    ).toBe(true)
  })

  test('does not intercept slash commands or mutation requests', () => {
    expect(isReasoningStatusQuestion('/reasoning current')).toBe(false)
    expect(isReasoningStatusQuestion('추론 모드 deep으로 바꿔줘')).toBe(false)
  })
})
