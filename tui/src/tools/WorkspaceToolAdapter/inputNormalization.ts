import { homedir } from 'node:os'
import { join } from 'node:path'
import type { ToolUseContext } from '../../Tool.js'
import { WORKSPACE_GLOB_TOOL_NAME } from './toolNames.js'

const DOCUMENT_FORMAT_HINT_RE =
  /\b(?:hwp|hwpx|docx|pdf|xlsx|pptx)\b|\.(?:hwp|hwpx|docx|pdf|xlsx|pptx)\b/iu
const HWPX_DOCUMENT_HINT_RE = /\bhwpx\b|\.hwpx\b/iu
const MALFORMED_GLOB_EXTENSION_RE =
  /\s|\*\.hwp\s+\*\.hwpx|\*\.hwpx\s+\*\.hwp/iu
const DOWNLOADS_FOLDER_RE = /\bdownloads?\b|다운로드/iu

type WorkspaceInputNormalizationSpec = {
  readonly name: string
  readonly supportsUserFolderHints?: boolean
}

export function isWorkspaceInputRecord(
  input: unknown,
): input is Record<string, unknown> {
  return typeof input === 'object' && input !== null && !Array.isArray(input)
}

function textFromContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map(block => {
      if (typeof block === 'string') return block
      if (!isWorkspaceInputRecord(block)) return ''
      return typeof block.text === 'string' ? block.text : ''
    })
    .filter(Boolean)
    .join('\n')
}

export function latestUserTextFromWorkspaceContext(
  context: ToolUseContext,
): string {
  for (let index = context.messages.length - 1; index >= 0; index -= 1) {
    const message = context.messages[index]
    if (!isWorkspaceInputRecord(message)) continue
    const nested = message.message
    if (!isWorkspaceInputRecord(nested)) continue
    if (nested.role !== 'user') continue
    const text = textFromContent(nested.content)
    if (text.trim()) return text
  }
  return ''
}

export function userTextMentionsDownloads(text: string): boolean {
  return DOWNLOADS_FOLDER_RE.test(text)
}

export function inferredDownloadsPath(text: string): string | undefined {
  return userTextMentionsDownloads(text)
    ? join(homedir(), 'Downloads')
    : undefined
}

function normalizedDocumentGlobPattern(
  text: string,
  pattern: unknown,
): string | undefined {
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

export function normalizeWorkspaceInputFromContext(
  spec: WorkspaceInputNormalizationSpec,
  input: unknown,
  context: ToolUseContext,
): unknown {
  if (!spec.supportsUserFolderHints) return input
  if (!isWorkspaceInputRecord(input)) return input
  const userText = latestUserTextFromWorkspaceContext(context)
  if (spec.name === WORKSPACE_GLOB_TOOL_NAME) {
    const normalizedPattern = normalizedDocumentGlobPattern(
      userText,
      input.pattern,
    )
    if (normalizedPattern !== undefined) {
      input.pattern = normalizedPattern
    }
  }
  if (typeof input.path === 'string' && input.path.trim()) return input
  const inferredPath = inferredDownloadsPath(userText)
  if (inferredPath !== undefined) {
    input.path = inferredPath
  }
  return input
}
