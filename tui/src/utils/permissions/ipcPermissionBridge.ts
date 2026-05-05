// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic FU-4 · IPC permission_request → toolUseConfirmQueue bridge.
//
// Diagnosis (Lead-FU-1 2026-05-04):
//   Backend emits permission_request frame → deps.ts routes to setPendingPermission
//   but the PermissionGauntletModal consumer was removed in Spec 1979. The 4-arm
//   permissionComponentForTool switch (PermissionRequest.tsx:92-102) IS wired but
//   toolUseConfirmQueue is empty so nothing mounts. Citizens see a 1m38s+ spinner.
//
// Fix (Option B — CC-canonical bridge):
//   Frame → synthesized ToolUseConfirm → setToolUseConfirmQueue push.
//   REPL registers its setter via registerIpcToolUseConfirmQueue; deps.ts calls
//   pushIpcPermissionRequest whenever a permission_request frame arrives.
//   The 4-arm switch then auto-mounts the correct adapter.
//
// CC reference:
//   tui/src/utils/swarm/leaderPermissionBridge.ts — same register/push pattern
//   used for in-process teammate permission delegation.
//
// Spec refs:
//   specs/2077-kexaone-tool-wiring/contracts/pending-permission-slot.md
//   docs/requirements/kosmos-migration-tree.md § UI-C

import type {
  PermissionRequestFrame,
  PermissionResponseFrame,
} from '../../ipc/frames.generated.js'
import type { ToolUseConfirm } from '../../components/permissions/PermissionRequest.js'
import { LookupPrimitive } from '../../tools/LookupPrimitive/LookupPrimitive.js'
import { VerifyPrimitive } from '../../tools/VerifyPrimitive/VerifyPrimitive.js'
import { SubmitPrimitive } from '../../tools/SubmitPrimitive/SubmitPrimitive.js'
import { SubscribePrimitive } from '../../tools/SubscribePrimitive/SubscribePrimitive.js'
import type { IPCFrame } from '../../ipc/frames.generated.js'
import type { Tool } from '../../Tool.js'
import { createAssistantMessage } from '../../utils/messages.js'
import { getOrCreateKosmosBridge } from '../../ipc/bridgeSingleton.js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SetToolUseConfirmQueueFn = (
  updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[],
) => void

// ---------------------------------------------------------------------------
// Module-level registry — one setter per REPL mount
// ---------------------------------------------------------------------------

let _registeredSetter: SetToolUseConfirmQueueFn | null = null

// ---------------------------------------------------------------------------
// Audit-4 P0-5 fix — per-request decision stash so the KOSMOS adapter can
// communicate `allow_once` vs `allow_session` to onAllow (whose CC-canonical
// signature is parameter-free). Key: PermissionRequestFrame.request_id.
// Cleared in onAllow / onReject to bound memory.
// ---------------------------------------------------------------------------

const _pendingPermissionDecisions = new Map<
  string,
  'allow_once' | 'allow_session'
>()

/**
 * Adapter-only setter. The KOSMOS PrimitivePermissionRequest adapter calls
 * this with the citizen's exact decision JUST BEFORE invoking
 * `toolUseConfirm.onAllow(...)` so the wire frame carries the right
 * vocabulary. Keyed by the frame's `request_id` (which is the same string
 * used as `toolUseConfirm.toolUseID`). Safe to call repeatedly: last write
 * wins; consumed at most once by `_sendPermissionResponse`.
 */
export function setPendingPermissionDecision(
  requestId: string,
  decision: 'allow_once' | 'allow_session',
): void {
  _pendingPermissionDecisions.set(requestId, decision)
}

/**
 * Register the REPL's setToolUseConfirmQueue.
 * Call with null on REPL unmount to avoid stale references.
 */
export function registerIpcToolUseConfirmQueue(
  setter: SetToolUseConfirmQueueFn | null,
): void {
  _registeredSetter = setter
}

// ---------------------------------------------------------------------------
// Primitive kind → Tool mapping
// ---------------------------------------------------------------------------

type PrimitiveKind = PermissionRequestFrame['primitive_kind']

