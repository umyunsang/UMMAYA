// SPDX-License-Identifier: Apache-2.0
// Tests for aalToLayer — FR-005 matrix (8 cases).

import { describe, test, expect } from 'bun:test'
import { aalToLayer } from './aalToLayer'

describe('aalToLayer', () => {
  test('lookup returns null (bypass — no gauntlet)', () => {
    expect(aalToLayer('lookup')).toBeNull()
  })

  test('lookup with isIrreversible=true still returns null', () => {
    expect(aalToLayer('lookup', true)).toBeNull()
  })

  test('verify returns 1 (green ⓵, low risk)', () => {
    expect(aalToLayer('verify')).toBe(1)
  })

  test('verify with isIrreversible=true still returns 1', () => {
    // verify AAL level does not affect layer — FR-005 matrix is primitive-based
    expect(aalToLayer('verify', true)).toBe(1)
  })

  test('submit (reversible, default) returns 2 (orange ⓶)', () => {
    expect(aalToLayer('submit')).toBe(2)
  })

  test('submit (irreversible=false) returns 2 (orange ⓶)', () => {
    expect(aalToLayer('submit', false)).toBe(2)
  })

  test('submit (irreversible=true) returns 3 (red ⓷)', () => {
    expect(aalToLayer('submit', true)).toBe(3)
  })

  test('subscribe returns 2 (orange ⓶, medium risk)', () => {
    expect(aalToLayer('subscribe')).toBe(2)
  })
})
