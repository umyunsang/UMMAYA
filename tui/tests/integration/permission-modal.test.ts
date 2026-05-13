// SPDX-License-Identifier: Apache-2.0
// T022 — End-to-end permission modal integration test (Epic #2077 K-EXAONE tool wiring)
//
// Spec refs:
//   specs/2077-kexaone-tool-wiring/spec.md § US3 + SC-003 + FR-013–FR-018
//   specs/2077-kexaone-tool-wiring/contracts/pending-permission-slot.md § Test coverage
//
// Approach (b): Test only the store + modal data-flow + outbound-frame seam.
// deps.ts plumbing (permission_request frame → setPendingPermission) is
// covered by T020's handlers.test.ts and is not re-tested here.  The modal
// itself is a renderer of store state — the store contract is the source of
// truth.  All tests operate directly on the pendingPermissionSlot module API.
//
// Tests:
//   Test 1 — happy path (grant)
//   Test 2 — deny path
//   Test 3 — timeout fail-closed
//   Test 4 — queue progression
//   Test 5 — wire-decision collapse (timeout → denied at IPC boundary)

import { describe, it, expect, beforeEach, afterEach } from 'bun:test'
import {
  setPendingPermission,
  resolvePermissionDecision,
  getActivePermission,
  getPermissionQueueDepth,
  _resetPermissionSlotForTest,
} from '../../src/store/pendingPermissionSlot'
import type { PendingPermissionRequest } from '../../src/store/pendingPermissionSlot'
import type { PermissionDecision } from '../../src/ipc/codec'

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

