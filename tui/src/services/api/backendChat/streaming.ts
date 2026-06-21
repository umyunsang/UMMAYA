import { randomUUID } from 'crypto'
import { APIUserAbortError } from 'src/sdk-compat.js'
import {
  getOrCreateUmmayaBridge,
  getUmmayaBridgeSessionId,
} from '../../../ipc/bridgeSingleton.js'
import type {
  ChatRequestFrame,
  IPCFrame,
} from '../../../ipc/frames.generated.js'
import { buildChatMessagesFromTranscript } from '../../../query/chatMessagesBuilder.js'
import { getToolDefinitionsForFrame } from '../../../query/toolSerialization.js'
import { assertFriendliApiKeyForUse } from '../../../utils/auth.js'
import { createAssistantMessage } from '../../../utils/assistantMessageFactories.js'
import {
  extractTextualToolCallProposals,
  parseTrailingRawJsonToolCallProposal,
} from '../../../utils/rawJsonToolCall.js'
import {
  firstRawJsonToolCallBufferStartOffset,
  firstTextualToolCallBufferStartOffset,
} from '../../../utils/toolCallStreamBuffer.js'
import {
  createContentBlockStopEvent,
  createMessageDeltaEvent,
  createMessageStartStreamEvent,
  createMessageStopEvent,
  createTextBlockStartEvent,
  createTextDeltaEvent,
  createThinkingBlockStartEvent,
  createThinkingDeltaEvent,
  createToolUseBlockStartEvent,
} from './events.js'
import { createFinalAssistantMessage } from './finalMessage.js'
import { toNonEmptyMessages } from './frame.js'
import {
  createBackendChatState,
  hasAssistantPayload,
  type BackendChatParams,
  type BackendChatState,
} from './types.js'

const LLM_STREAM_ERROR_CODE = 'llm_stream_error'
const STREAM_TIMEOUT_PATTERN = /\b(?:timeout|timed out|idle)\b/iu
const LLM_STREAM_TIMEOUT_HANDOFF =
  'K-EXAONE 응답이 지연되어 이번 요청을 이어갈 수 없습니다. 잠시 후 다시 시도해 주세요.'
const DEFAULT_FRAME_IDLE_TIMEOUT_MS = 90_000
const TEXTUAL_TOOL_CALL_OPEN = '<tool_call>'

export async function* queryModelWithStreaming(
  params: BackendChatParams,
): AsyncGenerator<unknown> {
  const { messages, signal } = params
  assertFriendliApiKeyForUse()

  const correlationId = randomUUID()
  const messageUuid = randomUUID()
  const innerMessageId = randomUUID()
  const turnStartedAt = performance.now()
  const bridge = getOrCreateUmmayaBridge()
  const requestFrame: ChatRequestFrame = {
    session_id: getUmmayaBridgeSessionId(),
    correlation_id: correlationId,
    ts: new Date().toISOString(),
    role: 'tui',
    kind: 'chat_request',
    messages: toNonEmptyMessages(buildChatMessagesFromTranscript(messages)),
    tools: await getToolDefinitionsForFrame(),
  }

  yield { type: 'stream_request_start' as const }

  const sent = bridge.send(requestFrame)
  if (!sent) {
    throw new Error('UMMAYA bridge send failed (backend exited)')
  }

  const persistThinking = process.env.UMMAYA_PERSIST_THINKING === '1'
  const state = createBackendChatState()
  const frameIdleTimeoutMs = getFrameIdleTimeoutMs()
  const frameIterator = bridge.frames()[Symbol.asyncIterator]()
  let correlatedFrameDeadline = performance.now() + frameIdleTimeoutMs

  while (true) {
    if (signal?.aborted) throw new APIUserAbortError()
    const timeoutMs = correlatedFrameDeadline - performance.now()
    const nextFrame = await readNextFrame(frameIterator, timeoutMs)
    if (nextFrame === 'timeout') {
      yield createAssistantMessage({
        content: LLM_STREAM_TIMEOUT_HANDOFF,
      })
      yield* stopOpenBlocks(state)
      if (state.messageStartEmitted) yield createMessageStopEvent()
      return
    }
    if (nextFrame.done) break
    const frame = nextFrame.value
    if (frame.correlation_id !== correlationId) continue
    correlatedFrameDeadline = performance.now() + frameIdleTimeoutMs

    if (frame.kind === 'assistant_chunk') {
      yield* handleAssistantChunk({
        frame,
        state,
        persistThinking,
        turnStartedAt,
        innerMessageId,
        messageUuid,
      })
      if (frame.done) return
    } else if (frame.kind === 'tool_call') {
      yield* handleToolCallFrame({
        frame,
        state,
        persistThinking,
        turnStartedAt,
        innerMessageId,
        messageUuid,
      })
      return
    } else if (frame.kind === 'error') {
      yield createAssistantMessage({
        content: formatBackendErrorMessage(frame),
      })
      yield* stopOpenBlocks(state)
      if (state.messageStartEmitted) yield createMessageStopEvent()
      return
    }
  }

  if (hasAssistantPayload(state, persistThinking) || !state.messageStartEmitted) {
    yield createFinalAssistantMessage({
      accumulated: state.accumulated,
      accumulatedThinking: state.accumulatedThinking,
      messageUuid,
      innerMessageId,
      pendingContentBlocks: state.pendingContentBlocks,
      persistThinking,
    })
  }
  if (state.messageStartEmitted) {
    yield* stopOpenBlocks(state)
    yield createMessageStopEvent()
  }
}

