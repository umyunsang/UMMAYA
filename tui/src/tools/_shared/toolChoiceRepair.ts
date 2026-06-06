import type { BetaToolChoiceTool } from '../../sdk-compat.js'
import type { Tools } from '../../Tool.js'
import type { Message } from '../../types/message.js'
import {
  buildNmcAedFollowupPromptIfNeeded,
  textFromContent,
} from './nmcAedGuard.js'
import { resolveAdapter } from '../../services/api/adapterManifest.js'
import {
  isKmaAnalysisMapText,
  KMA_ANALYSIS_CHART_TOOL_NAME,
} from './kmaAnalysisGuard.js'
import { isNonSyntheticUserMessageText } from './citizenUserText.js'
import { TOOL_SEARCH_TOOL_NAME } from '../ToolSearchTool/constants.js'

const KMA_AIR_TOOLS = [
  'kma_apihub_url_air_metar_decoded',
  'kma_apihub_url_air_amos_minute',
] as const
const NMC_EMERGENCY_TOOL_NAME = 'nmc_emergency_search'
const NMC_AED_TOOL_NAME = 'nmc_aed_site_locate'
const KAKAO_COORD_TO_REGION_TOOL_NAME = 'kakao_coord_to_region'
const TAGO_STATION_TOOL_NAME = 'tago_bus_station_search'
const TAGO_ROUTE_TOOL_NAME = 'tago_bus_route_search'
const TAGO_ROUTE_STATION_TOOL_NAME = 'tago_bus_route_station_search'
const TAGO_ARRIVAL_TOOL_NAME = 'tago_bus_arrival_search'
const PPS_BID_TOOL_NAME = 'pps_bid_public_info'
const AIRKOREA_TOOL_NAME = 'airkorea_ctprvn_air_quality'
const DOCUMENT_TOOL_NAME = 'document'
const DOCUMENT_RENDER_TOOL_NAME = 'document_render'
const DOCUMENT_TOOL_LOAD_QUERY = 'select:document'
const WORKSPACE_GLOB_TOOL_NAME = 'workspace_glob'
const LEGACY_GLOB_TOOL_NAME = 'Glob'
const PROTECTED_CHECK_TOOLS = [
  'mock_verify_module_simple_auth',
  'mock_verify_ganpyeon_injeung',
  'mock_verify_mobile_id',
  'mock_verify_mydata',
] as const

const AIRPORT_PLACE_RE =
  /(김해|김포|김해공항|김포공항|gimhae|gimpo|rkpk|rkss|\bairport\b|공항)/iu
const AIRPORT_AVIATION_RE =
  /(비행기|항공편|비행편|운항|이륙|착륙|결항|지연|뜰\s*만|뜨나|뜰\s*수|flight|take\s*off|landing|delay|cancel|metar|speci|amos|rvr|활주로|시정|visibility|공항기상|항공기상)/iu
const AMOS_PREFERENCE_RE = /(amos|rvr|활주로|runway)/iu
const GIMPO_RE = /(김포|김포공항|gimpo|rkss)/iu
const PROTECTED_QUERY_RE =
  /(본인확인|인증|간편인증|모바일\s*(?:신분증|id)|mobile\s*id|마이데이터|mydata|증명원|소득금액증명|소득금액증명원|주민등록등본|민원|발급)/iu
const MOBILE_ID_RE = /(mobile\s*id|모바일\s*(?:신분증|id)|mobile_id)/iu
const SIMPLE_AUTH_RE =
  /(simple_auth|간편인증|ganpyeon|소득금액증명|증명원|민원|발급)/iu
const MYDATA_RE = /(mydata|마이데이터)/iu
const GOV24_MINWON_SUBMIT_RE =
  /(?=.*(?:정부24|gov24))(?=.*(?:주민등록등본|등본|민원|발급))(?=.*(?:신청|접수|발급|submit|apply|issue))/iu
const MEDICAL_COLLAPSE_RE =
  /(사람이\s*쓰러|쓰러졌|쓰러짐|쓰러져|의식[을이가은는\s]*(없|잃|불명)|무의식|심정지|심폐소생|cpr|호흡\s*(없|곤란)|숨\s*(안|못)|collapse|collapsed|unconscious|cardiac\s*arrest|not\s*breathing|aed|자동심장|심장충격|제세동)/iu
const MEDICAL_COLLAPSE_OR_ER_RE =
  /(사람이\s*쓰러|쓰러졌|쓰러짐|쓰러져|의식[을이가은는\s]*(없|잃|불명)|무의식|심정지|심폐소생|cpr|호흡\s*(없|곤란)|숨\s*(안|못)|collapse|collapsed|unconscious|cardiac\s*arrest|not\s*breathing|응급실|응급의료기관|응급의료센터|emergency\s*room|\ber\b)/iu
const NON_MEDICAL_EMERGENCY_RE =
  /(비상벨|안심벨|emergency\s*(call\s*)?box|call\s*box)/iu
const TAGO_BUS_RE =
  /(버스|시내버스|정류장|정류소|노선|도착|언제\s*와|몇\s*분|bus|route|arrival|station)/iu
const TAGO_ROUTE_NO_RE = /(?:^|[^\d])(\d{1,4}(?:-\d)?)\s*번/u
const TAGO_PLACE_RE = /([가-힣A-Za-z0-9().·\s]+?)(?:에서|근처|앞|인근)/u
const PPS_BID_RE = /(입찰|나라장터|조달청|공고|공사조회|전기공사|bid|procurement)/iu
const AIRKOREA_RE =
  /(미세먼지|초미세먼지|초미세|대기질|대기오염|공기질|마스크|pm\s*2\.?5|pm\s*10|air\s*korea|airkorea|air\s*quality|airquality)/iu
