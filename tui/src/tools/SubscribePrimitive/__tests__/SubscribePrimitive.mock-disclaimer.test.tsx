// SPDX-License-Identifier: Apache-2.0
// Audit-2 P0 · SubscribePrimitive mock-disclaimer unit tests.
//
// Citizen-safety: mock subscribe results MUST display 🧪 모의 prefix and
// "실제 행정 영향 없는 시연 결과입니다." caveat.
// Live subscribe results MUST NOT show any mock prefix.

import { test, expect, describe } from 'bun:test'
import { render } from 'ink-testing-library'
import type React from 'react'
import { SubscribePrimitive } from '../SubscribePrimitive.js'
import type { Output } from '../SubscribePrimitive.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderSubscribe(output: Output, opts: { verbose?: boolean } = {}): string {
  const element = SubscribePrimitive.renderToolResultMessage!(
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
// Mock path — disclaimer required
// ---------------------------------------------------------------------------

describe('SubscribePrimitive renderToolResultMessage — mock disclaimer', () => {
  test('input schema accepts backend lifetime_seconds contract', () => {
    const parsed = SubscribePrimitive.inputSchema.safeParse({
      tool_id: 'mock_rest_pull_tick_v1',
      params: {},
      lifetime_seconds: 300,
    })

    expect(parsed.success).toBe(true)
  })

  test('mock subscribe (ok=true, _mode="mock" in result) shows 🧪 모의 prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        handle_id: 'mock-handle-disaster-001',
        lifetime: 'session',
        kind: 'disaster_alert',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.mois.go.kr/v1/subscribe/disaster',
        _security_wrapping_pattern: 'OAuth2.1 + WebSocket',
        _policy_authority: 'https://www.mois.go.kr/policy',
        _international_reference: 'Japan J-Alert',
      },
    }

    const frame = renderSubscribe(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('실제 행정 영향 없는 시연 결과입니다')
  })

  test('mock subscribe heading changes to 모의 구독 시작', () => {
    const output: Output = {
      ok: true,
      result: {
        handle_id: 'mock-handle-rss-002',
        lifetime: 'short',
        kind: 'rss',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.gov.kr/v1/rss/subscribe',
        _security_wrapping_pattern: 'OAuth2.1',
        _policy_authority: 'https://www.mois.go.kr/policy',
        _international_reference: 'UK GOV.UK One Login',
      },
    }

    const frame = renderSubscribe(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('구독 시작')
    expect(frame).toContain('mock-handle-rss-002')
  })

  test('mock subscribe shows actual endpoint footer when present', () => {
    const output: Output = {
      ok: true,
      result: {
        handle_id: 'mock-handle-003',
        lifetime: 'session',
        kind: 'cbs',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.mois.go.kr/v1/subscribe/cbs',
        _security_wrapping_pattern: 'WebSocket',
        _policy_authority: 'https://www.mois.go.kr/policy',
        _international_reference: 'EU Emergency Alert',
      },
    }

    const frame = renderSubscribe(output)
    expect(frame).toContain('실제 엔드포인트 (운영 시):')
    expect(frame).toContain('https://api.mois.go.kr/v1/subscribe/cbs')
  })
})

// ---------------------------------------------------------------------------
// Live path — NO mock disclaimer
// ---------------------------------------------------------------------------

describe('SubscribePrimitive renderToolResultMessage — live path (no mock disclaimer)', () => {
  test('live subscribe (no _mode field) shows 구독 완료 without 🧪 prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        handle_id: 'live-handle-001',
        lifetime: 'session',
        kind: 'disaster_alert',
      },
    }

    const frame = renderSubscribe(output)
    expect(frame).toContain('구독 완료')
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('시연 결과')
  })

  test('live subscribe with _mode="live" does NOT show mock disclaimer', () => {
    const output: Output = {
      ok: true,
      result: {
        handle_id: 'live-handle-002',
        lifetime: 'session',
        kind: 'rss',
        _mode: 'live',
      },
    }

    const frame = renderSubscribe(output)
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('시연 결과')
  })
})

// ---------------------------------------------------------------------------
// Error path preserved
// ---------------------------------------------------------------------------

describe('SubscribePrimitive renderToolResultMessage — error path preserved', () => {
  test('ok=false renders error without mock disclaimer', () => {
    const output: Output = {
      ok: false,
      error: {
        kind: 'tool_not_found',
        message: '구독 어댑터를 찾을 수 없습니다.',
      },
    }

    const frame = renderSubscribe(output)
    expect(frame).toContain('구독 실패')
    expect(frame).toContain('구독 어댑터를 찾을 수 없습니다')
    expect(frame).not.toContain('🧪')
  })
})
