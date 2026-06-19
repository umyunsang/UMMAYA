import type { Tool } from '../../Tool.js'
import { validateWorkspacePathInsideAllowedRoots, workspaceReadSearchDecision } from './allowedRootPolicy.js'
import {
  isWorkspaceInputRecord,
  normalizeWorkspaceInputFromContext,
} from './inputNormalization.js'
import {
  workspaceBashDocumentFormatValidation,
  workspaceDocumentFormatPathValidation,
} from './documentFormatGuards.js'
import { WORKSPACE_BASH_TOOL_NAME } from './toolNames.js'

export type WorkspaceToolSpec = {
  readonly name: string
  readonly source: () => Tool
  readonly searchHint: string
  readonly alwaysLoad?: boolean
  readonly shouldDefer?: boolean
  readonly blocksDocumentFormats?: boolean
  readonly supportsUserFolderHints?: boolean
  readonly enforcesAllowedRoots?: boolean
  readonly readSearchDefaultAllowed?: boolean
}

function migrateToolText(text: string): string {
  return text
    .replace(/\bGlob\b/g, 'workspace_glob')
    .replace(/\bGrep\b/g, 'workspace_grep')
    .replace(/\bRead\b/g, 'workspace_read')
    .replace(/\bWrite\b/g, 'workspace_write')
    .replace(/\bEdit\b/g, 'workspace_edit')
    .replace(/\bBash\b/g, WORKSPACE_BASH_TOOL_NAME)
}

function lazyWorkspaceToolOptionals(
  tool: Tool,
  source: () => Tool,
): Tool {
  Object.defineProperties(tool, {
    backfillObservableInput: { get: () => source().backfillObservableInput },
    extractSearchText: { get: () => source().extractSearchText },
    getToolUseSummary: { get: () => source().getToolUseSummary },
    inputJSONSchema: { get: () => source().inputJSONSchema },
    inputsEquivalent: { get: () => source().inputsEquivalent },
    isLsp: { get: () => source().isLsp },
    isMcp: { get: () => source().isMcp },
    isOpenWorld: { get: () => source().isOpenWorld },
    isResultTruncated: { get: () => source().isResultTruncated },
    isTransparentWrapper: { get: () => source().isTransparentWrapper },
    mcpInfo: { get: () => source().mcpInfo },
    outputSchema: { get: () => source().outputSchema },
    preparePermissionMatcher: { get: () => source().preparePermissionMatcher },
    renderGroupedToolUse: { get: () => source().renderGroupedToolUse },
    renderToolResultMessage: { get: () => source().renderToolResultMessage },
    renderToolUseErrorMessage: { get: () => source().renderToolUseErrorMessage },
    renderToolUseProgressMessage: {
      get: () => source().renderToolUseProgressMessage,
    },
    renderToolUseQueuedMessage: { get: () => source().renderToolUseQueuedMessage },
    renderToolUseRejectedMessage: {
      get: () => source().renderToolUseRejectedMessage,
    },
    renderToolUseTag: { get: () => source().renderToolUseTag },
    requiresUserInteraction: { get: () => source().requiresUserInteraction },
    strict: { get: () => source().strict },
    userFacingNameBackgroundColor: {
      get: () => source().userFacingNameBackgroundColor,
    },
  })
  return tool
}

