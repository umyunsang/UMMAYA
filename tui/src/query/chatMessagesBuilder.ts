// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Lead-Diag-4 (2026-05-04) role='tool' wire conversion.
//
// Builds the OpenAI Chat Completions-compliant ``ChatRequestFrame.messages``
// payload from CC's transcript ``Message[]``.
//
// CC (Claude Code) uses the Anthropic Messages API native shape — tool_result
// blocks live INSIDE ``role='user'`` messages and tool_use blocks live INSIDE
// ``role='assistant'`` messages. KOSMOS forwards to K-EXAONE on FriendliAI,
// which uses the OpenAI Chat Completions spec — tool_result is its own
// ``role='tool'`` message keyed by ``tool_call_id``, and assistant tool
// invocations live in the ``tool_calls[]`` array on the assistant message.
//
// This module is the conversion seam. It walks the CC transcript and emits
// wire-shape ``ChatMessage[]`` that:
//
//   1. Preserves user prose turns as ``{role:'user', content}``.
//   2. Preserves assistant prose turns as ``{role:'assistant', content}``.
//   3. Promotes assistant tool_use blocks to OpenAI ``tool_calls[]`` entries
//      on the assistant message (with ``id`` matching the tool_use_id), so the
//      OpenAI multi-turn pairing invariant is satisfied.
//   4. Promotes user-wrapped tool_result blocks to standalone OpenAI
//      ``role='tool'`` messages with ``tool_call_id`` + ``name`` set.
//
// Without (3) and (4), FriendliAI would receive the previous-turn JSON
// envelope flattened to a ``role='user'`` text message — the model loses the
// structured invocation context, tail-attention ranks the 12 KB result-as-text
// over the actual user prompt, and multi-turn flows reason over stale state
// (Lead-Diag-4 evidence captured 2026-05-04 in
// ``specs/spec-multi-turn-contamination/diagnostic-runs/scn-A-*``).
//
// CC reference (the source shape we read):
//   .references/claude-code-sourcemap/restored-src/src/utils/messages.ts:600-630
//   (createToolResultStopMessage / createUserMessage with content blocks)
//
// OpenAI spec reference (the target shape we emit):
//   - Multi-turn tool_calls / role='tool' pairing — verified via
//     openai-cookbook ``Orchestrating_agents.ipynb`` (2026-05-04).
//
// Backward compat: legacy senders that emit ``createUserMessage`` with raw
// string content still flow through unchanged. The converter only acts on the
// structured-blocks branch.

import type {
  ChatMessage,
  ChatMessageToolCall,
} from '../ipc/frames.generated.js'

// ---------------------------------------------------------------------------
// Loose input types — mirror the CC ``Message`` shape WITHOUT importing
// utils/messages.ts (which transitively pulls Ink + the React store and
// would defeat the leaf-module isolation pattern from orphanHelpers.ts).
// ---------------------------------------------------------------------------

interface InputToolUseBlock {
  type: 'tool_use'
  id: string
  name: string
  input: unknown
}

interface InputToolResultBlock {
  type: 'tool_result'
  tool_use_id: string
  content: unknown
  is_error?: boolean
}

interface InputTextBlock {
  type: 'text'
  text: string
}

interface InputThinkingBlock {
  type: 'thinking'
  thinking: string
}

type InputContentBlock =
  | InputToolUseBlock
  | InputToolResultBlock
  | InputTextBlock
  | InputThinkingBlock
  | { type: string; [k: string]: unknown }

interface InputMessage {
  type?: string
  message?: {
    role?: string
    content?: string | InputContentBlock[]
  }
}

// ---------------------------------------------------------------------------
// Pure helpers (extracted so unit tests target the contract directly)
// ---------------------------------------------------------------------------

/**
 * Extracts plain text from a CC-shape content value (string OR block array).
 * Mirrors the legacy ``extractText`` helper in deps.ts but lives here so the
 * builder is self-contained.
 *
 * - String value → returned verbatim.
 * - Array value → concatenates ``text`` blocks (and tolerates the legacy
 *   ``content``-keyed shape some intermediate builders use).
 * - Anything else → empty string.
 */
