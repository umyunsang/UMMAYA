// SPDX-License-Identifier: Apache-2.0
// Wave-4 G9 (F-beta-04 UX) — ipcPermissionBridge setter-null replay queue.
//
// Verifies:
//   1. pushIpcPermissionRequest with no setter → queues instead of dropping.
//   2. registerIpcToolUseConfirmQueue(non-null) → drains queue synchronously.
//   3. Replay drives the original setter once per queued frame.
//   4. Queue eviction at 16+ entries (oldest dropped, stderr warning).

import { describe, it, expect, mock, beforeEach } from 'bun:test'

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
  _resetPermissionBridgeForTest,
} from '../../../src/utils/permissions/ipcPermissionBridge'
import type { PermissionRequestFrame } from '../../../src/ipc/frames.generated'
import type { ToolUseConfirm } from '../../../src/components/permissions/PermissionRequest'

function makeFrame(reqId: string): PermissionRequestFrame {
  return {
    version: '1.0',
    session_id: 'sess-g9',
    correlation_id: 'corr-g9',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    kind: 'permission_request',
    request_id: reqId,
    worker_id: '',
    primitive_kind: 'lookup',
    description_ko: 'NMC 응급실 검색',
    description_en: 'NMC emergency search',
    risk_level: 'high',
  } as PermissionRequestFrame
}

function captureSetter(): {
  setter: (updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[]) => void
  calls: ToolUseConfirm[][]
} {
  const calls: ToolUseConfirm[][] = []
  const setter = (updater: (prev: ToolUseConfirm[]) => ToolUseConfirm[]) => {
    const prev = calls[calls.length - 1] ?? []
    calls.push(updater(prev))
  }
  return { setter, calls }
}

describe('G9 — ipcPermissionBridge setter-null replay queue', () => {
  beforeEach(() => {
    _resetPermissionBridgeForTest()
    sentFrames.length = 0
  })

  it('queues a frame when no setter is registered (does not silently drop)', () => {
    pushIpcPermissionRequest(makeFrame('req-g9-001'))
    // Setter never called because none registered; frame must NOT have been
    // forwarded to bridge yet either (no permission_response sent prematurely).
    expect(sentFrames.length).toBe(0)

    const { setter, calls } = captureSetter()
    registerIpcToolUseConfirmQueue(setter)
    // On registration, the queued frame should drain synchronously.
    expect(calls.length).toBe(1)
    expect(calls[0]).toBeDefined()
    expect(calls[0]!.length).toBe(1)
    expect(calls[0]![0]!.toolUseID).toBe('req-g9-001')
  })

  it('drains multiple queued frames in FIFO order on registration', () => {
    pushIpcPermissionRequest(makeFrame('req-g9-A'))
    pushIpcPermissionRequest(makeFrame('req-g9-B'))
    pushIpcPermissionRequest(makeFrame('req-g9-C'))

    const { setter, calls } = captureSetter()
    registerIpcToolUseConfirmQueue(setter)

    expect(calls.length).toBe(3)
    expect(calls[0]![0]!.toolUseID).toBe('req-g9-A')
    expect(calls[1]![1]!.toolUseID).toBe('req-g9-B')
    expect(calls[2]![2]!.toolUseID).toBe('req-g9-C')
  })

  it('after register, subsequent push routes directly (no double-queueing)', () => {
    const { setter, calls } = captureSetter()
    registerIpcToolUseConfirmQueue(setter)

    pushIpcPermissionRequest(makeFrame('req-g9-direct'))
    expect(calls.length).toBe(1)
    expect(calls[0]![0]!.toolUseID).toBe('req-g9-direct')
  })

  it('queue eviction at 16+ — oldest dropped, newest preserved', () => {
    for (let i = 0; i < 20; i++) {
      pushIpcPermissionRequest(makeFrame(`req-g9-evict-${i}`))
    }
    const { setter, calls } = captureSetter()
    registerIpcToolUseConfirmQueue(setter)
    // Capacity 16 → first 4 evicted (req-g9-evict-0..3); 16 remain (4..19).
    expect(calls.length).toBe(16)
    expect(calls[0]![0]!.toolUseID).toBe('req-g9-evict-4')
    expect(calls[15]![15]!.toolUseID).toBe('req-g9-evict-19')
  })
})
