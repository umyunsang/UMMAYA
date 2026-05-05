// SPDX-License-Identifier: Apache-2.0
// Wave-4 G11 / F-gamma-04 — optimistic receipt update test.
//
// Verifies that when `onAllow` fires in `ipcPermissionBridge`, it immediately
// writes a placeholder receipt to the registered optimistic writer (before the
// backend echo arrives), so `/consent list` shows the grant with source=optimistic.

import { describe, it, expect, mock, beforeEach } from 'bun:test'

// ---------------------------------------------------------------------------
// Mock bridge so _sendPermissionResponse does not require a real backend
// ---------------------------------------------------------------------------
const sentFrames: unknown[] = []
mock.module('../../../src/ipc/bridgeSingleton.js', () => ({
  getOrCreateKosmosBridge: () => ({
    send: (frame: unknown) => {
      sentFrames.push(frame)
      return true
    },
  }),
  getKosmosBridgeSessionId: () => 'sess-g11b-001',
}))

// Mock adapterManifest — returns a minimal entry for the test tool_id
mock.module('../../../src/services/api/adapterManifest.js', () => ({
  resolveAdapter: (toolId: string) =>
    toolId === 'mock_verify_mobile_id'
      ? { name: '모바일신분증 인증', is_irreversible: false }
      : undefined,
}))

import {
  registerIpcToolUseConfirmQueue,
  registerOptimisticAddReceipt,
  pushIpcPermissionRequest,
  _resetPermissionBridgeForTest,
} from '../../../src/utils/permissions/ipcPermissionBridge'
import {
  setPendingPermission,
  _resetPermissionSlotForTest,
} from '../../../src/store/pendingPermissionSlot'
import type { PermissionRequestFrame } from '../../../src/ipc/frames.generated'
import type { ToolUseConfirm } from '../../../src/components/permissions/PermissionRequest'
import type { PermissionReceiptT } from '../../../src/schemas/ui-l2/permission'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFrame(
  overrides: Partial<PermissionRequestFrame> = {},
): PermissionRequestFrame {
  return {
    version: '1.0',
    session_id: 'sess-g11b-001',
    correlation_id: 'corr-g11b-001',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    kind: 'permission_request',
    request_id: 'reqg11b001',
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
  _resetPermissionBridgeForTest()
  _resetPermissionSlotForTest()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('G11 / F-gamma-04 — optimistic receipt write on onAllow', () => {
  it('onAllow calls the registered optimistic addReceipt before echo arrives', async () => {
    const requestId = 'reqg11b-opt-001'
    let captured: ToolUseConfirm | null = null
    const optimisticReceipts: PermissionReceiptT[] = []

    // Register queue setter (modal display path)
    const setter = (updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[]): void => {
      const next = updater([])
      if (next.length > 0) captured = next[0] ?? null
    }
    registerIpcToolUseConfirmQueue(setter)

    // Register optimistic writer (receipt context path — G11b fix)
    registerOptimisticAddReceipt((r) => {
      optimisticReceipts.push(r)
    })

    // Slot registration (deps.ts path — not needed for this test but mirrors prod)
    const slotPromise = setPendingPermission({
      request_id: requestId,
      primitive_kind: 'verify',
      description_ko: '본인 확인',
      description_en: 'Verify',
      risk_level: 'low',
      receipt_id: '',
      enqueued_at: performance.now(),
    })

    // Push the permission request frame
    pushIpcPermissionRequest(makeFrame({ request_id: requestId }))
    expect(captured).not.toBeNull()

    // Citizen presses Y — onAllow fires synchronously
    captured!.onAllow({} as Record<string, unknown>, [])

    // Optimistic receipt must be added immediately (same tick)
    expect(optimisticReceipts.length).toBe(1)
    const opt = optimisticReceipts[0]!
    expect(opt.receipt_id).toMatch(/^rcpt-opt-[A-Za-z0-9]{8,}$/)
    expect(opt.decision).toBe('allow_once')
    expect(opt.layer).toBeGreaterThanOrEqual(1)
    expect(opt.layer).toBeLessThanOrEqual(3)
    expect(opt.revoked_at).toBeNull()

    // Wire frame was also sent (G3 invariant preserved)
    expect(sentFrames.length).toBeGreaterThanOrEqual(1)

    // Slot resolved to 'granted' (G3 invariant preserved)
    const watchdog = new Promise<'timeout'>((r) => setTimeout(() => r('timeout'), 100))
    const decision = await Promise.race([slotPromise, watchdog])
    expect(decision).toBe('granted')

    registerIpcToolUseConfirmQueue(null)
    registerOptimisticAddReceipt(null)
  })

  it('no optimistic write if addReceipt not registered (graceful no-op)', () => {
    const requestId = 'reqg11b-noop-002'
    let captured: ToolUseConfirm | null = null

    const setter = (updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[]): void => {
      const next = updater([])
      if (next.length > 0) captured = next[0] ?? null
    }
    registerIpcToolUseConfirmQueue(setter)
    // Do NOT call registerOptimisticAddReceipt

    pushIpcPermissionRequest(makeFrame({ request_id: requestId }))
    expect(captured).not.toBeNull()

    // Should not throw even with no optimistic writer registered
    expect(() => captured!.onAllow({} as Record<string, unknown>, [])).not.toThrow()

    registerIpcToolUseConfirmQueue(null)
  })
})
