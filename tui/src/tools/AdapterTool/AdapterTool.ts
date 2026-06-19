import { z } from 'zod/v4'
import { randomUUID } from 'node:crypto'
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { basename, join } from 'node:path'
import {
  buildTool,
  type Tool,
  type ToolDef,
  type ToolInputJSONSchema,
  type Tools,
} from '../../Tool.js'
import {
  listAdapters,
  resolveAdapter,
  type AdapterManifestEntry,
} from '../../services/api/adapterManifest.js'
import { getOrCreateUmmayaBridge } from '../../ipc/bridgeSingleton.js'
import { getOrCreatePendingCallRegistry } from '../../ipc/pendingCallSingleton.js'
import { dispatchPrimitive } from '../_shared/dispatchPrimitive.js'
import {
  applyDocumentVisualRenderGateToOutput,
  extractDocumentToolResultPayload,
  isDocumentVisualRenderFailedOutput,
  renderDocumentToolResultIfPresent,
} from '../_shared/documentToolResultRender.js'
import { LookupPrimitive } from '../LookupPrimitive/LookupPrimitive.js'
import { ResolveLocationPrimitive } from '../ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { SubmitPrimitive } from '../SubmitPrimitive/SubmitPrimitive.js'
import { VerifyPrimitive } from '../VerifyPrimitive/VerifyPrimitive.js'
import { DocumentPrimitive } from '../DocumentPrimitive/DocumentPrimitive.js'
import { resolveDocumentPrimitiveTimeoutMs } from '../_shared/documentPrimitiveTimeout.js'

type AdapterPrimitive = 'find' | 'locate' | 'send' | 'check' | 'document'

type InputSchema = z.ZodType<{ [key: string]: unknown }>

