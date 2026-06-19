import type { AssistantMessage, Message } from '../types/message.js'
import {
  buildGenericPendingFinalAnswerRepairPromptIfNeeded,
  shouldWithholdGenericPendingFinalAnswer,
} from '../tools/_shared/toolChoiceRepair/publicDataRepair.js'
import {
  contentBlocks,
  isUserMessage,
  latestTextUserMessageIndex,
  messageText,
  toolUseBlocks,
} from './messageGuards.js'
import {
  buildUnavailableToolRepairPromptIfNeeded,
} from './unavailableToolRepair.js'

export {
  buildUnavailableToolFinalAnswerBlockedText,
  shouldBlockFinalAnswerAfterUnavailableToolRepair,
} from './unavailableToolRepair.js'

const UNSUPPORTED_ROUTE_REPAIR_MARKER = 'Unsupported route answer repair:'
const ROUTE_REQUEST_RE =
  /(경로|대중교통|길\s*찾|길찾|어떻게\s*가|가는\s*법|환승|route|transit|directions|public\s+transport)/iu
const ROUTE_LIMITATION_RE =
  /(실시간\s*(경로|대중교통|교통).*(제한|없|지원하지|연결되지)|경로\s*adapter|대중교통\s*adapter|공식.*(지도|교통|앱)|카카오맵|네이버\s*지도)/iu
const ROUTE_DETAIL_CLAIM_RE =
  /(\d+\s*호선|[0-9０-９]+\s*번\s*버스|승차|하차|환승\s*(하면|후|→|->)|요금[^\n.。]*\d|(?:약|대략)?\s*\d+\s*분(?:입니다|정도|소요)?)/iu
const EXPLICIT_PRIOR_RESULT_REQUEST_RE =
  /(이전|전에|아까|방금|앞서|지난|다시|그\s*(결과|검색|병원|곳|장소|정보)|prior|previous|again)/iu
const RELATIVE_LOCATION_FOLLOWUP_RE =
  /(주위|주변|우리\s*동네|여기|이\s*근처|현재\s*위치|내\s*위치|가까운|가까이|인근|근방)/iu
const LOCATION_SCOPED_PUBLIC_DATA_RE =
  /(응급|응급실|야간\s*진료|야간진료|병원|의료|날씨|비\s*(?:와|오|올|내리)|우산|미세먼지|대기질|공기질|emergency|hospital|weather|rain|umbrella|air\s*quality)/iu
const PENDING_TOOL_ACTION_RE =
  /(조회하겠습니다|찾아보겠습니다|검색해\s*보겠습니다|검색하겠습니다|확인해\s*보겠습니다|확인하겠습니다|찾기\s*위해|조회하기\s*위해|검색하기\s*위해)/iu
const PENDING_TOOL_ACTION_REPAIR_MARKER = 'Pending tool action repair:'
const LOCATION_RESULT_KINDS = new Set([
  'coords',
  'address',
  'adm_cd',
  'poi',
  'region',
  'bundle',
])
const SENSITIVE_SCALAR_KEY_RE =
  /(^|[_\-.])(?:id|no|num|number|code|receipt|ref|reference|token|auth|authorization|approval|confirm|confirmation|certificate|serial|registration|payment|tax|amount|fee|price|cost|total|balance|claim|case|application|tracking|invoice|bill|번호|코드|접수|영수|승인|인증|토큰|증명|증서|등록|납부|결제|세금|세액|금액|요금|합계|잔액|청구|사건|신청|추적|송장)(?:$|[_\-.])/iu
const CODE_LIKE_SCALAR_RE = /^[0-9A-Za-z][0-9A-Za-z._:-]*$/u

type ToolResultBlock = {
  readonly type: 'tool_result'
  readonly tool_use_id: string
  readonly content?: unknown
  readonly is_error?: boolean
}

