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
import { validateKmaAviationToolChoice } from '../_shared/kmaAviationGuard.js'
import { validateKmaAnalysisToolChoice } from '../_shared/kmaAnalysisGuard.js'
import { validateNmcAedToolChoice } from '../_shared/nmcAedGuard.js'
import {
  normalizeDirectPublicDataToolInput,
  validateDirectPublicDataToolChoice,
} from '../_shared/directPublicDataGuard.js'
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
const KMA_URL_AIR_TOOL_NAMES = new Set([
  'kma_apihub_url_air_amos_minute',
  'kma_apihub_url_air_metar_decoded',
])
const KMA_ANALYSIS_TOOL_NAMES = new Set([
  'kma_apihub_url_high_resolution_grid_point',
  'kma_apihub_url_aws_objective_analysis_grid',
  'kma_apihub_url_analysis_weather_chart_image',
])
const TAGO_BUS_TOOL_NAMES = new Set([
  'tago_bus_station_search',
  'tago_bus_arrival_search',
  'tago_bus_route_search',
  'tago_bus_route_station_search',
  'tago_bus_location_search',
])
const KMA_GIMHAE_AIRPORT_RE = /(김해공항|gimhae|rkpk)/iu
const KMA_GIMPO_AIRPORT_RE = /(김포공항|gimpo|rkss)/iu
const KMA_AIRPORT_NAME_RE = /(공항|\bairport\b|\brk[a-z]{2}\b|station\s*\d{2,3})/iu
const KMA_AIRPORT_AVIATION_RE =
  /(amos|metar|speci|rvr|항공기상|공항기상|활주로|runway|aviation|비행기|항공편|비행편|이륙|착륙|결항|지연|운항|뜰\s*만|뜨나|뜰\s*수|flight|take\s*off|landing|delay|cancel)/iu
const KMA_RUNWAY_AREA_RE =
  /(amos|활주로|rvr|runway|시정|visibility|공항기상관측|매분)/iu
const KMA_ANALYSIS_DATA_RE =
  /(분석자료|이미\s*분석|고해상도\s*격자|객관분석|aws\s*객관|지도\s*자료|일기도|분석일기도|비구름|바람\s*흐름|synoptic|weather\s*chart|objective\s*analysis|high[-\s]?resolution|grid)/iu
const KMA_ANALYSIS_MAP_RE =
  /(일기도|분석일기도|지도\s*자료|비구름|바람\s*흐름|synoptic|weather\s*chart)/iu
const KMA_ANALYSIS_POINT_RE =
  /(주변|근처|특정지점|좌표|위도|경도|\blat\b|\blon\b|공항\s*주변)/iu
const KMA_LIFESTYLE_WEATHER_RE =
  /(날씨|현재\s*기상|실황|관측|예보|기온|습도|풍속|지금\s*비|비\s*(와|오|올|내리)|우산|강수|소나기|산책|퇴근|current\s+weather|forecast|rain|umbrella|precipitation|temperature)/iu
const KMA_LIFESTYLE_WEATHER_TOOL_NAMES = new Set([
  'kma_current_observation',
  'kma_ultra_short_term_forecast',
  'kma_short_term_forecast',
])
const HIRA_MEDICAL_DETAIL_RE =
  /((병원|의료기관|의원).*(상세|진료과|진료과목|진료시간|주차)|(상세|진료시간|주차|응급실).*(병원|의료기관|의원)|ykiho|detail)/iu
const MOIS_EMERGENCY_CALL_BOX_RE =
  /(안전\s*비상벨|비상벨|긴급\s*신고함|긴급신고함|방범벨|emergency\s+call\s+box)/iu
const GYERYONG_ASSISTIVE_CHARGER_RE =
  /((전동보장구|전동\s*휠체어|보장구|장애인).*(충전|충전소|충전장소)|(충전|충전소|충전장소).*(전동보장구|전동\s*휠체어|보장구|장애인)|계룡시?.*(충전소|충전\s*장소))/iu
const MOF_OCEAN_WATER_QUALITY_RE =
  /(해양\s*수질|해양수질|수질\s*자동\s*측정|용존산소|\bpH\b|water\s+quality|ocean\s+water)/iu
