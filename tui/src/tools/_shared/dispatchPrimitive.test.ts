// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic ζ #2297 Phase 0b · T008 (revised post-smoke 2026-04-30)
//
// Unit tests for dispatchPrimitive.ts.
//
// CC contract: the provider emits assistant(tool_use) and stops. query.ts
// calls Tool.call(); dispatchPrimitive sends the matching ToolCallFrame to the
// backend and resolves only after the backend returns ToolResultFrame.

import { test, expect, describe, beforeEach } from 'bun:test'
import { dispatchPrimitive } from './dispatchPrimitive.js'
import { PendingCallRegistry } from './pendingCallRegistry.js'
import type { IPCBridge } from '../../ipc/bridge.js'
import type { ToolUseContext } from '../../Tool.js'

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function fakeContext(toolUseId = 'test-tool-use-id'): ToolUseContext {
  return {
    toolUseId,
    messages: [],
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

function fakeBridge(onSend?: (frame: unknown) => void): IPCBridge {
  return {
    send: (frame: unknown) => {
      onSend?.(frame)
      return true
    },
    frames: () => ({ [Symbol.asyncIterator]: () => ({ next: () => Promise.resolve({ done: true, value: undefined }) }) }) as unknown as AsyncIterable<never>,
    close: () => Promise.resolve(),
    proc: {} as ReturnType<typeof Bun.spawn>,
    applied_frame_seqs: new Set(),
    setSessionCredentials: () => {},
    lastSeenCorrelationId: null,
    lastSeenFrameSeq: null,
  } as unknown as IPCBridge
}

// ---------------------------------------------------------------------------
// Tests — CC register-and-await contract
// ---------------------------------------------------------------------------

describe('dispatchPrimitive — CC register-and-await dispatch', () => {
  let registry: PendingCallRegistry

  beforeEach(() => {
    registry = new PendingCallRegistry()
  })

  test('sends a ToolCallFrame with the original tool_use id and arguments', async () => {
    const sentFrames: unknown[] = []
    const toolUseId = 'find-use-cc-1'
    const args = {
      mode: 'fetch',
      tool_id: 'kma_current_observation',
      params: { nx: 97, ny: 74 },
    }

    const promise = dispatchPrimitive({
      primitive: 'find',
      args,
      context: fakeContext(toolUseId),
      registry,
      bridge: fakeBridge((frame) => sentFrames.push(frame)),
    }) as unknown as Promise<{ data: { ok: boolean; result?: unknown } }>

    await Promise.resolve()
    expect(sentFrames).toHaveLength(1)
    expect(sentFrames[0]).toMatchObject({
      role: 'tool',
      kind: 'tool_call',
      call_id: toolUseId,
      name: 'find',
      arguments: args,
    })

    registry.resolve(toolUseId, {
      session_id: 'test-session',
      correlation_id: 'test-corr',
      ts: '2026-05-24T00:00:00Z',
      role: 'backend',
      kind: 'tool_result',
      call_id: toolUseId,
      envelope: { kind: 'find', result: { status: 'ok' } },
    } as unknown as Parameters<typeof registry.resolve>[1])

    const result = await promise
    expect(result.data.ok).toBe(true)
    expect(result.data.result).toEqual({ status: 'ok' })
  })

  test('can preserve a concrete adapter name while dispatching through its primitive family', async () => {
    const sentFrames: unknown[] = []
    const toolUseId = 'kma-use-cc-1'
    const args = { nx: 97, ny: 74, base_date: '20260524', base_time: '1600' }

    const promise = dispatchPrimitive({
      primitive: 'find',
      toolName: 'kma_current_observation',
      args,
      context: fakeContext(toolUseId),
      registry,
      bridge: fakeBridge((frame) => sentFrames.push(frame)),
    }) as unknown as Promise<{ data: { ok: boolean; result?: unknown } }>

    await Promise.resolve()
    expect(sentFrames[0]).toMatchObject({
      role: 'tool',
      kind: 'tool_call',
      call_id: toolUseId,
      name: 'kma_current_observation',
      arguments: args,
    })

    registry.resolve(toolUseId, {
      session_id: 'test-session',
      correlation_id: 'test-corr',
      ts: '2026-05-24T00:00:00Z',
      role: 'backend',
      kind: 'tool_result',
      call_id: toolUseId,
      envelope: { kind: 'find', result: { kind: 'record' } },
    } as unknown as Parameters<typeof registry.resolve>[1])

    const result = await promise
    expect(result.data.ok).toBe(true)
    expect(result.data.result).toEqual({ kind: 'record' })
  })

  test('adds current user query to document IPC calls without exposing it to other primitives', async () => {
    const sentFrames: unknown[] = []
    const toolUseId = 'document-use-cc-1'
    const userQuery =
      '/tmp/weekly.hwpx 문서 내용을 파악해서 다음 주차 활동일지로 알아서 작성하고, 저장은 /tmp/weekly-auto.hwpx 로 해줘.'
    const context = {
      ...fakeContext(toolUseId),
      messages: [
        {
          type: 'user',
          message: { role: 'user', content: userQuery },
        },
      ],
    } as unknown as ToolUseContext
    const args = {
      correlation_id: 'corr-document',
      document: { path: '/tmp/weekly.hwpx', expected_format: 'hwpx' },
      operation: 'extract',
      instruction: '문서 내용을 구조적으로 추출하세요.',
    }

    const promise = dispatchPrimitive({
      primitive: 'document',
      args,
      context,
      registry,
      bridge: fakeBridge((frame) => sentFrames.push(frame)),
    }) as unknown as Promise<{ data: { ok: boolean; result?: unknown } }>

    await Promise.resolve()
    expect(sentFrames[0]).toMatchObject({
      role: 'tool',
      kind: 'tool_call',
      call_id: toolUseId,
      name: 'document',
      arguments: {
        ...args,
        __ummaya_user_query: userQuery,
      },
    })
    expect(args).not.toHaveProperty('__ummaya_user_query')

    registry.resolve(toolUseId, {
      session_id: 'test-session',
      correlation_id: 'test-corr',
      ts: '2026-05-24T00:00:00Z',
      role: 'backend',
      kind: 'tool_result',
      call_id: toolUseId,
      envelope: { kind: 'document', result: { status: 'ok' } },
    } as unknown as Parameters<typeof registry.resolve>[1])

    const result = await promise
    expect(result.data.ok).toBe(true)
  })

  test('missing toolUseId fails closed instead of dispatching an unmatchable call', async () => {
    let sent = false
    const ctx = {
      messages: [],
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

    const result = (await dispatchPrimitive({
      primitive: 'find',
      args: {},
      context: ctx,
      registry,
      bridge: fakeBridge(() => {
        sent = true
      }),
    })) as unknown as { data: { ok: boolean; error?: { kind: string } } }

    expect(sent).toBe(false)
    expect(result.data.ok).toBe(false)
    expect(result.data.error?.kind).toBe('dispatch_error')
  })
})

// ---------------------------------------------------------------------------
// [H1] (2026-05-04) — inner-payload error classification
//
// dispatchPrimitive must flip ``ok: false`` when the unwrapped
// ``envelope.result`` looks like a primitive-level error sentinel:
//   - VerifyMismatchError dump      → result.family === "mismatch_error"
//   - LookupError / mock errors     → result.kind   === "error"
//   - Defense-in-depth fatal reason → result.reason ∈ {family_mismatch,
//                                       scope_violation, coercion_violation}
//
// Without this classification, the renderer for each primitive falls
// through to its success path and citizens see e.g. "결과 수신됨" for what
// is actually an auth-module rejection. Citizen-safety guard.
// ---------------------------------------------------------------------------

describe('dispatchPrimitive — [H1] inner-payload error classification', () => {
  let registry: PendingCallRegistry

  beforeEach(() => {
    registry = new PendingCallRegistry()
  })

  // Helper: drive a fake ToolResultFrame through the dispatcher by resolving
  // the pending call's promise mid-flight. We bypass the IPC bridge entirely
  // — only the unwrap path under test matters here.
  async function dispatchAndInjectFrame(
    primitive: 'find' | 'locate' | 'check' | 'send' | 'document',
    envelope: Record<string, unknown>,
    toolUseId = `${primitive}-h1-1`,
  ): Promise<{ data: { ok: boolean; result?: unknown; error?: { kind: string; message: string } } }> {
    const promise = dispatchPrimitive({
      primitive,
      args: {},
      context: fakeContext(toolUseId),
      registry,
      bridge: fakeBridge(),
    }) as unknown as Promise<{
      data: { ok: boolean; result?: unknown; error?: { kind: string; message: string } }
    }>

    // Wait one microtask for register() to land, then resolve from outside.
    await Promise.resolve()
    const fakeFrame = {
      session_id: 'test-session',
      correlation_id: 'test-corr',
      ts: '2026-05-04T00:00:00Z',
      role: 'backend',
      kind: 'tool_result',
      call_id: toolUseId,
      envelope,
    } as unknown as Parameters<typeof registry.resolve>[1]
    registry.resolve(toolUseId, fakeFrame)
    return promise
  }

  test('check: inner family=mismatch_error → ok=false, error.kind=mismatch_error', async () => {
    const envelope = {
      kind: 'check',
      family: '',
      result: {
        family: 'mismatch_error',
        reason: 'family_mismatch',
        expected_family: 'gongdong_injeungseo',
        observed_family: '<no_adapter>',
        message:
          "No verify adapter registered for family 'gongdong_injeungseo'.",
      },
    }
    const result = await dispatchAndInjectFrame('check', envelope)
    expect(result.data.ok).toBe(false)
    expect(result.data.error?.kind).toBe('mismatch_error')
    expect(result.data.error?.message).toContain('No verify adapter registered')
    // Inner payload preserved so the renderer can surface structured fields.
    expect((result.data.result as Record<string, unknown>)?.['expected_family']).toBe(
      'gongdong_injeungseo',
    )
  })

  test('find: inner kind=error with reason=scope_violation → ok=false, error.kind=scope_violation', async () => {
    const envelope = {
      kind: 'find',
      result: {
        kind: 'error',
        reason: 'scope_violation',
        message:
          "Delegation token scope 'find:other' does not grant 'find:hometax.simplified'.",
        retryable: false,
      },
    }
    const result = await dispatchAndInjectFrame('find', envelope)
    expect(result.data.ok).toBe(false)
    // ``reason`` (more specific) wins over ``kind === error`` (generic) in
    // the kind-precedence rules, but we accept either as a citizen-safe
    // classification — both surface as ok=false.
    expect(['scope_violation', 'tool_error']).toContain(result.data.error?.kind)
    expect(result.data.error?.message).toContain('Delegation token scope')
  })

  test('send: inner kind=error → ok=false, error.kind=tool_error', async () => {
    const envelope = {
      kind: 'send',
      result: {
        kind: 'error',
        message: 'Hometax 신고 모듈 OPAQUE — submit 불가.',
      },
    }
    const result = await dispatchAndInjectFrame('send', envelope)
    expect(result.data.ok).toBe(false)
    expect(result.data.error?.kind).toBe('tool_error')
    expect(result.data.error?.message).toContain('OPAQUE')
  })

  test('send: adapter_invocation_failed reason → ok=false', async () => {
    const envelope = {
      kind: 'send',
      result: {
        reason: 'adapter_invocation_failed',
        tool_id: 'mock_submit_module_gov24_minwon',
        structured: {
          exception_type: 'ValidationError',
          message: 'minwon_type field required',
        },
        message: 'Adapter raised ValidationError.',
      },
    }
    const result = await dispatchAndInjectFrame('send', envelope)
    expect(result.data.ok).toBe(false)
    expect(result.data.error?.kind).toBe('adapter_invocation_failed')
    expect(result.data.error?.message).toContain('ValidationError')
  })

  test('find: success envelope with normal result still flips ok=true (regression guard)', async () => {
    // The classifier must NOT over-trigger — a benign result with no
    // family/kind/reason fields should pass through as ok=true.
    const envelope = {
      kind: 'find',
      result: {
        items: [{ name: 'Sample', value: 42 }],
        count: 1,
      },
    }
    const result = await dispatchAndInjectFrame('find', envelope)
    expect(result.data.ok).toBe(true)
    expect((result.data.result as Record<string, unknown>)?.['count']).toBe(1)
  })

  test('top-level envelope.error still classified as ok=false (legacy path preserved)', async () => {
    const envelope = {
      kind: 'check',
      error: 'IPC bridge crashed mid-dispatch.',
      tool_id: 'verify_module_modid',
    }
    const result = await dispatchAndInjectFrame('check', envelope)
    expect(result.data.ok).toBe(false)
    expect(result.data.error?.kind).toBe('dispatch_error')
    expect(result.data.error?.message).toContain('IPC bridge crashed')
  })
})