export function buildPublicDataTerminalRepairPrompt(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): string | undefined {
  const unavailableToolRepairPrompt =
    buildUnavailableToolRepairPromptIfNeeded(params)
  if (unavailableToolRepairPrompt !== undefined) {
    return unavailableToolRepairPrompt
  }
  const pendingToolActionPrompt =
    buildPendingToolActionRepairPromptIfNeeded(params)
  if (pendingToolActionPrompt !== undefined) {
    return pendingToolActionPrompt
  }
  if (
    shouldWithholdGenericPendingFinalAnswer({
      messages: params.messages,
      candidate: params.candidate,
    })
  ) {
    return buildGenericPendingFinalAnswerRepairPromptIfNeeded({
      messages: [...params.messages, params.candidate],
    })
  }
  if (shouldWithholdUnsupportedRouteAnswer(params)) {
    return buildUnsupportedRouteRepairPrompt()
  }
  return undefined
}

export function shouldBlockFinalAnswerAfterUnsupportedRouteRepair(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): boolean {
  return hasUnsupportedRouteRepairPromptAfterLatestUser(params.messages) &&
    toolUseBlocks(params.candidate).length === 0
}

export function shouldBlockUnsupportedRouteDetailAnswer(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): boolean {
  if (toolUseBlocks(params.candidate).length > 0) return false
  if (!isLatestUserRouteRequest(params.messages)) return false
  if (!hasOnlyLocationEvidenceAfterLatestUser(params.messages)) return false
  return ROUTE_DETAIL_CLAIM_RE.test(messageText(params.candidate))
}

export function shouldBlockStalePriorToolResultAnswer(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): boolean {
  if (toolUseBlocks(params.candidate).length > 0) return false
  const latestUserIndex = latestTextUserMessageIndex(params.messages)
  if (latestUserIndex < 0) return false
  const latestUser = params.messages[latestUserIndex]
  if (latestUser === undefined) return false
  const latestUserText = messageText(latestUser)
  if (EXPLICIT_PRIOR_RESULT_REQUEST_RE.test(latestUserText)) return false

  const currentPhrases = successfulToolResultPhrases(
    params.messages.slice(latestUserIndex + 1),
  )
  const currentEvidenceText = [...currentPhrases, latestUserText]
    .map(normalizePhraseText)
    .join('\n')
  const candidateText = normalizePhraseText(messageText(params.candidate))
  if (candidateText.length === 0) return false

  for (const phrase of successfulToolResultPhrases(
    params.messages.slice(0, latestUserIndex),
    { excludeLocationResults: RELATIVE_LOCATION_FOLLOWUP_RE.test(latestUserText) },
  )) {
    const normalizedPhrase = normalizePhraseText(phrase)
    if (normalizedPhrase.length === 0) continue
    if (currentEvidenceText.includes(normalizedPhrase)) continue
    if (candidateText.includes(normalizedPhrase)) return true
  }
  return false
}

export function buildUnsupportedRouteFinalAnswerBlockedText(): string {
  return [
    '현재 UMMAYA 실행 도구 표면에는 실시간 경로 adapter 결과가 없습니다.',
    '이번 턴에서 확인된 것은 출발지/도착지 위치 결과뿐이므로 환승역, 버스번호, 요금, 소요시간을 단정하지 않습니다.',
    '실시간 이동 경로는 카카오맵, 네이버지도, 부산교통공사 등 공식 교통 채널에서 확인해야 합니다.',
  ].join('\n\n')
}

export function buildStalePriorToolResultFinalAnswerBlockedText(): string {
  return [
    '이번 턴에서 확인되지 않은 이전 도구 결과를 현재 요청의 근거로 재사용하지 않습니다.',
    '현재 답변은 최신 사용자 요청 이후 실행된 tool_result에 근거해야 하며, 이전 검색 결과를 새 위치나 새 조건의 결과처럼 단정할 수 없습니다.',
    '필요한 정보는 해당 위치와 조건에 맞는 등록 adapter 결과를 다시 받은 뒤 안내해야 합니다.',
  ].join('\n\n')
}

