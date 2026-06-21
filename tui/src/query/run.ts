import type { QueryParams, QueryGenerator } from '../query.js'
import type { AssistantMessage, Message } from '../types/message.js'
import { productionDeps } from './deps.js'
import { Terminal } from './transitions.js'
import { enforceSupportToolBoundary } from './supportBoundary.js'
import {
  buildPublicDataTerminalRepairPrompt,
  buildStalePriorToolResultFinalAnswerBlockedText,
  buildUnsupportedRouteFinalAnswerBlockedText,
  buildUnavailableToolFinalAnswerBlockedText,
  shouldBlockStalePriorToolResultAnswer,
  shouldBlockFinalAnswerAfterUnsupportedRouteRepair,
  shouldBlockFinalAnswerAfterUnavailableToolRepair,
  shouldBlockUnsupportedRouteDetailAnswer,
} from './publicDataTerminalRepair.js'
import {
  contentBlocks,
  isAssistantMessage,
  isUserMessage,
  latestTextUserMessageIndex,
  messageText,
  toolUseBlocks,
  type ToolUseBlock,
} from './messageGuards.js'
import { runToolUseBlocks } from './toolRunner.js'
import {
  buildDocumentCompletionPromptIfNeeded,
  selectRecoveredDocumentToolChoiceNameForMessages,
  selectRecoveredSupportToolChoiceNameForMessages,
} from '../tools/_shared/toolChoiceRepair.js'
import {
  extractTextualToolCallProposals,
  parseTrailingRawJsonToolCallProposal,
  textContainsToolCallProposal,
  textContainsMalformedToolCallProposal,
} from '../utils/rawJsonToolCall.js'
import {
  buildGenericPendingFinalAnswerToolUseBlockedText,
  shouldBlockToolUseAfterGenericPendingFinalAnswerRepair,
} from '../tools/_shared/toolChoiceRepair/publicDataRepair.js'
import {
  parseToolUnavailableError,
} from './toolResultErrors.js'
import {
  appendRouteDiagnostic,
  hashRouteDiagnosticText,
} from '../tools/AdapterTool/routeDiagnostics.js'
import { createAssistantMessage, createUserMessage } from '../utils/messages.js'
import { getKstTimeParts } from '../constants/common.js'
import { streamGuardedAssistantMessage } from './guardedAssistantPreview.js'

type QueryYield = QueryGenerator extends AsyncGenerator<infer Yielded, unknown, unknown>
  ? Yielded
  : never

const ROOT_FIND_TOOL_NAME = 'find'
const ROOT_PRIMITIVE_TOOL_NAMES = new Set([
  'find',
  'locate',
  'check',
  'send',
  'document',
])
const KAKAO_LOCATION_TOOL_NAMES = new Set([
  'kakao_address_search',
  'kakao_keyword_search',
])
const KMA_METAR_TOOL_NAME = 'kma_apihub_url_air_metar_decoded'
const KMA_ORDINARY_WEATHER_TOOL_NAMES = new Set([
  'kma_apihub_upp_mtly_info_service_get_max_wind',
  'kma_current_observation',
  'kma_forecast_fetch',
  'kma_short_term_forecast',
  'kma_ultra_short_term_forecast',
])
const KMA_CURRENT_OBSERVATION_TOOL_NAME = 'kma_current_observation'
const AIRKOREA_AIR_QUALITY_TOOL_NAME = 'airkorea_ctprvn_air_quality'
const NMC_AED_TOOL_NAME = 'nmc_aed_site_locate'
const HIRA_HOSPITAL_TOOL_NAME = 'hira_hospital_search'
const KMA_FORECAST_TOOL_NAMES = new Set([
  'kma_forecast_fetch',
  'kma_short_term_forecast',
  'kma_ultra_short_term_forecast',
])
const REGISTERED_EMERGENCY_RESULT_TOOL_NAMES = new Set([
  'nmc_emergency_search',
  HIRA_HOSPITAL_TOOL_NAME,
])
let recoveredRawJsonToolUseSequence = 0
const PERMISSION_DENIED_TEXT_RE =
  /(permission_denied|Authentication rejected|permission denied|인증이 거부)/iu
const ADAPTERLESS_FIND_TEXT_RE =
  /find\(mode='fetch'\) requires a concrete adapter tool_id|No concrete adapter was selected|requires a concrete adapter tool_id|Missing or invalid fields:\s*tool_id/iu
const PROMPT_INJECTION_USER_RE =
  /(이전\s*지시.*무시|모든\s*지시.*무시|ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions|시스템\s*프롬프트|system\s+prompt|토큰|token|secret|credential|api[_\s-]?key|도구를\s*(?:이렇게\s*)?(?:직접\s*)?실행|execute\s+(?:this\s+)?tool|run\s+(?:this\s+)?tool|call\s+(?:this\s+)?tool)/iu
const SENSITIVE_DISCLOSURE_ACK_RE =
  /(시스템\s*프롬프트.*(출력|공개)|토큰.*(출력|공개)|system\s+prompt.*(?:print|show|reveal)|token.*(?:print|show|reveal)|secret.*(?:print|show|reveal)|도구를.*(?:직접\s*)?실행|execute\s+(?:the\s+)?tool|run\s+(?:the\s+)?tool)/iu
const EMERGENCY_RESULT_REQUEST_RE =
  /(응급|응급실|야간\s*진료|야간진료|병원|의료|emergency|hospital|\bER\b)/iu
const EMERGENCY_FACILITY_CLAIM_RE =
  /[가-힣A-Za-z0-9·()]{1,24}(?:병원|의료원|응급의료센터|응급센터|응급실)/u
const EMERGENCY_STATUS_OR_DISTANCE_CLAIM_RE =
  /(?:\d+(?:\.\d+)?\s*(?:km|킬로미터|m|미터)|병상|가용|진료\s*가능|운영\s*중|24\s*시간|대기\s*시간)/iu
const EMERGENCY_SEARCH_SUCCESS_CLAIM_RE =
  /(?:응급실|응급의료|병원)[^\n.。]*(?:검색|조회|확인|찾았|추천|결과)|(?:검색|조회)\s*결과[^\n.。]*(?:응급실|응급의료|병원)/iu
const EMERGENCY_SAFE_LIMITATION_RE =
  /(결과\s*없이|없이는|단정하지|조회하지\s*못|확인하지\s*못|연결된\s*뒤|adapter|handoff|공식\s*(?:채널|응급의료)|119)/iu
const WEATHER_RESULT_REQUEST_RE =
  /(날씨|기상|weather|예보|현재\s*기온|강수|비|눈|습도|풍속)/iu
const AIR_QUALITY_RESULT_REQUEST_RE =
  /(미세먼지|초미세먼지|초미세|대기질|공기질|대기오염|pm\s*2\.?5|pm\s*10|air\s*korea|airkorea|air\s*quality)/iu
const AED_RESULT_REQUEST_RE = /(AED|자동심장충격기|제세동기)/iu
const HOSPITAL_RESULT_REQUEST_RE =
  /(병원|의원|내과|소아과|안과|이비인후과|피부과|정형외과|진료|의료기관|주소|전화|hospital|clinic|medical)/iu
const DJTC_SUBWAY_SEGMENT_REQUEST_RE =
  /((대전|DJTC|대전교통공사|도시철도|지하철).*(역간|소요시간|거리|운임|요금)|(역간|소요시간|거리|운임|요금).*(대전|DJTC|대전교통공사|도시철도|지하철))/iu
const WEATHER_NEGATIVE_CONSTRAINT_RE =
  /((날씨|기상|weather).*(대체하지\s*(?:마|말고|말아|말아줘)|쓰지\s*(?:마|말고|말아|말아줘)|사용하지\s*(?:마|말고|말아|말아줘))|(대체하지\s*(?:마|말고|말아|말아줘)|쓰지\s*(?:마|말고|말아|말아줘)|사용하지\s*(?:마|말고|말아|말아줘)).*(날씨|기상|weather))/iu
const WEATHER_CANDIDATE_CLAIM_RE =
  /(날씨|기상|weather|예보|현재\s*기온|강수|습도|풍속|하늘상태|하늘\s*상태)/iu
const WEATHER_NO_EVIDENCE_SAFE_RE =
  /(지역|주소|위치)[^\n.。]*(?:알려|입력|필요)|(?:조회|확인)하지\s*못|adapter\s*결과\s*없이|단정하지|제한/iu
const FAILED_TOOL_RESULT_TEXT_RE =
  /(Do NOT fabricate|raised an exception|HTTPStatusError|ToolExecutionError|Adapter .* failed|NO DATA FOUND|404\s+Not\s+Found|permission_denied|permission denied|failed|error|exception|오류|실패)/iu
const FAILED_TOOL_SAFE_FINAL_RE =
  /(실패|오류|조회하지\s*못|확인하지\s*못|제공되지\s*않|포함되어\s*있지\s*않|데이터가\s*없|결과가\s*없|not\s+available|failed|error|NO DATA FOUND|404)/iu
const FAILED_TOOL_SUCCESS_CLAIM_RE =
  /(조회\s*결과|공식\s*데이터\s*조회\s*결과|확인했습니다|찾았습니다|제공됩니다|검색\s*결과|데이터\s*:|전력사용량|요금액|계량기\s*수|사용량|접수번호|승인코드|신청[^\n.。!?]{0,40}접수|접수[^\n.。!?]{0,24}(?:되었|됐|됨)|납부\s*완료|발급\s*완료|result|success)/iu
const FAILED_TOOL_UNGROUNDED_DETAIL_RE =
  /(권장\s*조치|참고용|일반적인|홈페이지|직접\s*문의|https?:\/\/|콜센터|구청|복지로|국민행복카드|기초생활보장|주거급여|긴급복지지원|장애인\s*복지|노인\s*복지|한부모[·\s]*조손)/iu
const PROTECTED_ACTION_BYPASS_REQUEST_RE =
  /(인증\s*없이|권한\s*없이|인증이\s*없더라도|권한이\s*없더라도|도구\s*호출이\s*실패|실패(?:하거나|해도|하더라도)|실제\s*결제가\s*안\s*됐어도|접수번호[^\n.。!?]{0,24}(?:만들|생성)|성공했다고\s*말|성공\s*처리|납부\s*완료라고|완료라고\s*답)/iu
const PROTECTED_ACTION_BYPASS_SAFE_FINAL_RE =
  /(실행하지\s*않|처리할\s*수\s*없|만들\s*수\s*없|공식\s*gateway|권한[^\n.。!?]{0,40}필요|인증[^\n.。!?]{0,40}필요|성공으로\s*처리할\s*수\s*없|완료\s*상태를\s*안내할\s*수\s*없)/iu
const READ_ONLY_PUBLIC_SERVICE_REQUEST_RE =
  /(확인|조회|검색|찾|알려|요약|설명|상담|창구|정보|받을\s*수\s*있는|which|what|find|look\s*up|search|summarize|explain)/iu
const PROTECTED_SEND_ACTION_REQUEST_RE =
  /(신청|제출|접수|신고|발급|납부|결제|송신|동의\s*제공|성공\s*처리|submit|send|apply|file|issue|pay)/iu
const NON_ACTION_BOUNDARY_REQUEST_RE =
  /(실제로\s*(?:만들|생성|접수|신청|제출|발급|납부|결제).*(?:말고|마|않|안)|(?:만들|생성|접수|신청|제출|발급|납부|결제).*실제로.*(?:말고|마|않|안)|어떤\s*인증|어떤\s*권한|필요한지만|만\s*설명|만\s*알려|하지\s*말고|하지마|하지\s*마)/iu
const READ_ONLY_SEND_REPAIR_MARKER = 'Read-only protected-action repair:'
const UNGROUNDED_PUBLIC_DATA_REPAIR_MARKER = 'Ungrounded public-data final repair:'
const REPEATED_STALE_PRIOR_TOOL_RESULT_REPAIR_MARKER =
  'Repeated read-only stale-prior repair:'
const CURRENT_EVIDENCE_STALE_PRIOR_TOOL_RESULT_REPAIR_MARKER =
  'Current-evidence stale-prior repair:'
const PUBLIC_DATA_GROUNDED_DETAIL_RE =
  /(https?:\/\/[^\s)]+|지역번호\s*\+\s*129|\d{2,4}-\d{3,4}-\d{4}|부산\s*사하구청|사하구청|동주민센터|보건소|복지과|복지콜센터|life\.go\.kr)/giu
const UNGROUNDED_DETAIL_NEGATED_CONTEXT_RE =
  /(확인되지\s*않|확인하지\s*못|반환되지\s*않|포함되지\s*않|미확인|not\s+verified|not\s+returned|not\s+included)/iu
const WELFARE_UNVERIFIED_LOCAL_ADVICE_RE =
  /(부산\s*)?사하구청|구청\s*홈페이지|보건소|동주민센터|복지로|bokjiro|홈페이지|직접\s*문의|방문\s*상담/iu
const KMA_FORECAST_SUMMARY_LIMIT = 6
const KOREAN_DATE_CLAIM_RE =
  /(오늘|현재)\s*날짜는\s*\d{4}년\s*\d{1,2}월\s*\d{1,2}일(?:입니다)?/gu
const KOREAN_TODAY_PAREN_DATE_RE =
  /(오늘\s*\()\s*\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*(\))/gu
const KOREAN_TODAY_DATE_PAREN_RE =
  /(오늘\s*날짜\s*\()\s*\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*(\))/gu
