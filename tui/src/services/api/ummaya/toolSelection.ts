import { getAllBaseTools } from '../../../tools.js'
import type { Tool, Tools } from '../../../Tool.js'
import {
  getAdapterToolByName,
  hasRestrictiveAdapterRoutingIntentForQuery,
  selectTopKAdapterToolNamesForQuery,
} from '../../../tools/AdapterTool/AdapterTool.js'
import {
  appendRouteDiagnostic,
  hashRouteDiagnosticText,
} from '../../../tools/AdapterTool/routeDiagnostics.js'
import { selectRecoveredSupportToolNamesForQuery } from '../../../tools/ToolSearchTool/supportIntentHints.js'
import {
  getAdapterManifestHash,
  listAdapters,
  type AdapterManifestEntry,
} from '../adapterManifest.js'
import type { ProviderTurnEvidenceContext } from './evidence.js'
import {
  DOCUMENT_TOOL_NAME,
  isExactLocalReadOnlyDocumentPrompt,
} from '../../../tools/_shared/toolChoiceRepair/documentCompletionPatterns.js'

const MAIN_THREAD_QUERY_SOURCE = 'repl_main_thread'
const SDK_QUERY_SOURCE = 'sdk'
const ADAPTER_CANDIDATE_LIMIT = 5
const WORKSPACE_SUPPORT_TOOL_NAMES = new Set([
  'workspace_grep',
  'workspace_read',
])
const FORCEABLE_WORKSPACE_SUPPORT_TOOL_NAMES = new Set([
  'workspace_bash',
])

function pushUniqueTool(target: Tool[], tool: Tool | undefined): void {
  if (!tool) return
  if (!target.some(candidate => candidate.name === tool.name)) {
    target.push(tool)
  }
}

function baseToolByName(name: string): Tool | undefined {
  return getAllBaseTools().find(tool => tool.name === name)
}

function hasToolNamed(tools: readonly Tool[], name: string): boolean {
  return tools.some(tool => tool.name === name)
}

function toolByName(tools: readonly Tool[], name: string): Tool | undefined {
  return tools.find(tool => tool.name === name)
}

function pushUniqueAdapterEntry(
  target: AdapterManifestEntry[],
  entry: AdapterManifestEntry | undefined,
): void {
  if (!entry) return
  if (!target.some(candidate => candidate.tool_id === entry.tool_id)) {
    target.push(entry)
  }
}

function hasWorkspaceSupportToolName(names: readonly string[]): boolean {
  return names.some(name => WORKSPACE_SUPPORT_TOOL_NAMES.has(name))
}

function isMainThreadQuerySource(querySource: string): boolean {
  return (
    querySource === MAIN_THREAD_QUERY_SOURCE ||
    querySource.startsWith(`${MAIN_THREAD_QUERY_SOURCE}:`)
  )
}

function isUserFacingQuerySource(querySource: string): boolean {
  return isMainThreadQuerySource(querySource) || querySource === SDK_QUERY_SOURCE
}

function filterToAdapterSurface(params: {
  readonly selected: readonly Tool[]
  readonly selectedAdapterEntries: readonly AdapterManifestEntry[]
  readonly forcedToolName?: string
}): Tool[] {
  if (params.selectedAdapterEntries.length === 0) {
    return params.selected.filter(tool => tool.name === params.forcedToolName)
  }
  const selectedAdapterToolIds = new Set(
    params.selectedAdapterEntries.map(entry => entry.tool_id),
  )
  return params.selected.filter(tool => {
    if (tool.name === params.forcedToolName) return true
    return selectedAdapterToolIds.has(tool.name)
  })
}

export function selectProviderToolChoiceName(params: {
  readonly tools: Tools
  readonly userText: string
  readonly forcedToolName?: string
}): string | undefined {
  if (params.forcedToolName) return params.forcedToolName
  if (
    isExactLocalReadOnlyDocumentPrompt(params.userText) &&
    hasToolNamed(params.tools, DOCUMENT_TOOL_NAME)
  ) {
    return DOCUMENT_TOOL_NAME
  }
  for (const name of selectRecoveredSupportToolNamesForQuery(params.userText)) {
    if (
      FORCEABLE_WORKSPACE_SUPPORT_TOOL_NAMES.has(name) &&
      baseToolByName(name)
    ) {
      return name
    }
  }
  return undefined
}

