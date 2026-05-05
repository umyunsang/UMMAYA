// SPDX-License-Identifier: Apache-2.0
// Wave-2 G5 (Spec realuse-audit-2026-05-05) — F-beta-05 regression test.
//
// Asserts that the JSON-aware truncation helper appends an explicit U+2026
// ellipsis whenever a string is cut to fit the LookupPrimitive ⎿ row
// budget. Citizens were previously seeing mid-key fragments like
//   {"timestamp_iso":"2026-05-05T12:00:00",...,"sky_code":"1","interval
// with no closing brace and no truncation marker.

import { describe, test, expect } from 'bun:test'
import { truncateJson } from '../../src/tools/_shared/jsonTruncate'

describe('truncateJson', () => {
  test('returns input unchanged when within budget', () => {
    expect(truncateJson('hello', 10)).toBe('hello')
    expect(truncateJson('exact', 5)).toBe('exact')
  })

  test('appends U+2026 ellipsis when input exceeds budget', () => {
    const out = truncateJson('hello world', 8)
    expect(out).toHaveLength(8)
    expect(out.endsWith('…')).toBe(true)
    expect(out).toBe('hello w…')
  })

  test('handles JSON-shape input with mid-key cut', () => {
    // Exact reproduction of F-beta-05 β1 snap-005 surface.
    const json = JSON.stringify({
      timestamp_iso: '2026-05-05T12:00:00',
      temperature_c: 19,
      pop_pct: 0,
      precipitation_mm: '강수없음',
      sky_code: '1',
      interval_minutes: 60,
      additional_field: 'value',
    })
    const truncated = truncateJson(json, 120)
    expect(truncated.length).toBe(120)
    expect(truncated.endsWith('…')).toBe(true)
    // The previous (unfixed) behaviour produced strings WITHOUT this marker.
    expect(truncated).not.toEndWith('"interval')
  })

  test('degenerate max=1 returns single ellipsis', () => {
    expect(truncateJson('long string', 1)).toBe('…')
  })

  test('max=0 returns empty string', () => {
    expect(truncateJson('anything', 0)).toBe('')
  })

  test('does not append ellipsis at exactly-at-boundary length', () => {
    // 8-character input with budget 8 → unchanged (no ellipsis added).
    const eight = 'abcdefgh'
    expect(truncateJson(eight, 8)).toBe(eight)
    expect(truncateJson(eight, 8).endsWith('…')).toBe(false)
  })
})