const PPS_SHOPPING_RE = /(종합\s*쇼핑몰|쇼핑몰|계약\s*물품|물품\s*조회|shopping\s*mall)/iu
const PPS_BID_RE = /(입찰|나라장터|조달청|\bbid\b|procurement|tender)/iu
const PROTECTED_QUERY_RE =
  /(본인확인|인증|간편인증|모바일\s*(?:신분증|id)|mobile\s*id|마이데이터|mydata|증명원|소득금액증명|소득금액증명원|주민등록등본|민원|발급)/iu
const PROTECTED_MOBILE_ID_RE = /(mobile\s*id|모바일\s*(?:신분증|id)|mobile_id)/iu
const PROTECTED_SIMPLE_AUTH_RE =
  /(simple_auth|간편인증|ganpyeon|소득금액증명|증명원|민원|발급)/iu
const PROTECTED_MYDATA_RE = /(mydata|마이데이터)/iu
const PROTECTED_CHECK_TOOL_NAMES = [
  'mock_verify_module_simple_auth',
  'mock_verify_ganpyeon_injeung',
  'mock_verify_mobile_id',
  'mock_verify_mydata',
] as const
const TAGO_BUS_RE =
  /(버스|시내버스|정류장|정류소|노선|도착|언제\s*와|몇\s*분|bus|route|arrival|station)/iu
const AED_REQUEST_RE = /(aed|자동심장|심장충격|제세동)/iu
const EMERGENCY_REQUEST_RE = /(응급|응급실|\ber\b|emergency)/iu
const MEDICAL_COLLAPSE_RE =
  /(사람이\s*쓰러|쓰러졌|쓰러져|의식\s*잃|의식을\s*잃|심정지|호흡이\s*없|숨을\s*안|collapsed|unconscious|cardiac\s*arrest)/iu
const TRAFFIC_HAZARD_RE =
  /(교통사고|사고\s*위험|사고다발|위험\s*(구간|도로|지점)|어린이보호구역|보호구역|도로\s*구간|accident|hazard|hotspot)/iu
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

