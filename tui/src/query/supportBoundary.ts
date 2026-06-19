import { createAssistantMessage } from '../utils/messages.js'
import type { AssistantMessage, Message } from '../types/message.js'
import {
  buildIgnoredDocumentToolChoiceBlockedText,
  buildIgnoredSupportToolChoiceBlockedText,
  scrubIgnoredSupportToolChoiceMessage,
  shouldWithholdIgnoredDocumentToolChoiceText,
  shouldWithholdIgnoredSupportToolChoiceText,
} from '../tools/_shared/toolChoiceRepair.js'
import { selectRecoveredSupportToolNamesForQuery } from '../tools/ToolSearchTool/supportIntentHints.js'
import {
  cloneAssistantWithoutText,
  contentBlocks,
  hasAssistantToolUseNamedAfterLatestTextUser,
  latestTextUserMessageIndex,
  messageText,
  toolUseBlocks,
} from './messageGuards.js'

const ADAPTERLESS_FIND_FAILURE_RE =
  /find\(mode='fetch'\) requires a concrete adapter tool_id|No concrete adapter was selected|requires a concrete adapter tool_id|Missing or invalid fields:\s*tool_id/iu
const WORKSPACE_READ_SUMMARY_RE =
  /\bRead\s+\d+\s+files?\b(?:\s+\(ctrl\+o to expand\))?/iu

export type SupportBoundaryResult =
  | { readonly kind: 'pass'; readonly message: AssistantMessage }
  | { readonly kind: 'block'; readonly message: AssistantMessage }

function shouldWithholdIgnoredToolChoiceText(params: {
  readonly toolChoiceName: string
  readonly candidate: unknown
}): boolean {
  return shouldWithholdIgnoredSupportToolChoiceText(params) ||
    shouldWithholdIgnoredDocumentToolChoiceText(params)
}

function buildIgnoredToolChoiceBlockedText(
  toolChoiceName: string,
  toolChoiceAvailable: boolean,
): string {
  if (shouldWithholdIgnoredDocumentToolChoiceText({
    toolChoiceName,
    candidate: 'document-boundary',
  })) {
    return buildIgnoredDocumentToolChoiceBlockedText(toolChoiceAvailable)
  }
  return buildIgnoredSupportToolChoiceBlockedText(
    toolChoiceName,
    toolChoiceAvailable,
  )
}

function toolResultContentText(block: Record<string, unknown>): string {
  if (block.type !== 'tool_result') return ''
  return typeof block.content === 'string' ? block.content : ''
}

function hasAdapterlessFindFailure(messages: readonly Message[]): boolean {
  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index]
    if (!message) continue
    for (const block of contentBlocks(message)) {
      if (ADAPTERLESS_FIND_FAILURE_RE.test(toolResultContentText(block))) {
        return true
      }
    }
  }
  return false
}

function latestUserRequestsWorkspaceRead(messages: readonly Message[]): boolean {
  const latestUserIndex = latestTextUserMessageIndex(messages)
  if (latestUserIndex < 0) return false
  const latestUserMessage = messages[latestUserIndex]
  if (!latestUserMessage) return false
  return selectRecoveredSupportToolNamesForQuery(
    messageText(latestUserMessage),
  ).includes('workspace_read')
}

function shouldBlockAdapterlessFindWorkspaceSummary(params: {
  readonly messagesForQuery: readonly Message[]
  readonly assistantMessage: AssistantMessage
}): boolean {
  if (latestUserRequestsWorkspaceRead(params.messagesForQuery)) return false
  return hasAdapterlessFindFailure(params.messagesForQuery) &&
    WORKSPACE_READ_SUMMARY_RE.test(messageText(params.assistantMessage))
}

function buildAdapterlessFindWorkspaceBlockedText(): string {
  return [
    '공공서비스 adapter 선택 차단: root find가 구체적인 adapter tool_id 없이 실패했습니다.',
    '로컬 파일/워크스페이스 결과는 이 시민 업무의 근거로 사용하지 않습니다.',
    '사용 가능한 출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 adapter가 로드되면 이어서 진행하고, 현재는 공식 기관 채널 확인 또는 필요한 adapter/credential 준비가 필요합니다.',
  ].join(' ')
}

export function enforceSupportToolBoundary(params: {
  readonly activeToolChoiceName: string | undefined
  readonly activeToolChoiceAvailable: boolean
  readonly messagesForQuery: readonly Message[]
  readonly assistantMessage: AssistantMessage
}): SupportBoundaryResult {
  const { activeToolChoiceName, assistantMessage, messagesForQuery } = params
  if (
    shouldBlockAdapterlessFindWorkspaceSummary({
      messagesForQuery,
      assistantMessage,
    })
  ) {
    return {
      kind: 'block',
      message: createAssistantMessage({
        content: buildAdapterlessFindWorkspaceBlockedText(),
      }),
    }
  }
  if (!activeToolChoiceName) return { kind: 'pass', message: assistantMessage }

  const currentToolUseExists = toolUseBlocks(assistantMessage).some(
    block => block.name === activeToolChoiceName,
  )
  if (currentToolUseExists) {
    const scrubbed = scrubIgnoredSupportToolChoiceMessage({
      toolChoiceName: activeToolChoiceName,
      candidate: messageText(assistantMessage),
    })
    const shouldScrubDocumentText = shouldWithholdIgnoredDocumentToolChoiceText({
      toolChoiceName: activeToolChoiceName,
      candidate: messageText(assistantMessage),
    })
    return {
      kind: 'pass',
      message:
        scrubbed === undefined && !shouldScrubDocumentText
          ? assistantMessage
          : cloneAssistantWithoutText(assistantMessage),
    }
  }

  if (
    hasAssistantToolUseNamedAfterLatestTextUser(
      messagesForQuery,
      activeToolChoiceName,
    )
  ) {
    return { kind: 'pass', message: assistantMessage }
  }

  if (
    shouldWithholdIgnoredToolChoiceText({
      toolChoiceName: activeToolChoiceName,
      candidate: messageText(assistantMessage),
    })
  ) {
    return {
      kind: 'block',
      message: createAssistantMessage({
        content: buildIgnoredToolChoiceBlockedText(
          activeToolChoiceName,
          params.activeToolChoiceAvailable,
        ),
      }),
    }
  }

  return { kind: 'pass', message: assistantMessage }
}
