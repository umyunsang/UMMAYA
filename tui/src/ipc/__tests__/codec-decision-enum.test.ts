// SPDX-License-Identifier: Apache-2.0
/**
 * Decision drift fix tests — codec.ts PermissionResponseFrameSchema.
 *
 * Verifies that the Zod schema for permission_response frames accepts all
 * 5 decision values (synced with backend frame_schema.py:PermissionResponseFrame.decision
 * Literal) and that the receipt_id field is parsed correctly (Gap A fix).
 *
 * Prior state (before fix): only 'granted' | 'denied' were valid — the 3
 * Spec 033 values (allow_once | allow_session | deny) would fail Zod
 * validation and be silently dropped.
 */

import { describe, expect, test } from 'bun:test'
import { decodeFrame } from '../codec'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASE_FIELDS = {
  version: '1.0',
  session_id: 'sess-test',
  correlation_id: 'corr-test',
  role: 'backend',
  ts: '2026-05-04T00:00:00.000Z',
  frame_seq: 0,
  kind: 'permission_response',
  request_id: 'req-abc-123',
}

function makePermissionResponseLine(
  decision: string,
  receipt_id?: string | null,
): string {
  const frame: Record<string, unknown> = {
    ...BASE_FIELDS,
    decision,
  }
  if (receipt_id !== undefined) {
    frame.receipt_id = receipt_id
  }
  return JSON.stringify(frame) + '\n'
}

// ---------------------------------------------------------------------------
// 1. All 5 decision values must be accepted
// ---------------------------------------------------------------------------

const ALL_DECISION_VALUES = [
  'granted',       // Spec 287 legacy alias — kept for backward compat
  'allow_once',    // Spec 1978 / Spec 033
  'allow_session', // Spec 1978 / Spec 033
  'denied',        // Spec 287 legacy alias — kept for backward compat
  'deny',          // Spec 1978 / Spec 033
] as const

describe('PermissionResponseFrame decision enum — 5-value vocabulary', () => {
  for (const decision of ALL_DECISION_VALUES) {
    test(`decision='${decision}' parses without error`, () => {
      const line = makePermissionResponseLine(decision)
      const result = decodeFrame(line)
      expect(result.ok).toBe(true)
      if (result.ok) {
        const frame = result.frame
        expect(frame.kind).toBe('permission_response')
        if (frame.kind === 'permission_response') {
          expect(frame.decision).toBe(decision)
        }
      }
    })
  }
})

// ---------------------------------------------------------------------------
// 2. Unknown decision values must be rejected
// ---------------------------------------------------------------------------

describe('PermissionResponseFrame — invalid decisions are rejected', () => {
  test("unknown decision 'approve' is rejected", () => {
    const line = makePermissionResponseLine('approve')
    const result = decodeFrame(line)
    expect(result.ok).toBe(false)
  })

  test("unknown decision '' (empty) is rejected", () => {
    const line = makePermissionResponseLine('')
    const result = decodeFrame(line)
    expect(result.ok).toBe(false)
  })

  test("unknown decision 'GRANTED' (uppercase) is rejected", () => {
    const line = makePermissionResponseLine('GRANTED')
    const result = decodeFrame(line)
    expect(result.ok).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// 3. receipt_id field — Gap A fix
// ---------------------------------------------------------------------------

describe('PermissionResponseFrame receipt_id — Gap A fix', () => {
  test('receipt_id is parsed when present (allow_once)', () => {
    const rcptId = 'rcpt-12345678-1234-5678-abcd-ef0123456789'
    const line = makePermissionResponseLine('allow_once', rcptId)
    const result = decodeFrame(line)
    expect(result.ok).toBe(true)
    if (result.ok) {
      const frame = result.frame
      if (frame.kind === 'permission_response') {
        expect(frame.receipt_id).toBe(rcptId)
      }
    }
  })

  test('receipt_id is null on deny (backward compat)', () => {
    const line = makePermissionResponseLine('deny', null)
    const result = decodeFrame(line)
    expect(result.ok).toBe(true)
    if (result.ok) {
      const frame = result.frame
      if (frame.kind === 'permission_response') {
        expect(frame.receipt_id).toBeNull()
      }
    }
  })

  test('receipt_id is absent (undefined) on legacy frames without it', () => {
    // Legacy frames from older backend versions won't have receipt_id at all
    const line = makePermissionResponseLine('granted')  // no receipt_id param
    const result = decodeFrame(line)
    expect(result.ok).toBe(true)
    if (result.ok) {
      const frame = result.frame
      if (frame.kind === 'permission_response') {
        // undefined or null are both acceptable — field is optional
        expect(frame.receipt_id == null).toBe(true)
      }
    }
  })
})

// ---------------------------------------------------------------------------
// 4. Spec 287 backward compat: granted / denied still work
// ---------------------------------------------------------------------------

describe('Spec 287 backward compat — granted/denied aliases', () => {
  test("'granted' is accepted (Spec 287 legacy alias for allow_once)", () => {
    const line = makePermissionResponseLine('granted')
    const result = decodeFrame(line)
    expect(result.ok).toBe(true)
    if (result.ok && result.frame.kind === 'permission_response') {
      expect(result.frame.decision).toBe('granted')
    }
  })

  test("'denied' is accepted (Spec 287 legacy alias for deny)", () => {
    const line = makePermissionResponseLine('denied')
    const result = decodeFrame(line)
    expect(result.ok).toBe(true)
    if (result.ok && result.frame.kind === 'permission_response') {
      expect(result.frame.decision).toBe('denied')
    }
  })
})