function validateAdapterContractInput(
  toolId: string,
  input: Record<string, unknown>,
) {
  if (toolId !== 'kma_apihub_url_analysis_weather_chart_image') return undefined
  const analTime = input.anal_time
  if (typeof analTime === 'string' && /^\d{12}$/u.test(analTime)) return undefined
  return {
    result: false as const,
    message:
      'KMA analysis weather-chart schema mismatch: anal_time is required as UTC YYYYMMDDHHMM. ' +
      "Use a 12-digit official analysis time with minutes, for example '202605281200', not a 10-digit KST hour. " +
      'If the citizen asks for now/today, choose the latest completed official UTC analysis slot and report upstream failure directly if APIHub has no chart.',
    errorCode: 1,
  }
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

function expandedQueryTokens(query: string): Set<string> {
  const tokens = new Set(searchTokens(query))
  const compact = query.toLowerCase()
  const airportAviationQuery = isAirportAviationQuery(query)
  if (/[날씨기상비강수기온습도풍속예보관측실황]/u.test(compact)) {
    for (const token of [
      '날씨',
      '기상',
      '현재',
      '관측',
      '실황',
      'weather',
      'current',
      'observation',
      'forecast',
      'temperature',
      'precipitation',
      'humidity',
      'wind',
      'kma',
      '초단기실황',
      '초단기예보',
      '단기예보',
      '우산',
      'nx',
      'ny',
      'base_date',
      'base_time',
    ]) {
      tokens.add(token)
    }
  }
  const medicalEmergencyQuery = isMedicalEmergencyQuery(query)
  const collapseOrAedQuery = isCollapseOrAedQuery(query)
  if (EMERGENCY_REQUEST_RE.test(compact) && medicalEmergencyQuery) {
    for (const token of [
      '응급',
      '응급실',
      '응급의료',
      '응급의료센터',
      '실시간',
      '병상',
      '야간',
      'emergency',
      'room',
      'er',
      'nmc',
    ]) {
      tokens.add(token)
    }
  }
  if (collapseOrAedQuery) {
    for (const token of [
      '응급',
      '응급실',
      '응급의료',
      '응급의료센터',
      'aed',
      '자동심장충격기',
      '자동제세동기',
      '심장충격기',
      '응급처치',
      '심정지',
      '의식불명',
      'emergency',
      'room',
      'er',
      'defibrillator',
      'cardiac',
      'arrest',
      'nmc',
    ]) {
      tokens.add(token)
    }
  }
  if (/(병원|의료|진료|약국|hospital|clinic|medical)/u.test(compact)) {
    for (const token of [
      '병원',
      '의료기관',
      '진료',
      '진료과목',
      '야간',
      '약국',
      'hospital',
      'clinic',
      'medical',
      'nearby',
    ]) {
      tokens.add(token)
    }
  }
  if (HIRA_MEDICAL_DETAIL_RE.test(query)) {
    for (const token of [
      '상세정보',
      '진료과',
      '진료과목',
      '진료시간',
      '주차',
      '요양기호',
      'ykiho',
      'hira',
      'detail',
      'specialty',
    ]) {
      tokens.add(token)
    }
  }
  if (MOIS_EMERGENCY_CALL_BOX_RE.test(query)) {
    for (const token of [
      '안전비상벨',
      '비상벨',
      '긴급신고함',
      '방범',
      '행정안전부',
      'mois',
      'emergency',
      'call',
      'box',
    ]) {
      tokens.add(token)
    }
  }
  if (GYERYONG_ASSISTIVE_CHARGER_RE.test(query)) {
    for (const token of [
      '계룡시',
      '전동보장구',
      '전동휠체어',
      '보장구',
      '장애인',
      '충전소',
      '충전장소',
      'accessibility',
      'charger',
    ]) {
      tokens.add(token)
    }
  }
  if (MOF_OCEAN_WATER_QUALITY_RE.test(query)) {
    for (const token of [
      '해양수산부',
      '해양수질',
      '수질자동측정망',
      '관측소',
      'sea3003',
      '용존산소',
      'water',
      'quality',
      'ocean',
    ]) {
      tokens.add(token)
    }
  }
  if (isPpsBidQuery(query)) {
    for (const token of [
      '조달청',
      '나라장터',
      '입찰공고',
      '공사입찰',
      'bidntcenm',
      'inqrybgndt',
      'inqryenddt',
      'pps',
      'bid',
      'procurement',
    ]) {
      tokens.add(token)
    }
  }
  if (isProtectedCheckQuery(query)) {
    for (const token of [
      '본인확인',
      '인증',
      '간편인증',
      '모바일신분증',
      '모바일id',
      '소득금액증명원',
      '증명원',
      '홈택스',
      '정부24',
      'check',
      'verify',
      'identity',
      'simple',
      'auth',
      'mobile',
      'id',
      'mydata',
    ]) {
      tokens.add(token)
    }
  }
  if (isTagoBusQuery(query)) {
    for (const token of [
      '국토교통부',
      'tago',
      '버스',
      '시내버스',
      '버스정류소',
      '정류장',
      '정류소',
      '노선',
      '노선번호',
      '버스도착',
      '도착',
      'nodeid',
      'nodenm',
      'nodeno',
      'routeid',
      'routeno',
      'citycode',
      'bus',
      'station',
      'route',
      'arrival',
    ]) {
      tokens.add(token)
    }
  }
  if (collapseOrAedQuery) {
    for (const token of ['aed', '자동심장충격기', '자동제세동기', '심장충격기', '위치']) {
      tokens.add(token)
    }
  }
  if (/(미세먼지|초미세|대기질|공기질|airquality|air quality)/u.test(compact)) {
    for (const token of ['미세먼지', '대기질', '대기오염', 'airkorea', 'air', 'quality']) {
      tokens.add(token)
    }
  }
  if (/(법률|변호사|무료상담|상담)/u.test(compact)) {
    for (const token of ['법률', '변호사', '마을변호사', '상담', 'legal', 'lawyer']) {
      tokens.add(token)
    }
  }
  if (/(장례|화장|봉안|장사|funeral)/u.test(compact)) {
    for (const token of ['장례', '장례식장', '시설사용료', 'funeral', 'fee']) {
      tokens.add(token)
    }
  }
  if (/(취업|채용|공고|공무원|job|recruit)/u.test(compact)) {
    for (const token of ['취업', '채용', '공고', '공무원', 'public', 'job']) {
      tokens.add(token)
    }
  }
  if (/(대학|등록금|유학생|tuition|university)/u.test(compact)) {
    for (const token of ['대학', '등록금', '유학생', '대학알리미', 'tuition', 'university']) {
      tokens.add(token)
    }
  }
  if (/(전력|전기|한전|계약종별|power|kepco)/u.test(compact)) {
    for (const token of ['전력', '전기사용량', '계약종별', '한전', 'kepco', 'power', 'usage']) {
      tokens.add(token)
    }
  }
  if (/(특보|예비특보|경보|주의보|태풍|warning|alert)/u.test(compact)) {
    for (const token of ['특보', '예비특보', '경보', '주의보', '기상청', 'weather', 'alert']) {
      tokens.add(token)
    }
  }
  if (airportAviationQuery) {
    for (const token of [
      'metar',
      'speci',
      'amos',
      '항공기상',
      '공항기상',
      '항공',
      '비행기',
      '항공편',
      '운항',
      '이륙',
      '시정',
      'rvr',
      'wind',
      'visibility',
    ]) {
      tokens.add(token)
    }
    if (KMA_GIMPO_AIRPORT_RE.test(query) && KMA_RUNWAY_AREA_RE.test(query)) {
      for (const token of [
        'amos',
        '공항기상관측',
        '매분자료',
        '활주로',
        '김포공항',
        'stn110',
        'runway',
        'visibility',
      ]) {
        tokens.add(token)
      }
    }
  }
  if (KMA_ANALYSIS_DATA_RE.test(query)) {
    for (const token of [
      '분석자료',
      '고해상도',
      '격자자료',
      '객관분석',
      'aws',
      '분석일기도',
      '지도',
      '비구름',
      '바람흐름',
      'objective',
      'analysis',
      'grid',
      'chart',
    ]) {
      tokens.add(token)
    }
  }
  if (/(교통사고|사고\s*위험|사고다발|위험\s*(구간|도로|지점)|어린이보호구역|보호구역|도로\s*구간|accident|hazard|hotspot)/u.test(compact)) {
    for (const token of [
      '교통사고',
      '사고',
      '위험',
      '위험지점',
      '사고다발',
      '사고다발구역',
      '어린이보호구역',
      '행정동코드',
      'koroad',
      'accident',
      'hazard',
      'hotspot',
    ]) {
      tokens.add(token)
    }
  }
  if (/(주소|위치|좌표|행정|[가-힣]+(시|군|구|동|읍|면|로|길))/u.test(compact)) {
    for (const token of [
      'locate',
      '위치',
      '주소',
      '좌표',
      '행정동',
      '법정동',
      'geocode',
      'address',
      'kakao',
    ]) {
      tokens.add(token)
    }
  }
  if (
    !airportAviationQuery &&
    /(근처|주변|인근|가까운|역|터미널|공항|캠퍼스|대학교|대학|해수욕장|시장|공원|랜드마크|nearby|around)/u.test(compact)
  ) {
    for (const token of [
      '장소',
      '키워드',
      'poi',
      '랜드마크',
      '역',
      'keyword',
      'station',
      'place',
    ]) {
      tokens.add(token)
    }
  }
  return tokens
}

type ScoredAdapterEntry = {
  entry: AdapterManifestEntry
  score: number
}

function queryExplicitlyMentionsCoordinates(query: string): boolean {
  return /좌표|위도|경도|\blat\b|\blon\b|\blongitude\b|\blatitude\b|wgs84|coord|coord2region|reverse geocode|q0|q1/i.test(query)
}

function isReverseGeocodeAdapter(toolId: string): boolean {
  return toolId === 'kakao_coord_to_region' || toolId === 'sgis_adm_cd_lookup'
}

function queryTargetsKoroadHazardDataset(query: string): boolean {
  return /(사고\s*위험|위험\s*(구간|도로|지점)|도로\s*구간|어린이보호구역|보호구역|스쿨존|행정동코드|adm_cd|hazard|hotspot)/iu.test(query)
}

function isAirportAviationQuery(query: string): boolean {
  return KMA_AIRPORT_NAME_RE.test(query) && KMA_AIRPORT_AVIATION_RE.test(query)
}

function isMedicalEmergencyQuery(query: string): boolean {
  return (
    (EMERGENCY_REQUEST_RE.test(query) ||
      AED_REQUEST_RE.test(query) ||
      MEDICAL_COLLAPSE_RE.test(query)) &&
    !MOIS_EMERGENCY_CALL_BOX_RE.test(query)
  )
}

function isCollapseOrAedQuery(query: string): boolean {
  return (
    (AED_REQUEST_RE.test(query) || MEDICAL_COLLAPSE_RE.test(query)) &&
    !MOIS_EMERGENCY_CALL_BOX_RE.test(query)
  )
}

function isLocationAdapter(entry: AdapterManifestEntry): boolean {
  return entry.primitive === 'locate' || ROOT_PRIMITIVE_TOOL_NAMES.has(entry.tool_id)
}

function isKmaAnalysisQuery(query: string): boolean {
  return KMA_ANALYSIS_DATA_RE.test(query)
}

function isLifestyleWeatherQuery(query: string): boolean {
  return (
    KMA_LIFESTYLE_WEATHER_RE.test(query) &&
    !isAirportAviationQuery(query) &&
    !isKmaAnalysisQuery(query) &&
    !isMedicalEmergencyQuery(query) &&
    !TRAFFIC_HAZARD_RE.test(query) &&
    !MOF_OCEAN_WATER_QUALITY_RE.test(query)
  )
}

function isPpsBidQuery(query: string): boolean {
  return PPS_BID_RE.test(query) && !PPS_SHOPPING_RE.test(query)
}

function isProtectedCheckQuery(query: string): boolean {
  return PROTECTED_QUERY_RE.test(query)
}

function protectedCheckToolPreference(query: string): string[] {
  const preferred = [
    PROTECTED_MOBILE_ID_RE.test(query) ? 'mock_verify_mobile_id' : undefined,
    PROTECTED_SIMPLE_AUTH_RE.test(query) ? 'mock_verify_module_simple_auth' : undefined,
    PROTECTED_SIMPLE_AUTH_RE.test(query) ? 'mock_verify_ganpyeon_injeung' : undefined,
    PROTECTED_MYDATA_RE.test(query) ? 'mock_verify_mydata' : undefined,
    ...PROTECTED_CHECK_TOOL_NAMES,
  ].filter((toolName): toolName is string => typeof toolName === 'string')
  return [...new Set(preferred)]
}

function isTagoBusQuery(query: string): boolean {
  return TAGO_BUS_RE.test(query)
}

function isKmaAnalysisMapQuery(query: string): boolean {
  return KMA_ANALYSIS_MAP_RE.test(query)
}

function isKmaAnalysisPointQuery(query: string): boolean {
  return KMA_ANALYSIS_POINT_RE.test(query) && !isKmaAnalysisMapQuery(query)
}

function queryPrefersPoiLocation(query: string): boolean {
  return /(근처|주변|인근|가까운|역|터미널|공항|캠퍼스|대학교|대학|해수욕장|시장|공원|랜드마크|nearby|around)/iu.test(query)
}

function scoreAdapterEntry(
  entry: AdapterManifestEntry,
  queryTokens: Set<string>,
  query: string,
): number {
  const searchHint = entry.search_hint.toLowerCase()
  const description = (entry.llm_description ?? '').toLowerCase()
  const haystack = [
    entry.tool_id,
    entry.name,
    entry.primitive,
    searchHint,
    description,
  ].join(' ').toLowerCase()
  const hintTokens = new Set(searchTokens(searchHint))
  let score = 0
  for (const token of queryTokens) {
    if (!token) continue
    if (entry.tool_id.toLowerCase().includes(token)) score += 12
    if (hintTokens.has(token)) score += 8
    else if (searchHint.includes(token)) score += 4
    if (description.includes(token)) score += 2
    if (haystack.includes(token)) score += 1
  }
  if (query.toLowerCase().includes(entry.tool_id.toLowerCase())) score += 1000
  if (
    isReverseGeocodeAdapter(entry.tool_id) &&
    !queryExplicitlyMentionsCoordinates(query)
  ) {
    score = Math.max(0, score - 24)
  }
  if (queryTargetsKoroadHazardDataset(query)) {
    if (entry.tool_id === 'koroad_accident_hazard_search') score += 32
    if (entry.tool_id === 'koroad_accident_search') score = 0
  }
  if (isKmaAnalysisQuery(query)) {
    if (entry.tool_id === 'kma_apihub_url_analysis_weather_chart_image') {
      score += isKmaAnalysisMapQuery(query) ? 900 : isKmaAnalysisPointQuery(query) ? -20 : 150
    }
    if (entry.tool_id === 'kma_apihub_url_high_resolution_grid_point') {
      score += isKmaAnalysisPointQuery(query) ? 900 : 450
    }
    if (entry.tool_id === 'kma_apihub_url_aws_objective_analysis_grid') {
      score += isKmaAnalysisPointQuery(query) ? 800 : 400
    }
    if (isKmaAnalysisPointQuery(query) && queryPrefersPoiLocation(query)) {
      if (entry.tool_id === 'kakao_keyword_search') score += 30
      if (entry.tool_id === 'kakao_address_search') score = Math.max(1, score - 15)
    }
  }
  if (isLifestyleWeatherQuery(query)) {
    if (entry.tool_id === 'kakao_keyword_search') score += 1100
    if (entry.tool_id === 'kakao_address_search') score += 1000
    if (entry.tool_id === 'kma_current_observation') score += 900
    if (entry.tool_id === 'kma_ultra_short_term_forecast') score += 800
    if (entry.tool_id === 'kma_short_term_forecast') score += 650
    if (entry.tool_id === 'kakao_coord_to_region') score += 260
    if (entry.tool_id === 'juso_adm_cd_lookup') score += 260
    if (entry.tool_id === 'sgis_adm_cd_lookup') score += 260
  }
  if (HIRA_MEDICAL_DETAIL_RE.test(query)) {
    if (entry.tool_id === 'hira_medical_institution_detail') score += 650
  }
  if (MOIS_EMERGENCY_CALL_BOX_RE.test(query)) {
    if (entry.tool_id === 'mois_emergency_call_box_lookup') score += 1000
  }
  if (GYERYONG_ASSISTIVE_CHARGER_RE.test(query)) {
    if (entry.tool_id === 'gyeryong_assistive_device_charging_place_locate') {
      score += 1000
    }
  }
  if (MOF_OCEAN_WATER_QUALITY_RE.test(query)) {
    if (entry.tool_id === 'mof_ocean_water_quality_check') score += 1000
  }
  if (isPpsBidQuery(query)) {
    if (entry.tool_id === 'pps_bid_public_info') score += 1000
  }
  if (isProtectedCheckQuery(query) && entry.primitive === 'check') {
    const preference = protectedCheckToolPreference(query)
    const index = preference.indexOf(entry.tool_id)
    score += index >= 0 ? 1000 - index * 20 : 500
  }
  if (isTagoBusQuery(query)) {
    if (entry.tool_id === 'tago_bus_station_search') score += 1050
    if (entry.tool_id === 'tago_bus_arrival_search') score += 1000
    if (entry.tool_id === 'tago_bus_route_station_search') score += 950
    if (entry.tool_id === 'tago_bus_route_search') score += 850
    if (entry.tool_id === 'tago_bus_location_search') score += 650
  }
  if (isCollapseOrAedQuery(query)) {
    if (entry.tool_id === 'nmc_aed_site_locate') score += 900
    if (entry.tool_id === 'nmc_emergency_search') score += 700
    if (queryPrefersPoiLocation(query) && entry.tool_id === 'kakao_keyword_search') score += 120
  }
  if (
    KMA_GIMPO_AIRPORT_RE.test(query) &&
    KMA_RUNWAY_AREA_RE.test(query) &&
    KMA_AIRPORT_AVIATION_RE.test(query) &&
    entry.tool_id === 'kma_apihub_url_air_amos_minute'
  ) {
    score += 500
  }
  return score
}

function filterSpecialCaseRanked(
  query: string,
  ranked: ScoredAdapterEntry[],
): ScoredAdapterEntry[] {
  let filtered = ranked
  if (isKmaAnalysisQuery(query)) {
    const allowLocation = isKmaAnalysisPointQuery(query)
    const preferPoiLocation = queryPrefersPoiLocation(query)
    filtered = filtered
      .filter(candidate => {
        if (KMA_ANALYSIS_TOOL_NAMES.has(candidate.entry.tool_id)) return true
        return allowLocation && isLocationAdapter(candidate.entry)
      })
      .map(candidate => {
        if (!allowLocation || !isLocationAdapter(candidate.entry)) return candidate
        let score = Math.max(1, candidate.score - 10)
        if (preferPoiLocation && candidate.entry.tool_id === 'kakao_keyword_search') {
          score += 30
        } else if (preferPoiLocation && candidate.entry.tool_id === 'kakao_address_search') {
          score = Math.max(1, score - 15)
        }
        return { ...candidate, score }
      })
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
  }
  if (isLifestyleWeatherQuery(query)) {
    const allowed = filtered.filter(
      candidate =>
        KMA_LIFESTYLE_WEATHER_TOOL_NAMES.has(candidate.entry.tool_id) ||
        isLocationAdapter(candidate.entry),
    )
    if (allowed.length > 0) {
      filtered = allowed.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (isPpsBidQuery(query)) {
    const allowed = filtered.filter(candidate => candidate.entry.tool_id === 'pps_bid_public_info')
    if (allowed.length > 0) {
      filtered = allowed.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (isProtectedCheckQuery(query)) {
    const preference = protectedCheckToolPreference(query)
    const allowed = filtered.filter(candidate => candidate.entry.primitive === 'check')
    if (allowed.length > 0) {
      filtered = allowed.sort((a, b) => {
        const aIndex = preference.indexOf(a.entry.tool_id)
        const bIndex = preference.indexOf(b.entry.tool_id)
        const aRank = aIndex >= 0 ? aIndex : Number.MAX_SAFE_INTEGER
        const bRank = bIndex >= 0 ? bIndex : Number.MAX_SAFE_INTEGER
        if (aRank !== bRank) return aRank - bRank
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (isTagoBusQuery(query)) {
    const allowed = filtered.filter(candidate => TAGO_BUS_TOOL_NAMES.has(candidate.entry.tool_id))
    if (allowed.length > 0) {
      filtered = allowed.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (isCollapseOrAedQuery(query)) {
    const allowed = filtered.filter(candidate => {
      if (candidate.entry.tool_id === 'nmc_aed_site_locate') return true
      if (candidate.entry.tool_id === 'nmc_emergency_search') return true
      return isLocationAdapter(candidate.entry)
    })
    if (allowed.some(candidate => candidate.entry.tool_id === 'nmc_aed_site_locate')) {
      filtered = allowed.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.entry.tool_id.localeCompare(b.entry.tool_id)
      })
    }
  }
  if (KMA_GIMHAE_AIRPORT_RE.test(query) && KMA_AIRPORT_AVIATION_RE.test(query)) {
    filtered = filtered.filter(
      candidate => candidate.entry.tool_id !== 'kma_apihub_url_air_amos_minute',
    )
  }
  if (isAirportAviationQuery(query)) {
    const hasAirUrlCandidate = filtered.some(candidate =>
      KMA_URL_AIR_TOOL_NAMES.has(candidate.entry.tool_id),
    )
    if (hasAirUrlCandidate) {
      filtered = filtered.filter(
        candidate =>
          !isLocationAdapter(candidate.entry) &&
          candidate.entry.tool_id !== 'kma_current_observation',
      )
    }
  }
  return filtered
}

export function selectTopKAdapterToolNamesForQuery(
  query: string,
  maxResults = 5,
): string[] {
  const normalizedQuery = query.trim()
  if (!normalizedQuery || maxResults <= 0) return []
  const queryTokens = expandedQueryTokens(normalizedQuery)
  const ranked = filterSpecialCaseRanked(
    normalizedQuery,
    listAdapters()
    .filter(entry => !ROOT_PRIMITIVE_TOOL_NAMES.has(entry.tool_id))
    .map(entry => ({
      entry,
      score: scoreAdapterEntry(entry, queryTokens, normalizedQuery),
    }))
    .filter(candidate => candidate.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      return a.entry.tool_id.localeCompare(b.entry.tool_id)
    }),
  )

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
      return primitiveTool.isReadOnly(rootInputFor(entry, input))
    },

    isDestructive(input) {
      return primitiveTool.isDestructive?.(rootInputFor(entry, input)) ?? false
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
      const directPublicDataChoice = validateDirectPublicDataToolChoice(
        entry.tool_id,
        context,
        input,
      )
      if (directPublicDataChoice) return directPublicDataChoice
      const kmaAviationChoice = validateKmaAviationToolChoice(entry.tool_id, context)
      if (kmaAviationChoice) return kmaAviationChoice
      const kmaAnalysisChoice = validateKmaAnalysisToolChoice(entry.tool_id, context)
      if (kmaAnalysisChoice) return kmaAnalysisChoice
      const nmcAedChoice = validateNmcAedToolChoice(entry.tool_id, context)
      if (nmcAedChoice) return nmcAedChoice
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
      const directPublicDataInput = normalizeDirectPublicDataToolInput(
        entry.tool_id,
        context,
        normalizedDocumentInput,
      )
      const result = await dispatchPrimitive({
        primitive,
        toolName: entry.tool_id,
        args: directPublicDataInput,
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
