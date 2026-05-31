import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import { isNonSyntheticUserMessageText } from './citizenUserText.js'

const NMC_EMERGENCY_TOOL_NAME = 'nmc_emergency_search'
const NMC_AED_TOOL_NAME = 'nmc_aed_site_locate'
const HIRA_TOOL_NAME_RE = /^hira_/u
const AED_RE = /(aed|자동심장|심장충격|제세동)/iu
const ER_RE = /(응급실|응급의료기관|응급의료센터|emergency\s*room|\ber\b)/iu
const MEDICAL_COLLAPSE_RE =
  /(사람이\s*쓰러|쓰러졌|쓰러짐|쓰러져|의식[을이가은는\s]*(없|잃|불명)|무의식|심정지|심폐소생|cpr|호흡\s*(없|곤란)|숨\s*(안|못)|collapse|collapsed|unconscious|cardiac\s*arrest|not\s*breathing)/iu
const NON_MEDICAL_EMERGENCY_RE =
  /(비상벨|안심벨|emergency\s*(call\s*)?box|call\s*box)/iu
const NMC_AED_FOLLOWUP_PROMPT =
  'Required follow-up for this tool chain: the citizen described a collapse, unconsciousness, cardiac-arrest, or AED-relevant medical emergency, and nmc_emergency_search has already returned a successful ER result. Before any final answer, call nmc_aed_site_locate with schema-valid fields using the latest region or location context from this turn. If AED returns no data or an upstream error, report that explicitly with 119 guidance. Do not write final prose until nmc_aed_site_locate has been attempted.'
const NMC_AED_COMPLETION_PROMPT =
  'Emergency evidence chain complete: nmc_emergency_search and nmc_aed_site_locate have both been attempted for this collapse/unconsciousness request. Do not emit <tool_call> text, JSON tool-call text, or request another medical search. Write the final Korean emergency guidance now using the actual ER and AED tool results already in this conversation. Put 119 first, then nearest ER, then nearby AED locations or AED upstream/no-data status. Copy AED org, buildAddress, buildPlace, clerkTel, operating-time fields, and distance_km exactly when present; do not rename or summarize building places into new labels. Do not invent distances, walking times, building labels, station-inside labels, operating hours, or phone numbers that are absent from the tool results; omit unavailable details instead.'

type ToolUseRecord = {
  id: string
  name: string
}

export function textFromContent(content: unknown): string {
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

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : undefined
}

function messageRecord(message: unknown): Record<string, unknown> | undefined {
  const record = asRecord(message)
  return asRecord(record?.message)
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

function latestRoleText(context: ToolUseContext, role: 'assistant' | 'user'): string {
  const messages = Array.isArray(context.messages) ? context.messages : []
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== role) continue
    const text = textFromContent(messageContent(message))
    if (role === 'user' && !isNonSyntheticUserMessageText(message, text)) continue
    if (text.trim()) return text
  }
  return ''
}

function latestUserTurnStartIndex(messages: readonly unknown[]): number {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== 'user') continue
    const text = textFromContent(messageContent(message))
    if (isNonSyntheticUserMessageText(message, text)) return idx
  }
  return -1
}

function latestUserTurnMessages(messages: readonly unknown[]): readonly unknown[] {
  const startIdx = latestUserTurnStartIndex(messages)
  return startIdx === -1 ? [] : messages.slice(startIdx)
}

function latestUserTextFromMessages(messages: readonly unknown[]): string {
  const startIdx = latestUserTurnStartIndex(messages)
  if (startIdx === -1) return ''
  return textFromContent(messageContent(messages[startIdx]))
}

function isMedicalCollapseQuery(text: string): boolean {
  if (!text.trim()) return false
  if (AED_RE.test(text) || MEDICAL_COLLAPSE_RE.test(text)) return true
  return false
}

function isOnlyNonMedicalEmergencyQuery(text: string): boolean {
  return NON_MEDICAL_EMERGENCY_RE.test(text) && !isMedicalCollapseQuery(text)
}

function toolUsesFromMessages(messages: readonly unknown[]): ToolUseRecord[] {
  const toolUses: ToolUseRecord[] = []
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_use') continue
      if (typeof record.id !== 'string' || typeof record.name !== 'string') continue
      const input = asRecord(record.input)
      const nestedToolName =
        typeof input?.tool_id === 'string' ? input.tool_id : undefined
      toolUses.push({ id: record.id, name: nestedToolName ?? record.name })
    }
  }
  return toolUses
}

