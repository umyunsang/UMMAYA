// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — no upstream analog (Claude Code uses HTTP SSE, not stdio JSONL).
//
// Codec for the KOSMOS NDJSON IPC protocol.
//
// Spec 032 WS1 T018: extended for all 19 frame kinds + kind-narrowed type guards.
//
// Responsibilities:
//   - encodeFrame: serialise an IPCFrame to a newline-terminated JSON string
//     with payload-internal newlines escaped (FR-009).
//   - decodeFrame / decodeFrames: parse a buffer string into validated IPCFrame
//     objects (handles partial lines / multiple lines in one chunk).
//
// Validation strategy: two-layer (FR-003).
//   1. JSON.parse — catches syntax errors immediately.
//   2. Zod discriminated union — validates shape against the generated types.
//   Both layers must pass; a failure in either yields a DecodeError result.
//
// All frame types live in tui/src/ipc/frames.generated.ts (code-gen from
// src/kosmos/ipc/frame_schema.py via bun run gen:ipc).

import { z } from 'zod'
import type {
  IPCFrame,
  UserInputFrame,
  AssistantChunkFrame,
  ToolCallFrame,
  ToolResultFrame,
  CoordinatorPhaseFrame,
  WorkerStatusFrame,
  PermissionRequestFrame,
  PermissionResponseFrame,
  SessionEventFrame,
  ErrorFrame,
  PayloadStartFrame,
  PayloadDeltaFrame,
  PayloadEndFrame,
  BackpressureSignalFrame,
  ResumeRequestFrame,
  ResumeResponseFrame,
  ResumeRejectedFrame,
  HeartbeatFrame,
  NotificationPushFrame,
  AdapterManifestSyncFrame,
  ConsentRevokeRequestFrame,
  ConsentRevokeResponseFrame,
} from './frames.generated'

// Re-export AdapterManifestSyncFrame so router code imports from codec.
export type { AdapterManifestSyncFrame }
// Re-export consent revoke types.
export type { ConsentRevokeRequestFrame, ConsentRevokeResponseFrame }

// ---------------------------------------------------------------------------
// Zod schemas (belt-and-braces atop generated TypeScript types)
// ---------------------------------------------------------------------------

// Base fields present on every frame arm (Spec 032 extended envelope).
const BaseFrame = z.object({
  version: z.literal('1.0'),
  // contracts/chat-request-frame.md envelope: session_id may be "" before
  // the first session_event handshake. Accept any string (incl. empty);
  // backend is the authority on when the session is materialised.
  session_id: z.string(),
  correlation_id: z.string().min(1),
  role: z.enum(['tui', 'backend', 'tool', 'llm', 'notification']),
  frame_seq: z.number().int().min(0),
  transaction_id: z.string().min(1).nullable().optional(),
  ts: z.string(),
  trailer: z
    .object({
      final: z.boolean(),
      transaction_id: z.string().min(1).nullable().optional(),
      checksum_sha256: z.string().nullable().optional(),
    })
    .nullable()
    .optional(),
})

// ---------------------------------------------------------------------------
// Spec 287 baseline arms
// ---------------------------------------------------------------------------

const UserInputFrameSchema = BaseFrame.extend({
  kind: z.literal('user_input'),
  text: z.string(),
})

// Spec 1978 ADR-0001 — TUI tools-aware chat request.
const ChatMessageSchema = z.object({
  role: z.enum(['system', 'user', 'assistant', 'tool']),
  content: z.string(),
  name: z.string().nullable().optional(),
  tool_call_id: z.string().nullable().optional(),
})

const ToolDefinitionFunctionSchema = z.object({
  name: z.string(),
  description: z.string().nullable().optional(),
  parameters: z.record(z.string(), z.unknown()).default({}),
  strict: z.boolean().optional(),
})

const ToolDefinitionSchema = z.object({
  type: z.literal('function').default('function'),
  function: ToolDefinitionFunctionSchema,
})

const ChatRequestFrameSchema = BaseFrame.extend({
  kind: z.literal('chat_request'),
  messages: z.array(ChatMessageSchema).min(1),
  tools: z.array(ToolDefinitionSchema).default([]),
  system: z.string().nullable().optional(),
  max_tokens: z.number().int().min(1).max(32000).default(8192),
  temperature: z.number().min(0).max(2).default(1.0),
  top_p: z.number().min(0).max(1).default(0.95),
})

