// SPDX-License-Identifier: Apache-2.0
// KOSMOS hotfix (2026-05-04, KMA base_time hallucination 차단):
// `getKstTimeParts()` returns the current KST date + HH:MM + HHMM tuple
// that `getUserContext()` emits as the `currentKstTime` field. The LLM
// uses this to pick KMA `base_time` (KST publication slots: 0200/0500/
// 0800/1100/1400/1700/2000/2300) instead of guessing.
//
// Two invariants:
//   1. Output structure: { iso: 'YYYY-MM-DD', hm: 'HH:MM', hhmm: 'HHMM' }
//      with HH:MM and HHMM internally consistent.
//   2. Timezone correctness: Asia/Seoul wall-clock, NOT UTC. We probe with
//      KOSMOS_OVERRIDE_KST_TIME so the test is independent of the host's
//      wall-clock and timezone.

import { afterEach, describe, expect, it } from 'bun:test'
import { getKstTimeParts } from '../../src/constants/common.js'

const ENV_KEY = 'KOSMOS_OVERRIDE_KST_TIME'

afterEach(() => {
  delete process.env[ENV_KEY]
})

describe('getKstTimeParts', () => {
  it('returns iso (YYYY-MM-DD), hm (HH:MM), and hhmm (HHMM) shape', () => {
    const parts = getKstTimeParts()
    expect(parts.iso).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(parts.hm).toMatch(/^\d{2}:\d{2}$/)
    expect(parts.hhmm).toMatch(/^\d{4}$/)
  })

  it('keeps hm and hhmm internally consistent', () => {
    const parts = getKstTimeParts()
    expect(parts.hm.replace(':', '')).toBe(parts.hhmm)
  })

  it('honours KOSMOS_OVERRIDE_KST_TIME with HH:MM input', () => {
    process.env[ENV_KEY] = '07:35'
    const parts = getKstTimeParts()
    expect(parts.hm).toBe('07:35')
    expect(parts.hhmm).toBe('0735')
  })

  it('honours KOSMOS_OVERRIDE_KST_TIME with full ISO-8601 input', () => {
    process.env[ENV_KEY] = '2026-05-04T16:42:00+09:00'
    const parts = getKstTimeParts()
    expect(parts.iso).toBe('2026-05-04')
    expect(parts.hm).toBe('16:42')
    expect(parts.hhmm).toBe('1642')
  })

  it('produces Asia/Seoul wall-clock (not UTC)', () => {
    // Pick a moment when KST and UTC dates differ: 2026-05-04 00:30 KST is
    // 2026-05-03 15:30 UTC. The function must report the KST-local 00:30.
    process.env[ENV_KEY] = '2026-05-04T00:30:00+09:00'
    const parts = getKstTimeParts()
    expect(parts.iso).toBe('2026-05-04')
    expect(parts.hm).toBe('00:30')
    expect(parts.hhmm).toBe('0030')
  })
})

describe('getUserContext currentKstTime injection', () => {
  it('emits currentKstTime in the user context payload', async () => {
    // getUserContext is memoised; clear it first so the override below is
    // observed. Importing dynamically avoids ESM cache contamination across
    // test files.
    const { getUserContext } = await import('../../src/context.js')
    // Cast through unknown so we can reach the memoize cache without
    // widening the public type surface.
    const memoised = getUserContext as unknown as { cache: { clear?: () => void } }
    memoised.cache.clear?.()

    process.env[ENV_KEY] = '2026-05-04T16:00:00+09:00'

    const ctx = await getUserContext()
    expect(ctx).toHaveProperty('currentKstTime')
    expect(ctx.currentKstTime).toContain('현재 KST 시각: 16:00 (1600)')
    // KMA base_time enumeration must appear so a sub-agent reading the
    // citizen-facing user context still sees the publication-slot anchor.
    expect(ctx.currentKstTime).toContain('0200/0500/0800/1100/1400/1700/2000/2300')
    expect(ctx.currentKstTime).toContain('추측 금지')

    // currentDate must still be present (back-compat).
    expect(ctx).toHaveProperty('currentDate')
  })
})
