import type {
  ToolCallProgress,
  ToolResult,
  ToolUseContext,
} from '../../Tool.js'
import type { WebSearchProgress } from '../../types/tools.js'
import type { Input, Output } from './schemas.js'
import { makeBlockedOutputFromProviderError } from './responseMapping.js'

class WebSearchProviderUnavailableError extends Error {
  readonly name = 'WebSearchProviderUnavailableError'

  constructor() {
    super(
      'WebSearch is blocked: UMMAYA does not currently expose a policy-approved server-side web search provider for the FriendliAI execution path. Use WebFetch with an explicit public URL or a registered live adapter instead.',
    )
  }
}

export async function callWebSearch(
  input: Input,
  _context: ToolUseContext,
  _onProgress?: ToolCallProgress<WebSearchProgress>,
): Promise<ToolResult<Output>> {
  const startTime = performance.now()
  return {
    data: makeBlockedOutputFromProviderError(
      input.query,
      startTime,
      new WebSearchProviderUnavailableError(),
    ),
  }
}