const DOCUMENT_PATH_RE =
  /(?:^|[\s:'"(])(?:~|\/|[A-Za-z]:\\|\.{1,2}\/)?[^\s:'"]*\.(?:hwpx|hwp|docx|pdf|xlsx|pptx)\b/iu
const DOCUMENT_EXPLICIT_PATH_SCAN_RE =
  /(?:^|[\s:'"(])((?:~|\/|[A-Za-z]:\\|\.{1,2}\/)[^\s:'"]+\.(hwpx|hwp|docx|pdf|xlsx|pptx))\b/giu
const DOCUMENT_FORMAT_RE = /\b(?:hwpx|hwp|docx|pdf|xlsx|pptx)\b/iu
const DOCUMENT_ARTIFACT_ID_RE =
  /(?:^|[\s"'`(])(?:artifact_id|artifact\s*id|artifact|아티팩트)?\s*((?:source|working|derivative|render|export|viewport)-[A-Za-z0-9][A-Za-z0-9_.-]{0,127})(?=$|[^A-Za-z0-9_.-])/iu
const DOCUMENT_INTENT_RE =
  /(문서|공문서|양식|서식|파일|작성|저장|렌더|미리보기|변경사항|\bdiff\b|\bcompact\b|\bdocument\b|\bfile\b|\bform\b|\brender\b|\bsave\b|\bwrite\b)/iu
const DOCUMENT_WRITE_RE =
  /(작성|수정|편집|채우|채워|입력|변경|저장|write|edit|fill|apply|save)/iu
const DOCUMENT_READ_ONLY_RE =
  /(읽기\s*전용|수정\s*없이|변경\s*없이|저장\s*없이|열람만|확인만|inspect|extract|read\s*only)/iu
const DOCUMENT_REVIEW_RE =
  /(diff|compact|변경사항|렌더|미리보기|render|viewport|page)/iu
const DOCUMENT_DIFF_ONLY_FINAL_RE =
  /(실제(?:로)?\s*바뀐\s*내용만|바뀐\s*내용만|변경된\s*부분만|변경사항만|actual\s+changed\s+content\s+only|only\s+changed)/iu
const DOCUMENT_DIFF_AND_SAVE_ONLY_FINAL_RE =
  /(실제(?:로)?\s*바뀐\s*내용\s*(?:과|및|랑|하고)\s*저장\s*(?:위치|경로)만|변경(?:된)?\s*(?:내용|부분|사항).{0,24}저장\s*(?:위치|경로)만|changed.{0,24}(?:save|saved).{0,24}(?:location|path).{0,24}only)/iu
const DOCUMENT_LOCAL_HINT_RE =
  /(다운로드|downloads?|폴더|파일|양식|서식|활동일지|신청서|등본|증명서)/iu
const PUBLIC_DATA_MISMATCH_TARGET_RE =
  /Public-data tool-choice mismatch:\s*target=([a-z_]+)/iu
const PUBLIC_DATA_MISMATCH_CALL_RE =
  /Public-data tool-choice mismatch:[\s\S]*?\bCall\s+([a-z][a-z0-9_]*)\s+/iu
const TAGO_BUS_COMPLETION_PROMPT =
  'TAGO bus arrival evidence chain complete: the route search, route passing-stop lookup, and arrival lookup have already been attempted for this bus-arrival request. Do not call another location, public-data, or TAGO bus tool in this turn. Write the final Korean answer now from the actual TAGO results only. If the arrival result has zero items, say that no current matching arrival is shown for the checked stop/direction, and include the route/stop evidence that was found.'
const TAGO_BUS_REPAIR_PROMPT =
  'TAGO bus final answer repair: the previous answer still promised another stop/route lookup after TAGO arrival evidence was already attempted. Rewrite the final Korean answer now from the actual TAGO tool_result only. Do not say 확인하겠습니다, 확인해보겠습니다, 검색해 보겠습니다, 다시 조회, or that you will check another stop. If the arrival result has zero items, say no current arrival is shown for the checked 부산역 stop and ask the citizen for a specific route number or exact stop only as a next-step option.'
const AIRKOREA_COMPLETION_PROMPT =
  'AirKorea air-quality evidence complete: the official AirKorea result has already returned for this 미세먼지/초미세먼지 request. Do not call another location, weather, public-data, or AirKorea tool in this turn. Write the final Korean answer now from the actual tool_result only. Include stationName, dataTime, PM10 value and pm10GradeLabelKo, PM2.5 value and pm25GradeLabelKo, and CAI/khaiValue with khaiGradeLabelKo when present. This result returns city/province measurement rows, not a geocoded nearest-station result: say it is city/province station data, use only exact stationName rows present in tool_result, and do not infer the citizen place district, distance, nearest station, station groups, or value ranges unless those exact fields exist in tool_result. If totalCount is 0 or items are empty, say the official AirKorea API returned no rows for the checked sidoName and do not say you are still checking.'
const AIRKOREA_REPAIR_PROMPT =
  'AirKorea final answer repair: the previous answer inferred nearest/direction/distance, average/range values, district groups, or changed raw values beyond the official tool_result. Rewrite the final Korean answer using only the exact AirKorea rows listed below. Do not say 가장 가까운, 인근, 동쪽, 서쪽, 남쪽, 북쪽, distance, nearest, 평균, 범위, 대부분, 해운대구 지역, or average unless those exact fields exist in tool_result. Copy PM10, PM2.5, CAI, stationName, dataTime, and grade labels literally. If the citizen named a place but the tool returned only city/province rows, say this is city/province station data rather than a nearest-station answer.'
const AIRKOREA_UNSUPPORTED_LOCATION_CLAIM_RE =
  /(가장\s*가까운|인근|동쪽|서쪽|남쪽|북쪽|거리|평균|범위|대부분|전체적으로|해운대구\s*지역|명확한\s*측정소|지역에\s*해당|nearest|distance|average|range)/iu
const TAGO_BUS_PENDING_FINAL_RE =
  /(확인해\s*보겠습니다|확인하겠습니다|검색해\s*보겠습니다|검색하겠습니다|다른\s*정류장|다시\s*(?:조회|확인|검색)|조회하겠습니다|will\s+check|will\s+search|will\s+look\s+up)/iu
const GENERIC_PENDING_FINAL_RE =
  /(답변을?\s*제공하겠습니다|제공하겠습니다|확인해\s*보겠습니다|확인하겠습니다|조회하겠습니다|찾아보겠습니다|검색해\s*보겠습니다|검색하겠습니다|최종\s*답변은|final answer should|will\s+(?:answer|provide|check|search|look\s+up))/iu
const GENERIC_PENDING_FINAL_REPAIR_PROMPT =
  'Final answer repair: successful tool_result evidence already exists, but the previous assistant message was still a plan or promise to answer later. Write the final Korean answer now from the actual tool_result values only. Do not say 제공하겠습니다, 확인하겠습니다, 조회하겠습니다, 찾아보겠습니다, 검색해 보겠습니다, or describe what you will answer next.'
const DOCUMENT_COMPLETION_PROMPT_MARKER = 'Document primitive result complete'
const DOCUMENT_COMPLETION_PROMPT =
  `${DOCUMENT_COMPLETION_PROMPT_MARKER}: the document tool_result for the latest citizen request is already visible in the TUI. Do not call another document, workspace, render, or tool-search tool in this turn. Answer in Korean only. Write the final Korean answer now from the actual tool_result only. Keep it to one or two short sentences: state whether the document was updated, blocked, failed, or needs explicit input; when the status is needs_input or the path is missing, ask the user to provide an exact existing file path or make an explicit selection; mention only changed field labels/values or required selection that are present in the visible diff; include the saved path only when the tool_result reports one. Do not invent units, parenthetical labels, workflow steps, style claims, or extra facts. Do not say an image, screenshot, viewport, render artifact, browser view, viewer, or visual artifact was generated. The inline TUI diff above is the user-visible proof.`

type DocumentFormat = 'hwpx' | 'hwp' | 'docx' | 'pdf' | 'xlsx' | 'pptx'

interface DocumentPathRef {
  path: string
  expectedFormat: DocumentFormat
}

export interface UmmayaTuiRepairPolicy {
  id: string
  kind: 'display_or_answer_repair'
  owner: string
  evidenceEvent: string
  removalCondition: string
}

export interface UmmayaBackendRepairReceipt {
  source: 'backend_route_decision' | 'backend_validation'
  reason: string
  evidenceEvent: string
  toolName?: string
}

export const UMMAYA_TUI_REPAIR_POLICIES: readonly UmmayaTuiRepairPolicy[] = [
  {
    id: 'document_observable_operation_backfill',
    kind: 'display_or_answer_repair',
    owner: 'ummaya:tui-display-repair',
    evidenceEvent: 'ummaya.tui.repair.document_observable_operation_backfill',
    removalCondition:
      'Delete when document adapters emit display_operation in backend tool-use receipts.',
  },
  {
    id: 'document_completion_prompt',
    kind: 'display_or_answer_repair',
    owner: 'ummaya:tui-answer-repair',
    evidenceEvent: 'ummaya.tui.repair.document_completion_prompt',
    removalCondition:
      'Delete when backend RouteDecision stop reasons emit terminal document answer instructions.',
  },
  {
    id: 'tago_bus_followup_prompt',
    kind: 'display_or_answer_repair',
    owner: 'ummaya:tui-answer-repair',
    evidenceEvent: 'ummaya.tui.repair.tago_bus_followup_prompt',
    removalCondition:
      'Delete when backend route decisions encode TAGO chain prerequisites and next required adapter.',
  },
  {
    id: 'tago_bus_completion_prompt',
    kind: 'display_or_answer_repair',
    owner: 'ummaya:tui-answer-repair',
    evidenceEvent: 'ummaya.tui.repair.tago_bus_completion_prompt',
    removalCondition:
      'Delete when TAGO adapters return a backend terminal answer contract.',
  },
  {
    id: 'airkorea_completion_prompt',
    kind: 'display_or_answer_repair',
    owner: 'ummaya:tui-answer-repair',
    evidenceEvent: 'ummaya.tui.repair.airkorea_completion_prompt',
    removalCondition:
      'Delete when AirKorea adapter output includes backend answer-synthesis constraints.',
  },
  {
    id: 'generic_pending_final_answer_repair',
    kind: 'display_or_answer_repair',
    owner: 'ummaya:tui-answer-repair',
    evidenceEvent: 'ummaya.tui.repair.generic_pending_final_answer_repair',
    removalCondition:
      'Delete when backend stop reasons reject plan-only final answers after tool_result evidence.',
  },
]

function hasBackendRepairReceipt(
  receipt: UmmayaBackendRepairReceipt | undefined,
): boolean {
  return (
    receipt !== undefined &&
    (receipt.source === 'backend_route_decision' ||
      receipt.source === 'backend_validation') &&
    receipt.reason.trim() !== '' &&
    receipt.evidenceEvent.startsWith('ummaya.')
  )
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : undefined
}

function messageRecord(message: unknown): Record<string, unknown> | undefined {
  return asRecord(asRecord(message)?.message)
}

function messageRole(message: unknown): string | undefined {
  const outer = asRecord(message)
  const inner = messageRecord(message)
  if (typeof inner?.role === 'string') return inner.role
  if (typeof outer?.role === 'string') return outer.role
  return typeof outer?.type === 'string' ? outer.type : undefined
}

function messageContent(message: unknown): unknown {
  return messageRecord(message)?.content ?? asRecord(message)?.content
}

function assistantPreludeTextFromContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map(block => {
      if (typeof block === 'string') return block
      if (typeof block !== 'object' || block === null) return ''
      const record = block as Record<string, unknown>
      if (typeof record.text === 'string') return record.text
      return typeof record.thinking === 'string' ? record.thinking : ''
    })
    .filter(Boolean)
    .join('\n')
}

function latestUserText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== 'user') continue
    const text = textFromContent(messageContent(message))
    if (isNonSyntheticUserMessageText(message, text)) return text
  }
  return ''
}

function latestUserMessageIndex(messages: readonly unknown[]): number {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== 'user') continue
    const text = textFromContent(messageContent(message))
    if (isNonSyntheticUserMessageText(message, text)) return idx
  }
  return -1
}