function buildPendingToolActionRepairPromptIfNeeded(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): string | undefined {
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  if (hasPendingToolActionRepairPromptAfterLatestUser(params.messages)) {
    return undefined
  }
  const latestUserIndex = latestTextUserMessageIndex(params.messages)
  if (latestUserIndex < 0) return undefined
  const latestUser = params.messages[latestUserIndex]
  if (latestUser === undefined) return undefined
  const latestUserText = messageText(latestUser)
  if (!RELATIVE_LOCATION_FOLLOWUP_RE.test(latestUserText)) return undefined
  if (!LOCATION_SCOPED_PUBLIC_DATA_RE.test(latestUserText)) return undefined
  if (hasSuccessfulToolResultAfter(params.messages, latestUserIndex)) {
    return undefined
  }
  if (!hasLocationEvidenceBefore(params.messages, latestUserIndex)) {
    return undefined
  }
  if (!PENDING_TOOL_ACTION_RE.test(messageText(params.candidate))) {
    return undefined
  }
  return [
    `${PENDING_TOOL_ACTION_REPAIR_MARKER} the assistant ended with a promise to look up current public-service data, but no tool_result exists for the latest citizen request.`,
    'Use the prior location context only as input context, then call a registered adapter tool now when one is available in the current tool schema.',
    'If no registered adapter supports the request, write a Korean fail-closed limitation; do not end with 조회하겠습니다, 확인하겠습니다, 검색하겠습니다, or another promise to answer later.',
  ].join(' ')
}

function hasPendingToolActionRepairPromptAfterLatestUser(
  messages: readonly Message[],
): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  return messages.slice(latestUserIndex + 1).some(message =>
    messageText(message).includes(PENDING_TOOL_ACTION_REPAIR_MARKER),
  )
}

function shouldWithholdUnsupportedRouteAnswer(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): boolean {
  if (toolUseBlocks(params.candidate).length > 0) return false
  if (hasUnsupportedRouteRepairPromptAfterLatestUser(params.messages)) return false
  if (!isLatestUserRouteRequest(params.messages)) return false
  if (!hasOnlyLocationEvidenceAfterLatestUser(params.messages)) return false
  return !ROUTE_LIMITATION_RE.test(messageText(params.candidate))
}

function buildUnsupportedRouteRepairPrompt(): string {
  return [
    `${UNSUPPORTED_ROUTE_REPAIR_MARKER} successful tool_result evidence only located places; no routing, realtime transit, fare, or directions adapter returned route data.`,
    'Do not provide transfer stations, bus numbers, fares, travel times, or step-by-step route instructions from general knowledge.',
    'Write a Korean limitation/handoff answer grounded only in the location tool_results and tell the citizen to verify realtime route details in official transit/map channels.',
  ].join(' ')
}

function isLatestUserRouteRequest(messages: readonly Message[]): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  const latestUser = messages[latestUserIndex]
  return latestUser !== undefined && ROUTE_REQUEST_RE.test(messageText(latestUser))
}

function hasUnsupportedRouteRepairPromptAfterLatestUser(
  messages: readonly Message[],
): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  return messages.slice(latestUserIndex + 1).some(message =>
    messageText(message).includes(UNSUPPORTED_ROUTE_REPAIR_MARKER),
  )
}

function hasOnlyLocationEvidenceAfterLatestUser(messages: readonly Message[]): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  const successfulResults = messages
    .slice(latestUserIndex + 1)
    .flatMap(message => isUserMessage(message) ? toolResultBlocks(message) : [])
    .filter(block => block.is_error !== true)
  return successfulResults.length > 0 &&
    successfulResults.every(block => isLocationToolResult(block.content))
}

function hasLocationEvidenceBefore(
  messages: readonly Message[],
  endIndex: number,
): boolean {
  return messages.slice(0, endIndex).some(message =>
    isUserMessage(message) &&
    toolResultBlocks(message).some(block =>
      block.is_error !== true && isLocationToolResult(block.content),
    ),
  )
}

