// biome-ignore-all assist/source/organizeImports: ANT-ONLY import markers must not be reordered
import { toolMatchesName, type Tool, type Tools } from './Tool.js'
import { AgentTool } from './tools/AgentTool/AgentTool.js'
import { SkillTool } from './tools/SkillTool/SkillTool.js'
import { LookupPrimitive } from './tools/LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from './tools/ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { SubmitPrimitive } from './tools/SubmitPrimitive/SubmitPrimitive.js'
import { VerifyPrimitive } from './tools/VerifyPrimitive/VerifyPrimitive.js'
import { DocumentPrimitive } from './tools/DocumentPrimitive/DocumentPrimitive.js'
import { getAdapterTools } from './tools/AdapterTool/AdapterTool.js'
import { ToolSearchTool } from './tools/ToolSearchTool/ToolSearchTool.js'
import { getWorkspaceTools } from './tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import uniqBy from 'lodash-es/uniqBy.js'
export {
  ALL_AGENT_DISALLOWED_TOOLS,
  CUSTOM_AGENT_DISALLOWED_TOOLS,
  ASYNC_AGENT_ALLOWED_TOOLS,
  COORDINATOR_MODE_ALLOWED_TOOLS,
} from './constants/tools.js'
import type { ToolPermissionContext } from './Tool.js'
import { getDenyRuleForTool } from './utils/permissions/permissions.js'
import { isEnvTruthy } from './utils/envUtils.js'
import {
  areCcSupportToolsEnabled,
  getCcSupportCapabilityTools,
  getSupportSimpleModeTools,
  REPL_TOOL_NAME,
  REPL_ONLY_TOOLS,
  isReplModeEnabled,
} from './tools/ToolSearchTool/ccSupportTools.js'
import { isModelFacingMcpTool } from './tools/WorkspaceToolAdapter/mcpExposurePolicy.js'

export { REPL_ONLY_TOOLS, areCcSupportToolsEnabled }
export {
  MCP_MODEL_EXPOSURE_SERVER_CLASSES,
  classifyMcpServerForModelExposure,
  type McpModelExposureServerClass,
} from './tools/WorkspaceToolAdapter/mcpExposurePolicy.js'

/**
 * Predefined tool presets that can be used with --tools flag
 */
export const TOOL_PRESETS = ['default'] as const

export type ToolPreset = (typeof TOOL_PRESETS)[number]

export function parseToolPreset(preset: string): ToolPreset | null {
  const presetString = preset.toLowerCase()
  if (!TOOL_PRESETS.includes(presetString as ToolPreset)) {
    return null
  }
  return presetString as ToolPreset
}

/**
 * Get the list of tool names for a given preset
 * Filters out tools that are disabled via isEnabled() check
 * @param preset The preset name
 * @returns Array of tool names
 */
export function getToolsForDefaultPreset(): string[] {
  const tools = getModelFacingBaseTools()
  const isEnabled = tools.map(tool => tool.isEnabled())
  return tools.filter((_, i) => isEnabled[i]).map(tool => tool.name)
}

/**
 * Get the complete exhaustive list of all tools that could be available
 * in the current environment (respecting process.env flags).
 * This is the source of truth for ALL tools.
 */
/**
 * NOTE: This MUST stay in sync with https://console.statsig.com/4aF3Ewatb6xPVpCwxb5nA3/dynamic_configs/claude_code_global_system_caching, in order to cache the system prompt across users.
 */
export function getModelFacingBaseTools(): Tools {
  return [
    // UMMAYA tool-surface swap: keep Claude Code's registry shape, but make
    // the built-in model-facing catalog the Korean public-service primitives.
    ToolSearchTool,
    LookupPrimitive,
    ResolveLocationPrimitive,
    SubmitPrimitive,
    VerifyPrimitive,
    DocumentPrimitive,
    ...getWorkspaceTools(),
  ]
}

export function getAllBaseTools(): Tools {
  return uniqBy(
    [...getModelFacingBaseTools(), ...getCcSupportCapabilityTools()],
    'name',
  )
}

/**
 * Filters out tools that are blanket-denied by the permission context.
 * A tool is filtered out if there's a deny rule matching its name with no
 * ruleContent (i.e., a blanket deny for that tool).
 *
 * Uses the same matcher as the runtime permission check (step 1a), so MCP
 * server-prefix rules like `mcp__server` strip all tools from that server
 * before the model sees them — not just at call time.
 */