function toolUseNames(messages: readonly unknown[]): Set<string> {
  const names = new Set<string>()
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type === 'tool_use') {
        const input = asRecord(record.input)
        const nestedToolName =
          typeof input?.tool_id === 'string' ? input.tool_id : undefined
        if (nestedToolName) names.add(nestedToolName)
        else if (typeof record.name === 'string') names.add(record.name)
        continue
      }
      if (record?.type !== 'tool_result') continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      const source = asRecord(asRecord(parsed?.result)?.meta)?.source
      if (typeof source === 'string') names.add(source)
    }
  }
  return names
}

function latestToolResultText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const content = messageContent(messages[idx])
    if (!Array.isArray(content)) continue
    const parts: string[] = []
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (typeof record.content === 'string') {
        parts.push(record.content)
      } else {
        const text = textFromContent(record.content)
        if (text.trim()) parts.push(text)
      }
    }
    if (parts.length > 0) return parts.join('\n')
  }
  return ''
}

function latestAssistantText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    if (messageRole(messages[idx]) !== 'assistant') continue
    const text = textFromContent(messageContent(messages[idx]))
    if (text.trim()) return text
  }
  return ''
}

function hasAirKoreaRepairPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message => textFromContent(messageContent(message)).includes('AirKorea final answer repair'))
}

function hasTagoBusRepairPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message => textFromContent(messageContent(message)).includes('TAGO bus final answer repair'))
}

function hasGenericPendingFinalRepairPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message => textFromContent(messageContent(message)).includes('Final answer repair: successful tool_result'))
}

function hasDocumentCompletionPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message =>
    textFromContent(messageContent(message)).includes(DOCUMENT_COMPLETION_PROMPT_MARKER),
  )
}

function hasToolResult(messages: readonly unknown[]): boolean {
  return messages.some(message => {
    const content = messageContent(message)
    if (!Array.isArray(content)) return false
    return content.some(block => asRecord(block)?.type === 'tool_result')
  })
}

function toolResultTextsFor(
  messages: readonly unknown[],
  toolName: string,
): string[] {
  const idToName = toolUseById(messages)
  const texts: string[] = []
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (typeof record.tool_use_id !== 'string') continue
      const mappedToolName = idToName.get(record.tool_use_id)
      if (mappedToolName === toolName) {
        if (typeof record.content === 'string') texts.push(record.content)
        continue
      }
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      const source = asRecord(asRecord(parsed?.result)?.meta)?.source
      if (source === toolName) texts.push(record.content)
    }
  }
  return texts
}

function isDocumentHarnessQuery(text: string): boolean {
  return DOCUMENT_PATH_RE.test(text) ||
    ((DOCUMENT_FORMAT_RE.test(text) || DOCUMENT_ARTIFACT_ID_RE.test(text)) &&
      DOCUMENT_INTENT_RE.test(text)) ||
    (DOCUMENT_INTENT_RE.test(text) &&
      DOCUMENT_WRITE_RE.test(text) &&
      DOCUMENT_LOCAL_HINT_RE.test(text))
}

function hasExplicitDocumentLocator(text: string): boolean {
  return DOCUMENT_PATH_RE.test(text) || DOCUMENT_ARTIFACT_ID_RE.test(text)
}

function shouldExploreDocumentPathWithGlob(
  userText: string,
  messages: readonly unknown[],
): boolean {
  if (!isDocumentHarnessQuery(userText)) return false
  if (hasExplicitDocumentLocator(userText)) return false
  if (!DOCUMENT_LOCAL_HINT_RE.test(userText)) return false
  const latestUserIndex = latestUserMessageIndex(messages)
  for (let index = Math.max(0, latestUserIndex + 1); index < messages.length; index += 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_use') continue
      if (
        record.name === WORKSPACE_GLOB_TOOL_NAME ||
        record.name === LEGACY_GLOB_TOOL_NAME
      ) {
        return false
      }
    }
  }
  return true
}

function explicitDocumentPathRefs(userText: string): DocumentPathRef[] {
  return [...userText.matchAll(DOCUMENT_EXPLICIT_PATH_SCAN_RE)].map(match => ({
    path: match[1]!,
    expectedFormat: match[2]!.toLowerCase() as DocumentFormat,
  }))
}

