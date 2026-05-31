import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import {
  listAdapters,
  resolveAdapter,
} from '../../services/api/adapterManifest.js'
import { isNonSyntheticUserMessageText } from './citizenUserText.js'
import { textFromContent } from './nmcAedGuard.js'

const PROTECTED_QUERY_RE =
  /(본인확인|인증|간편인증|모바일\s*(?:신분증|id)|mobile\s*id|마이데이터|mydata|증명원|소득금액증명|소득금액증명원|주민등록등본|민원|발급)/iu
const VERIFY_ALIAS_RE =
  /^(?:check|mobile_id|modid|simple_auth_module|ganpyeon_injeung|gongdong_injeungseo|geumyung_injeungseo|mydata|any_id_sso)$/iu
const PROTECTED_CHECK_TOOL_NAMES = new Set([
  'mock_verify_module_simple_auth',
  'mock_verify_ganpyeon_injeung',
  'mock_verify_mobile_id',
  'mock_verify_mydata',
  'mock_verify_digital_onepass',
  'mock_verify_gongdong_injeungseo',
  'mock_verify_geumyung_injeungseo',
  'mock_verify_module_modid',
  'mock_verify_module_kec',
  'mock_verify_module_geumyung',
  'mock_verify_module_any_id_sso',
])
const PROTECTED_CHECK_COMPLETION_PROMPT =
  'Protected-domain evidence chain complete: a registered check adapter has already been attempted for this certificate, authentication, identity, or protected-service request. Do not emit <tool_call> text, JSON tool-call text, or request another identity tool. Write the final Korean answer now using the actual check result already in this conversation. If the result is permission_denied, unavailable, or mock-only, state that UMMAYA cannot complete the protected action in-session, then give official handoff options without claiming issuance succeeded.'
const PROTECTED_CHECK_REPAIR_PROMPT =
  'Protected-domain final-answer repair: the previous assistant message was invalid because it printed JSON tool-call text after a registered check adapter result. Do not call or print any tool. Write one Korean prose answer only. Use the existing check result already in this conversation. If the result is permission_denied, unavailable, or mock-only, state that UMMAYA cannot complete the protected action in-session, then give official handoff options such as Government24, Hometax, mobile ID, or 간편인증 without claiming issuance succeeded.'
const PROTECTED_TOOL_CALL_TEXT_RE =
  /<tool_call>|"name"\s*:\s*"[^"]*(?:check|verify|auth|mobile|simple|ganpyeon|mydata)[^"]*"|"arguments"\s*:\s*\{/iu

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

function hasProtectedCheckToolUse(messages: readonly unknown[]): boolean {
  for (const message of messages) {
    const content = messageContent(message)
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const record = asRecord(block)
      if (record?.type !== 'tool_use') continue
      if (
        typeof record.name === 'string' &&
        PROTECTED_CHECK_TOOL_NAMES.has(record.name)
      ) {
        return true
      }
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
      'Protected-domain final-answer repair',
    ),
  )
}

function checkAdapterIds(): string[] {
  return listAdapters()
    .filter(entry => entry.primitive === 'check')
    .map(entry => entry.tool_id)
}

function selectSuggestions(toolId: string, userText: string): string[] {
  const available = checkAdapterIds()
  const wantsMobile = /mobile\s*id|모바일\s*(?:신분증|id)|mobile_id/iu.test(
    `${toolId} ${userText}`,
  )
  const wantsSimple =
    /simple_auth|간편인증|ganpyeon|소득금액증명|증명원|민원|발급/iu.test(
      `${toolId} ${userText}`,
    )
  const wantsMydata = /mydata|마이데이터/iu.test(`${toolId} ${userText}`)
  const preferred = [
    wantsMobile ? 'mock_verify_mobile_id' : undefined,
    wantsSimple ? 'mock_verify_module_simple_auth' : undefined,
    wantsSimple ? 'mock_verify_ganpyeon_injeung' : undefined,
    wantsMydata ? 'mock_verify_mydata' : undefined,
  ].filter((id): id is string => typeof id === 'string' && available.includes(id))
  const merged = [...preferred, ...available]
  return [...new Set(merged)].slice(0, 3)
}

export function validateProtectedCheckToolChoice(
  toolId: string,
  context: ToolUseContext,
): ValidationResult | undefined {
  const userText = latestUserText(context)
  const adapter = resolveAdapter(toolId)
  if (adapter?.primitive === 'check') {
    return {
      result: false,
      message:
        `Protected-domain tool-choice mismatch: ${toolId} is a check adapter but was called through find. ` +
        `Call check({tool_id:${JSON.stringify(toolId)}, params:{...}}) instead. ` +
        'Do not call check adapters through find.',
      errorCode: 1,
    }
  }
  if (!PROTECTED_QUERY_RE.test(userText) && !VERIFY_ALIAS_RE.test(toolId)) {
    return undefined
  }
  if (!VERIFY_ALIAS_RE.test(toolId)) return undefined
  const suggestions = selectSuggestions(toolId, userText)
  if (suggestions.length === 0) return undefined
  return {
    result: false,
    message:
      `Protected-domain tool-choice mismatch: ${toolId} is not a registered find adapter. ` +
      `Use the check primitive with a registered check adapter such as ${suggestions.join(', ')}. ` +
      'Do not call identity, authentication, consent, or certificate adapters through find.',
    errorCode: 1,
  }
}

export function buildProtectedCheckCompletionPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = userTextFromMessages(messages)
  if (!PROTECTED_QUERY_RE.test(userText)) return undefined
  if (!hasProtectedCheckToolUse(messages)) return undefined
  return PROTECTED_CHECK_COMPLETION_PROMPT
}

export function buildProtectedCheckFinalAnswerRepairPromptIfNeeded({
  messages,
}: {
  messages: readonly unknown[]
}): string | undefined {
  const userText = userTextFromMessages(messages)
  if (!PROTECTED_QUERY_RE.test(userText)) return undefined
  if (!hasProtectedCheckToolUse(messages)) return undefined
  if (hasRepairPrompt(messages)) return undefined
  const assistantText = latestAssistantText(messages)
  if (!PROTECTED_TOOL_CALL_TEXT_RE.test(assistantText)) return undefined
  return PROTECTED_CHECK_REPAIR_PROMPT
}

export function shouldWithholdProtectedCheckToolCallText({
  messages,
  candidate,
}: {
  messages: readonly unknown[]
  candidate: unknown
}): boolean {
  if (hasRepairPrompt(messages)) return false
  return (
    buildProtectedCheckFinalAnswerRepairPromptIfNeeded({
      messages: [...messages, candidate],
    }) !== undefined
  )
}
