import {
  createAssistantAPIErrorMessage,
  createAssistantMessage,
} from '../../../utils/messages.js'
import { logError } from '../../../utils/log.js'
import {
  classifyRawJsonToolCallProposal,
  extractTextualToolCallProposals,
  parseTrailingRawJsonToolCallProposal,
  RAW_JSON_REGISTERED_TOOL_USE_ID_PREFIX,
  RAW_JSON_UNREGISTERED_TOOL_USE_ID_PREFIX,
  textContainsMalformedToolCallProposal,
} from '../../../utils/rawJsonToolCall.js'
import type { RawJsonToolCallProposal } from '../../../utils/rawJsonToolCall.js'
import {
  firstRawJsonToolCallBufferStartOffset,
  firstTextualToolCallBufferStartOffset,
} from '../../../utils/toolCallStreamBuffer.js'
import type { Message, StreamEvent } from '../../../types/message.js'
import type { OpenAIToolCall } from './types.js'
import {
  cancelReader,
  dataIdleDeadline,
  dataIdleTimeoutRemaining,
  readNextStreamChunk,
} from './streamingReader.js'
import {
  chunkFromPayload,
  completedToolCalls,
  parseJsonLine,
  parseToolArguments,
  providerFailureMessage,
} from './streamingPayload.js'

const PROVIDER_EMPTY_COMPLETION_HANDOFF =
  'K-EXAONE 응답이 비어 있어 이번 요청을 이어갈 수 없습니다. 잠시 후 다시 시도해 주세요.'
const PROVIDER_MALFORMED_TOOL_CALL_HANDOFF =
  'K-EXAONE emitted malformed tool-call JSON. Retry with a registered tool call instead of raw JSON prose.'
const TEXTUAL_TOOL_CALL_OPEN = '<tool_call>'

export type StreamResponseOptions = {
  readonly dataIdleTimeoutMs?: number
  readonly availableToolNames?: readonly string[]
  readonly includeReasoning?: boolean
}

type ToolCallState = {
  id?: string
  name?: string
  arguments: string
}

export class ProviderStreamIdleTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`FriendliAI SSE data idle timeout after ${timeoutMs}ms`)
    this.name = 'ProviderStreamIdleTimeoutError'
  }
}