function stableDocumentCorrelationId(userText: string): string {
  let hash = 0x811c9dc5
  for (let index = 0; index < userText.length; index += 1) {
    hash ^= userText.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return `client-forced-document-${(hash >>> 0).toString(16).padStart(8, '0')}`
}

function forcedDocumentInputFromExplicitPath(
  userText: string,
): Record<string, unknown> | undefined {
  if (!isDocumentHarnessQuery(userText)) return undefined
  const wantsWrite =
    DOCUMENT_WRITE_RE.test(userText) && !DOCUMENT_READ_ONLY_RE.test(userText)
  const wantsReview = DOCUMENT_REVIEW_RE.test(userText)
  const wantsReadOnly = DOCUMENT_READ_ONLY_RE.test(userText)
  if (!wantsWrite && !wantsReview && !wantsReadOnly) return undefined

  const paths = explicitDocumentPathRefs(userText)
  const source = paths[0]
  if (!source) return undefined

  const input: Record<string, unknown> = {
    correlation_id: stableDocumentCorrelationId(userText),
    document: {
      path: source.path,
      expected_format: source.expectedFormat,
    },
    operation: wantsWrite ? 'fill' : 'inspect',
    instruction: userText,
  }
  const destination = paths.find(candidate => candidate.path !== source.path)
  if (destination && wantsWrite) {
    input.destination_path = destination.path
  }
  return input
}

function workspaceGlobToolName(available: ReadonlySet<string>): string | undefined {
  if (available.has(WORKSPACE_GLOB_TOOL_NAME)) return WORKSPACE_GLOB_TOOL_NAME
  if (available.has(LEGACY_GLOB_TOOL_NAME)) return LEGACY_GLOB_TOOL_NAME
  return undefined
}

function isSuccessfulDocumentToolPayload(
  value: unknown,
  toolNames: ReadonlySet<string>,
): boolean {
  if (Array.isArray(value)) {
    return value.some(item => isSuccessfulDocumentToolPayload(item, toolNames))
  }
  const record = asRecord(value)
  if (!record) return false
  const toolId = typeof record.tool_id === 'string' ? record.tool_id : undefined
  if (toolId !== undefined && toolNames.has(toolId)) {
    const status = typeof record.status === 'string' ? record.status.toLowerCase() : 'ok'
    const okFlag = typeof record.ok === 'boolean' ? record.ok : true
    const hasError =
      record.kind === 'error' ||
      typeof record.error === 'string' ||
      asRecord(record.error) !== undefined
    return (
      okFlag &&
      !hasError &&
      ['ok', 'succeeded', 'completed', 'ready'].includes(status)
    )
  }
  return Object.values(record).some(item =>
    isSuccessfulDocumentToolPayload(item, toolNames),
  )
}

function hasSuccessfulDocumentToolResultAfter(
  messages: readonly unknown[],
  toolNames: ReadonlySet<string>,
  afterIndex: number,
): boolean {
  for (let index = Math.max(0, afterIndex + 1); index < messages.length; index += 1) {
    const message = messages[index]
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (record.is_error === true) continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      if (isSuccessfulDocumentToolPayload(parsed, toolNames)) return true
    }
  }
  return false
}

function isTerminalDocumentToolPayload(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some(isTerminalDocumentToolPayload)
  }
  const record = asRecord(value)
  if (!record) return false
  const toolId = typeof record.tool_id === 'string' ? record.tool_id : undefined
  if (toolId === DOCUMENT_TOOL_NAME) {
    const status = typeof record.status === 'string' ? record.status.toLowerCase() : 'ok'
    return status === 'ok' || status === 'blocked' || status === 'failed' || status === 'needs_input'
  }
  if (toolId !== undefined && toolId.startsWith('document_')) {
    const status = typeof record.status === 'string' ? record.status.toLowerCase() : 'ok'
    if (status === 'blocked' || status === 'failed' || status === 'needs_input') {
      return true
    }
    return toolId === DOCUMENT_RENDER_TOOL_NAME && status === 'ok'
  }
  return Object.values(record).some(isTerminalDocumentToolPayload)
}

function hasTerminalDocumentToolResultAfter(
  messages: readonly unknown[],
  afterIndex: number,
): boolean {
  for (let index = Math.max(0, afterIndex + 1); index < messages.length; index += 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      if (isTerminalDocumentToolPayload(parsed)) return true
    }
  }
  return false
}

function hasTerminalDocumentPrimitiveToolResultAfter(
  messages: readonly unknown[],
  afterIndex: number,
): boolean {
  for (let index = Math.max(0, afterIndex + 1); index < messages.length; index += 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      if (isTerminalDocumentPrimitivePayload(parsed)) return true
    }
  }
  return false
}

function isTerminalDocumentPrimitivePayload(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some(isTerminalDocumentPrimitivePayload)
  }
  const record = asRecord(value)
  if (!record) return false
  const toolId = typeof record.tool_id === 'string' ? record.tool_id : undefined
  if (toolId === DOCUMENT_TOOL_NAME) {
    const status = typeof record.status === 'string' ? record.status.toLowerCase() : 'ok'
    return status === 'ok' || status === 'blocked' || status === 'failed' || status === 'needs_input'
  }
  return Object.values(record).some(isTerminalDocumentPrimitivePayload)
}

function isDocumentAnswerSynthesisPayload(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some(isDocumentAnswerSynthesisPayload)
  }
  const record = asRecord(value)
  if (!record) return false
  const toolId = typeof record.tool_id === 'string' ? record.tool_id : undefined
  if (toolId === DOCUMENT_TOOL_NAME) {
    const status = typeof record.status === 'string' ? record.status.toLowerCase() : 'ok'
    return status === 'ok' || status === 'blocked' || status === 'failed' || status === 'needs_input'
  }
  if (toolId === DOCUMENT_RENDER_TOOL_NAME) {
    const status = typeof record.status === 'string' ? record.status.toLowerCase() : 'ok'
    return status === 'ok'
  }
  return Object.values(record).some(isDocumentAnswerSynthesisPayload)
}

function latestDocumentResultPayloadAfter(
  messages: readonly unknown[],
  afterIndex: number,
): Record<string, unknown> | undefined {
  for (let index = messages.length - 1; index >= Math.max(0, afterIndex + 1); index -= 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (let blockIndex = content.length - 1; blockIndex >= 0; blockIndex -= 1) {
      const record = asRecord(content[blockIndex])
      if (record?.type !== 'tool_result') continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      const payload = findDocumentResultPayload(parsed)
      if (payload !== undefined) return payload
    }
  }
  return undefined
}

function findDocumentResultPayload(value: unknown): Record<string, unknown> | undefined {
  if (Array.isArray(value)) {
    for (let index = value.length - 1; index >= 0; index -= 1) {
      const payload = findDocumentResultPayload(value[index])
      if (payload !== undefined) return payload
    }
    return undefined
  }
  const record = asRecord(value)
  if (!record) return undefined
  const toolId = typeof record.tool_id === 'string' ? record.tool_id : undefined
  if (toolId === DOCUMENT_TOOL_NAME || toolId === DOCUMENT_RENDER_TOOL_NAME) {
    return record
  }
  for (const nested of Object.values(record).reverse()) {
    const payload = findDocumentResultPayload(nested)
    if (payload !== undefined) return payload
  }
  return undefined
}

function documentDiffOnlyCompletionPrompt(
  userText: string,
  messages: readonly unknown[],
): string | undefined {
  const result = latestDocumentResultPayloadAfter(
    messages,
    latestUserMessageIndex(messages),
  )
  if (DOCUMENT_DIFF_AND_SAVE_ONLY_FINAL_RE.test(userText)) {
    return documentDiffAndSaveOnlyCompletionPrompt(result)
  }
  if (!DOCUMENT_DIFF_ONLY_FINAL_RE.test(userText)) return undefined
  return documentDiffOnlyCompletionPromptFromResult(result)
}

function documentDiffOnlyCompletionPromptFromResult(
  result: Record<string, unknown> | undefined,
): string | undefined {
  const diff = asRecord(result?.diff)
  const changes = Array.isArray(diff?.changes) ? diff.changes : []
  const lines = changes
    .map(change => {
      const record = asRecord(change)
      if (!record) return undefined
      const targetPath = String(record.target_path ?? 'document')
      const beforeValue = String(record.before_value ?? '')
      const afterValue = String(record.after_value ?? '')
      return `- ${targetPath}: ${beforeValue} -> ${afterValue}`
    })
    .filter((line): line is string => line !== undefined)
  if (lines.length === 0) return undefined
  return [
    `${DOCUMENT_COMPLETION_PROMPT_MARKER}: the document tool_result for the latest citizen request is already visible in the TUI.`,
    'The citizen explicitly requested only the actually changed content.',
    'Reply in Korean with exactly these lines and nothing else:',
    '실제 변경된 내용:',
    ...lines,
    'Do not add document status, save/render/browser/artifact/viewer details, workflow summaries, visual diff explanations, or any extra sentence.',
  ].join('\n')
}

