import { mcpInfoFromString } from '../../services/mcp/mcpStringUtils.js'
import type { ToolPermissionContext, ToolUseContext } from '../../Tool.js'
import type { PermissionResult } from '../../utils/permissions/PermissionResult.js'
import {
  getAllowRules,
  getDenyRuleForTool,
} from '../../utils/permissions/permissions.js'

const TRUSTED_BUILTIN_MCP_SERVERS = ['ummaya'] as const

type McpTrustInput = { readonly [key: string]: unknown }

function mcpServerRuleName(serverName: string): string {
  return `mcp__${serverName}`
}

function hasExactServerAllowRule(
  permissionContext: ToolPermissionContext,
  serverName: string,
): boolean {
  return getAllowRules(permissionContext).some(rule => {
    if (rule.ruleValue.ruleContent !== undefined) return false
    const ruleInfo = mcpInfoFromString(rule.ruleValue.toolName)
    if (ruleInfo === null) return false
    return (
      ruleInfo.serverName === serverName &&
      (ruleInfo.toolName === undefined || ruleInfo.toolName === '*')
    )
  })
}

function hasServerDenyRule(
  permissionContext: ToolPermissionContext,
  serverName: string,
): boolean {
  return (
    getDenyRuleForTool(permissionContext, {
      name: mcpServerRuleName(serverName),
      mcpInfo: { serverName, toolName: '*' },
    }) !== null
  )
}

export function isTrustedMcpServer(
  permissionContext: ToolPermissionContext,
  serverName: string,
): boolean {
  if (hasServerDenyRule(permissionContext, serverName)) return false
  if (TRUSTED_BUILTIN_MCP_SERVERS.some(name => name === serverName)) return true
  return hasExactServerAllowRule(permissionContext, serverName)
}

export function assertNonEmptyMcpServerName(serverName: string): void {
  if (serverName.trim().length === 0) {
    throw new Error('MCP server name cannot be empty')
  }
}

export function assertNonEmptyMcpResourceUri(uri: string): void {
  if (uri.trim().length === 0) {
    throw new Error('MCP resource URI cannot be empty')
  }
}

export function assertTrustedMcpServerForResourceAccess(
  permissionContext: ToolPermissionContext,
  serverName: string,
): void {
  assertTrustedMcpServer(
    permissionContext,
    serverName,
    `Server "${serverName}" is not trusted for MCP resource access`,
  )
}

export function assertTrustedMcpServer(
  permissionContext: ToolPermissionContext,
  serverName: string,
  message: string,
): void {
  assertNonEmptyMcpServerName(serverName)
  if (!isTrustedMcpServer(permissionContext, serverName)) {
    throw new Error(message)
  }
}

export function createMcpServerTrustSuggestion(serverName: string) {
  return {
    type: 'addRules' as const,
    rules: [
      {
        toolName: mcpServerRuleName(serverName),
        ruleContent: undefined,
      },
    ],
    behavior: 'allow' as const,
    destination: 'localSettings' as const,
  }
}

export function checkMcpServerTrustPermission<Input extends McpTrustInput>(
  serverName: string,
  input: Input,
  context: ToolUseContext,
  message: string,
): PermissionResult<Input> {
  assertNonEmptyMcpServerName(serverName)
  if (
    isTrustedMcpServer(context.getAppState().toolPermissionContext, serverName)
  ) {
    return { behavior: 'allow', updatedInput: input }
  }
  return {
    behavior: 'passthrough',
    message,
    suggestions: [createMcpServerTrustSuggestion(serverName)],
  }
}
