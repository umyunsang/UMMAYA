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

export function buildUnavailableToolFinalAnswerBlockedText(): string {
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
