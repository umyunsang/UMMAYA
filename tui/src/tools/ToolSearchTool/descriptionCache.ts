import memoize from 'lodash-es/memoize.js'
import { findToolByName, type Tools } from '../../Tool.js'
import { logForDebugging } from '../../utils/debug.js'

let cachedDeferredToolNames: string | null = null

function getDeferredToolsCacheKey(deferredTools: Tools): string {
  return deferredTools
    .map(tool => tool.name)
    .sort()
    .join(',')
}

export const getToolDescriptionMemoized = memoize(
  async (toolName: string, tools: Tools): Promise<string> => {
    const tool = findToolByName(tools, toolName)
    if (!tool) {
      return ''
    }
    return tool.prompt({
      getToolPermissionContext: async () => ({
        mode: 'default' as const,
        additionalWorkingDirectories: new Map(),
        alwaysAllowRules: {},
        alwaysDenyRules: {},
        alwaysAskRules: {},
        isBypassPermissionsModeAvailable: false,
      }),
      tools,
      agents: [],
    })
  },
  (toolName: string) => toolName,
)

export function maybeInvalidateCache(deferredTools: Tools): void {
  const currentKey = getDeferredToolsCacheKey(deferredTools)
  if (cachedDeferredToolNames !== currentKey) {
    logForDebugging(
      `ToolSearchTool: cache invalidated - deferred tools changed`,
    )
    getToolDescriptionMemoized.cache.clear?.()
    cachedDeferredToolNames = currentKey
  }
}

export function clearToolSearchDescriptionCache(): void {
  getToolDescriptionMemoized.cache.clear?.()
  cachedDeferredToolNames = null
}
