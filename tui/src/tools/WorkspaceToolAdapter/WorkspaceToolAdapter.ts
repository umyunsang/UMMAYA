import { homedir } from 'node:os'
import { join } from 'node:path'
import { buildTool, type Tool, type ToolUseContext, type ValidationResult } from '../../Tool.js'
import { BashTool } from '../BashTool/BashTool.js'
import { FileEditTool } from '../FileEditTool/FileEditTool.js'
import { FileReadTool } from '../FileReadTool/FileReadTool.js'
import { FileWriteTool } from '../FileWriteTool/FileWriteTool.js'
import { GlobTool } from '../GlobTool/GlobTool.js'
import { GrepTool } from '../GrepTool/GrepTool.js'

export const WORKSPACE_GLOB_TOOL_NAME = 'workspace_glob'
export const WORKSPACE_GREP_TOOL_NAME = 'workspace_grep'
export const WORKSPACE_READ_TOOL_NAME = 'workspace_read'
export const WORKSPACE_WRITE_TOOL_NAME = 'workspace_write'
export const WORKSPACE_EDIT_TOOL_NAME = 'workspace_edit'
export const WORKSPACE_BASH_TOOL_NAME = 'workspace_bash'

const DOCUMENT_FORMAT_PATH_RE = /\.(?:hwp|hwpx|docx|pdf|xlsx|pptx)$/iu
const DOCUMENT_FORMAT_COMMAND_RE = /\.(?:hwp|hwpx|docx|pdf|xlsx|pptx)(?=$|[\s"'`;|&<>])/iu
const DOWNLOADS_FOLDER_RE = /\bdownloads?\b|다운로드/iu
const DOCUMENT_FORMAT_HINT_RE = /\b(?:hwp|hwpx|docx|pdf|xlsx|pptx)\b|\.(?:hwp|hwpx|docx|pdf|xlsx|pptx)\b/iu
const HWPX_DOCUMENT_HINT_RE = /\bhwpx\b|\.hwpx\b/iu
const MALFORMED_GLOB_EXTENSION_RE = /\s|\*\.hwp\s+\*\.hwpx|\*\.hwpx\s+\*\.hwp/iu

type WorkspaceToolSpec = {
  name: string
  source: Tool
  searchHint: string
  alwaysLoad?: boolean
  shouldDefer?: boolean
  blocksDocumentFormats?: boolean
  supportsUserFolderHints?: boolean
}

function documentPathFromInput(input: unknown): string | undefined {
  if (typeof input !== 'object' || input === null) return undefined
  const record = input as Record<string, unknown>
  return typeof record.file_path === 'string' ? record.file_path : undefined
}

function migrateToolText(text: string): string {
  return text
    .replace(/\bGlob\b/g, WORKSPACE_GLOB_TOOL_NAME)
    .replace(/\bGrep\b/g, WORKSPACE_GREP_TOOL_NAME)
    .replace(/\bRead\b/g, WORKSPACE_READ_TOOL_NAME)
    .replace(/\bWrite\b/g, WORKSPACE_WRITE_TOOL_NAME)
    .replace(/\bEdit\b/g, WORKSPACE_EDIT_TOOL_NAME)
    .replace(/\bBash\b/g, WORKSPACE_BASH_TOOL_NAME)
}

function textFromContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map(block => {
      if (typeof block === 'string') return block
      if (typeof block !== 'object' || block === null) return ''
      const record = block as Record<string, unknown>
      return typeof record.text === 'string' ? record.text : ''
    })
    .filter(Boolean)
    .join('\n')
}

function latestUserText(context: ToolUseContext): string {
  for (let index = context.messages.length - 1; index >= 0; index -= 1) {
    const message = context.messages[index]
    if (typeof message !== 'object' || message === null) continue
    const record = message as Record<string, unknown>
    const nested = record.message
    if (typeof nested !== 'object' || nested === null) continue
    const nestedRecord = nested as Record<string, unknown>
    if (nestedRecord.role !== 'user') continue
    const text = textFromContent(nestedRecord.content)
    if (text.trim()) return text
  }
  return ''
}

function userFolderPath(text: string): string | undefined {
  return DOWNLOADS_FOLDER_RE.test(text) ? join(homedir(), 'Downloads') : undefined
}

function normalizedDocumentGlobPattern(text: string, pattern: unknown): string | undefined {
  if (typeof pattern !== 'string') return undefined
  if (!DOCUMENT_FORMAT_HINT_RE.test(text)) return undefined
  if (pattern.startsWith('**/') && !pattern.startsWith('**/*')) {
    const basenamePattern = pattern.slice('**/'.length)
    if (
      !basenamePattern.includes('/') &&
      /\.(?:hwp|hwpx|docx|pdf|xlsx|pptx)$/iu.test(basenamePattern)
    ) {
      return `**/*${basenamePattern}`
    }
  }
  if (!HWPX_DOCUMENT_HINT_RE.test(text)) return undefined
  if (!MALFORMED_GLOB_EXTENSION_RE.test(pattern)) return undefined
  return '**/*.hwpx'
}

function normalizeWorkspaceInputFromContext(
  spec: WorkspaceToolSpec,
  input: unknown,
  context: ToolUseContext,
): unknown {
  if (!spec.supportsUserFolderHints) return input
  if (typeof input !== 'object' || input === null) return input
  const record = input as Record<string, unknown>
  const userText = latestUserText(context)
  if (spec.name === WORKSPACE_GLOB_TOOL_NAME) {
    const normalizedPattern = normalizedDocumentGlobPattern(userText, record.pattern)
    if (normalizedPattern !== undefined) {
      record.pattern = normalizedPattern
    }
  }
  if (typeof record.path === 'string' && record.path.trim()) return input
  const inferredPath = userFolderPath(userText)
  if (inferredPath !== undefined) {
    record.path = inferredPath
  }
  return input
}

function buildWorkspaceTool(spec: WorkspaceToolSpec): Tool {
  const { source } = spec
  return buildTool({
    ...source,
    name: spec.name,
    aliases: [],
    searchHint: spec.searchHint,
    alwaysLoad: spec.alwaysLoad,
    shouldDefer: spec.alwaysLoad ? false : spec.shouldDefer ?? true,
    async description(input, options) {
      const base = await source.description(input, options)
      return `${migrateToolText(base)}

UMMAYA workspace adapter: this tool delegates to the Claude Code local workspace implementation under a namespaced tool id. Use the document primitive for HWPX, HWP, DOCX, PDF, XLSX, and PPTX content edits.`
    },
    async prompt(options) {
      const base = await source.prompt(options)
      return `${migrateToolText(base)}

UMMAYA workspace boundary:
- This adapter is for local workspace text/file access.
- Use document for HWPX, HWP, DOCX, PDF, XLSX, and PPTX reading, editing, rendering, diffing, or saving.
- Do not call raw Claude Code tool names; use the workspace_* adapter names exposed in this session.`
    },
    async validateInput(input, context): Promise<ValidationResult> {
      normalizeWorkspaceInputFromContext(spec, input, context as ToolUseContext)
      const filePath = documentPathFromInput(input)
      if (spec.blocksDocumentFormats && filePath && DOCUMENT_FORMAT_PATH_RE.test(filePath)) {
        return {
          result: false,
          message: `Document formats must be edited through the document primitive, not ${spec.name}.`,
          errorCode: 1,
        }
      }
      if (spec.name === WORKSPACE_BASH_TOOL_NAME) {
        const record =
          typeof input === 'object' && input !== null
            ? (input as Record<string, unknown>)
            : {}
        if (record.dangerouslyDisableSandbox === true) {
          return {
            result: false,
            message:
              'workspace_bash does not allow dangerouslyDisableSandbox. Use the normal permission and sandbox boundary.',
            errorCode: 2,
          }
        }
        const command = typeof record.command === 'string' ? record.command : ''
        if (
          DOCUMENT_FORMAT_COMMAND_RE.test(command) &&
          !source.isReadOnly(input)
        ) {
          return {
            result: false,
            message:
              'Document formats must be edited through the document primitive, not workspace_bash.',
            errorCode: 1,
          }
        }
      }
      return source.validateInput
        ? source.validateInput(input, context as ToolUseContext)
        : { result: true }
    },
    async checkPermissions(input, context) {
      const normalizedInput = normalizeWorkspaceInputFromContext(
        spec,
        input,
        context,
      )
      return source.checkPermissions(normalizedInput, context)
    },
    async call(input, context, canUseTool, parentMessage, onProgress) {
      const normalizedInput = normalizeWorkspaceInputFromContext(
        spec,
        input,
        context,
      )
      return source.call(
        normalizedInput,
        context,
        canUseTool,
        parentMessage,
        onProgress,
      )
    },
    userFacingName() {
      return spec.name
    },
    getActivityDescription(input) {
      const activity = source.getActivityDescription?.(input)
      return activity ? migrateToolText(activity) : spec.name
    },
  }) as Tool
}

export function getWorkspaceTools(): readonly Tool[] {
  return [
    buildWorkspaceTool({
      name: WORKSPACE_GLOB_TOOL_NAME,
      source: GlobTool,
      searchHint: 'find local files by name pattern',
      alwaysLoad: true,
      supportsUserFolderHints: true,
    }),
    buildWorkspaceTool({
      name: WORKSPACE_GREP_TOOL_NAME,
      source: GrepTool,
      searchHint: 'search local file contents',
      supportsUserFolderHints: true,
    }),
    buildWorkspaceTool({
      name: WORKSPACE_READ_TOOL_NAME,
      source: FileReadTool,
      searchHint: 'read local text files',
    }),
    buildWorkspaceTool({
      name: WORKSPACE_WRITE_TOOL_NAME,
      source: FileWriteTool,
      searchHint: 'create or overwrite local text files',
      blocksDocumentFormats: true,
    }),
    buildWorkspaceTool({
      name: WORKSPACE_EDIT_TOOL_NAME,
      source: FileEditTool,
      searchHint: 'modify local text files in place',
      blocksDocumentFormats: true,
    }),
    buildWorkspaceTool({
      name: WORKSPACE_BASH_TOOL_NAME,
      source: BashTool,
      searchHint: 'run local shell commands with permission',
    }),
  ]
}
