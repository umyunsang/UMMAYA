// SPDX-License-Identifier: Apache-2.0
//
// Spec 2643 Epic G US2 — dateTimeParser PORT regression test (T021).
//
// Verifies Korean natural-language date/time parsing via mocked queryHaiku.
// Covers FR-008 (INVALID handling), FR-009 (looksLikeISO8601), FR-011 (4 Korean
// fixture paths). No live K-EXAONE call (AGENTS.md hard rule).
//
// Spec source: specs/2643-utils-residue/contracts/dateTimeParser.contract.md

import { test, expect, mock, beforeAll } from 'bun:test'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TUI_SRC_ROOT = resolve(__dirname, '..', '..', '..')

beforeAll(() => {
  mock.module(resolve(TUI_SRC_ROOT, 'services/api/ummaya.js'), () => ({
    queryHaiku: async ({ userPrompt }: { userPrompt: string }) => {
      // Match the Korean fixture inputs from spec FR-011 + contract test plan
      let text = 'INVALID'
      if (userPrompt.includes('내일 오후 3시')) {
        text = '2026-05-04T15:00:00+09:00'
      } else if (userPrompt.includes('다음주 월요일 오전 9시')) {
        text = '2026-05-11T09:00:00+09:00'
      } else if (userPrompt.includes('다음주 월요일')) {
        text = '2026-05-11'
      }
      return { message: { content: [{ type: 'text', text }] } }
    },
  }))
})

test('parseNaturalLanguageDateTime: 내일 오후 3시 → ISO date-time', async () => {
  const { parseNaturalLanguageDateTime } = await import('../dateTimeParser.js')
  const ctl = new AbortController()
  const result = await parseNaturalLanguageDateTime(
    '내일 오후 3시',
    'date-time',
    ctl.signal,
  )
  expect(result).toEqual({ success: true, value: '2026-05-04T15:00:00+09:00' })
})

test('parseNaturalLanguageDateTime: 다음주 월요일 오전 9시 → ISO date-time', async () => {
  const { parseNaturalLanguageDateTime } = await import('../dateTimeParser.js')
  const ctl = new AbortController()
  const result = await parseNaturalLanguageDateTime(
    '다음주 월요일 오전 9시',
    'date-time',
    ctl.signal,
  )
  expect(result).toEqual({ success: true, value: '2026-05-11T09:00:00+09:00' })
})

test('parseNaturalLanguageDateTime: 다음주 월요일 → ISO date', async () => {
  const { parseNaturalLanguageDateTime } = await import('../dateTimeParser.js')
  const ctl = new AbortController()
  const result = await parseNaturalLanguageDateTime(
    '다음주 월요일',
    'date',
    ctl.signal,
  )
  expect(result).toEqual({ success: true, value: '2026-05-11' })
})

test('parseNaturalLanguageDateTime: asdf → INVALID failure', async () => {
  const { parseNaturalLanguageDateTime } = await import('../dateTimeParser.js')
  const ctl = new AbortController()
  const result = await parseNaturalLanguageDateTime('asdf', 'date', ctl.signal)
  expect(result).toEqual({
    success: false,
    error: 'Unable to parse date/time from input',
  })
})

test('looksLikeISO8601: positive + negative cases', async () => {
  const { looksLikeISO8601 } = await import('../dateTimeParser.js')
  expect(looksLikeISO8601('2026-05-03')).toBe(true)
  expect(looksLikeISO8601('2026-05-03T14:30:00Z')).toBe(true)
  expect(looksLikeISO8601('내일')).toBe(false)
  expect(looksLikeISO8601('asdf')).toBe(false)
})
