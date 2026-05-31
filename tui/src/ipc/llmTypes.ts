// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1633 P2 · Anthropic→FriendliAI type shim.
//
// Structural replacements for the Anthropic SDK types that QueryEngine.ts
// and query.ts import. These types are in-process only; they never reach the
// wire. The Spec 032 IPC envelope (frames.generated.ts) carries actual frames
// to / from the Python backend.
//
// Responsibility: keep the TS agentic loop compiling after the Anthropic SDK
// is removed, without rewriting the loop's control flow (rewrite-boundary
// rule, Constitution Principle I).

// ---------------------------------------------------------------------------
// Message roles and content blocks
// ---------------------------------------------------------------------------

export type UmmayaRole = 'user' | 'assistant'

export type UmmayaTextBlockParam = {
  type: 'text'
  text: string
}

export type UmmayaToolUseBlockParam = {
  type: 'tool_use'
  id: string
  name: string
  input: Record<string, unknown>
}

export type UmmayaToolResultBlockParam = {
  type: 'tool_result'
  tool_use_id: string
  content: string | UmmayaContentBlockParam[]
  is_error?: boolean
}

export type UmmayaContentBlockParam =
  | UmmayaTextBlockParam
  | UmmayaToolUseBlockParam
  | UmmayaToolResultBlockParam

// ---------------------------------------------------------------------------
// Messages + tool definitions
// ---------------------------------------------------------------------------

export type UmmayaMessageParam = {
  role: UmmayaRole
  content: string | UmmayaContentBlockParam[]
}

export type UmmayaToolDefinition = {
  name: string
  description?: string
  input_schema: { type: 'object'; [k: string]: unknown }
}

// ---------------------------------------------------------------------------
// Stream parameters + usage
// ---------------------------------------------------------------------------

export type UmmayaMessageStreamParams = {
  model: string
  system?: string
  messages: UmmayaMessageParam[]
  tools?: UmmayaToolDefinition[]
  max_tokens: number
  temperature?: number
  reasoning_mode?: import('../utils/kExaoneReasoning.js').ReasoningMode
  metadata?: Record<string, string>
}

export type UmmayaUsage = {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens?: number
}

// ---------------------------------------------------------------------------
// Streaming events (structural compatibility with Anthropic's SDK event shape)
// ---------------------------------------------------------------------------

export type UmmayaStopReason = 'end_turn' | 'max_tokens' | 'tool_use' | 'stop_sequence'

export type UmmayaMessageStart = {
  type: 'message_start'
  message: {
    id: string
    role: 'assistant'
    model: string
  }
}

export type UmmayaContentBlockStart = {
  type: 'content_block_start'
  index: number
  content_block: UmmayaContentBlockParam
}

export type UmmayaTextDelta = {
  type: 'text_delta'
  text: string
}

export type UmmayaInputJsonDelta = {
  type: 'input_json_delta'
  partial_json: string
}

/**
 * UMMAYA / Anthropic-compat thinking delta. Carries a chunk of the model's
 * chain-of-thought trace. The backend forwards K-EXAONE's
 * ``delta.reasoning_content`` (FriendliAI / vLLM separated reasoning channel)
 * via ``AssistantChunkFrame.thinking``, and llmClient.ts converts those frames
 * into one or more ``content_block_delta { delta: UmmayaThinkingDelta }``
 * events on a dedicated thinking block index. The TUI's ``Message.tsx``
 * picks up ``type: 'thinking'`` content blocks and routes them to
 * ``AssistantThinkingMessage`` (``∴ Thinking`` in dim italic).
 */
export type UmmayaThinkingDelta = {
  type: 'thinking_delta'
  thinking: string
}

export type UmmayaProgressDelta = {
  type: 'progress_event'
  phase: 'analysis' | 'tool_selection' | 'tool_call' | 'tool_result' | 'answer_synthesis'
  message_ko: string
  message_en: string
  safe_to_persist: boolean
  tool_id?: string | null
  call_id?: string | null
}

export type UmmayaContentBlockDelta = {
  type: 'content_block_delta'
  index: number
  delta:
    | UmmayaTextDelta
    | UmmayaInputJsonDelta
    | UmmayaThinkingDelta
    | UmmayaProgressDelta
}

export type UmmayaContentBlockStop = {
  type: 'content_block_stop'
  index: number
}

export type UmmayaMessageDelta = {
  type: 'message_delta'
  delta: {
    stop_reason?: UmmayaStopReason
  }
  usage?: UmmayaUsage
}

export type UmmayaMessageStop = {
  type: 'message_stop'
}

export type UmmayaRawMessageStreamEvent =
  | UmmayaMessageStart
  | UmmayaContentBlockStart
  | UmmayaContentBlockDelta
  | UmmayaContentBlockStop
  | UmmayaMessageDelta
  | UmmayaMessageStop

// ---------------------------------------------------------------------------
// Finalized message returned by LLMClient.complete() + LLMClient.stream() return
// ---------------------------------------------------------------------------

export type UmmayaMessageFinal = {
  id: string
  role: 'assistant'
  model: string
  content: UmmayaContentBlockParam[]
  stop_reason: UmmayaStopReason
  usage: UmmayaUsage
}