function primitiveKindToTool(kind: PrimitiveKind): Tool {
  switch (kind) {
    case 'lookup':
    case 'resolve_location':
      return LookupPrimitive
    case 'verify':
      return VerifyPrimitive
    case 'submit':
      return SubmitPrimitive
    case 'subscribe':
      return SubscribePrimitive
    default: {
      // Exhaustive fallback — future primitive kinds fall through to verify
      // (Layer 1, safest default per Constitution §II fail-closed).
      const _exhaustive: never = kind
      console.warn(`[kosmos.ipc.permission] unknown primitive_kind=${String(_exhaustive)}, falling back to VerifyPrimitive`)
      return VerifyPrimitive
    }
  }
}

// ---------------------------------------------------------------------------
// Bridge — IPC frame → ToolUseConfirm synthesis
// ---------------------------------------------------------------------------

/**
 * Synthesize a ToolUseConfirm from a PermissionRequestFrame and push it into
 * the REPL's toolUseConfirmQueue. The REPL's permissionComponentForTool switch
 * then auto-mounts the correct adapter (VerifyPermissionRequestAdapter, etc.).
 *
 * onAllow / onReject forward the citizen's decision as a permission_response
 * frame via the kosmos bridge's write channel (process.stdout NDJSON).
 *
 * Must be called AFTER registerIpcToolUseConfirmQueue has been called by REPL.
 * If no setter is registered (e.g. REPL unmounted), logs a warning and no-ops.
 */
export function pushIpcPermissionRequest(frame: PermissionRequestFrame): void {
  const setter = _registeredSetter
  if (setter === null) {
    console.warn(
      `[kosmos.ipc.permission] no setter registered — cannot present permission modal for request_id=${frame.request_id}. Is REPL mounted?`,
    )
    return
  }

  const tool = primitiveKindToTool(frame.primitive_kind)

  // Synthesize a minimal AssistantMessage stub so permissionComponentForTool
  // has a stable reference (the adapter components read it for display context).
  const assistantMessage = createAssistantMessage({
    content: `[kosmos permission gate] ${frame.description_en}`,
  })

  // Build the description shown in the CC permission banner (English primary,
  // Korean secondary per CC UX convention).
  const description = `${frame.description_en}\n${frame.description_ko}`

  // The toolUseID we emit here is the frame's request_id — it becomes the
  // key used in the permission_response frame so the backend can correlate.
  const toolUseID = frame.request_id

  // -------------------------------------------------------------------------
  // onAllow — citizen approved.
  // Audit-4 P0-5 fix: read the citizen's exact decision from the
  // module-level stash (set by KosmosPermissionRequestAdapter just before
  // it called us). Defaults to 'allow_once' for non-KOSMOS adapters that
  // never set a decision. Without this, the wire collapsed both Y and A
  // to 'granted' → backend's _session_grants cache never activated and
  // citizens were re-prompted on every same-tool call within a session.
  // -------------------------------------------------------------------------
  function onAllow(): void {
    const decision =
      _pendingPermissionDecisions.get(frame.request_id) ?? 'allow_once'
    _pendingPermissionDecisions.delete(frame.request_id)
    _sendPermissionResponse(frame, decision)
    setter!((prev) => prev.filter((item) => item.toolUseID !== toolUseID))
  }

  // -------------------------------------------------------------------------
  // onReject — citizen denied
  // Audit-4 P0-5 fix: send 'deny' (Spec 1978 ADR-0002 canonical wire token);
  // backend accepts both 'deny' and legacy 'denied' (frame_schema.py:580).
  // -------------------------------------------------------------------------
  function onReject(): void {
    _pendingPermissionDecisions.delete(frame.request_id)
    _sendPermissionResponse(frame, 'deny')
    setter!((prev) => prev.filter((item) => item.toolUseID !== toolUseID))
  }

  const confirm: ToolUseConfirm = {
    assistantMessage,
    tool,
    description,
    input: {
      // Audit-4 P0-10 fix — prefer the explicit `tool_id` field (added to
      // PermissionRequestFrame schema in the same audit). Fall back to
      // worker_id (legacy / pre-fix backends used `worker_id="main"`) and
      // finally to the primitive verb. The KOSMOS adapter feeds this into
      // resolveAdapter() to produce the human-readable Korean modal title.
      tool_id:
        (frame as { tool_id?: string | null }).tool_id ||
        frame.worker_id ||
        frame.primitive_kind,
      params: {},
    },
    toolUseContext: {} as ToolUseConfirm['toolUseContext'],
    toolUseID,
    permissionResult: 'ask',
    permissionPromptStartTimeMs: performance.now(),
    onUserInteraction() {
      // No-op: IPC permission requests do not have auto-approval classifiers.
    },
    onAbort() {
      // Citizen aborted (Ctrl-C): treat as deny for fail-closed.
      _pendingPermissionDecisions.delete(frame.request_id)
      _sendPermissionResponse(frame, 'deny')
    },
    onAllow,
    onReject,
    async recheckPermission() {
      // No-op: permission mode changes do not affect in-flight IPC gates.
    },
  }

  setter((prev) => [...prev, confirm])
}

