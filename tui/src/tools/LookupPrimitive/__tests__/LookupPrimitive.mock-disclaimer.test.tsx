// SPDX-License-Identifier: Apache-2.0
// Audit-2 P0 · LookupPrimitive mock-disclaimer unit tests.
//
// Citizen-safety: mock lookup results MUST display 🧪 모의 prefix and
// "실제 행정 영향 없는 시연 결과입니다." caveat.
// Live lookup results MUST NOT show any mock prefix.

import { test, expect, describe } from 'bun:test'
import { render } from 'ink-testing-library'
import type React from 'react'
import { LookupPrimitive } from '../LookupPrimitive.js'
import type { Output } from '../LookupPrimitive.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLookup(output: Output, opts: { verbose?: boolean } = {}): string {
  const element = LookupPrimitive.renderToolResultMessage!(
    output,
    null,
    { verbose: opts.verbose ?? false },
  )
  if (typeof element === 'string') return element
  if (element === null || element === undefined) return ''
  const { lastFrame } = render(element as React.ReactElement)
  return lastFrame() ?? ''
}

// ---------------------------------------------------------------------------
// Mock path — disclaimer required (fetch / record result)
// ---------------------------------------------------------------------------

describe('LookupPrimitive renderToolResultMessage — mock disclaimer', () => {
  test('mock lookup (ok=true, _mode="mock" in result) shows 🧪 모의 prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'mock_lookup_module_hometax_simplified',
        kind: 'record',
        fields: { tax_year: 2025, total_income: 50000000 },
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.hometax.go.kr/v1/lookup/simplified',
        _security_wrapping_pattern: 'OAuth2.1 + mTLS',
        _policy_authority: 'https://www.hometax.go.kr/policy',
        _international_reference: 'Singapore APEX',
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('실제 행정 영향 없는 시연 결과입니다')
  })

  test('mock lookup shows tool_id and count in parentheses', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'mock_hira_hospital_search',
        kind: 'collection',
        items: [
          { name: '모의 병원 A', address: '서울시 강남구' },
          { name: '모의 병원 B', address: '서울시 종로구' },
        ],
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.hira.or.kr/v1/hospital/search',
        _security_wrapping_pattern: 'API Key + HTTPS',
        _policy_authority: 'https://www.hira.or.kr/policy',
        _international_reference: 'EU eHealth',
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('mock_hira_hospital_search')
    expect(frame).toContain('2건')
  })

  test('mock lookup shows actual endpoint footer when present', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'mock_lookup_module_gov24_certificate',
        kind: 'record',
        fields: { certificate_type: '주민등록등본' },
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.gov24.go.kr/v1/certificate',
        _security_wrapping_pattern: 'OAuth2.1',
        _policy_authority: 'https://www.mois.go.kr/policy',
        _international_reference: 'Estonia X-Road',
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('실제 엔드포인트 (운영 시):')
    expect(frame).toContain('https://api.gov24.go.kr/v1/certificate')
  })
})

// ---------------------------------------------------------------------------
// Live path — NO mock disclaimer
// ---------------------------------------------------------------------------

describe('LookupPrimitive renderToolResultMessage — live path (no mock disclaimer)', () => {
  test('live lookup (no _mode field) shows tool_id without 🧪 prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'kma_current_observation',
        kind: 'record',
        fields: { temperature: 18.7, humidity: 65 },
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('kma_current_observation')
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('시연 결과')
  })

  test('live lookup with _mode="live" does NOT show mock disclaimer', () => {
    const output: Output = {
      ok: true,
      result: {
        tool_id: 'koroad_accident_hazard_search',
        kind: 'collection',
        items: [{ location: '서울시 강남구 테헤란로' }],
        _mode: 'live',
      },
    }

    const frame = renderLookup(output)
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('시연 결과')
  })
})

// ---------------------------------------------------------------------------
// Error path preserved
// ---------------------------------------------------------------------------

describe('LookupPrimitive renderToolResultMessage — error path preserved', () => {
  test('ok=false renders error message in red, no mock disclaimer', () => {
    const output: Output = {
      ok: false,
      error: {
        kind: 'tool_not_found',
        message: "어댑터 'unknown_tool'을 찾을 수 없습니다.",
      },
    }

    const frame = renderLookup(output)
    expect(frame).toContain('오류가 발생했습니다')
    expect(frame).toContain("어댑터 'unknown_tool'을 찾을 수 없습니다")
    expect(frame).not.toContain('🧪')
  })
})