const ROOT_PRIMITIVE_TOOL_NAMES = new Set([
  'locate',
  'find',
  'check',
  'send',
  'document',
])
const DOCUMENT_TOOL_NAMES = new Set([
  'document',
  'document_inspect',
  'document_extract',
  'document_form_schema',
  'document_copy_for_edit',
  'document_apply_fill',
  'document_apply_style',
  'document_render',
  'document_validate_public_form',
  'document_save',
])
const DOCUMENT_MUTATION_TOOL_NAMES = new Set([
  'document_apply_fill',
  'document_apply_style',
])
const DOCUMENT_ARTIFACT_FOLLOWUP_TOOL_NAMES = new Set([
  'document_apply_fill',
  'document_apply_style',
  'document_render',
  'document_validate_public_form',
  'document_save',
])
// Purely mechanical pipeline steps that carry no user-meaningful change — only
// these are hidden on success. Substantive mutations (apply_fill / apply_style)
// now render their inline structural diff immediately (per-mutation trigger),
// the same way Claude Code shows a diff the moment an edit lands. See
// specs/2802-public-doc-harness/deep-research-migration-document-render.md.
const MECHANICAL_DOCUMENT_TOOL_NAMES = new Set(['document_copy_for_edit'])
const SAFE_DOCUMENT_ARTIFACT_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/u
const EXPLICIT_DOCUMENT_ARTIFACT_MARKER_RE =
  /(?:^|[\s"'`(])(?:artifact_id|artifact\s*id|artifact|아티팩트)\s*[:=]?\s*([A-Za-z0-9][A-Za-z0-9_.-]{0,127})(?=$|[^A-Za-z0-9_.-])/iu
const EXPLICIT_DOCUMENT_ARTIFACT_PREFIX_RE =
  /(?:^|[\s"'`(])((?:source|working|derivative|render|export|viewport)-[A-Za-z0-9][A-Za-z0-9_.-]{0,127})(?=$|[^A-Za-z0-9_.-])/u
const DOCUMENT_FORMAT_RE = /\b(?:hwpx|hwp|docx|pdf|xlsx|pptx)\b/iu
const DOWNLOADS_FOLDER_PATH_RE = /(?:^|[\\/])Downloads$/u
const DOWNLOADS_PATH_SEGMENT_RE = /(?:^|[\\/])Downloads[\\/](?<tail>.+)$/iu
const DOCUMENT_EXTENSION_RE = /\.(?:hwpx|hwp|docx|pdf|xlsx|pptx)$/iu
const DOCUMENT_EXTENSION_TRAILING_PUNCT_RE =
  /(\.(?:hwpx|hwp|docx|pdf|xlsx|pptx))[.。．]+$/iu
const EXPLICIT_LOCAL_DOCUMENT_PATH_RE =
  /(?:^|[\s"'`(])(?<path>(?:~|\/|\.{1,2}\/|[A-Za-z]:\\)[^\n\r"'`]*?\.(?:hwpx|hwp|docx|pdf|xlsx|pptx))(?=$|[\s"'`),，。]|[가-힣])/giu
const HWPX_TEXT_TARGET_ALIAS_RE =
  /^\/?hwp(?:x)?[-_/]text(?:[-_](?<indexA>\d+)|\[(?<indexB>\d+)\])(?:\/text\(\))?$/iu
const HWPX_TEXT_TARGET_RE = /^\/hwpx\/text\[\d+\]$/u
const HWPX_BLOCK_TABLE_CELL_TARGET_RE =
  /^\/hwpx\/\[(?<tableId>hwpx-table-\d{3})\]\/cells\[(?<row>\d+)\]\[(?<column>\d+)\]$/u

const fallbackInputSchema = z.object({}).passthrough() as InputSchema

type JsonObject = Record<string, unknown>

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asJsonObject(value: unknown): JsonObject {
  return isJsonObject(value) ? value : {}
}

function documentToolUseAction(toolId: string): string {
  switch (toolId) {
    case 'document':
      return 'Prepare document workflow'
    case 'document_inspect':
      return 'Inspect document form'
    case 'document_extract':
      return 'Read document content'
    case 'document_form_schema':
      return 'Map document fields'
    case 'document_apply_fill':
      return 'Fill document fields'
    case 'document_apply_style':
      return 'Apply document formatting'
    case 'document_render':
      return 'Render document diff'
    case 'document_validate_public_form':
      return 'Validate public-form rules'
    case 'document_save':
      return 'Save document'
    default:
      return 'Process document'
  }
}

function documentToolUseTarget(input: Record<string, unknown>): string | undefined {
  const document = asJsonObject(input.document)
  const path =
    typeof document.path === 'string'
      ? document.path
      : typeof input.path === 'string'
        ? input.path
        : undefined
  if (path !== undefined && path.trim()) {
    return basename(path)
  }
  if (
    typeof document.artifact_id === 'string' ||
    typeof input.artifact_id === 'string'
  ) {
    return 'current document'
  }
  return undefined
}

function renderDocumentToolUseMessage(
  toolId: string,
  input: Record<string, unknown>,
): string | null {
  if (MECHANICAL_DOCUMENT_TOOL_NAMES.has(toolId)) return null
  const action = documentToolUseAction(toolId)
  const target = documentToolUseTarget(input)
  return target === undefined ? action : `${action}: ${target}`
}

function messageInnerRecord(message: unknown): JsonObject {
  return asJsonObject(asJsonObject(message).message)
}

function messageRole(message: unknown): string | undefined {
  const inner = messageInnerRecord(message)
  const outer = asJsonObject(message)
  if (typeof inner.role === 'string') return inner.role
  if (typeof outer.role === 'string') return outer.role
  return typeof outer.type === 'string' ? outer.type : undefined
}

function messageContent(message: unknown): unknown {
  const inner = messageInnerRecord(message)
  return inner.content ?? asJsonObject(message).content
}

function isToolResultContent(content: unknown): boolean {
  if (!Array.isArray(content)) return false
  return content.some(block => asJsonObject(block).type === 'tool_result')
}

function textFromMessageContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map(block => {
      if (typeof block === 'string') return block
      const record = asJsonObject(block)
      if (record.type === 'tool_result') return ''
      if (typeof record.text === 'string') return record.text
      if (typeof record.content === 'string') return record.content
      return ''
    })
    .filter(Boolean)
    .join('\n')
}

function latestPlainUserText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const content = messageContent(messages[idx])
    if (messageRole(messages[idx]) !== 'user' || isToolResultContent(content)) {
      continue
    }
    const text = textFromMessageContent(content).trim()
    if (text) return text
  }
  return ''
}

function safeDocumentArtifactId(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const candidate = value.trim()
  return SAFE_DOCUMENT_ARTIFACT_ID_RE.test(candidate) ? candidate : undefined
}

function explicitDocumentArtifactIdFromText(text: string): string | undefined {
  const marked = EXPLICIT_DOCUMENT_ARTIFACT_MARKER_RE.exec(text)?.[1]
  const markedArtifactId = safeDocumentArtifactId(marked)
  if (markedArtifactId) return markedArtifactId
  const prefixed = EXPLICIT_DOCUMENT_ARTIFACT_PREFIX_RE.exec(text)?.[1]
  return safeDocumentArtifactId(prefixed)
}

function parseJsonObject(value: unknown): JsonObject | undefined {
  if (isJsonObject(value)) return value
  if (typeof value !== 'string' || !value.trim()) return undefined
  try {
    return asJsonObject(JSON.parse(value))
  } catch {
    return undefined
  }
}

function documentToolResultPayload(message: unknown): JsonObject | undefined {
  const directResult = asJsonObject(asJsonObject(message).toolUseResult).result
  if (isJsonObject(directResult)) return directResult

  const content = messageContent(message)
  if (!Array.isArray(content)) return undefined
  for (const block of content) {
    const record = asJsonObject(block)
    if (record.type !== 'tool_result') continue
    const parsed = parseJsonObject(record.content)
    const nestedResult = asJsonObject(parsed).result
    if (isJsonObject(nestedResult)) return nestedResult
  }
  return undefined
}

function latestDocumentArtifactRef(
  messages: readonly unknown[],
  options: {
    toolIds: ReadonlySet<string>
    artifactPrefix: string
  },
): string | undefined {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const payload = documentToolResultPayload(messages[idx])
    if (!payload) continue
    if (
      typeof payload.tool_id !== 'string' ||
      !options.toolIds.has(payload.tool_id)
    ) continue
    if (payload.status !== 'ok') continue
    const refs = Array.isArray(payload.artifact_refs) ? payload.artifact_refs : []
    for (let refIdx = refs.length - 1; refIdx >= 0; refIdx -= 1) {
      const ref = safeDocumentArtifactId(refs[refIdx])
      if (ref?.startsWith(options.artifactPrefix)) return ref
    }
  }
  return undefined
}

function latestMutableDocumentArtifactRef(messages: readonly unknown[]): string | undefined {
  return (
    latestDocumentArtifactRef(messages, {
      toolIds: DOCUMENT_MUTATION_TOOL_NAMES,
      artifactPrefix: 'derivative-',
    }) ??
    latestDocumentArtifactRef(messages, {
      toolIds: new Set([
        'document_copy_for_edit',
        'document_apply_fill',
        'document_apply_style',
      ]),
      artifactPrefix: 'working-',
    })
  )
}

function shouldHideSuccessfulIntermediateDocumentResult(output: unknown): boolean {
  const payload = extractDocumentToolResultPayload(output)
  return (
    payload !== null &&
    payload.status === 'ok' &&
    typeof payload.tool_id === 'string' &&
    MECHANICAL_DOCUMENT_TOOL_NAMES.has(payload.tool_id)
  )
}

function documentCorrelationId(value: unknown): string {
  return typeof value === 'string' && value.trim()
    ? value.trim()
    : `document-render-${randomUUID()}`
}

function documentFormatFromText(text: string): string | undefined {
  return DOCUMENT_FORMAT_RE.exec(text)?.[0]?.toLowerCase()
}

function documentFormatFromPath(path: string): string | undefined {
  const match = /\.(hwpx|hwp|docx|pdf|xlsx|pptx)$/iu.exec(path.trim())
  return match?.[1]?.toLowerCase()
}

function inferredDownloadsDocumentPath(text: string): string | undefined {
  if (!/(다운로드\s*폴더|downloads)/iu.test(text)) return undefined
  const formatMatch = DOCUMENT_FORMAT_RE.exec(text)
  const format = formatMatch?.[0]?.toLowerCase()
  if (!format || formatMatch === null) return undefined
  const beforeFormat = text.slice(0, formatMatch.index).trim()
  const nameMatch =
    /(?:다운로드\s*폴더|downloads)(?:에)?\s*(?:있는|의)?\s*(?<name>.+)$/iu.exec(
      beforeFormat,
    )
  const rawName = nameMatch?.groups?.name?.trim()
  if (!rawName) return undefined
  const fileName = rawName
    .replace(/[\\/:*?"<>|]/gu, ' ')
    .replace(/\s+/gu, ' ')
    .replace(/[.。．]+$/gu, '')
    .trim()
  if (!fileName) return undefined
  return join(homedir(), 'Downloads', `${fileName}.${format}`)
}

function isDownloadsFolderLikePath(value: unknown): boolean {
  if (typeof value !== 'string') return false
  const normalized = value
    .trim()
    .replace(/^['"`]+|['"`]+$/gu, '')
    .replace(/[\\/]+$/u, '')
    .replace(/\.$/u, '')
  return DOWNLOADS_FOLDER_PATH_RE.test(normalized)
}

function normalizeDownloadsDocumentPath(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const cleaned = value
    .trim()
    .replace(/^['"`]+|['"`]+$/gu, '')
    .replace(DOCUMENT_EXTENSION_TRAILING_PUNCT_RE, '$1')
  if (!cleaned) return undefined
  const downloadsPathMatch = DOWNLOADS_PATH_SEGMENT_RE.exec(cleaned)
  if (DOCUMENT_EXTENSION_RE.test(cleaned) && downloadsPathMatch) {
    const homeDownloads = `${homedir()}/Downloads/`
    if (cleaned.startsWith(homeDownloads)) return cleaned
    const tail = downloadsPathMatch.groups?.tail
    if (!tail || tail.includes('..')) return undefined
    const parts = tail.split(/[\\/]+/u).filter(Boolean)
    if (parts.length === 0) return undefined
    return join(homedir(), 'Downloads', ...parts)
  }
  return undefined
}

function cleanUserDocumentPath(value: string): string {
  return value
    .trim()
    .replace(/^['"`]+|['"`]+$/gu, '')
    .replace(DOCUMENT_EXTENSION_TRAILING_PUNCT_RE, '$1')
    .replace(/^~/u, homedir())
}

function existingUserDocumentPathsFromText(text: string): string[] {
  const paths: string[] = []
  for (const match of text.matchAll(EXPLICIT_LOCAL_DOCUMENT_PATH_RE)) {
    const rawPath = match.groups?.path
    if (typeof rawPath !== 'string') continue
    const candidate = cleanUserDocumentPath(rawPath)
    if (!candidate || !DOCUMENT_EXTENSION_RE.test(candidate)) continue
    if (!existsSync(candidate)) continue
    if (!paths.includes(candidate)) paths.push(candidate)
  }
  return paths
}

function normalizeExactUserDocumentPathInput(
  input: Record<string, unknown>,
  document: JsonObject,
  messages: readonly unknown[],
): Record<string, unknown> | undefined {
  if (document.artifact_id !== undefined) return undefined
  const userPaths = existingUserDocumentPathsFromText(latestPlainUserText(messages))
  if (userPaths.length !== 1) return undefined
  const lockedPath = userPaths[0]
  if (lockedPath === undefined) return undefined

  const currentPath =
    typeof document.path === 'string' ? cleanUserDocumentPath(document.path) : undefined
  if (currentPath !== undefined && existsSync(currentPath)) return undefined
  if (
    currentPath !== undefined &&
    basename(currentPath) !== basename(lockedPath)
  ) {
    return undefined
  }

  return {
    ...input,
    correlation_id: documentCorrelationId(input.correlation_id),
    document: {
      ...document,
      path: lockedPath,
      expected_format:
        documentFormatFromPath(lockedPath) ??
        document.expected_format ??
        input.expected_format ??
        documentFormatFromText(latestPlainUserText(messages)),
    },
  }
}

function normalizeDocumentInspectPathInput(
  toolId: string,
  input: Record<string, unknown>,
  document: JsonObject,
  messages: readonly unknown[],
): Record<string, unknown> | undefined {
  if (toolId !== 'document_inspect' && toolId !== 'document') return undefined
  const path = document.path ?? input.path
  const userText = latestPlainUserText(messages)
  const cleanedPath = typeof path === 'string' ? cleanUserDocumentPath(path) : undefined
  if (
    cleanedPath !== undefined &&
    DOCUMENT_EXTENSION_RE.test(cleanedPath) &&
    existsSync(cleanedPath)
  ) {
    return undefined
  }
  const normalizedDownloadsPath = normalizeDownloadsDocumentPath(path)
  const inferredPath = isDownloadsFolderLikePath(path)
    ? inferredDownloadsDocumentPath(userText)
    : undefined
  const inferredDownloadsPath = inferredDownloadsDocumentPath(userText)
  const shouldPreferUserTextDownloadsPath =
    normalizedDownloadsPath !== undefined &&
    inferredDownloadsPath !== undefined &&
    normalizedDownloadsPath !== inferredDownloadsPath
  const normalizedPath =
    (shouldPreferUserTextDownloadsPath ? inferredDownloadsPath : undefined) ??
    (normalizedDownloadsPath !== undefined && existsSync(normalizedDownloadsPath)
      ? normalizedDownloadsPath
      : undefined) ??
    (inferredPath !== undefined && existsSync(inferredPath) ? inferredPath : undefined) ??
    (inferredDownloadsPath !== undefined && existsSync(inferredDownloadsPath)
      ? inferredDownloadsPath
      : undefined) ??
    inferredDownloadsPath ??
    normalizedDownloadsPath ??
    inferredPath
  if (!normalizedPath) return undefined
  return {
    ...input,
    correlation_id: documentCorrelationId(input.correlation_id),
    document: {
      ...document,
      path: normalizedPath,
      expected_format:
        documentFormatFromPath(normalizedPath) ??
        document.expected_format ??
        input.expected_format ??
        documentFormatFromText(userText),
    },
  }
}

function normalizeDocumentPathExpectedFormatInput(
  input: Record<string, unknown>,
  document: JsonObject,
): Record<string, unknown> | undefined {
  if (document.artifact_id !== undefined) return undefined
  if (typeof document.path !== 'string') return undefined
  const normalizedPath = cleanUserDocumentPath(document.path)
  const pathFormat = documentFormatFromPath(normalizedPath)
  if (pathFormat === undefined) return undefined
  const currentFormat =
    typeof document.expected_format === 'string'
      ? document.expected_format.toLowerCase()
      : undefined
  if (currentFormat === pathFormat && document.path === normalizedPath) {
    return undefined
  }
  return {
    ...input,
    correlation_id: documentCorrelationId(input.correlation_id),
    document: {
      ...document,
      path: normalizedPath,
      expected_format: pathFormat,
    },
  }
}

function normalizeHwpxTextTargetPath(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const targetPath = value.trim()
  const match = HWPX_TEXT_TARGET_ALIAS_RE.exec(targetPath)
  const rawIndex = match?.groups?.indexA ?? match?.groups?.indexB
  if (!rawIndex) return undefined
  return `/hwpx/text[${Number(rawIndex)}]`
}

function latestDocumentFieldPaths(messages: readonly unknown[]): Set<string> | undefined {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const payload = documentToolResultPayload(messages[idx])
    const extraction = asJsonObject(payload?.extraction)
    const fields = Array.isArray(extraction.fields) ? extraction.fields : []
    const paths = new Set<string>()
    for (const field of fields) {
      const path = asJsonObject(field).path
      if (typeof path === 'string' && path.trim()) {
        paths.add(path.trim())
      }
    }
    if (paths.size > 0) return paths
  }
  return undefined
}

function latestDocumentTableCellFieldAliases(
  messages: readonly unknown[],
): Map<string, string> | undefined {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const payload = documentToolResultPayload(messages[idx])
    const extraction = asJsonObject(payload?.extraction)
    const tables = Array.isArray(extraction.tables) ? extraction.tables : []
    const aliases = new Map<string, string>()
    for (const tableValue of tables) {
      const table = asJsonObject(tableValue)
      const blockId = table.block_id
      const cells = Array.isArray(table.cells) ? table.cells : []
      if (typeof blockId !== 'string' || !blockId.trim()) continue
      for (const cellValue of cells) {
        const cell = asJsonObject(cellValue)
        const rowIndex = cell.row_index
        const columnIndex = cell.column_index
        const fieldPath = cell.field_path
        if (
          typeof rowIndex !== 'number' ||
          typeof columnIndex !== 'number' ||
          typeof fieldPath !== 'string' ||
          !fieldPath.trim()
        ) {
          continue
        }
        aliases.set(
          `/hwpx/[${blockId.trim()}]/cells[${rowIndex}][${columnIndex}]`,
          fieldPath.trim(),
        )
      }
    }
    if (aliases.size > 0) return aliases
  }
  return undefined
}

function normalizeHwpxTableCellTargetPath(
  value: unknown,
  aliases: ReadonlyMap<string, string> | undefined,
): string | undefined {
  if (typeof value !== 'string') return undefined
  const targetPath = value.trim()
  if (!HWPX_BLOCK_TABLE_CELL_TARGET_RE.test(targetPath)) return undefined
  return aliases?.get(targetPath)
}

function normalizeDocumentPatchTargetPaths(
  input: Record<string, unknown>,
  messages: readonly unknown[],
): Record<string, unknown> {
  const patches = input.patches
  if (!Array.isArray(patches)) return input

  const fieldPaths = latestDocumentFieldPaths(messages)
  const tableCellAliases = latestDocumentTableCellFieldAliases(messages)
  let changed = false
  const normalizedPatches = patches.flatMap(patch => {
    if (!isJsonObject(patch)) return patch
    const rawTargetPath =
      typeof patch.target_path === 'string' ? patch.target_path.trim() : patch.target_path
    const isHwpxTableCellTarget =
      typeof rawTargetPath === 'string' && HWPX_BLOCK_TABLE_CELL_TARGET_RE.test(rawTargetPath)
    const normalizedTargetPath =
      normalizeHwpxTextTargetPath(patch.target_path) ??
      normalizeHwpxTableCellTargetPath(patch.target_path, tableCellAliases)
    const targetPath =
      normalizedTargetPath ?? (
        typeof rawTargetPath === 'string' ? rawTargetPath : patch.target_path
      )
    if (
      isHwpxTableCellTarget &&
      tableCellAliases !== undefined &&
      normalizedTargetPath === undefined
    ) {
      changed = true
      return []
    }
    if (
      typeof targetPath === 'string' &&
      fieldPaths !== undefined &&
      HWPX_TEXT_TARGET_RE.test(targetPath) &&
      !fieldPaths.has(targetPath)
    ) {
      changed = true
      return []
    }
    if (
      normalizedTargetPath === undefined ||
      normalizedTargetPath === patch.target_path
    ) {
      return patch
    }
    changed = true
    return {
      ...patch,
      target_path: normalizedTargetPath,
    }
  })

  if (normalizedPatches.length === 0) return input
  return changed ? { ...input, patches: normalizedPatches } : input
}

function normalizeDocumentPrimitiveInstructionInput(
  toolId: string,
  input: Record<string, unknown>,
  messages: readonly unknown[],
): Record<string, unknown> {
  if (toolId !== 'document') return input
  if (Array.isArray(input.patches) && input.patches.length > 0) return input

  const userText = latestPlainUserText(messages)
  if (!userText) return input

  const instruction =
    typeof input.instruction === 'string' ? input.instruction.trim() : ''
  if (instruction.includes(userText)) return input

  return {
    ...input,
    instruction: instruction
      ? `${instruction}\n\nOriginal user request:\n${userText}`
      : userText,
  }
}

export function normalizeExplicitDocumentArtifactInput(
  toolId: string,
  input: Record<string, unknown>,
  messages: readonly unknown[],
): Record<string, unknown> {
  if (!DOCUMENT_TOOL_NAMES.has(toolId)) return input

  const instructionInput = normalizeDocumentPrimitiveInstructionInput(
    toolId,
    input,
    messages,
  )
  const normalizedPatchInput = normalizeDocumentPatchTargetPaths(
    instructionInput,
    messages,
  )
  const { artifact_id: topLevelArtifactIdRaw, ...withoutTopLevelArtifactId } =
    normalizedPatchInput
  const document = asJsonObject(normalizedPatchInput.document)
  const normalizedExactUserPathInput = normalizeExactUserDocumentPathInput(
    normalizedPatchInput,
    document,
    messages,
  )
  if (normalizedExactUserPathInput) return normalizedExactUserPathInput
  const normalizedInspectPathInput = normalizeDocumentInspectPathInput(
    toolId,
    normalizedPatchInput,
    document,
    messages,
  )
  if (normalizedInspectPathInput) return normalizedInspectPathInput
  const { path: _documentPath, ...documentWithoutPath } = document
  const existingDocumentArtifactId = safeDocumentArtifactId(document.artifact_id)
  const inputArtifactId =
    existingDocumentArtifactId ?? safeDocumentArtifactId(topLevelArtifactIdRaw)
  const hasExtractionArtifactId = inputArtifactId?.startsWith('document-intake-') === true

  if (DOCUMENT_ARTIFACT_FOLLOWUP_TOOL_NAMES.has(toolId)) {
    const artifactId = latestMutableDocumentArtifactRef(messages)
    if (
      artifactId &&
      (
        document.path !== undefined ||
        existingDocumentArtifactId?.startsWith('source-') ||
        hasExtractionArtifactId
      )
    ) {
      return {
        ...withoutTopLevelArtifactId,
        correlation_id: documentCorrelationId(input.correlation_id),
        document: {
          ...documentWithoutPath,
          artifact_id: artifactId,
        },
      }
    }
  }

  if (toolId === 'document_copy_for_edit' && hasExtractionArtifactId) {
    const sourceArtifactId = latestDocumentArtifactRef(messages, {
      toolIds: new Set(['document_inspect', 'document_extract', 'document_form_schema']),
      artifactPrefix: 'source-',
    })
    if (sourceArtifactId) {
      return {
        ...withoutTopLevelArtifactId,
        correlation_id: documentCorrelationId(input.correlation_id),
        document: {
          ...documentWithoutPath,
          artifact_id: sourceArtifactId,
        },
      }
    }
  }

  if (existingDocumentArtifactId) {
    return topLevelArtifactIdRaw === undefined
      ? { ...normalizedPatchInput, document: documentWithoutPath }
      : { ...withoutTopLevelArtifactId, document: documentWithoutPath }
  }

  if (toolId === 'document_copy_for_edit' && document.path !== undefined) {
    const sourceArtifactId = latestDocumentArtifactRef(messages, {
      toolIds: new Set(['document_inspect', 'document_extract', 'document_form_schema']),
      artifactPrefix: 'source-',
    })
    if (sourceArtifactId) {
      return {
        ...withoutTopLevelArtifactId,
        correlation_id: documentCorrelationId(input.correlation_id),
        document: {
          ...documentWithoutPath,
          artifact_id: sourceArtifactId,
        },
      }
    }
  }

  const topLevelArtifactId = safeDocumentArtifactId(topLevelArtifactIdRaw)
  const currentTextArtifactId = explicitDocumentArtifactIdFromText(
    latestPlainUserText(messages),
  )
  const artifactId = topLevelArtifactId ?? currentTextArtifactId
  if (!artifactId) {
    return (
      normalizeDocumentPathExpectedFormatInput(normalizedPatchInput, document) ??
      normalizedPatchInput
    )
  }

  return {
    ...withoutTopLevelArtifactId,
    correlation_id: documentCorrelationId(input.correlation_id),
    document: {
      ...documentWithoutPath,
      artifact_id: artifactId,
    },
  }
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function schemaDescription(schema: JsonObject): string | undefined {
  return typeof schema.description === 'string' && schema.description.trim()
    ? schema.description
    : undefined
}

function applyJsonSchemaMetadata(schema: z.ZodTypeAny, jsonSchema: JsonObject): z.ZodTypeAny {
  let result = schema
  const description = schemaDescription(jsonSchema)
  if (description) {
    result = result.describe(description)
  }
  if (Object.prototype.hasOwnProperty.call(jsonSchema, 'default')) {
    result = result.default(jsonSchema.default)
  }
  return result
}

function zodUnion(schemas: z.ZodTypeAny[]): z.ZodTypeAny {
  if (schemas.length === 0) {
    return z.unknown()
  }
  if (schemas.length === 1) {
    return schemas[0] ?? z.unknown()
  }
  return z.union(schemas as [z.ZodTypeAny, z.ZodTypeAny, ...z.ZodTypeAny[]])
}

function zodLiteralUnion(values: unknown[]): z.ZodTypeAny {
  const literals = values.map(value => z.literal(value as string | number | boolean | null))
  return zodUnion(literals)
}

function resolveRef(root: JsonObject, ref: string): JsonObject | undefined {
  if (!ref.startsWith('#/$defs/')) {
    return undefined
  }
  const defName = decodeURIComponent(ref.slice('#/$defs/'.length))
  const defs = asJsonObject(root.$defs)
  const resolved = defs[defName]
  return isJsonObject(resolved) ? resolved : undefined
}

function zodFromJsonSchema(schema: JsonObject, root: JsonObject): z.ZodTypeAny {
  if (typeof schema.$ref === 'string') {
    const resolved = resolveRef(root, schema.$ref)
    if (resolved) {
      return applyJsonSchemaMetadata(zodFromJsonSchema(resolved, root), schema)
    }
  }

  const variants = Array.isArray(schema.anyOf)
    ? schema.anyOf
    : Array.isArray(schema.oneOf)
      ? schema.oneOf
      : undefined
  if (variants) {
    const variantSchemas = variants
      .filter(isJsonObject)
      .map(variant => zodFromJsonSchema(variant, root))
    return applyJsonSchemaMetadata(zodUnion(variantSchemas), schema)
  }

  if (Array.isArray(schema.enum) && schema.enum.length > 0) {
    return applyJsonSchemaMetadata(zodLiteralUnion(schema.enum), schema)
  }

  if (Object.prototype.hasOwnProperty.call(schema, 'const')) {
    return applyJsonSchemaMetadata(
      z.literal(schema.const as string | number | boolean | null),
      schema,
    )
  }

  const typeValue = schema.type
  if (Array.isArray(typeValue)) {
    const nonNullTypes = typeValue.filter(item => item !== 'null')
    const nullable = nonNullTypes.length !== typeValue.length
    const typedSchemas = nonNullTypes.map(typeName =>
      zodFromJsonSchema({ ...schema, type: typeName }, root),
    )
    const base = zodUnion(typedSchemas)
    return applyJsonSchemaMetadata(nullable ? base.nullable() : base, schema)
  }

  switch (typeValue) {
    case 'string':
      return applyJsonSchemaMetadata(z.string(), schema)
    case 'integer':
      return applyJsonSchemaMetadata(z.number().int(), schema)
    case 'number':
      return applyJsonSchemaMetadata(z.number(), schema)
    case 'boolean':
      return applyJsonSchemaMetadata(z.boolean(), schema)
    case 'array': {
      const itemSchema = isJsonObject(schema.items)
        ? zodFromJsonSchema(schema.items, root)
        : z.unknown()
      return applyJsonSchemaMetadata(z.array(itemSchema), schema)
    }
    case 'object': {
      const properties = asJsonObject(schema.properties)
      const required = new Set(asStringArray(schema.required))
      const shape: Record<string, z.ZodTypeAny> = {}
      for (const [propertyName, propertySchemaRaw] of Object.entries(properties)) {
        const propertySchema = asJsonObject(propertySchemaRaw)
        let fieldSchema = zodFromJsonSchema(propertySchema, root)
        if (
          !required.has(propertyName) &&
          !Object.prototype.hasOwnProperty.call(propertySchema, 'default')
        ) {
          fieldSchema = fieldSchema.optional()
        }
        shape[propertyName] = fieldSchema
      }
      const objectSchema =
        schema.additionalProperties === false
          ? z.object(shape).strict()
          : z.object(shape).passthrough()
      return applyJsonSchemaMetadata(objectSchema, schema)
    }
    case 'null':
      return applyJsonSchemaMetadata(z.null(), schema)
    default:
      return applyJsonSchemaMetadata(z.unknown(), schema)
  }
}

function inputSchemaFor(entry: AdapterManifestEntry): InputSchema {
  const schema = asJsonObject(entry.input_schema_json)
  if (schema.type !== 'object') {
    return fallbackInputSchema
  }
  return zodFromJsonSchema(schema, schema) as InputSchema
}

function inputJSONSchemaFor(entry: AdapterManifestEntry): ToolInputJSONSchema | undefined {
  const schema = asJsonObject(entry.input_schema_json)
  if (schema.type !== 'object') {
    return undefined
  }
  return schema as ToolInputJSONSchema
}

function primitiveFor(entry: AdapterManifestEntry): AdapterPrimitive {
  return entry.primitive as AdapterPrimitive
}

function primitiveToolFor(primitive: AdapterPrimitive): Tool {
  switch (primitive) {
    case 'locate':
      return ResolveLocationPrimitive as Tool
    case 'send':
      return SubmitPrimitive as Tool
    case 'document':
      return DocumentPrimitive as Tool
    case 'check':
      return VerifyPrimitive as Tool
    case 'find':
    default:
      return LookupPrimitive as Tool
  }
}

function rootInputFor(entry: AdapterManifestEntry, input: Record<string, unknown>) {
  return {
    tool_id: entry.tool_id,
    params: input,
  }
}

function concreteAdapterCallInputFor(
  entry: AdapterManifestEntry,
  input: Record<string, unknown>,
): Record<string, unknown> {
  if (input.tool_id !== entry.tool_id) return input
  const params = input.params
  return isJsonObject(params) ? params : input
}

function validateAdapterContractInput(
  _toolId: string,
  _input: Record<string, unknown>,
) {
  return undefined
}

export function isAdapterToolName(name: string): boolean {
  return resolveAdapter(name) !== undefined
}

export function isRootPrimitiveToolName(name: string): boolean {
  return ROOT_PRIMITIVE_TOOL_NAMES.has(name)
}

export function getAdapterToolByName(name: string): Tool | undefined {
  const entry = resolveAdapter(name)
  return entry ? buildAdapterTool(entry) : undefined
}

export function getAdapterTools(): Tools {
  return listAdapters().map(buildAdapterTool)
}

function searchTokens(text: string): string[] {
  return text.toLowerCase().match(/[\p{L}\p{N}_-]+/gu) ?? []
}

const KOREAN_TRAILING_PARTICLES = [
  '으로부터',
  '에서부터',
  '에게서',
  '한테서',
  '까지',
  '부터',
  '으로',
  '에서',
  '에게',
  '한테',
  '처럼',
  '보다',
  '하고',
  '이며',
  '이고',
  '로',
  '와',
  '과',
  '은',
  '는',
  '이',
  '가',
  '을',
  '를',
  '의',
  '에',
  '도',
  '만',
] as const

const LOW_SIGNAL_DISCOVERY_TOKENS = new Set([
  '지금',
  '현재',
  '오늘',
  '내일',
  '모레',
  '이번',
  '근처',
  '주변',
  '어디',
  '어떻게',
  'now',
  'current',
  'today',
  'tomorrow',
  'latest',
  'nearby',
  'realtime',
  'real-time',
])

const KMA_LIFESTYLE_WEATHER_RE =
  /(날씨|현재\s*기상|실황|관측|예보|기온|습도|풍속|지금\s*비|비\s*(?:와|오|올|내리)|우산|강수|소나기|산책|퇴근|current\s+weather|forecast|rain|umbrella|precipitation|temperature)/iu
const HEALTHCARE_RE =
  /(응급|응급실|응급의료|야간\s*진료|야간진료|병원|의원|의료기관|진료\s*가능|\bemergency\b|\ber\b|\bhospital\b|\bclinic\b)/iu
const AIR_QUALITY_RE =
  /(미세먼지|초미세먼지|초미세|대기질|대기오염|공기질|마스크|pm\s*2\.?5|pm\s*10|air\s*korea|airkorea|air\s*quality|airquality)/iu
const KMA_ANALYSIS_RE =
  /(분석자료|이미\s*분석|고해상도\s*격자|객관분석|AWS\s*객관|지도\s*자료|일기도|분석일기도|비구름|바람\s*흐름|날씨\s*흐름|전국\s*날씨|synoptic|weather\s*chart|objective\s*analysis|high[-\s]?resolution|grid)/iu
const AIRPORT_AVIATION_RE =
  /(AMOS|METAR|SPECI|RVR|항공기상|공항기상|활주로|runway|aviation|비행기|항공편|비행편|이륙|착륙|결항|지연|운항|뜰\s*만|뜨나|뜰\s*수|flight|take\s*off|landing|delay|cancel)/iu
const POI_LOCATION_RE =
  /(근처|주변|주위|인근|가까운|우리\s*동네|여기|이\s*근처|현재\s*위치|내\s*위치|역|터미널|공항|캠퍼스|대학교|대학|해수욕장|시장|공원|랜드마크)/iu
const ADMIN_LOCATION_RE =
  /(?:[가-힣]{2,}(?:시|군|구|동|읍|면)\b|[가-힣0-9]{2,}(?<!으)(?:로|길)\b)/iu
const COORDINATE_PAIR_RE =
  /[+-]?\d{1,2}(?:\.\d+)?\s*,\s*[+-]?\d{2,3}(?:\.\d+)?/u
const PRIOR_LOCATION_CONTEXT_RE = /\[prior_location_context\]/u
const GOV24_RE = /(정부24|gov24|주민등록등본|등본|증명서|민원)/iu
const GOV24_READ_ONLY_RE = /(가능\s*여부|준비물|확인|조회|안내|알려)/iu
const GOV24_ACTION_RE = /(신청|진행|제출|접수|발급\s*신청|apply|submit|issue)/iu
const WELFARE_RE =
  /(생활비|기초생활|주거급여|긴급복지|저소득|차상위|복지혜택|지원금|진료비\s*바우처|출산휴가|임신|아동수당|첫만남이용권)/iu
const CIVIL_BIRTH_HANDOFF_RE =
  /(출생신고|아기가\s*태어|아동수당|첫만남이용권|피부양자\s*등록)/iu
const UTILITY_RE = /(전기|수도|도시가스|요금|자동이체|공과금|고지서|납부)/iu
const HOUSING_HANDOFF_RE =
  /(생애최초\s*주택구입|주택구입|대출|취득세|등기|전입)/iu
const CIVIL_DEATH_RE = /(사망|돌아가|장례|유족|상속|재산|국민연금)/iu

const LOCATION_TOOL_IDS = new Set([
  'locate',
  'kakao_address_search',
  'kakao_keyword_search',
  'kakao_coord_to_region',
  'juso_adm_cd_lookup',
  'sgis_adm_cd_lookup',
])
const KMA_LIFESTYLE_WEATHER_TOOL_IDS = new Set([
  'kma_current_observation',
  'kma_ultra_short_term_forecast',
  'kma_short_term_forecast',
  'kma_forecast_fetch',
])
const EMERGENCY_TOOL_IDS = new Set([
  'nmc_emergency_search',
  'nmc_aed_site_locate',
  'hira_hospital_search',
  'hira_medical_institution_detail',
])
const GOV24_LOOKUP_TOOL_IDS = new Set(['mock_lookup_module_gov24_certificate'])
const GOV24_ACTION_TOOL_IDS = new Set([
  'mock_lookup_module_gov24_certificate',
  'mock_verify_module_simple_auth',
  'mock_verify_ganpyeon_injeung',
  'mock_verify_mobile_id',
  'mock_submit_module_gov24_minwon',
])
const WELFARE_TOOL_IDS = new Set([
  'mohw_welfare_eligibility_search',
  'mock_welfare_application_submit_v1',
])
const UTILITY_TOOL_IDS = new Set([
  'kepco_contract_power_usage',
  'mock_kftc_opengiro_bill_send_v1',
  'mock_kftc_opengiro_payment_send_v1',
])
const CIVIL_DEATH_TOOL_IDS = new Set([
  'bfc_funeral_area_fee',
  'reb_real_estate_stat_table',
  'mohw_welfare_eligibility_search',
])

type ProviderRoutingIntent = {
  readonly hasCoordinateLocationAnchor: boolean
  readonly hasAdminLocationAnchor: boolean
  readonly hasPriorLocationContext: boolean
  readonly hasLocationAnchor: boolean
  readonly hasLifestyleWeather: boolean
  readonly hasEmergencyMedical: boolean
  readonly hasGov24ReadOnly: boolean
  readonly hasGov24Action: boolean
  readonly hasWelfare: boolean
  readonly hasCivilBirthHandoff: boolean
  readonly hasUtility: boolean
  readonly hasHousingHandoff: boolean
  readonly hasCivilDeath: boolean
}

type AdapterSelectionOptions = {
  readonly hasCurrentTurnLocationContext?: boolean
}

function hasHangul(text: string): boolean {
  return /\p{Script=Hangul}/u.test(text)
}

function extractProviderRoutingIntent(query: string): ProviderRoutingIntent {
  const hasEmergencyMedical = HEALTHCARE_RE.test(query)
  const hasGov24 = GOV24_RE.test(query)
  const hasGov24Action = hasGov24 && GOV24_ACTION_RE.test(query)
  const hasCoordinateLocationAnchor = COORDINATE_PAIR_RE.test(query)
  const hasAdminLocationAnchor = ADMIN_LOCATION_RE.test(query)
  const hasPoiLocationAnchor = POI_LOCATION_RE.test(query)
  const hasPriorLocationContext = PRIOR_LOCATION_CONTEXT_RE.test(query)
  return {
    hasCoordinateLocationAnchor,
    hasAdminLocationAnchor,
    hasPriorLocationContext,
    hasLocationAnchor:
      hasCoordinateLocationAnchor ||
      hasPoiLocationAnchor ||
      hasAdminLocationAnchor ||
      hasPriorLocationContext,
    hasLifestyleWeather:
      KMA_LIFESTYLE_WEATHER_RE.test(query) &&
      !hasEmergencyMedical &&
      !AIR_QUALITY_RE.test(query) &&
      !KMA_ANALYSIS_RE.test(query) &&
      !AIRPORT_AVIATION_RE.test(query),
    hasEmergencyMedical,
    hasGov24ReadOnly:
      hasGov24 &&
      GOV24_READ_ONLY_RE.test(query) &&
      !hasGov24Action,
    hasGov24Action,
    hasWelfare: WELFARE_RE.test(query),
    hasCivilBirthHandoff: CIVIL_BIRTH_HANDOFF_RE.test(query),
    hasUtility: UTILITY_RE.test(query),
    hasHousingHandoff: HOUSING_HANDOFF_RE.test(query),
    hasCivilDeath: CIVIL_DEATH_RE.test(query),
  }
}

function addSetValues(target: Set<string>, values: ReadonlySet<string>): void {
  for (const value of values) target.add(value)
}

function restrictiveToolIdsForIntent(
  intent: ProviderRoutingIntent,
  options: AdapterSelectionOptions = {},
): Set<string> | undefined {
  const allowed = new Set<string>()
  let restrictive = false

  if (intent.hasGov24ReadOnly) {
    restrictive = true
    addSetValues(allowed, GOV24_LOOKUP_TOOL_IDS)
  } else if (intent.hasGov24Action) {
    restrictive = true
    addSetValues(allowed, GOV24_ACTION_TOOL_IDS)
  }

  if (intent.hasLifestyleWeather) {
    restrictive = true
    if (
      options.hasCurrentTurnLocationContext !== true &&
      !intent.hasPriorLocationContext
    ) {
      addSetValues(allowed, LOCATION_TOOL_IDS)
    }
    addSetValues(allowed, KMA_LIFESTYLE_WEATHER_TOOL_IDS)
  }

  if (intent.hasEmergencyMedical) {
    restrictive = true
    if (
      options.hasCurrentTurnLocationContext !== true &&
      !intent.hasPriorLocationContext &&
      intent.hasLocationAnchor
    ) {
      addSetValues(allowed, LOCATION_TOOL_IDS)
    }
    if (
      options.hasCurrentTurnLocationContext === true ||
      intent.hasPriorLocationContext ||
      intent.hasCoordinateLocationAnchor ||
      intent.hasAdminLocationAnchor
    ) {
      addSetValues(allowed, EMERGENCY_TOOL_IDS)
    }
  }

  if (intent.hasWelfare) {
    restrictive = true
    addSetValues(allowed, WELFARE_TOOL_IDS)
  }

  if (intent.hasCivilBirthHandoff) {
    restrictive = true
  }

  if (intent.hasUtility) {
    restrictive = true
    addSetValues(allowed, UTILITY_TOOL_IDS)
  }

  if (intent.hasHousingHandoff) {
    restrictive = true
  }

  if (intent.hasCivilDeath) {
    restrictive = true
    addSetValues(allowed, CIVIL_DEATH_TOOL_IDS)
  }

  return restrictive ? allowed : undefined
}

function routingIntentBoostForTool(
  toolId: string,
  intent: ProviderRoutingIntent,
): number {
  if (intent.hasGov24ReadOnly && GOV24_LOOKUP_TOOL_IDS.has(toolId)) return 1200
  if (intent.hasGov24Action && GOV24_ACTION_TOOL_IDS.has(toolId)) return 1000
  if (intent.hasLifestyleWeather) {
    if (toolId === 'kakao_keyword_search') return 1100
    if (toolId === 'kakao_address_search') return 1000
    if (toolId === 'kma_current_observation') return 900
    if (toolId === 'kma_ultra_short_term_forecast') return 800
    if (toolId === 'kma_short_term_forecast') return 650
    if (LOCATION_TOOL_IDS.has(toolId)) return 260
  }
  if (intent.hasEmergencyMedical && intent.hasLocationAnchor) {
    if (toolId === 'nmc_emergency_search') return 1200
    if (toolId === 'nmc_aed_site_locate') return 950
    if (toolId === 'kakao_keyword_search') return 900
    if (toolId === 'kakao_address_search') return 800
    if (toolId === 'kakao_coord_to_region') return 500
    if (toolId === 'hira_hospital_search') return 250
    if (toolId === 'hira_medical_institution_detail') return 200
    if (LOCATION_TOOL_IDS.has(toolId)) return 300
  }
  if (intent.hasWelfare && WELFARE_TOOL_IDS.has(toolId)) return 1000
  if (intent.hasUtility && UTILITY_TOOL_IDS.has(toolId)) return 1000
  if (intent.hasCivilDeath && CIVIL_DEATH_TOOL_IDS.has(toolId)) return 1000
  return 0
}

function koreanParticleStrippedVariants(token: string): string[] {
  if (!hasHangul(token)) return []
  const variants: string[] = []
  let current = token
  for (let i = 0; i < 2; i += 1) {
    const nextSuffix = KOREAN_TRAILING_PARTICLES.find(
      suffix => current.length > suffix.length + 1 && current.endsWith(suffix),
    )
    if (!nextSuffix) break
    current = current.slice(0, -nextSuffix.length)
    variants.push(current)
  }
  return variants
}

function expandedTokensForText(text: string): Set<string> {
  const tokens = new Set<string>()
  for (const token of searchTokens(text)) {
    tokens.add(token)
    for (const variant of koreanParticleStrippedVariants(token)) {
      tokens.add(variant)
    }
  }
  return tokens
}

function expandedQueryTokens(query: string): Set<string> {
  return expandedTokensForText(query)
}

function isUsefulDiscoveryToken(token: string): boolean {
  const compact = token.replace(/[_-]/gu, '')
  if (compact.length === 0) return false
  if (LOW_SIGNAL_DISCOVERY_TOKENS.has(token)) return false
  if (hasHangul(compact)) return compact.length >= 2
  if (compact === 'er') return true
  return compact.length >= 3
}

function isSingleHangulPlaceSuffixMatch(
  fieldToken: string,
  queryToken: string,
): boolean {
  return (
    hasHangul(fieldToken) &&
    fieldToken.length === 1 &&
    hasHangul(queryToken) &&
    queryToken.length >= 3 &&
    queryToken.endsWith(fieldToken)
  )
}

function fieldMatchesToken(
  fieldTokens: Set<string>,
  fieldText: string,
  queryToken: string,
): boolean {
  if (fieldTokens.has(queryToken) || fieldText.includes(queryToken)) {
    return true
  }
  if (!isUsefulDiscoveryToken(queryToken)) return false
  for (const fieldToken of fieldTokens) {
    if (isSingleHangulPlaceSuffixMatch(fieldToken, queryToken)) {
      return true
    }
    if (!isUsefulDiscoveryToken(fieldToken)) continue
    if (fieldToken.includes(queryToken) || queryToken.includes(fieldToken)) {
      return true
    }
  }
  return false
}

function requiredInputFieldsFor(entry: AdapterManifestEntry): string[] {
  return asStringArray(asJsonObject(entry.input_schema_json).required)
}

function isOpaqueProviderIdentifierField(fieldName: string): boolean {
  return (
    fieldName === 'ykiho' ||
    fieldName === 'id' ||
    fieldName.endsWith('_id')
  )
}

function isOpaqueIdentifierOnlyInitialCandidate(
  entry: AdapterManifestEntry,
  queryTokens: Set<string>,
  query: string,
): boolean {
  const requiredFields = requiredInputFieldsFor(entry)
  if (requiredFields.length === 0) return false
  if (!requiredFields.every(isOpaqueProviderIdentifierField)) return false

  const normalizedQuery = query.toLowerCase()
  if (normalizedQuery.includes(entry.tool_id.toLowerCase())) return false
  return !requiredFields.some(fieldName => queryTokens.has(fieldName.toLowerCase()))
}

type AdapterScore = {
  score: number
  qualifyingDiscoveryMatches: number
}

type ScoredAdapterEntry = {
  entry: AdapterManifestEntry
  score: number
}

function scoreAdapterEntry(
  entry: AdapterManifestEntry,
  queryTokens: Set<string>,
  query: string,
): AdapterScore {
  const toolId = entry.tool_id.toLowerCase()
  const name = entry.name.toLowerCase()
  const searchHint = entry.search_hint.toLowerCase()
  const description = (entry.llm_description ?? '').toLowerCase()
  const haystack = [
    toolId,
    name,
    entry.primitive,
    searchHint,
    description,
  ].join(' ').toLowerCase()
  const toolIdTokens = expandedTokensForText(toolId)
  const nameTokens = expandedTokensForText(name)
  const hintTokens = expandedTokensForText(searchHint)
  let score = 0
  let qualifyingDiscoveryMatches = 0
  for (const token of queryTokens) {
    if (!token) continue
    let matchedDiscovery = false
    if (fieldMatchesToken(toolIdTokens, toolId, token)) {
      score += 12
      matchedDiscovery = true
    }
    if (fieldMatchesToken(hintTokens, searchHint, token)) {
      score += 8
      matchedDiscovery = true
    }
    if (fieldMatchesToken(nameTokens, name, token)) {
      score += 4
      matchedDiscovery = true
    }
    if (description.includes(token)) score += 2
    if (haystack.includes(token)) score += 1
    if (matchedDiscovery && isUsefulDiscoveryToken(token)) {
      qualifyingDiscoveryMatches += 1
    }
  }
  if (query.toLowerCase().includes(toolId)) {
    score += 1000
    qualifyingDiscoveryMatches += 1
  }
  return { score, qualifyingDiscoveryMatches }
}

export function selectTopKAdapterToolNamesForQuery(
  query: string,
  maxResults = 5,
  options: AdapterSelectionOptions = {},
): string[] {
  const normalizedQuery = query.trim()
  if (!normalizedQuery || maxResults <= 0) return []
  const queryTokens = expandedQueryTokens(normalizedQuery)
  const routingIntent = extractProviderRoutingIntent(normalizedQuery)
  const restrictiveToolIds = restrictiveToolIdsForIntent(routingIntent, options)
  const ranked = listAdapters()
    .filter(entry => !ROOT_PRIMITIVE_TOOL_NAMES.has(entry.tool_id))
    .map(entry => {
      const result = scoreAdapterEntry(entry, queryTokens, normalizedQuery)
      const routingBoost = routingIntentBoostForTool(entry.tool_id, routingIntent)
      return {
        entry,
        score: result.score + routingBoost,
        qualifyingDiscoveryMatches:
          result.qualifyingDiscoveryMatches + (routingBoost > 0 ? 1 : 0),
      }
    })
    .filter(candidate =>
      (restrictiveToolIds === undefined ||
        restrictiveToolIds.has(candidate.entry.tool_id)) &&
      candidate.score > 0 &&
      candidate.qualifyingDiscoveryMatches > 0 &&
      !isOpaqueIdentifierOnlyInitialCandidate(
        candidate.entry,
        queryTokens,
        normalizedQuery,
      )
    )
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      return a.entry.tool_id.localeCompare(b.entry.tool_id)
    })

  return pickDiverseAdapterToolNames(ranked, maxResults)
}

function pickDiverseAdapterToolNames(
  ranked: ScoredAdapterEntry[],
  maxResults: number,
): string[] {
  const selected: string[] = []
  const seen = new Set<string>()
  const add = (candidate: ScoredAdapterEntry): void => {
    if (selected.length >= maxResults || seen.has(candidate.entry.tool_id)) return
    selected.push(candidate.entry.tool_id)
    seen.add(candidate.entry.tool_id)
  }

  const locateCandidates = ranked.filter(candidate => candidate.entry.primitive === 'locate')
  const actionCandidates = ranked.filter(candidate => candidate.entry.primitive !== 'locate')

  if (actionCandidates.length > 0) {
    const locateBudget = Math.min(2, Math.max(1, maxResults - 1))
    for (const candidate of locateCandidates.slice(0, locateBudget)) add(candidate)
    for (const candidate of actionCandidates) add(candidate)
  } else {
    for (const candidate of ranked) add(candidate)
  }

  for (const candidate of ranked) add(candidate)
  return selected
}

function buildAdapterTool(entry: AdapterManifestEntry): Tool {
  const primitive = primitiveFor(entry)
  const primitiveTool = primitiveToolFor(primitive)
  const adapterInputSchema = inputSchemaFor(entry)
  const adapterInputJSONSchema = inputJSONSchemaFor(entry)
  const directCheckAdapterRequiresPermission =
    primitive === 'check' && !ROOT_PRIMITIVE_TOOL_NAMES.has(entry.tool_id)

  return buildTool({
    name: entry.tool_id,
    // Keep concrete public-service adapters in CC's Tool object shape, but do
    // not inline every synced adapter schema into the first LLM request. The
    // ToolSearch path loads the few adapters relevant to the citizen request.
    shouldDefer: true,
    searchHint: [entry.search_hint, entry.name, entry.tool_id, primitive]
      .filter(Boolean)
      .join(' '),
    maxResultSizeChars: primitiveTool.maxResultSizeChars,
    inputJSONSchema: adapterInputJSONSchema,

    get inputSchema(): InputSchema {
      return adapterInputSchema
    },

    get outputSchema() {
      return primitiveTool.outputSchema
    },

    isEnabled() {
      return true
    },

    isConcurrencySafe(input) {
      return primitiveTool.isConcurrencySafe(rootInputFor(entry, input))
    },

    isReadOnly(input) {
      if (directCheckAdapterRequiresPermission) return false
      return primitiveTool.isReadOnly(rootInputFor(entry, input))
    },

    isDestructive(input) {
      if (directCheckAdapterRequiresPermission) return true
      return primitiveTool.isDestructive?.(rootInputFor(entry, input)) ?? false
    },

    async checkPermissions(input, context) {
      return primitiveTool.checkPermissions(rootInputFor(entry, input), context)
    },

    async description() {
      return entry.name
    },

    async prompt() {
      const description = entry.llm_description?.trim() || `${entry.name}.`
      return [
        description,
        `Concrete UMMAYA ${primitive} adapter. Call this tool directly with the ` +
          'adapter schema arguments supplied by the backend manifest.',
      ].join('\n\n')
    },

    async validateInput(input, context) {
      if (!resolveAdapter(entry.tool_id)) {
        return {
          result: false as const,
          message: `Adapter '${entry.tool_id}' is not in the synced backend manifest.`,
          errorCode: 1,
        }
      }
      if (typeof input !== 'object' || input === null) {
        return {
          result: false as const,
          message: `Adapter '${entry.tool_id}' expects a JSON object argument.`,
          errorCode: 1,
        }
      }
      const contractInput = validateAdapterContractInput(
        entry.tool_id,
        input as Record<string, unknown>,
      )
      if (contractInput) return contractInput
      return { result: true as const }
    },

    async call(input, context) {
      const normalizedDocumentInput = normalizeExplicitDocumentArtifactInput(
        entry.tool_id,
        input,
        context.messages,
      )
      const adapterCallInput = concreteAdapterCallInputFor(
        entry,
        normalizedDocumentInput,
      )
      const result = await dispatchPrimitive({
        primitive,
        toolName: entry.tool_id,
        args: adapterCallInput,
        context,
        registry: getOrCreatePendingCallRegistry(),
        bridge: getOrCreateUmmayaBridge(),
        timeoutMs:
          primitive === 'document'
            ? resolveDocumentPrimitiveTimeoutMs()
            : undefined,
      })
      return {
        ...result,
        data: applyDocumentVisualRenderGateToOutput(result.data),
      }
    },

    userFacingName(input) {
      if (DOCUMENT_TOOL_NAMES.has(entry.tool_id)) {
        return 'Document'
      }
      return primitiveTool.userFacingName(rootInputFor(entry, input ?? {}))
    },

    mapToolResultToToolResultBlockParam(output, toolUseID) {
      const gatedOutput = applyDocumentVisualRenderGateToOutput(output)
      const block = primitiveTool.mapToolResultToToolResultBlockParam(gatedOutput, toolUseID)
      return isDocumentVisualRenderFailedOutput(gatedOutput)
        ? { ...block, is_error: true }
        : block
    },

    renderToolUseMessage(input, options) {
      if (DOCUMENT_TOOL_NAMES.has(entry.tool_id)) {
        return renderDocumentToolUseMessage(
          entry.tool_id,
          input as Record<string, unknown>,
        )
      }
      const rendered = primitiveTool.renderToolUseMessage(
        rootInputFor(entry, input),
        options,
      )
      return rendered === null ? entry.tool_id : rendered
    },

    renderToolResultMessage(output, progressMessagesForMessage, options) {
      const gatedOutput = applyDocumentVisualRenderGateToOutput(output)
      if (shouldHideSuccessfulIntermediateDocumentResult(gatedOutput)) {
        return null
      }
      const documentResult = renderDocumentToolResultIfPresent(gatedOutput, options)
      if (documentResult !== null) {
        return documentResult
      }
      return primitiveTool.renderToolResultMessage?.(
        gatedOutput,
        progressMessagesForMessage,
        options,
      ) ?? null
    },

    isResultTruncated(output) {
      return primitiveTool.isResultTruncated?.(output) ?? false
    },
  } satisfies ToolDef<InputSchema>)
}