function parseJsonObject(value: string): Record<string, unknown> | undefined {
  try {
    return asRecord(JSON.parse(value))
  } catch {
    return undefined
  }
}

function isSuccessfulToolResult(block: Record<string, unknown>): boolean {
  if (block.is_error === true) return false
  if (typeof block.content !== 'string') return true

  const parsed = parseJsonObject(block.content)
  if (!parsed) return true
  if (parsed.ok === false) return false
  if (parsed.error || parsed.error_code || parsed.errorCode) return false

  const result = asRecord(parsed.result)
  if (result?.kind === 'error') return false
  return true
}

function hasSuccessfulToolResultFor(
  messages: readonly unknown[],
  toolName: string,
): boolean {
  const idToName = new Map(
    toolUsesFromMessages(messages).map(toolUse => [toolUse.id, toolUse.name]),
  )
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_result') continue
      if (typeof record.tool_use_id !== 'string') continue
      if (idToName.get(record.tool_use_id) !== toolName) continue
      if (isSuccessfulToolResult(record)) return true
    }
  }
  return false
}

function hasToolUse(messages: readonly unknown[], toolName: string): boolean {
  return toolUsesFromMessages(messages).some(toolUse => toolUse.name === toolName)
}

export function buildNmcAedFollowupPromptIfNeeded({
  messages,
  availableToolNames,
}: {
  messages: readonly unknown[]
  availableToolNames: Iterable<string>
}): string | undefined {
  const available = new Set(availableToolNames)
  if (!available.has(NMC_AED_TOOL_NAME)) return undefined

  const userText = latestUserTextFromMessages(messages)
  const turnMessages = latestUserTurnMessages(messages)
  if (isOnlyNonMedicalEmergencyQuery(userText)) return undefined
  if (!isMedicalCollapseQuery(userText)) return undefined
  if (hasToolUse(turnMessages, NMC_AED_TOOL_NAME)) return undefined
  if (!hasSuccessfulToolResultFor(turnMessages, NMC_EMERGENCY_TOOL_NAME)) {
    return undefined
  }
  return NMC_AED_FOLLOWUP_PROMPT
}

export function buildNmcAedCompletionPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = latestUserTextFromMessages(messages)
  const turnMessages = latestUserTurnMessages(messages)
  if (isOnlyNonMedicalEmergencyQuery(userText)) return undefined
  if (!isMedicalCollapseQuery(userText)) return undefined
  if (!hasToolUse(turnMessages, NMC_AED_TOOL_NAME)) return undefined
  if (!hasToolUse(turnMessages, NMC_EMERGENCY_TOOL_NAME)) return undefined
  return NMC_AED_COMPLETION_PROMPT
}

export function validateNmcAedToolChoice(
  toolId: string,
  context: ToolUseContext,
): ValidationResult | undefined {
  if (HIRA_TOOL_NAME_RE.test(toolId)) {
    const userText = latestRoleText(context, 'user')
    if (!isOnlyNonMedicalEmergencyQuery(userText) && isMedicalCollapseQuery(userText)) {
      return {
        result: false,
        message:
          'NMC emergency tool-choice mismatch: a collapse, unconsciousness, cardiac-arrest, or AED-relevant emergency must use official emergency-care evidence, not the general HIRA hospital/clinic search. ' +
          `Call ${NMC_EMERGENCY_TOOL_NAME} for nearest emergency-room/ER institution data and then ${NMC_AED_TOOL_NAME} for AED locations. ` +
          'If either NMC adapter returns no data or an upstream error, report that directly with 119 guidance.',
        errorCode: 1,
      }
    }
  }
  if (toolId !== NMC_EMERGENCY_TOOL_NAME) return undefined
  const assistantText = latestRoleText(context, 'assistant')
  const userText = latestRoleText(context, 'user')
  const assistantIsAskingForAed = AED_RE.test(assistantText) && !ER_RE.test(assistantText)
  const userAskedOnlyForAed = AED_RE.test(userText) && !ER_RE.test(userText)
  if (!assistantIsAskingForAed && !userAskedOnlyForAed) return undefined
  return {
    result: false,
    message:
      'NMC tool-choice mismatch: nmc_emergency_search answers emergency-room/ER institution data, not AED locations. ' +
      `Call ${NMC_AED_TOOL_NAME} for AED/자동심장충격기/자동제세동기 requests. ` +
      'If the AED API returns no data or an upstream error, report that result directly instead of substituting ER data.',
    errorCode: 1,
  }
}
