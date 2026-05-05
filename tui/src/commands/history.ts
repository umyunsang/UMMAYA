// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — T070 /history command (FR-033, US5).
//
// 3-filter session history search with AND composition.
// Emits kosmos.ui.surface=history (FR-037).
//
// Session data is loaded from ~/.kosmos/memdir/user/sessions/ (Spec 027).
// Each JSONL file is a session; the command enumerates them and builds
// SessionHistoryEntry objects for HistorySearchDialog.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { emitSurfaceActivation } from '../observability/surface.js';
import { getKosmosSessionsDir } from '../utils/kosmosPaths.js';
import {
  applyHistoryFilters,
  type HistorySearchFilters,
  type SessionHistoryEntry,
} from '../components/history/HistorySearchDialog.js';

/**
 * Sentinel value written as the first line of KOSMOS JSONL session files by
 * the file-history compactor.  Must be skipped before parsing session entries.
 *
 * Format (literal string prefix): `file-history-snapshot`
 */
const FILE_HISTORY_SNAPSHOT_PREFIX = 'file-history-snapshot';

/**
 * Enumerate sessions from the Spec 027 memdir path.
 *
 * Each session is a JSONL file `<session_id>.jsonl`.  The first non-empty,
 * non-sentinel line is the session header (JSON object with `session_id`,
 * `started_at`, and optionally `preview`).  Lines beginning with
 * `file-history-snapshot` are skipped — they are written by the compactor
 * and are not session entries.
 *
 * We scan the first meaningful `type:"user"` or `type:"assistant"` line to
 * derive `started_at` / `preview` when the explicit header fields are absent.
 */
/**
 * Audit-7 P0-4 fix: collect JSONL session files from BOTH the root sessions
 * directory (Python lazy-create_session output) AND any sanitized-cwd
 * subdirectory (CC-style projects layout, populated by /migrate-sessions or
 * legacy CC-bridge workspaces). The /history surface previously walked only
 * the root and missed every session migrated from `~/.claude/projects/`.
 *
 * Returns an array of `{ filePath, sessionId }` so the caller can defer the
 * JSONL parse + filter pipeline.
 */
function collectAllSessionJsonl(sessionsDirPath: string): Array<{ filePath: string; sessionId: string }> {
  const collected: Array<{ filePath: string; sessionId: string }> = [];

  let entries: string[];
  try {
    entries = readdirSync(sessionsDirPath);
  } catch {
    return collected;
  }

  for (const entry of entries) {
    const fullPath = join(sessionsDirPath, entry);
    let st;
    try { st = statSync(fullPath); }
    catch { continue; }

    if (st.isDirectory()) {
      // Sanitized-cwd subdirectory (e.g. `-Users-um-yunsang-KOSMOS-tui/`).
      // Walk one level only — CC project dirs are flat.
      let subFiles: string[];
      try { subFiles = readdirSync(fullPath); }
      catch { continue; }
      for (const sub of subFiles) {
        if (!sub.endsWith('.jsonl')) continue;
        collected.push({
          filePath: join(fullPath, sub),
          sessionId: sub.replace(/\.jsonl$/, ''),
        });
      }
    } else if (st.isFile() && entry.endsWith('.jsonl')) {
      // Root-level JSONL (Python session.store output).
      collected.push({
        filePath: fullPath,
        sessionId: entry.replace(/\.jsonl$/, ''),
      });
    }
  }

  return collected;
}