function documentDiffAndSaveOnlyCompletionPrompt(
  result: Record<string, unknown> | undefined,
): string | undefined {
  const diff = asRecord(result?.diff)
  const changes = Array.isArray(diff?.changes) ? diff.changes : []
  const changeLines = changes
    .map(change => {
      const record = asRecord(change)
      if (!record) return undefined
      const targetPath = String(record.target_path ?? 'document')
      const beforeValue = String(record.before_value ?? '')
      const afterValue = String(record.after_value ?? '')
      return `- ${targetPath}: ${beforeValue} -> ${afterValue}`
    })
    .filter((line): line is string => line !== undefined)
  if (changeLines.length === 0) return undefined

  const savedExports = Array.isArray(result?.saved_exports)
    ? result.saved_exports
    : []
  const saveLines = savedExports
    .map(savedExport => {
      const record = asRecord(savedExport)
      const localPath = record?.local_path
      return typeof localPath === 'string' && localPath.trim()
        ? `- ${localPath}`
        : undefined
    })
    .filter((line): line is string => line !== undefined)
  const lines = [
    `${DOCUMENT_COMPLETION_PROMPT_MARKER}: the document tool_result for the latest citizen request is already visible in the TUI.`,
    'The citizen explicitly requested only the actually changed content and save location.',
    'Reply in Korean with exactly these lines and nothing else:',
    '실제 변경된 내용:',
    ...changeLines,
  ]
  if (saveLines.length > 0) {
    lines.push('저장 위치:', ...saveLines)
  } else {
    lines.push('Do not mention 저장 위치 or any saved path because saved_exports is absent.')
  }
  lines.push(
    'Do not add document status, render/browser/artifact/viewer details, workflow summaries, visual diff explanations, or any extra sentence.',
  )
  return lines.join('\n')
}

function hasDocumentAnswerSynthesisResultAfter(
  messages: readonly unknown[],
  afterIndex: number,
): boolean {
  for (let index = Math.max(0, afterIndex + 1); index < messages.length; index += 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      if (isDocumentAnswerSynthesisPayload(parsed)) return true
    }
  }
  return false
}

function selectDocumentWorkflowTargetToolName(
  userText: string,
  messages: readonly unknown[],
): string | undefined {
  if (!isDocumentHarnessQuery(userText)) return undefined
  const wantsWrite =
    DOCUMENT_WRITE_RE.test(userText) && !DOCUMENT_READ_ONLY_RE.test(userText)
  const wantsReview = DOCUMENT_REVIEW_RE.test(userText)
  const wantsReadOnly = DOCUMENT_READ_ONLY_RE.test(userText)
  if (!wantsWrite && !wantsReview && !wantsReadOnly) return undefined
  const latestUserIndex = latestUserMessageIndex(messages)
  const hasDocumentForLatestRequest = hasTerminalDocumentPrimitiveToolResultAfter(
    messages,
    latestUserIndex,
  )

  return hasDocumentForLatestRequest ? undefined : DOCUMENT_TOOL_NAME
}

function selectDocumentWorkflowToolChoice(
  userText: string,
  available: Set<string>,
  messages: readonly unknown[],
): string | undefined {
  const globToolName = workspaceGlobToolName(available)
  if (
    globToolName !== undefined &&
    shouldExploreDocumentPathWithGlob(userText, messages)
  ) {
    return globToolName
  }
  const target = selectDocumentWorkflowTargetToolName(userText, messages)
  if (target === undefined) return undefined
  if (isAvailableOrSyncedAdapter(available, target)) return target
  return available.has(TOOL_SEARCH_TOOL_NAME) ? TOOL_SEARCH_TOOL_NAME : undefined
}

export interface ForcedUmmayaToolUse {
  name: string
  input: Record<string, unknown>
}

export function repairUmmayaExplicitDocumentToolUseFromUserQuery({
  toolName,
  input,
  messages,
  tools,
  backendRepairReceipt,
}: {
  toolName: string
  input: Record<string, unknown>
  messages: readonly Message[]
  tools: Tools
  backendRepairReceipt?: UmmayaBackendRepairReceipt
}): ForcedUmmayaToolUse | undefined {
  if (!hasBackendRepairReceipt(backendRepairReceipt)) return undefined
  const available = availableToolNamesFromTools(tools)
  if (!isAvailableOrSyncedAdapter(available, DOCUMENT_TOOL_NAME)) return undefined

  const userText = latestUserText(messages)
  if (!hasExplicitDocumentLocator(userText)) return undefined

  const forced = forcedDocumentInputFromExplicitPath(userText)
  if (!forced) return undefined
  if (toolName === DOCUMENT_TOOL_NAME) {
    const forcedOperation = typeof forced.operation === 'string'
      ? forced.operation
      : undefined
    const operation = typeof input.operation === 'string'
      ? input.operation
      : undefined
    const hasExplicitMutationPayload =
      Array.isArray(input.patches) ||
      Array.isArray(input.styles) ||
      typeof input.destination_path === 'string'
    if (forcedOperation === operation || (
      forcedOperation !== 'inspect' &&
      hasExplicitMutationPayload
    )) {
      return undefined
    }
  }
  return {
    name: DOCUMENT_TOOL_NAME,
    input: forced,
  }
}

export function backfillUmmayaObservableToolInputFromUserQuery({
  toolName,
  input,
  messages,
}: {
  toolName: string
  input: Record<string, unknown>
  messages: readonly Message[]
}): void {
  if (toolName !== DOCUMENT_TOOL_NAME) return
  const operation = typeof input.operation === 'string' ? input.operation : undefined
  if (operation !== 'inspect' && operation !== 'extract') return

  const userText = latestUserText(messages)
  if (!isDocumentHarnessQuery(userText)) return
  if (!DOCUMENT_WRITE_RE.test(userText) || DOCUMENT_READ_ONLY_RE.test(userText)) return
  if (!hasExplicitDocumentLocator(userText)) return

  input.__ummaya_display_operation = 'fill'
}

export function selectUmmayaClientForcedToolUse({
  messages,
  tools,
  backendRepairReceipt,
}: {
  messages: readonly Message[]
  tools: Tools
  backendRepairReceipt?: UmmayaBackendRepairReceipt
}): ForcedUmmayaToolUse | undefined {
  if (!hasBackendRepairReceipt(backendRepairReceipt)) return undefined
  const available = availableToolNamesFromTools(tools)
  const userText = latestUserText(messages)
  const documentToolName = selectDocumentWorkflowTargetToolName(
    userText,
    messages,
  )
  if (
    documentToolName !== undefined &&
    !isAvailableOrSyncedAdapter(available, documentToolName) &&
    available.has(TOOL_SEARCH_TOOL_NAME)
  ) {
    return {
      name: TOOL_SEARCH_TOOL_NAME,
      input: {
        query: DOCUMENT_TOOL_LOAD_QUERY,
        max_results: 1,
      },
    }
  }
  if (
    documentToolName !== undefined &&
    isAvailableOrSyncedAdapter(available, documentToolName)
  ) {
    const input = forcedDocumentInputFromExplicitPath(userText)
    if (input) {
      return {
        name: DOCUMENT_TOOL_NAME,
        input,
      }
    }
  }
  return undefined
}

export function shouldCompleteAfterSuccessfulDocumentRender({
  messages,
}: {
  messages: readonly Message[]
}): boolean {
  const userText = latestUserText(messages)
  if (!isDocumentHarnessQuery(userText)) return false
  if (!DOCUMENT_REVIEW_RE.test(userText)) return false
  if (!DOCUMENT_ARTIFACT_ID_RE.test(userText)) return false
  const latestUserIndex = latestUserMessageIndex(messages)
  return hasSuccessfulDocumentToolResultAfter(
    messages,
    new Set([DOCUMENT_TOOL_NAME, DOCUMENT_RENDER_TOOL_NAME]),
    latestUserIndex,
  )
}

