// SPDX-License-Identifier: Apache-2.0
// Tests for aalToLayer — active FR-005 matrix.

import { describe, test, expect } from 'bun:test'
import { aalToLayer } from './aalToLayer'

describe('aalToLayer', () => {
  test('find returns null (bypass — no gauntlet)', () => {
    expect(aalToLayer('find')).toBeNull()
  })

  test('find with isIrreversible=true still returns null', () => {
    expect(aalToLayer('find', true)).toBeNull()
  })

  test('check returns 1 (green ⓵, low risk)', () => {
    expect(aalToLayer('check')).toBe(1)
  })

  test('check with isIrreversible=true still returns 1', () => {
    // check AAL level does not affect layer — FR-005 matrix is primitive-based
    expect(aalToLayer('check', true)).toBe(1)
  })

  test('send (reversible, default) returns 2 (orange ⓶)', () => {
    expect(aalToLayer('send')).toBe(2)
  })

  test('send (irreversible=false) returns 2 (orange ⓶)', () => {
    expect(aalToLayer('send', false)).toBe(2)
  })

  test('send (irreversible=true) returns 3 (red ⓷)', () => {
    expect(aalToLayer('send', true)).toBe(3)
  })
})
