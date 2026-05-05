// SPDX-License-Identifier: Apache-2.0
// Source: KOSMOS Epic H #1302 (035-onboarding-brand-port)
//
// Filesystem read/write helpers for the memdir USER tier.  The TUI writes
// consent + ministry-scope records directly to `~/.kosmos/memdir/user/...`
// using the same atomic-write pattern as `src/kosmos/memdir/*.py`: tmp file
// + fsync + rename.  Reading scans descending filenames and returns the
// first Zod-validating record.
//
// Direct-filesystem persistence keeps Epic H self-contained — no new IPC
// frame type is required.  Python reads the same directory via
// `latest_consent()` / `latest_scope()`; both producers share POSIX fsync
// ordering for durability.

import {
  closeSync,
  fsyncSync,
  mkdirSync,
  openSync,
  readdirSync,
  readFileSync,
  renameSync,
  writeSync,
} from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { PIPAConsentRecordSchema, type PIPAConsentRecord } from './consent'
import {
  MinistryScopeAcknowledgmentSchema,
  type MinistryScopeAcknowledgment,
} from './ministry-scope'

// ---------------------------------------------------------------------------
// P0-3: lazy user-tier root — env-override aware
//
// `DEFAULT_MEMDIR_ROOT` was a module-load constant, so `writeConsentRecord`
// and `writeScopeRecord` always wrote to `~/.kosmos/memdir/user/` even when
// `KOSMOS_MEMDIR_USER` was set (as `uiL2Memdir.ts:25` already handles).
//
// `getDefaultUserTierRoot()` returns the USER-tier directory (the directory
// that contains `consent/`, `ministry-scope/`, etc.) using the same priority
// order as `uiL2Memdir.ts:25` and `ExportPDFTool.ts:89`:
//
//   1. KOSMOS_MEMDIR_USER  — direct user-tier root override (mirrors uiL2Memdir)
//   2. KOSMOS_MEMDIR_ROOT  — full memdir root override → appends `/user`
//   3. ~/.kosmos/memdir/user — production default
//
// The function is intentionally call-time (no module-level memoize) so test
// suites can change the env variable between test cases without cache leakage.
// ---------------------------------------------------------------------------
export function getDefaultUserTierRoot(): string {
  const userOverride = process.env['KOSMOS_MEMDIR_USER']
  if (userOverride) {
    return userOverride
  }
  const rootOverride = process.env['KOSMOS_MEMDIR_ROOT']
  if (rootOverride) {
    return join(rootOverride, 'user')
  }
  return join(homedir(), '.kosmos', 'memdir', 'user')
}

/**
 * @deprecated Use `getDefaultUserTierRoot()` for env-aware resolution.
 * Kept for backward compatibility with external callers that import the
 * named export.  The value is evaluated once at module-load time and does
 * NOT respect runtime env changes — new callers should use
 * `getDefaultUserTierRoot()`.
 */
export const DEFAULT_MEMDIR_ROOT = join(homedir(), '.kosmos', 'memdir')

// ---------------------------------------------------------------------------
// Common: atomic write
// ---------------------------------------------------------------------------

/** Escape the `:` characters in an ISO timestamp so it is a safe filename. */
function formatIsoForFilename(isoUtc: string): string {
  // Input shape: 2026-04-20T14:32:05.123Z  →  2026-04-20T14-32-05Z
  const noMillis = isoUtc.replace(/\.\d+Z$/, 'Z')
  return noMillis.replace(/:/g, '-')
}

function atomicWriteJson(path: string, bodyText: string): void {
  const parent = dirname(path)
  mkdirSync(parent, { recursive: true, mode: 0o700 })
  const tmpPath = `${path}.tmp`
  const fd = openSync(tmpPath, 'w', 0o600)
  try {
    writeSync(fd, bodyText)
    fsyncSync(fd)
  } finally {
    closeSync(fd)
  }
  renameSync(tmpPath, path)
}

// ---------------------------------------------------------------------------
// Consent records
// ---------------------------------------------------------------------------

// P0-3: `userTierRoot` is the USER-tier directory (contains consent/, ministry-scope/).
// Default uses the lazy env-aware getter so KOSMOS_MEMDIR_USER is respected.
export function consentDir(userTierRoot: string = getDefaultUserTierRoot()): string {
  return join(userTierRoot, 'consent')
}

export function writeConsentRecord(
  record: PIPAConsentRecord,
  userTierRoot: string = getDefaultUserTierRoot(),
): string {
  const parsed = PIPAConsentRecordSchema.parse(record)
  const ts = formatIsoForFilename(parsed.timestamp)
  const filename = `${ts}-${parsed.session_id}.json`
  const fullPath = join(consentDir(userTierRoot), filename)
  atomicWriteJson(fullPath, JSON.stringify(parsed))
  return fullPath
}

export function latestConsentRecord(
  userTierRoot: string = getDefaultUserTierRoot(),
): PIPAConsentRecord | null {
  return latestRecord(consentDir(userTierRoot), (body) =>
    PIPAConsentRecordSchema.safeParse(JSON.parse(body)),
  )
}

// ---------------------------------------------------------------------------
// Ministry-scope records
// ---------------------------------------------------------------------------

export function scopeDir(userTierRoot: string = getDefaultUserTierRoot()): string {
  return join(userTierRoot, 'ministry-scope')
}

export function writeScopeRecord(
  record: MinistryScopeAcknowledgment,
  userTierRoot: string = getDefaultUserTierRoot(),
): string {
  const parsed = MinistryScopeAcknowledgmentSchema.parse(record)
  const ts = formatIsoForFilename(parsed.timestamp)
  const filename = `${ts}-${parsed.session_id}.json`
  const fullPath = join(scopeDir(userTierRoot), filename)
  atomicWriteJson(fullPath, JSON.stringify(parsed))
  return fullPath
}

export function latestScopeRecord(
  userTierRoot: string = getDefaultUserTierRoot(),
): MinistryScopeAcknowledgment | null {
  return latestRecord(scopeDir(userTierRoot), (body) =>
    MinistryScopeAcknowledgmentSchema.safeParse(JSON.parse(body)),
  )
}

// ---------------------------------------------------------------------------
// Internal: shared "latest record in dir" scanner
// ---------------------------------------------------------------------------

type ZodSafeParse<T> =
  | { success: true; data: T }
  | { success: false; error: unknown }

function latestRecord<T>(
  dir: string,
  parse: (body: string) => ZodSafeParse<T>,
): T | null {
  let entries: string[]
  try {
    entries = readdirSync(dir)
  } catch {
    // Dir missing / permission-denied / broken symlink — fail-closed.
    return null
  }
  const jsons = entries.filter((name) => name.endsWith('.json')).sort().reverse()
  for (const name of jsons) {
    try {
      const body = readFileSync(join(dir, name), 'utf8')
      const result = parse(body)
      if (result.success) return result.data
    } catch {
      // Skip unreadable or non-JSON records, keep walking back.
      continue
    }
  }
  return null
}