export function shouldCompleteAfterTerminalDocumentToolResult({
  messages,
}: {
  messages: readonly Message[]
}): boolean {
  const userText = latestUserText(messages)
  if (!isDocumentHarnessQuery(userText)) return false
  return hasDocumentAnswerSynthesisResultAfter(
    messages,
    latestUserMessageIndex(messages),
  )
}

export function buildDocumentCompletionPromptIfNeeded({
  messages,
}: {
  messages: readonly Message[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!isDocumentHarnessQuery(userText)) return undefined
  if (hasDocumentCompletionPrompt(messages)) return undefined
  if (!hasTerminalDocumentToolResultAfter(
    messages,
    latestUserMessageIndex(messages),
  )) return undefined
  return (
    documentDiffOnlyCompletionPrompt(userText, messages) ??
    DOCUMENT_COMPLETION_PROMPT
  )
}

function toolUseById(messages: readonly unknown[]): Map<string, string> {
  const ids = new Map<string, string>()
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_use') continue
      if (typeof record.id !== 'string' || typeof record.name !== 'string') {
        continue
      }
      const input = asRecord(record.input)
      const nestedToolName =
        typeof input?.tool_id === 'string' ? input.tool_id : undefined
      ids.set(record.id, nestedToolName ?? record.name)
    }
  }
  return ids
}

function parseJsonRecord(value: string): Record<string, unknown> | undefined {
  try {
    return asRecord(JSON.parse(value))
  } catch {
    return undefined
  }
}

function stringField(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key]
  if (value === null || value === undefined) return undefined
  const text = String(value).trim()
  return text === '' ? undefined : text
}

function airKoreaExactRowsSummary(messages: readonly unknown[]): string | undefined {
  const rows: string[] = []
  for (const text of toolResultTextsFor(messages, AIRKOREA_TOOL_NAME)) {
    const parsed = parseJsonRecord(text)
    const result = asRecord(parsed?.result)
    const items = Array.isArray(result?.items) ? result.items : []
    for (const item of items) {
      const record = asRecord(asRecord(item)?.record)
      if (!record) continue
      const stationName = stringField(record, 'stationName')
      const dataTime = stringField(record, 'dataTime')
      const pm10Value = stringField(record, 'pm10Value')
      const pm10Grade = stringField(record, 'pm10GradeLabelKo')
      const pm25Value = stringField(record, 'pm25Value')
      const pm25Grade = stringField(record, 'pm25GradeLabelKo')
      const khaiValue = stringField(record, 'khaiValue')
      const khaiGrade = stringField(record, 'khaiGradeLabelKo')
      if (!stationName) continue
      rows.push(
        `- ${stationName}: dataTime=${dataTime ?? '없음'}, PM10=${pm10Value ?? '없음'}${pm10Grade ? `(${pm10Grade})` : ''}, PM2.5=${pm25Value ?? '없음'}${pm25Grade ? `(${pm25Grade})` : ''}, CAI=${khaiValue ?? '없음'}${khaiGrade ? `(${khaiGrade})` : ''}`,
      )
      if (rows.length >= 8) break
    }
    if (rows.length >= 8) break
  }
  if (rows.length === 0) return undefined
  return `\n\nExact AirKorea rows you may cite verbatim:\n${rows.join('\n')}`
}

function hasSuccessfulRegionLocateResult(messages: readonly unknown[]): boolean {
  const idToName = toolUseById(messages)
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (record.is_error === true) continue
      if (typeof record.tool_use_id !== 'string') continue
      const toolName = idToName.get(record.tool_use_id)
      if (toolName !== 'locate' && !toolName?.startsWith('kakao_')) continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      if (parsed?.ok === false) continue
      const result = asRecord(parsed?.result ?? parsed)
      if (result?.kind !== 'region') continue
      if (
        typeof result.region_1depth_name === 'string' &&
        typeof result.region_2depth_name === 'string'
      ) {
        return true
      }
    }
  }
  return false
}

function hasSuccessfulPoiLocateResult(messages: readonly unknown[]): boolean {
  const idToName = toolUseById(messages)
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (record.is_error === true) continue
      if (typeof record.tool_use_id !== 'string') continue
      const toolName = idToName.get(record.tool_use_id)
      if (toolName !== 'locate' && !toolName?.startsWith('kakao_')) continue
      if (typeof record.content !== 'string') continue
      const parsed = parseJsonRecord(record.content)
      if (parsed?.ok === false) continue
      const result = asRecord(parsed?.result ?? parsed)
      if (result?.kind !== 'poi') continue
      if (typeof result.lat === 'number' && typeof result.lon === 'number') {
        return true
      }
    }
  }
  return false
}

function availableToolNamesFromTools(tools: Tools): Set<string> {
  return new Set(tools.map(tool => tool.name))
}

function isAvailableOrSyncedAdapter(
  available: Set<string>,
  toolName: string,
): boolean {
  return available.has(toolName) || resolveAdapter(toolName) !== undefined
}

function chooseAvailableOrSyncedAdapter(
  available: Set<string>,
  candidates: readonly string[],
): string | undefined {
  return candidates.find(candidate => isAvailableOrSyncedAdapter(available, candidate))
}

function isAirportAviationQuery(text: string): boolean {
  return AIRPORT_PLACE_RE.test(text) && AIRPORT_AVIATION_RE.test(text)
}

function isMedicalCollapseQuery(text: string): boolean {
  return MEDICAL_COLLAPSE_RE.test(text) && !NON_MEDICAL_EMERGENCY_RE.test(text)
}

function routeNoFromUserText(text: string): string | undefined {
  return TAGO_ROUTE_NO_RE.exec(text)?.[1]
}

function placeNameFromUserText(text: string): string | undefined {
  const match = TAGO_PLACE_RE.exec(text)
  const place = match?.[1]?.trim()
  if (!place) return undefined
  return place.replace(/\s+/gu, ' ')
}

function isTagoRoutePlaceQuery(text: string): boolean {
  return TAGO_BUS_RE.test(text) && routeNoFromUserText(text) !== undefined
}

function isTagoBusQuery(text: string): boolean {
  return TAGO_BUS_RE.test(text)
}

function isTagoBusOriginDestinationQuery(text: string): boolean {
  if (!isTagoBusQuery(text) || routeNoFromUserText(text) !== undefined) return false
  return /에서[\s\S]{1,50}(?:까지|으로|로|가는|가려고|가야|가려면|이동|방향|행)/u.test(
    text,
  )
}

function hasSuccessfulStationSearch(messages: readonly unknown[]): boolean {
  return toolResultTextsFor(messages, TAGO_STATION_TOOL_NAME).some(
    text => text.includes('"ok":true') && text.includes('"nodeid"'),
  )
}

function hasSuccessfulRouteSearch(messages: readonly unknown[]): boolean {
  return toolResultTextsFor(messages, TAGO_ROUTE_TOOL_NAME).some(
    text => text.includes('"ok":true') && text.includes('"routeid"'),
  )
}

function hasSuccessfulRouteStationSearch(messages: readonly unknown[]): boolean {
  return toolResultTextsFor(messages, TAGO_ROUTE_STATION_TOOL_NAME).some(
    text => text.includes('"ok":true') && text.includes('"nodeid"'),
  )
}