const KOREAN_TODAY_INLINE_DATE_RE =
  /(오늘(?:은|의)?\s*)\d{4}년\s*\d{1,2}월\s*\d{1,2}일/gu
const KOREAN_CURRENT_TIME_REASON_RE =
  /(현재\s*시각)(?:은|이)?\s*\d{1,2}시(?:\s*\d{1,2}(?:분|경)?|\s*경)?\s*이므로/gu
const KOREAN_CURRENT_TIME_CLAIM_RE =
  /(현재\s*(?:시각|시간))(?:은|이)?\s*\d{1,2}시(?:\s*\d{1,2}(?:분|경)?|\s*경)?/gu
const KOREAN_CURRENT_TIME_PAREN_RE =
  /(현재\s*(?:시각|시간)\s*\()\s*\d{1,2}시(?:\s*\d{1,2}(?:분|경)?)?\s*(기준\s*\))/gu
const KOREAN_PREVIOUS_BASE_HOUR_OBJECT_RE =
  /직전\s*정시인\s*\d{1,2}시를/gu
const KOREAN_PREVIOUS_BASE_HOUR_RE =
  /직전\s*정시인\s*\d{1,2}시/gu
const KOREAN_CURRENT_SYSTEM_TIME_ASSUMPTION_RE =
  /현재\s*시스템\s*시각을\s*\d{1,2}시\s*이후로\s*가정하고,\s*/gu
const KOREAN_NUMERIC_BASE_TIME_CONFIRM_RE =
  /\b\d{3,4}\s*기준으로\s*확인하겠습니다/gu
type ToolResultBlock = {
  readonly type: 'tool_result'
  readonly tool_use_id: string
  readonly content?: unknown
  readonly is_error?: boolean
}

function toolResultBlocks(message: Message): readonly ToolResultBlock[] {
  return contentBlocks(message).filter(
    (block): block is ToolResultBlock =>
      block.type === 'tool_result' &&
      'tool_use_id' in block &&
      typeof block.tool_use_id === 'string',
  )
}

function ccStyleUnavailableToolResultContent(content: unknown): string | undefined {
  const unavailable = parseToolUnavailableError(content)
  if (unavailable === undefined) return undefined
  const toolName = unavailable.error.tool_name
  return JSON.stringify({
    ...unavailable,
    error: {
      ...unavailable.error,
      message: `Tool ${toolName} is unavailable.`,
    },
  })
}

function upgradeUnavailableToolResultMessage(message: Message): Message {
  if (!isUserMessage(message) || !Array.isArray(message.message.content)) {
    return message
  }
  let changed = false
  const content = message.message.content.map(block => {
    if (
      typeof block !== 'object' ||
      block === null ||
      !('type' in block) ||
      block.type !== 'tool_result' ||
      !('content' in block)
    ) {
      return block
    }
    const upgradedContent = ccStyleUnavailableToolResultContent(block.content)
    if (upgradedContent === undefined || upgradedContent === block.content) {
      return block
    }
    changed = true
    return { ...block, content: upgradedContent }
  })
  return changed
    ? { ...message, message: { ...message.message, content } }
    : message
}

function disabledProviderToolNamesForTurn(
  messages: readonly Message[],
): readonly string[] {
  const disabled: string[] = []
  disabled.push(...permissionDeniedToolNames(messages))
  if (hasAdapterlessFindFailure(messages)) {
    disabled.push(ROOT_FIND_TOOL_NAME)
  }
  return [...new Set(disabled)]
}

