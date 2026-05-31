import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import { isNonSyntheticUserMessageText } from './citizenUserText.js'

export const KMA_ANALYSIS_CHART_TOOL_NAME = 'kma_apihub_url_analysis_weather_chart_image'
const KMA_ANALYSIS_POINT_TOOL_NAMES = new Set([
  'kma_apihub_url_high_resolution_grid_point',
  'kma_apihub_url_aws_objective_analysis_grid',
])

const KMA_ANALYSIS_MAP_RE =
  /(일기도|분석일기도|지도\s*자료|비구름|바람\s*흐름|synoptic|weather\s*chart)/iu
const KMA_ANALYSIS_COMPLETION_PROMPT =
  'KMA analyzed weather-chart evidence chain complete: kma_apihub_url_analysis_weather_chart_image has already been attempted for this 일기도/지도/비구름/바람 흐름 request. The generic tool error hint is not permission to call or print a different tool in this turn. Do not emit <tool_call> text, JSON tool-call text, JSON with name/arguments, or point-grid/current-weather substitute requests. Write the final Korean answer now from the actual chart-tool result only. If the result is approval_state=approved with content_type=image/png or raw_format=image, say the official KMA chart image lookup succeeded, but do not infer rain-cloud or wind-flow details unless the tool result contains decoded chart semantics. If the result is APIHub approval-required, 403, no-data, or another upstream failure, report that failure directly and cite the official KMA channel as the handoff path.'
const KMA_ANALYSIS_REPAIR_PROMPT =
  'KMA analyzed weather-chart final-answer repair: the previous assistant message was invalid because it printed tool-call text, asked for location/tool follow-up, or inferred chart semantics after the chart tool result. Do not call or print any tool. Do not ask for coordinates, a region, or another lookup. Write one Korean prose answer only. Use the existing kma_apihub_url_analysis_weather_chart_image result: if it says approval_state=approved and content_type=image/png or raw_format=image, state that the official KMA analyzed chart image was fetched successfully, and state that this text-only adapter result does not decode the chart pixels into rain-cloud or wind-flow semantics. Do not invent meteorological interpretation from the image.'
const KMA_ANALYSIS_MISSING_TOOL_PROMPT =
  'Required KMA analyzed weather-chart lookup: the citizen asked for 전국 기상도, 위성 자료, 비구름 흐름, 바람 흐름, or analyzed map evidence. This is not a place-specific weather question, so do not ask for a location or coordinates. Before final prose, call kma_apihub_url_analysis_weather_chart_image directly if it is available. If only the legacy find primitive is available, call find with tool_id:"kma_apihub_url_analysis_weather_chart_image" and schema-valid chart params, including anal_time as the latest completed UTC YYYYMMDDHHMM slot. If APIHub returns approval-required, no-data, or another upstream failure, report that failure directly.'
const KMA_ANALYSIS_TOOL_CALL_TEXT_RE =
  /<tool_call>|"name"\s*:\s*"kma_apihub_url_analysis_weather_chart_image"|"arguments"\s*:\s*\{/iu
const KMA_ANALYSIS_INVALID_FOLLOWUP_TEXT_RE =
  /(현재\s*위치|위치\s*정보|정확한\s*좌표|지역명|알려주시면|어떤\s*방식|카카오|도구를\s*사용|확인하실\s*수\s*있습니다)/iu

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : undefined
}

function messageRecord(message: unknown): Record<string, unknown> | undefined {
  return asRecord(asRecord(message)?.message)
}

function messageRole(message: unknown): string | undefined {
  const record = asRecord(message)
  const inner = messageRecord(message)
  if (typeof inner?.role === 'string') return inner.role
  if (typeof record?.role === 'string') return record.role
  return typeof record?.type === 'string' ? record.type : undefined
}

function messageContent(message: unknown): unknown {
  return messageRecord(message)?.content ?? asRecord(message)?.content
}

function textFromContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map(block => {
      if (typeof block === 'string') return block
      if (typeof block !== 'object' || block === null) return ''
      const record = block as Record<string, unknown>
      return typeof record.text === 'string' ? record.text : ''
    })
    .filter(Boolean)
    .join('\n')
}

function latestUserText(context: ToolUseContext): string {
  const messages = Array.isArray(context.messages) ? context.messages : []
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== 'user') continue
    const text = textFromContent(messageContent(message))
    if (isNonSyntheticUserMessageText(message, text)) return text
  }
  return ''
}

function userTextFromMessages(messages: readonly unknown[]): string {
  return messages
    .filter(message => messageRole(message) === 'user')
    .map(message => ({ message, text: textFromContent(messageContent(message)) }))
    .filter(({ message, text }) => isNonSyntheticUserMessageText(message, text))
    .map(({ text }) => text)
    .join('\n')
}

function hasToolUse(messages: readonly unknown[], toolName: string): boolean {
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_use') continue
      const input = asRecord(record.input)
      const nestedToolName =
        typeof input?.tool_id === 'string' ? input.tool_id : undefined
      const name = nestedToolName ?? record.name
      if (name === toolName) return true
    }
  }
  return false
}

function latestAssistantText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== 'assistant') continue
    const text = textFromContent(messageContent(message))
    if (text.trim()) return text
  }
  return ''
}

function hasRepairPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message =>
    textFromContent(messageContent(message)).includes(
      'KMA analyzed weather-chart final-answer repair',
    ),
  )
}

function hasMissingToolPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message =>
    textFromContent(messageContent(message)).includes(
      'Required KMA analyzed weather-chart lookup',
    ),
  )
}

export function isKmaAnalysisMapText(text: string): boolean {
  return KMA_ANALYSIS_MAP_RE.test(text)
}

export function validateKmaAnalysisToolChoice(
  toolId: string,
  context: ToolUseContext,
): ValidationResult | undefined {
  if (!KMA_ANALYSIS_POINT_TOOL_NAMES.has(toolId)) return undefined
  const userText = latestUserText(context)
  if (!isKmaAnalysisMapText(userText)) return undefined
  return {
    result: false,
    message:
      'KMA analysis tool-choice mismatch: the latest citizen request asks for analyzed weather chart/map evidence. Call ' +
      `${KMA_ANALYSIS_CHART_TOOL_NAME} for 일기도/지도/비구름/바람 흐름 requests. ` +
      'If APIHub returns approval-required or another upstream error, report that failure directly and do not substitute point-grid data.',
    errorCode: 1,
  }
}

export function buildKmaAnalysisCompletionPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  if (!isKmaAnalysisMapText(userTextFromMessages(messages))) return undefined
  if (!hasToolUse(messages, KMA_ANALYSIS_CHART_TOOL_NAME)) return undefined
  return KMA_ANALYSIS_COMPLETION_PROMPT
}

export function buildKmaAnalysisFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  if (!isKmaAnalysisMapText(userTextFromMessages(messages))) return undefined
  if (!hasToolUse(messages, KMA_ANALYSIS_CHART_TOOL_NAME)) return undefined
  if (hasRepairPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (
    !KMA_ANALYSIS_TOOL_CALL_TEXT_RE.test(assistantText) &&
    !KMA_ANALYSIS_INVALID_FOLLOWUP_TEXT_RE.test(assistantText)
  ) {
    return undefined
  }
  return KMA_ANALYSIS_REPAIR_PROMPT
}

export function buildKmaAnalysisMissingToolPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  if (!isKmaAnalysisMapText(userTextFromMessages(messages))) return undefined
  if (hasToolUse(messages, KMA_ANALYSIS_CHART_TOOL_NAME)) return undefined
  if (hasMissingToolPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (!assistantText.trim()) return undefined
  return KMA_ANALYSIS_MISSING_TOOL_PROMPT
}

export function shouldWithholdKmaAnalysisToolCallText({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasRepairPrompt(messages)) return false
  return (
    buildKmaAnalysisFinalAnswerRepairPromptIfNeeded({
      messages: [...messages, candidate],
    }) !== undefined
  )
}