function selectTagoBusToolChoice(
  userText: string,
  available: Set<string>,
  usedToolNames: Set<string>,
  messages: readonly unknown[],
): string | undefined {
  if (!isTagoBusQuery(userText)) return undefined
  if (routeNoFromUserText(userText) === undefined) {
    if (
      !usedToolNames.has(TAGO_STATION_TOOL_NAME) &&
      isAvailableOrSyncedAdapter(available, TAGO_STATION_TOOL_NAME)
    ) {
      return TAGO_STATION_TOOL_NAME
    }
    if (isTagoBusOriginDestinationQuery(userText)) {
      return undefined
    }
    if (
      hasSuccessfulStationSearch(messages) &&
      !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME) &&
      isAvailableOrSyncedAdapter(available, TAGO_ARRIVAL_TOOL_NAME)
    ) {
      return TAGO_ARRIVAL_TOOL_NAME
    }
    return undefined
  }
  if (
    !usedToolNames.has(TAGO_ROUTE_TOOL_NAME) &&
    isAvailableOrSyncedAdapter(available, TAGO_ROUTE_TOOL_NAME)
  ) {
    return TAGO_ROUTE_TOOL_NAME
  }
  if (
    hasSuccessfulRouteSearch(messages) &&
    !usedToolNames.has(TAGO_ROUTE_STATION_TOOL_NAME) &&
    isAvailableOrSyncedAdapter(available, TAGO_ROUTE_STATION_TOOL_NAME)
  ) {
    return TAGO_ROUTE_STATION_TOOL_NAME
  }
  if (
    hasSuccessfulRouteStationSearch(messages) &&
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME) &&
    isAvailableOrSyncedAdapter(available, TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return TAGO_ARRIVAL_TOOL_NAME
  }
  return undefined
}

export function buildTagoBusFollowupPromptIfNeeded({
  messages,
  availableToolNames,
}: {
  messages: readonly unknown[]
  availableToolNames: Iterable<string>
}): string | undefined {
  const userText = latestUserText(messages)
  if (!isTagoBusQuery(userText)) return undefined
  const available = new Set(availableToolNames)
  const usedToolNames = toolUseNames(messages)
  const routeNo = routeNoFromUserText(userText)
  const placeName = placeNameFromUserText(userText) ?? 'the citizen-named place'
  if (
    routeNo === undefined &&
    isTagoBusOriginDestinationQuery(userText) &&
    hasSuccessfulStationSearch(messages) &&
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return (
      'TAGO bus origin-destination limitation: the citizen asked for an origin-to-destination trip without a route number. ' +
      'The available TAGO adapters expose stop search, route-number search, route passing stops, and stop-based current arrivals; ' +
      'they do not prove an origin-destination route from stop arrivals alone. Do not call tago_bus_arrival_search for this OD request. ' +
      'Write the final Korean answer now from the station evidence, explain that current TAGO tools need a route number or exact stop/route to check arrivals, ' +
      'and do not claim that a bus route to the destination was found.'
    )
  }
  if (
    routeNo === undefined &&
    hasSuccessfulStationSearch(messages) &&
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME) &&
    available.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return (
      'Required follow-up for this TAGO bus chain: the station search has returned nodeid. ' +
      `Before any final answer, call ${TAGO_ARRIVAL_TOOL_NAME} with city_code:"21" ` +
      'and the best matching node_id from the station result to get current arrivals. ' +
      'Do not switch to route search unless the citizen named a route number.'
    )
  }
  if (
    routeNo !== undefined &&
    hasSuccessfulRouteSearch(messages) &&
    !usedToolNames.has(TAGO_ROUTE_STATION_TOOL_NAME) &&
    available.has(TAGO_ROUTE_STATION_TOOL_NAME)
  ) {
    return (
      'Required follow-up for this TAGO bus chain: the route search has returned route_id. ' +
      `Before any final answer, call ${TAGO_ROUTE_STATION_TOOL_NAME} with city_code:"21", ` +
      `that route_id, and node_nm:"${placeName}" to find the route's passing stop nodeid.`
    )
  }
  if (
    routeNo !== undefined &&
    hasSuccessfulRouteStationSearch(messages) &&
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME) &&
    available.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return (
      'Required follow-up for this TAGO bus chain: route passing-stop evidence has returned nodeid. ' +
      `Before any final answer, call ${TAGO_ARRIVAL_TOOL_NAME} with city_code:"21", ` +
      `a matching node_id, and route_no:"${routeNo}" or route_id to get current arrivals. ` +
      'If the first matching direction returns no arrivals, try the other matching nodeid before final prose.'
    )
  }
  return undefined
}

export function buildTagoBusCompletionPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!isTagoBusQuery(userText)) return undefined
  const usedToolNames = toolUseNames(messages)
  if (routeNoFromUserText(userText) === undefined) {
    return usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)
      ? TAGO_BUS_COMPLETION_PROMPT
      : undefined
  }
  if (
    !usedToolNames.has(TAGO_ROUTE_STATION_TOOL_NAME) ||
    !usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return undefined
  }
  return TAGO_BUS_COMPLETION_PROMPT
}

export function buildTagoBusFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!isTagoBusQuery(userText)) return undefined
  const usedToolNames = toolUseNames(messages)
  if (!usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)) return undefined
  if (hasTagoBusRepairPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (!TAGO_BUS_PENDING_FINAL_RE.test(assistantText)) return undefined
  return TAGO_BUS_REPAIR_PROMPT
}

export function shouldWithholdTagoBusFinalAnswer({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasTagoBusRepairPrompt(messages)) return false
  return (
    buildTagoBusFinalAnswerRepairPromptIfNeeded({
      messages: [...messages, candidate],
    }) !== undefined
  )
}

export function buildAirKoreaCompletionPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!AIRKOREA_RE.test(userText)) return undefined
  const usedToolNames = toolUseNames(messages)
  if (!usedToolNames.has(AIRKOREA_TOOL_NAME)) return undefined
  return AIRKOREA_COMPLETION_PROMPT + (airKoreaExactRowsSummary(messages) ?? '')
}

export function buildAirKoreaFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!AIRKOREA_RE.test(userText)) return undefined
  const usedToolNames = toolUseNames(messages)
  if (!usedToolNames.has(AIRKOREA_TOOL_NAME)) return undefined
  if (hasAirKoreaRepairPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (!AIRKOREA_UNSUPPORTED_LOCATION_CLAIM_RE.test(assistantText)) return undefined
  return AIRKOREA_REPAIR_PROMPT + (airKoreaExactRowsSummary(messages) ?? '')
}

export function shouldWithholdAirKoreaFinalAnswer({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasAirKoreaRepairPrompt(messages)) return false
  return (
    buildAirKoreaFinalAnswerRepairPromptIfNeeded({
      messages: [...messages, candidate],
    }) !== undefined
  )
}

export function buildGenericPendingFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  if (!hasToolResult(messages)) return undefined
  if (hasGenericPendingFinalRepairPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (!GENERIC_PENDING_FINAL_RE.test(assistantText)) return undefined
  return GENERIC_PENDING_FINAL_REPAIR_PROMPT
}

export function shouldWithholdGenericPendingFinalAnswer({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasGenericPendingFinalRepairPrompt(messages)) return false
  return (
    buildGenericPendingFinalAnswerRepairPromptIfNeeded({
      messages: [...messages, candidate],
    }) !== undefined
  )
}

function needsEmergencyRoomSearch(text: string): boolean {
  return MEDICAL_COLLAPSE_OR_ER_RE.test(text) && !NON_MEDICAL_EMERGENCY_RE.test(text)
}

function selectKmaAviationTool(
  userText: string,
  available: Set<string>,
  usedToolNames: Set<string>,
  preferUnused: boolean,
): string | undefined {
  const preferAmos = AMOS_PREFERENCE_RE.test(userText) && GIMPO_RE.test(userText)
  const candidates = preferAmos
    ? ['kma_apihub_url_air_amos_minute', 'kma_apihub_url_air_metar_decoded']
    : ['kma_apihub_url_air_metar_decoded', 'kma_apihub_url_air_amos_minute']
  if (preferUnused) {
    const unused = candidates.filter(candidate => !usedToolNames.has(candidate))
    const unusedChoice = chooseAvailableOrSyncedAdapter(available, unused)
    if (unusedChoice) return unusedChoice
  }
  return chooseAvailableOrSyncedAdapter(available, candidates)
}