const AssistantChunkFrameSchema = BaseFrame.extend({
  kind: z.literal('assistant_chunk'),
  message_id: z.string(),
  // ``delta`` (visible answer) and ``thinking`` (chain-of-thought) are two
  // independent channels on the same frame — mirror of Anthropic's
  // ``content_block_delta`` (CC reference at
  // ``src/kosmos/llm/_cc_reference/claude.ts:2053-2169``). Either may be
  // empty on a given chunk; ``done=true`` terminates the message.
  delta: z.string().default(''),
  thinking: z.string().default(''),
  done: z.boolean(),
})

const ToolCallFrameSchema = BaseFrame.extend({
  kind: z.literal('tool_call'),
  call_id: z.string(),
  name: z.enum(['lookup', 'resolve_location', 'submit', 'subscribe', 'verify']),
  arguments: z.record(z.unknown()),
})

const ToolResultEnvelopeSchema = z.object({
  kind: z.enum(['lookup', 'resolve_location', 'submit', 'subscribe', 'verify']),
}).passthrough()

const ToolResultFrameSchema = BaseFrame.extend({
  kind: z.literal('tool_result'),
  call_id: z.string(),
  envelope: ToolResultEnvelopeSchema,
})

const CoordinatorPhaseFrameSchema = BaseFrame.extend({
  kind: z.literal('coordinator_phase'),
  phase: z.enum(['Research', 'Synthesis', 'Implementation', 'Verification']),
})

const WorkerStatusFrameSchema = BaseFrame.extend({
  kind: z.literal('worker_status'),
  worker_id: z.string(),
  role_id: z.string(),
  current_primitive: z.enum(['lookup', 'resolve_location', 'submit', 'subscribe', 'verify']),
  status: z.enum(['idle', 'running', 'waiting_permission', 'error']),
})

const PermissionRequestFrameSchema = BaseFrame.extend({
  kind: z.literal('permission_request'),
  request_id: z.string(),
  worker_id: z.string(),
  primitive_kind: z.enum(['lookup', 'resolve_location', 'submit', 'subscribe', 'verify']),
  description_ko: z.string(),
  description_en: z.string(),
  risk_level: z.enum(['low', 'medium', 'high']),
  tool_id: z.string().optional().nullable(),
  arguments: z.record(z.string(), z.unknown()).optional().nullable(),
})

const PermissionResponseFrameSchema = BaseFrame.extend({
  kind: z.literal('permission_response'),
  request_id: z.string(),
  // Spec 1978 ADR-0002 + Spec 033 — 5-value vocabulary (synced with
  // frame_schema.py:PermissionResponseFrame.decision Literal).
  // 'granted'/'denied' are Spec 287 legacy aliases kept for backward
  // compatibility; backend normalises them to allow_once/deny internally.
  decision: z.enum(['granted', 'allow_once', 'allow_session', 'denied', 'deny']),
  // Gap A fix — receipt_id emitted by backend on granted decisions.
  // Optional for backward compat: older backend versions omit this field.
  receipt_id: z.string().nullable().optional(),
})

const SessionEventFrameSchema = BaseFrame.extend({
  kind: z.literal('session_event'),
  event: z.enum(['save', 'load', 'list', 'resume', 'new', 'exit']),
  payload: z.record(z.unknown()),
})

const ErrorFrameSchema = BaseFrame.extend({
  kind: z.literal('error'),
  code: z.string(),
  message: z.string(),
  details: z.record(z.unknown()),
})

// ---------------------------------------------------------------------------
// Spec 032 new arms
// ---------------------------------------------------------------------------

const PayloadStartFrameSchema = BaseFrame.extend({
  kind: z.literal('payload_start'),
  content_type: z.enum(['text/markdown', 'application/json', 'text/plain']),
  estimated_bytes: z.number().int().min(0).nullable().optional(),
})

const PayloadDeltaFrameSchema = BaseFrame.extend({
  kind: z.literal('payload_delta'),
  delta_seq: z.number().int().min(0),
  payload: z.string(),
})