function successfulToolResultPhrases(
  messages: readonly Message[],
  options: { readonly excludeLocationResults?: boolean } = {},
): Set<string> {
  const phrases = new Set<string>()
  for (const message of messages) {
    if (!isUserMessage(message)) continue
    for (const block of toolResultBlocks(message)) {
      if (block.is_error === true) continue
      if (options.excludeLocationResults === true && isLocationToolResult(block.content)) {
        continue
      }
      collectSalientPhrases(block.content, phrases)
    }
  }
  return phrases
}

function collectSalientPhrases(
  value: unknown,
  phrases: Set<string>,
  keyHint?: string,
): void {
  if (typeof value === 'string') {
    const parsed = parseJsonObject(value)
    if (parsed !== undefined) {
      collectSalientPhrases(parsed, phrases)
      return
    }
    addSalientPhrase(value, phrases, keyHint)
    return
  }
  if (typeof value === 'number') {
    if (Number.isFinite(value)) {
      addSalientPhrase(String(value), phrases, keyHint)
    }
    return
  }
  if (Array.isArray(value)) {
    for (const item of value) collectSalientPhrases(item, phrases, keyHint)
    return
  }
  if (typeof value !== 'object' || value === null) return
  for (const [key, entry] of Object.entries(value)) {
    collectSalientPhrases(entry, phrases, key)
  }
}

function addSalientPhrase(
  value: string,
  phrases: Set<string>,
  keyHint?: string,
): void {
  const phrase = normalizePhraseText(value)
  if (
    !isSalientToolResultPhrase(phrase) &&
    !isSensitiveScalarToolResultPhrase(keyHint, phrase)
  ) {
    return
  }
  phrases.add(phrase)
}

function normalizePhraseText(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function isSalientToolResultPhrase(value: string): boolean {
  if (value.length < 3 || value.length > 80) return false
  if (!/[A-Za-z가-힣]/u.test(value)) return false
  if (/^(ok|true|false|null|none|unknown|collection|bundle|coords|address|region|poi|mock_complete)$/iu.test(value)) {
    return false
  }
  return true
}

function isSensitiveScalarToolResultPhrase(
  keyHint: string | undefined,
  value: string,
): boolean {
  if (keyHint === undefined) return false
  if (!SENSITIVE_SCALAR_KEY_RE.test(keyHint)) return false
  if (value.length < 3 || value.length > 80) return false
  if (!/[0-9]/u.test(value)) return false
  if (!CODE_LIKE_SCALAR_RE.test(value)) return false
  if (/^(ok|true|false|null|none|unknown|success)$/iu.test(value)) return false
  return true
}

function isLocationToolResult(content: unknown): boolean {
  const parsed = parseJsonObject(content)
  if (parsed === undefined) return false
  const data = parseJsonObject(parsed.data)
  const result = parseJsonObject(parsed.result) ??
    (data !== undefined ? parseJsonObject(data.result) : undefined)
  const kind = result?.kind
  return typeof kind === 'string' && LOCATION_RESULT_KINDS.has(kind)
}

function parseJsonObject(value: unknown): Record<string, unknown> | undefined {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  if (typeof value !== 'string') return undefined
  try {
    const parsed: unknown = JSON.parse(value)
    return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : undefined
  } catch {
    return undefined
  }
}

function hasSuccessfulToolResultAfter(
  messages: readonly Message[],
  startIndex: number,
): boolean {
  return messages.slice(startIndex + 1).some(message =>
    isUserMessage(message) &&
    toolResultBlocks(message).some(block => block.is_error !== true),
  )
}

function toolResultBlocks(message: Message): readonly ToolResultBlock[] {
  return contentBlocks(message).filter(
    (block): block is ToolResultBlock =>
      block.type === 'tool_result' &&
      typeof block.tool_use_id === 'string',
  )
}
