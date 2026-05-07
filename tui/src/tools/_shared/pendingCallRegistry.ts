// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic ζ #2297 Phase 0b · T007
//
// PendingCallRegistry — session-scoped registry that correlates outbound
// tool_call frames (dispatched by dispatchPrimitive.ts) to their matching
// inbound tool_result frames (routed by llmClient.ts).
//
// Contract: contracts/tui-primitive-dispatcher.md I-D4
// Data model: data-model.md § 3

import type { ToolResultFrame } from '../../ipc/frames.generated.js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PendingCall {
  callId: string
  primitive: 'lookup' | 'resolve_location' | 'verify' | 'submit'
  resolve: (frame: ToolResultFrame) => void
  reject: (err: Error) => void
  timeoutHandle: ReturnType<typeof setTimeout>
  startMs: number
}

// ---------------------------------------------------------------------------
// PendingCallRegistry
// ---------------------------------------------------------------------------

/**
 * Session-scoped registry for in-flight primitive dispatches.
 *
 * Lifecycle:
 *   - `register()` — called by dispatchPrimitive immediately before sending the
 *     IPC tool_call frame.
 *   - `resolve()` — called by llmClient's tool_result arm on frame arrival.
 *   - `reject()` — called on timeout expiry (FR-006).
 *   - `clear()` — called on session teardown to cancel all pending timeouts.
 *
 * I-D4 invariants:
 *   - Throws on duplicate callId (assert-once semantics).
 *   - resolve/reject are idempotent: returns false if no matching pending call.
 *   - Concurrent calls with distinct callId are non-interfering (Map is
 *     single-threaded JS; no locking needed).
 */
export class PendingCallRegistry {
  private _pending = new Map<string, PendingCall>()
  // KOSMOS hotfix #2519 — race-safe buffering for ToolResultFrame frames
  // that arrive BEFORE the matching dispatchPrimitive call has registered
  // (the backend's _dispatch_primitive runs as a parallel asyncio.Task and
  // can complete in <1s for cached / mock adapters, often beating the
  // SDK's tool_use block parse → Tool.call() invocation timeline).
  private _buffered = new Map<string, ToolResultFrame>()

  /**
   * Register a new pending call.
   *
   * If a matching tool_result frame has already arrived (buffered), the
   * caller's `resolve` is fired synchronously and the entry is NOT added
   * to `_pending` — keeping invariant size() == in-flight calls.
   *
   * @throws {Error} if callId is already registered (duplicate detection).
   */
  register(call: Omit<PendingCall, 'startMs'>): void {
    if (this._pending.has(call.callId)) {
      throw new Error(
        `PendingCallRegistry: duplicate callId="${call.callId}" — assert-once semantics violated`,
      )
    }
    // Race-safe path: if the result frame already arrived, drain the buffer
    // and resolve immediately without ever putting the entry on _pending.
    const buffered = this._buffered.get(call.callId)
    if (buffered) {
      this._buffered.delete(call.callId)
      clearTimeout(call.timeoutHandle)
      call.resolve(buffered)
      return
    }
    const entry: PendingCall = { ...call, startMs: Date.now() }
    this._pending.set(call.callId, entry)
  }

  /**
   * Resolve a pending call with the matching tool_result frame.
   * Clears the timeout handle and invokes the call's resolve callback.
   *
   * If no pending call exists yet (race: backend was faster than the SDK
   * tool_use parse), the frame is buffered until `register()` arrives.
   *
   * @returns true if a matching pending call was found and resolved;
   *          false if the callId was unknown (frame buffered for later
   *          register).
   */
  resolve(callId: string, frame: ToolResultFrame): boolean {
    const call = this._pending.get(callId)
    if (!call) {
      // Buffer the frame; the matching register() will pick it up.
      this._buffered.set(callId, frame)
      return false
    }
    clearTimeout(call.timeoutHandle)
    this._pending.delete(callId)
    call.resolve(frame)
    return true
  }

  /**
   * Reject a pending call with an error (timeout or explicit cancellation).
   * Clears the timeout handle and invokes the call's reject callback.
   *
   * @returns true if a matching pending call was found and rejected;
   *          false if the callId is unknown.
   */
  reject(callId: string, err: Error): boolean {
    const call = this._pending.get(callId)
    if (!call) return false
    clearTimeout(call.timeoutHandle)
    this._pending.delete(callId)
    call.reject(err)
    return true
  }

  /**
   * Check if a callId is currently registered.
   */
  has(callId: string): boolean {
    return this._pending.has(callId)
  }

  /**
   * Number of in-flight pending calls.
   */
  size(): number {
    return this._pending.size
  }

  /**
   * Cancel all pending calls at session teardown.
   * Clears all timeout handles to prevent leaks.
   */
  clear(): void {
    for (const call of this._pending.values()) {
      clearTimeout(call.timeoutHandle)
      call.reject(new Error('Session teardown — pending call cancelled'))
    }
    this._pending.clear()
  }
}
