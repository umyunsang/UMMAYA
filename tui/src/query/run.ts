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
const KMA_FORECAST_TOOL_NAMES = new Set([
  'kma_forecast_fetch',
  'kma_short_term_forecast',
  'kma_ultra_short_term_forecast',
])
const REGISTERED_EMERGENCY_RESULT_TOOL_NAMES = new Set([
  'nmc_emergency_search',
  'hira_hospital_search',
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
const WEATHER_CANDIDATE_CLAIM_RE =
  /(날씨|기상|weather|예보|현재\s*기온|강수|습도|풍속|하늘상태|하늘\s*상태)/iu
const WEATHER_NO_EVIDENCE_SAFE_RE =
  /(지역|주소|위치)[^\n.。]*(?:알려|입력|필요)|(?:조회|확인)하지\s*못|adapter\s*결과\s*없이|단정하지|제한/iu
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
  return parseJsonRecord(value)?.ok === false
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
        toolNamesByUseId.set(block.id, block.name)
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
  if (!WEATHER_RESULT_REQUEST_RE.test(latestUserText(params.messages))) {
    return undefined
  }
  const results = toolResultsSinceLatestPrompt(params.messages)
  const item = results.map(kmaCurrentObservationItem).find(item => item !== undefined)
  const forecastItems = results.flatMap(result => [...kmaForecastItems(result)])
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
  })
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
        yield blockedMessage
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
        yield blockedMessage
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
        yield blockedMessage
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
        yield blockedMessage
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
        yield blockedMessage
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
        yield weatherGuardMessage
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
        yield blockedMessage
        messages.push(blockedMessage)
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
        yield blockedMessage
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
        yield blockedMessage
        messages.push(blockedMessage)
        return Terminal.completed()
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
      yield boundary.message
      assistantMessage = boundary.message
      messages.push(boundary.message)
      if (boundary.kind === 'block') return Terminal.completed()
      break
    }

    if (shouldContinueAfterRepairPrompt) continue
    if (!assistantMessage) {
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
      messages.push(domainGuardFinalAnswer)
      yield domainGuardFinalAnswer
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
