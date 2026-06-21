import type { AssistantMessage, Message, StreamEvent } from '../types/message.js'
import {
  appendRouteDiagnostic,
  hashRouteDiagnosticText,
} from '../tools/AdapterTool/routeDiagnostics.js'
import { latestTextUserMessageIndex, messageText } from './messageGuards.js'

const GUARDED_ASSISTANT_PREVIEW_MIN_CHARS = 160
const GUARDED_ASSISTANT_PREVIEW_CHUNK_CHARS = 24
const GUARDED_ASSISTANT_PREVIEW_DELAY_MS = 32

type GuardedAssistantPreviewEvent = {
  readonly type: 'stream_event'
  readonly event: StreamEvent
  readonly ttftMs?: number
}

function guardedAssistantPreviewDelayMs(): number {
  const raw = process.env.UMMAYA_TUI_SYNTHETIC_STREAM_DELAY_MS
  if (raw === undefined) return GUARDED_ASSISTANT_PREVIEW_DELAY_MS
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) && parsed >= 0
    ? parsed
    : GUARDED_ASSISTANT_PREVIEW_DELAY_MS
}

function waitForPreviewFrameBoundary(delayMs: number): Promise<void> {
  if (delayMs <= 0) return Promise.resolve()
  return new Promise(resolve => setTimeout(resolve, delayMs))
}

function splitGuardedAssistantPreviewText(text: string): readonly string[] {
  const chunks: string[] = []
  let start = 0
  while (start < text.length) {
    const hardEnd = Math.min(text.length, start + GUARDED_ASSISTANT_PREVIEW_CHUNK_CHARS)
    let end = hardEnd
    const newline = text.lastIndexOf('\n', hardEnd)
    if (newline >= start + 12) {
      end = newline + 1
    } else {
      const punctuation = Math.max(
        text.lastIndexOf('. ', hardEnd),
        text.lastIndexOf(', ', hardEnd),
        text.lastIndexOf('。', hardEnd),
        text.lastIndexOf('다.', hardEnd),
        text.lastIndexOf('요.', hardEnd),
        text.lastIndexOf(' ', hardEnd),
      )
      if (punctuation >= start + 16) end = punctuation + 1
    }
    if (end <= start) end = hardEnd
    chunks.push(text.slice(start, end))
    start = end
  }
  return chunks
}

function guardedAssistantStreamEvent(
  event: StreamEvent,
  ttftMs?: number,
): GuardedAssistantPreviewEvent {
  return ttftMs === undefined
    ? { type: 'stream_event', event }
    : { type: 'stream_event', event, ttftMs }
}

function latestPreviewQueryHash(messages: readonly Message[]): string {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  const latestUserMessage = latestUserIndex >= 0 ? messages[latestUserIndex] : undefined
  return hashRouteDiagnosticText(
    latestUserMessage ? messageText(latestUserMessage) : '',
  )
}

export async function* streamGuardedAssistantMessage(params: {
  readonly message: AssistantMessage
  readonly messages: readonly Message[]
  readonly querySource: string
  readonly turnCount: number
  readonly enabled: boolean
}): AsyncGenerator<GuardedAssistantPreviewEvent | AssistantMessage> {
  const text = messageText(params.message)
  const chunks = splitGuardedAssistantPreviewText(text)
  if (
    !params.enabled ||
    text.length < GUARDED_ASSISTANT_PREVIEW_MIN_CHARS ||
    chunks.length < 2
  ) {
    yield params.message
    return
  }

  const delayMs = guardedAssistantPreviewDelayMs()
  appendRouteDiagnostic('query_assistant_streamed_guard_preview', {
    query_hash: latestPreviewQueryHash(params.messages),
    query_source: params.querySource,
    turn_count: params.turnCount,
    assistant_text_chars: text.length,
    preview_chunk_count: chunks.length,
    preview_delay_ms: delayMs,
  })
  yield guardedAssistantStreamEvent({
    type: 'message_start',
    message: {
      ...params.message.message,
      content: [],
    },
  }, 0)
  yield guardedAssistantStreamEvent({
    type: 'content_block_start',
    index: 0,
    content_block: { type: 'text', text: '' },
  })
  for (const [index, chunk] of chunks.entries()) {
    yield guardedAssistantStreamEvent({
      type: 'content_block_delta',
      index: 0,
      delta: { type: 'text_delta', text: chunk },
    })
    if (index < chunks.length - 1) {
      await waitForPreviewFrameBoundary(delayMs)
    }
  }
  yield guardedAssistantStreamEvent({
    type: 'content_block_stop',
    index: 0,
  })
  yield guardedAssistantStreamEvent({
    type: 'message_delta',
    delta: { stop_reason: 'end_turn', stop_sequence: null },
    usage: { output_tokens: 0 },
  })
  yield guardedAssistantStreamEvent({ type: 'message_stop' })
  yield params.message
}
