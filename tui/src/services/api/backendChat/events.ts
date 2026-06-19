import { SYNTHETIC_MODEL } from '../../../utils/messageText.js'
import type { PendingToolUseBlock } from './types.js'

const EMPTY_USAGE = {
  input_tokens: 0,
  output_tokens: 0,
  cache_creation_input_tokens: 0,
  cache_read_input_tokens: 0,
}

export function createMessageStartStreamEvent(
  innerMessageId: string,
  ttftMs: number,
): unknown {
  return {
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
        usage: EMPTY_USAGE,
      },
    },
    ttftMs,
  }
}

export function createThinkingBlockStartEvent(index: number): unknown {
  return {
    type: 'stream_event' as const,
    event: {
      type: 'content_block_start' as const,
      index,
      content_block: { type: 'thinking' as const, thinking: '' },
    },
  }
}

export function createTextBlockStartEvent(index: number): unknown {
  return {
    type: 'stream_event' as const,
    event: {
      type: 'content_block_start' as const,
      index,
      content_block: { type: 'text' as const, text: '' },
    },
  }
}

export function createThinkingDeltaEvent(index: number, thinking: string): unknown {
  return {
    type: 'stream_event' as const,
    event: {
      type: 'content_block_delta' as const,
      index,
      delta: { type: 'thinking_delta' as const, thinking },
    },
  }
}

export function createTextDeltaEvent(index: number, text: string): unknown {
  return {
    type: 'stream_event' as const,
    event: {
      type: 'content_block_delta' as const,
      index,
      delta: { type: 'text_delta' as const, text },
    },
  }
}

export function createContentBlockStopEvent(index: number): unknown {
  return {
    type: 'stream_event' as const,
    event: { type: 'content_block_stop' as const, index },
  }
}

export function createToolUseBlockStartEvent(
  index: number,
  contentBlock: PendingToolUseBlock,
): unknown {
  return {
    type: 'stream_event' as const,
    event: {
      type: 'content_block_start' as const,
      index,
      content_block: contentBlock,
    },
  }
}

export function createMessageDeltaEvent(
  stopReason: 'end_turn' | 'tool_use',
): unknown {
  return {
    type: 'stream_event' as const,
    event: {
      type: 'message_delta' as const,
      delta: { stop_reason: stopReason, stop_sequence: null },
      usage: { output_tokens: 0 },
    },
  }
}

export function createMessageStopEvent(): unknown {
  return {
    type: 'stream_event' as const,
    event: { type: 'message_stop' as const },
  }
}