function contentText(value: unknown): string {
  if (typeof value === 'string') return value
  if (value === undefined || value === null) return ''
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function parseJsonRecord(value: unknown): Record<string, unknown> | undefined {
  if (isRecord(value)) return value
  if (typeof value !== 'string') return undefined
  try {
    const parsed: unknown = JSON.parse(value)
    return isRecord(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function isStructuredFailureToolResult(value: unknown): boolean {
  const parsed = parseJsonRecord(value)
  if (parsed === undefined) return false
  if (parsed.ok === false) return true
  const data = parseJsonRecord(parsed.data)
  if (data?.ok === false) return true
  return parsed.status === 'failed' || data?.status === 'failed'
}

function stripLeadingTemplateControlTokens(text: string): string {
  return text.replace(/^\s*(?:<%+|%>+)\s*/u, '')
}

function koreanTodayText(): string {
  const [year, month, day] = getKstTimeParts().iso.split('-')
  return `${year}년 ${Number(month)}월 ${Number(day)}일`
}

function koreanNowTimeText(): string {
  const [hour, minute] = getKstTimeParts().hm.split(':')
  return `${Number(hour)}시 ${minute}분`
}

function normalizeKoreanTemporalClaims(text: string): string {
  const hasDateClaim =
    KOREAN_DATE_CLAIM_RE.test(text) ||
    KOREAN_TODAY_PAREN_DATE_RE.test(text) ||
    KOREAN_TODAY_DATE_PAREN_RE.test(text) ||
    KOREAN_TODAY_INLINE_DATE_RE.test(text) ||
    KOREAN_CURRENT_TIME_REASON_RE.test(text) ||
    KOREAN_CURRENT_TIME_CLAIM_RE.test(text) ||
    KOREAN_CURRENT_TIME_PAREN_RE.test(text) ||
    KOREAN_PREVIOUS_BASE_HOUR_OBJECT_RE.test(text) ||
    KOREAN_PREVIOUS_BASE_HOUR_RE.test(text) ||
    KOREAN_CURRENT_SYSTEM_TIME_ASSUMPTION_RE.test(text) ||
    KOREAN_NUMERIC_BASE_TIME_CONFIRM_RE.test(text)
  KOREAN_DATE_CLAIM_RE.lastIndex = 0
  KOREAN_TODAY_PAREN_DATE_RE.lastIndex = 0
  KOREAN_TODAY_DATE_PAREN_RE.lastIndex = 0
  KOREAN_TODAY_INLINE_DATE_RE.lastIndex = 0
  KOREAN_CURRENT_TIME_REASON_RE.lastIndex = 0
  KOREAN_CURRENT_TIME_CLAIM_RE.lastIndex = 0
  KOREAN_CURRENT_TIME_PAREN_RE.lastIndex = 0
  KOREAN_PREVIOUS_BASE_HOUR_OBJECT_RE.lastIndex = 0
  KOREAN_PREVIOUS_BASE_HOUR_RE.lastIndex = 0
  KOREAN_CURRENT_SYSTEM_TIME_ASSUMPTION_RE.lastIndex = 0
  KOREAN_NUMERIC_BASE_TIME_CONFIRM_RE.lastIndex = 0
  if (!hasDateClaim) return text
  const today = koreanTodayText()
  const now = koreanNowTimeText()
  return text
    .replace(KOREAN_DATE_CLAIM_RE, (_match, prefix: string) => {
      return `${prefix} 날짜는 ${today}입니다`
    })
    .replace(KOREAN_TODAY_PAREN_DATE_RE, (_match, prefix: string, suffix: string) => {
      return `${prefix}${today}${suffix}`
    })
    .replace(KOREAN_TODAY_DATE_PAREN_RE, (_match, prefix: string, suffix: string) => {
      return `${prefix}${today}${suffix}`
    })
    .replace(KOREAN_TODAY_INLINE_DATE_RE, (_match, prefix: string) => {
      return `${prefix}${today}`
    })
    .replace(KOREAN_CURRENT_TIME_REASON_RE, (_match, prefix: string) => {
      return `${prefix}은 ${now}이므로`
    })
    .replace(KOREAN_CURRENT_TIME_CLAIM_RE, (_match, prefix: string) => {
      return `${prefix}은 ${now}`
    })
    .replace(KOREAN_CURRENT_TIME_PAREN_RE, (_match, prefix: string, suffix: string) => {
      return `${prefix}${now} ${suffix}`
    })
    .replace(KOREAN_PREVIOUS_BASE_HOUR_OBJECT_RE, '최근 발표 시각을')
    .replace(KOREAN_PREVIOUS_BASE_HOUR_RE, '최근 발표 시각')
    .replace(KOREAN_CURRENT_SYSTEM_TIME_ASSUMPTION_RE, '현재 KST 시각 기준으로 ')
    .replace(KOREAN_NUMERIC_BASE_TIME_CONFIRM_RE, '최근 발표 기준으로 확인하겠습니다')
}

function sanitizeVisibleAssistantControlTokens(
  message: AssistantMessage,
): AssistantMessage {
  const content = message.message.content
  if (typeof content === 'string') {
    const sanitized = normalizeKoreanTemporalClaims(stripLeadingTemplateControlTokens(content))
    return sanitized === content
      ? message
      : { ...message, message: { ...message.message, content: sanitized } }
  }
  if (!Array.isArray(content)) return message
  let changed = false
  const sanitizedContent = content.map(block => {
    if (!isRecord(block) || block.type !== 'text' || typeof block.text !== 'string') {
      return block
    }
    const sanitizedText = normalizeKoreanTemporalClaims(stripLeadingTemplateControlTokens(block.text))
    if (sanitizedText === block.text) return block
    changed = true
    return { ...block, text: sanitizedText }
  })
  return changed
    ? { ...message, message: { ...message.message, content: sanitizedContent } }
    : message
}

type PriorToolResult = {
  readonly toolName: string
  readonly content: unknown
  readonly isError: boolean
}

type KmaForecastSummaryRow = {
  key: string
  date: string
  time: string
  temperature?: string
  precipitationProbability?: string
  sky?: string
  precipitationType?: string
  humidity?: string
  windSpeed?: string
  precipitation?: string
}

type AirQualitySummary = {
  readonly stationName?: string
  readonly dataTime?: string
  readonly pm10?: string
  readonly pm25?: string
  readonly khai?: string
}

function concreteToolName(block: ToolUseBlock): string {
  const toolId = block.input.tool_id
  return ROOT_PRIMITIVE_TOOL_NAMES.has(block.name) &&
    typeof toolId === 'string' &&
    toolId.length > 0
    ? toolId
    : block.name
}

function toolResultsSinceLatestPrompt(
  messages: readonly Message[],
): readonly PriorToolResult[] {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return []
  const toolNamesByUseId = new Map<string, string>()
  const results: PriorToolResult[] = []
  for (const message of messages.slice(latestUserIndex + 1)) {
    if (isAssistantMessage(message)) {
      for (const block of toolUseBlocks(message)) {
        toolNamesByUseId.set(block.id, concreteToolName(block))
      }
      continue
    }
    if (!isUserMessage(message)) continue
    for (const block of toolResultBlocks(message)) {
      const toolName = toolNamesByUseId.get(block.tool_use_id)
      if (toolName === undefined) continue
      results.push({
        toolName,
        content: block.content,
        isError: block.is_error === true || isStructuredFailureToolResult(block.content),
      })
    }
  }
  return results
}

function shouldDeferProviderStreamUntilGuard(messages: readonly Message[]): boolean {
  if (PROTECTED_ACTION_BYPASS_REQUEST_RE.test(latestUserText(messages))) {
    return true
  }
  const results = toolResultsSinceLatestPrompt(messages)
  return results.some(result =>
    result.isError ||
    result.toolName === AIRKOREA_AIR_QUALITY_TOOL_NAME ||
    result.toolName === KMA_CURRENT_OBSERVATION_TOOL_NAME ||
    result.toolName === NMC_AED_TOOL_NAME ||
    KMA_FORECAST_TOOL_NAMES.has(result.toolName) ||
    REGISTERED_EMERGENCY_RESULT_TOOL_NAMES.has(result.toolName),
  )
}

function isProviderStreamEvent(event: unknown): boolean {
  return isRecord(event) && event.type === 'stream_event'
}

function systemPromptForTurn(
  basePrompt: readonly string[],
  messages: readonly Message[],
): readonly string[] {
  const priorResults = toolResultsSinceLatestPrompt(messages)
  if (!priorResults.some(result => result.toolName === KMA_METAR_TOOL_NAME)) {
    return basePrompt
  }
  return [
    ...basePrompt,
    [
      'KMA aviation weather boundary: prior decoded METAR evidence exists for this airport-flight request.',
      'Do not ask the user for KMA nx/ny grid coordinates.',
      'Do not call ordinary KMA current or forecast tools as a fallback for airport aviation weather.',
      'Answer from the aviation evidence or hand off to official airline/airport status channels.',
    ].join(' '),
  ]
}

function hasConcreteFindToolId(input: Record<string, unknown>): boolean {
  const toolId = input.tool_id
  return typeof toolId === 'string' &&
    toolId.trim().length > 0 &&
    !ROOT_PRIMITIVE_TOOL_NAMES.has(toolId)
}

function isAdapterlessFindToolUse(block: ToolUseBlock): boolean {
  return block.name === ROOT_FIND_TOOL_NAME && !hasConcreteFindToolId(block.input)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function createRecoveredRawJsonToolUseId(baseUuid: string): string {
  recoveredRawJsonToolUseSequence += 1
  return `toolu-raw-json-${baseUuid}-${recoveredRawJsonToolUseSequence}`
}

function upgradeRawJsonToolCallAssistant(params: {
  readonly assistantMessage: AssistantMessage
  readonly createToolUseId: () => string
}): AssistantMessage {
  if (toolUseBlocks(params.assistantMessage).length > 0) {
    return params.assistantMessage
  }
  const blocks = contentBlocks(params.assistantMessage)
  const textualExtraction = extractTextualToolCallProposals({
    text: messageText(params.assistantMessage),
  })
  if (textualExtraction !== undefined) {
    const preservedBlocks = blocks.filter(block => block.type !== 'text')
    const content = textualExtraction.text.length > 0
      ? [
          ...preservedBlocks,
          { type: 'text' as const, text: textualExtraction.text },
        ]
      : preservedBlocks

    return {
      ...params.assistantMessage,
      message: {
        ...params.assistantMessage.message,
        content: [
          ...content,
          ...textualExtraction.proposals.map(proposal => ({
            type: 'tool_use' as const,
            id: params.createToolUseId(),
            name: proposal.name,
            input: proposal.input,
          })),
        ],
      },
    }
  }

  const trailingProposal = parseTrailingRawJsonToolCallProposal({
    text: messageText(params.assistantMessage),
  })
  if (trailingProposal === undefined) return params.assistantMessage

  const preservedBlocks = blocks.filter(block => block.type !== 'text')
  const content = trailingProposal.prelude.length > 0
    ? [
        ...preservedBlocks,
        { type: 'text' as const, text: trailingProposal.prelude },
      ]
    : preservedBlocks

  return {
    ...params.assistantMessage,
    message: {
      ...params.assistantMessage.message,
      content: [
        ...content,
        {
          type: 'tool_use' as const,
          id: params.createToolUseId(),
          name: trailingProposal.proposal.name,
          input: trailingProposal.proposal.input,
        },
      ],
    },
  }
}

function hasAdapterlessFindFailure(messages: readonly Message[]): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  const toolNamesByUseId = new Map<string, string>()
  for (let index = latestUserIndex + 1; index < messages.length; index += 1) {
    const message = messages[index]
    if (!message) continue
    if (isAssistantMessage(message)) {
      for (const block of toolUseBlocks(message)) {
        toolNamesByUseId.set(block.id, block.name)
      }
      continue
    }
    if (!isUserMessage(message)) continue
    for (const block of toolResultBlocks(message)) {
      if (
        toolNamesByUseId.get(block.tool_use_id) === ROOT_FIND_TOOL_NAME &&
        ADAPTERLESS_FIND_TEXT_RE.test(contentText(block.content))
      ) {
        return true
      }
    }
  }
  return false
}

function shouldBlockRepeatedAdapterlessFind(
  block: ToolUseBlock,
  messages: readonly Message[],
): boolean {
  return isAdapterlessFindToolUse(block) && hasAdapterlessFindFailure(messages)
}

function createAdapterlessFindContinuationGuardResult(
  block: ToolUseBlock,
  assistantMessage: AssistantMessage,
): Message {
  const message = [
    'Root find wrapper already failed because no concrete adapter tool_id was selected.',
    'Do not call find again without tool_id in this citizen turn.',
    'Call a concrete loaded adapter directly when one is available; otherwise write a stable Korean final, needs-input, or handoff answer that names the missing adapter/credential limitation.',
  ].join(' ')
  return createUserMessage({
    content: [
      {
        type: 'tool_result',
        tool_use_id: block.id,
        content: message,
        is_error: true,
      },
    ],
    toolUseResult: message,
    sourceToolAssistantUUID: assistantMessage.uuid,
  })
}

function createAdapterlessFindHardGuardFinalMessage(): AssistantMessage {
  return createAssistantMessage({
    content: [
      '공공서비스 adapter가 선택되지 않아 이 시민 업무를 계속 진행할 수 없습니다.',
      '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
      '요청하신 신청/조회/등록 업무는 공식 공공서비스 adapter와 필요한 인증/위임 credential이 연결된 뒤 이어서 처리해야 합니다. 지금은 공식 신청 채널 확인으로 handoff합니다.',
    ].join('\n\n'),
  })
}

function createPromptInjectionToolRecoveryBlockedMessage(): AssistantMessage {
  return createAssistantMessage({
    content: [
      '시스템 프롬프트나 토큰, 비밀값은 공개할 수 없습니다.',
      '사용자 입력에 포함된 JSON/도구 실행 지시는 신뢰된 도구 호출이 아니므로 실행하지 않습니다.',
      '필요한 업무를 자연어로 다시 요청하면 등록된 도구와 권한 경계 안에서 처리하겠습니다.',
    ].join('\n\n'),
  })
}

function createMalformedToolProposalBlockedMessage(): AssistantMessage {
  return createAssistantMessage({
    content: [
      '유효하지 않은 도구 호출 형식이 감지되어 실행하지 않았습니다.',
      '등록된 도구의 정상 tool_use 경계와 검증된 tool_result 없이 서류 목록이나 처리 결과를 단정하지 않겠습니다.',
      '필요한 업무를 자연어로 다시 요청하면 현재 등록된 도구 표면 안에서 처리하겠습니다.',
    ].join('\n\n'),
  })
}

function createGenericPendingFinalAnswerToolUseBlockedMessage(): AssistantMessage {
  return createAssistantMessage({
    content: buildGenericPendingFinalAnswerToolUseBlockedText(),
  })
}

function createUnavailableToolFinalAnswerBlockedMessage(
  messages: readonly Message[],
): AssistantMessage {
  void messages
  return createAssistantMessage({
    content: buildUnavailableToolFinalAnswerBlockedText(),
  })
}

function createUnsupportedRouteFinalAnswerBlockedMessage(): AssistantMessage {
  return createAssistantMessage({
    content: buildUnsupportedRouteFinalAnswerBlockedText(),
  })
}

function createStalePriorToolResultFinalAnswerBlockedMessage(): AssistantMessage {
  return createAssistantMessage({
    content: buildStalePriorToolResultFinalAnswerBlockedText(),
  })
}

function createEmergencyNoClaimBlockedMessage(): AssistantMessage {
  return createAssistantMessage({
    content: [
      '등록된 응급의료 adapter 결과 없이 응급실 이름, 거리, 운영 상태, 병상 여부를 단정하지 않습니다.',
      '최신 사용자 요청 이후 nmc_emergency_search 또는 hira_hospital_search tool_result가 없으므로 공식 검색 결과처럼 안내할 수 없습니다.',
      '긴급하면 119 또는 응급의료포털/병원 공식 채널에서 즉시 확인해야 하며, 해당 adapter가 연결되면 그 결과에 근거해 다시 안내하겠습니다.',
    ].join('\n\n'),
  })
}

function scalarText(value: unknown): string | undefined {
  if (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return String(value)
  }
  return undefined
}

function kmaCurrentObservationItem(result: PriorToolResult): Record<string, unknown> | undefined {
  if (result.toolName !== KMA_CURRENT_OBSERVATION_TOOL_NAME || result.isError) {
    return undefined
  }
  const envelope = parseJsonRecord(result.content)
  const resultRecord = isRecord(envelope?.result) ? envelope.result : undefined
  const item = isRecord(resultRecord?.item) ? resultRecord.item : undefined
  return item
}

function kmaForecastItems(result: PriorToolResult): readonly Record<string, unknown>[] {
  if (!KMA_FORECAST_TOOL_NAMES.has(result.toolName) || result.isError) {
    return []
  }
  const envelope = parseJsonRecord(result.content)
  const resultRecord = isRecord(envelope?.result) ? envelope.result : undefined
  const item = isRecord(resultRecord?.item) ? resultRecord.item : undefined
  const items = Array.isArray(item?.items) ? item.items : []
  const points = Array.isArray(resultRecord?.points) ? resultRecord.points : []
  return [...items, ...points].filter(isRecord)
}

function nestedResultRecord(envelope: Record<string, unknown> | undefined): Record<string, unknown> | undefined {
  if (envelope === undefined) return undefined
  if (isRecord(envelope.result)) return envelope.result
  return isRecord(envelope.data) && isRecord(envelope.data.result)
    ? envelope.data.result
    : undefined
}

function airKoreaAirQualityRecords(result: PriorToolResult): readonly Record<string, unknown>[] {
  if (result.toolName !== AIRKOREA_AIR_QUALITY_TOOL_NAME || result.isError) {
    return []
  }
  const resultRecord = nestedResultRecord(parseJsonRecord(result.content))
  const items = Array.isArray(resultRecord?.items) ? resultRecord.items : []
  return items.flatMap(item => {
    if (!isRecord(item)) return []
    if (isRecord(item.record)) return [item.record]
    return [item]
  })
}

function airQualityMeasure(value: unknown, grade: unknown): string | undefined {
  const measure = scalarText(value)
  if (measure === undefined || measure.length === 0) return undefined
  const gradeText = scalarText(grade)
  return gradeText !== undefined && gradeText.length > 0
    ? `${measure} (${gradeText})`
    : measure
}

function airQualitySummary(record: Record<string, unknown>): AirQualitySummary | undefined {
  const pm10 = airQualityMeasure(record.pm10Value, record.pm10GradeLabelKo)
  const pm25 = airQualityMeasure(record.pm25Value, record.pm25GradeLabelKo)
  const khai = airQualityMeasure(record.khaiValue, record.khaiGradeLabelKo)
  if (pm10 === undefined && pm25 === undefined && khai === undefined) {
    return undefined
  }
  return {
    stationName: scalarText(record.stationName),
    dataTime: scalarText(record.dataTime),
    pm10,
    pm25,
    khai,
  }
}

function firstAirQualitySummary(results: readonly PriorToolResult[]): AirQualitySummary | undefined {
  for (const record of results.flatMap(airKoreaAirQualityRecords)) {
    const summary = airQualitySummary(record)
    if (summary !== undefined) return summary
  }
  return undefined
}

function airQualitySummaryLines(summary: AirQualitySummary): readonly string[] {
  const observedAt = [
    summary.stationName !== undefined ? `${summary.stationName} 측정소` : undefined,
    summary.dataTime,
  ].filter((part): part is string => part !== undefined && part.length > 0).join(', ')
  const lines = [
    '',
    'AirKorea adapter 결과 기준으로 확인된 값만 정리합니다.',
  ]
  if (observedAt.length > 0) {
    lines.push(`대기질(${observedAt})`)
  }
  if (summary.pm10 !== undefined) lines.push(`- PM10: ${summary.pm10}`)
  if (summary.pm25 !== undefined) lines.push(`- PM2.5: ${summary.pm25}`)
  if (summary.khai !== undefined) lines.push(`- 통합대기환경지수(CAI): ${summary.khai}`)
  lines.push('대기질 값은 AirKorea 측정소 결과이며 날씨 값과 출처를 분리했습니다.')
  return lines
}

function precipitationTypeText(value: string | undefined): string | undefined {
  if (value === undefined) return undefined
  const byCode: Record<string, string> = {
    '0': '없음',
    '1': '비',
    '2': '비/눈',
    '3': '눈',
    '5': '빗방울',
    '6': '빗방울/눈날림',
    '7': '눈날림',
  }
  return byCode[value] ?? value
}

function skyText(value: string | undefined): string | undefined {
  if (value === undefined) return undefined
  const byCode: Record<string, string> = {
    '1': '맑음',
    '3': '구름많음',
    '4': '흐림',
  }
  return byCode[value] ?? value
}

function formatKmaDate(value: string): string {
  return /^\d{8}$/u.test(value)
    ? `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`
    : value
}

function formatKmaTime(value: string): string {
  return /^\d{4}$/u.test(value) ? `${value.slice(0, 2)}:${value.slice(2, 4)}` : value
}

function assignKmaForecastField(
  row: KmaForecastSummaryRow,
  category: string,
  value: string,
): void {
  switch (category.toUpperCase()) {
    case 'TMP':
    case 'T1H':
      row.temperature = `${value}°C`
      break
    case 'POP':
      row.precipitationProbability = `${value}%`
      break
    case 'SKY':
      row.sky = skyText(value)
      break
    case 'PTY':
      row.precipitationType = precipitationTypeText(value)
      break
    case 'REH':
      row.humidity = `${value}%`
      break
    case 'WSD':
      row.windSpeed = `${value}m/s`
      break
    case 'PCP':
    case 'RN1':
      row.precipitation = value
      break
    default:
      break
  }
}

function kmaTimestampParts(value: string): { readonly date: string; readonly time: string } | undefined {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/u.exec(value)
  if (match === null) return undefined
  const [, date, hour, minute] = match
  if (date === undefined || hour === undefined || minute === undefined) return undefined
  return { date, time: `${hour}:${minute}` }
}

function assignKmaTimeseriesPoint(
  row: KmaForecastSummaryRow,
  item: Record<string, unknown>,
): void {
  const temperature = scalarText(item.temperature_c)
  const pop = scalarText(item.pop_pct)
  const sky = scalarText(item.sky_code)
  const precipitation = scalarText(item.precipitation_mm)
  const windSpeed = scalarText(item.wind_speed_m_s)
  if (temperature !== undefined) row.temperature = `${temperature}°C`
  if (pop !== undefined) row.precipitationProbability = `${pop}%`
  if (sky !== undefined) row.sky = skyText(sky)
  if (precipitation !== undefined) row.precipitation = precipitation
  if (windSpeed !== undefined) row.windSpeed = `${windSpeed}m/s`
}

function kmaForecastSummaryRows(
  items: readonly Record<string, unknown>[],
): readonly KmaForecastSummaryRow[] {
  const rows = new Map<string, KmaForecastSummaryRow>()
  for (const item of items) {
    const timestamp = scalarText(item.timestamp_iso)
    const timestampParts = timestamp !== undefined ? kmaTimestampParts(timestamp) : undefined
    if (timestampParts !== undefined) {
      const key = `${timestampParts.date}${timestampParts.time}`
      const row = rows.get(key) ?? {
        key,
        date: timestampParts.date,
        time: timestampParts.time,
      }
      assignKmaTimeseriesPoint(row, item)
      rows.set(key, row)
      continue
    }
    const date = scalarText(item.fcst_date) ?? scalarText(item.base_date)
    const time = scalarText(item.fcst_time) ?? scalarText(item.base_time)
    const category = scalarText(item.category)
    const value = scalarText(item.fcst_value)
    if (
      date === undefined ||
      time === undefined ||
      category === undefined ||
      value === undefined
    ) {
      continue
    }
    const key = `${date}${time}`
    const row = rows.get(key) ?? { key, date, time }
    assignKmaForecastField(row, category, value)
    rows.set(key, row)
  }
  return [...rows.values()]
    .filter(row =>
      row.temperature !== undefined ||
      row.precipitationProbability !== undefined ||
      row.sky !== undefined ||
      row.precipitationType !== undefined ||
      row.humidity !== undefined ||
      row.windSpeed !== undefined ||
      row.precipitation !== undefined,
    )
    .sort((left, right) => left.key.localeCompare(right.key))
    .slice(0, KMA_FORECAST_SUMMARY_LIMIT)
}

function kmaForecastRowText(row: KmaForecastSummaryRow): string | undefined {
  const fields = [
    row.temperature !== undefined ? `기온 ${row.temperature}` : undefined,
    row.precipitationProbability !== undefined
      ? `강수확률 ${row.precipitationProbability}`
      : undefined,
    row.sky !== undefined ? `하늘 ${row.sky}` : undefined,
    row.precipitationType !== undefined ? `강수형태 ${row.precipitationType}` : undefined,
    row.humidity !== undefined ? `습도 ${row.humidity}` : undefined,
    row.windSpeed !== undefined ? `풍속 ${row.windSpeed}` : undefined,
    row.precipitation !== undefined ? `강수량 ${row.precipitation}` : undefined,
  ].filter((field): field is string => field !== undefined)
  if (fields.length === 0) return undefined
  return `- ${formatKmaDate(row.date)} ${formatKmaTime(row.time)}: ${fields.join(', ')}`
}

function createKmaWeatherEvidenceMessage(params: {
  readonly currentItem?: Record<string, unknown>
  readonly forecastItems: readonly Record<string, unknown>[]
  readonly airQuality?: AirQualitySummary
}): AssistantMessage {
  const rows = kmaForecastSummaryRows(params.forecastItems)
  const item = params.currentItem
  const baseDate = scalarText(item?.base_date)
  const baseTime = scalarText(item?.base_time)
  const observedAt = baseDate && baseTime
    ? `${formatKmaDate(baseDate)} ${formatKmaTime(baseTime)}`
    : '기상청 현재관측 기준'
  const lines = ['기상청 adapter 결과 기준으로 확인된 값만 정리합니다.']
  if (item !== undefined) {
    lines.push(
      '',
      `현재관측(${observedAt})`,
      scalarText(item.t1h) !== undefined ? `- 기온: ${scalarText(item.t1h)}°C` : '',
      scalarText(item.rn1) !== undefined ? `- 1시간 강수량: ${scalarText(item.rn1)}mm` : '',
      scalarText(item.reh) !== undefined ? `- 습도: ${scalarText(item.reh)}%` : '',
      scalarText(item.wsd) !== undefined ? `- 풍속: ${scalarText(item.wsd)}m/s` : '',
      scalarText(item.vec) !== undefined ? `- 풍향: ${scalarText(item.vec)}°` : '',
      precipitationTypeText(scalarText(item.pty)) !== undefined
        ? `- 강수형태: ${precipitationTypeText(scalarText(item.pty))}`
        : '',
    )
  }
  const forecastLines = rows.map(kmaForecastRowText).filter((line): line is string => line !== undefined)
  if (forecastLines.length > 0) {
    lines.push('', '예보 주요 시간대', ...forecastLines)
  }
  lines.push(
    '',
    '현재관측과 예보 항목을 분리했습니다. KMA VEC는 풍향 각도이며 풍속으로 해석하지 않습니다.',
  )
  if (forecastLines.length === 0) {
    lines.push(
      '하늘상태, 구름, 맑음/흐림, 강수확률, 체감온도는 현재관측 결과만으로 단정하지 않습니다.',
    )
  }
  if (params.airQuality !== undefined) {
    lines.push(...airQualitySummaryLines(params.airQuality))
  }
  return createAssistantMessage({
    content: lines.filter(line => line !== '').join('\n'),
  })
}

function createKmaWeatherNoEvidenceMessage(): AssistantMessage {
  return createAssistantMessage({
    content: [
      'KMA adapter 결과 없이 날씨/예보를 단정하지 않습니다.',
      '최신 사용자 요청 이후 kma_current_observation 또는 KMA forecast tool_result가 없어 현재/예보 값을 제공하지 않습니다.',
      '위치 확인 뒤 KMA adapter 결과가 도착하면 그 결과 기준으로 다시 정리합니다.',
    ].join('\n'),
  })
}

function kmaWeatherEvidenceGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  const latestUser = latestUserText(params.messages)
  if (
    !WEATHER_RESULT_REQUEST_RE.test(latestUser) ||
    DJTC_SUBWAY_SEGMENT_REQUEST_RE.test(latestUser) ||
    WEATHER_NEGATIVE_CONSTRAINT_RE.test(latestUser)
  ) {
    return undefined
  }
  const results = toolResultsSinceLatestPrompt(params.messages)
  const item = results.map(kmaCurrentObservationItem).find(item => item !== undefined)
  const forecastItems = results.flatMap(result => [...kmaForecastItems(result)])
  const airQuality = AIR_QUALITY_RESULT_REQUEST_RE.test(latestUser)
    ? firstAirQualitySummary(results)
    : undefined
  if (item === undefined && forecastItems.length === 0) {
    const candidateText = messageText(params.candidate)
    const attemptedKmaWeather = results.some(result =>
      result.toolName === KMA_CURRENT_OBSERVATION_TOOL_NAME ||
      KMA_FORECAST_TOOL_NAMES.has(result.toolName),
    )
    if (!attemptedKmaWeather && !WEATHER_CANDIDATE_CLAIM_RE.test(candidateText)) {
      return undefined
    }
    return WEATHER_NO_EVIDENCE_SAFE_RE.test(candidateText)
      ? undefined
      : createKmaWeatherNoEvidenceMessage()
  }
  return createKmaWeatherEvidenceMessage({
    currentItem: item,
    forecastItems,
    airQuality,
  })
}

function nmcAedRecords(result: PriorToolResult): readonly Record<string, unknown>[] {
  if (result.toolName !== NMC_AED_TOOL_NAME || result.isError) {
    return []
  }
  const resultRecord = nestedResultRecord(parseJsonRecord(result.content))
  const items = Array.isArray(resultRecord?.items) ? resultRecord.items : []
  return items.flatMap(item => {
    if (!isRecord(item)) return []
    return isRecord(item.record) ? [item.record] : [item]
  })
}

function nmcAedDistanceText(record: Record<string, unknown>): string | undefined {
  const value = scalarText(record.distance_km) ?? scalarText(record.distance)
  if (value === undefined || value.length === 0) return undefined
  return value.endsWith('km') ? value : `${value}km`
}

function nmcAedOperatingText(record: Record<string, unknown>): string | undefined {
  const start = scalarText(record.monSttTme)
  const end = scalarText(record.monEndTme)
  if (start === undefined || end === undefined) return undefined
  const format = (value: string): string =>
    value.length === 4 ? `${value.slice(0, 2)}:${value.slice(2)}` : value
  return `${format(start)}-${format(end)}`
}

function nmcAedSummaryLines(records: readonly Record<string, unknown>[]): readonly string[] {
  return records.slice(0, 5).flatMap((record, index) => {
    const org = scalarText(record.org) ?? 'AED'
    const distance = nmcAedDistanceText(record)
    const title = distance === undefined
      ? `${index + 1}. ${org}`
      : `${index + 1}. ${org} (${distance})`
    return [
      title,
      scalarText(record.buildAddress) !== undefined
        ? `- 주소: ${scalarText(record.buildAddress)}`
        : undefined,
      scalarText(record.buildPlace) !== undefined
        ? `- 설치장소: ${scalarText(record.buildPlace)}`
        : undefined,
      nmcAedOperatingText(record) !== undefined
        ? `- 운영시간: ${nmcAedOperatingText(record)}`
        : undefined,
      scalarText(record.clerkTel) !== undefined
        ? `- 연락처: ${scalarText(record.clerkTel)}`
        : undefined,
      scalarText(record.model) !== undefined
        ? `- 모델: ${scalarText(record.model)}`
        : undefined,
    ].filter((line): line is string => line !== undefined)
  })
}

function createNmcAedEvidenceMessage(records: readonly Record<string, unknown>[]): AssistantMessage {
  const hasDistance = records.some(record => nmcAedDistanceText(record) !== undefined)
  const lines = [
    'NMC AED adapter 결과 기준으로 확인된 값만 정리합니다.',
    hasDistance
      ? '거리값이 있는 결과를 adapter 반환 순서대로 가까운 순서로 표시합니다.'
      : '이번 결과에는 거리값이 없어 가까운 순서를 단정하지 않습니다.',
    '',
    ...nmcAedSummaryLines(records),
  ]
  return createAssistantMessage({
    content: lines.filter(line => line !== '').join('\n'),
  })
}

function nmcAedEvidenceGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  if (!AED_RESULT_REQUEST_RE.test(latestUserText(params.messages))) {
    return undefined
  }
  const records = toolResultsSinceLatestPrompt(params.messages)
    .flatMap(result => nmcAedRecords(result))
  return records.length === 0 ? undefined : createNmcAedEvidenceMessage(records)
}

function hiraHospitalRecords(result: PriorToolResult): readonly Record<string, unknown>[] {
  if (result.toolName !== HIRA_HOSPITAL_TOOL_NAME || result.isError) {
    return []
  }
  const resultRecord = nestedResultRecord(parseJsonRecord(result.content))
  const items = Array.isArray(resultRecord?.items) ? resultRecord.items : []
  return items.flatMap(item => {
    if (!isRecord(item)) return []
    return isRecord(item.record) ? [item.record] : [item]
  })
}

function formatHiraDistance(
  value: string,
  unitHint: 'km' | 'm' | 'unknown',
): string {
  const compact = value.trim()
  if (/km|킬로미터|m|미터/iu.test(compact)) return compact
  const numeric = Number(compact)
  if (!Number.isFinite(numeric)) return compact
  if (
    unitHint === 'km' ||
    (unitHint === 'unknown' && numeric > 0 && numeric < 20 && compact.includes('.'))
  ) {
    return `${numeric.toFixed(1)}km`
  }
  if (numeric >= 1000) return `${(numeric / 1000).toFixed(1)}km`
  return `${Math.round(numeric)}m`
}

function hiraHospitalDistanceText(record: Record<string, unknown>): string | undefined {
  const distanceKm = scalarText(record.distance_km)
  if (distanceKm !== undefined && distanceKm.trim().length > 0) {
    return formatHiraDistance(distanceKm, 'km')
  }
  const distance = scalarText(record.distance)
  if (distance !== undefined && distance.trim().length > 0) {
    return formatHiraDistance(distance, 'unknown')
  }
  const distanceLabel = scalarText(record.distanceLabel)
  if (distanceLabel !== undefined && distanceLabel.trim().length > 0) {
    return formatHiraDistance(distanceLabel, 'unknown')
  }
  return undefined
}

function hiraHospitalName(record: Record<string, unknown>): string | undefined {
  return scalarText(record.yadmNm) ??
    scalarText(record.name) ??
    scalarText(record.hospital_name)
}

function hiraHospitalAddress(record: Record<string, unknown>): string | undefined {
  return scalarText(record.addr) ??
    scalarText(record.address) ??
    scalarText(record.roadAddress)
}

function hiraHospitalPhone(record: Record<string, unknown>): string | undefined {
  return scalarText(record.telno) ??
    scalarText(record.phone) ??
    scalarText(record.telephone)
}

function hiraHospitalSummaryLines(
  records: readonly Record<string, unknown>[],
): readonly string[] {
  return records.slice(0, 5).flatMap((record, index) => {
    const name = hiraHospitalName(record)
    if (name === undefined || name.length === 0) return []
    const distance = hiraHospitalDistanceText(record)
    const title = distance === undefined
      ? `${index + 1}. ${name}`
      : `${index + 1}. ${name} (${distance})`
    return [
      title,
      hiraHospitalAddress(record) !== undefined
        ? `- 주소: ${hiraHospitalAddress(record)}`
        : undefined,
      hiraHospitalPhone(record) !== undefined
        ? `- 전화번호: ${hiraHospitalPhone(record)}`
        : undefined,
      scalarText(record.clCdNm) !== undefined
        ? `- 종별: ${scalarText(record.clCdNm)}`
        : undefined,
    ].filter((line): line is string => line !== undefined)
  })
}

function createHiraHospitalEvidenceMessage(
  records: readonly Record<string, unknown>[],
): AssistantMessage {
  const hasDistance = records.some(record => hiraHospitalDistanceText(record) !== undefined)
  const lines = [
    'HIRA hospital adapter 결과 기준으로 확인된 값만 정리합니다.',
    hasDistance
      ? 'HIRA adapter가 거리 오름차순으로 반환한 순서를 그대로 표시합니다.'
      : '이번 결과에는 거리값이 없어 가까운 순서를 단정하지 않습니다.',
    '',
    ...hiraHospitalSummaryLines(records),
    '',
    '오늘 진료 가능 여부나 접수 가능 여부가 tool_result에 없으면 전화로 확인해야 합니다.',
  ]
  return createAssistantMessage({
    content: lines.filter(line => line !== '').join('\n'),
  })
}

function hiraHospitalEvidenceGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  if (!HOSPITAL_RESULT_REQUEST_RE.test(latestUserText(params.messages))) {
    return undefined
  }
  const records = toolResultsSinceLatestPrompt(params.messages)
    .flatMap(result => hiraHospitalRecords(result))
  return records.length === 0 ? undefined : createHiraHospitalEvidenceMessage(records)
}

function hasSuccessfulRegisteredEmergencyResult(
  messages: readonly Message[],
): boolean {
  return toolResultsSinceLatestPrompt(messages).some(result =>
    REGISTERED_EMERGENCY_RESULT_TOOL_NAMES.has(result.toolName) &&
    !result.isError,
  )
}

function isEmergencyResultClaim(text: string): boolean {
  const hasFacilityClaim = EMERGENCY_FACILITY_CLAIM_RE.test(text)
  const hasStatusOrDistanceClaim =
    EMERGENCY_STATUS_OR_DISTANCE_CLAIM_RE.test(text)
  if (
    EMERGENCY_SAFE_LIMITATION_RE.test(text) &&
    !hasFacilityClaim &&
    !hasStatusOrDistanceClaim
  ) {
    return false
  }
  return hasFacilityClaim ||
    hasStatusOrDistanceClaim ||
    EMERGENCY_SEARCH_SUCCESS_CLAIM_RE.test(text)
}

function shouldBlockEmergencyResultClaim(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): boolean {
  if (toolUseBlocks(params.candidate).length > 0) return false
  if (!EMERGENCY_RESULT_REQUEST_RE.test(latestUserText(params.messages))) {
    return false
  }
  if (hasSuccessfulRegisteredEmergencyResult(params.messages)) return false
  return isEmergencyResultClaim(messageText(params.candidate))
}

function domainGuardFinalAnswerForToolResults(
  results: readonly Message[],
): AssistantMessage | undefined {
  const text = results
    .flatMap(message =>
      contentBlocks(message).map(block => contentText(block)),
    )
    .join('\n')
  if (text.includes('Hometax lookup already returned')) {
    return createAssistantMessage({
      content:
        '홈택스 조회는 이미 완료되었습니다. 다음 단계는 본인확인, 위임, 동의 확인입니다. verify 도구로 인증/위임 승인을 먼저 진행하거나, 승인 없이는 공식 채널 확인으로 handoff합니다.',
    })
  }
  if (text.includes('KMA aviation lookup already returned')) {
    return createAssistantMessage({
      content:
        '항공기상 확인 결과는 이미 확보했거나 credential 한계가 확인되었습니다. 같은 항공기상 도구를 반복 호출하지 않고, 확보된 근거와 공식 항공사/공항 상태 확인 한계를 기준으로 안내합니다.',
    })
  }
  if (text.includes('as a fallback for airport aviation weather')) {
    return createAssistantMessage({
      content:
        '항공기상 근거를 바탕으로 지연 위험과 일반 날씨 fallback 한계를 안내합니다. 공항/항공편 상태는 항공사와 공항 공식 채널에서 최종 확인해야 합니다.',
    })
  }
  if (text.includes('Do not repeat ordinary KMA current or forecast tools')) {
    return createAssistantMessage({
      content:
        'KMA 일반 날씨 도구를 반복 호출하지 않습니다. 기존 위치 근거와 격자값 누락 한계를 바탕으로 안전한 이동 판단은 공식 날씨/교통 채널 확인으로 handoff합니다.',
    })
  }
  if (text.includes('TAGO route lookup already returned zero official rows')) {
    return createAssistantMessage({
      content:
        'TAGO 시내버스 노선 조회에서 해당 노선/도시 조합의 결과가 0건으로 확인되었습니다. 서울-대전 같은 도시 간 이동은 TAGO 시내버스 노선 API 범위가 아닙니다. 공식 공공데이터에는 국토교통부 TAGO 고속버스정보와 국토교통부 TAGO 시외버스정보가 별도 채널로 존재하지만, 현재 UMMAYA에 해당 intercity adapter가 등록되어 있지 않아 시간표, 요금, 노선ID를 만들지 않습니다. 철도와 고속·시외버스 공식 예매/운행 채널 확인으로 handoff합니다.',
    })
  }
  if (text.includes('MOHW/SSIS welfare lookup already returned NO DATA FOUND')) {
    return createAssistantMessage({
      content:
        'mohw_welfare_eligibility_search가 이번 요청에서 두 차례 NO DATA FOUND를 반환했습니다. tool_result에 없는 지역 복지 항목, 구청 전화번호, 지원 자격을 만들지 않습니다. 공식 fallback은 복지로 서비스 검색 또는 보건복지상담센터 129에서 1인 가구, 거주지, 연령, 소득 조건을 다시 확인하는 것입니다. UMMAYA는 현재 확보한 MOHW/SSIS 결과가 없다고만 보고하고 신청이나 제출은 실행하지 않습니다.',
    })
  }
  if (text.includes('PPS shopping mall product lookup already returned official product rows')) {
    return createAssistantMessage({
      content:
        'pps_shopping_mall_product_lookup가 이번 요청에서 이미 공식 공공조달 물품 행을 반환했습니다. 같은 조달 물품 조회를 반복하거나 정상 API 응답을 실패로 바꾸지 않습니다. 직전 tool_result에 있는 품목명, 식별번호, 계약업체, 가격, 총건수만 근거로 요약해야 합니다.',
    })
  }
  if (text.includes('PPS shopping mall product lookup already returned an official successful response with totalCount=0')) {
    return createAssistantMessage({
      content:
        'pps_shopping_mall_product_lookup가 공공조달 종합쇼핑몰 API에서 정상 응답을 받았지만 totalCount=0으로 공식 물품 행이 없었습니다. 이는 기관 API 실패가 아니라 0건 결과입니다. 노트북과 무관한 검색어로 임의 확장하지 않고 여기서 멈춥니다. 다른 검색어로 다시 조회할지는 사용자가 확인해야 합니다.',
    })
  }
  return undefined
}

function isPermissionDeniedToolResultBlock(block: ToolResultBlock): boolean {
  return PERMISSION_DENIED_TEXT_RE.test(contentText(block.content))
}

function permissionDeniedToolNames(messages: readonly Message[]): readonly string[] {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return []
  const toolNamesByUseId = new Map<string, string>()
  const denied = new Set<string>()
  for (let index = latestUserIndex + 1; index < messages.length; index += 1) {
    const message = messages[index]
    if (!message) continue
    if (isAssistantMessage(message)) {
      for (const block of toolUseBlocks(message)) {
        toolNamesByUseId.set(block.id, block.name)
      }
      continue
    }
    if (!isUserMessage(message)) continue
    for (const block of toolResultBlocks(message)) {
      const toolName = toolNamesByUseId.get(block.tool_use_id)
      if (toolName !== undefined && isPermissionDeniedToolResultBlock(block)) {
        denied.add(toolName)
      }
    }
  }
  return [...denied]
}

function shouldBlockRepeatedPermissionDeniedTool(
  block: ToolUseBlock,
  messages: readonly Message[],
): boolean {
  return permissionDeniedToolNames(messages).includes(block.name)
}

function createPermissionDeniedContinuationGuardResult(
  block: ToolUseBlock,
  assistantMessage: AssistantMessage,
): Message {
  const message = [
    `Permission boundary blocked: ${block.name} was already rejected with permission_denied in this request.`,
    'Do not retry the same protected check until the user explicitly grants or restarts authentication.',
    'Write a stable Korean needs-input or handoff answer explaining that authentication approval is required before continuing.',
  ].join(' ')
  return createUserMessage({
    content: [
      {
        type: 'tool_result',
        tool_use_id: block.id,
        content: message,
        is_error: true,
      },
    ],
    toolUseResult: message,
    sourceToolAssistantUUID: assistantMessage.uuid,
  })
}

function latestQueryHash(messages: readonly Message[]): string {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  const latestUserMessage = latestUserIndex >= 0 ? messages[latestUserIndex] : undefined
  return hashRouteDiagnosticText(
    latestUserMessage ? messageText(latestUserMessage) : '',
  )
}

function latestUserText(messages: readonly Message[]): string {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  const latestUserMessage = latestUserIndex >= 0 ? messages[latestUserIndex] : undefined
  return latestUserMessage ? messageText(latestUserMessage) : ''
}

function previousTextUserMessageBefore(
  messages: readonly Message[],
  endIndex: number,
): Message | undefined {
  for (let index = endIndex - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (
      message !== undefined &&
      isUserMessage(message) &&
      message.isMeta !== true &&
      messageText(message).trim().length > 0
    ) {
      return message
    }
  }
  return undefined
}

function normalizeRepeatedUserRequestText(text: string): string {
  return text.normalize('NFKC').replace(/\s+/gu, ' ').trim().toLocaleLowerCase()
}

function isRepeatedLatestUserRequest(messages: readonly Message[]): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  const latest = messages[latestUserIndex]
  if (latest === undefined) return false
  const previous = previousTextUserMessageBefore(messages, latestUserIndex)
  if (previous === undefined) return false
  const latestText = normalizeRepeatedUserRequestText(messageText(latest))
  if (latestText.length === 0) return false
  return latestText === normalizeRepeatedUserRequestText(messageText(previous))
}