function loadSessionEntries(): SessionHistoryEntry[] {
  const entries: SessionHistoryEntry[] = [];
  // Resolved lazily so KOSMOS_MEMDIR_USER overrides (tests/env) are respected.
  const sessionsDir = getKosmosSessionsDir();
  const sessionsDirPath = join(sessionsDir);

  // Audit-7 P0-4 fix: walk root + sanitized-cwd subdirectories.
  const candidates = collectAllSessionJsonl(sessionsDirPath);

  for (const { filePath, sessionId } of candidates) {

    try {
      const content = readFileSync(filePath, { encoding: 'utf-8' });
      const rawLines = content.split('\n');

      // Skip sentinel `file-history-snapshot` lines and find the first
      // parseable JSON entry to use as the session header.
      let header: Record<string, unknown> | null = null;
      for (const line of rawLines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        // Skip the file-history compactor sentinel line.
        if (trimmed.startsWith(FILE_HISTORY_SNAPSHOT_PREFIX)) continue;
        try {
          const parsed = JSON.parse(trimmed) as Record<string, unknown>;
          header = parsed;
          break;
        } catch {
          // skip malformed lines, keep searching
        }
      }

      if (!header) continue;

      // Audit-7 P0-4 stub filter: skip metadata-only stub files (1 JSON line
      // with entry_type='metadata' AND message_count=0). These were created
      // by the pre-lazy IPC boot before the create_session lazy fix landed.
      // Render `kosmos session gc-stubs` would purge them — until then we
      // hide them from /history so the citizen sees only real sessions.
      const data = header['data'] as Record<string, unknown> | undefined;
      if (
        header['entry_type'] === 'metadata' &&
        data &&
        typeof data === 'object' &&
        data['message_count'] === 0 &&
        rawLines.filter((l) => l.trim().length > 0).length === 1
      ) {
        continue;
      }

      // Derive started_at from the first entry's timestamp field when
      // the explicit session-header `started_at` field is absent.
      const startedAt: string =
        typeof header['started_at'] === 'string'
          ? header['started_at']
          : typeof header['timestamp'] === 'string'
            ? header['timestamp']
            : new Date(0).toISOString();

      // Derive preview from the first user-visible message text when
      // the explicit `preview` field is absent.
      let preview: string =
        typeof header['preview'] === 'string' ? header['preview'] : '';

      if (!preview) {
        // Walk lines looking for first `type:"user"` message text
        for (const line of rawLines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(FILE_HISTORY_SNAPSHOT_PREFIX)) continue;
          try {
            const entry = JSON.parse(trimmed) as Record<string, unknown>;
            if (entry['type'] !== 'user') continue;
            const msg = entry['message'] as Record<string, unknown> | undefined;
            const content = msg?.['content'];
            if (typeof content === 'string' && content.trim()) {
              preview = content.trim().slice(0, 200);
              break;
            } else if (Array.isArray(content)) {
              for (const block of content as Record<string, unknown>[]) {
                if (block['type'] === 'text' && typeof block['text'] === 'string') {
                  preview = (block['text'] as string).trim().slice(0, 200);
                  break;
                }
              }
              if (preview) break;
            }
          } catch {
            // skip malformed lines
          }
        }
      }

      // Extract layers_touched from all lines (scan for layer annotations)
      const layersTouched = new Set<number>();
      for (const line of rawLines) {
        if (!line.trim()) continue;
        try {
          const entry = JSON.parse(line) as Record<string, unknown>;
          const layer = entry['permission_layer'];
          if (typeof layer === 'number' && [1, 2, 3].includes(layer)) {
            layersTouched.add(layer);
          }
        } catch {
          // skip malformed lines
        }
      }

      // Determine last_active_at: prefer explicit field, fall back to started_at
      const lastActiveAt: string =
        typeof header['last_active_at'] === 'string'
          ? header['last_active_at']
          : startedAt;

      entries.push({
        session_id:
          typeof header['session_id'] === 'string'
            ? header['session_id']
            : sessionId,
        started_at: startedAt,
        last_active_at: lastActiveAt,
        preview,
        layers_touched: [...layersTouched],
      });
    } catch {
      // Skip unreadable or malformed session files
    }
  }

  // Sort descending by started_at (most recent first)
  entries.sort((a, b) => b.started_at.localeCompare(a.started_at));

  return entries;
}

// ---------------------------------------------------------------------------
// Result type
// ---------------------------------------------------------------------------

export type HistoryCommandResult = {
  /** All sessions loaded from memdir */
  sessions: SessionHistoryEntry[];
  /** Pre-applied filters (from CLI args) */
  appliedFilters: HistorySearchFilters;
  /** Pre-filtered results */
  filteredSessions: SessionHistoryEntry[];
};

// ---------------------------------------------------------------------------
// Command handler (T070)
// ---------------------------------------------------------------------------

/**
 * Execute the /history command with optional pre-applied filters.
 *
 * Emits `kosmos.ui.surface=history` (FR-037).
 *
 * @param args  Raw arguments string (e.g. "--date 2026-04-01..2026-04-25 --layer 2")
 */
export function executeHistory(args: string = ''): HistoryCommandResult {
  // FR-037: emit surface activation at command start
  emitSurfaceActivation('history');

  const sessions = loadSessionEntries();

  // Parse filters from CLI args
  const appliedFilters: HistorySearchFilters = {
    dateRange: null,
    sessionId: null,
    layer: null,
  };

  const dateMatch = args.match(/--date\s+(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})/);
  if (dateMatch) {
    appliedFilters.dateRange = { from: dateMatch[1]!, to: dateMatch[2]! };
  }

  const sessionMatch = args.match(/--session\s+([A-Za-z0-9_-]+)/);
  if (sessionMatch) {
    appliedFilters.sessionId = sessionMatch[1]!;
  }

  const layerMatch = args.match(/--layer\s+([123])/);
  if (layerMatch) {
    appliedFilters.layer = parseInt(layerMatch[1]!, 10);
  }

  const filteredSessions = applyHistoryFilters(sessions, appliedFilters);

  return { sessions, appliedFilters, filteredSessions };
}
