import { createHash } from 'node:crypto'
import type { Tools } from '../../../Tool.js'
import type { Message } from '../../../types/message.js'
import type {
  ForcedUmmayaToolUse,
  UmmayaBackendRepairReceipt,
} from '../toolChoiceRepair.js'
import {
  buildDocumentCompletionPrompt,
  hasTerminalDocumentCompletion,
  mentionsDocumentWork,
} from './documentCompletionPrompt.js'
import {
  DOCUMENT_INTENT_RE,
  DOCUMENT_READ_ONLY_RE,
  DOCUMENT_RENDER_TOOL_NAME,
  DOCUMENT_TOOL_NAME,
  DOCUMENT_WRITE_RE,
  documentExpectedFormatFromPath,
  isExactLocalReadOnlyDocumentPrompt,
  localDocumentPathFromText,
  type DocumentExpectedFormat,
} from './documentCompletionPatterns.js'
import {
  isRecord,
  latestUserMessageIndex,
  latestUserText,
  messageContent,
  textFromContent,
} from './messageAccess.js'

const DOCUMENT_EXPLICIT_PATH_SCAN_RE =
  /(?:^|[\s:'"(])((?:~|\/|[A-Za-z]:\\|\.{1,2}\/)[^\s:'"]+\.(hwpx|hwp|docx|pdf|xlsx|pptx))\b/giu
const DOCUMENT_ARTIFACT_ID_RE =
  /(?:^|[\s"'`(])(?:artifact_id|artifact\s*id|artifact|아티팩트)?\s*((?:source|working|derivative|render|export|viewport)-[A-Za-z0-9][A-Za-z0-9_.-]{0,127})(?=$|[^A-Za-z0-9_.-])/iu
const DOCUMENT_FORMAT_RE = /\b(?:hwpx|hwp|docx|pdf|xlsx|pptx)\b/iu
const DOCUMENT_REVIEW_RE =
  /(diff|compact|변경사항|렌더|미리보기|render|viewport|page)/iu
const DOCUMENT_LOCAL_HINT_RE =
  /(다운로드|downloads?|폴더|파일|양식|서식|활동일지|신청서|등본|증명서)/iu

function toolAvailable(tools: Tools, toolName: string): boolean {
  return tools.some(tool => tool.name === toolName)
}

function documentCandidateText(candidate: unknown): string {
  if (typeof candidate === 'string') return candidate
  if (!isRecord(candidate)) return ''
  const message = isRecord(candidate.message) ? candidate.message : candidate
  return textFromContent(messageContent(message))
}

type DocumentDispatchRepair =
  | {
      readonly kind: 'ready'
      readonly input: Record<string, unknown>
    }
  | {
      readonly kind: 'blocked'
      readonly message: string
    }

type DocumentPathRef = {
  readonly path: string
  readonly expectedFormat: DocumentExpectedFormat
}

export function repairUmmayaDocumentToolInputForDispatch({
  toolName,
  input,
  messages,
}: {
  readonly toolName: string
  readonly input: Record<string, unknown>
  readonly messages: readonly Message[]
}): DocumentDispatchRepair {
  if (toolName !== DOCUMENT_TOOL_NAME) {
    return { kind: 'ready', input }
  }

  const userText = latestUserText(messages)
  const exactReadOnlyInspect = isExactLocalReadOnlyDocumentPrompt(userText)
  if (hasDocumentDispatchContract(input) && !exactReadOnlyInspect) {
    return { kind: 'ready', input }
  }

  if (!exactReadOnlyInspect) {
    return {
      kind: 'blocked',
      message:
        'Document boundary blocked: provider emitted malformed document input, and the latest user request was not an exact local read-only inspect prompt. The document tool was not dispatched.',
    }
  }

  const path = localDocumentPathFromText(userText)
  if (path === undefined) {
    return {
      kind: 'blocked',
      message:
        'Document boundary blocked: provider emitted malformed document input, and no exact local document path could be recovered from the latest user request. Provide an exact existing file path.',
    }
  }

  const expectedFormat = documentExpectedFormatFromPath(path)
  return {
    kind: 'ready',
    input: {
      correlation_id:
        nonEmptyString(input.correlation_id) ??
        `client-repaired-document-${shortHash(`${path}\n${userText}`)}`,
      document: {
        path,
        ...(expectedFormat === undefined ? {} : { expected_format: expectedFormat }),
      },
      operation: 'inspect',
      instruction: documentInstruction(input, userText),
      __ummaya_user_query: userText,
    },
  }
}

function hasDocumentDispatchContract(input: Record<string, unknown>): boolean {
  const document = isRecord(input.document) ? input.document : undefined
  return nonEmptyString(input.correlation_id) !== undefined &&
    document !== undefined &&
    (nonEmptyString(document.path) !== undefined ||
      nonEmptyString(document.artifact_id) !== undefined) &&
    nonEmptyString(input.instruction) !== undefined
}

function documentInstruction(
  input: Record<string, unknown>,
  userText: string,
): string {
  const instruction = nonEmptyString(input.instruction)
  if (instruction === undefined) return userText
  if (instruction.includes(userText)) return instruction
  return `${instruction}\n\nOriginal user request:\n${userText}`
}

function nonEmptyString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0
    ? value
    : undefined
}

function shortHash(text: string): string {
  return createHash('sha256').update(text).digest('hex').slice(0, 8)
}

function hasBackendRepairReceipt(
  receipt: UmmayaBackendRepairReceipt | undefined,
): boolean {
  return receipt !== undefined &&
    (receipt.source === 'backend_route_decision' ||
      receipt.source === 'backend_validation') &&
    receipt.reason.trim() !== '' &&
    receipt.evidenceEvent.startsWith('ummaya.')
}

function isDocumentHarnessQuery(text: string): boolean {
  return localDocumentPathFromText(text) !== undefined ||
    DOCUMENT_ARTIFACT_ID_RE.test(text) ||
    ((DOCUMENT_FORMAT_RE.test(text) || DOCUMENT_ARTIFACT_ID_RE.test(text)) &&
      DOCUMENT_INTENT_RE.test(text)) ||
    (DOCUMENT_INTENT_RE.test(text) &&
      DOCUMENT_WRITE_RE.test(text) &&
      DOCUMENT_LOCAL_HINT_RE.test(text))
}

function hasExplicitDocumentLocator(text: string): boolean {
  return localDocumentPathFromText(text) !== undefined ||
    DOCUMENT_ARTIFACT_ID_RE.test(text)
}

function explicitDocumentPathRefs(userText: string): readonly DocumentPathRef[] {
  return [...userText.matchAll(DOCUMENT_EXPLICIT_PATH_SCAN_RE)].map(match => ({
    path: match[1]!,
    expectedFormat: match[2]!.toLowerCase() as DocumentExpectedFormat,
  }))
}

function stableDocumentCorrelationId(userText: string): string {
  return `client-forced-document-${shortHash(userText)}`
}

function forcedDocumentInputFromExplicitPath(
  userText: string,
): Record<string, unknown> | undefined {
  if (!isDocumentHarnessQuery(userText)) return undefined
  const wantsWrite =
    DOCUMENT_WRITE_RE.test(userText) && !DOCUMENT_READ_ONLY_RE.test(userText)
  const wantsReview = DOCUMENT_REVIEW_RE.test(userText)
  const wantsReadOnly = DOCUMENT_READ_ONLY_RE.test(userText)
  if (!wantsWrite && !wantsReview && !wantsReadOnly) return undefined

  const paths = explicitDocumentPathRefs(userText)
  const source = paths[0]
  if (!source) return undefined

  const input: Record<string, unknown> = {
    correlation_id: stableDocumentCorrelationId(userText),
    document: {
      path: source.path,
      expected_format: source.expectedFormat,
    },
    operation: wantsWrite ? 'fill' : 'inspect',
    instruction: userText,
  }
  const destination = paths.find(candidate => candidate.path !== source.path)
  if (destination !== undefined && wantsWrite) {
    input.destination_path = destination.path
  }
  return input
}

function toolAvailableOrSynced(tools: Tools, toolName: string): boolean {
  return toolAvailable(tools, toolName)
}

function hasExplicitMutationPayload(input: Record<string, unknown>): boolean {
  return Array.isArray(input.patches) ||
    Array.isArray(input.styles) ||
    typeof input.destination_path === 'string'
}

function parseJsonRecord(value: string): Record<string, unknown> | undefined {
  try {
    const parsed: unknown = JSON.parse(value)
    return isRecord(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function documentResultPayload(value: unknown): Record<string, unknown> | undefined {
  if (Array.isArray(value)) {
    for (let index = value.length - 1; index >= 0; index -= 1) {
      const nested = documentResultPayload(value[index])
      if (nested !== undefined) return nested
    }
    return undefined
  }
  if (!isRecord(value)) return undefined
  const toolId = typeof value.tool_id === 'string' ? value.tool_id : undefined
  if (toolId === DOCUMENT_TOOL_NAME || toolId === DOCUMENT_RENDER_TOOL_NAME) {
    return value
  }
  return documentResultPayload(value.result)
}

function isSuccessfulDocumentPayload(
  payload: Record<string, unknown>,
  acceptedToolNames: ReadonlySet<string>,
): boolean {
  const toolId = typeof payload.tool_id === 'string' ? payload.tool_id : undefined
  if (toolId === undefined || !acceptedToolNames.has(toolId)) return false
  const status = typeof payload.status === 'string'
    ? payload.status.toLowerCase()
    : 'ok'
  const okFlag = typeof payload.ok === 'boolean' ? payload.ok : true
  const hasError =
    payload.kind === 'error' ||
    typeof payload.error === 'string' ||
    isRecord(payload.error)
  return okFlag && !hasError &&
    ['ok', 'succeeded', 'completed', 'ready'].includes(status)
}

function hasSuccessfulDocumentResultAfter(
  messages: readonly Message[],
  afterIndex: number,
  acceptedToolNames: ReadonlySet<string>,
): boolean {
  for (let index = Math.max(0, afterIndex + 1); index < messages.length; index += 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (const block of content) {
      if (!isRecord(block) || block.type !== 'tool_result') continue
      if (block.is_error === true || typeof block.content !== 'string') continue
      const payload = documentResultPayload(parseJsonRecord(block.content))
      if (
        payload !== undefined &&
        isSuccessfulDocumentPayload(payload, acceptedToolNames)
      ) {
        return true
      }
    }
  }
  return false
}

export function repairUmmayaExplicitDocumentToolUseFromUserQuery({
  input,
  toolName,
  messages,
  tools,
  backendRepairReceipt,
}: {
  readonly toolName: string
  readonly input: Record<string, unknown>
  readonly messages: readonly Message[]
  readonly tools: Tools
  readonly backendRepairReceipt?: UmmayaBackendRepairReceipt
}): ForcedUmmayaToolUse | undefined {
  if (!hasBackendRepairReceipt(backendRepairReceipt)) return undefined
  if (!toolAvailableOrSynced(tools, DOCUMENT_TOOL_NAME)) return undefined

  const userText = latestUserText(messages)
  if (!hasExplicitDocumentLocator(userText)) return undefined
  const forced = forcedDocumentInputFromExplicitPath(userText)
  if (forced === undefined) return undefined

  if (toolName === DOCUMENT_TOOL_NAME) {
    const forcedOperation = typeof forced.operation === 'string'
      ? forced.operation
      : undefined
    const currentOperation = typeof input.operation === 'string'
      ? input.operation
      : undefined
    if (
      forcedOperation === currentOperation ||
      (forcedOperation !== 'inspect' && hasExplicitMutationPayload(input))
    ) {
      return undefined
    }
  }

  return {
    name: DOCUMENT_TOOL_NAME,
    input: forced,
  }
}

export function backfillUmmayaObservableToolInputFromUserQuery(_params: {
  readonly toolName: string
  readonly input: Record<string, unknown>
  readonly messages: readonly Message[]
}): void {
  if (_params.toolName !== DOCUMENT_TOOL_NAME) return
  const operation = typeof _params.input.operation === 'string'
    ? _params.input.operation
    : undefined
  if (operation !== 'inspect' && operation !== 'extract') return

  const userText = latestUserText(_params.messages)
  if (!isDocumentHarnessQuery(userText)) return
  if (!DOCUMENT_WRITE_RE.test(userText) || DOCUMENT_READ_ONLY_RE.test(userText)) {
    return
  }
  if (!hasExplicitDocumentLocator(userText)) return

  _params.input.__ummaya_display_operation = 'fill'
}

export function selectUmmayaClientForcedToolUse({
  messages,
  tools,
  backendRepairReceipt,
}: {
  readonly messages: readonly Message[]
  readonly tools: Tools
  readonly backendRepairReceipt?: UmmayaBackendRepairReceipt
}): ForcedUmmayaToolUse | undefined {
  if (!hasBackendRepairReceipt(backendRepairReceipt)) return undefined
  if (!toolAvailableOrSynced(tools, DOCUMENT_TOOL_NAME)) return undefined
  const input = forcedDocumentInputFromExplicitPath(latestUserText(messages))
  if (input === undefined) return undefined
  return {
    name: DOCUMENT_TOOL_NAME,
    input,
  }
}

export function selectRecoveredDocumentToolChoiceNameForMessages({
  messages,
  tools,
}: {
  readonly messages: readonly Message[]
  readonly tools: Tools
}): string | undefined {
  if (!isExactLocalReadOnlyDocumentPrompt(latestUserText(messages))) {
    return undefined
  }
  return toolAvailable(tools, DOCUMENT_TOOL_NAME) ? DOCUMENT_TOOL_NAME : undefined
}

export function shouldWithholdIgnoredDocumentToolChoiceText({
  toolChoiceName,
  candidate,
}: {
  readonly toolChoiceName: string
  readonly candidate: unknown
}): boolean {
  return toolChoiceName === DOCUMENT_TOOL_NAME &&
    documentCandidateText(candidate).trim().length > 0
}

export function buildIgnoredDocumentToolChoiceBlockedText(
  toolChoiceAvailable = true,
): string {
  const reason = toolChoiceAvailable
    ? 'provider ignored forced document tool_choice.'
    : 'document 도구가 현재 TUI 도구 풀에 없어 로컬 문서 검사를 실행할 수 없습니다.'
  return [
    '문서 도구 호출 차단: document tool_choice를 강제했지만 모델 응답에 document 도구 경계가 포함되지 않았습니다.',
    `이유: ${reason}`,
    '로컬 문서는 검색 또는 추측 답변으로 처리하지 않습니다.',
  ].join(' ')
}

export function shouldCompleteAfterSuccessfulDocumentRender(_params: {
  readonly messages: readonly Message[]
}): boolean {
  const userText = latestUserText(_params.messages)
  if (!isDocumentHarnessQuery(userText)) return false
  if (!DOCUMENT_REVIEW_RE.test(userText)) return false
  if (!DOCUMENT_ARTIFACT_ID_RE.test(userText)) return false
  return hasSuccessfulDocumentResultAfter(
    _params.messages,
    latestUserMessageIndex(_params.messages),
    new Set([DOCUMENT_TOOL_NAME, DOCUMENT_RENDER_TOOL_NAME]),
  )
}

export function shouldCompleteAfterTerminalDocumentToolResult(_params: {
  readonly messages: readonly Message[]
}): boolean {
  const userText = latestUserText(_params.messages)
  if (!mentionsDocumentWork(userText)) return false
  return hasTerminalDocumentCompletion({
    messages: _params.messages,
    userText,
  })
}

export function shouldSuppressDocumentToolCallsForAnswerSynthesis(params: {
  readonly messages: readonly Message[]
}): boolean {
  return shouldCompleteAfterSuccessfulDocumentRender(params) ||
    shouldCompleteAfterTerminalDocumentToolResult(params)
}

export function buildDocumentCompletionPromptIfNeeded({
  messages,
}: {
  readonly messages: readonly Message[]
}): string | undefined {
  const userText = latestUserText(messages)
  if (!mentionsDocumentWork(userText)) return undefined
  return buildDocumentCompletionPrompt({ messages, userText })
}