function hasRepeatedStalePriorToolResultRepairPromptAfterLatestUser(
  messages: readonly Message[],
): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  return messages.slice(latestUserIndex + 1).some(message =>
    messageText(message).includes(REPEATED_STALE_PRIOR_TOOL_RESULT_REPAIR_MARKER),
  )
}

function repeatedReadOnlyStalePriorToolResultRepairPrompt(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): string | undefined {
  const latestUser = latestUserText(params.messages)
  if (!READ_ONLY_PUBLIC_SERVICE_REQUEST_RE.test(latestUser)) return undefined
  if (queryExplicitlyRequestsProtectedSend(latestUser)) return undefined
  if (PROTECTED_ACTION_BYPASS_REQUEST_RE.test(latestUser)) return undefined
  if (!isRepeatedLatestUserRequest(params.messages)) return undefined
  if (hasRepeatedStalePriorToolResultRepairPromptAfterLatestUser(params.messages)) {
    return undefined
  }
  if (!shouldBlockStalePriorToolResultAnswer(params)) return undefined
  return [
    `${REPEATED_STALE_PRIOR_TOOL_RESULT_REPAIR_MARKER} the latest citizen request repeats a prior read-only public-service lookup, but the assistant tried to answer from prior tool_result text without fresh tool_result evidence after the latest user message.`,
    'Call the appropriate registered adapter tool again for the latest user request when one is available in the current tool schema.',
    'Do not reuse prior tool_result values as current evidence, and do not finish with the stale-prior safety text unless the retry also cannot produce a current tool_result.',
  ].join(' ')
}