function getFrameIdleTimeoutMs(): number {
  const raw = process.env.UMMAYA_TUI_FRAME_IDLE_TIMEOUT_MS
  if (raw === undefined) return DEFAULT_FRAME_IDLE_TIMEOUT_MS
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_FRAME_IDLE_TIMEOUT_MS
  return parsed
}

async function readNextFrame(
  iterator: AsyncIterator<IPCFrame>,
  timeoutMs: number,
): Promise<IteratorResult<IPCFrame> | 'timeout'> {
  if (timeoutMs <= 0) return 'timeout'
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  const timeout = new Promise<'timeout'>(resolve => {
    timeoutId = setTimeout(() => resolve('timeout'), timeoutMs)
  })
  const result = await Promise.race([iterator.next(), timeout])
  if (timeoutId !== undefined) clearTimeout(timeoutId)
  if (result === 'timeout') {
    void iterator.return?.()
  }
  return result
}

function formatBackendErrorMessage(
  frame: Extract<IPCFrame, { kind?: 'error' }>,
): string {
  if (
    frame.code === LLM_STREAM_ERROR_CODE &&
    STREAM_TIMEOUT_PATTERN.test(frame.message)
  ) {
    return LLM_STREAM_TIMEOUT_HANDOFF
  }
  return `[UMMAYA backend error] ${frame.message}`
}

