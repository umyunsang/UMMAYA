import type { Tools } from '../../../Tool.js'
import type { QuerySource } from '../../../constants/querySource.js'
import type { Message } from '../../../types/message.js'
import type { SystemPrompt } from '../../../utils/systemPromptType.js'

export type Usage = {
  readonly input_tokens: number
  readonly output_tokens: number
  readonly cache_creation_input_tokens: number
  readonly cache_read_input_tokens: number
  readonly server_tool_use?: {
    readonly web_search_requests?: number
    readonly web_fetch_requests?: number
  }
  readonly service_tier?: string | null
  readonly cache_creation?: {
    readonly ephemeral_1h_input_tokens?: number
    readonly ephemeral_5m_input_tokens?: number
  }
  readonly inference_geo?: string | null
  readonly iterations?: number | null
  readonly speed?: number | null
}

export const EMPTY_USAGE: Usage = {
  input_tokens: 0,
  output_tokens: 0,
  cache_creation_input_tokens: 0,
  cache_read_input_tokens: 0,
  server_tool_use: { web_search_requests: 0, web_fetch_requests: 0 },
  service_tier: null,
  cache_creation: {
    ephemeral_1h_input_tokens: 0,
    ephemeral_5m_input_tokens: 0,
  },
  inference_geo: null,
  iterations: null,
  speed: null,
}

export type OpenAIMessage = {
  readonly role: 'system' | 'user' | 'assistant' | 'tool'
  readonly content: string
  readonly tool_call_id?: string
  readonly name?: string
  readonly tool_calls?: readonly OpenAIToolCall[]
}

export type OpenAIToolCall = {
  readonly id: string
  readonly type: 'function'
  readonly function: {
    readonly name: string
    readonly arguments: string
  }
}

export type OpenAITool = {
  readonly type: 'function'
  readonly function: {
    readonly name: string
    readonly description: string
    readonly parameters: Record<string, unknown>
  }
}

export type ProviderOptions = {
  readonly getToolPermissionContext: () => Promise<unknown>
  readonly model: string
  readonly isNonInteractiveSession: boolean
  readonly querySource: QuerySource
  readonly agents: readonly unknown[]
  readonly allowedAgentTypes: readonly string[]
  readonly mcpTools: readonly unknown[]
  readonly toolChoice?: { readonly type: 'tool'; readonly name: string }
  readonly disabledProviderToolNames?: readonly string[]
  readonly fetchOverride?: (
    input: string | URL | Request,
    init?: RequestInit,
  ) => Promise<Response>
  readonly enablePromptCaching?: boolean
  readonly taskBudget?: { readonly total: number; readonly remaining?: number }
  readonly skipCacheWrite?: boolean
  readonly maxOutputTokensOverride?: number
}

export type QueryModelParams = {
  readonly messages: readonly Message[]
  readonly systemPrompt: SystemPrompt
  readonly thinkingConfig?: unknown
  readonly tools: Tools
  readonly signal: AbortSignal
  readonly options: ProviderOptions
}

export type ProviderRequest = {
  readonly model: string
  readonly stream: boolean
  readonly messages: readonly OpenAIMessage[]
  readonly chat_template_kwargs?: { readonly enable_thinking: boolean }
  readonly parse_reasoning?: boolean
  readonly include_reasoning?: boolean
  readonly tools?: readonly OpenAITool[]
  readonly tool_choice?: {
    readonly type: 'function'
    readonly function: { readonly name: string }
  }
  readonly metadata?: Record<string, string>
  readonly output_config?: Record<string, unknown>
}
