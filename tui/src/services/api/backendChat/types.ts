import type { ToolCallFrame } from '../../../ipc/frames.generated.js'

export type BackendChatParams = {
  readonly messages: readonly unknown[]
  readonly systemPrompt: unknown
  readonly thinkingConfig?: unknown
  readonly tools?: unknown
  readonly signal?: AbortSignal
  readonly options?: {
    readonly model?: string
    readonly querySource?: string
    readonly [key: string]: unknown
  }
}

export type PendingToolUseBlock = {
  readonly type: 'tool_use'
  readonly id: string
  readonly name: string
  readonly input: ToolCallFrame['arguments']
}

export type BackendChatState = {
  accumulated: string
  accumulatedThinking: string
  emittedTextLength: number
  messageStartEmitted: boolean
  nextContentBlockIndex: number
  shouldBufferTextDeltas: boolean
  textBlockIndex: number | null
  textBlockStopped: boolean
  thinkingBlockIndex: number | null
  thinkingBlockStopped: boolean
  readonly pendingContentBlocks: PendingToolUseBlock[]
}

export function createBackendChatState(): BackendChatState {
  return {
    accumulated: '',
    accumulatedThinking: '',
    emittedTextLength: 0,
    messageStartEmitted: false,
    nextContentBlockIndex: 0,
    shouldBufferTextDeltas: false,
    textBlockIndex: null,
    textBlockStopped: false,
    thinkingBlockIndex: null,
    thinkingBlockStopped: false,
    pendingContentBlocks: [],
  }
}

export function hasAssistantPayload(
  state: BackendChatState,
  persistThinking: boolean,
): boolean {
  return (
    state.accumulated.length > 0 ||
    state.pendingContentBlocks.length > 0 ||
    (persistThinking && state.accumulatedThinking.length > 0)
  )
}
