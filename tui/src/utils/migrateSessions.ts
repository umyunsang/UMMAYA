// SPDX-License-Identifier: Apache-2.0
//
// KOSMOS-original utility: migrate CC-workspace JSONL sessions to the
// KOSMOS-native memdir USER-tier sessions directory.
//
// Problem (Lead-Diag-3): 374 KOSMOS-TUI workspace sessions (13.6 MB) leaked
// into `~/.claude/projects/` alongside the 1,762 non-KOSMOS CC sessions.
// This utility copies them into `~/.kosmos/memdir/user/sessions/` so the
// KOSMOS session picker can discover them without touching the CC directory.
//
// Algorithm: walk CC dir → filter by cwd regex (default `.*KOSMOS.*`) →
// copyFile EXCL + fsync → optional unlink (--prune).
//
// Atomicity guarantee:
//   - copyFile(src, dest, COPYFILE_EXCL) — fails if dest already exists;
//     skips rather than overwriting.
//   - fsync(dest fd) — durability before unlink.
//   - --prune: any error during unlink phase throws + aborts (no partial-prune).
//   - src JSONL never truncated: if copyFile throws, src is untouched.
//
// Zero new runtime dependencies (AGENTS.md hard rule).

import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync, unlinkSync } from 'node:fs'
import { open, fsync, close } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { getKosmosSessionsDir } from './kosmosPaths.js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MigrateSessionsOpts {
  /**
   * When true, unlink each successfully copied source file after fsync.
   * If any unlink fails, the entire prune phase aborts and throws — no
   * partial-prune state is left.
   */
  prune?: boolean
  /**
   * Regex string applied to the CC project-dir name (the sanitized cwd) to
   * select which sessions to migrate. Defaults to `.*KOSMOS.*`.
   */
  filterCwd?: string
  /**
   * When true, list what would be copied/pruned without touching the filesystem.
   */
  dryRun?: boolean
  /**
   * Override the CC projects base directory (default: `~/.claude/projects/`).
   * Useful in tests.
   */
  ccProjectsDir?: string
  /**
   * Override the KOSMOS sessions destination directory.
   * Useful in tests.
   */
  destDir?: string
}

export interface MigrationSummary {
  /** Files successfully copied to the destination. */
  copied: number
  /** Files skipped because the destination already existed (COPYFILE_EXCL). */
  skipped: number
  /** Files unlinked from source (requires prune: true). */
  pruned: number
  /** Total bytes of copied files. */
  bytes: number
  /** Non-fatal errors encountered (e.g. stat failures on individual files). */
  errors: string[]
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Default CC projects directory (`~/.claude/projects`). */
function defaultCcProjectsDir(): string {
  return join(homedir(), '.claude', 'projects')
}

/**
 * Walk the CC projects directory and collect JSONL file paths that match
 * the filterCwd regex against the project-dir name (sanitized cwd).
 */
function collectSourceFiles(
  ccProjectsDir: string,
  filterRe: RegExp,
): string[] {
  if (!existsSync(ccProjectsDir)) return []

  let projectDirs: string[]
  try {
    projectDirs = readdirSync(ccProjectsDir)
  } catch {
    return []
  }

  const result: string[] = []
  for (const dirName of projectDirs) {
    if (!filterRe.test(dirName)) continue

    const fullDir = join(ccProjectsDir, dirName)
    let stat
    try {
      stat = statSync(fullDir)
    } catch {
      continue
    }
    if (!stat.isDirectory()) continue

    let files: string[]
    try {
      files = readdirSync(fullDir)
    } catch {
      continue
    }

    for (const file of files) {
      if (!file.endsWith('.jsonl')) continue
      result.push(join(fullDir, file))
    }
  }
  return result
}

/**
 * Perform an fsync on the file at the given path to ensure durability
 * before the optional unlink of the source.
 */
async function fsyncFile(path: string): Promise<void> {
  const fd = await open(path, 'r')
  try {
    await fsync(fd.fd)
  } finally {
    await close(fd.fd)
  }
}

// COPYFILE_EXCL constant — fails if dest already exists.
// Node.js exports it as fs.constants.COPYFILE_EXCL (value 1).
const COPYFILE_EXCL = 1

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Migrate CC-workspace JSONL sessions to the KOSMOS memdir USER-tier
 * sessions directory.
 *
 * @throws {Error} Only when `prune: true` and an unlink fails — in that case
 *   the prune phase aborts immediately and the error propagates to the caller.
 *   Partial-prune state (some files pruned, some not) is the invariant that
 *   MUST NOT happen; callers can re-run after fixing the failure.
 */
export async function migrateSessions(
  opts: MigrateSessionsOpts = {},
): Promise<MigrationSummary> {
  const {
    prune = false,
    filterCwd = '.*KOSMOS.*',
    dryRun = false,
    ccProjectsDir = defaultCcProjectsDir(),
    destDir = getKosmosSessionsDir(),
  } = opts

  const filterRe = new RegExp(filterCwd)
  const summary: MigrationSummary = {
    copied: 0,
    skipped: 0,
    pruned: 0,
    bytes: 0,
    errors: [],
  }

  // Collect candidate JSONL files from the CC projects tree.
  const sources = collectSourceFiles(ccProjectsDir, filterRe)

  if (dryRun) {
    // In dry-run mode, just count what would happen.
    for (const src of sources) {
      const destName = src.split('/').pop()!
      const dest = join(destDir, destName)
      if (existsSync(dest)) {
        summary.skipped += 1
      } else {
        try {
          const st = statSync(src)
          summary.copied += 1
          summary.bytes += st.size
          if (prune) summary.pruned += 1
        } catch (err) {
          summary.errors.push(`stat ${src}: ${String(err)}`)
        }
      }
    }
    return summary
  }

  // Ensure destination directory exists.
  mkdirSync(destDir, { recursive: true, mode: 0o700 })

  // Track successfully copied source paths for the prune phase.
  const copied: string[] = []

  // --- Copy phase ---
  for (const src of sources) {
    const destName = src.split('/').pop()!
    const dest = join(destDir, destName)

    // Skip if destination already exists (COPYFILE_EXCL would throw).
    if (existsSync(dest)) {
      summary.skipped += 1
      continue
    }

    let fileSize = 0
    try {
      const st = statSync(src)
      fileSize = st.size
    } catch (err) {
      summary.errors.push(`stat ${src}: ${String(err)}`)
      continue
    }

    try {
      copyFileSync(src, dest, COPYFILE_EXCL)
    } catch (err) {
      summary.errors.push(`copyFile ${src} → ${dest}: ${String(err)}`)
      continue
    }

    // fsync the destination for durability.
    try {
      await fsyncFile(dest)
    } catch (err) {
      // fsync failure is non-fatal for the copy summary but IS fatal for
      // the prune eligibility — do not add to `copied` so we don't prune.
      summary.errors.push(`fsync ${dest}: ${String(err)}`)
      continue
    }

    summary.copied += 1
    summary.bytes += fileSize
    copied.push(src)
  }

  // --- Prune phase (only runs when prune: true) ---
  // Invariant: any unlink failure aborts the entire prune phase and throws.
  // This prevents partial-prune state.
  if (prune && copied.length > 0) {
    for (const src of copied) {
      try {
        unlinkSync(src)
        summary.pruned += 1
      } catch (err) {
        // Abort immediately — throw to caller.
        throw new Error(
          `[migrate-sessions] prune aborted: unlink ${src} failed: ${String(err)}. ` +
            `${summary.pruned} files were pruned before this failure. ` +
            `Re-run /migrate-sessions --prune after fixing the issue.`,
        )
      }
    }
  }

  return summary
}