export function shouldWaitForAdapterManifestForProviderRequest(params: {
  readonly querySource: string
  readonly userText: string
}): boolean {
  const hasAdapterIntent =
    hasRestrictiveAdapterRoutingIntentForQuery(params.userText)
  if (
    !hasAdapterIntent &&
    selectRecoveredSupportToolNamesForQuery(params.userText).length > 0
  ) {
    return false
  }
  if (isExactLocalReadOnlyDocumentPrompt(params.userText)) {
    return false
  }
  return (
    params.userText.trim().length > 0 &&
    isUserFacingQuerySource(params.querySource)
  )
}

export function selectProviderTools(params: {
  readonly tools: Tools
  readonly userText: string
  readonly forcedToolName?: string
  readonly disabledToolNames?: readonly string[]
  readonly querySource: string
  readonly hasCurrentTurnLocationContext?: boolean
  readonly evidenceContext?: ProviderTurnEvidenceContext
}): readonly Tool[] {
  const adapters = listAdapters()
  const adapterEntriesByToolId = new Map(
    adapters.map(entry => [entry.tool_id, entry]),
  )
  const adapterToolIds = new Set(adapterEntriesByToolId.keys())
  const disabledToolNames = new Set(params.disabledToolNames ?? [])
  let selected: Tool[] = []
  const selectedAdapterEntries: AdapterManifestEntry[] = []
  const hasAdapterIntent = hasRestrictiveAdapterRoutingIntentForQuery(
    params.userText,
    { hasCurrentTurnLocationContext: params.hasCurrentTurnLocationContext },
  )
  const recoveredSupportToolNames =
    isExactLocalReadOnlyDocumentPrompt(params.userText) || hasAdapterIntent
      ? []
      : selectRecoveredSupportToolNamesForQuery(params.userText)
  const useWorkspaceOnlySurface = hasWorkspaceSupportToolName(recoveredSupportToolNames)

  for (const name of recoveredSupportToolNames) {
    pushUniqueTool(selected, baseToolByName(name))
  }

  if (!useWorkspaceOnlySurface) {
    for (const name of selectTopKAdapterToolNamesForQuery(
      params.userText,
      ADAPTER_CANDIDATE_LIMIT,
      { hasCurrentTurnLocationContext: params.hasCurrentTurnLocationContext },
    )) {
      if (disabledToolNames.has(name)) continue
      pushUniqueTool(selected, getAdapterToolByName(name))
      pushUniqueAdapterEntry(selectedAdapterEntries, adapterEntriesByToolId.get(name))
    }
  }

  if (params.forcedToolName) {
    pushUniqueTool(
      selected,
      toolByName(params.tools, params.forcedToolName) ??
        getAdapterToolByName(params.forcedToolName) ??
        baseToolByName(params.forcedToolName),
    )
    pushUniqueAdapterEntry(
      selectedAdapterEntries,
      adapterEntriesByToolId.get(params.forcedToolName),
    )
    selected = selected.filter(tool => tool.name === params.forcedToolName)
  }

  if (useWorkspaceOnlySurface) {
    selected = selected.filter(tool => {
      if (tool.name === params.forcedToolName) return true
      return recoveredSupportToolNames.includes(tool.name)
    })
  } else if (
    isUserFacingQuerySource(params.querySource) &&
    selectedAdapterEntries.length > 0
  ) {
    selected = filterToAdapterSurface({
      selected,
      selectedAdapterEntries,
      forcedToolName: params.forcedToolName,
    })
  }

  const adapterNames = selected
    .map(tool => tool.name)
    .filter(name => adapterEntriesByToolId.has(name))
  if (adapterNames.length > 0 || process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE) {
    appendRouteDiagnostic('adapter_selection', {
      manifest_hash: getAdapterManifestHash(),
      query_source: params.querySource,
      schema_projection_level: 'top_k_concrete_adapter_schemas',
      selected_tools: adapterNames,
      final_adapter_tools: adapterNames,
      disabled_provider_tools: [...disabledToolNames],
      has_current_turn_location_context:
        params.hasCurrentTurnLocationContext === true,
      query_hash: hashRouteDiagnosticText(params.userText),
      session_id: params.evidenceContext?.session_id ?? null,
      correlation_id: params.evidenceContext?.correlation_id ?? null,
      frame_hash: params.evidenceContext?.frame_hash ?? null,
    })
  }
  return selected
}
