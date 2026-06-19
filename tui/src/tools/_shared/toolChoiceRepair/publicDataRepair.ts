import type { Tools } from '../../../Tool.js'
import type { Message } from '../../../types/message.js'
import { isNonSyntheticUserMessageText } from '../citizenUserText.js'
import {
  isRecord,
  latestAssistantText,
  messageContent,
  messageRole,
  textFromContent,
} from './messageAccess.js'

type PromptParams = { readonly messages: readonly Message[] }
type CandidateWithholdParams = PromptParams & { readonly candidate: Message }

const GENERIC_PENDING_FINAL_RE =
  /(답변을?\s*제공하겠습니다|제공하겠습니다|확인해\s*보겠습니다|확인하겠습니다|조회하겠습니다|찾아보겠습니다|검색해\s*보겠습니다|검색하겠습니다|최종\s*답변은|final answer should|will\s+(?:answer|provide|check|search|look\s+up))/iu
const GENERIC_PENDING_FINAL_REPAIR_PROMPT =
  'Final answer repair: successful tool_result evidence already exists, but the previous assistant message was still a plan or promise to answer later. Write the final Korean answer now from the actual tool_result values only. Do not say 제공하겠습니다, 확인하겠습니다, 조회하겠습니다, 찾아보겠습니다, 검색해 보겠습니다, or describe what you will answer next.'
const GENERIC_PENDING_FINAL_TOOL_USE_BLOCKED_TEXT =
  '이미 도구 결과가 반환되어 최종 답변 보정이 요청되었습니다. 이 단계에서는 추가 도구를 실행하지 않습니다. 현재 확인된 도구 결과만 근거로 답변을 마무리하고, 연결되지 않은 업무는 공식 채널 확인 또는 필요한 adapter/credential 준비로 넘겨야 합니다.'

export function buildGenericPendingFinalAnswerRepairPromptIfNeeded(
  params: PromptParams,
): string | undefined {
  if (!hasToolResultAfterLatestUser(params.messages)) return undefined
  if (hasGenericPendingFinalRepairPrompt(params.messages)) return undefined
  if (!GENERIC_PENDING_FINAL_RE.test(latestAssistantText(params.messages))) {
    return undefined
  }
  return GENERIC_PENDING_FINAL_REPAIR_PROMPT
}

export function shouldWithholdGenericPendingFinalAnswer(
  params: CandidateWithholdParams,
): boolean {
  if (hasGenericPendingFinalRepairPrompt(params.messages)) return false
  if (candidateHasToolUse(params.candidate)) return false
  return buildGenericPendingFinalAnswerRepairPromptIfNeeded({
    messages: [...params.messages, params.candidate],
  }) !== undefined
}

export function shouldBlockToolUseAfterGenericPendingFinalAnswerRepair(
  params: CandidateWithholdParams,
): boolean {
  return hasGenericPendingFinalRepairPrompt(params.messages) &&
    candidateHasToolUse(params.candidate)
}

export function buildGenericPendingFinalAnswerToolUseBlockedText(): string {
  return GENERIC_PENDING_FINAL_TOOL_USE_BLOCKED_TEXT
}

export function selectUmmayaClientForcedToolUseForPublicData(_params: {
  readonly messages: readonly Message[]
  readonly tools: Tools
}): undefined {
  return undefined
}

function hasGenericPendingFinalRepairPrompt(messages: readonly Message[]): boolean {
  return messages.some(message =>
    textFromContent(messageContent(message)).includes(
      'Final answer repair: successful tool_result',
    ),
  )
}

function candidateHasToolUse(candidate: Message): boolean {
  const content = messageContent(candidate)
  return Array.isArray(content) &&
    content.some(block => isRecord(block) && block.type === 'tool_use')
}

function hasToolResultAfterLatestUser(messages: readonly Message[]): boolean {
  let latestUserIndex = -1
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (messageRole(message) !== 'user') continue
    const text = textFromContent(messageContent(message))
    if (isNonSyntheticUserMessageText(message, text)) {
      latestUserIndex = index
      break
    }
  }
  if (latestUserIndex < 0) return false
  return messages.slice(latestUserIndex + 1).some(message => {
    const content = messageContent(message)
    return Array.isArray(content) &&
      content.some(block => isRecord(block) && block.type === 'tool_result')
  })
}
