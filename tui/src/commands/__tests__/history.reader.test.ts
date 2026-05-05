// SPDX-License-Identifier: Apache-2.0
/**
 * Unit tests for history.ts session reader.
 *
 * Verifies:
 *   1. `file-history-snapshot` sentinel first line is skipped correctly.
 *   2. The first real JSONL entry (user/assistant) is parsed as session header.
 *   3. `permission_layer` values are extracted from all lines.
 *   4. Sessions with only a sentinel line (no real entries) are excluded.
 *   5. `last_active_at` falls back to `started_at` when absent.
 */

import { test, expect, beforeEach, afterEach } from 'bun:test'
import { mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'

// ---------------------------------------------------------------------------
// Test isolation: override the SESSIONS_DIR by pointing KOSMOS_MEMDIR_USER
// ---------------------------------------------------------------------------

const TMP_ROOT = join(tmpdir(), `kosmos-history-reader-test-${Date.now()}`)
const SESSIONS_DIR = join(TMP_ROOT, 'sessions')

const ORIG_KOSMOS_MEMDIR_USER = process.env.KOSMOS_MEMDIR_USER

// Session UUIDs
const SESSION_WITH_SENTINEL = 'aaaaaaaa-0000-0000-0000-000000000001'
const SESSION_NO_SENTINEL = 'bbbbbbbb-0000-0000-0000-000000000002'
const SESSION_SENTINEL_ONLY = 'cccccccc-0000-0000-0000-000000000003'
const SESSION_WITH_LAYER = 'dddddddd-0000-0000-0000-000000000004'
const SESSION_EXPLICIT_HEADER = 'eeeeeeee-0000-0000-0000-000000000005'

function writeSessionFile(sessionId: string, content: string): void {
  writeFileSync(join(SESSIONS_DIR, `${sessionId}.jsonl`), content)
}

beforeEach(() => {
  mkdirSync(SESSIONS_DIR, { recursive: true })

  // Session 1: starts with file-history-snapshot, then a user entry
  writeSessionFile(
    SESSION_WITH_SENTINEL,
    [
      'file-history-snapshot {"compacted":true,"version":1}',
      JSON.stringify({
        type: 'user',
        session_id: SESSION_WITH_SENTINEL,
        timestamp: '2026-03-01T10:00:00.000Z',
        message: { role: 'user', content: 'Hello from sentinel session' },
      }),
      JSON.stringify({
        type: 'assistant',
        timestamp: '2026-03-01T10:00:01.000Z',
        message: { role: 'assistant', content: 'Hi!' },
      }),
      '',
    ].join('\n'),
  )

  // Session 2: no sentinel — normal session starting with user entry
  writeSessionFile(
    SESSION_NO_SENTINEL,
    [
      JSON.stringify({
        type: 'user',
        session_id: SESSION_NO_SENTINEL,
        timestamp: '2026-04-01T10:00:00.000Z',
        message: { role: 'user', content: 'Normal session user message' },
      }),
      '',
    ].join('\n'),
  )

  // Session 3: sentinel line only — no real entries, should be excluded
  writeSessionFile(
    SESSION_SENTINEL_ONLY,
    'file-history-snapshot {"compacted":true,"version":1}\n',
  )

  // Session 4: has a permission_layer annotation
  writeSessionFile(
    SESSION_WITH_LAYER,
    [
      JSON.stringify({
        type: 'user',
        session_id: SESSION_WITH_LAYER,
        timestamp: '2026-05-01T10:00:00.000Z',
        message: { role: 'user', content: 'Layer test session' },
      }),
      JSON.stringify({
        type: 'tool_use',
        permission_layer: 2,
        timestamp: '2026-05-01T10:00:02.000Z',
      }),
      '',
    ].join('\n'),
  )

  // Session 5: first line is an explicit header object with all fields set
  writeSessionFile(
    SESSION_EXPLICIT_HEADER,
    [
      JSON.stringify({
        type: 'session_header',
        session_id: SESSION_EXPLICIT_HEADER,
        started_at: '2026-06-01T09:00:00.000Z',
        last_active_at: '2026-06-01T11:00:00.000Z',
        preview: 'Explicit header preview',
      }),
      '',
    ].join('\n'),
  )

  // Point KOSMOS_MEMDIR_USER at our temp dir so history.ts reads from SESSIONS_DIR
  process.env.KOSMOS_MEMDIR_USER = TMP_ROOT
})

afterEach(() => {
  if (ORIG_KOSMOS_MEMDIR_USER === undefined) {
    delete process.env.KOSMOS_MEMDIR_USER
  } else {
    process.env.KOSMOS_MEMDIR_USER = ORIG_KOSMOS_MEMDIR_USER
  }
  try {
    rmSync(TMP_ROOT, { recursive: true, force: true })
  } catch {
    // Ignore cleanup errors
  }
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test('history reader skips file-history-snapshot sentinel and parses the next line', async () => {
  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(
    s => s.session_id === SESSION_WITH_SENTINEL,
  )
  expect(entry).toBeDefined()
  // preview should come from the user message, not the sentinel
  expect(entry!.preview).toBe('Hello from sentinel session')
})

test('history reader parses session without sentinel normally', async () => {
  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(s => s.session_id === SESSION_NO_SENTINEL)
  expect(entry).toBeDefined()
  expect(entry!.preview).toBe('Normal session user message')
})

test('history reader excludes sessions with only a sentinel line and no real entries', async () => {
  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(
    s => s.session_id === SESSION_SENTINEL_ONLY,
  )
  // Should not be included since there are no parseable entries
  expect(entry).toBeUndefined()
})

test('history reader extracts permission_layer from annotated lines', async () => {
  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(s => s.session_id === SESSION_WITH_LAYER)
  expect(entry).toBeDefined()
  expect(entry!.layers_touched).toContain(2)
})

test('history reader uses explicit header fields when present', async () => {
  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(
    s => s.session_id === SESSION_EXPLICIT_HEADER,
  )
  expect(entry).toBeDefined()
  expect(entry!.started_at).toBe('2026-06-01T09:00:00.000Z')
  expect(entry!.last_active_at).toBe('2026-06-01T11:00:00.000Z')
  expect(entry!.preview).toBe('Explicit header preview')
})

test('history reader derives started_at from timestamp field when started_at absent', async () => {
  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(
    s => s.session_id === SESSION_WITH_SENTINEL,
  )
  // The user entry has timestamp: '2026-03-01T10:00:00.000Z'
  expect(entry!.started_at).toBe('2026-03-01T10:00:00.000Z')
})

test('history reader permission_layer is empty array when no annotations present', async () => {
  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(s => s.session_id === SESSION_NO_SENTINEL)
  expect(entry).toBeDefined()
  expect(entry!.layers_touched).toEqual([])
})

// ---------------------------------------------------------------------------
// Audit-7 P0-4 fix tests
// ---------------------------------------------------------------------------

test('Audit-7 P0-4: history reader walks sanitized-cwd subdirectories (CC-style projects layout)', async () => {
  // Pre-populate: simulate /migrate-sessions output (subdirectory layout
  // with a real CC-style session JSONL inside).
  const subDir = join(SESSIONS_DIR, '-Users-um-yunsang-KOSMOS-tui')
  mkdirSync(subDir, { recursive: true })
  const SUBDIR_SESSION = 'ffffffff-0000-0000-0000-000000000099'
  writeFileSync(
    join(subDir, `${SUBDIR_SESSION}.jsonl`),
    [
      JSON.stringify({
        type: 'user',
        session_id: SUBDIR_SESSION,
        timestamp: '2026-04-15T08:00:00.000Z',
        message: { role: 'user', content: 'CC-migrated session' },
      }),
      '',
    ].join('\n'),
  )

  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(s => s.session_id === SUBDIR_SESSION)
  expect(entry).toBeDefined()
  expect(entry!.preview).toBe('CC-migrated session')
})

test('Audit-7 P0-4: history reader skips Python metadata-only stubs (1-line + message_count=0)', async () => {
  const STUB_SESSION = '99999999-0000-0000-0000-000000000100'
  // Mirrors what the pre-lazy Python create_session wrote at IPC boot.
  writeFileSync(
    join(SESSIONS_DIR, `${STUB_SESSION}.jsonl`),
    JSON.stringify({
      timestamp: '2026-05-04T15:18:12.227611Z',
      entry_type: 'metadata',
      data: {
        session_id: STUB_SESSION,
        created_at: '2026-05-04T15:18:12.227611Z',
        updated_at: '2026-05-04T15:18:12.227611Z',
        title: null,
        message_count: 0,
        total_tokens_used: 0,
        parent_session_id: null,
      },
      parent_id: null,
    }) + '\n',
  )

  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(s => s.session_id === STUB_SESSION)
  // Stub MUST be hidden from /history surface.
  expect(entry).toBeUndefined()
})

test('Audit-7 P0-4: history reader keeps Python sessions that have message_count > 0', async () => {
  const REAL_SESSION = '88888888-0000-0000-0000-000000000200'
  // metadata header + a real user message (message_count effectively 1)
  writeFileSync(
    join(SESSIONS_DIR, `${REAL_SESSION}.jsonl`),
    [
      JSON.stringify({
        timestamp: '2026-05-04T15:18:12.227611Z',
        entry_type: 'metadata',
        data: {
          session_id: REAL_SESSION,
          created_at: '2026-05-04T15:18:12.227611Z',
          updated_at: '2026-05-04T15:18:12.227611Z',
          message_count: 0, // header still says 0 but body has entries
        },
        parent_id: null,
      }),
      JSON.stringify({
        type: 'user',
        timestamp: '2026-05-04T15:20:00.000Z',
        message: { role: 'user', content: 'real user message' },
      }),
      '',
    ].join('\n'),
  )

  const { executeHistory } = await import('../history.js')
  const result = executeHistory()
  const entry = result.sessions.find(s => s.session_id === REAL_SESSION)
  expect(entry).toBeDefined()
})
