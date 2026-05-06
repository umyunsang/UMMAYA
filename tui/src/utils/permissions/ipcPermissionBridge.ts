// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic FU-4 · IPC permission_request → toolUseConfirmQueue bridge.
//
// Diagnosis (Lead-FU-1 2026-05-04):
//   Backend emits permission_request frame → deps.ts routes to setPendingPermission
//   and the request must enter CC's toolUseConfirmQueue. Without that bridge,
//   no PermissionRequest mounts and citizens see a spinner until timeout.
//
// Fix (Option B — CC-canonical bridge):
//   Frame → synthesized ToolUseConfirm → setToolUseConfirmQueue push.
//   REPL registers its setter via registerIpcToolUseConfirmQueue; deps.ts calls
//   pushIpcPermissionRequest whenever a permission_request frame arrives.
//   CC's PermissionRequest then mounts its canonical permission component.
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
import type { PermissionUpdate } from './PermissionUpdateSchema.js'
import { LookupPrimitive } from '../../tools/LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from '../../tools/ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { VerifyPrimitive } from '../../tools/VerifyPrimitive/VerifyPrimitive.js'
import { SubmitPrimitive } from '../../tools/SubmitPrimitive/SubmitPrimitive.js'
import { SubscribePrimitive } from '../../tools/SubscribePrimitive/SubscribePrimitive.js'
import type { IPCFrame } from '../../ipc/frames.generated.js'
import type { Tool } from '../../Tool.js'
import { createAssistantMessage } from '../../utils/messages.js'
import { getOrCreateKosmosBridge } from '../../ipc/bridgeSingleton.js'
import { resolvePermissionDecision } from '../../store/pendingPermissionSlot.js'

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
}

// ---------------------------------------------------------------------------
// Primitive kind → Tool mapping
// ---------------------------------------------------------------------------

type PrimitiveKind = PermissionRequestFrame['primitive_kind']

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function primitiveKindToTool(kind: PrimitiveKind): Tool {
  switch (kind) {
    case 'lookup':
      return LookupPrimitive
    case 'resolve_location':
      return ResolveLocationPrimitive
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
 * the REPL's toolUseConfirmQueue. CC's PermissionRequest chooses the
 * canonical renderer for the synthesized tool; KOSMOS primitives intentionally
 * fall through to FallbackPermissionRequest.
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

  // Synthesize a minimal AssistantMessage stub so PermissionRequest has a
  // stable message reference for CC's prompt logging and display path.
  const assistantMessage = createAssistantMessage({
    content: `[kosmos permission gate] ${frame.description_en}`,
  })

  // Build the description shown in the CC permission banner (English primary,
  // Korean secondary per CC UX convention).
  const description = `${frame.description_en}\n${frame.description_ko}`

  // The toolUseID we emit here is the frame's request_id — it becomes the
  // key used in the permission_response frame so the backend can correlate.
  const toolUseID = frame.request_id
  const fallbackToolId =
    (frame as { tool_id?: string | null }).tool_id ||
    frame.worker_id ||
    frame.primitive_kind
  const frameArguments = (frame as { arguments?: unknown }).arguments
  const input = {
    tool_id: fallbackToolId,
    params: {},
    ...(isRecord(frameArguments) ? frameArguments : {}),
  } as Record<string, unknown>
  if (!isRecord(input.params)) {
    input.params = {}
  }

  // -------------------------------------------------------------------------
  // onAllow — citizen approved.
  // CC FallbackPermissionRequest sends an addRules/allow update when the
  // citizen chooses "Yes, and don't ask again". KOSMOS maps that canonical CC
  // update to the backend's session-grant wire token while keeping the UI
  // itself byte-aligned with the CC permission prompt.
  // -------------------------------------------------------------------------
  function onAllow(
    _updatedInput?: unknown,
    permissionUpdates: PermissionUpdate[] = [],
  ): void {
    const decision = permissionUpdates.some(
      (update) => update.type === 'addRules' && update.behavior === 'allow',
    )
      ? 'allow_session'
      : 'allow_once'
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
    setter!((prev) => prev.filter((item) => item.toolUseID !== toolUseID))
  }

  // -------------------------------------------------------------------------
  // onReject — citizen denied
  // Audit-4 P0-5 fix: send 'deny' (Spec 1978 ADR-0002 canonical wire token);
  // backend accepts both 'deny' and legacy 'denied' (frame_schema.py:580).
  // -------------------------------------------------------------------------
  function onReject(): void {
    _sendPermissionResponse(frame, 'deny')
    // Wave-2 G3 fix (F-gamma-01) — same rationale as onAllow.
    resolvePermissionDecision(frame.request_id, 'denied')
    setter!((prev) => prev.filter((item) => item.toolUseID !== toolUseID))
  }

  const confirm: ToolUseConfirm = {
    assistantMessage,
    tool,
    description,
    input,
    toolUseContext: {} as ToolUseConfirm['toolUseContext'],
    toolUseID,
    permissionResult: 'ask',
    permissionPromptStartTimeMs: performance.now(),
    onUserInteraction() {
      // No-op: IPC permission requests do not have auto-approval classifiers.
    },
    onAbort() {
      // Citizen aborted (Ctrl-C): treat as deny for fail-closed.
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
 * The fix routes through the bridge singleton instead of writing protocol
 * frames to terminal stdout.
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
    // backend is the single source of truth for the canonical receipt id.
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
