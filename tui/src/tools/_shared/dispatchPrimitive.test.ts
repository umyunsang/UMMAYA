// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic ζ #2297 Phase 0b · T008 (revised post-smoke 2026-04-30)
//
// Unit tests for dispatchPrimitive.ts (server-side-ack architecture).
//
// Architecture note: live smoke on 2026-04-30 revealed the backend's
// `_handle_chat_request` runs the full agentic loop server-side and
// emits its own tool_result frames; the TUI's CC SDK Tool.call() has
// no inbound-tool_call counterpart on the backend, so the original
// IPC-dispatch design timed out. The revised dispatcher returns a
// synthetic-success ack envelope immediately so the SDK turn closes
// without re-triggering execution. See the dispatchPrimitive.ts header
// for the full rationale.

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
// Tests — server-side-ack contract
// ---------------------------------------------------------------------------

// KOSMOS hotfix #2519 (CC-original migration, 2026-04-30): the
// server-side-ack stub architecture this file tests was superseded by
// the register-and-await pattern (see dispatchPrimitive.ts header).
// The new architecture awaits a real ToolResultFrame from the backend;
// the assertions below (synchronous return + ack envelope shape + no
// inbound IPC tool_call frame) no longer apply. A follow-up Spec will
// rewrite these tests against the register-and-await contract.
describe.skip('dispatchPrimitive (server-side-ack) — superseded by register-and-await', () => {
  let registry: PendingCallRegistry

  beforeEach(() => {
    registry = new PendingCallRegistry()
  })

  test('lookup returns ok=true with ack envelope', async () => {
    const result = (await dispatchPrimitive({
      primitive: 'lookup',
      args: { mode: 'search', query: '날씨' },
      context: fakeContext('lookup-use-1'),
      registry,
      bridge: fakeBridge(),
    })) as unknown as { data: { ok: boolean; result?: Record<string, unknown> } }

    expect(result.data.ok).toBe(true)
    expect(result.data.result?.['dispatched_via']).toBe('backend-server-side')
    expect(result.data.result?.['primitive']).toBe('lookup')
    expect(result.data.result?.['tool_use_id']).toBe('lookup-use-1')
  })

  test('verify forwards args verbatim — tool_id preserved (FR-009 / I-V6)', async () => {
    const args = {
      tool_id: 'mock_verify_module_modid',
      params: {
        scope_list: ['lookup:hometax.simplified'],
        purpose_ko: '종합소득세 신고',
        purpose_en: 'Tax return',
      },
    }

    const result = (await dispatchPrimitive({
      primitive: 'verify',
      args,
      context: fakeContext('verify-use-1'),
      registry,
      bridge: fakeBridge(),
    })) as unknown as { data: { ok: boolean; result?: Record<string, unknown> } }

    expect(result.data.ok).toBe(true)
    // The dispatcher does NOT translate tool_id at the TUI layer (FR-009).
    // The server-side-ack architecture leaves args untouched on the
    // wire — backend's `_VerifyInputForLLM` pre-validator owns translation.
    expect(args.tool_id).toBe('mock_verify_module_modid')
    expect(args.params.scope_list).toEqual(['lookup:hometax.simplified'])
  })

  test('submit returns ack with submit primitive name', async () => {
    const result = (await dispatchPrimitive({
      primitive: 'submit',
      args: { tool_id: 'mock_submit_module_hometax_taxreturn' },
      context: fakeContext('submit-use-1'),
      registry,
      bridge: fakeBridge(),
    })) as unknown as { data: { ok: boolean; result?: Record<string, unknown> } }

    expect(result.data.ok).toBe(true)
    expect(result.data.result?.['primitive']).toBe('submit')
  })

  test('missing toolUseId surfaces null in ack envelope', async () => {
    const ctx = {
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
      primitive: 'lookup',
      args: {},
      context: ctx,
      registry,
      bridge: fakeBridge(),
    })) as unknown as { data: { ok: boolean; result?: Record<string, unknown> } }

    expect(result.data.ok).toBe(true)
    expect(result.data.result?.['tool_use_id']).toBe(null)
  })

  test('does NOT send IPC tool_call frame (server-side-ack architecture)', async () => {
    let sendCalled = false
    const bridge = {
      ...fakeBridge(),
      send: () => {
        sendCalled = true
        return true
      },
    } as unknown as IPCBridge

    await dispatchPrimitive({
      primitive: 'lookup',
      args: {},
      context: fakeContext(),
      registry,
      bridge,
    })

    // Per the server-side-ack architecture, the dispatcher does NOT emit
    // a fresh tool_call frame — the backend's `_handle_chat_request`
    // already dispatches internally.
    expect(sendCalled).toBe(false)
  })

  test('completes synchronously (no timeout path under default settings)', async () => {
    const start = Date.now()
    await dispatchPrimitive({
      primitive: 'lookup',
      args: {},
      context: fakeContext(),
      registry,
      bridge: fakeBridge(),
    })
    const elapsed = Date.now() - start
    // Server-side-ack returns immediately — should complete in well under 1s.
    expect(elapsed).toBeLessThan(1000)
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
    primitive: 'lookup' | 'resolve_location' | 'verify' | 'submit',
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

  test('verify: inner family=mismatch_error → ok=false, error.kind=mismatch_error', async () => {
    const envelope = {
      kind: 'verify',
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
    const result = await dispatchAndInjectFrame('verify', envelope)
    expect(result.data.ok).toBe(false)
    expect(result.data.error?.kind).toBe('mismatch_error')
    expect(result.data.error?.message).toContain('No verify adapter registered')
    // Inner payload preserved so the renderer can surface structured fields.
    expect((result.data.result as Record<string, unknown>)?.['expected_family']).toBe(
      'gongdong_injeungseo',
    )
  })

  test('lookup: inner kind=error with reason=scope_violation → ok=false, error.kind=scope_violation', async () => {
    const envelope = {
      kind: 'lookup',
      result: {
        kind: 'error',
        reason: 'scope_violation',
        message:
          "Delegation token scope 'lookup:other' does not grant 'lookup:hometax.simplified'.",
        retryable: false,
      },
    }
    const result = await dispatchAndInjectFrame('lookup', envelope)
    expect(result.data.ok).toBe(false)
    // ``reason`` (more specific) wins over ``kind === error`` (generic) in
    // the kind-precedence rules, but we accept either as a citizen-safe
    // classification — both surface as ok=false.
    expect(['scope_violation', 'tool_error']).toContain(result.data.error?.kind)
    expect(result.data.error?.message).toContain('Delegation token scope')
  })

  test('submit: inner kind=error → ok=false, error.kind=tool_error', async () => {
    const envelope = {
      kind: 'submit',
      result: {
        kind: 'error',
        message: 'Hometax 신고 모듈 OPAQUE — submit 불가.',
      },
    }
    const result = await dispatchAndInjectFrame('submit', envelope)
    expect(result.data.ok).toBe(false)
    expect(result.data.error?.kind).toBe('tool_error')
    expect(result.data.error?.message).toContain('OPAQUE')
  })

  test('lookup: success envelope with normal result still flips ok=true (regression guard)', async () => {
    // The classifier must NOT over-trigger — a benign result with no
    // family/kind/reason fields should pass through as ok=true.
    const envelope = {
      kind: 'lookup',
      result: {
        items: [{ name: 'Sample', value: 42 }],
        count: 1,
      },
    }
    const result = await dispatchAndInjectFrame('lookup', envelope)
    expect(result.data.ok).toBe(true)
    expect((result.data.result as Record<string, unknown>)?.['count']).toBe(1)
  })

  test('top-level envelope.error still classified as ok=false (legacy path preserved)', async () => {
    const envelope = {
      kind: 'verify',
      error: 'IPC bridge crashed mid-dispatch.',
      tool_id: 'verify_module_modid',
    }
    const result = await dispatchAndInjectFrame('verify', envelope)
    expect(result.data.ok).toBe(false)
    expect(result.data.error?.kind).toBe('dispatch_error')
    expect(result.data.error?.message).toContain('IPC bridge crashed')
  })
})