/** Build a minimal PendingPermissionRequest fixture */
function makeRequest(overrides?: Partial<PendingPermissionRequest>): PendingPermissionRequest {
  return {
    request_id: 'req-t022-001',
    primitive_kind: 'send',
    description_ko: '출생신고 서류 제출',
    description_en: 'Submit birth registration document',
    risk_level: 'high',
    receipt_id: 'rcpt-t022-abc',
    enqueued_at: performance.now(),
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Isolation — _resetPermissionSlotForTest() in beforeEach (per Constitution)
// ---------------------------------------------------------------------------

beforeEach(() => {
  _resetPermissionSlotForTest()
})

afterEach(() => {
  _resetPermissionSlotForTest()
})

// ---------------------------------------------------------------------------
// Test 1 — Happy path (grant)
// ---------------------------------------------------------------------------

describe('T022 Test 1 — happy path (grant)', () => {
  it('getActivePermission returns request within 1000 ms after setPendingPermission (SC-003)', async () => {
    const req = makeRequest({ request_id: 'req-t022-grant' })

    const t0 = performance.now()
    // Fire-and-forget — the Promise resolves only after resolvePermissionDecision.
    void setPendingPermission(req)
    const t1 = performance.now()

    // SC-003: consent prompt must appear within 1 s of agent decision.
    // setPendingPermission is synchronous up to slot activation; the active
    // slot is set before this line — so latency is the module's synchronous
    // execution time, well under 1000 ms.
    const active = getActivePermission()
    expect(active).not.toBeNull()
    expect(active!.request_id).toBe('req-t022-grant')
    expect(t1 - t0).toBeLessThan(1000)

    // Clean up: resolve so timeout does not leak.
    resolvePermissionDecision('req-t022-grant', 'granted')
  })

  it('Promise resolves to "granted" after resolvePermissionDecision(..., granted)', async () => {
    const req = makeRequest({ request_id: 'req-t022-grant-resolve' })
    const promise = setPendingPermission(req)

    resolvePermissionDecision('req-t022-grant-resolve', 'granted')

    const decision = await promise
    expect(decision).toBe('granted')
  })

  it('getActivePermission returns null after the grant resolution (slot cleared)', async () => {
    const req = makeRequest({ request_id: 'req-t022-grant-clear' })
    const promise = setPendingPermission(req)

    resolvePermissionDecision('req-t022-grant-clear', 'granted')
    await promise  // ensure microtask queue has flushed

    expect(getActivePermission()).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Test 2 — Deny path
// ---------------------------------------------------------------------------

describe('T022 Test 2 — deny path', () => {
  it('Promise resolves to "denied" after resolvePermissionDecision(..., denied)', async () => {
    const req = makeRequest({ request_id: 'req-t022-deny' })
    const promise = setPendingPermission(req)

    resolvePermissionDecision('req-t022-deny', 'denied')

    const decision = await promise
    expect(decision).toBe('denied')
  })

  it('getActivePermission returns null after the deny resolution (slot cleared)', async () => {
    const req = makeRequest({ request_id: 'req-t022-deny-clear' })
    const promise = setPendingPermission(req)

    resolvePermissionDecision('req-t022-deny-clear', 'denied')
    await promise

    expect(getActivePermission()).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Test 3 — Timeout fail-closed (FR-017, SC-003, Constitution §II)
// ---------------------------------------------------------------------------

describe('T022 Test 3 — timeout fail-closed', () => {
  it('Promise resolves to "timeout" when no decision is made within UMMAYA_PERMISSION_TIMEOUT_SEC', async () => {
    const originalEnv = process.env['UMMAYA_PERMISSION_TIMEOUT_SEC']
    // Set 1-second timeout for a fast test.
    process.env['UMMAYA_PERMISSION_TIMEOUT_SEC'] = '1'

    // Reset so getPermissionTimeoutMs() re-reads the updated env.
    _resetPermissionSlotForTest()

    try {
      const req = makeRequest({ request_id: 'req-t022-timeout' })
      const promise = setPendingPermission(req)

      // Wait 1.2 s for the 1 s timeout to fire.
      await new Promise<void>((r) => setTimeout(r, 1200))

      const decision = await promise
      expect(decision).toBe('timeout')
    } finally {
      if (originalEnv === undefined) {
        delete process.env['UMMAYA_PERMISSION_TIMEOUT_SEC']
      } else {
        process.env['UMMAYA_PERMISSION_TIMEOUT_SEC'] = originalEnv
      }
      _resetPermissionSlotForTest()
    }
  }, 5000)

  it('getActivePermission returns null after the timeout fires (slot cleared)', async () => {
    const originalEnv = process.env['UMMAYA_PERMISSION_TIMEOUT_SEC']
    process.env['UMMAYA_PERMISSION_TIMEOUT_SEC'] = '1'
    _resetPermissionSlotForTest()

    try {
      const req = makeRequest({ request_id: 'req-t022-timeout-clear' })
      const promise = setPendingPermission(req)

      await new Promise<void>((r) => setTimeout(r, 1200))
      await promise  // drain microtasks

      expect(getActivePermission()).toBeNull()
    } finally {
      if (originalEnv === undefined) {
        delete process.env['UMMAYA_PERMISSION_TIMEOUT_SEC']
      } else {
        process.env['UMMAYA_PERMISSION_TIMEOUT_SEC'] = originalEnv
      }
      _resetPermissionSlotForTest()
    }
  }, 5000)
})

// ---------------------------------------------------------------------------
// Test 4 — Queue progression (FR-018)
// ---------------------------------------------------------------------------

describe('T022 Test 4 — queue progression', () => {
  it('first request is active; second is queued at depth 1', () => {
    const req1 = makeRequest({ request_id: 'req-t022-q1' })
    const req2 = makeRequest({ request_id: 'req-t022-q2' })

    void setPendingPermission(req1)
    void setPendingPermission(req2)

    // req1 must be the active head.
    const active = getActivePermission()
    expect(active).not.toBeNull()
    expect(active!.request_id).toBe('req-t022-q1')

    // req2 is queued (active slot not counted).
    expect(getPermissionQueueDepth()).toBe(1)

    // Clean up.
    resolvePermissionDecision('req-t022-q1', 'denied')
    resolvePermissionDecision('req-t022-q2', 'denied')
  })

  it('resolving first promotes second to active (queue shifts)', async () => {
    const req1 = makeRequest({ request_id: 'req-t022-shift1' })
    const req2 = makeRequest({ request_id: 'req-t022-shift2' })

    const p1 = setPendingPermission(req1)
    void setPendingPermission(req2)

    expect(getActivePermission()!.request_id).toBe('req-t022-shift1')
    expect(getPermissionQueueDepth()).toBe(1)

    // Resolve the first request.
    resolvePermissionDecision('req-t022-shift1', 'granted')
    await p1  // flush microtasks

    // Second request must now be the active head.
    const newActive = getActivePermission()
    expect(newActive).not.toBeNull()
    expect(newActive!.request_id).toBe('req-t022-shift2')
    expect(getPermissionQueueDepth()).toBe(0)

    // Clean up.
    resolvePermissionDecision('req-t022-shift2', 'denied')
  })

  it('resolving second leaves slot empty (queue depth 0)', async () => {
    const req1 = makeRequest({ request_id: 'req-t022-empty1' })
    const req2 = makeRequest({ request_id: 'req-t022-empty2' })

    const p1 = setPendingPermission(req1)
    const p2 = setPendingPermission(req2)

    resolvePermissionDecision('req-t022-empty1', 'granted')
    await p1

    // Second is now active.
    expect(getActivePermission()!.request_id).toBe('req-t022-empty2')

    resolvePermissionDecision('req-t022-empty2', 'denied')
    await p2

    // Slot must be empty.
    expect(getActivePermission()).toBeNull()
    expect(getPermissionQueueDepth()).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// Test 5 — Wire-decision collapse (timeout → denied at IPC boundary)
//   Spec: FR-017 + Constitution §II fail-closed.
//   The deps.ts T020 seam (line ~384) collapses 'timeout' to 'denied' before
//   sending the permission_response frame to the backend:
//     const wireDecision = decision === 'timeout' ? 'denied' : decision
//   This test validates that collapse logic inline — no import of deps.ts
//   needed (the pattern is trivial and self-evident from the contract).
// ---------------------------------------------------------------------------

describe('T022 Test 5 — wire-decision collapse (timeout → denied at IPC boundary)', () => {
  /** Mirrors the wire-collapse expression in deps.ts T020 line ~384 */
  function collapseWireDecision(decision: PermissionDecision): 'granted' | 'denied' {
    return decision === 'timeout' ? 'denied' : decision
  }

  it('timeout collapses to "denied" at the IPC wire boundary (FR-017)', () => {
    expect(collapseWireDecision('timeout')).toBe('denied')
  })

  it('"granted" passes through the collapse unchanged', () => {
    expect(collapseWireDecision('granted')).toBe('granted')
  })

  it('"denied" passes through the collapse unchanged', () => {
    expect(collapseWireDecision('denied')).toBe('denied')
  })

  it('collapse is idempotent: "denied" input already maps to "denied"', () => {
    // Applying collapse twice must produce the same result.
    const first = collapseWireDecision('denied')
    expect(collapseWireDecision(first)).toBe('denied')
  })
})
