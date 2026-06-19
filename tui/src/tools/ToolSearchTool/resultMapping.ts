import type { ToolResultBlockParam } from '@anthropic-ai/sdk/resources/index.mjs'
import type { Output } from './schemas.js'

export function buildSearchResult(
  matches: string[],
  query: string,
  totalDeferredTools: number,
  pendingMcpServers?: string[],
): { data: Output } {
  return {
    data: {
      matches,
      query,
      total_deferred_tools: totalDeferredTools,
      ...(pendingMcpServers && pendingMcpServers.length > 0
        ? { pending_mcp_servers: pendingMcpServers }
        : {}),
    },
  }
}

export function makeToolReferenceContent(
  matches: readonly string[],
): ToolResultBlockParam['content'] {
  const content = matches.map(name => ({
    type: 'tool_reference',
    tool_name: name,
  }))
  return JSON.parse(JSON.stringify(content))
}