function* handleAssistantChunk({
  frame,
  state,
  persistThinking,
  turnStartedAt,
  innerMessageId,
  messageUuid,
}: {
  readonly frame: Extract<IPCFrame, { kind?: 'assistant_chunk' }>
  readonly state: BackendChatState
  readonly persistThinking: boolean
  readonly turnStartedAt: number
  readonly innerMessageId: string
  readonly messageUuid: string
}): Generator<unknown> {
  yield* startMessageIfNeeded(state, innerMessageId, turnStartedAt)
  const thinkingText = frame.thinking ?? ''
  if (thinkingText.length > 0) yield* appendThinking(state, thinkingText, persistThinking)

  const deltaText = frame.delta ?? ''
  state.accumulated += deltaText
  if (deltaText.length > 0) yield* appendText(state, deltaText)

  if (!frame.done) return
  const textualToolUse = extractTextualToolCallProposals({
    text: state.accumulated,
  })
  const rawJsonToolUse = textualToolUse === undefined
    ? parseTrailingRawJsonToolCallProposal({
        text: state.accumulated,
      })
    : undefined
  if (
    (textualToolUse !== undefined || rawJsonToolUse !== undefined) &&
    state.pendingContentBlocks.length === 0
  ) {
    const prelude = textualToolUse?.text ?? rawJsonToolUse?.prelude ?? ''
    yield* flushTextPreludeBeforeRawJsonToolUse(state, prelude)
    yield* stopOpenBlocks(state)
    const proposals = textualToolUse?.proposals ??
      (rawJsonToolUse !== undefined ? [rawJsonToolUse.proposal] : [])
    for (let index = 0; index < proposals.length; index += 1) {
      const proposal = proposals[index]
      if (!proposal) continue
      yield* appendRawJsonToolUseBlock({
        state,
        name: proposal.name,
        input: proposal.input,
        id: textualToolUse !== undefined
          ? `call_textual_tool_${index}`
          : 'call_raw_json_tool_0',
      })
    }
    state.accumulated = prelude
    yield createFinalAssistantMessage({
      accumulated: state.accumulated,
      accumulatedThinking: state.accumulatedThinking,
      messageUuid,
      innerMessageId,
      pendingContentBlocks: state.pendingContentBlocks,
      persistThinking,
    })
    yield createMessageDeltaEvent('tool_use')
    yield createMessageStopEvent()
    return
  }
  if (state.shouldBufferTextDeltas) {
    yield* flushBufferedText(state)
  }
  yield* stopOpenBlocks(state)
  if (hasAssistantPayload(state, persistThinking) || !state.messageStartEmitted) {
    yield createFinalAssistantMessage({
      accumulated: state.accumulated,
      accumulatedThinking: state.accumulatedThinking,
      messageUuid,
      innerMessageId,
      pendingContentBlocks: state.pendingContentBlocks,
      persistThinking,
    })
  }
  if (state.messageStartEmitted) {
    yield createMessageDeltaEvent('end_turn')
    yield createMessageStopEvent()
  }
}

function* handleToolCallFrame({
  frame,
  state,
  persistThinking,
  turnStartedAt,
  innerMessageId,
  messageUuid,
}: {
  readonly frame: Extract<IPCFrame, { kind?: 'tool_call' }>
  readonly state: BackendChatState
  readonly persistThinking: boolean
  readonly turnStartedAt: number
  readonly innerMessageId: string
  readonly messageUuid: string
}): Generator<unknown> {
  yield* startMessageIfNeeded(state, innerMessageId, turnStartedAt)
  if (state.shouldBufferTextDeltas) {
    yield* flushBufferedText(state)
  }
  yield* stopOpenBlocks(state)

  const toolUseBlock = {
    type: 'tool_use' as const,
    id: frame.call_id,
    name: frame.name,
    input: frame.arguments,
  }
  state.pendingContentBlocks.push(toolUseBlock)
  const toolBlockIndex = state.nextContentBlockIndex
  state.nextContentBlockIndex += 1

  yield createToolUseBlockStartEvent(toolBlockIndex, toolUseBlock)
  yield createContentBlockStopEvent(toolBlockIndex)
  yield createFinalAssistantMessage({
    accumulated: state.accumulated,
    accumulatedThinking: state.accumulatedThinking,
    messageUuid,
    innerMessageId,
    pendingContentBlocks: state.pendingContentBlocks,
    persistThinking,
  })
  yield createMessageDeltaEvent('tool_use')
  yield createMessageStopEvent()
}

function* startMessageIfNeeded(
  state: BackendChatState,
  innerMessageId: string,
  turnStartedAt: number,
): Generator<unknown> {
  if (state.messageStartEmitted) return
  yield createMessageStartStreamEvent(innerMessageId, performance.now() - turnStartedAt)
  state.messageStartEmitted = true
}

function* appendThinking(
  state: BackendChatState,
  text: string,
  persistThinking: boolean,
): Generator<unknown> {
  if (state.thinkingBlockIndex === null) {
    yield createThinkingBlockStartEvent(state.nextContentBlockIndex)
    state.thinkingBlockIndex = state.nextContentBlockIndex
    state.nextContentBlockIndex += 1
  }
  if (persistThinking) state.accumulatedThinking += text
  yield createThinkingDeltaEvent(state.thinkingBlockIndex, text)
}