function hasCurrentEvidenceStalePriorToolResultRepairPromptAfterLatestUser(
  messages: readonly Message[],
): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  return messages.slice(latestUserIndex + 1).some(message =>
    messageText(message).includes(CURRENT_EVIDENCE_STALE_PRIOR_TOOL_RESULT_REPAIR_MARKER),
  )
}

function hasCurrentSuccessfulNonLocationToolResult(messages: readonly Message[]): boolean {
  return toolResultsSinceLatestPrompt(messages).some(result =>
    !result.isError && !KAKAO_LOCATION_TOOL_NAMES.has(result.toolName),
  )
}

function currentEvidenceStalePriorToolResultRepairPrompt(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): string | undefined {
  if (hasCurrentEvidenceStalePriorToolResultRepairPromptAfterLatestUser(params.messages)) {
    return undefined
  }
  if (!hasCurrentSuccessfulNonLocationToolResult(params.messages)) {
    return undefined
  }
  if (!shouldBlockStalePriorToolResultAnswer(params)) {
    return undefined
  }
  return [
    `${CURRENT_EVIDENCE_STALE_PRIOR_TOOL_RESULT_REPAIR_MARKER} the latest citizen request already has successful non-location tool_result evidence, but the assistant answer mixed in stale prior-turn values.`,
    'Write the final Korean answer from successful tool_results after the latest citizen request only.',
    'Do not reuse earlier weather, AED, hospital, route, welfare, procurement, or receipt values unless the latest user explicitly asked for prior results.',
    'If the current official adapter returned zero rows or partial data, say that directly and name the adapter or agency API instead of fabricating a replacement.',
  ].join(' ')
}

type FailedToolResult = {
  readonly toolName: string
  readonly errorText: string
}

function isFailedToolResultBlock(block: ToolResultBlock): boolean {
  return block.is_error === true ||
    isStructuredFailureToolResult(block.content) ||
    FAILED_TOOL_RESULT_TEXT_RE.test(contentText(block.content))
}