// ---------------------------------------------------------------------------
// Internal — emit permission_response frame
// ---------------------------------------------------------------------------

/**
 * Emit a permission_response frame back to the Python backend.
 *
 * Audit-4 P0-8 fix (2026-05-04): the prior implementation called
 * `process.stdout.write(encodeFrame(...))` directly. In the KOSMOS TUI
 * architecture (`tui/src/ipc/bridge.ts`) the backend is a CHILD process
 * of the TUI — `process.stdout` is the citizen's terminal, NOT the IPC
 * pipe. The backend reads from its own stdin, which is the TUI's
 * `proc.stdin`. Writing to TUI stdout therefore spilled raw NDJSON
 * (`{"version":"1.0","session_id":...}`) into the rendered UI on every
 * /consent revoke decision, leaving the citizen staring at protocol bytes.
 *
 * The fix routes through the bridge singleton — same pattern used by
 * `consentBridge.ts:135` (`bridge.send({...consent_revoke_request...})`).
 *
 * If the bridge has already exited, `bridge.send()` returns false; we log
 * to stderr (NEVER stdout — see `bridge.ts:200-208` rationale) and proceed
 * silently because the citizen's UI flow has already completed.
 */
function _sendPermissionResponse(
  frame: PermissionRequestFrame,
  // Audit-4 P0-5 vocabulary — Spec 1978 ADR-0002 canonical wire tokens
  // (`allow_once` / `allow_session` / `deny`); legacy `granted` / `denied`
  // remain accepted by the backend frame_schema for backward-compat.
  decision: 'allow_once' | 'allow_session' | 'deny' | 'granted' | 'denied',
): void {
  const responseFrame: PermissionResponseFrame = {
    version: '1.0',
    session_id: frame.session_id,
    correlation_id: frame.correlation_id,
    ts: new Date().toISOString(),
    role: 'tui',
    frame_seq: 0,
    // Spec 1978 ADR-0002 + Spec 033 — the wire vocabulary now distinguishes
    // allow_once from allow_session so the backend's _session_grants cache
    // (stdio.py:_check_permission_gate) activates on `A`. `deny` is the
    // canonical denial token; legacy `granted` / `denied` continue to work.
    kind: 'permission_response',
    request_id: frame.request_id,
    decision,
    // Audit-4 P0-11 fix — TUI no longer generates a receipt_id. The
    // backend is the single source of truth for the canonical
    // `rcpt-<hex>` string written to ~/.kosmos/memdir/user/consent/.
    // Two receipt_ids on the wire (TUI + backend) created an audit-trail
    // discrepancy where the TUI-side ID could leak into OTEL spans
    // while the backend silently overwrote it. Backend echoes back the
    // canonical value via the role="backend" PermissionResponseFrame
    // observed by usePermissionReceiptWatcher.
    receipt_id: null,
  }

  const bridge = getOrCreateKosmosBridge()
  const sent = bridge.send(responseFrame as unknown as IPCFrame)
  if (!sent) {
    // Backend already exited — write a diagnostic to stderr so PTY scenarios
    // surface the drop without polluting stdout.
    process.stderr.write(
      `[KOSMOS permissionBridge WARN] permission_response drop ` +
        `(backend exited) request_id=${frame.request_id} decision=${decision}\n`,
    )
  }
}
