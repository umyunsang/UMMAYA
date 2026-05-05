// SPDX-License-Identifier: Apache-2.0
// Wave-4 G9 (F-beta-04 UX) — dispatchPrimitive permission-aware watchdog.
//
// Verifies:
//   1. Baseline: no permission modal active → timeout fires at timeoutMs.
//   2. Permission modal active during await → timer extends beyond timeoutMs.
//   3. After modal resolved + result frame arrives → returns success.

import { test, expect, describe, beforeEach } from 'bun:test'
import { dispatchPrimitive } from './dispatchPrimitive.js'
import { PendingCallRegistry } from './pendingCallRegistry.js'
import {
  setPendingPermission,
  resolvePermissionDecision,
  _resetPermissionSlotForTest,
} from '../../store/pendingPermissionSlot.js'
import type { IPCBridge } from '../../ipc/bridge.js'
import type { ToolUseContext } from '../../Tool.js'
import type { ToolResultFrame } from '../../ipc/frames.generated.js'

function fakeContext(toolUseId: string): ToolUseContext {
  return {
    toolUseId,
    options: {
      sessionId: 'test-session',
      commands: [],
      debug: false,
      mainLoopModel: 'test',
      tools: [],
      verbose: false,
      thinkingConfig: {},
      mcpClients: [],
      mcpResources: {},
      isNonInteractiveSession: true,
    },
  } as unknown as ToolUseContext
}

function fakeBridge(): IPCBridge {
  return {
    send: () => true,
    frames: () =>
      ({
        [Symbol.asyncIterator]: () => ({
          next: () => Promise.resolve({ done: true, value: undefined }),
        }),
      }) as unknown as AsyncIterable<never>,
    close: () => Promise.resolve(),
    proc: {} as ReturnType<typeof Bun.spawn>,
    applied_frame_seqs: new Set(),
    setSessionCredentials: () => {},
    lastSeenCorrelationId: null,
    lastSeenFrameSeq: null,
  } as unknown as IPCBridge
}

function fakeResult(callId: string): ToolResultFrame {
  return {
    version: '1.0',
    session_id: 'test-session',
    correlation_id: 'test-corr',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    kind: 'tool_result',
    call_id: callId,
    envelope: { kind: 'lookup', result: { ok: true, hits: [] } },
  } as unknown as ToolResultFrame
}

describe('G9 — dispatchPrimitive permission-aware watchdog', () => {
  let registry: PendingCallRegistry

  beforeEach(() => {
    registry = new PendingCallRegistry()
    _resetPermissionSlotForTest()
  })

  test('baseline: no modal active → times out at configured timeoutMs', async () => {
    const start = Date.now()
    const result = await dispatchPrimitive({
      primitive: 'lookup',
      args: {},
      context: fakeContext('g9-baseline'),
      registry,
      bridge: fakeBridge(),
      timeoutMs: 1500,
    })
    const elapsed = Date.now() - start
    expect((result.data as { ok: boolean }).ok).toBe(false)
    expect((result.data as { error: { kind: string } }).error.kind).toBe(
      'timeout',
    )
    // Watchdog ticks every max(1000, timeoutMs/5) → 1000ms here. Allow ±1.5
    // ticks of slack so the assertion is not flaky on slower CI.
    expect(elapsed).toBeGreaterThanOrEqual(1300)
    expect(elapsed).toBeLessThanOrEqual(3500)
  })

  test('permission modal active → timer extends, then result resolves', async () => {
    // Pre-arm a pending permission so the watchdog sees the slot occupied.
    const permPromise = setPendingPermission({
      request_id: 'g9-modal-1',
      primitive_kind: 'lookup',
      description_ko: 'NMC 응급실',
      description_en: 'NMC ER',
      risk_level: 'high',
      receipt_id: '',
      enqueued_at: performance.now(),
    })

    const dispatchPromise = dispatchPrimitive({
      primitive: 'lookup',
      args: {},
      context: fakeContext('g9-modal-call'),
      registry,
      bridge: fakeBridge(),
      timeoutMs: 1500,
    })

    // Wait past the baseline 1.5 s. With the permission slot occupied, the
    // watchdog must NOT have rejected yet.
    await new Promise((r) => setTimeout(r, 2200))
    expect(registry.has('g9-modal-call')).toBe(true)

    // Citizen grants → slot resolves → backend dispatches → result arrives.
    resolvePermissionDecision('g9-modal-1', 'granted')
    await permPromise
    registry.resolve('g9-modal-call', fakeResult('g9-modal-call'))

    const result = await dispatchPromise
    expect((result.data as { ok: boolean }).ok).toBe(true)
  })

  test('modal resolves WITHOUT result frame → fresh budget then times out', async () => {
    const permPromise = setPendingPermission({
      request_id: 'g9-modal-2',
      primitive_kind: 'lookup',
      description_ko: 'NMC',
      description_en: 'NMC',
      risk_level: 'high',
      receipt_id: '',
      enqueued_at: performance.now(),
    })
    const start = Date.now()
    const dispatchPromise = dispatchPrimitive({
      primitive: 'lookup',
      args: {},
      context: fakeContext('g9-no-result'),
      registry,
      bridge: fakeBridge(),
      timeoutMs: 1500,
    })

    // Resolve modal at 800ms; backend never replies.
    setTimeout(() => resolvePermissionDecision('g9-modal-2', 'granted'), 800)
    const result = await dispatchPromise
    await permPromise
    const elapsed = Date.now() - start

    // Post-grant we expect at least one fresh `timeoutMs` budget before reject.
    expect((result.data as { ok: boolean }).ok).toBe(false)
    expect((result.data as { error: { kind: string } }).error.kind).toBe(
      'timeout',
    )
    // Lower bound: 800ms (modal grant) + ~1500ms (fresh budget) = 2300ms.
    expect(elapsed).toBeGreaterThanOrEqual(2000)
  })
})