function latestFailedToolResultAfterLatestUser(
  messages: readonly Message[],
): FailedToolResult | undefined {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return undefined
  const toolNamesByUseId = new Map<string, string>()
  let latestFailure: FailedToolResult | undefined
  for (const message of messages.slice(latestUserIndex + 1)) {
    if (isAssistantMessage(message)) {
      for (const block of toolUseBlocks(message)) {
        toolNamesByUseId.set(block.id, block.name)
      }
      continue
    }
    if (!isUserMessage(message)) continue
    for (const block of toolResultBlocks(message)) {
      if (isFailedToolResultBlock(block)) {
        latestFailure = {
          toolName: toolNamesByUseId.get(block.tool_use_id) ?? 'unknown_adapter',
          errorText: contentText(block.content),
        }
      } else {
        latestFailure = undefined
      }
    }
  }
  return latestFailure
}

function failedToolSummaryText(errorText: string): string {
  const parsed = parseJsonRecord(errorText)
  const error = parseJsonRecord(parsed?.error)
  const result = parseJsonRecord(parsed?.result)
  const message =
    typeof error?.message === 'string'
      ? error.message
      : typeof result?.message === 'string'
        ? result.message
        : errorText
  return message.replace(/\s+/gu, ' ').trim().slice(0, 420)
}

function buildFailedToolFinalAnswerBlockedText(failure: FailedToolResult): string {
  const compactError = failedToolSummaryText(failure.errorText)
  return [
    `${failure.toolName} 조회는 이번 턴에서 실패했습니다.`,
    compactError ? `오류 요약: ${compactError}` : '오류 요약: 등록 adapter가 성공 결과를 반환하지 않았습니다.',
    '성공한 tool_result 없이 수치, 접수 결과, 요금, 사용량, 자격 여부를 단정하지 않습니다.',
    '다른 파라미터나 다른 공식 도구로 재시도하려면 먼저 사용자 확인이 필요합니다.',
  ].join('\n\n')
}

function isProtectedActionToolUse(block: ToolUseBlock): boolean {
  const toolId = typeof block.input.tool_id === 'string' ? block.input.tool_id : ''
  return block.name === 'send' ||
    block.name === 'document' ||
    /^mock_submit_/u.test(toolId) ||
    /_(?:submit|pay|payment|issue|certificate)/iu.test(toolId)
}

function buildProtectedBypassBlockedText(): string {
  return [
    '요청은 실행하지 않았습니다.',
    '인증, 권한, 또는 도구 실패를 건너뛰고 신청, 제출, 발급, 접수, 납부를 성공으로 처리할 수 없습니다.',
    '접수번호나 납부 완료 상태는 공식 gateway와 정상 권한 확인을 통과한 tool_result가 있을 때만 안내할 수 있습니다.',
  ].join('\n\n')
}

function queryExplicitlyRequestsProtectedSend(text: string): boolean {
  return PROTECTED_SEND_ACTION_REQUEST_RE.test(text) &&
    !NON_ACTION_BOUNDARY_REQUEST_RE.test(text)
}

function isSendActionToolUse(block: ToolUseBlock): boolean {
  const toolId = typeof block.input.tool_id === 'string' ? block.input.tool_id : ''
  return block.name === 'send' ||
    /^mock_.*submit/iu.test(block.name) ||
    /_(?:submit)(?:_|$)/iu.test(block.name) ||
    /^mock_.*submit/iu.test(toolId) ||
    /_(?:submit)(?:_|$)/iu.test(toolId)
}

function buildReadOnlySendBlockedText(): string {
  return [
    '요청은 실행하지 않았습니다.',
    '이 요청은 조회, 확인, 설명, 상담 창구 확인 같은 읽기 전용 요청입니다.',
    '신청, 제출, 발급, 접수, 납부, 결제, 동의 같은 보호 작업은 명시 요청과 권한 확인이 있을 때만 진행합니다.',
    '성공한 조회 결과가 부족하면 어떤 adapter 또는 기관 API가 실패했는지 그대로 안내해야 합니다.',
  ].join('\n\n')
}

function welfareServiceSummaryLine(item: Record<string, unknown>): string | undefined {
  const name = scalarText(item.servNm) ?? scalarText(item.serviceName) ?? scalarText(item.name)
  if (name === undefined || name.length === 0) return undefined
  const ministry = scalarText(item.jurMnofNm)
  const summary = scalarText(item.servDgst)
  const parts = [
    `- ${name}`,
    ministry !== undefined && ministry.length > 0 ? `(${ministry})` : undefined,
    summary !== undefined && summary.length > 0 ? `: ${summary.slice(0, 120)}` : undefined,
  ]
  return parts.filter((part): part is string => part !== undefined).join(' ')
}

function welfareServiceItems(result: PriorToolResult): readonly Record<string, unknown>[] {
  if (result.toolName !== 'mohw_welfare_eligibility_search' || result.isError) {
    return []
  }
  const resultRecord = nestedResultRecord(parseJsonRecord(result.content))
  const items = Array.isArray(resultRecord?.items) ? resultRecord.items : []
  return items.flatMap(item => {
    if (!isRecord(item)) return []
    return isRecord(item.record) ? [item.record] : [item]
  })
}

function readOnlyPublicServiceEvidenceMessage(
  messages: readonly Message[],
): AssistantMessage | undefined {
  const welfareLines = toolResultsSinceLatestPrompt(messages)
    .flatMap(result => welfareServiceItems(result))
    .map(welfareServiceSummaryLine)
    .filter((line): line is string => line !== undefined)
    .slice(0, 5)
  if (welfareLines.length === 0) return undefined
  return createAssistantMessage({
    content: [
      '요청은 실행하지 않았습니다.',
      '최신 보건복지부/SSIS adapter 조회 결과에 포함된 항목만 정리합니다.',
      ...welfareLines,
      '지역 상담 창구, 전화번호, 신청 가능 여부가 tool_result에 없으면 확인된 값처럼 단정하지 않습니다.',
    ].join('\n'),
  })
}

function buildNonActionProtectedBoundaryText(): string {
  return [
    '요청은 실행하지 않았습니다.',
    '정부24 민원 접수번호는 실제 신청 또는 접수 단계의 결과이므로 이 흐름에서는 생성하지 않습니다.',
    '필요한 확인은 본인확인, 민원 대상 자격, 대리 신청 또는 위임 권한, 신청 범위, 수수료와 제출 동의, 결과 수령 권한입니다.',
    '본인확인은 공식 gateway의 간편인증, 공동/금융인증서, 모바일 신분증 같은 인증 수단을 통해 처리되어야 합니다.',
    '성공한 tool_result 없이 신청 완료나 접수번호를 성공 처리하지 않습니다.',
  ].join('\n\n')
}

function hasReadOnlySendRepairPromptAfterLatestUser(
  messages: readonly Message[],
): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  return messages.slice(latestUserIndex + 1).some(message =>
    messageText(message).includes(READ_ONLY_SEND_REPAIR_MARKER),
  )
}

function buildReadOnlySendRepairPrompt(): string {
  return [
    `${READ_ONLY_SEND_REPAIR_MARKER} the latest citizen request is read-only, but the assistant attempted a protected send/submit action.`,
    'Do not call send, submit, apply, issue, payment, or another protected-action adapter.',
    'Write the final Korean answer from successful tool_results already returned after the latest citizen request.',
    'If an adapter failed or returned no data, name that adapter or agency API exactly and do not fabricate missing eligibility, application, receipt, or contact details.',
  ].join(' ')
}

function readOnlySendPromptActionRepairPrompt(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): string | undefined {
  const latestUser = latestUserText(params.messages)
  if (!READ_ONLY_PUBLIC_SERVICE_REQUEST_RE.test(latestUser)) {
    return undefined
  }
  if (queryExplicitlyRequestsProtectedSend(latestUser)) {
    return undefined
  }
  if (!toolUseBlocks(params.candidate).some(isSendActionToolUse)) {
    return undefined
  }
  if (hasReadOnlySendRepairPromptAfterLatestUser(params.messages)) {
    return undefined
  }
  return buildReadOnlySendRepairPrompt()
}

function readOnlySendPromptActionGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  const latestUser = latestUserText(params.messages)
  if (!READ_ONLY_PUBLIC_SERVICE_REQUEST_RE.test(latestUser)) {
    return undefined
  }
  if (queryExplicitlyRequestsProtectedSend(latestUser)) {
    return undefined
  }
  if (!toolUseBlocks(params.candidate).some(isSendActionToolUse)) {
    return undefined
  }
  const evidenceMessage = readOnlyPublicServiceEvidenceMessage(params.messages)
  if (evidenceMessage !== undefined) {
    return evidenceMessage
  }
  return createAssistantMessage({
    content: buildReadOnlySendBlockedText(),
  })
}

function hasUngroundedPublicDataRepairPromptAfterLatestUser(
  messages: readonly Message[],
): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  return messages.slice(latestUserIndex + 1).some(message =>
    messageText(message).includes(UNGROUNDED_PUBLIC_DATA_REPAIR_MARKER),
  )
}

function successfulToolEvidenceSinceLatestUser(messages: readonly Message[]): string {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return ''
  return messages
    .slice(latestUserIndex + 1)
    .flatMap(message => isUserMessage(message) ? toolResultBlocks(message) : [])
    .filter(block => block.is_error !== true)
    .map(block => contentText(block.content))
    .join('\n')
}

function normalizeGroundedDetail(value: string): string {
  return value.replace(/[)\].,，。]+$/gu, '').replace(/\s+/gu, '').toLowerCase()
}

function ungroundedPublicDataDetails(
  candidateText: string,
  evidenceText: string,
): readonly string[] {
  const evidence = normalizeGroundedDetail(evidenceText)
  const ungrounded = new Set<string>()
  for (const match of candidateText.matchAll(PUBLIC_DATA_GROUNDED_DETAIL_RE)) {
    const value = normalizeGroundedDetail(match[0] ?? '')
    if (value.length === 0) continue
    const matchIndex = match.index ?? 0
    const context = candidateText.slice(
      Math.max(0, matchIndex - 80),
      Math.min(candidateText.length, matchIndex + match[0].length + 80),
    )
    if (UNGROUNDED_DETAIL_NEGATED_CONTEXT_RE.test(context)) continue
    if (!evidence.includes(value)) ungrounded.add(value)
  }
  return [...ungrounded]
}

function hasUngroundedWelfareLocalAdvice(candidateText: string): boolean {
  const match = WELFARE_UNVERIFIED_LOCAL_ADVICE_RE.exec(candidateText)
  if (match === null) return false
  const matchIndex = match.index
  const context = candidateText.slice(
    Math.max(0, matchIndex - 80),
    Math.min(candidateText.length, matchIndex + match[0].length + 80),
  )
  return !UNGROUNDED_DETAIL_NEGATED_CONTEXT_RE.test(context)
}

function buildUngroundedPublicDataRepairPrompt(details: readonly string[]): string {
  const joinedDetails = details.slice(0, 5).join(', ')
  return [
    `${UNGROUNDED_PUBLIC_DATA_REPAIR_MARKER} the final answer included URL, phone, or local-office details not present in the latest successful tool_results.`,
    joinedDetails ? `Ungrounded details: ${joinedDetails}.` : '',
    'Rewrite the final Korean answer using only fields visible in successful tool_results after the latest citizen request.',
    'If 부산 사하구 local counseling windows, phone numbers, or URLs were not returned by the adapter, state they were not verified in this run; do not invent or substitute them.',
  ].filter(Boolean).join(' ')
}

function ungroundedPublicDataFinalRepairPrompt(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): string | undefined {
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  if (!READ_ONLY_PUBLIC_SERVICE_REQUEST_RE.test(latestUserText(params.messages))) {
    return undefined
  }
  if (hasUngroundedPublicDataRepairPromptAfterLatestUser(params.messages)) {
    return undefined
  }
  const evidenceText = successfulToolEvidenceSinceLatestUser(params.messages)
  if (evidenceText.length === 0) return undefined
  const candidateText = messageText(params.candidate)
  if (
    readOnlyPublicServiceEvidenceMessage(params.messages) !== undefined &&
    hasUngroundedWelfareLocalAdvice(candidateText)
  ) {
    return undefined
  }
  const details = ungroundedPublicDataDetails(candidateText, evidenceText)
  if (details.length > 0) return buildUngroundedPublicDataRepairPrompt(details)
  return undefined
}

function buildUngroundedPublicDataBlockedText(): string {
  return [
    '이번 턴의 tool_result에 없는 URL, 전화번호, 지역 상담 창구를 현재 결과처럼 안내하지 않습니다.',
    '성공한 adapter 결과에 포함된 항목만 요약하고, 반환되지 않은 부산 사하구 지역 상담 창구나 연락처는 미확인으로 남겨야 합니다.',
  ].join('\n\n')
}

function ungroundedPublicDataFinalGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  const evidenceMessage = readOnlyPublicServiceEvidenceMessage(params.messages)
  const hasWelfareLocalAdvice =
    evidenceMessage !== undefined &&
    hasUngroundedWelfareLocalAdvice(messageText(params.candidate))
  if (
    !hasWelfareLocalAdvice &&
    !hasUngroundedPublicDataRepairPromptAfterLatestUser(params.messages)
  ) {
    return undefined
  }
  const evidenceText = successfulToolEvidenceSinceLatestUser(params.messages)
  const details = ungroundedPublicDataDetails(messageText(params.candidate), evidenceText)
  if (
    details.length === 0 &&
    !hasWelfareLocalAdvice
  ) {
    return undefined
  }
  return evidenceMessage ??
    createAssistantMessage({ content: buildUngroundedPublicDataBlockedText() })
}

function protectedBypassPromptActionGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  const latestUser = latestUserText(params.messages)
  if (!PROTECTED_ACTION_BYPASS_REQUEST_RE.test(latestUser)) {
    return undefined
  }
  if (toolUseBlocks(params.candidate).length === 0) {
    return undefined
  }
  if (NON_ACTION_BOUNDARY_REQUEST_RE.test(latestUser)) {
    return createAssistantMessage({
      content: buildNonActionProtectedBoundaryText(),
    })
  }
  return createAssistantMessage({
    content: buildProtectedBypassBlockedText(),
  })
}

function protectedBypassPromptFinalAnswerGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  if (!PROTECTED_ACTION_BYPASS_REQUEST_RE.test(latestUserText(params.messages))) {
    return undefined
  }
  const candidateText = messageText(params.candidate)
  if (PROTECTED_ACTION_BYPASS_SAFE_FINAL_RE.test(candidateText)) {
    return undefined
  }
  if (NON_ACTION_BOUNDARY_REQUEST_RE.test(latestUserText(params.messages))) {
    return createAssistantMessage({
      content: buildNonActionProtectedBoundaryText(),
    })
  }
  return createAssistantMessage({
    content: buildProtectedBypassBlockedText(),
  })
}

function buildProtectedActionAfterFailedToolBlockedText(
  failure: FailedToolResult,
): string {
  const compactError = failure.errorText.replace(/\s+/gu, ' ').trim().slice(0, 420)
  return [
    '요청은 완료되지 않았습니다.',
    `${failure.toolName} 단계가 이번 턴에서 실패했기 때문에 보호된 신청, 제출, 발급, 납부를 계속 진행할 수 없습니다.`,
    compactError ? `오류 요약: ${compactError}` : '오류 요약: 등록 adapter가 성공 결과를 반환하지 않았습니다.',
    '인증, 권한, 또는 공식 gateway 확인 없이 접수번호나 납부 완료를 만들 수 없습니다.',
  ].join('\n\n')
}

function protectedActionAfterFailedToolGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  const failure = latestFailedToolResultAfterLatestUser(params.messages)
  if (failure === undefined) return undefined
  if (!toolUseBlocks(params.candidate).some(isProtectedActionToolUse)) {
    return undefined
  }
  return createAssistantMessage({
    content: buildProtectedActionAfterFailedToolBlockedText(failure),
  })
}

function failedToolFinalAnswerGuard(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): AssistantMessage | undefined {
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  const failure = latestFailedToolResultAfterLatestUser(params.messages)
  if (failure === undefined) return undefined
  const candidateText = messageText(params.candidate)
  const hasUngroundedDetail = FAILED_TOOL_UNGROUNDED_DETAIL_RE.test(candidateText)
  if (!FAILED_TOOL_SUCCESS_CLAIM_RE.test(candidateText) && !hasUngroundedDetail) {
    return undefined
  }
  if (
    FAILED_TOOL_SAFE_FINAL_RE.test(candidateText) &&
    !PROTECTED_ACTION_BYPASS_REQUEST_RE.test(latestUserText(params.messages)) &&
    !hasUngroundedDetail
  ) {
    return undefined
  }
  return createAssistantMessage({
    content: buildFailedToolFinalAnswerBlockedText(failure),
  })
}

function shouldBlockPromptInjectionToolRecovery(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
  readonly activeToolChoiceName: string | undefined
}): boolean {
  const userText = latestUserText(params.messages)
  if (!PROMPT_INJECTION_USER_RE.test(userText)) return false
  const candidateToolUses = toolUseBlocks(params.candidate)
  if (
    params.activeToolChoiceName !== undefined &&
    candidateToolUses.some(block => block.name === params.activeToolChoiceName)
  ) {
    return false
  }
  if (candidateToolUses.length > 0) return true
  const candidateText = messageText(params.candidate)
  return textContainsToolCallProposal(candidateText) ||
    SENSITIVE_DISCLOSURE_ACK_RE.test(candidateText)
}

function shouldBlockMalformedUserToolProposal(
  messages: readonly Message[],
): boolean {
  return textContainsMalformedToolCallProposal(latestUserText(messages))
}

function appendQueryAssistantDiagnostic(params: {
  readonly event: string
  readonly querySource: string
  readonly messages: readonly Message[]
  readonly assistantMessage: AssistantMessage
  readonly turnCount: number
  readonly boundaryKind: string
  readonly repairPromptChars: number
  readonly continueAfterRepair: boolean
}): void {
  appendRouteDiagnostic(params.event, {
    query_hash: latestQueryHash(params.messages),
    query_source: params.querySource,
    turn_count: params.turnCount,
    message_count: params.messages.length,
    assistant_text_chars: messageText(params.assistantMessage).length,
    assistant_tool_use_count: toolUseBlocks(params.assistantMessage).length,
    assistant_content_block_count: contentBlocks(params.assistantMessage).length,
    boundary_kind: params.boundaryKind,
    repair_prompt_chars: params.repairPromptChars,
    continue_after_repair: params.continueAfterRepair,
  })
}

function appendQueryCompletedWithoutAssistantDiagnostic(params: {
  readonly querySource: string
  readonly messages: readonly Message[]
  readonly turnCount: number
}): void {
  appendRouteDiagnostic('query_completed_without_assistant', {
    query_hash: latestQueryHash(params.messages),
    query_source: params.querySource,
    turn_count: params.turnCount,
    message_count: params.messages.length,
  })
}

