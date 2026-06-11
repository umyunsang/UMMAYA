// SPDX-License-Identifier: Apache-2.0

import type { ToolUseContext } from '../../Tool.js'
import { lastLocalDocumentPath } from './documentDestinationPath.js'
import { normalizeDocumentMutationPayloadsForDispatch } from './documentPatchNormalization.js'

const WRITE_INTENT_RE =
  /(작성|수정|편집|채우|채워|입력|변경|저장|보정|서식|글꼴|글자색|배경색|정렬|굵게|write|edit|fill|apply|save|style|format|bold)/iu
const READ_ONLY_INTENT_RE =
  /(읽기\s*전용|수정\s*없이|변경\s*없이|저장\s*없이|열람만|확인만|추출|파악|쓰지\s*마|작성하지\s*마|반영하지\s*마|저장하지\s*마|inspect|extract|read\s*only)/iu
const DEFERRED_WRITE_INTENT_RE =
  /((아직|먼저|초안).{0,40}(쓰지\s*마|작성하지\s*마|저장하지\s*마|반영하지\s*마))|((쓰지\s*마|작성하지\s*마|저장하지\s*마|반영하지\s*마).{0,40}(아직|먼저|초안))/iu
const APPROVED_DERIVATIVE_SAVE_RE =
  /((승인|approved).{0,100}(저장|복사본|derivative|\/[^\s]+))|((저장|복사본|derivative|\/[^\s]+).{0,100}(승인|approved))/iu
const QUESTION_FIRST_AUTHORING_RE =
  /(근거|질문|먼저\s*물|먼저\s*질문|초안|승인|evidence|question|draft|approval)/iu
const STRUCTURE_INSPECTION_RE =
  /(구조|빈칸|문항|양식|필드|항목).*(확인|파악|검토)|(?:확인|파악|검토).*(구조|빈칸|문항|양식|필드|항목)/iu
const INTERNAL_DISPATCH_KEYS = new Set(['__ummaya_display_operation'])
const READ_ONLY_OPERATIONS = new Set(['inspect', 'extract', 'validate'])
const READ_ONLY_MUTATION_KEYS = new Set([
  'destination_path',
  'destination_display_name',
  'patches',
  'styles',
  'approved_draft_id',
  'approved_draft_sha256',
])

export type DocumentPrimitiveDispatchInput = {
  readonly document?: unknown
  readonly operation?: string
  readonly instruction?: string
  readonly destination_path?: string
  readonly patches?: readonly unknown[]
  readonly styles?: readonly unknown[]
  readonly [key: string]: unknown
}

export function normalizeDocumentPrimitiveInputForDispatch(
  input: DocumentPrimitiveDispatchInput,
  userText: string | undefined,
): Record<string, unknown> {
  const operation = operationOf(input, userText)
  const text = `${input.instruction ?? ''}\n${userText ?? ''}`
  const destinationPath =
    typeof input.destination_path === 'string' ||
    READ_ONLY_OPERATIONS.has(operation) ||
    !hasApprovedDerivativeSaveIntent(input, text)
      ? undefined
      : lastLocalDocumentPath(text)
  const args = normalizeDocumentLocatorForDispatch(
    normalizeDocumentMutationPayloadsForDispatch(
      stripDispatchOnlyFields({
        ...input,
        operation,
        ...(destinationPath === undefined ? {} : { destination_path: destinationPath }),
      }),
      userText,
    ),
  )
  if (userText === undefined || hasPatchOrStylePayload(input)) {
    return args
  }

  const instruction = typeof input.instruction === 'string'
    ? input.instruction.trim()
    : ''
  if (instruction.includes(userText)) {
    return args
  }
  return {
    ...args,
    instruction: instruction
      ? `${instruction}\n\nOriginal user request:\n${userText}`
      : userText,
  }
}

export function operationOf(
  input: DocumentPrimitiveDispatchInput,
  userText?: string,
): string {
  const operation = typeof input.operation === 'string' ? input.operation : 'fill'
  if (hasReadOnlyIntentFromText(input, userText)) {
    return operation === 'extract' ? 'extract' : 'inspect'
  }
  if (shouldPreserveQuestionFirstRead(input, userText, operation)) {
    return operation
  }
  const displayOperation =
    typeof input.__ummaya_display_operation === 'string'
      ? input.__ummaya_display_operation
      : undefined
  if (
    displayOperation === 'fill' ||
    displayOperation === 'style' ||
    displayOperation === 'save'
  ) {
    return displayOperation
  }
  if (
    (operation === 'inspect' || operation === 'extract') &&
    hasWriteIntentFromText(input, userText)
  ) {
    return 'fill'
  }
  return operation
}

