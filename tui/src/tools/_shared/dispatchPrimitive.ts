// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic ζ #2297 Phase 0b · T008
//
// dispatchPrimitive — shared helper that replaces the {status: 'stub'} bodies
// in the 4 primitive call() implementations with real IPC dispatch.
//
// Contracts: contracts/tui-primitive-dispatcher.md I-D2 / I-D3 / I-D6 / I-D7
// Data model: data-model.md § 4
// FR-009 (verify args verbatim): dispatcher MUST NOT translate tool_id.

import { trace } from '@opentelemetry/api'
import { makeUUIDv7, makeBaseEnvelope } from '../../ipc/envelope.js'
import type { IPCBridge } from '../../ipc/bridge.js'
import type { ToolCallFrame, ToolResultFrame } from '../../ipc/frames.generated.js'
import type { ToolUseContext, ToolResult } from '../../Tool.js'
import { PendingCallRegistry } from './pendingCallRegistry.js'

// ---------------------------------------------------------------------------
// Re-export PendingCallRegistry for convenience (tests/callers can import
// both from the same module).
// ---------------------------------------------------------------------------
export { PendingCallRegistry } from './pendingCallRegistry.js'

// ---------------------------------------------------------------------------
// OTEL tracer
// ---------------------------------------------------------------------------

const _tracer = trace.getTracer('kosmos.tui.primitive', '0.1.0')

// ---------------------------------------------------------------------------
// Environment-driven timeout (FR-006)
// ---------------------------------------------------------------------------

const DEFAULT_TIMEOUT_MS = 30_000

function _resolveTimeoutMs(override?: number): number {
  if (override !== undefined && override > 0) return override
  const env = process.env['KOSMOS_TUI_PRIMITIVE_TIMEOUT_MS']
  if (env) {
    const n = parseInt(env, 10)
    if (!isNaN(n) && n > 0) return n
  }
  return DEFAULT_TIMEOUT_MS
}

// ---------------------------------------------------------------------------
// Options type (I-D2)
// ---------------------------------------------------------------------------

export interface DispatchPrimitiveOpts {
  primitive: 'lookup' | 'verify' | 'submit' | 'subscribe'
  /** Forwarded verbatim into tool_call frame arguments (FR-009). */
  args: Record<string, unknown>
  /** From CC SDK Tool.call signature. */
  context: ToolUseContext
  /** Session-scoped pending call registry (injected). */
  registry: PendingCallRegistry
  /** IPC bridge (injected). */
  bridge: IPCBridge
  /** Default 30_000 ms; env KOSMOS_TUI_PRIMITIVE_TIMEOUT_MS overrides. */
  timeoutMs?: number
}

// ---------------------------------------------------------------------------
// CHECKPOINT marker state (I-P2 / T014)
// ---------------------------------------------------------------------------

const _RECEIPT_REGEX = /hometax-\d{4}-\d{2}-\d{2}-RX-[A-Z0-9]{5}/

let _checkpointEmitted = false

/** Reset checkpoint state — used by tests to verify exactly-once semantics. */
export function _resetCheckpointState(): void {
  _checkpointEmitted = false
}

function _maybeEmitCheckpoint(
  primitive: 'lookup' | 'verify' | 'submit' | 'subscribe',
  frame: ToolResultFrame,
): void {
  if (process.env['KOSMOS_SMOKE_CHECKPOINTS'] !== 'true') return
  if (primitive !== 'submit') return
  if (_checkpointEmitted) return

  // Check transaction_id on the frame first
  const txId = frame.transaction_id
  if (txId && typeof txId === 'string' && _RECEIPT_REGEX.test(txId)) {
    _checkpointEmitted = true
    process.stderr.write('CHECKPOINTreceipt token observed\n')
    return
  }

  // Also scan the envelope for a receipt-id-like field
  try {
    const envelopeStr = JSON.stringify(frame.envelope)
    if (_RECEIPT_REGEX.test(envelopeStr)) {
      _checkpointEmitted = true
      process.stderr.write('CHECKPOINTreceipt token observed\n')
    }
  } catch {
    // Ignore serialization errors
  }
}

// ---------------------------------------------------------------------------
// dispatchPrimitive<O> (I-D3)
// ---------------------------------------------------------------------------

/**
 * Dispatch a primitive call over the IPC bridge and await the tool_result.
 *
 * Invariants:
 *   I-D2 — signature exactly as specified in the contract.
 *   I-D3 — mints callId, constructs ToolCallFrame, registers pending call,
 *           sends frame, returns Promise driven by registry resolution.
 *   I-D6 — timeout (default 30s) rejects with Korean error message and sets
 *           OTEL span attribute `kosmos.tui.primitive.timeout=true`.
 *   I-D7 — error envelope (envelope.error set) surfaces as ok=false result.
 *   I-D8 — verify args forwarded verbatim (FR-009); no translation here.
 */