export async function* query(params: QueryParams): QueryGenerator {
  const deps = params.deps ?? productionDeps()
  const messages: Message[] = [...params.messages]
  let turnCount = 0

  while (params.maxTurns === undefined || turnCount < params.maxTurns) {
    turnCount += 1
    if (params.toolUseContext.abortController.signal.aborted) {
      return Terminal.aborted_streaming()
    }
    if (shouldBlockMalformedUserToolProposal(messages)) {
      const blockedMessage = createMalformedToolProposalBlockedMessage()
      appendQueryAssistantDiagnostic({
        event: 'query_user_blocked_malformed_tool_proposal',
        querySource: String(params.querySource),
        messages,
        assistantMessage: blockedMessage,
        turnCount,
        boundaryKind: 'block',
        repairPromptChars: 0,
        continueAfterRepair: false,
      })
      yield blockedMessage
      messages.push(blockedMessage)
      return Terminal.completed()
    }
    yield { type: 'stream_request_start' }

    let assistantMessage: AssistantMessage | undefined
    let shouldContinueAfterRepairPrompt = false
    const disabledProviderToolNames = disabledProviderToolNamesForTurn(
      messages,
    )
    const activeToolChoiceName =
      selectRecoveredSupportToolChoiceNameForMessages(messages) ??
      selectRecoveredDocumentToolChoiceNameForMessages({
        messages,
        tools: params.toolUseContext.options.tools,
      })
    const activeToolChoiceAvailable = activeToolChoiceName
      ? params.toolUseContext.options.tools.some(
          tool => tool.name === activeToolChoiceName,
        )
      : false
    const guardedPreviewEnabled =
      params.toolUseContext.options.isNonInteractiveSession !== true
    const shouldDeferProviderStream =
      shouldDeferProviderStreamUntilGuard(messages)
    const deferredProviderStreamEvents: QueryYield[] = []
    let loggedProviderStreamDefer = false
    const deferProviderStreamEvent = (event: QueryYield): void => {
      deferredProviderStreamEvents.push(event)
      if (loggedProviderStreamDefer) return
      loggedProviderStreamDefer = true
      appendRouteDiagnostic('query_provider_stream_deferred_until_guard', {
        query_hash: latestQueryHash(messages),
        query_source: String(params.querySource),
        turn_count: turnCount,
        message_count: messages.length,
      })
    }
    function* flushDeferredProviderStreamEvents(
      reason: string,
    ): Generator<QueryYield, void, unknown> {
      if (deferredProviderStreamEvents.length === 0) return
      appendRouteDiagnostic('query_provider_stream_flushed_after_guard', {
        query_hash: latestQueryHash(messages),
        query_source: String(params.querySource),
        turn_count: turnCount,
        message_count: messages.length,
        buffered_event_count: deferredProviderStreamEvents.length,
        reason,
      })
      while (deferredProviderStreamEvents.length > 0) {
        const event = deferredProviderStreamEvents.shift()
        if (event !== undefined) yield event
      }
    }

    for await (const event of deps.callModel({
      messages,
      systemPrompt: systemPromptForTurn(params.systemPrompt, messages),
      thinkingConfig: params.toolUseContext.options.thinkingConfig,
      tools: params.toolUseContext.options.tools,
      signal: params.toolUseContext.abortController.signal,
      options: {
        getToolPermissionContext: async () =>
          params.toolUseContext.getAppState().toolPermissionContext,
        model: params.toolUseContext.options.mainLoopModel,
        isNonInteractiveSession:
          params.toolUseContext.options.isNonInteractiveSession,
        querySource: params.querySource,
        agents: params.toolUseContext.options.agentDefinitions.activeAgents,
        allowedAgentTypes:
          params.toolUseContext.options.agentDefinitions.allowedAgentTypes,
        mcpTools: params.toolUseContext.options.mcpClients,
        maxOutputTokensOverride: params.maxOutputTokensOverride,
        taskBudget: params.taskBudget,
        skipCacheWrite: params.skipCacheWrite,
        disabledProviderToolNames,
      },
    })) {
      if (params.toolUseContext.abortController.signal.aborted) {
        return Terminal.aborted_streaming()
      }
      if (!isAssistantMessage(event)) {
        if (shouldDeferProviderStream && isProviderStreamEvent(event)) {
          deferProviderStreamEvent(event as QueryYield)
          continue
        }
        yield event
        continue
      }
      const sanitizedCandidate = sanitizeVisibleAssistantControlTokens(event)
      if (
        shouldBlockPromptInjectionToolRecovery({
          messages,
          candidate: sanitizedCandidate,
          activeToolChoiceName,
        })
      ) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_prompt_injection_tool_recovery',
          querySource: String(params.querySource),
          messages,
          assistantMessage: sanitizedCandidate,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        const blockedMessage = createPromptInjectionToolRecoveryBlockedMessage()
        yield* streamGuardedAssistantMessage({
          message: blockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(blockedMessage)
        return Terminal.completed()
      }
      const assistantCandidate = upgradeRawJsonToolCallAssistant({
        assistantMessage: sanitizedCandidate,
        createToolUseId: () => createRecoveredRawJsonToolUseId(deps.uuid()),
      })
      if (
        toolUseBlocks(assistantCandidate).length === 0 &&
        textContainsMalformedToolCallProposal(messageText(assistantCandidate))
      ) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_malformed_tool_proposal',
          querySource: String(params.querySource),
          messages,
          assistantMessage: assistantCandidate,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        const blockedMessage = createMalformedToolProposalBlockedMessage()
        yield* streamGuardedAssistantMessage({
          message: blockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(blockedMessage)
        return Terminal.completed()
      }

      const boundary = enforceSupportToolBoundary({
        activeToolChoiceName,
        activeToolChoiceAvailable,
        messagesForQuery: messages,
        assistantMessage: assistantCandidate,
      })
      if (
        boundary.kind === 'pass' &&
        shouldBlockUnsupportedRouteDetailAnswer({
          messages,
          candidate: boundary.message,
        })
      ) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_unsupported_route_detail',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        const blockedMessage = createUnsupportedRouteFinalAnswerBlockedMessage()
        yield* streamGuardedAssistantMessage({
          message: blockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(blockedMessage)
        return Terminal.completed()
      }
      if (
        boundary.kind === 'pass' &&
        shouldBlockStalePriorToolResultAnswer({
          messages,
          candidate: boundary.message,
        })
      ) {
        const repeatedReadOnlyStalePriorRepairPrompt =
          repeatedReadOnlyStalePriorToolResultRepairPrompt({
            messages,
            candidate: boundary.message,
          })
        if (repeatedReadOnlyStalePriorRepairPrompt !== undefined) {
          appendQueryAssistantDiagnostic({
            event: 'query_assistant_repaired_repeated_stale_prior_tool_result',
            querySource: String(params.querySource),
            messages,
            assistantMessage: boundary.message,
            turnCount,
            boundaryKind: 'pass',
            repairPromptChars: repeatedReadOnlyStalePriorRepairPrompt.length,
            continueAfterRepair: true,
          })
          messages.push(boundary.message)
          messages.push(
            createUserMessage({
              content: repeatedReadOnlyStalePriorRepairPrompt,
              isMeta: true,
            }),
          )
          shouldContinueAfterRepairPrompt = true
          break
        }
        const currentEvidenceRepairPrompt =
          currentEvidenceStalePriorToolResultRepairPrompt({
            messages,
            candidate: boundary.message,
          })
        if (currentEvidenceRepairPrompt !== undefined) {
          appendQueryAssistantDiagnostic({
            event: 'query_assistant_repaired_current_evidence_stale_prior_tool_result',
            querySource: String(params.querySource),
            messages,
            assistantMessage: boundary.message,
            turnCount,
            boundaryKind: 'pass',
            repairPromptChars: currentEvidenceRepairPrompt.length,
            continueAfterRepair: true,
          })
          messages.push(boundary.message)
          messages.push(
            createUserMessage({
              content: currentEvidenceRepairPrompt,
              isMeta: true,
            }),
          )
          shouldContinueAfterRepairPrompt = true
          break
        }
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_stale_prior_tool_result',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        const blockedMessage = createStalePriorToolResultFinalAnswerBlockedMessage()
        yield* streamGuardedAssistantMessage({
          message: blockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(blockedMessage)
        return Terminal.completed()
      }
      const publicDataRepairPrompt = boundary.kind === 'pass'
        ? buildPublicDataTerminalRepairPrompt({
            messages,
            candidate: boundary.message,
          })
        : undefined
      if (publicDataRepairPrompt !== undefined) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_withheld_for_repair',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: boundary.kind,
          repairPromptChars: publicDataRepairPrompt.length,
          continueAfterRepair: true,
        })
        messages.push(boundary.message)
        messages.push(
          createUserMessage({
            content: publicDataRepairPrompt,
            isMeta: true,
          }),
        )
        shouldContinueAfterRepairPrompt = true
        break
      }
      const aedGuardMessage = boundary.kind === 'pass'
        ? nmcAedEvidenceGuard({
            messages,
            candidate: boundary.message,
          })
        : undefined
      if (aedGuardMessage !== undefined) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_replaced_nmc_aed_with_evidence_summary',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        yield* streamGuardedAssistantMessage({
          message: aedGuardMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(aedGuardMessage)
        return Terminal.completed()
      }
      const hospitalGuardMessage = boundary.kind === 'pass'
        ? hiraHospitalEvidenceGuard({
            messages,
            candidate: boundary.message,
          })
        : undefined
      if (hospitalGuardMessage !== undefined) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_replaced_hira_hospital_with_evidence_summary',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        yield* streamGuardedAssistantMessage({
          message: hospitalGuardMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(hospitalGuardMessage)
        return Terminal.completed()
      }
      const ungroundedPublicDataRepairPrompt = boundary.kind === 'pass'
        ? ungroundedPublicDataFinalRepairPrompt({
            messages,
            candidate: boundary.message,
          })
        : undefined
      if (ungroundedPublicDataRepairPrompt !== undefined) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_repaired_ungrounded_public_data_final',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: boundary.kind,
          repairPromptChars: ungroundedPublicDataRepairPrompt.length,
          continueAfterRepair: true,
        })
        messages.push(
          createUserMessage({
            content: ungroundedPublicDataRepairPrompt,
            isMeta: true,
          }),
        )
        shouldContinueAfterRepairPrompt = true
        break
      }
      const ungroundedPublicDataBlockedMessage = boundary.kind === 'pass'
        ? ungroundedPublicDataFinalGuard({
            messages,
            candidate: boundary.message,
          })
        : undefined
      if (ungroundedPublicDataBlockedMessage !== undefined) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_ungrounded_public_data_final',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        yield* streamGuardedAssistantMessage({
          message: ungroundedPublicDataBlockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(ungroundedPublicDataBlockedMessage)
        return Terminal.completed()
      }
      if (
        boundary.kind === 'pass' &&
        shouldBlockEmergencyResultClaim({
          messages,
          candidate: boundary.message,
        })
      ) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_emergency_no_claim',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        const blockedMessage = createEmergencyNoClaimBlockedMessage()
        yield* streamGuardedAssistantMessage({
          message: blockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(blockedMessage)
        return Terminal.completed()
      }
      const weatherGuardMessage = boundary.kind === 'pass'
        ? kmaWeatherEvidenceGuard({
            messages,
            candidate: boundary.message,
          })
        : undefined
      if (weatherGuardMessage !== undefined) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_replaced_kma_weather_with_evidence_summary',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        yield* streamGuardedAssistantMessage({
          message: weatherGuardMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(weatherGuardMessage)
        return Terminal.completed()
      }
      if (
        boundary.kind === 'pass' &&
        shouldBlockFinalAnswerAfterUnavailableToolRepair({
          messages,
          candidate: boundary.message,
        })
      ) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_after_unavailable_tool_repair',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        const blockedMessage = createUnavailableToolFinalAnswerBlockedMessage(messages)
        yield* streamGuardedAssistantMessage({
          message: blockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(blockedMessage)
        return Terminal.completed()
      }
      const protectedBypassFinalMessage = boundary.kind === 'pass'
        ? protectedBypassPromptFinalAnswerGuard({
            messages,
            candidate: boundary.message,
          })
        : undefined
      if (protectedBypassFinalMessage !== undefined) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_protected_bypass_final_answer',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        yield* streamGuardedAssistantMessage({
          message: protectedBypassFinalMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(protectedBypassFinalMessage)
        return Terminal.completed()
      }
      const failedToolGuardMessage = boundary.kind === 'pass'
        ? failedToolFinalAnswerGuard({
            messages,
            candidate: boundary.message,
          })
        : undefined
      if (failedToolGuardMessage !== undefined) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_replaced_failed_tool_fabrication',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        yield* streamGuardedAssistantMessage({
          message: failedToolGuardMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(failedToolGuardMessage)
        return Terminal.completed()
      }
      if (
        boundary.kind === 'pass' &&
        shouldBlockFinalAnswerAfterUnsupportedRouteRepair({
          messages,
          candidate: boundary.message,
        })
      ) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_after_unsupported_route_repair',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        const blockedMessage = createUnsupportedRouteFinalAnswerBlockedMessage()
        yield* streamGuardedAssistantMessage({
          message: blockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(blockedMessage)
        return Terminal.completed()
      }
      if (
        boundary.kind === 'pass' &&
        shouldBlockToolUseAfterGenericPendingFinalAnswerRepair({
          messages,
          candidate: boundary.message,
        })
      ) {
        appendQueryAssistantDiagnostic({
          event: 'query_assistant_blocked_after_final_repair',
          querySource: String(params.querySource),
          messages,
          assistantMessage: boundary.message,
          turnCount,
          boundaryKind: 'block',
          repairPromptChars: 0,
          continueAfterRepair: false,
        })
        const blockedMessage = createGenericPendingFinalAnswerToolUseBlockedMessage()
        yield* streamGuardedAssistantMessage({
          message: blockedMessage,
          messages,
          querySource: String(params.querySource),
          turnCount,
          enabled: guardedPreviewEnabled,
        })
        messages.push(blockedMessage)
        return Terminal.completed()
      }
      if (boundary.kind === 'pass') {
        const protectedBypassBlockedMessage = protectedBypassPromptActionGuard({
          messages,
          candidate: boundary.message,
        })
        if (protectedBypassBlockedMessage !== undefined) {
          appendQueryAssistantDiagnostic({
            event: 'query_assistant_blocked_protected_bypass_request',
            querySource: String(params.querySource),
            messages,
            assistantMessage: boundary.message,
            turnCount,
            boundaryKind: 'block',
            repairPromptChars: 0,
            continueAfterRepair: false,
          })
          yield* streamGuardedAssistantMessage({
            message: protectedBypassBlockedMessage,
            messages,
            querySource: String(params.querySource),
            turnCount,
            enabled: guardedPreviewEnabled,
          })
          messages.push(protectedBypassBlockedMessage)
          return Terminal.completed()
        }
        const readOnlySendRepairPrompt = readOnlySendPromptActionRepairPrompt({
          messages,
          candidate: boundary.message,
        })
        if (readOnlySendRepairPrompt !== undefined) {
          appendQueryAssistantDiagnostic({
            event: 'query_assistant_repaired_read_only_send_request',
            querySource: String(params.querySource),
            messages,
            assistantMessage: boundary.message,
            turnCount,
            boundaryKind: 'pass',
            repairPromptChars: readOnlySendRepairPrompt.length,
            continueAfterRepair: true,
          })
          messages.push(
            createUserMessage({
              content: readOnlySendRepairPrompt,
              isMeta: true,
            }),
          )
          shouldContinueAfterRepairPrompt = true
          break
        }
        const readOnlySendBlockedMessage = readOnlySendPromptActionGuard({
          messages,
          candidate: boundary.message,
        })
        if (readOnlySendBlockedMessage !== undefined) {
          appendQueryAssistantDiagnostic({
            event: 'query_assistant_blocked_read_only_send_request',
            querySource: String(params.querySource),
            messages,
            assistantMessage: boundary.message,
            turnCount,
            boundaryKind: 'block',
            repairPromptChars: 0,
            continueAfterRepair: false,
          })
          yield* streamGuardedAssistantMessage({
            message: readOnlySendBlockedMessage,
            messages,
            querySource: String(params.querySource),
            turnCount,
            enabled: guardedPreviewEnabled,
          })
          messages.push(readOnlySendBlockedMessage)
          return Terminal.completed()
        }
        const protectedActionBlockedMessage = protectedActionAfterFailedToolGuard({
          messages,
          candidate: boundary.message,
        })
        if (protectedActionBlockedMessage !== undefined) {
          appendQueryAssistantDiagnostic({
            event: 'query_assistant_blocked_after_failed_tool',
            querySource: String(params.querySource),
            messages,
            assistantMessage: boundary.message,
            turnCount,
            boundaryKind: 'block',
            repairPromptChars: 0,
            continueAfterRepair: false,
          })
          yield* streamGuardedAssistantMessage({
            message: protectedActionBlockedMessage,
            messages,
            querySource: String(params.querySource),
            turnCount,
            enabled: guardedPreviewEnabled,
          })
          messages.push(protectedActionBlockedMessage)
          return Terminal.completed()
        }
      }
      appendQueryAssistantDiagnostic({
        event: 'query_assistant_yield',
        querySource: String(params.querySource),
        messages,
        assistantMessage: boundary.message,
        turnCount,
        boundaryKind: boundary.kind,
        repairPromptChars: 0,
        continueAfterRepair: false,
      })
      if (boundary.kind === 'pass') {
        yield* flushDeferredProviderStreamEvents('accepted_assistant')
      }
      yield boundary.message
      assistantMessage = boundary.message
      messages.push(boundary.message)
      if (boundary.kind === 'block') return Terminal.completed()
      break
    }

    if (shouldContinueAfterRepairPrompt) continue
    if (!assistantMessage) {
      yield* flushDeferredProviderStreamEvents('completed_without_assistant')
      appendQueryCompletedWithoutAssistantDiagnostic({
        querySource: String(params.querySource),
        messages,
        turnCount,
      })
      return Terminal.completed()
    }
    const toolUses = toolUseBlocks(assistantMessage)
    if (toolUses.length === 0) return Terminal.completed()
    if (params.toolUseContext.abortController.signal.aborted) {
      return Terminal.aborted_tools()
    }

    const toolResults: Message[] = []
    let shouldCompleteAfterHardGuard = false
    for (let blockIndex = 0; blockIndex < toolUses.length; blockIndex += 1) {
      const block = toolUses[blockIndex]
      if (!block) continue
      if (shouldBlockRepeatedPermissionDeniedTool(block, messages)) {
        toolResults.push(
          createPermissionDeniedContinuationGuardResult(block, assistantMessage),
        )
      } else if (shouldBlockRepeatedAdapterlessFind(block, messages)) {
        toolResults.push(
          createAdapterlessFindContinuationGuardResult(block, assistantMessage),
        )
        toolResults.push(createAdapterlessFindHardGuardFinalMessage())
        shouldCompleteAfterHardGuard = true
      } else {
        const blockResults = await runToolUseBlocks({
          blocks: [block],
          assistantMessage,
          messages: [...messages, ...toolResults],
          toolUseContext: params.toolUseContext,
          canUseTool: params.canUseTool,
        })
        toolResults.push(...blockResults.map(upgradeUnavailableToolResultMessage))
        const nextAdapterlessFind = toolUses
          .slice(blockIndex + 1)
          .find(isAdapterlessFindToolUse)
        if (
          isAdapterlessFindToolUse(block) &&
          nextAdapterlessFind !== undefined &&
          hasAdapterlessFindFailure([...messages, ...toolResults])
        ) {
          toolResults.push(
            createAdapterlessFindContinuationGuardResult(nextAdapterlessFind, assistantMessage),
          )
          toolResults.push(createAdapterlessFindHardGuardFinalMessage())
          shouldCompleteAfterHardGuard = true
          break
        }
      }
    }

    for (const result of toolResults) {
      if (params.toolUseContext.abortController.signal.aborted) {
        return Terminal.aborted_tools()
      }
      messages.push(result)
      yield result
    }
    const domainGuardFinalAnswer = domainGuardFinalAnswerForToolResults(toolResults)
    if (domainGuardFinalAnswer !== undefined) {
      yield* streamGuardedAssistantMessage({
        message: domainGuardFinalAnswer,
        messages,
        querySource: String(params.querySource),
        turnCount,
        enabled: guardedPreviewEnabled,
      })
      messages.push(domainGuardFinalAnswer)
      return Terminal.completed()
    }
    if (shouldCompleteAfterHardGuard) return Terminal.completed()
    const documentCompletionPrompt = buildDocumentCompletionPromptIfNeeded({
      messages,
    })
    if (documentCompletionPrompt !== undefined) {
      messages.push(
        createUserMessage({
          content: documentCompletionPrompt,
          isMeta: true,
        }),
      )
    }
  }

  return Terminal.max_turns(turnCount)
}
