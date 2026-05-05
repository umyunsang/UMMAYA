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
import { resolvePermissionDecision } from '../../store/pendingPermissionSlot.js'
import type { PermissionReceiptT } from '../../schemas/ui-l2/permission.js'
import {
  aalToLayer,
  type KosmosPrimitive,
} from './aalToLayer.js'
import { resolveAdapter } from '../../services/api/adapterManifest.js'
import { getKosmosBridgeSessionId } from '../../ipc/bridgeSingleton.js'

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
// Wave-4 G11 / F-gamma-04 — optimistic receipt writer.
//
// When the citizen presses Y in the permission modal, `onAllow` fires and
// the backend receipt is written + echoed back within ~1s. But `/consent list`
// invocations that happen in that brief window see 0 receipts because the
// watcher has not yet received the echo.  Registering an optimistic writer
// here lets `onAllow` immediately add a placeholder receipt to the context,
// giving `/consent list` instant feedback with source="optimistic".  The real
// backend echo (with the canonical rcpt-* id) arrives shortly after and is
// added as a second entry; the context allows multiple receipts per tool.
// ---------------------------------------------------------------------------

/** Callback injected by REPL to eagerly add an optimistic receipt. */
let _optimisticAddReceipt: ((r: PermissionReceiptT) => void) | null = null

/**
 * Register the addReceipt callback for optimistic (pre-echo) receipt writes.
 * Call with null on REPL unmount.
 */
export function registerOptimisticAddReceipt(
  fn: ((r: PermissionReceiptT) => void) | null,
): void {
  _optimisticAddReceipt = fn
}

// ---------------------------------------------------------------------------
// Wave-4 G9 (F-beta-04 UX) — setter-null replay queue.
//
// Backend `permission_request` frames can arrive at ANY moment, including
// during REPL mount/unmount transitions when `_registeredSetter` is briefly
// null (e.g., `--continue` warm-up, suspense boundary swap, error-boundary
// remount). The prior behaviour silently dropped the frame with a warning,
// leaving the citizen with a frozen spinner that timed out at 30 s with no
// modal ever rendered.
//
// Fix: buffer the inbound `PermissionRequestFrame` payloads in this queue
// when no setter is registered. As soon as `registerIpcToolUseConfirmQueue`
// is called with a non-null setter (REPL mount), drain the queue by calling
// `pushIpcPermissionRequest` once per buffered frame. Idempotent on
// duplicate request_id (the slot's `isDuplicate` guard handles re-entry).
//
// Bound the queue at 16 entries — beyond that the backend has clearly lost
// the citizen-facing flow and additional frames are not actionable; we drop
// the oldest with a stderr warning so the audit trail surfaces the loss.
// ---------------------------------------------------------------------------

const _MAX_QUEUED_FRAMES = 16
const _pendingFrames: PermissionRequestFrame[] = []

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
 *
 * Wave-4 G9 (F-beta-04 UX): on transition from null → non-null, drain any
 * `permission_request` frames that arrived while the REPL was unmounted so
 * the citizen sees the modal instead of a 30 s timeout. Replay is
 * synchronous — the slot's idempotency guard (`isDuplicate`) absorbs any
 * duplicate the backend may resend.
 */
export function registerIpcToolUseConfirmQueue(
  setter: SetToolUseConfirmQueueFn | null,
): void {
  const wasNull = _registeredSetter === null
  _registeredSetter = setter
  if (setter !== null && wasNull && _pendingFrames.length > 0) {
    const drained = _pendingFrames.splice(0, _pendingFrames.length)
    for (const frame of drained) {
      pushIpcPermissionRequest(frame)
    }
  }
}

/**
 * Test-only helper: clear the replay queue. Production code never calls this.
 */
