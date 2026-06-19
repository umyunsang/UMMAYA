import type { AppState } from '../../state/AppState.js'
import type { Tools, ToolUseContext } from '../../Tool.js'
import { sleep } from '../../utils/sleep.js'
import type { AgentDefinition } from './loadAgentsDir.js'
import { hasRequiredMcpServers } from './loadAgentsDir.js'

export async function waitForRequiredMcpServers(
  selectedAgent: AgentDefinition,
  toolUseContext: ToolUseContext,
  appState: AppState,
): Promise<void> {
  const requiredMcpServers = selectedAgent.requiredMcpServers
  if (!requiredMcpServers?.length) return
  let currentAppState = appState
  if (hasPendingRequiredServers(currentAppState, requiredMcpServers)) {
    const deadline = Date.now() + 30_000
    while (Date.now() < deadline) {
      await sleep(500)
      currentAppState = toolUseContext.getAppState()
      if (hasFailedRequiredServer(currentAppState, requiredMcpServers)) break
      if (!hasPendingRequiredServers(currentAppState, requiredMcpServers)) break
    }
  }
  const serversWithTools = mcpServersWithTools(currentAppState.mcp.tools)
  if (hasRequiredMcpServers(selectedAgent, serversWithTools)) return
  const missing = requiredMcpServers.filter(
    pattern =>
      !serversWithTools.some(server =>
        server.toLowerCase().includes(pattern.toLowerCase()),
      ),
  )
  throw new Error(
    `Agent '${selectedAgent.agentType}' requires MCP servers matching: ${missing.join(', ')}. MCP servers with tools: ${serversWithTools.length > 0 ? serversWithTools.join(', ') : 'none'}. Use /mcp to configure and authenticate the required MCP servers.`,
  )
}

export function mcpServersWithTools(tools: Tools): string[] {
  const serverNames: string[] = []
  for (const tool of tools) {
    if (!tool.name?.startsWith('mcp__')) continue
    const serverName = tool.name.split('__')[1]
    if (serverName && !serverNames.includes(serverName)) {
      serverNames.push(serverName)
    }
  }
  return serverNames
}

function hasPendingRequiredServers(
  appState: AppState,
  requiredMcpServers: readonly string[],
): boolean {
  return appState.mcp.clients.some(
    client =>
      client.type === 'pending' &&
      requiredMcpServers.some(pattern =>
        client.name.toLowerCase().includes(pattern.toLowerCase()),
      ),
  )
}

function hasFailedRequiredServer(
  appState: AppState,
  requiredMcpServers: readonly string[],
): boolean {
  return appState.mcp.clients.some(
    client =>
      client.type === 'failed' &&
      requiredMcpServers.some(pattern =>
        client.name.toLowerCase().includes(pattern.toLowerCase()),
      ),
  )
}