export async function* streamResponseToMessages(
  response: Response,
  options: StreamResponseOptions = {},
): AsyncGenerator<StreamEvent | Message> {
  yield streamEvent({ type: 'message_start' })
  let text = ''
  let thinking = ''
  let thinkingBlockStarted = false
  let shouldBufferTextDeltas = false
  let emittedTextLength = 0
  let sawTextDelta = false
  const toolCallStates = new Map<number, ToolCallState>()
  if (!response.ok) {
    const body = await response.text()
    const message = providerFailureMessage(response, body)
    logError(new Error(message))
    yield createAssistantAPIErrorMessage({
      content: message,
      apiError: 'api_error',
    })
    return
  }
  if (response.body === null) {
    const message =
      'FriendliAI response did not include a stream body. Check provider configuration and retry.'
    logError(new Error(message))
    yield createAssistantAPIErrorMessage({
      content: message,
      apiError: 'api_error',
    })
    return
  }
  let sawStreamData = false
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let streamDone = false
  let nextDataDeadline = dataIdleDeadline(options.dataIdleTimeoutMs)
  while (!streamDone) {
    const timeoutMs = dataIdleTimeoutRemaining(
      options.dataIdleTimeoutMs,
      nextDataDeadline,
    )
    const read = await readNextStreamChunk(reader, timeoutMs)
    if (read === 'timeout') {
      void cancelReader(reader)
      throw new ProviderStreamIdleTimeoutError(options.dataIdleTimeoutMs ?? 0)
    }
    if (read.done) {
      buffer += decoder.decode()
      streamDone = true
    } else {
      buffer += decoder.decode(read.value, { stream: true })
    }
    const lines = buffer.split(/\n/u)
    buffer = streamDone ? '' : lines.pop() ?? ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      nextDataDeadline = dataIdleDeadline(options.dataIdleTimeoutMs)
      const data = trimmed.slice(5).trim()
      if (data === '[DONE]') {
        streamDone = true
        void cancelReader(reader)
        break
      }
      const payload = parseJsonLine(data)
      if (!payload) continue
      sawStreamData = true
      const chunk = chunkFromPayload(payload)
      if (chunk.reasoning.length > 0 && options.includeReasoning === true) {
        thinking += chunk.reasoning
        if (!thinkingBlockStarted) {
          thinkingBlockStarted = true
          yield streamEvent({
            type: 'content_block_start',
            index: 0,
            content_block: { type: 'thinking', thinking: '' },
          })
        }
        yield streamEvent({
          type: 'content_block_delta',
          index: 0,
          delta: { type: 'thinking_delta', thinking: chunk.reasoning },
        })
      }
      if (chunk.text.length > 0) {
        text += chunk.text
        const bufferOffset = firstToolCallTextOffset(text)
        const startsBuffering = !shouldBufferTextDeltas && bufferOffset >= 0
        if (startsBuffering) {
          shouldBufferTextDeltas = true
        }
        sawTextDelta = true
        if (startsBuffering) {
          if (bufferOffset > emittedTextLength) {
            const prefix = text.slice(emittedTextLength, bufferOffset)
            yield streamEvent({
              type: 'content_block_delta',
              delta: { type: 'text_delta', text: prefix },
            })
            emittedTextLength = bufferOffset
          }
        } else if (shouldBufferTextDeltas && bufferOffset < 0) {
          shouldBufferTextDeltas = false
          const visibleText = text.slice(emittedTextLength)
          yield streamEvent({
            type: 'content_block_delta',
            delta: { type: 'text_delta', text: visibleText },
          })
          emittedTextLength = text.length
        } else if (!shouldBufferTextDeltas) {
          yield streamEvent({
            type: 'content_block_delta',
            delta: { type: 'text_delta', text: chunk.text },
          })
          emittedTextLength = text.length
        }
      }
      for (const toolCallDelta of chunk.toolCallDeltas) {
        const state = toolCallStates.get(toolCallDelta.index) ?? { arguments: '' }
        if (toolCallDelta.id !== undefined) state.id = toolCallDelta.id
        if (toolCallDelta.name !== undefined) state.name = toolCallDelta.name
        if (toolCallDelta.argumentsDelta !== undefined) {
          state.arguments += toolCallDelta.argumentsDelta
        }
        toolCallStates.set(toolCallDelta.index, state)
      }
    }
  }

  let toolCalls = completedToolCalls(toolCallStates)
  const textualToolCallExtraction = toolCalls.length === 0
    ? extractTextualToolCallProposals({ text })
    : undefined
  const rawJsonToolCallClassification =
    toolCalls.length === 0 && textualToolCallExtraction === undefined
      ? classifyRawJsonToolCallProposal({
          text,
          availableToolNames: options.availableToolNames ?? [],
        })
      : undefined
  const trailingRawJsonToolCall =
    rawJsonToolCallClassification?.kind === 'non_proposal'
    ? parseTrailingRawJsonToolCallProposal({
        text,
      })
    : undefined
  if (textualToolCallExtraction !== undefined) {
    const remainingPrelude = textualToolCallExtraction.text.slice(
      emittedTextLength,
    )
    if (remainingPrelude.length > 0) {
      yield streamEvent({
        type: 'content_block_delta',
        delta: { type: 'text_delta', text: remainingPrelude },
      })
    }
    text = textualToolCallExtraction.text
    toolCalls = textualToolCallExtraction.proposals.map((proposal, index) => ({
      id: rawJsonToolCallId({
        name: proposal.name,
        index,
        availableToolNames: options.availableToolNames ?? [],
      }),
      type: 'function' as const,
      function: {
        name: proposal.name,
        arguments: JSON.stringify(proposal.input),
      },
    }))
  } else if (rawJsonToolCallClassification !== undefined) {
    switch (rawJsonToolCallClassification.kind) {
      case 'registered':
      case 'unregistered':
        text = ''
        toolCalls = [toolCallFromRawJsonProposal({
          id: rawJsonToolCallId({
            name: rawJsonToolCallClassification.proposal.name,
            index: 0,
            availableToolNames: options.availableToolNames ?? [],
          }),
          proposal: rawJsonToolCallClassification.proposal,
        })]
        break
      case 'malformed_input':
        yield streamEvent({
          type: 'content_block_delta',
          delta: {
            type: 'text_delta',
            text: PROVIDER_MALFORMED_TOOL_CALL_HANDOFF,
          },
        })
        text = PROVIDER_MALFORMED_TOOL_CALL_HANDOFF
        emittedTextLength = text.length
        break
      case 'non_proposal':
        if (trailingRawJsonToolCall !== undefined) {
          const remainingPrelude = trailingRawJsonToolCall.prelude.slice(
            emittedTextLength,
          )
          if (remainingPrelude.length > 0) {
            yield streamEvent({
              type: 'content_block_delta',
              delta: { type: 'text_delta', text: remainingPrelude },
            })
          }
          text = trailingRawJsonToolCall.prelude
          toolCalls = [toolCallFromRawJsonProposal({
            id: rawJsonToolCallId({
              name: trailingRawJsonToolCall.proposal.name,
              index: 0,
              availableToolNames: options.availableToolNames ?? [],
            }),
            proposal: trailingRawJsonToolCall.proposal,
          })]
        } else if (shouldBufferTextDeltas && text.length > emittedTextLength) {
          const bufferedText = text.slice(emittedTextLength)
          if (textContainsMalformedToolCallProposal(bufferedText)) {
            yield streamEvent({
              type: 'content_block_delta',
              delta: {
                type: 'text_delta',
                text: PROVIDER_MALFORMED_TOOL_CALL_HANDOFF,
              },
            })
            text = [
              text.slice(0, emittedTextLength).trimEnd(),
              PROVIDER_MALFORMED_TOOL_CALL_HANDOFF,
            ]
              .filter(part => part.length > 0)
              .join('\n')
            emittedTextLength = text.length
          } else {
            yield streamEvent({
              type: 'content_block_delta',
              delta: { type: 'text_delta', text: bufferedText },
            })
            emittedTextLength = text.length
          }
        }
        break
    }
  } else if (shouldBufferTextDeltas && text.length > emittedTextLength) {
    yield streamEvent({
      type: 'content_block_delta',
      delta: { type: 'text_delta', text: text.slice(emittedTextLength) },
    })
  }
  if (text.length === 0 && toolCalls.length === 0) {
    if (sawStreamData) {
      yield createAssistantMessage({ content: PROVIDER_EMPTY_COMPLETION_HANDOFF })
      return
    }
    const message =
      'FriendliAI response did not contain stream data. Check provider configuration and retry.'
    logError(new Error(message))
    yield createAssistantAPIErrorMessage({
      content: message,
      apiError: 'api_error',
    })
    return
  }

  const blocks = []
  if (thinking.length > 0) {
    blocks.push({ type: 'thinking' as const, thinking })
  }
  if (text.length > 0) blocks.push({ type: 'text' as const, text })
  for (const call of toolCalls) {
    blocks.push({
      type: 'tool_use' as const,
      id: call.id,
      name: call.function.name,
      input: parseToolArguments(call.function.arguments),
    })
  }
  yield createAssistantMessage({ content: blocks })
}

function streamEvent(event: Record<string, unknown>): StreamEvent {
  return { type: 'stream_event', event }
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

function rawJsonToolCallId(params: {
  readonly name: string
  readonly index: number
  readonly availableToolNames: readonly string[]
}): string {
  const availableToolNames = new Set(params.availableToolNames)
  const prefix = availableToolNames.has(params.name)
    ? RAW_JSON_REGISTERED_TOOL_USE_ID_PREFIX
    : RAW_JSON_UNREGISTERED_TOOL_USE_ID_PREFIX
  return `${prefix}${params.index}`
}

function toolCallFromRawJsonProposal(params: {
  readonly id: string
  readonly proposal: RawJsonToolCallProposal
}): OpenAIToolCall {
  return {
    id: params.id,
    type: 'function',
    function: {
      name: params.proposal.name,
      arguments: JSON.stringify(params.proposal.input),
    },
  }
}
