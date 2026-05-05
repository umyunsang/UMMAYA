import { randomUUID, type UUID } from 'crypto'
import { APIUserAbortError } from 'src/sdk-compat.js'
import { autoCompactIfNeeded } from '../services/compact/autoCompact.js'
import { microcompactMessages } from '../services/compact/microCompact.js'
import { getOrCreateKosmosBridge, getKosmosBridgeSessionId } from '../ipc/bridgeSingleton.js'
import type { ChatRequestFrame, IPCFrame } from '../ipc/frames.generated.js'
import { getToolDefinitionsForFrame } from './toolSerialization.js'
import { createAssistantMessage, createSystemMessage, createUserMessage, SYNTHETIC_MODEL } from '../utils/messages.js'
import { buildChatMessagesFromTranscript } from './chatMessagesBuilder.js'

// SWAP/llm-provider(2521) — frontend deps.ts typewriter REVERTED.
//
// Layer 5 frame capture against /tmp/tdb-typewriter (codepoint-by-
// codepoint yield + 30 ms setTimeout) showed _typewriter() entered
// 221 times per turn but the rendered cell-grid still painted the
// 605-byte answer paragraph as a single PTY write at t=26.327 — Ink's
// React reconciler fold all 200 setState dispatches into one commit.
// Pacing at this layer therefore only adds wait latency; it cannot
// dilate the paragraph's paint moment.
//
// The follow-up fix that DOES work (byte-copy file modification of
// AssistantTextMessage / Markdown to add a useState/useInterval
// reveal) is staged separately; until that lands we leave the
// stream_event hot-path untouched so disabled-pacing == zero
// latency cost.

function buildToolUseResultFromEnvelope(
  envelope: { kind?: string; [k: string]: unknown },
): Record<string, unknown> {
  const outboundTraces = Array.isArray(envelope['outbound_traces'])
    ? envelope['outbound_traces']
    : undefined
  const errorMessage =
    typeof envelope['error'] === 'string'
      ? envelope['error']
      : envelope.kind === 'error' && typeof envelope['message'] === 'string'
        ? envelope['message']
        : undefined

  if (errorMessage && errorMessage.length > 0) {
    const errorResult: Record<string, unknown> = {
      ok: false,
      error: {
        kind: typeof envelope.kind === 'string' ? envelope.kind : 'dispatch_error',
        message: errorMessage,
      },
    }
    if (outboundTraces && outboundTraces.length > 0) {
      errorResult['outbound_traces'] = outboundTraces
    }
    return errorResult
  }

  const successResult: Record<string, unknown> = {
    ok: true,
    result: 'result' in envelope ? envelope['result'] : envelope,
  }
  if (outboundTraces && outboundTraces.length > 0) {
    successResult['outbound_traces'] = outboundTraces
  }
  return successResult
}

function stripUiOnlyToolResultFields(toolUseResult: Record<string, unknown>): string {
  const llmFacing = Object.fromEntries(
    Object.entries(toolUseResult).filter(([key]) => key !== 'outbound_traces'),
  )
  return JSON.stringify(llmFacing)
}

function isErrorEnvelope(envelope: { kind?: string; [k: string]: unknown }): boolean {
  return envelope.kind === 'error' || typeof envelope['error'] === 'string'
}


/**
 * KOSMOS-1633 P3 wire-up — replaces the Anthropic-SDK queryModelWithStreaming.
 *
 * Bridges CC's `query()` agentic loop to the Spec 1978 ADR-0001 backend
 * (kosmos.ipc.stdio._handle_chat_request) over the existing Spec 032 IPC
 * envelope. CC's call shape is preserved: yields `AssistantMessage` on
 * completion (CC's query.ts collapses streaming events into a single
 * assistant message anyway). System prompt, tools, and signal are wired
 * through; the rich `options.*` shape is accepted but most fields are
 * informational at this layer — the backend owns model selection,
 * streaming, and tool-call dispatch.
 *
 * Single-frame protocol on this hop:
 *   TUI → backend: ChatRequestFrame { messages, system?, tools? }
 *   backend → TUI: AssistantChunkFrame{...delta, done:true} | ErrorFrame
 *
 * The backend's CC-engine-mirroring native FC dispatch handles tool calls
 * server-side and streams only the final assistant text deltas back; tool
 * results are emitted as separate frames consumed by other TUI subsystems.
 */