export function _resetPermissionBridgeForTest(): void {
  _registeredSetter = null
  _pendingFrames.length = 0
  _pendingPermissionDecisions.clear()
  _optimisticAddReceipt = null
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
    // Wave-4 G9 (F-beta-04 UX) — buffer instead of dropping. The frame is
    // replayed synchronously the moment a setter is registered (REPL mount).
    if (_pendingFrames.length >= _MAX_QUEUED_FRAMES) {
      const evicted = _pendingFrames.shift()
      process.stderr.write(
        `[KOSMOS permissionBridge WARN] replay queue full (${_MAX_QUEUED_FRAMES}); ` +
          `evicting oldest request_id=${evicted?.request_id ?? '(unknown)'}\n`,
      )
    }
    _pendingFrames.push(frame)
    process.stderr.write(
      `[kosmos.ipc.permission] setter not registered yet; queued request_id=${frame.request_id} ` +
        `(queue depth=${_pendingFrames.length})\n`,
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
    // Wave-2 G3 fix (F-gamma-01) — resolve the pendingPermissionSlot Promise
    // that `tui/src/query/deps.ts:590` is awaiting. Without this call the IPC
    // frame loop in `queryModelWithStreaming` blocks for the full 300-second
    // permission TTL, so the buffered tool_result frame is never consumed
    // and the citizen sees a frozen spinner instead of the mock fixture body
    // + the 🧪 모의 disclaimer banner. The bridge pipeline (the
    // `_sendPermissionResponse` above) was already sending the wire response
    // correctly; the slot pipeline was just orphaned because no production
    // code ever called `resolvePermissionDecision`. Both `allow_once` and
    // `allow_session` collapse to `'granted'` for the slot's binary semantics
    // (deps.ts only inspects the 3-value `'granted' | 'denied' | 'timeout'`
    // projection); the canonical 5-value wire decision was already sent above
    // and is what the backend's `_check_permission_gate` uses to populate the
    // consent ledger.
    resolvePermissionDecision(frame.request_id, 'granted')
    // Wave-4 G11 / F-gamma-04 — optimistic receipt write.
    // Write a placeholder receipt immediately so `/consent list` shows the
    // grant BEFORE the backend echo arrives (~1s later).  The watcher in
    // `usePermissionReceiptWatcher` will add the canonical receipt when the
    // echo frame arrives; both coexist in the context (distinct receipt_ids).
    // The optimistic id uses prefix `rcpt-opt-` which satisfies the schema
    // regex /^rcpt-[A-Za-z0-9_-]{8,}$/ (9 + 12 = 21 chars).
    if (_optimisticAddReceipt !== null) {
      const toolId =
        (frame as { tool_id?: string | null }).tool_id ||
        frame.worker_id ||
        frame.primitive_kind
      const manifestEntry = toolId ? resolveAdapter(toolId) : undefined
      const toolName: string = manifestEntry?.name ?? toolId ?? 'unknown'
      const isIrreversible: boolean =
        (manifestEntry as unknown as { is_irreversible?: boolean } | undefined)
          ?.is_irreversible ?? false
      const primitiveKind = frame.primitive_kind
      const layer: 1 | 2 | 3 = primitiveKind
        ? (aalToLayer(primitiveKind as KosmosPrimitive, isIrreversible) ?? 1)
        : 1
      // Build a stable alphanum suffix from request_id (trim to 12 chars)
      const suffix = frame.request_id.replace(/[^A-Za-z0-9]/g, '').slice(0, 12).padEnd(8, '0')
      const optimisticReceipt: PermissionReceiptT = {
        receipt_id: `rcpt-opt-${suffix}` as PermissionReceiptT['receipt_id'],
        layer,
        tool_name: toolName,
        decision: decision as PermissionReceiptT['decision'],
        decided_at: new Date().toISOString(),
        session_id: getKosmosBridgeSessionId() ?? 'unknown',
        revoked_at: null,
      }
      process.stderr.write(
        `RECEIPT_CTX state=optimistic source=optimistic receipt_id=${optimisticReceipt.receipt_id}\n`,
      )
      _optimisticAddReceipt(optimisticReceipt)
    }
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
    // Wave-2 G3 fix (F-gamma-01) — same rationale as onAllow.
    resolvePermissionDecision(frame.request_id, 'denied')
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
      // Wave-2 G3 fix (F-gamma-01) — same as onReject. Without this the IPC
      // frame loop holds the spinner for 300 s after Ctrl-C.
      resolvePermissionDecision(frame.request_id, 'denied')
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
