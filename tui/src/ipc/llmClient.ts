// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1633 P2 · Anthropic→FriendliAI LLM client.
//
// Emulates the Anthropic SDK Messages.create streaming-generator surface
// consumed by QueryEngine.ts and query.ts, but all wire traffic goes over the
// Spec 032 stdio IPC bridge (TS) → Python backend → FriendliAI Serverless.
// TS never speaks HTTPS to FriendliAI directly (docs/vision.md § L1-A A1,
// Constitution Principle I rewrite boundary).
//
// T007: stream() — async generator body translating Spec 032 frames into
//       UmmayaRawMessageStreamEvent values.
// T008: complete() — drives stream() to exhaustion, returns UmmayaMessageFinal.
// T009: OTEL gen_ai.client.invoke span — emitted on every stream() call.
// T010: ummaya.prompt.hash — sourced from bridge.systemPromptHash if available;
//       placeholder empty string with TODO(T091) if not yet wired.

import { trace, SpanStatusCode } from '@opentelemetry/api'
import type { Span } from '@opentelemetry/api'
import type { IPCBridge } from './bridge.js'
import { makeUUIDv7, makeBaseEnvelope } from './envelope.js'
import type { AssistantChunkFrame, BackpressureSignalFrame, ChatMessage as IPCChatMessage, ChatRequestFrame, ErrorFrame, ProgressEventFrame, ToolCallFrame, ToolResultFrame, ToolDefinition as IPCToolDefinition } from './frames.generated.js'
import type { PendingCallRegistry } from '../tools/_shared/pendingCallRegistry.js'
import { getOrCreatePendingCallRegistry } from './pendingCallSingleton.js'
import type {
  UmmayaMessageStreamParams,
  UmmayaRawMessageStreamEvent,
  UmmayaMessageFinal,
  UmmayaUsage,
  UmmayaContentBlockParam,
  UmmayaStopReason,
} from './llmTypes.js'

export const UMMAYA_DEFAULT_MODEL = 'LGAI-EXAONE/K-EXAONE-236B-A23B'

export type LLMClientErrorClass = 'llm' | 'tool' | 'network'

export class LLMClientError extends Error {
  readonly errorClass: LLMClientErrorClass
  readonly code: string
  readonly retryAfterMs?: number

  constructor(
    errorClass: LLMClientErrorClass,
    code: string,
    message: string,
    retryAfterMs?: number,
  ) {
    super(message)
    this.name = 'LLMClientError'
    this.errorClass = errorClass
    this.code = code
    this.retryAfterMs = retryAfterMs
  }
}

export interface LLMClientOptions {
  bridge: IPCBridge
  model?: string
  sessionId: string
  /**
   * Session-scoped pending call registry for resolving tool_result frames.
   * If omitted, the process-wide singleton from pendingCallSingleton.ts is used.
   * Tests inject a fresh instance for isolation (I-D5).
   */
  pendingCallRegistry?: PendingCallRegistry
}

// ---------------------------------------------------------------------------
// OTEL tracer (T009)
// ---------------------------------------------------------------------------

const _tracer = trace.getTracer('ummaya.tui.llm', '0.1.0')

// ---------------------------------------------------------------------------
// Internal usage accumulator populated from the done-frame trailer
// ---------------------------------------------------------------------------

interface _TurnAccumulator {
  messageId: string | null
  contentBlocks: UmmayaContentBlockParam[]
  usage: UmmayaUsage
  stopReason: UmmayaStopReason
  /** Index of the current text block. It is opened lazily on the first
   *  CC-compatible text delta, not at message_start. */
  blockIndex: number
  /** Monotonic counter for tool_use blocks within this turn. The nth
   *  tool_use block lands at index `blockIndex + n` (so text is 0, tool
   *  blocks are 1, 2, 3, ...). Incrementing this counter must NOT mutate
   *  `blockIndex` — otherwise the terminal `content_block_stop` for text
   *  fires on the wrong index (Codex review P1 on PR #1706). */
  toolBlockCounter: number
  /** Index of the thinking block, if any. K-EXAONE's reasoning_content
   *  channel is forwarded by the backend as `AssistantChunkFrame.thinking`;
   *  llmClient mirrors CC's claude.ts:2148-2165 by routing those chunks to
   *  a dedicated thinking content block (`type: 'thinking'`). The block
   *  is opened lazily on the first thinking delta and closed before text/tool
   *  blocks, matching CC's one-open-content-block stream shape. */
  thinkingBlockIndex: number | undefined
  /** Currently open non-tool block. CC closes text/thinking before tool_use. */
  openBlockIndex: number | undefined
  seenFirstChunk: boolean
}

