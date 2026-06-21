import type { AssistantMessage, Message } from '../types/message.js'
import {
  contentBlocks,
  isUserMessage,
  latestTextUserMessageIndex,
  messageText,
  toolUseBlocks,
} from './messageGuards.js'
import {
  parseAdapterNotFoundToolName,
  parseToolUnavailableError,
} from './toolResultErrors.js'

const UNAVAILABLE_TOOL_REPAIR_MARKER = 'Unavailable tool boundary:'
const MAJOR_CITY_RE =
  '(?:서울|인천|대전|대구|광주|부산|울산|세종|수원|성남|고양|용인|청주|천안|전주|포항|창원|김해|진주|여수|순천|목포|강릉|춘천|원주|제주|서귀포)'
const ROAD_HAZARD_RE =
  '(?:교통사고|사고\\s*위험|사고다발|위험\\s*(?:구간|도로|지점)|도로교통공단|KOROAD|accident|hazard)'
const PUBLIC_TRANSPORT_RE =
  '(?:대중\\s*교통|교통편|교통\\s*수단|고속\\s*버스|시외\\s*버스|버스|열차|기차|KTX|SRT|철도|지하철)'
const INTERCITY_PUBLIC_TRANSPORT_REQUEST_RE = new RegExp(
  `(?!.*${ROAD_HAZARD_RE})(?=.*${PUBLIC_TRANSPORT_RE})${MAJOR_CITY_RE}[^\\n]{0,24}(?:에서|부터)[^\\n]{0,80}${MAJOR_CITY_RE}[^\\n]{0,24}(?:까지|로|으로|도착|이동|가는)`,
  'iu',
)

type ToolResultBlock = {
  readonly type: 'tool_result'
  readonly tool_use_id: string
  readonly content?: unknown
  readonly is_error?: boolean
}

export function shouldBlockFinalAnswerAfterUnavailableToolRepair(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): boolean {
  const repairPromptIndex = latestUnavailableToolRepairPromptIndex(params.messages)
  return repairPromptIndex >= 0 &&
    !hasSuccessfulToolResultAfter(params.messages, repairPromptIndex) &&
    toolUseBlocks(params.candidate).length === 0
}

export function hasUnavailableToolResultAfterLatestUser(
  messages: readonly Message[],
): boolean {
  return unavailableToolNamesAfterLatestUser(messages).length > 0
}

export function isIntercityPublicTransportRequestText(text: string): boolean {
  return INTERCITY_PUBLIC_TRANSPORT_REQUEST_RE.test(text)
}

export function buildUnavailableToolFinalAnswerBlockedText(
  latestUserText = '',
): string {
  if (isIntercityPublicTransportRequestText(latestUserText)) {
    return [
      '서울-대전 같은 도시 간 대중교통은 TAGO 시내버스 도구 범위가 아닙니다.',
      '공식 공공데이터에는 국토교통부 TAGO 고속버스정보와 TAGO 시외버스정보 채널이 별도로 있으나, 현재 UMMAYA에는 해당 intercity adapter가 등록되어 있지 않습니다.',
      '시간표, 요금, 노선 ID, 터미널 정보를 만들지 않고 고속·시외버스/철도 공식 채널 확인으로 handoff합니다.',
    ].join('\n\n')
  }

  return [
    '현재 등록된 UMMAYA 도구로는 이 요청을 직접 조회하거나 완료하지 못했습니다.',
    '검증된 도구 결과 없이 기관명, 서류 목록, 처리 결과를 단정하지 않겠습니다.',
    '공식 채널에서 확인하거나, 해당 업무 adapter가 연결된 뒤 다시 처리해야 합니다.',
  ].join('\n\n')
}

export function buildUnavailableToolRepairPromptIfNeeded(params: {
  readonly messages: readonly Message[]
  readonly candidate: AssistantMessage
}): string | undefined {
  const blockedToolNames = unavailableToolNamesAfterLatestUser(params.messages)
  if (blockedToolNames.length === 0) return undefined
  if (toolUseBlocks(params.candidate).length > 0) return undefined
  if (hasUnavailableToolRepairPromptAfterLatestUser(params.messages)) {
    return undefined
  }
  return [
    `${UNAVAILABLE_TOOL_REPAIR_MARKER} ${blockedToolNames.join(', ')} returned an unavailable adapter error and did not execute.`,
    'Call a different registered tool from the provided schema only when it actually supports the citizen request.',
    'If no registered tool supports the request, do not claim data, search results, submissions, verification, or successful work; finish with a Korean blocked or handoff answer grounded only in the unavailable tool_result.',
  ].join(' ')
}

function unavailableToolNamesAfterLatestUser(
  messages: readonly Message[],
): readonly string[] {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return []
  const names = new Set<string>()
  for (let index = latestUserIndex + 1; index < messages.length; index += 1) {
    const message = messages[index]
    if (!message || !isUserMessage(message)) continue
    for (const block of toolResultBlocks(message)) {
      if (block.is_error !== true) continue
      const unavailable = parseUnavailableToolName(block.content)
      if (unavailable !== undefined) names.add(unavailable)
    }
  }
  return [...names]
}

function parseUnavailableToolName(content: unknown): string | undefined {
  return parseToolUnavailableError(content)?.error.tool_name ??
    parseAdapterNotFoundToolName(content)
}

function hasUnavailableToolRepairPromptAfterLatestUser(
  messages: readonly Message[],
): boolean {
  return latestUnavailableToolRepairPromptIndex(messages) >= 0
}

function latestUnavailableToolRepairPromptIndex(
  messages: readonly Message[],
): number {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return -1
  for (let index = messages.length - 1; index > latestUserIndex; index -= 1) {
    const message = messages[index]
    if (message !== undefined &&
      messageText(message).includes(UNAVAILABLE_TOOL_REPAIR_MARKER)) {
      return index
    }
  }
  return -1
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
