// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic ζ #2297 Phase 0b · T008
//
// dispatchPrimitive — shared helper that replaces the {status: 'stub'} bodies
// in the primitive call() implementations with real IPC dispatch.
//
// Contracts: contracts/tui-primitive-dispatcher.md I-D2 / I-D3 / I-D6 / I-D7
// Data model: data-model.md § 4
// FR-009 (verify args verbatim): dispatcher MUST NOT translate tool_id.

import { trace } from '@opentelemetry/api'
import { makeUUIDv7, makeBaseEnvelope } from '../../ipc/envelope.js'
import type { IPCBridge } from '../../ipc/bridge.js'
import type { ToolCallFrame, ToolResultFrame } from '../../ipc/frames.generated.js'
import { getUmmayaBridgeSessionId } from '../../ipc/bridgeSingleton.js'
import type { ToolUseContext, ToolResult } from '../../Tool.js'
import { argumentsForPrimitive } from './documentDispatchArguments.js'
import { PendingCallRegistry } from './pendingCallRegistry.js'

// ---------------------------------------------------------------------------
// Re-export PendingCallRegistry for convenience (tests/callers can import
// both from the same module).
// ---------------------------------------------------------------------------
export { PendingCallRegistry } from './pendingCallRegistry.js'

// ---------------------------------------------------------------------------
// OTEL tracer
// ---------------------------------------------------------------------------

const _tracer = trace.getTracer('ummaya.tui.primitive', '0.1.0')

// ---------------------------------------------------------------------------
// Environment-driven timeout (FR-006)
// ---------------------------------------------------------------------------

const DEFAULT_TIMEOUT_MS = 30_000