function _defaultAccumulator(): _TurnAccumulator {
  return {
    messageId: null,
    contentBlocks: [],
    usage: { input_tokens: 0, output_tokens: 0 },
    stopReason: 'end_turn',
    blockIndex: -1,
    toolBlockCounter: 0,
    thinkingBlockIndex: undefined,
    openBlockIndex: undefined,
    seenFirstChunk: false,
  }
}

// ---------------------------------------------------------------------------
// Helper: extract usage from an AssistantChunkFrame done-trailer.
//
// Spec 032 does not currently define a typed usage payload on the frame itself;
// the Python backend is expected to embed usage counts in the frame's `trailer`
// extra fields or in a sibling ephemeral dict.  Until the backend-side contract
// is finalised in Spec 032 US4, we read from `(frame as any).usage` first
// (a forward-compatible extension field the backend may include) and fall back
// to zeros.  A TODO(T091) marks the binding point for the actual backend wiring.
// ---------------------------------------------------------------------------

function _extractUsage(frame: AssistantChunkFrame): UmmayaUsage {
  // TODO(T091): Once the Python backend embeds usage in the done-frame's trailer
  // extension fields, read them here.  For now, read from an optional `usage`
  // property that the backend may attach to the frame as a forward-compat field.
  const raw = (frame as Record<string, unknown>)['usage']
  if (raw && typeof raw === 'object') {
    const u = raw as Record<string, unknown>
    return {
      input_tokens: typeof u['input_tokens'] === 'number' ? u['input_tokens'] : 0,
      output_tokens: typeof u['output_tokens'] === 'number' ? u['output_tokens'] : 0,
      cache_read_input_tokens:
        typeof u['cache_read_input_tokens'] === 'number'
          ? u['cache_read_input_tokens']
          : undefined,
    }
  }
  return { input_tokens: 0, output_tokens: 0 }
}

/**
 * LLMClient — stdio-IPC-backed LLM client.
 *
 * Contracts/llm-client.md § 1.1 / § 1.2 define the full surface.
 */
export class LLMClient {
  readonly bridge: IPCBridge
  readonly model: string
  readonly sessionId: string
  readonly pendingCallRegistry: PendingCallRegistry
  /** Per-instance flag — emit FR-013 checkpoint marker exactly once per session. */
  checkpointEmitted: boolean = false

  constructor(opts: LLMClientOptions) {
    this.bridge = opts.bridge
    this.model = opts.model ?? UMMAYA_DEFAULT_MODEL
    this.sessionId = opts.sessionId
    this.pendingCallRegistry = opts.pendingCallRegistry ?? getOrCreatePendingCallRegistry()
  }

  // -------------------------------------------------------------------------
  // T007: stream() — async generator body
  // -------------------------------------------------------------------------

