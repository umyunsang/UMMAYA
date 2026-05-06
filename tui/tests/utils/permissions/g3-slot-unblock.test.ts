// SPDX-License-Identifier: Apache-2.0
// Wave-2 G3 fix (F-gamma-01) regression — verifies that the modal-grant flow
// now unblocks `tui/src/store/pendingPermissionSlot.ts:setPendingPermission`.
//
// Pre-fix: pushIpcPermissionRequest.onAllow only called bridge.send +
// setter(filter). The Promise returned by `setPendingPermission(...)` (which
// `tui/src/query/deps.ts:590` awaits) was never resolved by any production
// path — the slot's only resolver was the 300-second `setTimeout` inside
// `activateHead`. Citizens experienced a frozen spinner after approving or
// rejecting the prompt for the full 5-minute TTL, then a synthetic 'denied'
// arrived too late.
//
// Post-fix: onAllow / onReject / onAbort each call
// `resolvePermissionDecision(request_id, ...)` so the slot resolves in
// the same tick the bridge frame is sent.

import { describe, it, expect, mock, beforeEach } from 'bun:test'

// Mock the bridge so onAllow's _sendPermissionResponse does not require a
// real backend.
const sentFrames: unknown[] = []
mock.module('../../../src/ipc/bridgeSingleton.js', () => ({
  getOrCreateKosmosBridge: () => ({
    send: (frame: unknown) => {
      sentFrames.push(frame)
      return true
    },
  }),
}))

import {
  registerIpcToolUseConfirmQueue,
  pushIpcPermissionRequest,
} from '../../../src/utils/permissions/ipcPermissionBridge'
import {
  setPendingPermission,
  _resetPermissionSlotForTest,
} from '../../../src/store/pendingPermissionSlot'
import type { PermissionRequestFrame } from '../../../src/ipc/frames.generated'
import type { ToolUseConfirm } from '../../../src/components/permissions/PermissionRequest'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFrame(
  overrides: Partial<PermissionRequestFrame> = {},
): PermissionRequestFrame {
  return {
    version: '1.0',
    session_id: 'sess-g3-001',
    correlation_id: 'corr-g3-001',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    kind: 'permission_request',
    request_id: 'req-g3-grant-001',
    worker_id: '',
    primitive_kind: 'verify',
    description_ko: '본인 확인을 진행합니다.',
    description_en: 'Verify identity.',
    risk_level: 'low',
    tool_id: 'mock_verify_mobile_id',
    ...overrides,
  } as PermissionRequestFrame
}

beforeEach(() => {
  sentFrames.length = 0
  _resetPermissionSlotForTest()
})

describe('G3 — pushIpcPermissionRequest onAllow/onReject unblock pendingPermissionSlot', () => {
  it('onAllow resolves the slot Promise within one tick of the modal grant (F-gamma-01)', async () => {
    const requestId = 'req-g3-grant-onAllow'
    let captured: ToolUseConfirm | null = null
    const setter = (
      updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[],
    ): void => {
      const next = updater([])
      if (next.length > 0) captured = next[0] ?? null
    }
    registerIpcToolUseConfirmQueue(setter)

    // Step 1 — deps.ts arm awaits the slot (300 s TTL, must NOT be reached).
    const slotPromise = setPendingPermission({
      request_id: requestId,
      primitive_kind: 'verify',
      description_ko: '본인 확인',
      description_en: 'Verify',
      risk_level: 'low',
      receipt_id: '',
      enqueued_at: performance.now(),
    })

    // Step 2 — IPC arm pushes the modal frame.
    pushIpcPermissionRequest(makeFrame({ request_id: requestId }))
    expect(captured).not.toBeNull()

    // Step 3 — citizen presses Y in the modal. CC pipeline calls
    // toolUseConfirm.onAllow().
    captured!.onAllow({} as Record<string, unknown>, [])

    // Step 4 — slot Promise must resolve in the same microtask, not 300 s
    // later. Race against a 100 ms watchdog so the test fails fast on
    // regression instead of hanging the whole bun test runner.
    const watchdog = new Promise<'timeout'>((resolve) => {
      setTimeout(() => resolve('timeout'), 100)
    })
    const decision = await Promise.race([slotPromise, watchdog])
    expect(decision).toBe('granted')

    // Step 5 — bridge wire frame was also sent (existing behaviour preserved).
    expect(sentFrames.length).toBe(1)
    const sent = sentFrames[0] as { kind: string; decision: string }
    expect(sent.kind).toBe('permission_response')
    expect(['allow_once', 'allow_session', 'granted']).toContain(sent.decision)

    registerIpcToolUseConfirmQueue(null)
  })

  it('onReject resolves the slot Promise to "denied" within one tick (F-gamma-01)', async () => {
    const requestId = 'req-g3-deny-onReject'
    let captured: ToolUseConfirm | null = null
    const setter = (
      updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[],
    ): void => {
      const next = updater([])
      if (next.length > 0) captured = next[0] ?? null
    }
    registerIpcToolUseConfirmQueue(setter)

    const slotPromise = setPendingPermission({
      request_id: requestId,
      primitive_kind: 'submit',
      description_ko: '제출',
      description_en: 'Submit',
      risk_level: 'high',
      receipt_id: '',
      enqueued_at: performance.now(),
    })

    pushIpcPermissionRequest(
      makeFrame({ request_id: requestId, primitive_kind: 'submit' }),
    )
    expect(captured).not.toBeNull()

    captured!.onReject()

    const watchdog = new Promise<'timeout'>((resolve) => {
      setTimeout(() => resolve('timeout'), 100)
    })
    const decision = await Promise.race([slotPromise, watchdog])
    expect(decision).toBe('denied')

    expect(sentFrames.length).toBe(1)
    const sent = sentFrames[0] as { decision: string }
    expect(['deny', 'denied']).toContain(sent.decision)

    registerIpcToolUseConfirmQueue(null)
  })

  it('onAbort (Ctrl-C during modal) resolves slot to "denied" (fail-closed)', async () => {
    const requestId = 'req-g3-abort'
    let captured: ToolUseConfirm | null = null
    const setter = (
      updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[],
    ): void => {
      const next = updater([])
      if (next.length > 0) captured = next[0] ?? null
    }
    registerIpcToolUseConfirmQueue(setter)

    const slotPromise = setPendingPermission({
      request_id: requestId,
      primitive_kind: 'verify',
      description_ko: '본인 확인',
      description_en: 'Verify',
      risk_level: 'low',
      receipt_id: '',
      enqueued_at: performance.now(),
    })

    pushIpcPermissionRequest(makeFrame({ request_id: requestId }))
    expect(captured).not.toBeNull()

    captured!.onAbort()

    const watchdog = new Promise<'timeout'>((resolve) => {
      setTimeout(() => resolve('timeout'), 100)
    })
    const decision = await Promise.race([slotPromise, watchdog])
    expect(decision).toBe('denied')

    registerIpcToolUseConfirmQueue(null)
  })
})
