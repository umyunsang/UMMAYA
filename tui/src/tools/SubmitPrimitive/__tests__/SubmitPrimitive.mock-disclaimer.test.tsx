// SPDX-License-Identifier: Apache-2.0
// Audit-2 P0 · SubmitPrimitive mock-disclaimer unit tests.
//
// Citizen-safety: mock submit results MUST display 🧪 모의 prefix and
// "실제 행정 영향 없는 시연 결과입니다." caveat.
// Live submit results MUST NOT show any mock prefix.

import { test, expect, describe } from 'bun:test'
import { render } from 'ink-testing-library'
import type React from 'react'
import { SubmitPrimitive } from '../SubmitPrimitive.js'
import type { Output } from '../SubmitPrimitive.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderSubmit(output: Output, opts: { verbose?: boolean } = {}): string {
  const element = SubmitPrimitive.renderToolResultMessage!(
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

describe('SubmitPrimitive renderToolResultMessage — mock disclaimer', () => {
  test('mock submit (ok=true, _mode="mock" in result) shows 🧪 모의 prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        transaction_id: 'hometax-2026-05-04-RX-MOCK1',
        ministry: '국세청',
        status: 'accepted',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.hometax.go.kr/v1/submit',
        _security_wrapping_pattern: 'OAuth2.1 + mTLS',
        _policy_authority: 'https://www.hometax.go.kr/policy',
        _international_reference: 'Singapore APEX',
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('실제 행정 영향 없는 시연 결과입니다')
  })

  test('mock submit shows actual endpoint footer when present', () => {
    const output: Output = {
      ok: true,
      result: {
        transaction_id: 'hometax-2026-05-04-RX-MOCK2',
        status: 'accepted',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.hometax.go.kr/v1/submit',
        _security_wrapping_pattern: 'OAuth2.1 + mTLS',
        _policy_authority: 'https://www.hometax.go.kr/policy',
        _international_reference: 'Singapore APEX',
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('실제 엔드포인트 (운영 시):')
    expect(frame).toContain('https://api.hometax.go.kr/v1/submit')
  })

  test('mock submit still shows receipt_id and status', () => {
    const output: Output = {
      ok: true,
      result: {
        receipt_id: 'gov24-MOCK-2026-05-04',
        status: 'accepted',
        _mode: 'mock',
        _reference_implementation: 'ax-infrastructure-callable-channel',
        _actual_endpoint_when_live: 'https://api.gov24.go.kr/v1/submit',
        _security_wrapping_pattern: 'OAuth2.1',
        _policy_authority: 'https://www.mois.go.kr/policy',
        _international_reference: 'Estonia X-Road',
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('gov24-MOCK-2026-05-04')
  })

  test('mock hometax receipt inside adapter_receipt shows action, agency receipt, and payment state', () => {
    const output: Output = {
      ok: true,
      result: {
        transaction_id: 'urn:kosmos:submit:tax-file',
        status: 'succeeded',
        adapter_receipt: {
          receipt_id: 'hometax-2026-05-06-RX-ABCDE123',
          action_type: 'file_return',
          status: '신고완료',
          preflight_validation: {
            payment: 'separate_submit_required_before_payment',
          },
          _mode: 'mock',
          _reference_implementation: 'ax-infrastructure-callable-channel',
          _actual_endpoint_when_live: 'https://api.hometax.go.kr/v1/submit',
          _security_wrapping_pattern: 'OAuth2.1 + mTLS',
          _policy_authority: 'https://www.hometax.go.kr/policy',
          _international_reference: 'Singapore APEX',
        },
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('처리: 신고 제출')
    expect(frame).toContain('접수 번호: hometax-2026-05-06-RX-ABCDE123')
    expect(frame).toContain('상태: 신고완료')
    expect(frame).toContain('납부 단계: 별도 납부 확인 필요')
    expect(frame).toContain('트랜잭션: urn:kosmos:submit:tax-file')
  })

  test('mock hometax payment reminder is visually distinct from filing submit', () => {
    const output: Output = {
      ok: true,
      result: {
        transaction_id: 'urn:kosmos:submit:tax-reminder',
        status: 'succeeded',
        adapter_receipt: {
          receipt_id: 'hometax-2026-05-06-PAYREM-FEDCBA98',
          action_type: 'create_payment_deadline_reminder',
          status: '납부기한알림생성',
          preflight_validation: {
            payment: 'deadline_reminder_created',
          },
          _mode: 'mock',
          _reference_implementation: 'ax-infrastructure-callable-channel',
          _actual_endpoint_when_live: 'https://api.hometax.go.kr/v1/submit',
          _security_wrapping_pattern: 'OAuth2.1 + mTLS',
          _policy_authority: 'https://www.hometax.go.kr/policy',
          _international_reference: 'Singapore APEX',
        },
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('🧪 모의')
    expect(frame).toContain('처리: 납부기한 알림 생성')
    expect(frame).toContain('접수 번호: hometax-2026-05-06-PAYREM-FEDCBA98')
    expect(frame).toContain('상태: 납부기한알림생성')
    expect(frame).toContain('납부 단계: 납부기한 알림 생성됨')
  })

  test('mock rejected submit is rendered as rejection, not successful receipt', () => {
    const output: Output = {
      ok: true,
      result: {
        transaction_id: 'urn:kosmos:submit:gov24-rejected',
        status: 'rejected',
        adapter_receipt: {
          receipt_id: 'gov24-2026-05-06-REJ-0001',
          status: 'rejected',
          error: 'scope_violation',
          _mode: 'mock',
          _reference_implementation: 'ax-infrastructure-callable-channel',
          _actual_endpoint_when_live: 'https://api.gov24.go.kr/v1/submit',
          _security_wrapping_pattern: 'OAuth2.1 + mTLS',
          _policy_authority: 'https://www.gov.kr/policy',
          _international_reference: 'Estonia X-Road',
        },
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('🧪 모의 제출 반려')
    expect(frame).toContain('접수 번호: gov24-2026-05-06-REJ-0001')
    expect(frame).toContain('상태: 반려됨')
    expect(frame).toContain('반려 사유: scope_violation')
    expect(frame).not.toContain('제출이 접수되었습니다')
  })
})

// ---------------------------------------------------------------------------
// Live path — NO mock disclaimer
// ---------------------------------------------------------------------------

describe('SubmitPrimitive renderToolResultMessage — live path (no mock disclaimer)', () => {
  test('live submit (no _mode field) shows green ✓ without 🧪 prefix', () => {
    const output: Output = {
      ok: true,
      result: {
        transaction_id: 'hometax-2026-05-04-RX-L001',
        ministry: '국세청',
        status: 'accepted',
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('제출이 접수되었습니다')
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('시연 결과')
  })

  test('live submit with _mode="live" does NOT show mock disclaimer', () => {
    const output: Output = {
      ok: true,
      result: {
        transaction_id: 'hometax-live-001',
        status: 'accepted',
        _mode: 'live',
      },
    }

    const frame = renderSubmit(output)
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('시연 결과')
  })

  test('live rejected submit uses rejection copy without mock disclaimer', () => {
    const output: Output = {
      ok: true,
      result: {
        transaction_id: 'gov24-live-rejected',
        ministry: '행정안전부',
        status: 'rejected',
        adapter_receipt: {
          receipt_id: 'gov24-live-RJ-001',
          status: 'rejected',
          reason: 'missing_required_attachment',
        },
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('[행정안전부] 제출이 반려되었습니다')
    expect(frame).toContain('상태: 반려됨')
    expect(frame).toContain('반려 사유: missing_required_attachment')
    expect(frame).not.toContain('🧪')
    expect(frame).not.toContain('제출이 접수되었습니다')
  })
})

// ---------------------------------------------------------------------------
// Error path preserved
// ---------------------------------------------------------------------------

describe('SubmitPrimitive renderToolResultMessage — error path preserved', () => {
  test('ok=false renders error message in red, no mock disclaimer', () => {
    const output: Output = {
      ok: false,
      error: {
        kind: 'permission_denied',
        message: '권한이 거부되었습니다.',
      },
    }

    const frame = renderSubmit(output)
    expect(frame).toContain('권한이 거부되었습니다')
    expect(frame).not.toContain('🧪')
  })
})
