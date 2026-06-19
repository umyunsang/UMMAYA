import type {
  BetaContentBlock,
  BetaUsage as Usage,
  ThinkingBlock,
} from 'src/sdk-compat.js'
import type { SDKAssistantMessageError } from 'src/entrypoints/agentSdkTypes.js'
import { randomUUID } from 'crypto'
import { NO_CONTENT_MESSAGE } from '../constants/messages.js'
import type { AssistantMessage } from '../types/message.js'
import { SYNTHETIC_MODEL } from './messageText.js'

const EMPTY_USAGE: Usage = {
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

type AssistantContentBlock = BetaContentBlock | ThinkingBlock

function baseCreateAssistantMessage({
  content,
  isApiErrorMessage = false,
  apiError,
  error,
  errorDetails,
  isVirtual,
  usage = EMPTY_USAGE,
}: {
  content: AssistantContentBlock[]
  isApiErrorMessage?: boolean
  apiError?: AssistantMessage['apiError']
  error?: SDKAssistantMessageError
  errorDetails?: string
  isVirtual?: true
  usage?: Usage
}): AssistantMessage {
  return {
    type: 'assistant',
    uuid: randomUUID(),
    timestamp: new Date().toISOString(),
    message: {
      id: randomUUID(),
      container: null,
      model: SYNTHETIC_MODEL,
      role: 'assistant',
      stop_reason: 'stop_sequence',
      stop_sequence: '',
      type: 'message',
      usage,
      content,
      context_management: null,
    },
    requestId: undefined,
    apiError,
    error,
    errorDetails,
    isApiErrorMessage,
    isVirtual,
  }
}

export function createAssistantMessage({
  content,
  usage,
  isVirtual,
}: {
  content: string | AssistantContentBlock[]
  usage?: Usage
  isVirtual?: true
}): AssistantMessage {
  return baseCreateAssistantMessage({
    content:
      typeof content === 'string'
        ? [
            {
              type: 'text' as const,
              text: content === '' ? NO_CONTENT_MESSAGE : content,
            } as BetaContentBlock,
          ]
        : content,
    usage,
    isVirtual,
  })
}

export function createAssistantAPIErrorMessage({
  content,
  apiError,
  error,
  errorDetails,
}: {
  content: string
  apiError?: AssistantMessage['apiError']
  error?: SDKAssistantMessageError
  errorDetails?: string
}): AssistantMessage {
  return baseCreateAssistantMessage({
    content: [
      {
        type: 'text' as const,
        text: content === '' ? NO_CONTENT_MESSAGE : content,
      } as BetaContentBlock,
    ],
    isApiErrorMessage: true,
    apiError,
    error,
    errorDetails,
  })
}
