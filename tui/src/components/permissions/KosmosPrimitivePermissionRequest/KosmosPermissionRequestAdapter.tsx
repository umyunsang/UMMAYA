// SPDX-License-Identifier: Apache-2.0
// Epic 1 finish — CC switch arm adapter for KOSMOS primitives.
//
// Bridges the CC `PermissionRequestProps` interface (used by the
// `permissionComponentForTool` switch in PermissionRequest.tsx) to the
// KOSMOS `KosmosPrimitivePermissionRequestProps` interface.
//
// One adapter per primitive:
//   LookupPermissionRequestAdapter    → bypasses (returns null; lookup is read-only)
//   VerifyPermissionRequestAdapter    → Layer 1 (green ⓵)
//   SubmitPermissionRequestAdapter    → Layer 2 / 3 based on is_irreversible
//
// CC reference: .references/claude-code-sourcemap/restored-src/src/components/
//   permissions/PermissionRequest.tsx:47-82 (permissionComponentForTool switch).
// KOSMOS adaptation: wraps onAllow / onReject callbacks to satisfy both the
//   CC pipeline (toolUseConfirm.onAllow / onReject) and the KOSMOS modal API
//   (onDecision). receipt_id is surfaced in the footer via
//   context.kosmos_receipt_id injected by the backend echo frame handler.

import React, { useCallback } from 'react'
import { resolveAdapter } from '../../../services/api/adapterManifest.js'
import type { PermissionRequestProps } from '../PermissionRequest.js'
import type { PrimitiveDecision } from './KosmosPrimitivePermissionRequest.js'
import { KosmosPrimitivePermissionRequest } from './KosmosPrimitivePermissionRequest.js'
import { setPendingPermissionDecision } from '../../../utils/permissions/ipcPermissionBridge.js'

// ---------------------------------------------------------------------------
// LookupPermissionRequestAdapter — null bypass (read-only primitive)
// ---------------------------------------------------------------------------

/**
 * Lookup is read-only and side-effect-free. It always has
 * `checkPermissions → { behavior: 'allow' }` so this adapter is defensive-
 * only: it returns null and immediately calls `onDone`.
 *
 * The CC pipeline will never show the gauntlet for lookup because
 * `checkPermissions` returns `{ behavior: 'allow' }`, but `permissionComponentForTool`
 * must still return _some_ component for the switch statement to compile.
 */
export function LookupPermissionRequestAdapter({
  onDone,
}: PermissionRequestProps): React.ReactNode {
  // Defensive: dismiss immediately without showing any modal.
  // In practice this adapter is never rendered — lookup bypasses via
  // checkPermissions allow.
  React.useEffect(() => {
    onDone()
  }, [onDone])
  return null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Extract the adapter name for display in the modal body.
 * Prefers the synced backend manifest name; falls back to input.tool_id.
 */
function resolveToolDisplayName(input: Record<string, unknown>): string {
  const toolId = typeof input['tool_id'] === 'string' ? input['tool_id'] : ''
  if (toolId) {
    const entry = resolveAdapter(toolId)
    if (entry?.name) return entry.name
  }
  return toolId || '알 수 없는 어댑터'
}

/**
 * Maps a KOSMOS PrimitiveDecision to the CC `onAllow` / `onReject` callbacks.
 * - allow_once / allow_session → `onAllow(input, [])`
 * - deny → `onReject()`
 *
 * Audit-4 P0-5 fix (2026-05-04): the citizen's exact decision (`allow_once`
 * vs `allow_session`) is stashed via `setPendingPermissionDecision` BEFORE
 * `onAllow` runs. The CC `onAllow` signature carries no decision payload, so
 * the IPC bridge previously collapsed both Y and A to a single `'granted'`
 * wire token — defeating the backend's `_session_grants` cache (the citizen
 * was re-prompted on every same-tool call within a session). Stashing the
 * decision keyed by `toolUseID` (= `request_id`) lets the bridge's
 * `onAllow` closure read the citizen's exact intent.
 */
function handleDecision(
  decision: PrimitiveDecision,
  toolUseConfirm: PermissionRequestProps['toolUseConfirm'],
  onDone: () => void,
  onReject: () => void,
): void {
  if (decision === 'allow_once' || decision === 'allow_session') {
    setPendingPermissionDecision(toolUseConfirm.toolUseID, decision)
    toolUseConfirm.onAllow(toolUseConfirm.input as Record<string, unknown>, [])
    onDone()
  } else {
    // deny
    toolUseConfirm.onReject()
    onReject()
    onDone()
  }
}

// ---------------------------------------------------------------------------
// VerifyPermissionRequestAdapter — Layer 1 (green ⓵)
// ---------------------------------------------------------------------------

export function VerifyPermissionRequestAdapter({
  toolUseConfirm,
  onDone,
  onReject,
  workerBadge,
}: PermissionRequestProps): React.ReactNode {
  const toolName = resolveToolDisplayName(
    toolUseConfirm.input as Record<string, unknown>,
  )

  const handleDecisionMemo = useCallback(
    (decision: PrimitiveDecision) => {
      handleDecision(decision, toolUseConfirm, onDone, onReject)
    },
    [toolUseConfirm, onDone, onReject],
  )

  return (
    <KosmosPrimitivePermissionRequest
      primitive="verify"
      toolName={toolName}
      workerBadge={
        workerBadge
          ? { label: workerBadge.label, color: workerBadge.color }
          : undefined
      }
      onDecision={handleDecisionMemo}
    />
  )
}

// ---------------------------------------------------------------------------
// SubmitPermissionRequestAdapter — Layer 2 / 3 (isIrreversible from manifest)
// ---------------------------------------------------------------------------

export function SubmitPermissionRequestAdapter({
  toolUseConfirm,
  onDone,
  onReject,
  workerBadge,
}: PermissionRequestProps): React.ReactNode {
  const input = toolUseConfirm.input as Record<string, unknown>
  const toolId = typeof input['tool_id'] === 'string' ? input['tool_id'] : ''

  // Resolve is_irreversible from the backend manifest (Spec 024 field).
  // Falls back to false (Layer 2) for unknown adapters or manifest-not-synced.
  const manifestEntry = toolId ? resolveAdapter(toolId) : undefined
  const isIrreversible: boolean =
    (manifestEntry as unknown as { is_irreversible?: boolean } | undefined)
      ?.is_irreversible ?? false

  const toolName = resolveToolDisplayName(input)

  const handleDecisionMemo = useCallback(
    (decision: PrimitiveDecision) => {
      handleDecision(decision, toolUseConfirm, onDone, onReject)
    },
    [toolUseConfirm, onDone, onReject],
  )

  return (
    <KosmosPrimitivePermissionRequest
      primitive="submit"
      toolName={toolName}
      isIrreversible={isIrreversible}
      workerBadge={
        workerBadge
          ? { label: workerBadge.label, color: workerBadge.color }
          : undefined
      }
      onDecision={handleDecisionMemo}
    />
  )
}

// ---------------------------------------------------------------------------
