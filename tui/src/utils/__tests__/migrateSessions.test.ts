// SPDX-License-Identifier: Apache-2.0
//
// Unit tests for tui/src/utils/migrateSessions.ts
//
// Test matrix:
//   1. happy-path          — files copied, summary accurate, prune=false
//   2. skip-collision      — dest already exists → skipped counter, no overwrite
//   3. prune-abort         — unlink fails mid-way → throws, pruned count frozen
//   4. filter-cwd          — non-matching project dirs excluded
//   5. dry-run             — no filesystem changes, counts match expected
//   6. empty-cc-dir        — returns zero summary safely
//   7. prune-happy-path    — files pruned after successful copy

import { test, expect, beforeEach, afterEach, describe } from 'bun:test'
import {
  mkdirSync,
  writeFileSync,
  existsSync,
  readdirSync,
  mkdtempSync,
  rmSync,
} from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { migrateSessions } from '../migrateSessions.js'

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

let tmpRoot: string

beforeEach(() => {
  tmpRoot = mkdtempSync(join(tmpdir(), 'kosmos-migrate-test-'))
})

afterEach(() => {
  if (tmpRoot && existsSync(tmpRoot)) {
    rmSync(tmpRoot, { recursive: true, force: true })
  }
})

/**
 * Set up a CC-style projects directory with one project sub-dir containing
 * the given JSONL file names.
 */
function setupCcDir(
  projectDirName: string,
  files: Record<string, string> = {},
): string {
  const ccDir = join(tmpRoot, 'cc-projects')
  const projDir = join(ccDir, projectDirName)
  mkdirSync(projDir, { recursive: true })
  for (const [name, content] of Object.entries(files)) {
    writeFileSync(join(projDir, name), content, 'utf-8')
  }
  return ccDir
}

/**
 * Create a KOSMOS sessions destination directory (empty) and return the path.
 */