export function buildWorkspaceTool(spec: WorkspaceToolSpec): Tool {
  const source = spec.source
  const workspaceTool: Tool = {
    name: spec.name,
    aliases: [],
    searchHint: spec.searchHint,
    alwaysLoad: spec.alwaysLoad,
    shouldDefer: spec.alwaysLoad ? false : spec.shouldDefer ?? true,
    get maxResultSizeChars() {
      return source().maxResultSizeChars
    },
    get inputSchema() {
      return source().inputSchema
    },
    call(input, context, canUseTool, parentMessage, onProgress) {
      const normalizedInput = normalizeWorkspaceInputFromContext(
        spec,
        input,
        context,
      )
      return source().call(
        normalizedInput,
        context,
        canUseTool,
        parentMessage,
        onProgress,
      )
    },
    async description(input, options) {
      const base = await source().description(input, options)
      return `${migrateToolText(base)}

UMMAYA workspace adapter: this tool delegates to the Claude Code local workspace implementation under a namespaced tool id. Use the document primitive for HWPX, HWP, DOCX, PDF, XLSX, and PPTX content edits.`
    },
    async prompt(options) {
      const base = await source().prompt(options)
      return `${migrateToolText(base)}

UMMAYA workspace boundary:
- This adapter is for local workspace text/file access.
- Use document for HWPX, HWP, DOCX, PDF, XLSX, and PPTX reading, editing, rendering, diffing, or saving.
- Do not call raw Claude Code tool names; use the workspace_* adapter names exposed in this session.`
    },
    async validateInput(input, context) {
      const sourceTool = source()
      normalizeWorkspaceInputFromContext(spec, input, context)
      if (spec.blocksDocumentFormats) {
        const documentValidation = workspaceDocumentFormatPathValidation(
          spec.name,
          input,
        )
        if (documentValidation !== null) return documentValidation
      }
      const workspacePath =
        typeof sourceTool.getPath === 'function' && isWorkspaceInputRecord(input)
          ? sourceTool.getPath(input)
          : undefined
      if (spec.enforcesAllowedRoots && workspacePath) {
        const workspaceValidation = validateWorkspacePathInsideAllowedRoots(
          workspacePath,
          context,
        )
        if (!workspaceValidation.result) return workspaceValidation
      }
      if (spec.name === WORKSPACE_BASH_TOOL_NAME) {
        const bashValidation = workspaceBashDocumentFormatValidation(
          sourceTool,
          input,
        )
        if (bashValidation !== null) return bashValidation
      }
      return sourceTool.validateInput
        ? sourceTool.validateInput(input, context)
        : { result: true }
    },
    async checkPermissions(input, context) {
      const sourceTool = source()
      const normalizedInput = normalizeWorkspaceInputFromContext(
        spec,
        input,
        context,
      )
      if (
        spec.readSearchDefaultAllowed &&
        typeof sourceTool.getPath === 'function'
      ) {
        if (!isWorkspaceInputRecord(normalizedInput)) {
          return sourceTool.checkPermissions(normalizedInput, context)
        }
        return workspaceReadSearchDecision(
          sourceTool.getPath(normalizedInput),
          normalizedInput,
          context,
        )
      }
      return sourceTool.checkPermissions(normalizedInput, context)
    },
    isConcurrencySafe(input) {
      return source().isConcurrencySafe(input)
    },
    isDestructive(input) {
      return source().isDestructive?.(input) ?? false
    },
    isEnabled() {
      return source().isEnabled()
    },
    isReadOnly(input) {
      return source().isReadOnly(input)
    },
    interruptBehavior() {
      return source().interruptBehavior?.() ?? 'block'
    },
    isSearchOrReadCommand(input) {
      return (
        source().isSearchOrReadCommand?.(input) ?? {
          isSearch: false,
          isRead: false,
          isList: false,
        }
      )
    },
    mapToolResultToToolResultBlockParam(content, toolUseID) {
      return source().mapToolResultToToolResultBlockParam(content, toolUseID)
    },
    renderToolUseMessage(input, options) {
      return source().renderToolUseMessage(input, options)
    },
    toAutoClassifierInput(input) {
      return source().toAutoClassifierInput(input)
    },
    userFacingName() {
      return spec.name
    },
    getActivityDescription(input) {
      const activity = source().getActivityDescription?.(input)
      return activity ? migrateToolText(activity) : spec.name
    },
  }
  Object.defineProperty(workspaceTool, 'getPath', {
    get: () => source().getPath,
  })
  return lazyWorkspaceToolOptionals(workspaceTool, source)
}