export function extractTextFromContent(
  content: unknown,
): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map((b) => {
      if (typeof b === 'string') return b
      const ba = b as { type?: string; text?: string; content?: unknown }
      if (ba?.type === 'text' && typeof ba.text === 'string') return ba.text
      // Tolerate the legacy ``{type:'text', content:'...'}`` shape that
      // some test fixtures emit.
      if (typeof ba?.content === 'string') return ba.content
      return ''
    })
    .filter(Boolean)
    .join('\n')
}

/**
 * Serialises a tool_result.content value into the string body that
 * FriendliAI's role='tool' message accepts. CC's Anthropic-shape
 * tool_result.content can be a string OR an array of typed blocks; OpenAI
 * spec requires a string. We collapse the array case via JSON.
 */
export function serializeToolResultContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (content == null) return ''
  try {
    return JSON.stringify(content)
  } catch {
    return String(content)
  }
}

/**
 * Looks up the ``name`` of a tool by its ``tool_use_id`` by walking the
 * already-emitted assistant messages BACKWARDS. Returns null if not found
 * (the caller falls back to the tool_use_id as a synthetic name so the
 * wire validator's ``role='tool' requires non-empty name`` check still
 * passes).
 *
 * CC's invocation metadata lives on the assistant ``tool_use`` block;
 * the ``user.tool_result`` block carries only ``tool_use_id``. The
 * converter must therefore stitch the two halves back together at
 * conversion time.
 */
export function findToolNameForResult(
  toolUseId: string,
  emittedSoFar: ReadonlyArray<ChatMessage>,
): string | null {
  if (!toolUseId) return null
  for (let i = emittedSoFar.length - 1; i >= 0; i--) {
    const m = emittedSoFar[i]
    if (m?.role !== 'assistant') continue
    const calls = m.tool_calls
    if (!calls) continue
    for (const c of calls) {
      if (c.id === toolUseId) return c.function.name
    }
  }
  return null
}

/**
 * Serialises tool_use ``input`` into the OpenAI-spec arguments string.
 * Always returns a JSON-encoded string (never a raw object), since OpenAI's
 * ``tool_calls[i].function.arguments`` is a STRING by spec.
 */
export function serializeToolUseInput(input: unknown): string {
  if (typeof input === 'string') return input
  if (input == null) return '{}'
  try {
    return JSON.stringify(input)
  } catch {
    return '{}'
  }
}

// ---------------------------------------------------------------------------
// Builder — the public entry point used by deps.ts
// ---------------------------------------------------------------------------

/**
 * Walks a CC-shape transcript ``Message[]`` and emits an OpenAI Chat
 * Completions-compliant ``ChatMessage[]`` payload for ``ChatRequestFrame.messages``.
 *
 * Conversion rules (Lead-Diag-4):
 *
 *   • user message with string content
 *       → {role:'user', content}
 *   • user message with content blocks containing tool_result(s)
 *       → one {role:'tool', name, tool_call_id, content} per result block,
 *         in arrival order (preserves OpenAI parallel-tool-call semantics).
 *         Plain text blocks in the same user message become a separate
 *         {role:'user', content} appended AFTER the tool messages.
 *   • assistant message with string content
 *       → {role:'assistant', content}
 *   • assistant message with content blocks containing tool_use(s)
 *       → {role:'assistant', content:<text|"">, tool_calls:[...]}
 *         The text block (if any) becomes ``content``; tool_use blocks
 *         become ``tool_calls`` entries with id/name preserved.
 *   • Any other type → skipped (system/progress/attachment are TUI-only).
 *
 * Returns at least one ``{role:'user', content:''}`` message so the wire
 * validator's ``min_length=1`` invariant on ``ChatRequestFrame.messages``
 * holds for empty inputs (matches the legacy fallback in deps.ts:131-133).
 *
 * Backward compatible: legacy callers that constructed ``createUserMessage``
 * with a raw string still produce a single ``{role:'user', content}`` message
 * exactly as before.
 */
