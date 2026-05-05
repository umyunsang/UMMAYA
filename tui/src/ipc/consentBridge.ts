// SPDX-License-Identifier: Apache-2.0
// Epic 2 — consent revoke IPC bridge (arm 22/23).
//
// Provides `requestRevoke()` — a Promise-based wrapper around the
// consent_revoke_request / consent_revoke_response IPC round-trip.
//
// The bridge is the TS-side analog of kosmos.plugins.consent_bridge.IPCConsentBridge;
// it uses the same _pending Map pattern used by the existing permission
// round-trip in stdio.py (_pending_perms).
//
// Usage (from REPL.tsx onSubmit):
//   import { requestRevoke } from '../ipc/consentBridge.js'
//   const result = await requestRevoke(receiptId, { scope: 'once' })
//
// Integration notes:
// - The bridge registers itself as a listener on the IPC bridge singleton
//   (getOrCreateKosmosBridge) so `_handleConsentRevokeResponse` is called
//   whenever the backend emits a consent_revoke_response frame.
// - `_resetPending()` is exposed for tests to clear state between cases.
// - Default timeout: 5 s (KOSMOS_CONSENT_REVOKE_TIMEOUT_MS env var overrides).

import { getOrCreateKosmosBridge } from './bridgeSingleton.js'
import type { ConsentRevokeResponseFrame, IPCFrame } from './frames.generated.js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RevokeScope = 'once' | 'session-all'

export type RevokeBridgeResult =
  | { ok: true; revokedAt: string; recordHash: string | null }
  | { ok: false; error: 'already_revoked' | 'not_found' | 'io_error' | 'timeout' | 'unknown' }

type PendingEntry = {
  resolve: (result: RevokeBridgeResult) => void
  reject: (err: Error) => void
  timeoutHandle: ReturnType<typeof setTimeout>
}

// ---------------------------------------------------------------------------
// Default timeout
// ---------------------------------------------------------------------------

const DEFAULT_TIMEOUT_MS = (() => {
  const env = globalThis.process?.env?.['KOSMOS_CONSENT_REVOKE_TIMEOUT_MS']
  const parsed = env ? parseInt(env, 10) : NaN
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 5000
})()

// ---------------------------------------------------------------------------
// Internal pending map
// ---------------------------------------------------------------------------

const _pending = new Map<string, PendingEntry>()

// ---------------------------------------------------------------------------
// Frame handler — called for every incoming backend frame
// ---------------------------------------------------------------------------

export function _handleConsentRevokeResponse(frame: ConsentRevokeResponseFrame): void {
  const entry = _pending.get(frame.request_id)
  if (!entry) {
    // No pending entry means a stale or duplicate response — silently drop.
    return
  }

  clearTimeout(entry.timeoutHandle)
  _pending.delete(frame.request_id)

  if (frame.ok) {
    entry.resolve({
      ok: true,
      revokedAt: frame.revoked_at ?? new Date().toISOString(),
      recordHash: frame.record_hash ?? null,
    })
  } else {
    const errorCode = frame.error ?? 'unknown'
    entry.resolve({
      ok: false,
      error: errorCode as RevokeBridgeResult['error'],
    })
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Request revocation of a consent receipt via IPC.
 *
 * Sends a `consent_revoke_request` frame to the backend and waits for
 * a matching `consent_revoke_response` frame.  Resolves with the outcome;
 * never rejects (timeout → `{ ok: false, error: 'timeout' }`).
 *
 * @param receiptId  The `rcpt-<id>` value to revoke.
 * @param opts.scope `"once"` (default) or `"session-all"`.
 * @param opts.timeoutMs  Override default 5 s timeout.
 * @param opts.reason  Optional free-text reason for the ledger (PIPA §36).
 */
export function requestRevoke(
  receiptId: string,
  opts: {
    scope?: RevokeScope
    timeoutMs?: number
    reason?: string
    sessionId?: string
    correlationId?: string
  } = {},
): Promise<RevokeBridgeResult> {
  const {
    scope = 'once',
    timeoutMs = DEFAULT_TIMEOUT_MS,
    reason,
    sessionId = '',
    correlationId = crypto.randomUUID(),
  } = opts

  // request_id is the correlation key that the backend echoes back in the response.
  const requestId = crypto.randomUUID()

  const promise = new Promise<RevokeBridgeResult>((resolve, reject) => {
    const timeoutHandle = setTimeout(() => {
      _pending.delete(requestId)
      resolve({ ok: false, error: 'timeout' })
    }, timeoutMs)

    _pending.set(requestId, { resolve, reject, timeoutHandle })
  })

  // Emit the request frame via the bridge singleton.
  // bridge.send() is synchronous (returns bool); false means backend exited.
  const bridge = getOrCreateKosmosBridge()
  const sent = bridge.send({
    kind: 'consent_revoke_request',
    session_id: sessionId,
    correlation_id: correlationId,
    ts: new Date().toISOString(),
    role: 'tui',
    request_id: requestId,
    receipt_id: receiptId,
    scope,
    reason: reason ?? null,
  } as IPCFrame)

  if (!sent) {
    // Backend already exited — cancel the pending entry immediately.
    const entry = _pending.get(requestId)
    if (entry) {
      clearTimeout(entry.timeoutHandle)
      _pending.delete(requestId)
      entry.resolve({ ok: false, error: 'io_error' })
    }
  }

  return promise
}

// ---------------------------------------------------------------------------
// Frame dispatch hook — wire this into the bridge's onFrame
// ---------------------------------------------------------------------------

/**
 * Register the consent revoke response handler on the given bridge instance.
 * Called once at TUI startup from bridgeSingleton.ts (or from REPL.tsx init).
 *
 * The bridge singleton's `onFrame` hook is fire-and-forget; this function
 * installs a listener that routes `consent_revoke_response` frames to
 * `_handleConsentRevokeResponse`.
 */
export function installConsentRevokeBridgeListener(): void {
  const bridge = getOrCreateKosmosBridge()
  const existingOnFrame = bridge.onFrame
  bridge.onFrame = (frame: IPCFrame, direction: 'recv' | 'send', latencyMs: number) => {
    if (direction === 'recv' && frame.kind === 'consent_revoke_response') {
      _handleConsentRevokeResponse(frame as ConsentRevokeResponseFrame)
    }
    existingOnFrame?.(frame, direction, latencyMs)
  }
}

// ---------------------------------------------------------------------------
// Test seam
// ---------------------------------------------------------------------------

/**
 * Clear all pending entries.  Only for use in unit tests.
 */
export function _resetPending(): void {
  for (const entry of _pending.values()) {
    clearTimeout(entry.timeoutHandle)
  }
  _pending.clear()
}
