// SPDX-License-Identifier: Apache-2.0
// Epic 1 finish — addReceipt callsite hook.
//
// Wires the backend permission_response echo (Gap A fix, role="backend")
// into the PermissionReceiptContext.addReceipt() so that:
//   1. User Y/A is captured in the KOSMOS modal (KosmosPrimitivePermissionRequest).
//   2. CC pipeline routes through toolUseConfirm.onAllow (→ tool executes).
//   3. Backend writes the consent ledger and echoes back the receipt_id via
//      a PermissionResponseFrame{role: "backend"} outbound frame.
//   4. THIS HOOK detects that echo and calls addReceipt() so the context
//      (and /consent list) shows the new receipt without a round-trip.
//
// CC reference: no upstream analog (KOSMOS-original, Spec 033 + Spec 1635).
// AGENTS.md rule: zero new runtime dependencies.
// FR-018: receipt added after backend confirmation, not before.

import { useEffect, useRef } from 'react'
import { getOrCreateKosmosBridge } from '../ipc/bridgeSingleton.js'
import { isPermissionResponse } from '../ipc/codec.js'
import type { PermissionResponseFrame } from '../ipc/frames.generated.js'
import type { PermissionReceiptT } from '../schemas/ui-l2/permission.js'
import type { PermissionReceiptContextValue } from '../context/PermissionReceiptContext.js'
import { getKosmosBridgeSessionId } from '../ipc/bridgeSingleton.js'
import {
  aalToLayer,
  type KosmosPrimitive,
} from '../utils/permissions/aalToLayer.js'
import { resolveAdapter } from '../services/api/adapterManifest.js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type AddReceiptFn = PermissionReceiptContextValue['addReceipt']

// Map from the 5-value codec vocabulary to the 5-value PermissionDecisionT.
// The backend may send 'granted' or 'denied' as legacy aliases.
function _mapDecision(
  decision: PermissionResponseFrame['decision'],
): PermissionReceiptT['decision'] | null {
  switch (decision) {
    case 'allow_once':
    case 'granted': // legacy alias → allow_once
      return 'allow_once'
    case 'allow_session':
      return 'allow_session'
    case 'deny':
    case 'denied': // legacy alias → deny
      return 'deny'
    default:
      return null
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Mounts a fire-and-forget listener on the KOSMOS IPC bridge that watches
 * for `permission_response` frames emitted by the **backend** (role="backend")
 * with a non-null `receipt_id`. On receipt, calls `addReceipt()` to update
 * the PermissionReceiptContext without a separate /consent list round-trip.
 *
 * Must be rendered inside <PermissionReceiptProvider>.
 *
 * @param addReceipt - Stable callback from usePermissionReceipts().addReceipt.
 */
export function usePermissionReceiptWatcher(addReceipt: AddReceiptFn): void {
  // Stable ref so the onFrame closure never captures a stale addReceipt.
  const addReceiptRef = useRef<AddReceiptFn>(addReceipt)
  addReceiptRef.current = addReceipt

  useEffect(() => {
    const bridge = getOrCreateKosmosBridge()

    const prevHook = bridge.onFrame

    bridge.onFrame = (frame, direction, latencyMs) => {
      // Forward to any existing hook first (fire-and-forget, sync).
      prevHook?.(frame, direction, latencyMs)

      // Only process inbound frames (direction='recv') from the backend.
      if (direction !== 'recv') return

      // Guard: only permission_response echoes with a receipt_id.
      if (!isPermissionResponse(frame)) return
      const prf = frame as PermissionResponseFrame
      if ((prf as { role?: string }).role !== 'backend') return
      if (!prf.receipt_id) return

      const mappedDecision = _mapDecision(prf.decision)
      if (!mappedDecision) return // deny/timeout → no receipt to add

      // Build the PermissionReceiptT. Fields not in the IPC frame are derived:
      //   - layer: Audit-4 P0-6 fix (2026-05-04). Backend echo now carries
      //     `primitive_kind` (and the receipt context's `is_irreversible`
      //     resolved from the manifest), so the TUI can recompute the
      //     gauntlet layer (1=green / 2=orange / 3=red) via aalToLayer.
      //     Falls back to layer=1 only when primitive_kind is null
      //     (legacy backends).
      //   - tool_name: Audit-4 P0-7 fix. Backend echo now carries `tool_id`,
      //     and the TUI's adapterManifest cache returns the Korean adapter
      //     display name. Falls back to the raw tool_id, and finally to
      //     'unknown' for legacy backends.
      //   - session_id: pull from bridge singleton.
      const sessionId = getKosmosBridgeSessionId() ?? 'unknown'

      // Resolve adapter manifest entry — gives us human-readable name + the
      // is_irreversible flag needed for Layer 2/3 distinction on submit.
      const toolId =
        typeof (prf as { tool_id?: string | null }).tool_id === 'string'
          ? (prf as { tool_id: string }).tool_id
          : null
      const manifestEntry = toolId ? resolveAdapter(toolId) : undefined
      const toolName: string =
        manifestEntry?.name ?? toolId ?? 'unknown'
      const isIrreversible: boolean =
        (manifestEntry as unknown as { is_irreversible?: boolean } | undefined)
          ?.is_irreversible ?? false

      // Recompute layer from primitive_kind. aalToLayer returns null for
      // lookup (read-only, no receipt expected); guard with conservative
      // fallback to layer=1 in that defensive case.
      const primitiveKind = (prf as { primitive_kind?: string | null })
        .primitive_kind
      const computedLayer: 1 | 2 | 3 = primitiveKind
        ? (aalToLayer(
            primitiveKind as KosmosPrimitive,
            isIrreversible,
          ) ?? 1)
        : 1

      const receipt: PermissionReceiptT = {
        receipt_id: prf.receipt_id,
        layer: computedLayer,
        tool_name: toolName,
        decision: mappedDecision,
        decided_at: prf.ts ?? new Date().toISOString(),
        session_id: sessionId,
        revoked_at: null,
      }

      // Call addReceipt via ref — safe from async closures.
      addReceiptRef.current(receipt)
    }

    return () => {
      // Restore previous hook on unmount (cleanup).
      bridge.onFrame = prevHook
    }
  // addReceipt is stable (useCallback in PermissionReceiptProvider).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
