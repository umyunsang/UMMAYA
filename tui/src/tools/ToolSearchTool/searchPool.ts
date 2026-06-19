import type { ToolPermissionContext, Tools } from '../../Tool.js'
import { isDeferredTool } from './prompt.js'
import { selectRecoveredSupportToolNamesForQuery } from './supportIntentHints.js'

const DEFAULT_DISCOVERABLE_SUPPORT_TOOLS = new Set(['WebSearch', 'WebFetch'])

function selectedSupportToolNames(query: string): ReadonlySet<string> {
  const names = new Set(DEFAULT_DISCOVERABLE_SUPPORT_TOOLS)
  for (const toolName of selectRecoveredSupportToolNamesForQuery(query)) {
    names.add(toolName)
  }

  const selectMatch = query.match(/^select:(.+)$/iu)
  if (selectMatch) {
    for (const toolName of (selectMatch[1] ?? '').split(',')) {
      const trimmed = toolName.trim()
      if (trimmed.length > 0) names.add(trimmed)
    }
  }
  return names
}

export async function getToolSearchPool(
  tools: Tools,
  getAppState: () => { toolPermissionContext?: ToolPermissionContext },
  query = '',
): Promise<Tools> {
  const byName = new Map(tools.map(tool => [tool.name, tool]))
  const { filterToolsByDenyRules, getAllBaseTools } = await import(
    '../../tools.js'
  )
  const appState = getAppState()
  const registeredDeferredTools = getAllBaseTools().filter(isDeferredTool)
  const policyFilteredTools = appState.toolPermissionContext
    ? filterToolsByDenyRules(
        registeredDeferredTools,
        appState.toolPermissionContext,
      )
    : registeredDeferredTools
  const supportToolNames = selectedSupportToolNames(query)

  for (const tool of policyFilteredTools) {
    if (!byName.has(tool.name) && !supportToolNames.has(tool.name)) continue
    if (!byName.has(tool.name)) byName.set(tool.name, tool)
  }
  return [...byName.values()]
}
