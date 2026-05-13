import { feature } from 'bun:bundle'
import type { BetaToolUseBlock } from 'src/sdk-compat.js'
import type { SpinnerMode } from '../components/Spinner.js'
import { isConnectorTextBlock } from '../types/connectorText.js'
import type {
  Message,
  RequestStartEvent,
  StreamEvent,
  TombstoneMessage,
  ToolUseSummaryMessage,
} from '../types/message.js'

export type StreamingToolUse = {
  index: number
  contentBlock: BetaToolUseBlock
  unparsedToolInput: string
}

export type StreamingThinking = {
  thinking: string
  isStreaming: boolean
  streamingEndedAt?: number
}

export function handleMessageFromStream(
  message:
    | Message
    | TombstoneMessage
    | StreamEvent
    | RequestStartEvent
    | ToolUseSummaryMessage,
  onMessage: (message: Message) => void,
  onUpdateLength: (newContent: string) => void,
  onSetStreamMode: (mode: SpinnerMode) => void,
  onStreamingToolUses: (
    f: (streamingToolUse: StreamingToolUse[]) => StreamingToolUse[],
  ) => void,
  onTombstone?: (message: Message) => void,
  onStreamingThinking?: (
    f: (current: StreamingThinking | null) => StreamingThinking | null,
  ) => void,
  onApiMetrics?: (metrics: { ttftMs: number }) => void,
  onStreamingText?: (f: (current: string | null) => string | null) => void,
): void {
  if (
    message.type !== 'stream_event' &&
    message.type !== 'stream_request_start'
  ) {
    if (message.type === 'tombstone') {
      onTombstone?.(message.message)
      return
    }
    if (message.type === 'tool_use_summary') {
      return
    }
    if (message.type === 'assistant') {
      const thinkingBlock = message.message.content.find(
        block => block.type === 'thinking',
      )
      if (thinkingBlock && thinkingBlock.type === 'thinking') {
        onStreamingThinking?.(() => ({
          thinking: thinkingBlock.thinking,
          isStreaming: false,
          streamingEndedAt: Date.now(),
        }))
      }
    }
    onStreamingText?.(() => null)
    onMessage(message)
    return
  }

  if (message.type === 'stream_request_start') {
    onSetStreamMode('requesting')
    return
  }

  if (message.event.type === 'message_start' && message.ttftMs != null) {
    onApiMetrics?.({ ttftMs: message.ttftMs })
  }

  if (message.event.type === 'message_stop') {
    onSetStreamMode('tool-use')
    onStreamingToolUses(() => [])
    return
  }

  switch (message.event.type) {
    case 'content_block_start':
      onStreamingText?.(() => null)
      if (
        feature('CONNECTOR_TEXT') &&
        isConnectorTextBlock(message.event.content_block)
      ) {
        onSetStreamMode('responding')
        return
      }
      switch (message.event.content_block.type) {
        case 'thinking':
        case 'redacted_thinking':
          onSetStreamMode('thinking')
          return
        case 'text':
          onSetStreamMode('responding')
          return
        case 'tool_use': {
          onSetStreamMode('tool-input')
          const contentBlock = message.event.content_block
          const index = message.event.index
          onStreamingToolUses(_ => [
            ..._,
            {
              index,
              contentBlock,
              unparsedToolInput: '',
            },
          ])
          return
        }
        case 'server_tool_use':
        case 'web_search_tool_result':
        case 'code_execution_tool_result':
        case 'mcp_tool_use':
        case 'mcp_tool_result':
        case 'container_upload':
        case 'web_fetch_tool_result':
        case 'bash_code_execution_tool_result':
        case 'text_editor_code_execution_tool_result':
        case 'tool_search_tool_result':
        case 'compaction':
          onSetStreamMode('tool-input')
          return
      }
      return
    case 'content_block_delta':
      switch (message.event.delta.type) {
        case 'text_delta': {
          const deltaText = message.event.delta.text
          onUpdateLength(deltaText)
          onStreamingText?.(text => (text ?? '') + deltaText)
          return
        }
        case 'input_json_delta': {
          const delta = message.event.delta.partial_json
          const index = message.event.index
          onUpdateLength(delta)
          onStreamingToolUses(_ => {
            const element = _.find(_ => _.index === index)
            if (!element) {
              return _
            }
            return [
              ..._.filter(_ => _ !== element),
              {
                ...element,
                unparsedToolInput: element.unparsedToolInput + delta,
              },
            ]
          })
          return
        }
        case 'thinking_delta': {
          const thinkingDelta = message.event.delta.thinking
          onUpdateLength(thinkingDelta)
          onStreamingThinking?.(prev => ({
            thinking: (prev?.thinking ?? '') + thinkingDelta,
            isStreaming: true,
            streamingEndedAt: undefined,
          }))
          return
        }
        case 'signature_delta':
          return
        default:
          return
      }
    case 'content_block_stop':
      return
    case 'message_delta':
      onSetStreamMode('responding')
      return
    default:
      onSetStreamMode('responding')
      return
  }
}
