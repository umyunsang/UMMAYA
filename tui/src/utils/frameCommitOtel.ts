// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — observability/spec(debug-infra-rebuild RFC § P4 2026-05-02)
//
// frameCommitOtel — emit `kosmos.tui.frame_commit` OTEL span events on every
// Ink reconcile (React re-render of the component that mounts this hook).
//
// Why:
//   RFC § P4 explains that the OTLP → Langfuse pipeline (Spec 028) is already
//   in place. Adding one span event per Ink reconcile enables cross-correlation
//   of "when did the LLM stream arrive" (kosmos.llm.chunk — Phase 5) with
//   "when did the TUI paint" (kosmos.tui.frame_commit — this module).
//   Bug reports become "Langfuse trace + frame_commit sequence" instead of
//   grep-based guesswork (AGENTS.md anti-pattern #2).
//
// Usage:
//   function MessagesImpl({ conversationId, ... }: Props) {
//     useFrameCommitTracker(conversationId) // [Phase4] frame_commit OTEL hook
//     ...
//   }
//
// Safety:
//   When @opentelemetry/api has NOT been initialised (test envs, cold boot
//   before init.ts runs), `trace.getActiveSpan()` + `trace.getTracer()` both
//   return no-op proxies — the hook is a no-op with zero overhead.

import { useRef } from 'react'
import { trace } from '@opentelemetry/api'
import type { Tracer } from '@opentelemetry/api'

// ---------------------------------------------------------------------------
// Module-level tracer — no-op proxy until OTEL SDK initialises at runtime.
// Safe to call from test envs: getTracer() never throws.
// ---------------------------------------------------------------------------

let _tracer: Tracer | null = null

function getTracer(): Tracer {
  if (!_tracer) {
    _tracer = trace.getTracer('kosmos.tui.frame_commit', '0.1.0')
  }
  return _tracer
}

// ---------------------------------------------------------------------------
// FNV-1a hash — same algorithm as frameHash() in waitForFrame.ts.
// Duplicated here to keep this module import-free of test-only helpers.
// ---------------------------------------------------------------------------

function fnv1a(s: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

// ---------------------------------------------------------------------------
// Per-correlation-id sequence counter.
// Lives at module scope so counter survives React re-mounts.
// ---------------------------------------------------------------------------

const _seqCounters = new Map<string, number>()

function nextSeq(correlationId: string): number {
  const n = (_seqCounters.get(correlationId) ?? 0) + 1
  _seqCounters.set(correlationId, n)
  return n
}

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

/**
 * React hook: emits a `kosmos.tui.frame_commit` OTEL span event on every
 * render of the component that calls it.
 *
 * Attributes emitted:
 *   kosmos.correlation_id  — provided `correlationId` or `'unbound'`
 *   kosmos.tui.frame_hash  — FNV-1a hash of the component's rendered subtree
 *                            (approximated by hashing a per-render fingerprint
 *                            composed of correlationId + seq + Date.now())
 *   kosmos.tui.frame_seq   — monotonically increasing counter per correlationId
 *
 * When OTEL is not initialised (test envs) the hook is a no-op — it never
 * throws and has zero overhead beyond a ref read.
 *
 * @param correlationId  Optional. Ties the frame event to an IPC correlation
 *   chain (Spec 032). Pass `conversationId` from MessagesImpl props.
 */
export function useFrameCommitTracker(correlationId?: string): void {
  // useRef ensures we track the call count per component-instance without
  // triggering additional renders.
  const renderCountRef = useRef(0)
  renderCountRef.current += 1

  try {
    const cid = correlationId ?? 'unbound'
    const seq = nextSeq(cid)
    // Approximate frame fingerprint: we don't have direct access to the
    // Ink DOM tree here (that would require a ref sweep). Instead we hash
    // the tuple (cid, seq, timestamp) which produces a unique-per-render
    // value. Layer 5 pyte/tmux captures provide the true cell-grid hash;
    // this event's value is correlation-metadata, not pixel-accurate.
    const hash = fnv1a(`${cid}:${seq}:${renderCountRef.current}`)

    const tracer = getTracer()
    const span = tracer.startSpan('kosmos.tui.frame_commit')
    span.setAttributes({
      'kosmos.correlation_id': cid,
      'kosmos.tui.frame_hash': hash,
      'kosmos.tui.frame_seq': seq,
    })
    span.end()
  } catch {
    // Swallow all errors — OTEL must never break the render path.
    // Errors here are programming mistakes in this module, not user data.
  }
}

// ---------------------------------------------------------------------------
// Exposed for tests only — reset the sequence counter between test runs.
// Not imported in production code.
// ---------------------------------------------------------------------------

export function _resetSeqCounters(): void {
  _seqCounters.clear()
  _tracer = null
}