export function buildChatMessagesFromTranscript(
  messages: readonly unknown[],
): ChatMessage[] {
  const out: ChatMessage[] = []

  for (const m of messages) {
    const ma = m as InputMessage
    if (!ma) continue
    if (ma.type !== 'user' && ma.type !== 'assistant') continue

    const role: 'user' | 'assistant' = ma.type === 'user' ? 'user' : 'assistant'
    const content = ma.message?.content

    // String-content fast path (covers ~all assistant prose and most user
    // turns). Equivalent to the legacy chatMessages.push branch.
    if (typeof content === 'string') {
      if (content.length > 0) {
        out.push({ role, content })
      }
      continue
    }

    // Array-content branch — must inspect block types to decide whether to
    // emit a flat user/assistant message OR promote tool_result/tool_use
    // blocks to wire-native role='tool'/tool_calls form.
    if (!Array.isArray(content)) continue

    if (role === 'user') {
      const toolMessages: ChatMessage[] = []
      const textParts: string[] = []
      for (const block of content) {
        if (!block || typeof block !== 'object') continue
        const typed = block as InputContentBlock
        if (typed.type === 'tool_result') {
          const tr = typed as InputToolResultBlock
          const callId = tr.tool_use_id ?? ''
          if (!callId) continue
          // Resolve tool name by walking already-emitted assistant messages.
          // Fall back to the call_id as the name when no prior tool_use is
          // visible — keeps the wire validator's ``name'' invariant happy
          // and surfaces the gap in logs (the backend logs ``name'' on the
          // CHAT_REQUEST_DUMP path).
          const resolvedName = findToolNameForResult(callId, out) ?? callId
          toolMessages.push({
            role: 'tool',
            name: resolvedName,
            tool_call_id: callId,
            content: serializeToolResultContent(tr.content),
          })
        } else if (typed.type === 'text') {
          const tb = typed as InputTextBlock
          if (typeof tb.text === 'string' && tb.text.length > 0) {
            textParts.push(tb.text)
          }
        }
      }
      // Emit OpenAI-spec order: tool_result messages MUST appear AFTER the
      // assistant tool_calls turn that requested them and BEFORE the next
      // user prose turn. We preserve that by emitting tool messages first,
      // then any free-text user content.
      for (const tm of toolMessages) out.push(tm)
      if (textParts.length > 0) {
        out.push({ role: 'user', content: textParts.join('\n') })
      }
      continue
    }

    // role === 'assistant'
    const toolCalls: ChatMessageToolCall[] = []
    const textParts: string[] = []
    for (const block of content) {
      if (!block || typeof block !== 'object') continue
      const typed = block as InputContentBlock
      if (typed.type === 'tool_use') {
        const tu = typed as InputToolUseBlock
        if (!tu.id || !tu.name) continue
        toolCalls.push({
          id: tu.id,
          type: 'function',
          function: {
            name: tu.name,
            arguments: serializeToolUseInput(tu.input),
          },
        })
      } else if (typed.type === 'text') {
        const tb = typed as InputTextBlock
        if (typeof tb.text === 'string' && tb.text.length > 0) {
          textParts.push(tb.text)
        }
      }
      // ``thinking`` blocks are CoT — never forwarded to the next turn
      // (CC also drops them at the API boundary; FriendliAI's K-EXAONE
      // re-derives reasoning per turn from the messages array alone).
    }

    const assistantText = textParts.join('\n')
    if (toolCalls.length > 0) {
      // OpenAI spec accepts empty content when tool_calls is set.
      out.push({
        role: 'assistant',
        content: assistantText,
        tool_calls: toolCalls,
      })
    } else if (assistantText.length > 0) {
      out.push({ role: 'assistant', content: assistantText })
    }
  }

  // ChatRequestFrame.messages requires min_length=1 (Spec 1978). Match the
  // legacy fallback so an empty transcript still produces a valid frame.
  if (out.length === 0) {
    out.push({ role: 'user', content: '' })
  }
  return out
}