function* appendText(state: BackendChatState, text: string): Generator<unknown> {
  const bufferOffset = firstToolCallTextOffset(state.accumulated)
  const startsBuffering = !state.shouldBufferTextDeltas && bufferOffset >= 0
  if (startsBuffering) state.shouldBufferTextDeltas = true
  if (startsBuffering) {
    if (bufferOffset > state.emittedTextLength) {
      yield* appendVisibleTextDelta(
        state,
        state.accumulated.slice(state.emittedTextLength, bufferOffset),
        state.emittedTextLength,
      )
    }
    return
  }
  if (state.shouldBufferTextDeltas && bufferOffset < 0) {
    state.shouldBufferTextDeltas = false
    yield* appendVisibleTextDelta(
      state,
      state.accumulated.slice(state.emittedTextLength),
      state.emittedTextLength,
    )
    return
  }
  if (state.shouldBufferTextDeltas) return
  yield* appendVisibleTextDelta(
    state,
    state.accumulated.slice(state.emittedTextLength),
    state.emittedTextLength,
  )
}

function* appendVisibleTextDelta(
  state: BackendChatState,
  text: string,
  previousTextLength: number,
): Generator<unknown> {
  if (text.length === 0) return
  if (state.thinkingBlockIndex !== null && !state.thinkingBlockStopped) {
    yield createContentBlockStopEvent(state.thinkingBlockIndex)
    state.thinkingBlockStopped = true
  }
  if (state.textBlockIndex === null) {
    yield createTextBlockStartEvent(state.nextContentBlockIndex)
    state.textBlockIndex = state.nextContentBlockIndex
    state.nextContentBlockIndex += 1
  }
  yield createTextDeltaEvent(state.textBlockIndex, text)
  state.emittedTextLength = previousTextLength + text.length
}

function* flushBufferedText(state: BackendChatState): Generator<unknown> {
  if (state.accumulated.length <= state.emittedTextLength) return
  yield* appendVisibleTextDelta(
    state,
    state.accumulated.slice(state.emittedTextLength),
    state.emittedTextLength,
  )
}

function* flushTextPreludeBeforeRawJsonToolUse(
  state: BackendChatState,
  prelude: string,
): Generator<unknown> {
  if (prelude.length <= state.emittedTextLength) return
  yield* appendVisibleTextDelta(
    state,
    prelude.slice(state.emittedTextLength),
    state.emittedTextLength,
  )
}

function* appendRawJsonToolUseBlock(params: {
  readonly state: BackendChatState
  readonly name: string
  readonly input: Record<string, unknown>
  readonly id?: string
}): Generator<unknown> {
  const toolUseBlock = {
    type: 'tool_use' as const,
    id: params.id ?? 'call_raw_json_tool_0',
    name: params.name,
    input: params.input,
  }
  params.state.pendingContentBlocks.push(toolUseBlock)
  const toolBlockIndex = params.state.nextContentBlockIndex
  params.state.nextContentBlockIndex += 1
  yield createToolUseBlockStartEvent(toolBlockIndex, toolUseBlock)
  yield createContentBlockStopEvent(toolBlockIndex)
}

function firstToolCallTextOffset(text: string): number {
  const braceOffset = firstRawJsonToolCallBufferStartOffset(text)
  const tagOffset = firstTextualToolCallBufferStartOffset(
    text,
    TEXTUAL_TOOL_CALL_OPEN,
  )
  if (braceOffset < 0) return tagOffset
  if (tagOffset < 0) return braceOffset
  return Math.min(braceOffset, tagOffset)
}

function* stopOpenBlocks(state: BackendChatState): Generator<unknown> {
  if (state.thinkingBlockIndex !== null && !state.thinkingBlockStopped) {
    yield createContentBlockStopEvent(state.thinkingBlockIndex)
    state.thinkingBlockStopped = true
  }
  if (state.textBlockIndex !== null && !state.textBlockStopped) {
    yield createContentBlockStopEvent(state.textBlockIndex)
    state.textBlockStopped = true
  }
}
