// SPDX-License-Identifier: Apache-2.0
// Audit-5 P0-5 (2026-05-04) — analyzeSwarmActivation unit tests.
//
// Locks the migration-tree A+C union semantics:
//   · Path A — 3+ distinct ministries → activate
//   · Path C — explicit `복잡` / `complex` marker → activate
//   · Single-ministry simple text → no activation
//   · Empty / null input → no activation, no exception

import { describe, expect, it } from 'bun:test'
import { analyzeSwarmActivation } from '../../src/state/swarmActivation.js'

describe('analyzeSwarmActivation — Path A (3+ ministries)', () => {
  it('activates when 3 distinct canonical ministries appear', () => {
    const result = analyzeSwarmActivation(
      '기상청 · KOROAD · NMC 의 데이터를 종합하여 답변드리겠습니다.',
    )
    expect(result.shouldActivate).toBe(true)
    expect(result.trigger).toBe('three-plus-ministries')
    expect(result.mentioned_ministries).toContain('KMA')
    expect(result.mentioned_ministries).toContain('KOROAD')
    expect(result.mentioned_ministries).toContain('NMC')
  })

  it('does NOT activate for 2 ministries even if listed twice', () => {
    const result = analyzeSwarmActivation(
      '기상청과 KMA, KOROAD 정보를 확인했습니다.',
    )
    expect(result.shouldActivate).toBe(false)
    expect(result.trigger).toBe('none')
    // KMA + 기상청 dedup to one label
    expect(new Set(result.mentioned_ministries).size).toBe(2)
  })

  it('dedup is case-insensitive across Korean and English tokens', () => {
    const result = analyzeSwarmActivation('hira 심평원 HIRA')
    expect(result.shouldActivate).toBe(false) // only 1 distinct ministry
    expect(new Set(result.mentioned_ministries)).toEqual(new Set(['HIRA']))
  })
})

describe('analyzeSwarmActivation — Path C (complex tag)', () => {
  it('activates on explicit Korean `복잡` marker', () => {
    const result = analyzeSwarmActivation(
      '이 질의는 복잡한 다부처 협업이 필요합니다.',
    )
    expect(result.shouldActivate).toBe(true)
    expect(result.complexity_tag).toBe('complex')
    expect(result.trigger).toBe('complex-tag')
  })

  it('activates on English `complex` marker', () => {
    const result = analyzeSwarmActivation('This requires a complex plan.')
    expect(result.shouldActivate).toBe(true)
    expect(result.trigger).toBe('complex-tag')
  })

  it('activates on `여러 부처` Korean phrase', () => {
    const result = analyzeSwarmActivation(
      '여러 부처가 협력해야 하는 작업입니다.',
    )
    expect(result.shouldActivate).toBe(true)
    expect(result.trigger).toBe('complex-tag')
  })
})

describe('analyzeSwarmActivation — A + C union (both)', () => {
  it('reports `both` when 3+ ministries AND complex tag fire together', () => {
    const result = analyzeSwarmActivation(
      'KMA · KOROAD · NMC 데이터를 결합한 복잡한 분석입니다.',
    )
    expect(result.shouldActivate).toBe(true)
    expect(result.trigger).toBe('both')
  })
})

describe('analyzeSwarmActivation — no activation', () => {
  it('returns false for empty string', () => {
    expect(analyzeSwarmActivation('').shouldActivate).toBe(false)
  })

  it('returns false for null', () => {
    expect(analyzeSwarmActivation(null).shouldActivate).toBe(false)
  })

  it('returns false for undefined', () => {
    expect(analyzeSwarmActivation(undefined).shouldActivate).toBe(false)
  })

  it('returns false for single-ministry simple text', () => {
    const result = analyzeSwarmActivation('서울 기상청 오늘 날씨 알려드립니다.')
    expect(result.shouldActivate).toBe(false)
    expect(result.complexity_tag).toBe('simple')
    expect(result.trigger).toBe('none')
    expect(result.mentioned_ministries).toEqual(['KMA'])
  })

  it('returns false for irrelevant text with no ministry / no complex tag', () => {
    const result = analyzeSwarmActivation('안녕하세요. 무엇을 도와드릴까요?')
    expect(result.shouldActivate).toBe(false)
    expect(result.mentioned_ministries).toEqual([])
  })
})
