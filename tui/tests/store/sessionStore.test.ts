// SPDX-License-Identifier: Apache-2.0
// T015 + T019 (cohesion-merged) — Epic #2077 K-EXAONE tool wiring.
//
// T015: Session save/resume preserves tool_use + tool_result blocks
//   (FR-008/SC-008).  The TUI's session serialization path is the
//   SESSION_EVENT load round-trip in session-store.ts — messages are
//   stored as plain JSON in the backend JSONL and replayed into the
//   store via SESSION_EVENT{event:'load', payload:{messages:[...]}}.
//   These tests verify that ToolCall + ToolResult records survive that
//   serialization boundary byte-equivalent.
//
// T019: pendingPermissionSlot lifecycle — 7 cases from
//   contracts/pending-permission-slot.md § Test coverage.

import { describe, it, expect, beforeEach, afterEach, spyOn } from 'bun:test'
import {
  dispatchSessionAction,
  getSessionSnapshot,
} from '../../src/store/session-store'
import type { ToolCall, ToolResult } from '../../src/store/session-store'
import {
  setPendingPermission,
  resolvePermissionDecision,
  getActivePermission,
  getPermissionQueueDepth,
  _resetPermissionSlotForTest,
} from '../../src/store/pendingPermissionSlot'
import type { PendingPermissionRequest } from '../../src/store/pendingPermissionSlot'

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function resetStore(): void {
  dispatchSessionAction({ type: 'SESSION_EVENT', event: 'new', payload: {} })
}