const PayloadEndFrameSchema = BaseFrame.extend({
  kind: z.literal('payload_end'),
  delta_count: z.number().int().min(0),
  status: z.enum(['ok', 'aborted']),
})

const BackpressureSignalFrameSchema = BaseFrame.extend({
  kind: z.literal('backpressure'),
  signal: z.enum(['pause', 'resume', 'throttle']),
  source: z.enum(['tui_reader', 'backend_writer', 'upstream_429']),
  queue_depth: z.number().int().min(0),
  hwm: z.number().int().min(1),
  retry_after_ms: z.number().int().min(0).nullable().optional(),
  hud_copy_ko: z.string().min(1),
  hud_copy_en: z.string().min(1),
})

const ResumeRequestFrameSchema = BaseFrame.extend({
  kind: z.literal('resume_request'),
  last_seen_correlation_id: z.string().nullable().optional(),
  last_seen_frame_seq: z.number().int().min(0).nullable().optional(),
  tui_session_token: z.string().min(1),
})

const ResumeResponseFrameSchema = BaseFrame.extend({
  kind: z.literal('resume_response'),
  resumed_from_frame_seq: z.number().int().min(0),
  replay_count: z.number().int().min(0),
  server_session_id: z.string(),
  heartbeat_interval_ms: z.number().int().min(1000),
})

const ResumeRejectedFrameSchema = BaseFrame.extend({
  kind: z.literal('resume_rejected'),
  reason: z.enum([
    'ring_evicted',
    'session_unknown',
    'token_mismatch',
    'protocol_incompatible',
    'session_expired',
  ]),
  detail: z.string(),
})

const HeartbeatFrameSchema = BaseFrame.extend({
  kind: z.literal('heartbeat'),
  direction: z.enum(['ping', 'pong']),
  peer_frame_seq: z.number().int().min(0),
})

const NotificationPushFrameSchema = BaseFrame.extend({
  kind: z.literal('notification_push'),
  subscription_id: z.string(),
  adapter_id: z.string(),
  event_guid: z.string(),
  payload_content_type: z.enum(['text/plain', 'application/json']),
  payload: z.string(),
})

// Epic #1636 P5 — plugin_op control plane.
const PluginOpFrameSchema = BaseFrame.extend({
  kind: z.literal('plugin_op'),
  op: z.enum(['request', 'progress', 'complete']),
  request_op: z.enum(['install', 'uninstall', 'list']).nullable().optional(),
  name: z.string().nullable().optional(),
  requested_version: z.string().nullable().optional(),
  dry_run: z.boolean().nullable().optional(),
  progress_phase: z.number().int().min(1).max(7).nullable().optional(),
  progress_message_ko: z.string().nullable().optional(),
  progress_message_en: z.string().nullable().optional(),
  result: z.enum(['success', 'failure']).nullable().optional(),
  exit_code: z.number().int().nullable().optional(),
  receipt_id: z.string().nullable().optional(),
})

// Epic ε #2296 — adapter_manifest_sync (22nd arm).
// Backend-emitted once at boot after register_all_tools() completes.
// AdapterManifestEntry sub-schema (per data-model.md § 4).
const AdapterManifestEntrySchema = z.object({
  tool_id: z.string().min(1),
  name: z.string().min(1).max(80),
  primitive: z.enum(['lookup', 'submit', 'subscribe', 'verify', 'resolve_location']),
  policy_authority_url: z.string().url().nullable().optional(),
  source_mode: z.enum(['live', 'mock', 'internal']),
})

const AdapterManifestSyncFrameSchema = BaseFrame.extend({
  kind: z.literal('adapter_manifest_sync'),
  entries: z.array(AdapterManifestEntrySchema).min(1),
  manifest_hash: z.string().length(64),
  emitter_pid: z.number().int().positive(),
})

// Epic 2 — consent_revoke_request (arm 22) / consent_revoke_response (arm 23).
const ConsentRevokeRequestFrameSchema = BaseFrame.extend({
  kind: z.literal('consent_revoke_request'),
  request_id: z.string().min(1),
  receipt_id: z.string().min(1),
  scope: z.enum(['once', 'session-all']),
  reason: z.string().nullable().optional(),
})

