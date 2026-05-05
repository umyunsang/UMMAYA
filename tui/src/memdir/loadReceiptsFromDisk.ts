// SPDX-License-Identifier: Apache-2.0
// Wave-5 (PR #2773 — F-gamma-04 micro-fix): /consent list must read
// prior-session receipts from disk, not just the in-memory ref bridge.
//
// Spec 035 + Spec 1636 ledger lives at:
//   ~/.kosmos/memdir/user/consent/<YYYY-MM-DD>.jsonl
// Each line is a PermissionReceipt JSON (G11b adds rcpt-opt-* placeholders
// that are filtered out — the backend echo replaces them with canonical ids).

import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import {
  PermissionReceipt,
  type PermissionReceiptT,
} from '../schemas/ui-l2/permission.js';

const LEDGER_DIR = path.join(os.homedir(), '.kosmos', 'memdir', 'user', 'consent');

/**
 * Synchronously load every persisted PermissionReceipt from the disk ledger.
 * Skips optimistic placeholders (rcpt-opt-*) and Zod-invalid lines. Returns
 * receipts sorted reverse-chronological (newest first) — matches the
 * ConsentListView render order.
 */
export function loadReceiptsFromDisk(): PermissionReceiptT[] {
  if (!fs.existsSync(LEDGER_DIR)) return [];
  const entries: PermissionReceiptT[] = [];
  let files: string[];
  try {
    files = fs.readdirSync(LEDGER_DIR).filter(f => f.endsWith('.jsonl'));
  } catch {
    return [];
  }
  for (const file of files) {
    let content: string;
    try {
      content = fs.readFileSync(path.join(LEDGER_DIR, file), 'utf8');
    } catch {
      continue;
    }
    for (const line of content.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      let parsed: unknown;
      try {
        parsed = JSON.parse(trimmed);
      } catch {
        continue;
      }
      const result = PermissionReceipt.safeParse(parsed);
      if (!result.success) continue;
      // Filter optimistic placeholders — backend echo replaces them with
      // canonical receipt_id (Wave-4 G11b pattern).
      if (result.data.receipt_id.startsWith('rcpt-opt-')) continue;
      entries.push(result.data);
    }
  }
  // De-duplicate by receipt_id (in-session ref + disk may overlap when echo
  // already arrived). Keep the latest decided_at when duplicates occur.
  const dedup = new Map<string, PermissionReceiptT>();
  for (const r of entries) {
    const existing = dedup.get(r.receipt_id);
    if (!existing || existing.decided_at < r.decided_at) {
      dedup.set(r.receipt_id, r);
    }
  }
  return [...dedup.values()].sort((a, b) =>
    a.decided_at < b.decided_at ? 1 : -1,
  );
}

/**
 * Merge disk-persisted receipts with the in-session ref. Disk wins on
 * canonical id collisions (backend echo authoritative); in-session-only
 * (optimistic rcpt-opt-*) entries pass through.
 */
export function mergeReceipts(
  inSession: readonly PermissionReceiptT[],
  fromDisk: readonly PermissionReceiptT[],
): PermissionReceiptT[] {
  const byId = new Map<string, PermissionReceiptT>();
  for (const r of fromDisk) byId.set(r.receipt_id, r);
  for (const r of inSession) {
    if (!byId.has(r.receipt_id)) byId.set(r.receipt_id, r);
  }
  return [...byId.values()].sort((a, b) =>
    a.decided_at < b.decided_at ? 1 : -1,
  );
}