function selectProtectedCheckTool(
  userText: string,
  available: Set<string>,
): string | undefined {
  const candidates = [
    MOBILE_ID_RE.test(userText) ? 'mock_verify_mobile_id' : undefined,
    SIMPLE_AUTH_RE.test(userText) ? 'mock_verify_module_simple_auth' : undefined,
    SIMPLE_AUTH_RE.test(userText) ? 'mock_verify_ganpyeon_injeung' : undefined,
    MYDATA_RE.test(userText) ? 'mock_verify_mydata' : undefined,
    ...PROTECTED_CHECK_TOOLS,
  ].filter((toolName): toolName is string => typeof toolName === 'string')
  return chooseAvailableOrSyncedAdapter(available, candidates)
}

function hasAnyToolUse(usedToolNames: Set<string>, candidates: readonly string[]): boolean {
  return candidates.some(candidate => usedToolNames.has(candidate))
}

function requiredKmaAviationTools(
  userText: string,
  available: Set<string>,
): string[] {
  const candidates = GIMPO_RE.test(userText)
    ? ['kma_apihub_url_air_metar_decoded', 'kma_apihub_url_air_amos_minute']
    : ['kma_apihub_url_air_metar_decoded']
  return candidates.filter(candidate => isAvailableOrSyncedAdapter(available, candidate))
}

export function shouldSuppressUmmayaToolCallsForAnswerSynthesis({
  messages,
  tools,
}: {
  messages: readonly Message[]
  tools: Tools
}): boolean {
  const available = availableToolNamesFromTools(tools)
  const userText = latestUserText(messages)
  const usedToolNames = toolUseNames(messages)
  if (
    isMedicalCollapseQuery(userText) &&
    usedToolNames.has(NMC_AED_TOOL_NAME)
  ) {
    return true
  }
  if (
    PROTECTED_QUERY_RE.test(userText) &&
    hasAnyToolUse(usedToolNames, PROTECTED_CHECK_TOOLS)
  ) {
    return true
  }
  if (
    isKmaAnalysisMapText(userText) &&
    usedToolNames.has(KMA_ANALYSIS_CHART_TOOL_NAME)
  ) {
    return true
  }
  if (AIRKOREA_RE.test(userText) && usedToolNames.has(AIRKOREA_TOOL_NAME)) {
    return true
  }
  if (
    isTagoBusQuery(userText) &&
    usedToolNames.has(TAGO_ARRIVAL_TOOL_NAME)
  ) {
    return true
  }
  if (
    isDocumentHarnessQuery(userText) &&
    hasDocumentAnswerSynthesisResultAfter(messages, latestUserMessageIndex(messages))
  ) {
    return true
  }
  if (!isAirportAviationQuery(userText)) return false

  const requiredTools = requiredKmaAviationTools(userText, available)
  if (requiredTools.length === 0) return false

  return requiredTools.every(toolName => usedToolNames.has(toolName))
}

function publicDataMismatchTargetTool(
  latestToolResult: string,
): string | undefined {
  const targetKind = PUBLIC_DATA_MISMATCH_TARGET_RE.exec(latestToolResult)?.[1]
  if (targetKind === 'weather_chart') return KMA_ANALYSIS_CHART_TOOL_NAME
  if (targetKind === 'air_quality') return AIRKOREA_TOOL_NAME
  if (targetKind === 'procurement_bid') return PPS_BID_TOOL_NAME
  const legacyCandidate = PUBLIC_DATA_MISMATCH_CALL_RE.exec(latestToolResult)?.[1]
  return legacyCandidate
}

export function selectUmmayaToolChoiceOverride({
  messages,
  tools,
}: {
  messages: readonly Message[]
  tools: Tools
}): BetaToolChoiceTool | undefined {
  const available = availableToolNamesFromTools(tools)
  const userText = latestUserText(messages)
  const latestToolResult = latestToolResultText(messages)
  const usedToolNames = toolUseNames(messages)
  const airportAviationQuery = isAirportAviationQuery(userText)
  const usedAviationTool = hasAnyToolUse(usedToolNames, KMA_AIR_TOOLS)
  const publicDataTargetTool = publicDataMismatchTargetTool(latestToolResult)
  if (
    shouldSuppressUmmayaToolCallsForAnswerSynthesis({
      messages,
      tools,
    })
  ) {
    return undefined
  }

  if (
    publicDataTargetTool &&
    !usedToolNames.has(publicDataTargetTool) &&
    isAvailableOrSyncedAdapter(available, publicDataTargetTool)
  ) {
    return { type: 'tool', name: publicDataTargetTool }
  }

  if (
    GOV24_MINWON_SUBMIT_RE.test(userText) &&
    !usedToolNames.has('mock_verify_module_simple_auth') &&
    isAvailableOrSyncedAdapter(available, 'mock_verify_module_simple_auth')
  ) {
    return { type: 'tool', name: 'mock_verify_module_simple_auth' }
  }

  if (
    needsEmergencyRoomSearch(userText) &&
    available.has(KAKAO_COORD_TO_REGION_TOOL_NAME) &&
    !usedToolNames.has(KAKAO_COORD_TO_REGION_TOOL_NAME) &&
    !hasSuccessfulRegionLocateResult(messages) &&
    hasSuccessfulPoiLocateResult(messages)
  ) {
    return { type: 'tool', name: KAKAO_COORD_TO_REGION_TOOL_NAME }
  }

  if (
    needsEmergencyRoomSearch(userText) &&
    available.has(NMC_EMERGENCY_TOOL_NAME) &&
    !usedToolNames.has(NMC_EMERGENCY_TOOL_NAME) &&
    hasSuccessfulRegionLocateResult(messages)
  ) {
    return { type: 'tool', name: NMC_EMERGENCY_TOOL_NAME }
  }

  const needsGimpoAviationFollowup =
    airportAviationQuery &&
    GIMPO_RE.test(userText) &&
    usedToolNames.has('kma_apihub_url_air_metar_decoded') &&
    !usedToolNames.has('kma_apihub_url_air_amos_minute') &&
    isAvailableOrSyncedAdapter(available, 'kma_apihub_url_air_amos_minute')

  const shouldForceAviation =
    latestToolResult.includes('KMA aviation tool-choice mismatch') ||
    needsGimpoAviationFollowup
  if (shouldForceAviation) {
    const name = selectKmaAviationTool(
      userText,
      available,
      usedToolNames,
      usedAviationTool,
    )
    if (name) return { type: 'tool', name }
  }

  const shouldForceKmaAnalysis =
    latestToolResult.includes('KMA analysis tool-choice mismatch')
  if (
    shouldForceKmaAnalysis &&
    isAvailableOrSyncedAdapter(available, KMA_ANALYSIS_CHART_TOOL_NAME)
  ) {
    return { type: 'tool', name: KMA_ANALYSIS_CHART_TOOL_NAME }
  }

  const shouldForceAed = buildNmcAedFollowupPromptIfNeeded({
    messages,
    availableToolNames: available,
  })
  if (shouldForceAed && available.has(NMC_AED_TOOL_NAME)) {
    return { type: 'tool', name: NMC_AED_TOOL_NAME }
  }

  const tagoToolName = selectTagoBusToolChoice(
    userText,
    available,
    usedToolNames,
    messages,
  )
  const hasTagoBusFollowupEvidence =
    hasSuccessfulStationSearch(messages) ||
    hasSuccessfulRouteSearch(messages) ||
    hasSuccessfulRouteStationSearch(messages)
  const hasTagoBusValidationMismatch =
    latestToolResult.includes('Public-data tool-choice mismatch') &&
    latestToolResult.includes('target=bus_realtime')
  if (tagoToolName && (hasTagoBusFollowupEvidence || hasTagoBusValidationMismatch)) {
    return { type: 'tool', name: tagoToolName }
  }

  const shouldForceProtected =
    latestToolResult.includes('Protected-domain tool-choice mismatch')
  if (shouldForceProtected) {
    const name = selectProtectedCheckTool(`${userText}\n${latestToolResult}`, available)
    if (name) return { type: 'tool', name }
  }

  return undefined
}