const ConsentRevokeResponseFrameSchema = BaseFrame.extend({
  kind: z.literal('consent_revoke_response'),
  request_id: z.string().min(1),
  ok: z.boolean(),
  revoked_at: z.string().nullable().optional(),
  record_hash: z.string().nullable().optional(),
  error: z.enum(['already_revoked', 'not_found', 'io_error']).nullable().optional(),
})

// ---------------------------------------------------------------------------
// Zod discriminated-union validator — all 24 IPCFrame arms
// (Spec 287 baseline 10 + Spec 032 9 + Epic #1636 plugin_op + Spec 1978
// chat_request + Epic ε #2296 adapter_manifest_sync +
// Epic 2 consent_revoke_request/response)
// ---------------------------------------------------------------------------

/** Zod discriminated-union validator for all 24 IPCFrame arms. */
export const IPCFrameSchema = z.discriminatedUnion('kind', [
  // Spec 287 baseline (10)
  UserInputFrameSchema,
  AssistantChunkFrameSchema,
  ToolCallFrameSchema,
  ToolResultFrameSchema,
  CoordinatorPhaseFrameSchema,
  WorkerStatusFrameSchema,
  PermissionRequestFrameSchema,
  PermissionResponseFrameSchema,
  SessionEventFrameSchema,
  ErrorFrameSchema,
  // Spec 032 new (9)
  PayloadStartFrameSchema,
  PayloadDeltaFrameSchema,
  PayloadEndFrameSchema,
  BackpressureSignalFrameSchema,
  ResumeRequestFrameSchema,
  ResumeResponseFrameSchema,
  ResumeRejectedFrameSchema,
  HeartbeatFrameSchema,
  NotificationPushFrameSchema,
  // Epic #1636 P5
  PluginOpFrameSchema,
  // Spec 1978 ADR-0001
  ChatRequestFrameSchema,
  // Epic ε #2296 — adapter manifest sync (22nd arm)
  AdapterManifestSyncFrameSchema,
  // Epic 2 — consent revoke arms (23rd + 24th)
  ConsentRevokeRequestFrameSchema,
  ConsentRevokeResponseFrameSchema,
])

// ---------------------------------------------------------------------------
// Kind-narrowed type guards
// ---------------------------------------------------------------------------

export function isUserInput(f: IPCFrame): f is UserInputFrame {
  return f.kind === 'user_input'
}
export function isAssistantChunk(f: IPCFrame): f is AssistantChunkFrame {
  return f.kind === 'assistant_chunk'
}
export function isToolCall(f: IPCFrame): f is ToolCallFrame {
  return f.kind === 'tool_call'
}
export function isToolResult(f: IPCFrame): f is ToolResultFrame {
  return f.kind === 'tool_result'
}
export function isCoordinatorPhase(f: IPCFrame): f is CoordinatorPhaseFrame {
  return f.kind === 'coordinator_phase'
}
export function isWorkerStatus(f: IPCFrame): f is WorkerStatusFrame {
  return f.kind === 'worker_status'
}
export function isPermissionRequest(f: IPCFrame): f is PermissionRequestFrame {
  return f.kind === 'permission_request'
}
export function isPermissionResponse(f: IPCFrame): f is PermissionResponseFrame {
  return f.kind === 'permission_response'
}
export function isSessionEvent(f: IPCFrame): f is SessionEventFrame {
  return f.kind === 'session_event'
}
export function isError(f: IPCFrame): f is ErrorFrame {
  return f.kind === 'error'
}
export function isPayloadStart(f: IPCFrame): f is PayloadStartFrame {
  return f.kind === 'payload_start'
}
export function isPayloadDelta(f: IPCFrame): f is PayloadDeltaFrame {
  return f.kind === 'payload_delta'
}
export function isPayloadEnd(f: IPCFrame): f is PayloadEndFrame {
  return f.kind === 'payload_end'
}
export function isBackpressureSignal(f: IPCFrame): f is BackpressureSignalFrame {
  return f.kind === 'backpressure'
}
export function isResumeRequest(f: IPCFrame): f is ResumeRequestFrame {
  return f.kind === 'resume_request'
}
export function isResumeResponse(f: IPCFrame): f is ResumeResponseFrame {
  return f.kind === 'resume_response'
}
export function isResumeRejected(f: IPCFrame): f is ResumeRejectedFrame {
  return f.kind === 'resume_rejected'
}
export function isHeartbeat(f: IPCFrame): f is HeartbeatFrame {
  return f.kind === 'heartbeat'
}
export function isNotificationPush(f: IPCFrame): f is NotificationPushFrame {
  return f.kind === 'notification_push'
}
export function isAdapterManifestSync(f: IPCFrame): f is AdapterManifestSyncFrame {
  return f.kind === 'adapter_manifest_sync'
}
export function isConsentRevokeRequest(f: IPCFrame): f is ConsentRevokeRequestFrame {
  return f.kind === 'consent_revoke_request'
}
export function isConsentRevokeResponse(f: IPCFrame): f is ConsentRevokeResponseFrame {
  return f.kind === 'consent_revoke_response'
}