/** Build a minimal PendingPermissionRequest fixture */
function makeRequest(overrides?: Partial<PendingPermissionRequest>): PendingPermissionRequest {
  return {
    request_id: 'req-001',
    primitive_kind: 'send',
    description_ko: '출생신고 서류 제출',
    description_en: 'Submit birth registration document',
    risk_level: 'high',
    receipt_id: 'rcpt-abc123',
    enqueued_at: performance.now(),
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// T015 — session save/resume preserves tool blocks (FR-008 / SC-008)
// ---------------------------------------------------------------------------

describe('T015 — tool_blocks round-trip via SESSION_EVENT load (FR-008)', () => {
  beforeEach(() => {
    resetStore()
  })

  it('tool_blocks_round_trip_save_resume — 2-turn fixture round-trips cleanly', () => {
    // Build a 2-turn fixture transcript in-memory:
    //   turn 1: user text + assistant message with [text_block, tool_use_block(id='A')]
    //           + user message with [tool_result(tool_use_id='A')]
    // Serialize via JSON.stringify → parse → SESSION_EVENT load (the JSONL
    // boundary the backend crosses when resuming a session).

    const assistantMsgId = 'assist-turn1'
    const userMsgId = 'user-turn1'
    const userResultMsgId = 'user-tool-result-turn1'

    // Step 1 — populate store as if the agentic loop ran.
    dispatchSessionAction({
      type: 'USER_INPUT',
      message_id: userMsgId,
      text: '강남구 24시간 응급실 어디야?',
    })
    dispatchSessionAction({
      type: 'ASSISTANT_CHUNK',
      message_id: assistantMsgId,
      delta: '응급실을 조회하겠습니다.',
      done: true,
    })
    dispatchSessionAction({
      type: 'TOOL_CALL',
      message_id: assistantMsgId,
      tool_call: {
        call_id: 'call-A',
        name: 'nmc_emergency_search',
        arguments: { region: '강남구' },
      },
    })
    dispatchSessionAction({
      type: 'TOOL_RESULT',
      call_id: 'call-A',
      envelope: { ok: true, data: [{ name: '강남세브란스병원', tel: '02-2019-3114' }] },
    })

    // Step 2 — serialize the current store state to JSON (simulating backend
    // JSONL save) and then reload it (simulating resume).
    const snap = getSessionSnapshot()
    const serialized: unknown[] = Array.from(snap.message_order).map((id) => {
      const msg = snap.messages.get(id)!
      // JSON round-trip (mirrors JSONL write → read on the Python backend)
      return JSON.parse(JSON.stringify({
        id: msg.id,
        role: msg.role,
        chunks: msg.chunks,
        done: msg.done,
        tool_calls: msg.tool_calls,
        tool_results: msg.tool_results,
      }))
    })

    // Step 3 — also include the assistant message that carries the tool_call
    // (it may not be in message_order if TOOL_CALL arrived after ASSISTANT_CHUNK;
    //  in this fixture we dispatched ASSISTANT_CHUNK first, so it is present).
    // Confirm the assistant message with tool blocks is serialized.
    const assistantSerialized = serialized.find(
      (m) => (m as Record<string, unknown>)['id'] === assistantMsgId
    ) as Record<string, unknown> | undefined
    expect(assistantSerialized).toBeDefined()

    const toolCallsSerialized = assistantSerialized!['tool_calls'] as ToolCall[]
    const toolResultsSerialized = assistantSerialized!['tool_results'] as ToolResult[]

    // Verify 1 tool_use block present in serialized form
    expect(toolCallsSerialized).toHaveLength(1)
    expect(toolCallsSerialized[0]!.call_id).toBe('call-A')
    expect(toolCallsSerialized[0]!.name).toBe('nmc_emergency_search')
    expect(toolCallsSerialized[0]!.arguments).toEqual({ region: '강남구' })

    // Verify 1 tool_result block present in serialized form
    expect(toolResultsSerialized).toHaveLength(1)
    expect(toolResultsSerialized[0]!.call_id).toBe('call-A')
    expect((toolResultsSerialized[0]!.envelope as Record<string, unknown>)['ok']).toBe(true)

    // Step 4 — reload via SESSION_EVENT load (resume path) on a fresh store
    resetStore()
    dispatchSessionAction({
      type: 'SESSION_EVENT',
      event: 'load',
      payload: {
        session_id: 'ses-round-trip',
        messages: serialized,
      },
    })

    const reloaded = getSessionSnapshot()
    expect(reloaded.session_id).toBe('ses-round-trip')

    // Find the reloaded assistant message
    const reloadedAssistant = reloaded.messages.get(assistantMsgId)
    expect(reloadedAssistant).toBeDefined()

    // FR-008: tool_use blocks survived round-trip byte-equivalent
    expect(reloadedAssistant!.tool_calls).toHaveLength(1)
    expect(reloadedAssistant!.tool_calls[0]!.call_id).toBe('call-A')
    expect(reloadedAssistant!.tool_calls[0]!.name).toBe('nmc_emergency_search')
    expect(reloadedAssistant!.tool_calls[0]!.arguments).toEqual({ region: '강남구' })

    // FR-008: tool_result blocks survived round-trip byte-equivalent
    expect(reloadedAssistant!.tool_results).toHaveLength(1)
    expect(reloadedAssistant!.tool_results[0]!.call_id).toBe('call-A')

    // FR-052: done flag forced to true on resume (no streaming animation)
    expect(reloadedAssistant!.done).toBe(true)
  })

  it('tool_blocks_round_trip_at_50_turn_scale — 50-turn fixture: 100% record retention (SC-008)', () => {
    // Build a synthetic 50-turn session: each turn has 1 tool_use block +
    // 1 tool_result block. Serialize → reload → assert 50 tool_use +
    // 50 tool_result blocks all paired correctly by call_id.
    const TURNS = 50

    for (let i = 0; i < TURNS; i++) {
      const msgId = `assist-${i}`
      const callId = `call-${i}`

      dispatchSessionAction({
        type: 'ASSISTANT_CHUNK',
        message_id: msgId,
        delta: `Turn ${i} response`,
        done: true,
      })
      dispatchSessionAction({
        type: 'TOOL_CALL',
        message_id: msgId,
        tool_call: {
          call_id: callId,
          name: 'nmc_emergency_search',
          arguments: { turn: i },
        },
      })
      dispatchSessionAction({
        type: 'TOOL_RESULT',
        call_id: callId,
        envelope: { ok: true, turn: i },
      })
    }

    const snap = getSessionSnapshot()

    // Serialize all messages in message_order
    const serialized: unknown[] = Array.from(snap.message_order).map((id) => {
      const msg = snap.messages.get(id)!
      return JSON.parse(JSON.stringify({
        id: msg.id,
        role: msg.role,
        chunks: msg.chunks,
        done: msg.done,
        tool_calls: msg.tool_calls,
        tool_results: msg.tool_results,
      }))
    })

    // Reload on a fresh store
    resetStore()
    dispatchSessionAction({
      type: 'SESSION_EVENT',
      event: 'load',
      payload: {
        session_id: 'ses-50-turns',
        messages: serialized,
      },
    })

    const reloaded = getSessionSnapshot()

    // Tally total tool_use and tool_result blocks across all messages
    let totalToolCalls = 0
    let totalToolResults = 0
    let allPaired = true

    for (let i = 0; i < TURNS; i++) {
      const msgId = `assist-${i}`
      const callId = `call-${i}`
      const msg = reloaded.messages.get(msgId)

      // Message must survive
      expect(msg).toBeDefined()
      if (!msg) { allPaired = false; continue }

      totalToolCalls += msg.tool_calls.length
      totalToolResults += msg.tool_results.length

      // Pairing: each call_id must have a matching tool_result
      const hasMatchingResult = msg.tool_results.some((r) => r.call_id === callId)
      if (!hasMatchingResult) allPaired = false

      // Arguments integrity
      expect(msg.tool_calls[0]?.arguments).toEqual({ turn: i })
    }

    // SC-008: 100% retention — all 50 tool_use + 50 tool_result blocks present
    expect(totalToolCalls).toBe(TURNS)
    expect(totalToolResults).toBe(TURNS)
    expect(allPaired).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// T019 — pendingPermissionSlot lifecycle (7 cases per contract)
// ---------------------------------------------------------------------------

describe('T019 — pendingPermissionSlot lifecycle (contracts/pending-permission-slot.md)', () => {
  beforeEach(() => {
    _resetPermissionSlotForTest()
  })

  afterEach(() => {
    _resetPermissionSlotForTest()
  })

  // Case 1: stores active when slot empty
  it('stores active when slot empty', () => {
    const req = makeRequest({ request_id: 'req-case1' })
    // Fire-and-forget — we don't await the promise in this test
    void setPendingPermission(req)

    const active = getActivePermission()
    expect(active).not.toBeNull()
    expect(active!.request_id).toBe('req-case1')
    expect(active!.primitive_kind).toBe('send')
    expect(active!.description_ko).toBe('출생신고 서류 제출')
    expect(active!.risk_level).toBe('high')
    expect(active!.receipt_id).toBe('rcpt-abc123')

    // Clean up: resolve so timeout doesn't leak into subsequent tests
    resolvePermissionDecision('req-case1', 'denied')
  })

  // Case 2: queues when occupied
  it('queues when occupied', () => {
    const req1 = makeRequest({ request_id: 'req-case2a' })
    const req2 = makeRequest({ request_id: 'req-case2b' })

    void setPendingPermission(req1)
    void setPendingPermission(req2)

    // First request must be the active slot
    const active = getActivePermission()
    expect(active).not.toBeNull()
    expect(active!.request_id).toBe('req-case2a')

    // Second request is queued (depth = 1, not counting active slot)
    expect(getPermissionQueueDepth()).toBe(1)

    resolvePermissionDecision('req-case2a', 'denied')
    resolvePermissionDecision('req-case2b', 'denied')
  })

  // Case 3: resolve shifts queue — after queueing two, resolving first makes second active
  it('resolve shifts queue', async () => {
    const req1 = makeRequest({ request_id: 'req-case3a' })
    const req2 = makeRequest({ request_id: 'req-case3b' })

    void setPendingPermission(req1)
    void setPendingPermission(req2)

    // Sanity: req1 is active
    expect(getActivePermission()!.request_id).toBe('req-case3a')
    expect(getPermissionQueueDepth()).toBe(1)

    // Resolve the head
    resolvePermissionDecision('req-case3a', 'granted')

    // Queue shifts: req2 is now the active slot, queue depth drops to 0
    const newActive = getActivePermission()
    expect(newActive).not.toBeNull()
    expect(newActive!.request_id).toBe('req-case3b')
    expect(getPermissionQueueDepth()).toBe(0)

    // Clean up
    resolvePermissionDecision('req-case3b', 'denied')
  })

  // Case 4: Promise resolves with decision
  it('Promise resolves with decision', async () => {
    const req = makeRequest({ request_id: 'req-case4' })
    const promise = setPendingPermission(req)

    // Resolve with 'granted'
    resolvePermissionDecision('req-case4', 'granted')

    const decision = await promise
    expect(decision).toBe('granted')
  })

  // Case 5: timeout resolves to 'timeout' after configured ms
  it("timeout resolves to 'timeout' after configured ms", async () => {
    // Use a 1-second timeout via env var
    const originalEnv = process.env['UMMAYA_PERMISSION_TIMEOUT_SEC']
    process.env['UMMAYA_PERMISSION_TIMEOUT_SEC'] = '1'

    // Reset so getPermissionTimeoutMs() re-reads env on next call.
    // The module caches nothing — it reads on each getPermissionTimeoutMs() call.
    _resetPermissionSlotForTest()

    try {
      const req = makeRequest({ request_id: 'req-case5' })
      const promise = setPendingPermission(req)

      // Wait 1.2 s for the 1 s timeout to fire
      await new Promise<void>((r) => setTimeout(r, 1200))

      const decision = await promise
      expect(decision).toBe('timeout')
    } finally {
      // Restore env regardless of test outcome
      if (originalEnv === undefined) {
        delete process.env['UMMAYA_PERMISSION_TIMEOUT_SEC']
      } else {
        process.env['UMMAYA_PERMISSION_TIMEOUT_SEC'] = originalEnv
      }
      _resetPermissionSlotForTest()
    }
  }, 5000)

  // Case 6: duplicate request_id resolves immediately to 'denied'
  it("duplicate request_id resolves immediately to 'denied'", async () => {
    const req = makeRequest({ request_id: 'req-case6' })

    // Spy on console.warn to verify the ummaya.permission.duplicate warning
    const warnSpy = spyOn(console, 'warn').mockImplementation(() => {})

    try {
      // First call — becomes active
      void setPendingPermission(req)

      // Second call with same request_id — must resolve immediately to 'denied'
      const secondPromise = setPendingPermission({ ...req })
      const decision = await secondPromise

      expect(decision).toBe('denied')

      // Verify the duplicate warning was emitted with the expected tag
      const warnCalls = warnSpy.mock.calls
      const duplicateWarned = warnCalls.some(
        (args) =>
          typeof args[0] === 'string' &&
          args[0].includes('ummaya.permission.duplicate'),
      )
      expect(duplicateWarned).toBe(true)
    } finally {
      warnSpy.mockRestore()
      resolvePermissionDecision('req-case6', 'denied')
    }
  })

  // Case 7: unknown id resolve is no-op — no error thrown, no state change
  it('unknown id resolve is no-op', () => {
    const req = makeRequest({ request_id: 'req-case7' })
    void setPendingPermission(req)

    const activeBefore = getActivePermission()
    expect(activeBefore).not.toBeNull()
    expect(activeBefore!.request_id).toBe('req-case7')

    // Attempt to resolve an ID that was never registered
    expect(() => {
      resolvePermissionDecision('completely-unknown-id', 'granted')
    }).not.toThrow()

    // Active slot must be unchanged
    const activeAfter = getActivePermission()
    expect(activeAfter).not.toBeNull()
    expect(activeAfter!.request_id).toBe('req-case7')

    // Clean up
    resolvePermissionDecision('req-case7', 'denied')
  })
})
