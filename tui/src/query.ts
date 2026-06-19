import type { CanUseToolFn } from './hooks/useCanUseTool.js'
import type { QuerySource } from './constants/querySource.js'
import type { QueryDeps } from './query/deps.js'
import type { ToolUseContext } from './Tool.js'
import type { SystemPrompt } from './utils/systemPromptType.js'
import type {
  Message,
  RequestStartEvent,
  StreamEvent,
  ToolUseSummaryMessage,
  TombstoneMessage,
} from './types/message.js'
import type { Terminal } from './query/transitions.js'
import { query } from './query/run.js'

export type QueryParams = {
  messages: Message[]
  systemPrompt: SystemPrompt
  userContext: { [k: string]: string }
  systemContext: { [k: string]: string }
  canUseTool: CanUseToolFn
  toolUseContext: ToolUseContext
  fallbackModel?: string
  querySource: QuerySource
  maxOutputTokensOverride?: number
  maxTurns?: number
  skipCacheWrite?: boolean
  taskBudget?: { total: number }
  deps?: QueryDeps
}

export { query }
export type QueryGenerator = AsyncGenerator<
  | StreamEvent
  | RequestStartEvent
  | Message
  | TombstoneMessage
  | ToolUseSummaryMessage,
  Terminal
>