export async function dispatchPrimitive<O = unknown>(
  opts: DispatchPrimitiveOpts,
): Promise<ToolResult<O>> {
  const timeoutMs = _resolveTimeoutMs(opts.timeoutMs)

  // ------------------------------------------------------------------
  // Step 1: OTEL span
  // ------------------------------------------------------------------
  const span = _tracer.startSpan(`kosmos.tui.primitive.${opts.primitive}`, {
    attributes: {
      'kosmos.tui.primitive.name': opts.primitive,
      'kosmos.tui.primitive.timeout_ms': timeoutMs,
    },
  })

  // ------------------------------------------------------------------
  // Architecture (CC-original byte-identical migration, 2026-04-30):
  //
  // The backend's `_handle_chat_request` parses K-EXAONE function_calls,
  // emits a ToolCallFrame (with call_id == K-EXAONE tool_use_id) AND
  // fires `_dispatch_primitive` server-side as a parallel asyncio.Task.
  // When the primitive completes, the backend emits a ToolResultFrame
  // carrying the same call_id and the authoritative result envelope.
  //
  // The frontend matches the backend's ToolResultFrame to the SDK's
  // Tool.call() invocation by call_id == toolUseId via PendingCallRegistry:
  //   1. dispatchPrimitive registers the toolUseId here (race-safe — if
  //      the backend's frame already arrived, register fires synchronously).
  //   2. llmClient.ts:455 routes inbound tool_result frames into
  //      registry.resolve(call_id, frame).
  //   3. The Promise below resolves with the matched ToolResultEnvelope.
  //
  // The ToolResultEnvelope is then unwrapped into the SDK's ToolResult
  // shape so the primitive's `renderToolResultMessage` sees the actual
  // primitive output (LookupSearchResult / KMA forecast / receipt /
  // SubscriptionHandle) rather than a sentinel. CC pattern: the SDK
  // tool-use turn closes WITH the real result, exactly as it does for
  // CC's Anthropic-API-direct path.
  //
  // Note: the SDK loop also adds the result to its turn-local message
  // history, but `tui/src/query/deps.ts:48-65` filters tool messages out
  // of the next ChatRequestFrame.messages (`only user/assistant turns
  // with extractable text are forwarded`), so there is no double-execute
  // risk — the backend retains its own role="tool" history server-side.
  // ------------------------------------------------------------------

  void makeUUIDv7  // import retained for future inbound-tool_call wiring
  void makeBaseEnvelope
  void opts.bridge

  const toolUseId =
    (opts.context as Record<string, unknown>)['toolUseId'] as string | undefined
  if (!toolUseId) {
    span.setAttribute('kosmos.tui.primitive.error', 'missing_tool_use_id')
    span.end()
    return {
      data: {
        ok: false as const,
        error: {
          kind: 'dispatch_error',
          message:
            'dispatchPrimitive: toolUseId missing on context — cannot match backend tool_result.',
        },
      } as unknown as O,
    }
  }

  span.setAttribute('kosmos.tui.primitive.dispatch_mode', 'register-and-await')
  span.setAttribute('kosmos.tui.primitive.tool_use_id', toolUseId)

  // Register-and-await. The backend has already started _dispatch_primitive
  // as a parallel task; we wait for the matching ToolResultFrame to arrive
  // via llmClient.ts → pendingCallRegistry.resolve().
  let resultFrame: ToolResultFrame
  try {
    resultFrame = await new Promise<ToolResultFrame>((resolve, reject) => {
      const timeoutHandle = setTimeout(() => {
        opts.registry.reject(
          toolUseId,
          new Error(
            `${opts.primitive} 요청 시간 초과 (${timeoutMs}ms) — 백엔드 처리가 지연되고 있습니다.`,
          ),
        )
      }, timeoutMs)

      opts.registry.register({
        callId: toolUseId,
        primitive: opts.primitive,
        resolve,
        reject,
        timeoutHandle,
      })
    })
  } catch (err) {
    span.setAttribute('kosmos.tui.primitive.timeout', true)
    span.end()
    return {
      data: {
        ok: false as const,
        error: {
          kind: 'timeout',
          message: err instanceof Error ? err.message : String(err),
        },
      } as unknown as O,
    }
  }

  // Convergence-marker emission (FR-013 / I-P2 PTY smoke contract).
  _maybeEmitCheckpoint(opts.primitive, resultFrame)

  // Unwrap envelope → SDK ToolResult.
  // backend envelope shape (src/kosmos/ipc/stdio.py:1115):
  //   { kind: '<primitive>', result: <serialized primitive output>, ... }
  // or on failure:
  //   { kind: '<primitive>', error: '...', tool_id: '...' }
  const env = resultFrame.envelope as Record<string, unknown>
  span.setAttribute(
    'kosmos.tui.primitive.envelope_kind',
    typeof env?.kind === 'string' ? (env.kind as string) : 'unknown',
  )
  span.end()

  if (typeof env?.error === 'string' && env.error.length > 0) {
    // Spec 2521 (2026-05-02) — forward outbound_traces even on dispatch
    // error so partial-failure cases (adapter made N calls then crashed)
    // still surface their captured request/response in the verbose view.
    const errorData: Record<string, unknown> = {
      ok: false,
      error: {
        kind: 'dispatch_error',
        message: env.error,
      },
    }
    if (Array.isArray(env['outbound_traces']) && (env['outbound_traces'] as unknown[]).length > 0) {
      errorData['outbound_traces'] = env['outbound_traces']
    }
    return {
      data: errorData as unknown as O,
    }
  }

  // Forward the inner `result` if present, else the entire envelope.
  // Each primitive's renderToolResultMessage knows its own result shape.
  const inner = 'result' in env ? env.result : env

  // Spec 2521 (2026-05-02) — surface envelope-level ``outbound_traces``
  // (populated by ``kosmos.tools._outbound_trace`` on the backend) so the
  // 4 primitives' ``renderToolResultMessage`` can render the verbose
  // outbound HTTP request/response section. Without this, the dispatcher
  // strips the field at unwrap time and the verbose view shows nothing
  // even when ``serviceKey``-redacted traces exist.
  const data: Record<string, unknown> = { ok: true, result: inner }
  if (Array.isArray(env['outbound_traces']) && (env['outbound_traces'] as unknown[]).length > 0) {
    data['outbound_traces'] = env['outbound_traces']
  }
  return {
    data: data as unknown as O,
  }
}
