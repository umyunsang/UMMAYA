// SPDX-License-Identifier: Apache-2.0
// Epic FU-4 — REPL IPC permission bridge integration tests.
//
// Strategy: test the bridge module independently of REPL render to avoid
// the heavyweight REPL rendering environment (dynamic imports, AppState
// context, etc.). The bridge module is a pure module-level state machine
// analogous to leaderPermissionBridge.ts — its register/push contract
// is fully testable without mounting a React component tree.
//
// For the REPL mount side (useEffect registration), we rely on typecheck
// and the bridge unit tests (ipcPermissionBridge.test.ts) for correctness.
// The frame-push → queue-update path is the load-bearing integration seam.
//
// Tests:
//   1. Register setter → push frame → setter receives ToolUseConfirm
//   2. Two frames → two setToolUseConfirmQueue calls (idempotent queue build)
//   3. Unregister → third frame → no additional setter call
//   4. REPL registration pattern: setter(prev => [...prev, confirm]) adds items
//   5. Frame fields are faithfully transcribed into the ToolUseConfirm

import { describe, it, expect, beforeEach, mock } from 'bun:test'
import {
  registerIpcToolUseConfirmQueue,
  pushIpcPermissionRequest,
  type SetToolUseConfirmQueueFn,
} from '../../../src/utils/permissions/ipcPermissionBridge'
import { VerifyPrimitive } from '../../../src/tools/VerifyPrimitive/VerifyPrimitive'
import { SubmitPrimitive } from '../../../src/tools/SubmitPrimitive/SubmitPrimitive'
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
    session_id: 'sess-rb-001',
    correlation_id: 'corr-rb-001',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    kind: 'permission_request',
    request_id: 'req-rb-001',
    worker_id: '',
    primitive_kind: 'verify',
    description_ko: '인증 기관 확인.',
    description_en: 'Verify with authority.',
    risk_level: 'low',
    ...overrides,
  } as PermissionRequestFrame
}

/** Accumulate every ToolUseConfirm that the setter receives */
function makeAccumulatingSetter(): {
  received: ToolUseConfirm[]
  setter: SetToolUseConfirmQueueFn
} {
  const received: ToolUseConfirm[] = []
  const setter: SetToolUseConfirmQueueFn = (updater) => {
    const next = updater(received.slice())
    // Track newly appended items.
    const newItems = next.filter(
      (item) => !received.some((r) => r.toolUseID === item.toolUseID),
    )
    received.push(...newItems)
  }
  return { received, setter }
}

// ---------------------------------------------------------------------------
// Isolation
// ---------------------------------------------------------------------------

beforeEach(() => {
  registerIpcToolUseConfirmQueue(null)
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('REPL permission-bridge — register+push integration', () => {
  it('Test 1 — registered setter receives a ToolUseConfirm after pushIpcPermissionRequest', () => {
    const { received, setter } = makeAccumulatingSetter()
    registerIpcToolUseConfirmQueue(setter)

    const origWrite = process.stdout.write.bind(process.stdout)
    process.stdout.write = mock(() => true) as typeof process.stdout.write
    try {
      pushIpcPermissionRequest(makeFrame({ request_id: 'req-rb-t1' }))
    } finally {
      process.stdout.write = origWrite
    }

    expect(received.length).toBe(1)
    expect(received[0]?.toolUseID).toBe('req-rb-t1')
  })

  it('Test 2 — two distinct frames produce two ToolUseConfirm items', () => {
    const { received, setter } = makeAccumulatingSetter()
    registerIpcToolUseConfirmQueue(setter)

    const origWrite = process.stdout.write.bind(process.stdout)
    process.stdout.write = mock(() => true) as typeof process.stdout.write
    try {
      pushIpcPermissionRequest(makeFrame({ request_id: 'req-rb-t2a' }))
      pushIpcPermissionRequest(makeFrame({ request_id: 'req-rb-t2b' }))
    } finally {
      process.stdout.write = origWrite
    }

    expect(received.length).toBe(2)
    expect(received[0]?.toolUseID).toBe('req-rb-t2a')
    expect(received[1]?.toolUseID).toBe('req-rb-t2b')
  })

  it('Test 3 — unregister → subsequent push is silent (setter not called again)', () => {
    const { received, setter } = makeAccumulatingSetter()
    registerIpcToolUseConfirmQueue(setter)

    const origWrite = process.stdout.write.bind(process.stdout)
    process.stdout.write = mock(() => true) as typeof process.stdout.write
    try {
      pushIpcPermissionRequest(makeFrame({ request_id: 'req-rb-t3a' }))
    } finally {
      process.stdout.write = origWrite
    }
    expect(received.length).toBe(1)

    // Unregister (mirrors REPL unmount cleanup).
    registerIpcToolUseConfirmQueue(null)

    process.stdout.write = mock(() => true) as typeof process.stdout.write
    try {
      pushIpcPermissionRequest(makeFrame({ request_id: 'req-rb-t3b' }))
    } finally {
      process.stdout.write = origWrite
    }
    // Still only 1 — the second push was silently dropped.
    expect(received.length).toBe(1)
  })

  it('Test 4 — setter receives [...prev, confirm] accumulator pattern', () => {
    const queue: ToolUseConfirm[] = []
    const setter: SetToolUseConfirmQueueFn = (updater) => {
      const next = updater(queue.slice())
      queue.splice(0, queue.length, ...next)
    }
    registerIpcToolUseConfirmQueue(setter)

    const origWrite = process.stdout.write.bind(process.stdout)
    process.stdout.write = mock(() => true) as typeof process.stdout.write
    try {
      pushIpcPermissionRequest(makeFrame({ request_id: 'req-rb-t4a' }))
      pushIpcPermissionRequest(makeFrame({ request_id: 'req-rb-t4b' }))
    } finally {
      process.stdout.write = origWrite
    }

    // Both items accumulated — queue behaves like useState functional updater.
    expect(queue.length).toBe(2)
  })

  it('Test 5 — primitive_kind=verify → VerifyPrimitive; =submit → SubmitPrimitive', () => {
    const { received, setter } = makeAccumulatingSetter()
    registerIpcToolUseConfirmQueue(setter)

    const origWrite = process.stdout.write.bind(process.stdout)
    process.stdout.write = mock(() => true) as typeof process.stdout.write
    try {
      pushIpcPermissionRequest(makeFrame({ primitive_kind: 'verify', request_id: 'req-rb-t5v' }))
      pushIpcPermissionRequest(makeFrame({ primitive_kind: 'submit', request_id: 'req-rb-t5s' }))
    } finally {
      process.stdout.write = origWrite
    }

    expect(received[0]?.tool).toBe(VerifyPrimitive)
    expect(received[1]?.tool).toBe(SubmitPrimitive)
  })
})
