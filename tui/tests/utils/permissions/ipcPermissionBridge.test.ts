// SPDX-License-Identifier: Apache-2.0
// Epic FU-4 — ipcPermissionBridge unit tests.
//
// Tests:
//   1. No setter → pushIpcPermissionRequest is a no-op (no crash)
//   2. Registered setter → pushIpcPermissionRequest calls setter with a ToolUseConfirm
//   3. Synthesized ToolUseConfirm maps primitive_kind to correct Tool
//   4. onAllow triggers a second setter call to remove the item from the queue
//   5. onReject triggers a second setter call to remove the item
//   6. null registration clears the setter (unregister path)
//   7. primitive_kind='verify' → VerifyPrimitive
//   8. primitive_kind='submit' → SubmitPrimitive
//   9. primitive_kind='subscribe' → SubscribePrimitive
//  10. primitive_kind='lookup' → LookupPrimitive

import { describe, it, expect, mock, beforeEach } from 'bun:test'

// Audit-4 P0-8 — _sendPermissionResponse now routes via bridgeSingleton's
// `bridge.send()`. We mock `getOrCreateKosmosBridge` BEFORE importing the
// SUT so the test never spawns a backend nor touches process.stdout. Each
// test inspects the captured `sentFrames` to assert wire-format correctness.
const sentFrames: unknown[] = []
const stderrLines: string[] = []
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
import { LookupPrimitive } from '../../../src/tools/LookupPrimitive/LookupPrimitive'
import { VerifyPrimitive } from '../../../src/tools/VerifyPrimitive/VerifyPrimitive'
import { SubmitPrimitive } from '../../../src/tools/SubmitPrimitive/SubmitPrimitive'
import { SubscribePrimitive } from '../../../src/tools/SubscribePrimitive/SubscribePrimitive'
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
    session_id: 'sess-test-001',
    correlation_id: 'corr-test-001',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    kind: 'permission_request',
    request_id: 'req-fu4-001',
    worker_id: '',
    primitive_kind: 'verify',
    description_ko: '인증 기관에 본인 정보를 전달합니다.',
    description_en: 'Verify identity with authentication authority.',
    risk_level: 'medium',
    ...overrides,
  } as PermissionRequestFrame
}

// Capture what the setter receives
function captureQueue(): {
  setter: (updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[]) => void
  calls: ToolUseConfirm[][]
} {
  const calls: ToolUseConfirm[][] = []
  const setter = (updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[]) => {
    const prev = calls[calls.length - 1] ?? []
    const next = updater(prev)
    calls.push(next)
  }
  return { setter, calls }
}

// ---------------------------------------------------------------------------
// Isolation
// ---------------------------------------------------------------------------

beforeEach(() => {
  // Clear any registered setter between tests.
  registerIpcToolUseConfirmQueue(null)
  sentFrames.length = 0
  stderrLines.length = 0
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ipcPermissionBridge — no setter registered', () => {
  it('pushIpcPermissionRequest with no setter is a no-op (no throw)', () => {
    // No setter registered.
    expect(() => pushIpcPermissionRequest(makeFrame())).not.toThrow()
  })
})

describe('ipcPermissionBridge — setter registered', () => {
  it('pushIpcPermissionRequest calls setter once with a ToolUseConfirm in the queue', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ request_id: 'req-fu4-002' }))

    // Setter was called once — the queue now has 1 item.
    expect(calls.length).toBe(1)
    expect(calls[0]?.length).toBe(1)
  })

  it('synthesized ToolUseConfirm carries the request_id as toolUseID', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ request_id: 'req-fu4-id-check' }))

    const confirm = calls[0]![0]!
    expect(confirm.toolUseID).toBe('req-fu4-id-check')
  })

  it('synthesized ToolUseConfirm description includes both English and Korean', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(
      makeFrame({
        description_en: 'Verify identity.',
        description_ko: '본인 확인.',
      }),
    )

    const confirm = calls[0]![0]!
    expect(confirm.description).toContain('Verify identity.')
    expect(confirm.description).toContain('본인 확인.')
  })
})