// ---------------------------------------------------------------------------
// Codec types
// ---------------------------------------------------------------------------

export type DecodeSuccess = { ok: true; frame: IPCFrame }
export type DecodeError = { ok: false; error: string; raw: string }
export type DecodeResult = DecodeSuccess | DecodeError

/**
 * The three outcomes a pending permission request can resolve to.
 *
 * - 'granted' — citizen approved the primitive call.
 * - 'denied'  — citizen rejected the call (Esc / 'n' key / cleanup).
 * - 'timeout' — KOSMOS_PERMISSION_TIMEOUT_SEC elapsed with no response
 *               (fail-closed per Constitution §II; backend treats identically
 *               to 'denied').
 *
 * Used by setPendingPermission / resolvePermissionDecision in sessionStore
 * (data-model.md § 4, contract pending-permission-slot.md).
 */
export type PermissionDecision = 'granted' | 'denied' | 'timeout'

// Re-export ToolDefinition from generated types so consumers can import from
// a single entry point (codec.ts) without depending on frames.generated.ts.
export type { ToolDefinition, ToolDefinitionFunction } from './frames.generated.js'

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Serialise *frame* to a JSON string terminated by a single newline.
 *
 * ``JSON.stringify`` escapes bare ``\n`` in string values to the two-character
 * JSON sequence ``\\n`` natively, so each frame occupies exactly one line
 * (FR-009).  A pre-escape step would double-encode and leave receivers with a
 * literal backslash-n in place of the original newline.
 */
export function encodeFrame(frame: IPCFrame): string {
  return JSON.stringify(frame) + '\n'
}

/**
 * Attempt to decode a single line of JSON into a validated IPCFrame.
 *
 * @param line - A single JSON string (without a trailing newline).
 * @returns A {@link DecodeResult}; check `.ok` before accessing `.frame`.
 */
export function decodeFrame(line: string): DecodeResult {
  let parsed: unknown
  try {
    parsed = JSON.parse(line)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    return { ok: false, error: `JSON parse error: ${msg}`, raw: line }
  }

  const result = IPCFrameSchema.safeParse(parsed)
  if (!result.success) {
    return {
      ok: false,
      error: `Zod validation error: ${result.error.message}`,
      raw: line,
    }
  }

  return { ok: true, frame: result.data as IPCFrame }
}

/**
 * Split a potentially-partial buffer string into complete frames + a remainder.
 *
 * The IPC protocol delimits frames with ``\n``.  Since Bun's stdout pipe may
 * deliver multiple lines in a single chunk (or a partial line), this function
 * accumulates a remainder across calls.
 *
 * @param buffer - The current accumulated buffer (may include previous
 *   incomplete lines concatenated with new data from the pipe).
 * @returns
 *   - `frames`: Array of {@link DecodeResult} — one entry per complete line,
 *     in arrival order.
 *   - `remainder`: Incomplete trailing bytes (no newline yet) to prepend to
 *     the next buffer chunk.
 */
export function decodeFrames(buffer: string): { frames: DecodeResult[]; remainder: string } {
  const parts = buffer.split('\n')
  // The last element is either empty (if buffer ends with \n) or a partial
  // line that must be held over until the next chunk arrives.
  const remainder = parts.pop() ?? ''
  const frames: DecodeResult[] = []
  for (const part of parts) {
    const trimmed = part.trim()
    if (trimmed.length === 0) continue // skip blank lines
    frames.push(decodeFrame(trimmed))
  }
  return { frames, remainder }
}