  /**
   * Begin an LLM turn.
   *
   * Yields {@link UmmayaRawMessageStreamEvent} values, returning a
   * {@link UmmayaMessageFinal} from the generator on normal completion.
   *
   * Implementation follows contracts/llm-client.md § 1.1 / § 1.2 (G1..G6):
   *  G1 — no direct HTTPS; all traffic via bridge.send().
   *  G2 — exactly one OTEL gen_ai.client.invoke span per call.
   *  G3 — model is forwarded from constructor (caller's responsibility).
   *  G4 — ErrorFrame(class=llm, code=auth) → immediate LLMClientError, no retry.
   *  G5 — BackpressureSignalFrame → pause until retry_after_ms; Python owns retry.
   *  G6 — return value carries stop_reason + usage from done-frame trailer.
   */
  async *stream(
    params: UmmayaMessageStreamParams,
  ): AsyncGenerator<UmmayaRawMessageStreamEvent, UmmayaMessageFinal, void> {
    // ------------------------------------------------------------------
    // Step 1: mint a fresh correlation_id for this turn (V1 invariant).
    // ------------------------------------------------------------------
    const correlationId = makeUUIDv7()

    // ------------------------------------------------------------------
    // Step 2: open OTEL span gen_ai.client.invoke (T009).
    //
    // T010: ummaya.prompt.hash — read from bridge.systemPromptHash if
    // present; US4 task T091 wires the actual handshake extension.
    // TODO(T091): replace placeholder once bridge exposes systemPromptHash.
    // ------------------------------------------------------------------
    const promptHash: string = (this.bridge as unknown as Record<string, unknown>)['systemPromptHash'] as string ?? ''
    // TODO(T091): Once US4 wires bridge.systemPromptHash from the backend
    // handshake, the placeholder above becomes the real 64-char SHA-256 hex.

    const span: Span = _tracer.startSpan('gen_ai.client.invoke', {
      attributes: {
        'gen_ai.system': 'friendli_exaone',
        'gen_ai.operation.name': 'chat',
        'gen_ai.request.model': this.model,
        'gen_ai.request.max_tokens': params.max_tokens,
        ...(params.temperature !== undefined
          ? { 'gen_ai.request.temperature': params.temperature }
          : {}),
        'ummaya.correlation_id': correlationId,
        'ummaya.session_id': this.sessionId,
        // T010: ummaya.prompt.hash from bridge handshake metadata.
        'ummaya.prompt.hash': promptHash,
      },
    })

    // ------------------------------------------------------------------
    // Per-turn state accumulator (used to construct the return value).
    // ------------------------------------------------------------------
    const acc = _defaultAccumulator()

    try {
      // ----------------------------------------------------------------
      // Step 3: construct ChatRequestFrame (Spec 1978 ADR-0001).
      //
      // ChatRequestFrame is the tools-aware frame consumed by the backend's
      // _handle_chat_request handler (src/ummaya/ipc/stdio.py:1130). It
      // carries:
      //   - `messages`: full conversation history flattened to plain text
      //   - `tools`: OpenAI-style function-calling tool definitions
      //   - `system`: dynamic system prompt (override of bridge's cached one)
      //
      // The legacy UserInputFrame path is dead — backend explicitly notes
      // "UserInputFrame{text=t} ≡ ChatRequestFrame{messages=[{role:'user',
      // content:t}], tools=[]}" (frame_schema.py:267-268). We bypass that
      // legacy translation and emit ChatRequestFrame directly so K-EXAONE
      // sees the tool inventory + autonomously routes to lookup / kma /
      // hira / nmc / etc. tools.
      //
      // Per Epic #2112 (memory feedback_ummaya_uses_cc_query_engine): the
      // agentic loop runs INSIDE the backend's _handle_chat_request — TS
      // sends one ChatRequestFrame per user turn, backend loops internally
      // (LLM → tool_use → tool_result → LLM → … up to UMMAYA_AGENTIC_LOOP_
      // MAX_TURNS) and emits AssistantChunkFrame on the final answer.
      // ----------------------------------------------------------------

      // Translate Anthropic-shape UmmayaMessageParam[] → OpenAI-shape ChatMessage[].
      // ChatRequestFrame.messages.content is a plain string (frames.generated.ts
      // Content = string), so multi-block content is flattened to a single
      // text payload. tool_use and tool_result blocks from prior turns are
      // dropped here — the backend's internal agentic loop maintains its
      // own intra-turn tool history; TUI history retains only user / assistant
      // textual exchanges per ADR-0005.
      const ipcMessages = params.messages.map<IPCChatMessage>(m => {
        const role: IPCChatMessage['role'] = m.role === 'assistant' ? 'assistant' : 'user'
        let content = ''
        if (typeof m.content === 'string') {
          content = m.content
        } else {
          content = m.content
            .filter((b): b is { type: 'text'; text: string } => b.type === 'text')
            .map(b => b.text)
            .join('')
        }
        return { role, content }
      })
      // ChatRequestFrame requires Messages = [ChatMessage, ...ChatMessage[]] — non-empty.
      // If params.messages somehow arrives empty, synthesise an empty user turn so the
      // schema validator on the backend does not reject the frame.
      const safeMessages: IPCChatMessage[] = ipcMessages.length > 0
        ? ipcMessages
        : [{ role: 'user', content: '' }]

      // Translate Anthropic-shape UmmayaToolDefinition[] → OpenAI-shape ToolDefinition[].
      const ipcTools: IPCToolDefinition[] | undefined = params.tools && params.tools.length > 0
        ? params.tools.map<IPCToolDefinition>(t => ({
            type: 'function',
            function: {
              name: t.name,
              ...(t.description !== undefined ? { description: t.description } : {}),
              parameters: t.input_schema as Record<string, unknown>,
            },
          }))
        : undefined

      const baseEnvelope = makeBaseEnvelope({
        sessionId: this.sessionId,
        correlationId,
      })

      const chatRequestFrame: ChatRequestFrame = {
        ...baseEnvelope,
        kind: 'chat_request',
        role: 'tui',
        messages: safeMessages as ChatRequestFrame['messages'],
        ...(ipcTools !== undefined ? { tools: ipcTools } : {}),
        ...(params.system !== undefined ? { system: params.system } : {}),
        max_tokens: params.max_tokens,
        ...(params.temperature !== undefined ? { temperature: params.temperature } : {}),
        ...(params.reasoning_mode !== undefined
          ? { reasoning_mode: params.reasoning_mode }
          : {}),
      }

      // ----------------------------------------------------------------
      // Step 4: send the frame.
      // ----------------------------------------------------------------
      const sent = this.bridge.send(chatRequestFrame)
      if (!sent) {
        throw new LLMClientError(
          'network',
          'ipc_transport',
          'Backend has exited; cannot start LLM turn',
        )
      }

      // ----------------------------------------------------------------
      // Step 5: consume inbound frames filtered on correlation_id.
      //
      // CC reference: services/api/claude.ts:1980-2295 — CC's streaming-event
      // taxonomy (message_start, content_block_start, content_block_delta,
      // content_block_stop, message_delta, message_stop). UMMAYA's IPC bridge
      // converts AssistantChunkFrame / ToolCallFrame / ToolResultFrame back
      // into the same event shapes so the rest of the SDK (assembly, history,
      // rendering) stays byte-equivalent with CC.
      //
      // Channel coverage per Spec 2521 parity-matrix.md (verified 2026-05-01):
      //   ✓ implemented: text_delta (claude.ts:2113), thinking_delta (2148),
      //     input_json_delta (2087), tool_use start (1997), text start (2019),
      //     thinking start (2030), content_block_stop (2171), message_start (1980),
      //     message_delta (2213), message_stop (2295)
      //   // SKIPPED — UMMAYA-N/A: signature_delta (2127) — K-EXAONE/FriendliAI
      //     does not emit thinking signatures (verified by probe_friendli_channels.py
      //     2026-05-01)
      //   // SKIPPED — UMMAYA-N/A: citations_delta (2084) — UMMAYA adapters
      //     return citations in tool_result envelopes, not stream events
      //   // SKIPPED — UMMAYA-N/A: connector_text_delta (2068) — Anthropic-only
      //     connector blocks; UMMAYA does not use connectors
      //   // SKIPPED — UMMAYA-N/A: server_tool_use start (2003) — UMMAYA uses IPC
      //     primitive bridge for all tool dispatch; no server-side tools
      // ----------------------------------------------------------------
      let streamDone = false
      const model = this.model
      const ensureMessageStart = function* (
        messageId: string,
      ): Generator<UmmayaRawMessageStreamEvent, void, unknown> {
        if (acc.seenFirstChunk) return
        acc.seenFirstChunk = true
        acc.messageId = messageId
        yield {
          type: 'message_start',
          message: {
            id: messageId,
            role: 'assistant',
            model,
          },
        } satisfies UmmayaRawMessageStreamEvent
      }

      const closeOpenBlock = function* (): Generator<
        UmmayaRawMessageStreamEvent,
        void,
        unknown
      > {
        if (acc.openBlockIndex === undefined) return
        yield {
          type: 'content_block_stop',
          index: acc.openBlockIndex,
        } satisfies UmmayaRawMessageStreamEvent
        acc.openBlockIndex = undefined
      }

      const ensureTextBlock = function* (): Generator<
        UmmayaRawMessageStreamEvent,
        void,
        unknown
      > {
        if (acc.openBlockIndex === acc.blockIndex && acc.blockIndex >= 0) {
          return
        }
        yield* closeOpenBlock()
        const textIndex = acc.contentBlocks.length
        acc.blockIndex = textIndex
        acc.contentBlocks[textIndex] = { type: 'text', text: '' }
        acc.openBlockIndex = textIndex
        yield {
          type: 'content_block_start',
          index: textIndex,
          content_block: { type: 'text', text: '' },
        } satisfies UmmayaRawMessageStreamEvent
      }

      const ensureThinkingBlock = function* (): Generator<
        UmmayaRawMessageStreamEvent,
        void,
        unknown
      > {
        if (
          acc.thinkingBlockIndex !== undefined &&
          acc.openBlockIndex === acc.thinkingBlockIndex
        ) {
          return
        }
        yield* closeOpenBlock()
        const thinkingIdx = acc.contentBlocks.length
        acc.thinkingBlockIndex = thinkingIdx
        acc.contentBlocks[thinkingIdx] = { type: 'thinking', thinking: '' }
        acc.openBlockIndex = thinkingIdx
        yield {
          type: 'content_block_start',
          index: thinkingIdx,
          content_block: { type: 'thinking', thinking: '' },
        } satisfies UmmayaRawMessageStreamEvent
      }

      for await (const frame of this.bridge.frames()) {
        // Filter: only process frames for this turn's correlation_id.
        if (frame.correlation_id !== correlationId) continue

        // ---- ProgressEventFrame ----------------------------------------
        // Deterministic harness progress. This is safe UI state, not provider
        // reasoning. It paints even when reasoning mode suppresses thinking.
        if (frame.kind === 'progress_event') {
          const progress = frame as ProgressEventFrame
          yield* ensureMessageStart(`progress-${correlationId}`)
          yield* ensureTextBlock()

          const progressText = `${
            progress.message_ko ?? progress.message_en ?? progress.phase
          }\n`
          yield {
            type: 'content_block_delta',
            index: acc.blockIndex,
            delta: {
              type: 'text_delta',
              text: progressText,
            },
          } satisfies UmmayaRawMessageStreamEvent
          const existing = acc.contentBlocks[acc.blockIndex]
          if (existing && existing.type === 'text') {
            existing.text += progressText
          }
          continue
        }

        // ---- AssistantChunkFrame ----------------------------------------
        // CC reference: services/api/claude.ts:1980-2169 (the message_start +
        // content_block_start + content_block_delta + content_block_stop
        // emission for text + thinking content blocks).
        if (frame.kind === 'assistant_chunk') {
          const chunk = frame as AssistantChunkFrame

          if (!chunk.done) {
            // First chunk: emit message_start + content_block_start.
            // CC reference: services/api/claude.ts:1980 (message_start),
            //               services/api/claude.ts:2019 (text content_block_start).
            if (!acc.seenFirstChunk) {
              yield* ensureMessageStart(chunk.message_id)
            }

            // Thinking delta — K-EXAONE's reasoning_content channel arrives
            // here. CC's claude.ts:2148-2165 routes thinking_delta to its own
            // content block; we mirror that so Message.tsx can pick up
            // `type: 'thinking'` blocks and route them to the
            // AssistantThinkingMessage component (∴ Thinking dim italic).
            if (chunk.thinking && chunk.thinking.length > 0) {
              yield* ensureThinkingBlock()
              const thinkingIdx = acc.thinkingBlockIndex!
              yield {
                type: 'content_block_delta',
                index: thinkingIdx,
                delta: { type: 'thinking_delta', thinking: chunk.thinking },
              } satisfies UmmayaRawMessageStreamEvent
              const existing = acc.contentBlocks[thinkingIdx]
              if (existing && existing.type === 'thinking') {
                existing.thinking += chunk.thinking
              }
            }

            // Emit text delta (even if delta is empty — forward compat).
            if (chunk.delta.length > 0) {
              yield* ensureTextBlock()
              yield {
                type: 'content_block_delta',
                index: acc.blockIndex,
                delta: { type: 'text_delta', text: chunk.delta },
              } satisfies UmmayaRawMessageStreamEvent

              // Accumulate text into the content block for the final object.
              const existing = acc.contentBlocks[acc.blockIndex]
              if (existing && existing.type === 'text') {
                existing.text += chunk.delta
              } else {
                // First delta for this block index.
                acc.contentBlocks[acc.blockIndex] = { type: 'text', text: chunk.delta }
              }
            }
          } else {
            // done=true: terminal chunk (V2 invariant satisfied here).

            // If we never saw a first chunk (edge: backend sends done=true
            // immediately on an empty response), bootstrap the message events.
            if (!acc.seenFirstChunk) {
              yield* ensureMessageStart(chunk.message_id)
            }

            // Emit any final delta text if present.
            if (chunk.delta.length > 0) {
              yield* ensureTextBlock()
              yield {
                type: 'content_block_delta',
                index: acc.blockIndex,
                delta: { type: 'text_delta', text: chunk.delta },
              } satisfies UmmayaRawMessageStreamEvent
              const existing = acc.contentBlocks[acc.blockIndex]
              if (existing && existing.type === 'text') {
                existing.text += chunk.delta
              } else {
                acc.contentBlocks[acc.blockIndex] = { type: 'text', text: chunk.delta }
              }
            }

            // Extract usage from the done-frame.
            const usage = _extractUsage(chunk)
            acc.usage = usage

            // CC reference: services/api/claude.ts:2171 (content_block_stop).
            yield* closeOpenBlock()

            // CC reference: services/api/claude.ts:2213 (message_delta with
            // stop_reason + usage).
            yield {
              type: 'message_delta',
              delta: { stop_reason: acc.stopReason },
              usage,
            } satisfies UmmayaRawMessageStreamEvent

            // CC reference: services/api/claude.ts:2295 (message_stop).
            yield { type: 'message_stop' } satisfies UmmayaRawMessageStreamEvent

            streamDone = true
            break
          }
        }

        // ---- ToolCallFrame ----------------------------------------------
        // CC reference: services/api/claude.ts:1997 (content_block_start with
        // tool_use type) + services/api/claude.ts:2087 (input_json_delta for
        // streaming arguments). UMMAYA pre-buffers arguments at the backend
        // (stdio.py tool_call_buf) and emits the complete tool_use block in a
        // single ToolCallFrame, so input_json_delta is collapsed into the
        // initial content_block_start payload.
        else if (frame.kind === 'tool_call') {
          const toolFrame = frame as ToolCallFrame
          yield* ensureMessageStart(`tool-${correlationId}`)
          yield* closeOpenBlock()
          // tool_call frames may arrive interleaved with text streaming AND
          // thinking streaming in a multi-turn / parallel-tool / K-EXAONE
          // reasoning scenario. Allocate the tool block at the next free
          // contentBlocks slot rather than `blockIndex + toolBlockCounter`
          // — the latter collides with the thinking block, which lives at
          // `contentBlocks.length` at first thinking_delta (typically 1
          // after the text block, the same slot the first tool would have
          // claimed via `0 + 1`). Codex P1 review on PR #2577 (2026-04-30):
          // collision corrupts the reasoning trace by overwriting it with
          // tool_use, breaking the dim-italic ∴ Thinking glyph for any
          // turn that emits both reasoning and a tool call. The
          // toolBlockCounter is preserved as a per-turn stat counter only.
          const toolBlockIndex = acc.contentBlocks.length
          acc.toolBlockCounter += 1
          yield {
            type: 'content_block_start',
            index: toolBlockIndex,
            content_block: {
              type: 'tool_use',
              id: toolFrame.call_id,
              name: toolFrame.name,
              input: toolFrame.arguments as Record<string, unknown>,
            },
          } satisfies UmmayaRawMessageStreamEvent

          yield {
            type: 'content_block_stop',
            index: toolBlockIndex,
          } satisfies UmmayaRawMessageStreamEvent

          acc.contentBlocks[toolBlockIndex] = {
            type: 'tool_use',
            id: toolFrame.call_id,
            name: toolFrame.name,
            input: toolFrame.arguments as Record<string, unknown>,
          }

          acc.stopReason = 'tool_use'
          yield {
            type: 'message_delta',
            delta: { stop_reason: 'tool_use' },
            usage: acc.usage,
          } satisfies UmmayaRawMessageStreamEvent
          yield { type: 'message_stop' } satisfies UmmayaRawMessageStreamEvent

          streamDone = true
          break
        }

        // ---- ToolResultFrame (I-D5 + Epic ζ smoke checkpoint, FR-013) ----
        else if (frame.kind === 'tool_result') {
          const trFrame = frame as ToolResultFrame
          // Resolve the pending Tool.call registered by dispatchPrimitive.
          // This is the CC-aligned path: provider yields assistant(tool_use),
          // query.ts calls Tool.call(), and the backend answers that inbound
          // tool_call with this tool_result frame.
          this.pendingCallRegistry.resolve(trFrame.call_id, trFrame)

          // Emit the canonical FR-013 / I-P2 checkpoint marker exactly once
          // when a send primitive's tool_result envelope contains a
          // hometax receipt id matching the regex. This is the convergence
          // marker the PTY smoke harness (T015 .expect script) greps for.
          if (process.env['UMMAYA_SMOKE_CHECKPOINTS'] === 'true') {
            try {
              const env = trFrame.envelope as Record<string, unknown>
              const envKind = typeof env?.['kind'] === 'string' ? env['kind'] : ''
              if (envKind === 'send') {
                const RX = /hometax-\d{4}-\d{2}-\d{2}-RX-[A-Z0-9]{5}/
                const haystack =
                  (typeof trFrame.transaction_id === 'string' ? trFrame.transaction_id : '') +
                  ' ' +
                  JSON.stringify(env)
                if (RX.test(haystack) && !this.checkpointEmitted) {
                  this.checkpointEmitted = true
                  process.stderr.write('CHECKPOINTreceipt token observed\n')
                }
              }
            } catch {
              // Ignore serialization errors; checkpoint is best-effort.
            }
          }
          // Do NOT yield a SDK event — the SDK loop continues to await message_stop
        }

        // ---- ErrorFrame -------------------------------------------------
        else if (frame.kind === 'error') {
          const errFrame = frame as ErrorFrame
          // Map ErrorFrame to LLMClientError (G4 fast-path for auth errors).
          const details = errFrame.details as Record<string, unknown>
          const errClass: LLMClientErrorClass =
            details['class'] === 'llm' || details['class'] === 'tool'
              ? (details['class'] as LLMClientErrorClass)
              : 'network'
          throw new LLMClientError(
            errClass,
            errFrame.code,
            errFrame.message,
          )
        }

        // ---- BackpressureSignalFrame (source=upstream_429) ---------------
        else if (frame.kind === 'backpressure') {
          const bpFrame = frame as BackpressureSignalFrame
          // G5: pause until retry_after_ms, then continue (Python owns retry).
          if (bpFrame.source === 'upstream_429' && bpFrame.retry_after_ms != null && bpFrame.retry_after_ms > 0) {
            await new Promise<void>((resolve) =>
              setTimeout(resolve, bpFrame.retry_after_ms!),
            )
          }
          // continue consuming the frame iterable — no re-send.
          continue
        }

        // ---- Unknown frame kind (matching correlation_id) ----------------
        else {
          // Log at WARN and skip (forward compatibility).
          process.stderr.write(
            `[UMMAYA LLMClient WARN] Unexpected frame kind="${(frame as { kind?: string }).kind}" for correlation_id=${correlationId}\n`,
          )
        }
      }

      // ------------------------------------------------------------------
      // Step 6: stream closed without done=true → protocol violation (V2).
      // ------------------------------------------------------------------
      if (!streamDone) {
        throw new LLMClientError(
          'network',
          'ipc_transport',
          'Stream ended before done=true',
        )
      }

      // ------------------------------------------------------------------
      // Step 7: finalize OTEL span — status OK (T009).
      // ------------------------------------------------------------------
      span.setAttribute('gen_ai.usage.input_tokens', acc.usage.input_tokens)
      span.setAttribute('gen_ai.usage.output_tokens', acc.usage.output_tokens)
      if (acc.usage.cache_read_input_tokens !== undefined) {
        span.setAttribute('gen_ai.usage.cache_read_input_tokens', acc.usage.cache_read_input_tokens)
      }
      span.setStatus({ code: SpanStatusCode.OK })
      span.end()

      // ------------------------------------------------------------------
      // Step 8: return UmmayaMessageFinal (G6).
      //
      // SWAP/llm-provider(2521, 2026-05-02): K-EXAONE on FriendliAI emits
      // `delta.reasoning_content` and `delta.tool_calls` on independent
      // channels with no guaranteed ordering. CC's Anthropic API
      // guarantees ``thinking`` content_blocks ALWAYS precede ``tool_use``
      // blocks because the API serializes them inline. With K-EXAONE the
      // streaming order can land tool_use blocks BEFORE thinking blocks
      // in ``acc.contentBlocks`` — which makes the TUI render
      // ``● find(...)`` BEFORE ``∴ Thinking — ...`` and confuses the
      // citizen ("왜 도구호출부터 하는거지?", user-reported 2026-05-02).
      //
      // Re-order to canonical CC layout at commit time so the rendered
      // message reads: thinking → text → tool_use, preserving
      // intra-bucket order. Stream-event indices already emitted to the
      // SDK are NOT mutated — only the final ``content`` array.
      // ------------------------------------------------------------------
      const reorderedContent: typeof acc.contentBlocks = []
      const _thinking: typeof acc.contentBlocks = []
      const _text: typeof acc.contentBlocks = []
      const _tools: typeof acc.contentBlocks = []
      const _other: typeof acc.contentBlocks = []
      for (const block of acc.contentBlocks) {
        if (!block) continue
        if (block.type === 'thinking' || block.type === 'redacted_thinking') _thinking.push(block)
        else if (block.type === 'text') _text.push(block)
        else if (block.type === 'tool_use') _tools.push(block)
        else _other.push(block)
      }
      reorderedContent.push(..._thinking, ..._text, ..._tools, ..._other)

      const finalMessage: UmmayaMessageFinal = {
        id: acc.messageId ?? correlationId,
        role: 'assistant',
        model: this.model,
        content: reorderedContent,
        stop_reason: acc.stopReason,
        usage: acc.usage,
      }

      return finalMessage
    } catch (err: unknown) {
      // Finalize OTEL span with ERROR status.
      if (err instanceof LLMClientError) {
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: err.message,
        })
        span.setAttribute('error.type', `${err.errorClass}:${err.code}`)
        span.end()
        throw err
      }
      // Unexpected non-LLMClientError (e.g. bridge internals).
      const msg = err instanceof Error ? err.message : String(err)
      span.setStatus({ code: SpanStatusCode.ERROR, message: msg })
      span.setAttribute('error.type', 'network:unknown')
      span.end()
      throw new LLMClientError('network', 'unknown', msg)
    }
  }

  // -------------------------------------------------------------------------
  // T008: complete() — drives stream() to exhaustion
  // -------------------------------------------------------------------------

  /**
   * Non-streaming convenience — awaits stream() and collects text deltas into
   * a single {@link UmmayaMessageFinal}.
   *
   * The generator's return value already includes the assembled content blocks
   * built inside stream(); we simply drain events and return the final object.
   */
  async complete(params: UmmayaMessageStreamParams): Promise<UmmayaMessageFinal> {
    const chunks: string[] = []
    let final: UmmayaMessageFinal | null = null

    const gen = this.stream(params)
    while (true) {
      const result = await gen.next()
      if (result.done) {
        // result.value is the UmmayaMessageFinal returned by stream().
        final = result.value as UmmayaMessageFinal
        break
      }
      const event = result.value
      if (
        event.type === 'content_block_delta' &&
        event.delta.type === 'text_delta'
      ) {
        chunks.push(event.delta.text)
      }
    }

    if (final !== null) {
      return final
    }

    // Fallback: fabricate a minimal UmmayaMessageFinal from accumulated chunks.
    // This path should not be reached in normal operation because stream()
    // always returns the final object — it's here as a safety net.
    return {
      id: makeUUIDv7(),
      role: 'assistant',
      model: this.model,
      content: [{ type: 'text', text: chunks.join('') }],
      stop_reason: 'end_turn',
      usage: { input_tokens: 0, output_tokens: 0 },
    }
  }
}
