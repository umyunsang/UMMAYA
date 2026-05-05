// SPDX-License-Identifier: Apache-2.0
// Wave-2 G5 (Spec realuse-audit-2026-05-05) — F-alpha-08 regression test.
//
// Asserts that the citizen-facing Ctrl-O / transcript reveal of LLM
// ``thinking`` text redacts internal scaffolding tokens (suffix block name,
// adapter ids, internal field names) before they reach the Markdown
// renderer in AssistantThinkingMessage.

import { describe, test, expect } from 'bun:test'
import { sanitizeThinking } from '../../../src/components/messages/sanitizeThinking'

describe('sanitizeThinking', () => {
  test('redacts available_adapters block name', () => {
    const out = sanitizeThinking('available_adapters 에서 후보 어댑터를 봅니다')
    expect(out).toContain('⟨내부⟩')
    expect(out).not.toContain('available_adapters')
  })

  test('redacts tool_id field name', () => {
    const out = sanitizeThinking('tool_id 를 골라 lookup 호출')
    expect(out).toContain('⟨내부⟩')
    expect(out).not.toContain('tool_id')
  })

  test('redacts ministry-namespace adapter ids', () => {
    const out = sanitizeThinking(
      'hira_hospital_search 와 kma_current_observation 그리고 koroad_accident_hazard_search',
    )
    expect(out).not.toContain('hira_hospital_search')
    expect(out).not.toContain('kma_current_observation')
    expect(out).not.toContain('koroad_accident_hazard_search')
    // Three distinct ⟨adapter⟩ replacements
    expect((out.match(/⟨adapter⟩/g) ?? []).length).toBe(3)
  })

  test('redacts mock_verify / mock_lookup / mock_submit / mock_subscribe ids', () => {
    const out = sanitizeThinking(
      'mock_verify_module_modid 와 mock_lookup_module_hometax_simplified 와 mock_submit_module_gov24_minwon 와 mock_subscribe_disaster_alert',
    )
    expect(out).not.toContain('mock_verify_module_modid')
    expect(out).not.toContain('mock_lookup_module_hometax_simplified')
    expect(out).not.toContain('mock_submit_module_gov24_minwon')
    expect(out).not.toContain('mock_subscribe_disaster_alert')
    expect((out.match(/⟨adapter⟩/g) ?? []).length).toBe(4)
  })

  test('preserves 5 primitive names (citizen sees them in gutter glyph)', () => {
    const text =
      'lookup, resolve_location, submit, verify, subscribe — 다섯 primitive'
    const out = sanitizeThinking(text)
    expect(out).toContain('lookup')
    expect(out).toContain('resolve_location')
    expect(out).toContain('submit')
    expect(out).toContain('verify')
    expect(out).toContain('subscribe')
  })

  test('preserves general Korean prose unchanged', () => {
    const text = '사용자가 부산 사하구의 현재 날씨를 묻고 있습니다.'
    const out = sanitizeThinking(text)
    expect(out).toBe(text)
  })

  test('handles empty string', () => {
    expect(sanitizeThinking('')).toBe('')
  })

  test('idempotent — applying twice yields same result', () => {
    const text =
      'available_adapters 에서 hira_hospital_search 를 골라 tool_id 로 호출'
    const once = sanitizeThinking(text)
    const twice = sanitizeThinking(once)
    expect(twice).toBe(once)
  })

  test('full F-alpha-08 reproduction — α5b snap-003 leak surface', () => {
    // Verbatim leaked text from
    // specs/realuse-audit-2026-05-05/findings/alpha/snap/alpha5b/
    //   snap-003-after-ctrl-o-collapse.txt:13-19, 41-54
    const leaked =
      '하지만 제공된 도구들을 보면:\n' +
      '  - lookup: 기상예보, 병원검색, 사고데이터 등 외부 API 조회용\n' +
      '  available_adapters 목록을 보면:\n' +
      '  hira_hospital_search - 병원 검색\n' +
      '  kma_current_observation - 현재 날씨\n' +
      '  kma_forecast_fetch - 단기예보\n' +
      '  kma_pre_warning - 기상예비특보\n' +
      '  kma_short_term_forecast - 단기예보\n' +
      '  koroad_accident_hazard_search - 교통사고 위험지역\n' +
      '  이 중 어떤 도구도 광역자치단체 목록을 제공하지 않습니다.\n' +
      '  적절한 tool_id가 있는지 확인해야 합니다.'
    const out = sanitizeThinking(leaked)
    // Internal scaffolding redacted
    expect(out).not.toContain('available_adapters')
    expect(out).not.toContain('tool_id')
    expect(out).not.toContain('hira_hospital_search')
    expect(out).not.toContain('kma_current_observation')
    expect(out).not.toContain('kma_forecast_fetch')
    expect(out).not.toContain('kma_pre_warning')
    expect(out).not.toContain('kma_short_term_forecast')
    expect(out).not.toContain('koroad_accident_hazard_search')
    // Korean prose retained
    expect(out).toContain('병원 검색')
    expect(out).toContain('단기예보')
    expect(out).toContain('교통사고 위험지역')
    // Primitive name retained (citizen sees lookup in ⏺ gutter glyph)
    expect(out).toContain('lookup')
  })
})
