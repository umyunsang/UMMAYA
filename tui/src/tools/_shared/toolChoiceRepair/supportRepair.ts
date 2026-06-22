import type { BetaToolChoiceTool } from '../../../sdk-compat.js'
import type { Tools } from '../../../Tool.js'
import type { Message } from '../../../types/message.js'
import { selectRecoveredSupportToolNamesForQuery } from '../../ToolSearchTool/supportIntentHints.js'
import { shouldSuppressDocumentToolCallsForAnswerSynthesis } from './documentRepair.js'
import { latestUserText, textFromContent, toolUseNames } from './messageAccess.js'

const AGENT_TOOL_NAME = 'Agent'
const LIST_MCP_RESOURCES_TOOL_NAME = 'ListMcpResourcesTool'
const WORKSPACE_BASH_TOOL_NAME = 'workspace_bash'
const WORKSPACE_WRITE_TOOL_NAME = 'workspace_write'
const FORCED_SUPPORT_TOOL_NAMES = new Set([
  AGENT_TOOL_NAME,
  LIST_MCP_RESOURCES_TOOL_NAME,
  WORKSPACE_BASH_TOOL_NAME,
])
const SENSITIVE_CONTEXT_RE =
  /(AGENTS\.md|CLAUDE\.md|system prompt|prompt-context|project instructions|\/Users\/um-yunsang\/\.claude)/iu

function toolAvailable(tools: Tools, toolName: string): boolean {
  return tools.some(tool => tool.name === toolName)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function supportCandidateText(candidate: unknown): string {
  if (typeof candidate === 'string') return candidate
  if (!isRecord(candidate)) return ''
  const message = isRecord(candidate.message) ? candidate.message : candidate
  return textFromContent(message.content)
}

export function selectRecoveredSupportToolChoiceNameForMessages(
  messages: readonly Message[],
): string | undefined {
  return selectRecoveredSupportToolNamesForQuery(latestUserText(messages)).find(
    toolName => FORCED_SUPPORT_TOOL_NAMES.has(toolName),
  )
}

export function shouldWithholdIgnoredSupportToolChoiceText({
  toolChoiceName,
  candidate,
}: {
  readonly toolChoiceName: string
  readonly candidate: unknown
}): boolean {
  const candidateText = supportCandidateText(candidate)
  if (candidateText.trim().length === 0) return false
  if (toolChoiceName === LIST_MCP_RESOURCES_TOOL_NAME) return true
  if (toolChoiceName === AGENT_TOOL_NAME) return true
  if (toolChoiceName === WORKSPACE_BASH_TOOL_NAME) return true
  return SENSITIVE_CONTEXT_RE.test(candidateText)
}

export function scrubIgnoredSupportToolChoiceMessage({
  toolChoiceName,
  candidate,
}: {
  readonly toolChoiceName: string
  readonly candidate: unknown
}): string | undefined {
  return shouldWithholdIgnoredSupportToolChoiceText({ toolChoiceName, candidate })
    ? ''
    : undefined
}

export function shouldScrubObeyedSupportToolChoicePrelude({
  candidate,
}: {
  readonly candidate: unknown
}): boolean {
  const candidateText = supportCandidateText(candidate)
  if (candidateText.trim().length === 0) return false
  return SENSITIVE_CONTEXT_RE.test(candidateText)
}

export function buildIgnoredSupportToolChoiceBlockedText(
  toolChoiceName: string,
  toolChoiceAvailable = true,
): string {
  if (toolChoiceName === WORKSPACE_BASH_TOOL_NAME) {
    const reason = toolChoiceAvailable
      ? 'provider ignored forced workspace_bash tool_choice.'
      : 'workspace_bash 도구가 현재 TUI 도구 풀에 없어 셸 권한 경계를 실행할 수 없습니다.'
    return [
      '셸 실행 차단: workspace_bash 호출을 강제했지만 모델 응답에 셸 도구 경계가 포함되지 않았습니다.',
      `이유: ${reason}`,
      'git 상태 확인이나 삭제 명령은 텍스트 안내로 대체하지 않습니다.',
    ].join(' ')
  }
  if (toolChoiceName === WORKSPACE_WRITE_TOOL_NAME) {
    const reason = toolChoiceAvailable
      ? 'provider ignored forced workspace_write tool_choice.'
      : 'workspace_write 도구가 현재 TUI 도구 풀에 없어 파일 쓰기 권한 경계를 실행할 수 없습니다.'
    return [
      '작업공간 쓰기 차단: workspace_write 호출을 강제했지만 모델 응답에 파일 쓰기 도구 경계가 포함되지 않았습니다.',
      `이유: ${reason}`,
      '파일 변경은 텍스트 안내로 대체하지 않습니다.',
    ].join(' ')
  }
  if (toolChoiceName === LIST_MCP_RESOURCES_TOOL_NAME) {
    const reason = toolChoiceAvailable
      ? 'provider ignored forced ListMcpResourcesTool tool_choice.'
      : 'ListMcpResourcesTool 도구가 현재 TUI 도구 풀에 없어 MCP 리소스 목록을 실행할 수 없습니다.'
    return [
      'MCP 리소스 조회 차단: ListMcpResourcesTool 호출을 강제했지만 모델 응답에 MCP 도구 경계가 포함되지 않았습니다.',
      `이유: ${reason}`,
      '민감한 프로젝트 지침이나 system prompt 내용은 표시하지 않습니다.',
    ].join(' ')
  }
  const reason = toolChoiceAvailable
    ? 'provider ignored forced Agent tool_choice.'
    : 'Agent 도구가 기본 TUI 도구 풀에 없어 provider/query-loop support choice를 실행할 수 없습니다.'
  return [
    '에이전트 위임 차단: Agent 도구 호출을 강제했지만 모델 응답에 Agent/Task 도구 경계가 포함되지 않았습니다.',
    `이유: ${reason}`,
    '진행/취소 상태를 표시할 수 없어 차단했습니다.',
    '구체적인 조사 주제를 주시면 Agent 진행/취소 경계가 보이는 상태로 다시 시도하겠습니다.',
  ].join(' ')
}

export function shouldSuppressUmmayaToolCallsForAnswerSynthesis({
  messages,
  tools,
}: {
  readonly messages: readonly Message[]
  readonly tools: Tools
}): boolean {
  if (shouldSuppressDocumentToolCallsForAnswerSynthesis({ messages })) {
    return true
  }
  const recovered = selectRecoveredSupportToolNamesForQuery(latestUserText(messages))
  return recovered.some(toolName => toolAvailable(tools, toolName)) &&
    !recovered.some(toolName => toolUseNames(messages).has(toolName))
}

export function selectUmmayaToolChoiceOverride(_params: {
  readonly messages: readonly Message[]
  readonly tools: Tools
}): BetaToolChoiceTool | undefined {
  return undefined
}
