// SPDX-License-Identifier: Apache-2.0
//
// Spec 2643 Epic G US1 — sessionTitle PORT regression test (T012).
//
// Verifies that generateSessionTitle (byte-copied from CC) returns the correct
// shape for: empty input → null, valid mock response → title, malformed JSON →
// null. Mocks queryHaiku via Bun mock.module() so no live K-EXAONE call.
//
// Spec source: specs/2643-utils-residue/contracts/sessionTitle.contract.md

import { test, expect, mock, beforeAll } from 'bun:test'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TUI_SRC_ROOT = resolve(__dirname, '..', '..')

// Track which response the mock should serve next
let mockText = '{"title":"Test session title"}'

beforeAll(() => {
  mock.module(resolve(TUI_SRC_ROOT, 'services/api/ummaya.js'), () => ({
    queryHaiku: async () => ({
      message: { content: [{ type: 'text', text: mockText }] },
    }),
  }))
})

test('generateSessionTitle returns null for empty description', async () => {
  const { generateSessionTitle } = await import('../sessionTitle.js')
  const ctl = new AbortController()
  expect(await generateSessionTitle('', ctl.signal)).toBeNull()
  expect(await generateSessionTitle('   ', ctl.signal)).toBeNull()
})

test('generateSessionTitle returns title from valid JSON mock response', async () => {
  const { generateSessionTitle } = await import('../sessionTitle.js')
  mockText = '{"title":"한강 다리 사고 조회"}'
  const ctl = new AbortController()
  const title = await generateSessionTitle('한강 다리 사고 확인 도와줘', ctl.signal)
  expect(title).toBe('한강 다리 사고 조회')
})

test('generateSessionTitle returns null on malformed JSON', async () => {
  const { generateSessionTitle } = await import('../sessionTitle.js')
  mockText = 'not valid json {{{'
  const ctl = new AbortController()
  const title = await generateSessionTitle('any input', ctl.signal)
  expect(title).toBeNull()
})
