export type ChatMessageRole = 'system' | 'user' | 'assistant' | 'tool'

export type ChatMessageToolCall = {
  readonly id: string
  readonly type: 'function'
  readonly function: {
    readonly name: string
    readonly arguments: string
  }
}

export type ChatMessage = {
  readonly role: ChatMessageRole
  readonly content: string
  readonly name?: string | null
  readonly tool_call_id?: string | null
  readonly tool_calls?: readonly ChatMessageToolCall[] | null
}