function _resolveTimeoutMs(override?: number): number {
  if (override !== undefined && override > 0) return override
  const env = process.env['UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS']
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
  primitive: 'find' | 'locate' | 'check' | 'send' | 'document'
  /** Concrete model-facing tool name. Defaults to the primitive for legacy root calls. */
  toolName?: string
  /** Forwarded verbatim into tool_call frame arguments (FR-009). */
  args: Record<string, unknown>
  /** From CC SDK Tool.call signature. */
  context: ToolUseContext
  /** Session-scoped pending call registry (injected). */
  registry: PendingCallRegistry
  /** IPC bridge (injected). */
  bridge: IPCBridge
  /** Default 30_000 ms; env UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS overrides. */
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
  primitive: 'find' | 'locate' | 'check' | 'send' | 'document',
  frame: ToolResultFrame,
): void {
  if (process.env['UMMAYA_SMOKE_CHECKPOINTS'] !== 'true') return
  if (primitive !== 'send') return
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
 *           OTEL span attribute `ummaya.tui.primitive.timeout=true`.
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
  const toolName = opts.toolName ?? opts.primitive
  const span = _tracer.startSpan(`ummaya.tui.primitive.${opts.primitive}`, {
    attributes: {
      'ummaya.tui.primitive.name': opts.primitive,
      'ummaya.tui.tool.name': toolName,
      'ummaya.tui.primitive.timeout_ms': timeoutMs,
    },
  })

  // ------------------------------------------------------------------
  // CC contract: query.ts owns tool execution. The provider emits
  // assistant(tool_use) and stops; runTools() invokes this Tool.call(), which
  // dispatches the primitive over IPC and awaits the matching tool_result.
  // The Python backend hosts the Korean public-service adapter surface, but
  // it does not synthesize the follow-up assistant turn for this Tool.call().
  // ------------------------------------------------------------------

  const toolUseId = opts.context.toolUseId
  if (!toolUseId) {
    span.setAttribute('ummaya.tui.primitive.error', 'missing_tool_use_id')
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

  span.setAttribute('ummaya.tui.primitive.dispatch_mode', 'register-and-await')
  span.setAttribute('ummaya.tui.primitive.tool_use_id', toolUseId)

  // Register-and-await. The backend has already started _dispatch_primitive
  // only after this Tool.call() sends the ToolCallFrame. The bridge singleton
  // routes inbound ToolResultFrame objects into pendingCallRegistry.resolve().
  let resultFrame: ToolResultFrame
  try {
    resultFrame = await new Promise<ToolResultFrame>((resolve, reject) => {
      const timeoutHandle = setTimeout(() => {
        opts.registry.reject(
          toolUseId,
          new Error(
            `${opts.primitive} request timed out (${timeoutMs}ms); backend processing is delayed.`,
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

      const toolCallFrame: ToolCallFrame = {
        ...makeBaseEnvelope({
          sessionId: getUmmayaBridgeSessionId(),
          correlationId: makeUUIDv7(),
        }),
        role: 'tool',
        kind: 'tool_call',
        call_id: toolUseId,
        name: toolName,
        arguments: argumentsForPrimitive(opts),
      }

      const sent = opts.bridge.send(toolCallFrame)
      if (!sent) {
        opts.registry.reject(
          toolUseId,
          new Error(
            `${opts.primitive} request could not be sent because the backend exited.`,
          ),
        )
      }
    })
  } catch (err) {
    span.setAttribute('ummaya.tui.primitive.timeout', true)
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
  // backend envelope shape (src/ummaya/ipc/stdio.py:1115):
  //   { kind: '<primitive>', result: <serialized primitive output>, ... }
  // or on failure:
  //   { kind: '<primitive>', error: '...', tool_id: '...' }
  const env = resultFrame.envelope as Record<string, unknown>
  span.setAttribute(
    'ummaya.tui.primitive.envelope_kind',
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

  // [H1] (2026-05-04) — Inner-payload error classification.
  //
  // The legacy unwrap above only flips ``ok=false`` when the envelope has a
  // top-level ``error: string`` field. But the check primitive (and several
  // mock adapters) signals failure inside ``result`` instead — for example
  // ``VerifyMismatchError`` from ``ummaya.primitives.verify`` is dumped as
  // ``{ family: "mismatch_error", reason: "family_mismatch", message: ... }``
  // and the lookup mocks emit ``{ kind: "error", reason: "scope_violation",
  // message: ... }``. Without this branch, the dispatcher returns
  // ``{ok: true, result: <error payload>}`` and the per-primitive renderer
  // falls back to ``String(rawStatus ?? 'Result received')`` — citizens AND the
  // LLM both read it as success. That mis-info is safety-critical for verify
  // (auth module rejection rendered as "verified") and breaks LLM cascade
  // accuracy for lookup (scope violation rendered as data).
  //
  // Classification rules (all OR'd, evaluated against ``inner`` only):
  //   - ``inner.family === "mismatch_error"`` — VerifyMismatchError dump.
  //   - ``inner.kind === "error"`` — lookup / submit error sentinel.
  //   - ``inner.reason ∈ FATAL_REASONS`` — defense-in-depth: an adapter that
  //     emits a known-fatal reason code is classified as failure even if it
  //     forgot to set ``kind``/``family``.
  const FATAL_REASONS = new Set([
    'adapter_invocation_failed',
    'adapter_not_found',
    'auth_required',
    'coercion_violation',
    'family_mismatch',
    'invalid_params',
    'scope_violation',
    'submit_already_succeeded',
    'verify_tool_choice_mismatch',
  ])
  const innerObj = (inner && typeof inner === 'object') ? (inner as Record<string, unknown>) : null
  if (innerObj) {
    const innerFamily = typeof innerObj['family'] === 'string' ? (innerObj['family'] as string) : null
    const innerKind = typeof innerObj['kind'] === 'string' ? (innerObj['kind'] as string) : null
    const innerReason = typeof innerObj['reason'] === 'string' ? (innerObj['reason'] as string) : null
    const isMismatchError = innerFamily === 'mismatch_error'
    const isErrorKind = innerKind === 'error'
    const isFatalReason = innerReason !== null && FATAL_REASONS.has(innerReason)
    if (isMismatchError || isErrorKind || isFatalReason) {
      const innerMessage = typeof innerObj['message'] === 'string'
        ? (innerObj['message'] as string)
        : (isMismatchError
            ? 'The authentication module rejected the request.'
            : 'The tool call was rejected.')
      // Pick the most-specific kind label so renderers + audit logs can
      // distinguish dispatcher-level failure (envelope.error) from
      // primitive-payload failure (mismatch_error / scope_violation / ...).
      let errorKind = 'primitive_error'
      if (isMismatchError) errorKind = 'mismatch_error'
      else if (isFatalReason) errorKind = innerReason as string
      else if (isErrorKind) errorKind = 'tool_error'
      const errorData: Record<string, unknown> = {
        ok: false,
        error: {
          kind: errorKind,
          message: innerMessage,
        },
        // Preserve the original inner payload so renderers can surface the
        // structured fields (expected_family / observed_family / retryable).
        result: inner,
      }
      if (
        Array.isArray(env['outbound_traces']) &&
        (env['outbound_traces'] as unknown[]).length > 0
      ) {
        errorData['outbound_traces'] = env['outbound_traces']
      }
      return {
        data: errorData as unknown as O,
      }
    }
  }

  // Spec 2521 (2026-05-02) — surface envelope-level ``outbound_traces``
  // (populated by ``ummaya.tools._outbound_trace`` on the backend) so the
  // primitives' ``renderToolResultMessage`` can render the verbose
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