export function filterToolsByDenyRules<
  T extends {
    name: string
    mcpInfo?: { serverName: string; toolName: string }
  },
>(tools: readonly T[], permissionContext: ToolPermissionContext): T[] {
  return tools.filter(tool => !getDenyRuleForTool(permissionContext, tool))
}

export const getTools = (permissionContext: ToolPermissionContext): Tools => {
  if (isEnvTruthy(process.env.CLAUDE_CODE_SIMPLE)) {
    return filterToolsByDenyRules(
      getSupportSimpleModeTools(getModelFacingBaseTools()),
      permissionContext,
    )
  }

  // Filter out tools that are denied by the deny rules
  let allowedTools = filterToolsByDenyRules(
    getModelFacingBaseTools(),
    permissionContext,
  )

  // When REPL mode is enabled, hide primitive tools from direct use.
  // They're still accessible inside REPL via the VM context.
  if (isReplModeEnabled()) {
    const replEnabled = allowedTools.some(tool =>
      toolMatchesName(tool, REPL_TOOL_NAME),
    )
    if (replEnabled) {
      allowedTools = allowedTools.filter(
        tool => !REPL_ONLY_TOOLS.has(tool.name),
      )
    }
  }

  const isEnabled = allowedTools.map(_ => _.isEnabled())
  return allowedTools.filter((_, i) => isEnabled[i])
}

/**
 * Assemble the full tool pool for a given permission context and MCP tools.
 *
 * This is the single source of truth for combining built-in tools with MCP tools.
 * Both REPL.tsx (via useMergedTools hook) and runAgent.ts (for coordinator workers)
 * use this function to ensure consistent tool pool assembly.
 *
 * The function:
 * 1. Gets built-in tools via getTools() (respects mode filtering)
 * 2. Filters MCP tools by deny rules
 * 3. Deduplicates by tool name (built-in tools take precedence)
 *
 * @param permissionContext - Permission context for filtering built-in tools
 * @param mcpTools - MCP tools from appState.mcp.tools
 * @returns Combined, deduplicated array of built-in and MCP tools
 */
export function assembleToolPool(
  permissionContext: ToolPermissionContext,
  mcpTools: Tools,
): Tools {
  const builtInTools = [...getTools(permissionContext), ...getAdapterTools()]

  // Filter out MCP tools that are in the deny list
  const allowedMcpTools = filterToolsByDenyRules(
    mcpTools,
    permissionContext,
  ).filter(tool => isModelFacingMcpTool(tool, permissionContext))

  // Sort each partition for prompt-cache stability, keeping built-ins as a
  // contiguous prefix. The server's claude_code_system_cache_policy places a
  // global cache breakpoint after the last prefix-matched built-in tool; a flat
  // sort would interleave MCP tools into built-ins and invalidate all downstream
  // cache keys whenever an MCP tool sorts between existing built-ins. uniqBy
  // preserves insertion order, so built-ins win on name conflict.
  // Avoid Array.toSorted (Node 20+) — we support Node 18. builtInTools is
  // readonly so copy-then-sort; allowedMcpTools is a fresh .filter() result.
  const byName = (a: Tool, b: Tool) => a.name.localeCompare(b.name)
  return uniqBy(
    [...builtInTools].sort(byName).concat(allowedMcpTools.sort(byName)),
    'name',
  )
}

/**
 * Get all tools including both built-in tools and MCP tools.
 *
 * This is the preferred function when you need the complete tools list for:
 * - Tool search threshold calculations (isToolSearchEnabled)
 * - Token counting that includes MCP tools
 * - Any context where MCP tools should be considered
 *
 * Use getTools() only when you specifically need just built-in tools.
 *
 * @param permissionContext - Permission context for filtering built-in tools
 * @param mcpTools - MCP tools from appState.mcp.tools
 * @returns Combined array of built-in and MCP tools
 */
export function getMergedTools(
  permissionContext: ToolPermissionContext,
  mcpTools: Tools,
): Tools {
  const builtInTools = getTools(permissionContext)
  const allowedMcpTools = filterToolsByDenyRules(
    mcpTools,
    permissionContext,
  ).filter(tool => isModelFacingMcpTool(tool, permissionContext))
  return [...builtInTools, ...allowedMcpTools]
}