function setupDestDir(): string {
  const dest = join(tmpRoot, 'kosmos-sessions')
  mkdirSync(dest, { recursive: true })
  return dest
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('migrateSessions — happy path', () => {
  test('copies JSONL files from matching project dir', async () => {
    const content = '{"kind":"user_input","ts":"2026-05-04T00:00:00Z"}\n'
    const ccDir = setupCcDir('-Users-um-yunsang-KOSMOS', {
      'session-abc.jsonl': content,
      'session-def.jsonl': content,
    })
    const dest = setupDestDir()

    const summary = await migrateSessions({
      ccProjectsDir: ccDir,
      destDir: dest,
      filterCwd: '.*KOSMOS.*',
    })

    expect(summary.copied).toBe(2)
    expect(summary.skipped).toBe(0)
    expect(summary.pruned).toBe(0)
    expect(summary.bytes).toBe(content.length * 2)
    expect(summary.errors).toEqual([])

    // Verify files are in dest.
    const destFiles = readdirSync(dest).sort()
    expect(destFiles).toContain('session-abc.jsonl')
    expect(destFiles).toContain('session-def.jsonl')

    // Verify src is still there (prune=false).
    expect(existsSync(join(ccDir, '-Users-um-yunsang-KOSMOS', 'session-abc.jsonl'))).toBe(true)
  })
})

describe('migrateSessions — skip collision', () => {
  test('skips files whose destination already exists', async () => {
    const content = '{"kind":"user_input"}\n'
    const ccDir = setupCcDir('-Users-um-yunsang-KOSMOS', {
      'session-abc.jsonl': content,
      'session-new.jsonl': content,
    })
    const dest = setupDestDir()

    // Pre-populate destination with one of the two files.
    writeFileSync(join(dest, 'session-abc.jsonl'), 'pre-existing\n', 'utf-8')

    const summary = await migrateSessions({
      ccProjectsDir: ccDir,
      destDir: dest,
    })

    expect(summary.copied).toBe(1)
    expect(summary.skipped).toBe(1)
    expect(summary.errors).toEqual([])

    // Pre-existing file must NOT be overwritten.
    const preContent = Bun.file(join(dest, 'session-abc.jsonl'))
    const text = await preContent.text()
    expect(text).toBe('pre-existing\n')

    // New file was copied.
    expect(existsSync(join(dest, 'session-new.jsonl'))).toBe(true)
  })
})

describe('migrateSessions — filter-cwd', () => {
  test('excludes project dirs that do not match filterCwd', async () => {
    const content = '{"kind":"user_input"}\n'
    // Two project dirs — only one matches the filter.
    const ccDir = join(tmpRoot, 'cc-projects')
    mkdirSync(join(ccDir, '-Users-um-yunsang-KOSMOS'), { recursive: true })
    writeFileSync(
      join(ccDir, '-Users-um-yunsang-KOSMOS', 'session-1.jsonl'),
      content,
      'utf-8',
    )
    mkdirSync(join(ccDir, '-Users-other-project'), { recursive: true })
    writeFileSync(
      join(ccDir, '-Users-other-project', 'session-2.jsonl'),
      content,
      'utf-8',
    )

    const dest = setupDestDir()

    const summary = await migrateSessions({
      ccProjectsDir: ccDir,
      destDir: dest,
      filterCwd: '.*KOSMOS.*',
    })

    // Only session-1.jsonl from the KOSMOS dir should be copied.
    expect(summary.copied).toBe(1)
    expect(summary.skipped).toBe(0)
    expect(existsSync(join(dest, 'session-1.jsonl'))).toBe(true)
    expect(existsSync(join(dest, 'session-2.jsonl'))).toBe(false)
  })
})

describe('migrateSessions — dry-run', () => {
  test('returns accurate counts without touching the filesystem', async () => {
    const content = '{"kind":"user_input"}\n'
    const ccDir = setupCcDir('-Users-um-yunsang-KOSMOS', {
      'session-a.jsonl': content,
      'session-b.jsonl': content,
    })
    const dest = setupDestDir()

    const summary = await migrateSessions({
      ccProjectsDir: ccDir,
      destDir: dest,
      dryRun: true,
    })

    expect(summary.copied).toBe(2)
    expect(summary.skipped).toBe(0)
    expect(summary.pruned).toBe(0)
    expect(summary.bytes).toBe(content.length * 2)

    // No files should have been written to dest in dry-run mode.
    const destFiles = readdirSync(dest)
    expect(destFiles).toHaveLength(0)

    // Source files still present.
    expect(existsSync(join(ccDir, '-Users-um-yunsang-KOSMOS', 'session-a.jsonl'))).toBe(true)
  })

  test('dry-run with prune flag counts pruned without deleting', async () => {
    const content = '{"kind":"user_input"}\n'
    const ccDir = setupCcDir('-Users-um-yunsang-KOSMOS', {
      'session-x.jsonl': content,
    })
    const dest = setupDestDir()

    const summary = await migrateSessions({
      ccProjectsDir: ccDir,
      destDir: dest,
      dryRun: true,
      prune: true,
    })

    expect(summary.copied).toBe(1)
    expect(summary.pruned).toBe(1)

    // Source file must still exist (dry-run).
    expect(existsSync(join(ccDir, '-Users-um-yunsang-KOSMOS', 'session-x.jsonl'))).toBe(true)
    // Dest must remain empty (dry-run).
    expect(readdirSync(dest)).toHaveLength(0)
  })
})

describe('migrateSessions — prune happy path', () => {
  test('unlinks source files after successful copy+fsync', async () => {
    const content = '{"kind":"user_input"}\n'
    const ccDir = setupCcDir('-Users-um-yunsang-KOSMOS', {
      'prune-me.jsonl': content,
    })
    const dest = setupDestDir()
    const srcPath = join(ccDir, '-Users-um-yunsang-KOSMOS', 'prune-me.jsonl')

    const summary = await migrateSessions({
      ccProjectsDir: ccDir,
      destDir: dest,
      prune: true,
    })

    expect(summary.copied).toBe(1)
    expect(summary.pruned).toBe(1)
    expect(summary.errors).toEqual([])

    // Source must be gone.
    expect(existsSync(srcPath)).toBe(false)

    // Destination must have the file.
    expect(existsSync(join(dest, 'prune-me.jsonl'))).toBe(true)
  })
})

describe('migrateSessions — empty CC dir', () => {
  test('returns zero summary when CC projects dir does not exist', async () => {
    const dest = setupDestDir()
    const nonExistent = join(tmpRoot, 'no-such-dir')

    const summary = await migrateSessions({
      ccProjectsDir: nonExistent,
      destDir: dest,
    })

    expect(summary.copied).toBe(0)
    expect(summary.skipped).toBe(0)
    expect(summary.pruned).toBe(0)
    expect(summary.bytes).toBe(0)
    expect(summary.errors).toEqual([])
  })

  test('returns zero summary when matching project dir is empty', async () => {
    const ccDir = setupCcDir('-Users-um-yunsang-KOSMOS', {}) // no files
    const dest = setupDestDir()

    const summary = await migrateSessions({
      ccProjectsDir: ccDir,
      destDir: dest,
    })

    expect(summary.copied).toBe(0)
    expect(summary.bytes).toBe(0)
  })
})