async function* queryModelWithStreaming(params: {
  messages: readonly unknown[]
  systemPrompt: unknown
  thinkingConfig?: unknown
  tools?: unknown
  signal?: AbortSignal
  options?: { model?: string; querySource?: string; [k: string]: unknown }
}): AsyncGenerator<unknown> {
  const { messages, systemPrompt, signal } = params
  const correlationId = randomUUID()
  // Outer transcript uuid + inner BetaMessage.id are fixed at turn start so
  // the final AssistantMessage carries stable React keys; rebuilding either
  // mid-stream would collide with the streamingText preview's atomic
  // transition (utils/messages.ts:2984 onStreamingText(() => null)).
  const messageUuid = randomUUID()
  const innerMessageId = randomUUID()
  const turnStartedAt = performance.now()
  const __t = (s: string) => {
    if (process.env.KOSMOS_QUERY_TRACE === '1') {
      try { require('fs').writeSync(2, `[KOSMOS-QUERY] ${s}\n`) } catch {}
    }
  }
  __t(`callModel:enter messages=${messages.length}`)

  // Convert CC `Message[]` → ChatRequestFrame.messages.
  //
  // Lead-Diag-4 (2026-05-04, role='tool' wire conversion): the CC transcript
  // shape is the Anthropic Messages API native shape — tool_result blocks
  // live INSIDE role='user' messages and tool_use blocks live INSIDE
  // role='assistant' messages. K-EXAONE on FriendliAI is OpenAI Chat
  // Completions spec, which requires tool_result as its own role='tool'
  // message keyed by tool_call_id, and assistant tool invocations carried in
  // the tool_calls[] array on the assistant message. ``buildChatMessagesFromTranscript``
  // is the conversion seam — see ``chatMessagesBuilder.ts`` for the
  // promotion rules + OpenAI-spec ordering invariants.
  //
  // Backward compat: legacy transcripts where assistant/user content is a
  // raw string (no structured blocks) flow through unchanged — the converter
  // matches the legacy ``extractText``-based behaviour for the string-content
  // fast path, including the ``min_length=1`` empty-input fallback.
  const chatMessages = buildChatMessagesFromTranscript(messages)

  // ---- spec-multi-turn-contamination diagnostic emit (FR-003)
  // Log the chatMessages tail so we can prove which user turn the TUI
  // serialised onto the wire BEFORE the bridge.send. If the
  // `[CHAT_MESSAGES_BUILT]` line shows a stale tail, H1 (frontend race)
  // is confirmed — the React store snapshot was taken before the new
  // user message landed. Off by default; gated by KOSMOS_QUERY_TRACE=1
  // to share the existing flag (no new env var introduced).
  if (process.env.KOSMOS_QUERY_TRACE === '1') {
    try {
      const tail = chatMessages[chatMessages.length - 1]
      const tailRole = tail?.role ?? '(empty)'
      const tailContent = (tail?.content ?? '').slice(0, 256)
      const userTurns = chatMessages.filter((m) => m.role === 'user').length
      __t(
        `[CHAT_MESSAGES_BUILT] count=${chatMessages.length} ` +
          `user_turns=${userTurns} tail_role=${tailRole} ` +
          `tail_first256=${JSON.stringify(tailContent)}`,
      )
    } catch {
      // Diagnostic must never raise.
    }
  }

  // KOSMOS hotfix #2519 (post-vhs verification, 2026-04-30 — dev-mode answer):
  //
  // The TUI's CC-original `getSystemPrompt()` (tui/src/constants/prompts.ts:428)
  // builds an English developer-facing prompt — the "Doing tasks" section
  // alone tells the model "primarily perform software engineering tasks
  // (solving bugs, adding new functionality, refactoring code, …)" plus
  // hundreds of lines of dev-only directives (tone, scratchpad, hooks,
  // git workflow, etc.). Forwarding that text via ChatRequestFrame.system
  // is what made K-EXAONE answer "안녕! 저는 K-EXAONE 모델입니다 …
  // 소프트웨어 엔지니어링 작업을 지원하며" to a citizen on KOSMOS — it
  // was honestly following the dev-prompt KOSMOS handed it.
  //
  // Earlier (commit 6ab1e4d, "option A simple") only the explicit textsmoke
  // leaks were rewritten to KOSMOS-canonical strings (model-family table,
  // claude.ai availability, Fast-mode descriptor); the bulk of the dev-mode
  // body remained intact, so the citizen still saw a developer assistant.
  //
  // Until a follow-up Spec replaces the entire client-side prompt builder
  // with a citizen-facing KOSMOS prompt (option A "full"), the pragmatic
  // fix is: send no `system` field, and let the backend's PromptLoader
  // resolve `prompts/system_v1.md` (the canonical Korean citizen system
  // prompt) via its existing fallback (src/kosmos/ipc/stdio.py:1213-1216
  // — `if not base_system: loaded = await _ensure_system_prompt()`).
  //
  // The TS-side `systemPrompt` value remains computed for any local
  // consumers (e.g. CC compaction surfaces) but is no longer transmitted.
  const _systemTextDiscarded = extractText(systemPrompt)
  void _systemTextDiscarded
  const bridge = getOrCreateKosmosBridge()
  const sessionId = getKosmosBridgeSessionId()

  // Publish the active tool inventory to the LLM on every turn (FR-001).
  // Backend authoritative-execution rule (FR-005): backend rejects any
  // tool name not in its registry, so unknown entries here are harmless.
  // Per data-model.md § 1: emit per turn, no caching.
  const tools = await getToolDefinitionsForFrame()

  const frame: ChatRequestFrame = {
    session_id: sessionId,
    correlation_id: correlationId,
    ts: new Date().toISOString(),
    role: 'tui',
    kind: 'chat_request',
    messages: chatMessages as ChatRequestFrame['messages'],
    // Intentionally omit `system` — see hotfix #2519 comment above.
    tools: tools as ChatRequestFrame['tools'],
  }

  // Flip the spinner from idle → 'requesting' before the network round-trip
  // so the user sees instant feedback even if the first backend chunk takes
  // a few seconds (handleMessageFromStream:line 2989).
  yield { type: 'stream_request_start' as const }

  __t(`sending chat_request corr=${correlationId} chatMessages=${chatMessages.length}`)
  const sent = bridge.send(frame as unknown as IPCFrame)
  __t(`bridge.send returned ${sent}`)
  if (!sent) {
    throw new Error('KOSMOS bridge send failed (backend exited)')
  }

  // Stream-event projection — yield CC-shape Anthropic SSE events per
  // assistant_chunk frame so handleMessageFromStream pipes text_delta
  // events into onStreamingText for incremental paint
  // (utils/messages.ts:3055-3059). The terminal AssistantMessage with the
  // accumulated text is yielded once on done=true; its outer uuid + inner
  // message.id are pinned to turn-start values so the React message store
  // never sees a duplicate key (the streaming preview lives in separate
  // React state, atomically cleared at line 2984 when the final message
  // arrives).
  let accumulated = ''
  // Spec 2521 — accumulate K-EXAONE reasoning_content into a thinking
  // content block so the terminal AssistantMessage carries the canonical
  // CC shape `[{type:'thinking',...}, {type:'text',...}, {type:'tool_use',...}]`.
  // Without this the live streamingThinking buffer paints reasoning at the
  // BOTTOM of the transcript while tool_use blocks land in the message
  // ABOVE — visually reversing the ReAct order. CC reference:
  // services/api/claude.ts:1995 (content_block_start thinking) +
  // messages.ts:normalizeContentFromAPI (final block array assembly).
  let accumulatedThinking = ''
  let messageStartEmitted = false
  let frameCount = 0
  // Epic #2077 T012 — turn-scoped CC content-block index. Index 0 is the
  // text block opened on the first ``assistant_chunk``; tool_use blocks
  // claim 1, 2, 3, … in arrival order. ``pendingContentBlocks`` mirrors the
  // CC pattern of ``messages.ts:normalizeContentFromAPI`` — every tool_use
  // block emitted during the turn is also accumulated so the terminal
  // ``createAssistantMessage`` carries the canonical ``BetaContentBlock[]``
  // shape (text + tool_use blocks) instead of a raw string. Required by
  // FR-006 (transcript-native invocation record) + FR-009 (one-to-one
  // pairing with tool_result content blocks).
  let blockIndex = 0
  const pendingContentBlocks: Array<{
    type: 'tool_use'
    id: string
    name: string
    input: unknown
  }> = []
  // Epic #2077 T016 — FR-009 one-to-one pairing invariant.
  // Every tool_call frame registers its call_id here; every tool_result frame
  // checks against this set. An unmatched tool_use_id surfaces as a visible
  // error (orphan), satisfying FR-009 "no orphan results".
  const seenToolUseIds = new Set<string>()
  for await (const f of bridge.frames()) {
    frameCount++
    if (frameCount <= 30) {
      const fAll = f as { kind?: string; correlation_id?: string; delta?: string; thinking?: string; done?: boolean; message_id?: string }
      const dStr = JSON.stringify(fAll.delta ?? '').slice(0, 40)
      const tStr = JSON.stringify(fAll.thinking ?? '').slice(0, 40)
      __t(`recv #${frameCount} kind=${fAll.kind} corr=${fAll.correlation_id?.slice(-8)} done=${fAll.done} delta=${dStr} thinking=${tStr}`)
    }
    if (signal?.aborted) {
      throw new APIUserAbortError()
    }
    const fa = f as {
      kind?: string
      correlation_id?: string
      delta?: string
      thinking?: string
      done?: boolean
      message?: string
      // tool_call fields
      call_id?: string
      name?: string
      arguments?: unknown
      // tool_result fields
      envelope?: { kind?: string; [k: string]: unknown }
    }
    if (fa.correlation_id !== correlationId) continue
    if (fa.kind === 'assistant_chunk') {
      const deltaText = fa.delta ?? ''
      const thinkingText = fa.thinking ?? ''
      // First chunk: emit message_start (carries ttftMs for OTPS) +
      // content_block_start so the spinner flips to 'responding'.
      if (!messageStartEmitted) {
        const ttftMs = performance.now() - turnStartedAt
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'message_start' as const,
            message: {
              id: innerMessageId,
              type: 'message',
              role: 'assistant',
              content: [],
              model: SYNTHETIC_MODEL,
              stop_reason: null,
              stop_sequence: null,
              usage: {
                input_tokens: 0,
                output_tokens: 0,
                cache_creation_input_tokens: 0,
                cache_read_input_tokens: 0,
              },
            },
          },
          ttftMs,
        }
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'content_block_start' as const,
            index: 0,
            content_block: { type: 'text' as const, text: '' },
          },
        }
        messageStartEmitted = true
      }

      // K-EXAONE chain-of-thought channel — backend forwards
      // delta.reasoning_content here. Mirror Anthropic's thinking_delta
      // (kosmos/llm/_cc_reference/claude.ts:2148-2161). handleMessageFromStream
      // (utils/messages.ts:3080) routes thinking_delta through onUpdateLength
      // so AssistantThinkingMessage paints the reasoning inline. We also
      // accumulate the full thinking text so the terminal AssistantMessage
      // can carry it as a content block (Spec 2521 ReAct transcript order).
      if (thinkingText.length > 0) {
        accumulatedThinking += thinkingText
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'content_block_delta' as const,
            index: 0,
            delta: { type: 'thinking_delta' as const, thinking: thinkingText },
          },
        }
      }

      accumulated += deltaText
      if (deltaText.length > 0) {
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'content_block_delta' as const,
            index: 0,
            delta: { type: 'text_delta' as const, text: deltaText },
          },
        }
      }

      if (fa.done) {
        // CC mirror (claude.ts:2192-2303): the AssistantMessage is yielded
        // *inside* the content_block_stop branch (line 2210) before the
        // outer for-loop yields stream_event{content_block_stop} (line
        // 2299). handleMessageFromStream then runs onStreamingText(() =>
        // null) at line 2984 against the AssistantMessage, clearing the
        // streamingText preview before message_delta / message_stop drive
        // the spinner from 'responding' to 'tool-use'. Same order here so
        // the deferred → final transition is atomic and matches CC behavior.
        // K-EXAONE often prefixes its first delta with `\n\n`; trim leading
        // whitespace so the rendered turn doesn't open with blank lines.
        // Epic #2077 T012 — when tool_use blocks accumulated during the
        // turn, the terminal AssistantMessage's content array carries them
        // alongside the text block (CC's BetaContentBlock[] shape). Empty
        // text + tool blocks stays valid (the assistant did only tool calls
        // before yielding); empty text + no tool blocks falls through to the
        // string path and createAssistantMessage substitutes NO_CONTENT_MESSAGE.
        const trimmedText = accumulated.trimStart()
        // Spec 2521 — assemble the terminal AssistantMessage content array
        // in CC ReAct order: thinking → text → tool_use. K-EXAONE streams
        // these channels sequentially (probe verified: 1438 chunks, 0 with
        // both reasoning + tool_calls in same chunk). Persisting the
        // thinking block on the transcript preserves the citizen-visible
        // reasoning trail after the live streamingThinking buffer clears.
        // CC reference: services/api/claude.ts:1995 + messages.ts:normalizeContentFromAPI.
        type _AssistantBlock =
          | { type: 'thinking'; thinking: string }
          | { type: 'text'; text: string }
          | { type: 'tool_use'; id: string; name: string; input: unknown }
        const blocks: _AssistantBlock[] = []
        if (accumulatedThinking.length > 0) {
          blocks.push({ type: 'thinking', thinking: accumulatedThinking })
        }
        if (trimmedText.length > 0) {
          blocks.push({ type: 'text', text: trimmedText })
        }
        for (const tu of pendingContentBlocks) {
          blocks.push(tu)
        }
        const finalContent =
          blocks.length > 0
            ? (blocks as unknown as Parameters<
                typeof createAssistantMessage
              >[0]['content'])
            : trimmedText
        const finalMsg = createAssistantMessage({ content: finalContent }) as {
          uuid: string
          message: { id: string }
        }
        finalMsg.uuid = messageUuid
        finalMsg.message.id = innerMessageId
        yield finalMsg
        yield {
          type: 'stream_event' as const,
          event: { type: 'content_block_stop' as const, index: 0 },
        }
        yield {
          type: 'stream_event' as const,
          event: {
            type: 'message_delta' as const,
            delta: { stop_reason: 'end_turn', stop_sequence: null },
            usage: { output_tokens: 0 },
          },
        }
        yield {
          type: 'stream_event' as const,
          event: { type: 'message_stop' as const },
        }
        return
      }
    } else if (fa.kind === 'tool_call') {
      // Epic #2077 T012 (Step 5) — CC stream-event projection. Mirrors
      // ``_cc_reference/claude.ts:1995-2052`` (content_block_start tool_use
      // case). ``handleMessageFromStream`` (utils/messages.ts:3024-3037)
      // routes the start event into ``streamingToolUses`` so the existing
      // ``AssistantToolUseMessage`` component (367 LOC, REPL-mounted)
      // renders the invocation as a transcript-native record (FR-006).
      // ``pendingContentBlocks.push`` accumulates the same block so the
      // terminal AssistantMessage's ``content`` array carries it (CC's
      // ``messages.ts:normalizeContentFromAPI`` shape).
      const toolUseBlock = {
        type: 'tool_use' as const,
        id: fa.call_id ?? '',
        name: fa.name ?? '(unknown tool)',
        input: fa.arguments ?? {},
      }
      // Register the call_id so tool_result frames can verify pairing (FR-009).
      if (fa.call_id) {
        seenToolUseIds.add(fa.call_id)
      }

      pendingContentBlocks.push(toolUseBlock)
      blockIndex += 1

      yield {
        type: 'stream_event' as const,
        event: {
          type: 'content_block_start' as const,
          index: blockIndex,
          content_block: toolUseBlock,
        },
      }
      yield {
        type: 'stream_event' as const,
        event: { type: 'content_block_stop' as const, index: blockIndex },
      }
    } else if (fa.kind === 'tool_result') {
      // Epic #2077 T012 (Step 6) — user-role tool_result content block.
      // Mirrors ``_cc_reference/messages.ts:ensureToolResultPairing`` (line
      // 1150-1250). The result enters the transcript as a user message so
      // the next agentic-loop turn picks it up as LLM context (FR-010).
      // Pairing to the originating tool_use is by ``tool_use_id`` (FR-009).
      // ``is_error: true`` flag is set when the envelope's discriminator is
      // ``'error'`` so downstream rendering can surface it distinctly.
      //
      // Epic #2077 T016 — FR-009 orphan detection. A tool_result whose
      // call_id was NOT registered by any prior tool_call in this turn is an
      // orphan. The tool_result user-message is still emitted (transcript
      // preservation), but a visible error SystemMessage precedes it so the
      // citizen sees the pairing failure immediately.
      const resultCallId = fa.call_id ?? ''
      if (resultCallId && !seenToolUseIds.has(resultCallId)) {
        yield createSystemMessage(
          `tool_result_orphan: Tool result references unknown tool_use_id "${resultCallId}"`,
          'error',
          resultCallId,
        )
      }

      // KOSMOS hotfix #2519 (CC-original migration, 2026-04-30) — forward
      // the tool_result frame to the dispatch registry so the matching
      // dispatchPrimitive register-and-await Promise resolves. Without this
      // the SDK's Tool.call() (LookupPrimitive.call → dispatchPrimitive)
      // would block until the 30-second timeout, K-EXAONE would never see
      // a result, and the citizen-facing tool_result row would render as
      // an error envelope ("dispatch_error: …timeout…") instead of the
      // real LookupSearchResult / KMA forecast / receipt body.
      if (resultCallId) {
        // Lazy-require to avoid a top-level import cycle through Tool.ts.
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const { getOrCreatePendingCallRegistry } = await import(
          '../ipc/pendingCallSingleton.js'
        )
        getOrCreatePendingCallRegistry().resolve(
          resultCallId,
          fa as unknown as Parameters<
            ReturnType<typeof getOrCreatePendingCallRegistry>['resolve']
          >[1],
        )
      }

      const env = fa.envelope ?? {}
      const toolUseResult = buildToolUseResultFromEnvelope(env)
      const isError = isErrorEnvelope(env)
      yield createUserMessage({
        content: [
          {
            type: 'tool_result' as const,
            tool_use_id: resultCallId,
            content: stripUiOnlyToolResultFields(toolUseResult),
            ...(isError ? { is_error: true as const } : {}),
          },
        ] as Parameters<typeof createUserMessage>[0]['content'],
        toolUseResult,
        sourceToolAssistantUUID: messageUuid as UUID,
      })
    } else if (fa.kind === 'permission_request') {
      // Epic #2077 T020 (Step 7) — CC permission gauntlet wire. Routes the
      // backend permission_request frame through sessionStore's pending
      // permission slot (T018 / contracts/pending-permission-slot.md). The
      // store dispatches the request to the mounted PermissionGauntletModal
      // (T021), awaits the citizen's Y/N decision (or 5-min timeout), and
      // resolves the Promise here. We then send the permission_response
      // frame upstream with the resolved decision (granted / denied /
      // timeout). 'timeout' is treated by the backend as 'denied' for
      // fail-closed (Constitution §II + FR-017).
      const fp = f as {
        request_id?: string
        primitive_kind?: 'lookup' | 'resolve_location' | 'verify' | 'submit' | 'subscribe'
        description_ko?: string
        description_en?: string
        risk_level?: 'low' | 'medium' | 'high'
        receipt_id?: string
        worker_id?: string
        session_id?: string
        correlation_id?: string
      }
      // Lazy import to avoid pulling the React store into modules that don't
      // need it; deps.ts is the only IPC↔store seam for this surface.
      const { setPendingPermission } = await import('../store/pendingPermissionSlot.js')
      const { dispatchSessionAction } = await import('../store/session-store.js')
      // Epic FU-4 — bridge the frame into toolUseConfirmQueue so the CC
      // 4-arm permissionComponentForTool switch auto-mounts the correct
      // adapter (VerifyPermissionRequestAdapter etc.).
      // This must run BEFORE setPendingPermission so the modal is visible
      // when the user arrives at the permission prompt.
      const { pushIpcPermissionRequest } = await import('../utils/permissions/ipcPermissionBridge.js')
      pushIpcPermissionRequest({
        request_id: fp.request_id ?? '',
        primitive_kind: fp.primitive_kind ?? 'submit',
        description_ko: fp.description_ko ?? '',
        description_en: fp.description_en ?? '',
        risk_level: fp.risk_level ?? 'medium',
        worker_id: fp.worker_id ?? '',
        session_id: fp.session_id ?? sessionId,
        correlation_id: fp.correlation_id ?? correlationId,
        // carry-through base frame fields required by PermissionRequestFrame
        ts: new Date().toISOString(),
        version: '1.0',
        role: 'backend',
        frame_seq: 0,
        kind: 'permission_request',
      } as import('../ipc/frames.generated.js').PermissionRequestFrame)
      // Mirror the request into the reducer's pending_permission field so
      // any remaining subscribers of `s.pending_permission` still receive
      // the notification. The pendingPermissionSlot owns the Promise + FIFO
      // queue lifecycle; the reducer field is a render-only mirror.
      const reducerRequest = {
        request_id: fp.request_id ?? '',
        correlation_id: correlationId,
        worker_id: '',
        primitive_kind: fp.primitive_kind ?? 'submit',
        description_ko: fp.description_ko ?? '',
        description_en: fp.description_en ?? '',
        risk_level: fp.risk_level ?? ('medium' as const),
      }
      dispatchSessionAction({ type: 'PERMISSION_REQUEST', request: reducerRequest })
      try {
        var decision = await setPendingPermission({
          request_id: fp.request_id ?? '',
          primitive_kind: fp.primitive_kind ?? 'submit',
          description_ko: fp.description_ko ?? '',
          description_en: fp.description_en ?? '',
          risk_level: fp.risk_level ?? 'medium',
          receipt_id: fp.receipt_id ?? '',
          enqueued_at: performance.now(),
        })
      } finally {
        // Always clear the reducer mirror so a stale `pending_permission`
        // never blocks the next turn even on grant/deny/timeout/throw.
        dispatchSessionAction({ type: 'PERMISSION_RESPONSE' })
      }
      // Backend's permission_response schema accepts only granted/denied;
      // collapse 'timeout' into 'denied' at the wire boundary (the timeout
      // distinction stays in the audit ledger via Spec 035 receipt).
      const wireDecision = decision === 'timeout' ? 'denied' : decision
      const respFrame = {
        session_id: sessionId,
        correlation_id: correlationId,
        ts: new Date().toISOString(),
        role: 'tui' as const,
        kind: 'permission_response' as const,
        request_id: fp.request_id ?? '',
        decision: wireDecision,
      }
      bridge.send(respFrame as unknown as IPCFrame)
    } else if (fa.kind === 'error') {
      const reason = fa.message ?? 'KOSMOS backend error'
      // CC mirror: yield the (error) AssistantMessage first so
      // handleMessageFromStream clears the streamingText preview, then
      // close the open block + message so the spinner reaches its terminal
      // state.
      yield createAssistantMessage({ content: `[KOSMOS backend error] ${reason}` })
      if (messageStartEmitted) {
        yield {
          type: 'stream_event' as const,
          event: { type: 'content_block_stop' as const, index: 0 },
        }
        yield {
          type: 'stream_event' as const,
          event: { type: 'message_stop' as const },
        }
      }
      return
    }
  }
  // Stream ended without a `done:true` chunk — yield the accumulated text
  // (so the turn isn't silently dropped), then close any open block in CC's
  // AssistantMessage-first order. Epic #2077 T012 — same content-array
  // promotion as the done=true path so any tool_use blocks captured before
  // the abrupt close still appear in the persisted transcript.
  const trimmedTailText = accumulated.trimStart()
  const finalTailContent =
    pendingContentBlocks.length > 0
      ? trimmedTailText.length > 0
        ? ([{ type: 'text' as const, text: trimmedTailText }, ...pendingContentBlocks] as Parameters<
            typeof createAssistantMessage
          >[0]['content'])
        : (pendingContentBlocks as unknown as Parameters<typeof createAssistantMessage>[0]['content'])
      : trimmedTailText
  const finalMsg = createAssistantMessage({ content: finalTailContent }) as {
    uuid: string
    message: { id: string }
  }
  finalMsg.uuid = messageUuid
  finalMsg.message.id = innerMessageId
  yield finalMsg
  if (messageStartEmitted) {
    yield {
      type: 'stream_event' as const,
      event: { type: 'content_block_stop' as const, index: 0 },
    }
    yield {
      type: 'stream_event' as const,
      event: { type: 'message_stop' as const },
    }
  }
}