describe('ipcPermissionBridge — primitive_kind → Tool mapping', () => {
  it('primitive_kind=verify → VerifyPrimitive', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ primitive_kind: 'verify' }))

    expect(calls[0]![0]!.tool).toBe(VerifyPrimitive)
  })

  it('primitive_kind=submit → SubmitPrimitive', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ primitive_kind: 'submit' }))

    expect(calls[0]![0]!.tool).toBe(SubmitPrimitive)
  })

  it('primitive_kind=subscribe → SubscribePrimitive', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ primitive_kind: 'subscribe' }))

    expect(calls[0]![0]!.tool).toBe(SubscribePrimitive)
  })

  it('primitive_kind=lookup → LookupPrimitive', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ primitive_kind: 'lookup' }))

    expect(calls[0]![0]!.tool).toBe(LookupPrimitive)
  })

  it('primitive_kind=resolve_location → LookupPrimitive (geo alias)', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ primitive_kind: 'resolve_location' }))

    expect(calls[0]![0]!.tool).toBe(LookupPrimitive)
  })
})

describe('ipcPermissionBridge — onAllow / onReject queue management', () => {
  it('onAllow removes the item from the queue (second setter call)', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ request_id: 'req-fu4-allow' }))

    // Trigger onAllow — it filters out the item and calls setter again.
    const confirm = calls[0]![0]!
    confirm.onAllow({} as never, [])

    // Second setter call removes the item — queue is empty.
    expect(calls.length).toBe(2)
    const removed = calls[1]!
    expect(removed.find((c) => c.toolUseID === 'req-fu4-allow')).toBeUndefined()
  })

  it('onReject removes the item from the queue (second setter call)', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ request_id: 'req-fu4-reject' }))

    const confirm = calls[0]![0]!
    confirm.onReject()

    expect(calls.length).toBe(2)
    const removed = calls[1]!
    expect(removed.find((c) => c.toolUseID === 'req-fu4-reject')).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// Audit-4 P0-8 — wire-format regression for permission_response routing
// ---------------------------------------------------------------------------

describe('ipcPermissionBridge — P0-8 NDJSON leak protection', () => {
  it('onAllow sends a permission_response frame via bridge (NOT process.stdout)', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ request_id: 'req-fu4-wire-allow' }))
    const confirm = calls[0]![0]!

    // Snapshot stdout to prove no NDJSON leaks into the citizen terminal.
    const origStdoutWrite = process.stdout.write.bind(process.stdout)
    const stdoutWriteMock = mock(() => true)
    process.stdout.write = stdoutWriteMock as typeof process.stdout.write
    try {
      confirm.onAllow({} as never, [])
    } finally {
      process.stdout.write = origStdoutWrite
    }

    expect(stdoutWriteMock).not.toHaveBeenCalled()
    expect(sentFrames.length).toBe(1)
    const sent = sentFrames[0] as Record<string, unknown>
    expect(sent.kind).toBe('permission_response')
    expect(sent.request_id).toBe('req-fu4-wire-allow')
    // Audit-4 P0-5 + P0-8 — wire decision defaults to canonical 'allow_once'
    // when no explicit allow_session stash was set by the adapter.
    expect(sent.decision).toBe('allow_once')
    expect(sent.role).toBe('tui')
  })

  it('onReject sends decision=deny via bridge (canonical Spec 1978 wire token)', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ request_id: 'req-fu4-wire-deny' }))
    const confirm = calls[0]![0]!
    confirm.onReject()

    expect(sentFrames.length).toBe(1)
    const sent = sentFrames[0] as Record<string, unknown>
    expect(sent.kind).toBe('permission_response')
    expect(sent.decision).toBe('deny')
    expect(sent.request_id).toBe('req-fu4-wire-deny')
  })

  it('onAbort sends decision=deny via bridge (fail-closed)', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame({ request_id: 'req-fu4-wire-abort' }))
    const confirm = calls[0]![0]!
    confirm.onAbort()

    expect(sentFrames.length).toBe(1)
    const sent = sentFrames[0] as Record<string, unknown>
    expect(sent.decision).toBe('deny')
  })
})

describe('ipcPermissionBridge — unregister', () => {
  it('registerIpcToolUseConfirmQueue(null) clears setter — subsequent push is a no-op', () => {
    const { setter, calls } = captureQueue()
    registerIpcToolUseConfirmQueue(setter)

    // Unregister.
    registerIpcToolUseConfirmQueue(null)

    // Should be no-op after unregistration.
    expect(() => pushIpcPermissionRequest(makeFrame())).not.toThrow()
    expect(calls.length).toBe(0)
  })
})
