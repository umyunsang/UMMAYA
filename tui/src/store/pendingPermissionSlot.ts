// KOSMOS-original — Epic #2077 T018
// Promise-based pending permission slot + FIFO queue.
//
// Spec refs:
//   contracts/pending-permission-slot.md
//   data-model.md § 4
//
// Architecture: This module is a standalone imperative state machine that
// lives outside the reducer.  The reducer's existing pending_permission field
// (PermissionRequest, used by PermissionGauntletModal subscriptions) is separate
// from this layer.  The queue here owns the Promise lifecycle and the timeout
// handle; the reducer is notified via callbacks when the active slot changes so
// that React components can subscribe.
//
// The module exports three functions that are re-exported from session-store.ts:
//   setPendingPermission     — enqueue + return Promise<PermissionDecision>
//   resolvePermissionDecision — resolve head or queued request
//   getActivePermission      — selector helper (non-reactive snapshot)

import type { PermissionDecision } from '../ipc/codec.js'

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/** The shape exposed to PermissionGauntletModal (no resolver, no enqueued_at) */
export interface PendingPermissionRequest {
  request_id: string
  primitive_kind: 'lookup' | 'resolve_location' | 'verify' | 'submit'
  description_ko: string
  description_en: string
  risk_level: 'low' | 'medium' | 'high'
  receipt_id: string
  enqueued_at: number
}

// ---------------------------------------------------------------------------
// Internal types
// ---------------------------------------------------------------------------

/** Internal — extends the public type with the Promise resolver and timeout bookkeeping */
interface QueuedRequest extends PendingPermissionRequest {
  resolver: (decision: PermissionDecision) => void
  timeoutHandle: ReturnType<typeof setTimeout> | null
}

// ---------------------------------------------------------------------------
// Timeout config
// ---------------------------------------------------------------------------

function getPermissionTimeoutMs(): number {
  // Bun / browser both expose process.env; fall back to 300 s per Spec 033.
  const raw = typeof process !== 'undefined'
    ? process.env['KOSMOS_PERMISSION_TIMEOUT_SEC']
    : undefined
  const secs = raw !== undefined && raw !== '' ? Number(raw) : 300
  return (Number.isFinite(secs) && secs > 0 ? secs : 300) * 1000
}

// ---------------------------------------------------------------------------
// Module-level mutable state
// ---------------------------------------------------------------------------

// Head of the permission queue (currently displayed to citizen).
let activeSlot: QueuedRequest | null = null

// FIFO overflow queue for requests arriving while slot is occupied.
const pendingQueue: QueuedRequest[] = []

// Listeners notified when activeSlot changes (so React components re-render).
type SlotListener = () => void
const slotListeners = new Set<SlotListener>()

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function notifyListeners(): void {
  for (const listener of slotListeners) listener()
}

/**
 * Returns true when request_id already exists in the active slot or the
 * pending queue.  Used to enforce idempotent-on-duplicate behaviour.
 */
function isDuplicate(request_id: string): boolean {
  if (activeSlot?.request_id === request_id) return true
  return pendingQueue.some((q) => q.request_id === request_id)
}

/**
 * Install a new request as the active head and arm its timeout.
 */
function activateHead(queued: QueuedRequest): void {
  const timeoutHandle = setTimeout(() => {
    resolvePermissionDecision(queued.request_id, 'timeout')
  }, getPermissionTimeoutMs())

  activeSlot = { ...queued, timeoutHandle }
  notifyListeners()
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Subscribe to slot-change notifications.
 * Returns an unsubscribe function — matches the `useSyncExternalStore`
 * subscription contract so components can hook into this directly.
 */
export function subscribeToPermissionSlot(listener: SlotListener): () => void {
  slotListeners.add(listener)
  return () => slotListeners.delete(listener)
}

/**
 * Enqueue a permission request.
 *
 * Returns a Promise that resolves to the citizen's decision (or 'timeout').
 *
 * Idempotent on duplicate request_id: immediately resolves to 'denied' and
 * emits a console.warn with tag [kosmos.permission.duplicate].
 */
export function setPendingPermission(
  request: PendingPermissionRequest,
): Promise<PermissionDecision> {
  // Idempotency guard — same request_id arriving twice.
  if (isDuplicate(request.request_id)) {
    console.warn(
      `[kosmos.permission.duplicate] request_id already tracked: ${request.request_id}. Resolving second call to 'denied'.`,
    )
    return Promise.resolve('denied' as PermissionDecision)
  }

  return new Promise<PermissionDecision>((resolve) => {
    const queued: QueuedRequest = {
      ...request,
      resolver: resolve,
      timeoutHandle: null,
    }

    if (activeSlot === null) {
      // Slot is free — become head immediately.
      activateHead(queued)
    } else {
      // Slot occupied — append to FIFO queue (no timeout until head is resolved).
      pendingQueue.push(queued)
    }
  })
}

/**
 * Resolve a pending permission request by its request_id.
 *
 * If request_id is the active head: clear timeout, invoke resolver, promote
 * the next item from the FIFO queue (if any) as the new head.
 *
 * If request_id is in the FIFO queue: invoke resolver, splice it out.
 *
 * If request_id is unknown: no-op.
 */
export function resolvePermissionDecision(
  request_id: string,
  decision: PermissionDecision,
): void {
  if (activeSlot?.request_id === request_id) {
    // Clear in-flight timeout.
    if (activeSlot.timeoutHandle !== null) {
      clearTimeout(activeSlot.timeoutHandle)
    }

    const resolver = activeSlot.resolver
    activeSlot = null

    // Promote next queued item before calling resolver so that components
    // observing getActivePermission see the next item synchronously on
    // their next render.
    const next = pendingQueue.shift() ?? null
    if (next !== null) {
      activateHead(next)
    } else {
      notifyListeners()
    }

    // Resolve AFTER slot update so any synchronous subscribers that call
    // getActivePermission() in the .then() callback see the new head.
    resolver(decision)
    return
  }

  // Search FIFO queue.
  const idx = pendingQueue.findIndex((q) => q.request_id === request_id)
  if (idx >= 0) {
    const item = pendingQueue[idx]
    if (item !== undefined) {
      pendingQueue.splice(idx, 1)
      item.resolver(decision)
    }
  }
  // Unknown request_id → no-op (per contract).
}

/**
 * Snapshot accessor — returns the currently active request without the
 * internal resolver / timeoutHandle fields.  Safe to expose to React
 * components via useSessionStore selector.
 */
export function getActivePermission(): PendingPermissionRequest | null {
  if (activeSlot === null) return null
  const { resolver: _r, timeoutHandle: _t, ...pub } = activeSlot
  return pub
}

/**
 * Returns the current FIFO queue depth (active slot not counted).
 * Used for OTEL attribute kosmos.permission.queue_depth.
 */
export function getPermissionQueueDepth(): number {
  return pendingQueue.length
}

/**
 * Reset all slot state — used in tests to isolate test cases.
 * Not for production use.
 */
export function _resetPermissionSlotForTest(): void {
  if (activeSlot?.timeoutHandle !== null) {
    if (activeSlot !== null) clearTimeout(activeSlot.timeoutHandle!)
  }
  activeSlot = null
  pendingQueue.length = 0
  slotListeners.clear()
}