function summarizeArgs(args: unknown): string {
  if (!args || typeof args !== 'object') return ''
  try {
    const json = JSON.stringify(args)
    return json.length > 80 ? ` ${json.slice(0, 77)}…` : ` ${json}`
  } catch {
    return ''
  }
}

function summarizeResult(env: { [k: string]: unknown }): string {
  const summary = (env.summary ?? env.message ?? env.text) as unknown
  if (typeof summary === 'string' && summary.length > 0) {
    return summary.length > 80 ? ` ${summary.slice(0, 77)}…` : ` ${summary}`
  }
  return ''
}

function extractText(v: unknown): string {
  if (typeof v === 'string') return v
  if (Array.isArray(v)) {
    return v
      .map((b) => {
        if (typeof b === 'string') return b
        const ba = b as { text?: string; content?: string }
        return ba?.text ?? ba?.content ?? ''
      })
      .filter(Boolean)
      .join('\n')
  }
  return ''
}

// -- deps

// I/O dependencies for query(). Passing a `deps` override into QueryParams
// lets tests inject fakes directly instead of spyOn-per-module — the most
// common mocks (callModel, autocompact) are each spied in 6-8 test files
// today with module-import-and-spy boilerplate.
//
// Using `typeof fn` keeps signatures in sync with the real implementations
// automatically. This file imports the real functions for both typing and
// the production factory — tests that import this file for typing are
// already importing query.ts (which imports everything), so there's no
// new module-graph cost.
//
// Scope is intentionally narrow (4 deps) to prove the pattern. Followup
// PRs can add runTools, handleStopHooks, logEvent, queue ops, etc.
export type QueryDeps = {
  // -- model
  callModel: typeof queryModelWithStreaming

  // -- compaction
  microcompact: typeof microcompactMessages
  autocompact: typeof autoCompactIfNeeded

  // -- platform
  uuid: () => string
}

export function productionDeps(): QueryDeps {
  return {
    callModel: queryModelWithStreaming,
    microcompact: microcompactMessages,
    autocompact: autoCompactIfNeeded,
    uuid: randomUUID,
  }
}

// ---------------------------------------------------------------------------
// Pure helpers (exported for unit tests — no bridge dependency)
// ---------------------------------------------------------------------------

// FR-009 pairing-invariant helpers live in a leaf module so unit tests can
// import them without dragging the deps.ts → autoCompact.ts → 'bun:bundle'
// chain through Bun's resolver.
export { isOrphanToolResult, orphanErrorMessage } from './orphanHelpers.js'
