import type { ToolPermissionContext } from '../../Tool.js'
import { mcpInfoFromString } from '../../services/mcp/mcpStringUtils.js'
import { getAllowRules } from '../../utils/permissions/permissions.js'

type McpExposureCandidate = {
  readonly name: string
  readonly mcpInfo?: { readonly serverName: string; readonly toolName: string }
}

export const MCP_MODEL_EXPOSURE_SERVER_CLASSES = [
  'ummaya',
  'trusted-configured',
  'untrusted-configured',
] as const

export type McpModelExposureServerClass =
  (typeof MCP_MODEL_EXPOSURE_SERVER_CLASSES)[number]

function getMcpServerName(tool: McpExposureCandidate): string | null {
  if (tool.mcpInfo?.serverName) return tool.mcpInfo.serverName
  return mcpInfoFromString(tool.name)?.serverName ?? null
}

function hasTrustedConfiguredMcpServerRecord(
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

export function classifyMcpServerForModelExposure(
  tool: McpExposureCandidate,
  permissionContext: ToolPermissionContext,
): McpModelExposureServerClass {
  const serverName = getMcpServerName(tool)
  if (serverName === 'ummaya') return 'ummaya'
  if (serverName === null) return 'untrusted-configured'
  if (hasTrustedConfiguredMcpServerRecord(permissionContext, serverName)) {
    return 'trusted-configured'
  }
  return 'untrusted-configured'
}

export function isModelFacingMcpTool(
  tool: McpExposureCandidate,
  permissionContext: ToolPermissionContext,
): boolean {
  const serverClass = classifyMcpServerForModelExposure(tool, permissionContext)
  switch (serverClass) {
    case 'ummaya':
    case 'trusted-configured':
      return true
    case 'untrusted-configured':
      return false
  }
}
