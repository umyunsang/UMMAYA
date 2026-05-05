// SPDX-License-Identifier: Apache-2.0
// Audit-2 P0 · VerifyPrimitive mock-disclaimer unit tests.
//
// Citizen-safety: mock verify results MUST display 🧪 모의 prefix and
// "실제 행정 영향 없는 시연 결과입니다." caveat.
// Live verify results MUST NOT show any mock prefix.

import { test, expect, describe } from 'bun:test'
import { render } from 'ink-testing-library'
import type React from 'react'
import { VerifyPrimitive } from '../VerifyPrimitive.js'
import type { Output } from '../VerifyPrimitive.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderVerify(output: Output, opts: { verbose?: boolean } = {}): string {
  const element = VerifyPrimitive.renderToolResultMessage!(
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

describe('VerifyPrimitive renderToolResultMessage — mock disclaimer', () => {
  test('mock verify (ok=true, _mode="mock" in result) shows 🧪 모의 prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        family: 'gongdong_injeungseo',
        status: 'verified',
        identity_label: '테스트 사용자',
        korea_tier: 'IA2',
        policy_authority: 'KISA',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.kisa.or.kr/v1/verify',
        _security_wrapping_pattern: 'OID4VP + DPoP',
        _policy_authority: 'https://www.kisa.or.kr/policy',
        _international_reference: 'Singapore APEX',
      },
    } as unknown as Output

    const frame = renderVerify(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('실제 행정 영향 없는 시연 결과입니다')
    expect(frame).toContain('인증 완료')
  })

  test('mock verify (pending status) shows 🧪 모의 인증 처리 중', () => {
    const output: Output = {
      ok: true,
      result: {
        family: 'mobile_id',
        status: 'pending',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.mois.go.kr/v1/mobile-id/verify',
        _security_wrapping_pattern: 'mDL ISO/IEC 18013-5',
        _policy_authority: 'https://www.mois.go.kr/policy',
        _international_reference: 'EU EUDI Wallet',
      },
    } as unknown as Output

    const frame = renderVerify(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('인증 처리 중')
  })

  test('mock verify shows actual endpoint footer when present', () => {
    const output: Output = {
      ok: true,
      result: {
        family: 'ganpyeon_injeung',
        status: 'verified',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.mois.go.kr/v1/verify/simple',
        _security_wrapping_pattern: 'OAuth2.1',
        _policy_authority: 'https://www.mois.go.kr/policy',
        _international_reference: 'UK GOV.UK One Login',
      },
    } as unknown as Output

    const frame = renderVerify(output)
    expect(frame).toContain('실제 엔드포인트 (운영 시):')
    expect(frame).toContain('https://api.mois.go.kr/v1/verify/simple')
  })
})

// ---------------------------------------------------------------------------
// Live path — NO mock disclaimer
// ---------------------------------------------------------------------------

describe('VerifyPrimitive renderToolResultMessage — live path (no mock disclaimer)', () => {
  test('live verify (no _mode field) shows 인증 완료 without 🧪 prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        family: 'gongdong_injeungseo',
        status: 'verified',
        identity_label: '실제 사용자',
        policy_authority: 'KISA',
      },
    } as unknown as Output

    const frame = renderVerify(output)
    expect(frame).toContain('검증 결과')
    expect(frame).toContain('인증 완료')
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('시연 결과')
  })

  test('live verify with _mode="live" does NOT show mock disclaimer', () => {
    const output: Output = {
      ok: true,
      result: {
        family: 'gongdong_injeungseo',
        status: 'verified',
        _mode: 'live',
      },
    } as unknown as Output

    const frame = renderVerify(output)
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('시연 결과')
  })
})

// ---------------------------------------------------------------------------
// Regression guard: mismatch_error path unaffected by mock disclaimer
// ---------------------------------------------------------------------------

describe('VerifyPrimitive renderToolResultMessage — mismatch guard unaffected', () => {
  test('[H1] mismatch_error (ok=false) still renders ❌ 인증 모듈 거부 regardless of mock', () => {
    const output: Output = {
      ok: false,
      error: {
        kind: 'mismatch_error',
        message: "No verify adapter registered for family 'gongdong_injeungseo'.",
      },
    } as unknown as Output

    const frame = renderVerify(output)
    expect(frame).toContain('❌')
    expect(frame).toContain('인증 모듈 거부')
    // mock disclaimer is irrelevant for error path
    expect(frame).not.toContain('인증 완료')
  })
})