export function latestUserTextFromContext(context: ToolUseContext): string | undefined {
  const messages = contextRecord(context).messages
  if (!Array.isArray(messages)) return undefined
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = recordFrom(messages[index])
    if (message === null) continue
    const sdkMessage = recordFrom(message.message)
    if (!isUserMessageRecord(message, sdkMessage)) continue
    const content = sdkMessage?.content ?? message.content
    const text = textFromMessageContent(content)
    if (text !== undefined) return text
  }
  return undefined
}

function normalizeDocumentLocatorForDispatch(
  args: Record<string, unknown>,
): Record<string, unknown> {
  const document = recordFrom(args.document)
  if (document === null) {
    return args
  }
  if (
    nonEmptyString(document.artifact_id) === undefined ||
    nonEmptyString(document.path) === undefined
  ) {
    return args
  }
  const normalizedDocument: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(document)) {
    if (key !== 'path') {
      normalizedDocument[key] = value
    }
  }
  return {
    ...args,
    document: normalizedDocument,
  }
}

function stripDispatchOnlyFields(args: Record<string, unknown>): Record<string, unknown> {
  const operation = typeof args.operation === 'string' ? args.operation : 'fill'
  const readOnlyOperation = READ_ONLY_OPERATIONS.has(operation)
  const cleaned: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(args)) {
    if (INTERNAL_DISPATCH_KEYS.has(key)) continue
    if (readOnlyOperation && READ_ONLY_MUTATION_KEYS.has(key)) continue
    cleaned[key] = value
  }
  return cleaned
}

function shouldPreserveQuestionFirstRead(
  input: DocumentPrimitiveDispatchInput,
  userText: string | undefined,
  operation: string,
): boolean {
  if (operation !== 'inspect' && operation !== 'extract') {
    return false
  }
  if (hasPatchOrStylePayload(input)) {
    return false
  }
  const text = `${input.instruction ?? ''}\n${userText ?? ''}`
  if (hasApprovedDerivativeSaveIntent(input, text)) {
    return false
  }
  if (operation === 'inspect' && STRUCTURE_INSPECTION_RE.test(input.instruction ?? '')) {
    return true
  }
  return QUESTION_FIRST_AUTHORING_RE.test(text) && WRITE_INTENT_RE.test(text)
}

function hasWriteIntentFromText(
  input: DocumentPrimitiveDispatchInput,
  userText: string | undefined,
): boolean {
  if (typeof input.destination_path === 'string') return true
  if (hasPatchOrStylePayload(input)) return true
  if (userText !== undefined) {
    return !READ_ONLY_INTENT_RE.test(userText) && WRITE_INTENT_RE.test(userText)
  }
  if (READ_ONLY_INTENT_RE.test(input.instruction ?? '')) return false
  return WRITE_INTENT_RE.test(input.instruction ?? '')
}

function hasReadOnlyIntentFromText(
  input: DocumentPrimitiveDispatchInput,
  userText: string | undefined,
): boolean {
  const text = userText ?? input.instruction ?? ''
  if (!READ_ONLY_INTENT_RE.test(text)) {
    return false
  }
  if (hasApprovedDerivativeSaveIntent(input, text)) {
    return false
  }
  return true
}

function hasPatchOrStylePayload(input: DocumentPrimitiveDispatchInput): boolean {
  return (Array.isArray(input.patches) && input.patches.length > 0) ||
    (Array.isArray(input.styles) && input.styles.length > 0)
}

function hasApprovedDerivativeSaveIntent(
  input: DocumentPrimitiveDispatchInput,
  text: string,
): boolean {
  if (DEFERRED_WRITE_INTENT_RE.test(text)) {
    return false
  }
  if (APPROVED_DERIVATIVE_SAVE_RE.test(text)) {
    return true
  }
  return typeof input.destination_path === 'string' &&
    /(승인|approved|검토용\s*복사본|원본은\s*건드리지\s*말)/iu.test(text) &&
    /(저장|save|\/[^\s]+)/iu.test(text)
}

function textFromMessageContent(content: unknown): string | undefined {
  if (typeof content === 'string' && content.trim() !== '') {
    return content
  }
  if (!Array.isArray(content)) {
    return undefined
  }
  const text = content
    .map(block => {
      const item = recordFrom(block)
      return item?.type === 'text' && typeof item.text === 'string'
        ? item.text
        : ''
    })
    .filter(Boolean)
    .join('\n')
    .trim()
  return text === '' ? undefined : text
}

function isUserMessageRecord(
  message: Record<string, unknown>,
  sdkMessage: Record<string, unknown> | null,
): boolean {
  return message.type === 'user' || message.role === 'user' || sdkMessage?.role === 'user'
}

function contextRecord(context: ToolUseContext): Record<string, unknown> {
  return context
}

function recordFrom(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? Object.fromEntries(Object.entries(value))
    : null
}

function nonEmptyString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() !== '' ? value : undefined
}
