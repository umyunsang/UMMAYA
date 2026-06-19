import {
  isRecord,
  latestUserMessageIndex,
  messageContent,
  textFromContent,
} from './messageAccess.js'
import {
  DOCUMENT_COMPLETION_PROMPT,
  DOCUMENT_COMPLETION_PROMPT_MARKER,
  DOCUMENT_DIFF_AND_SAVE_ONLY_FINAL_RE,
  DOCUMENT_DIFF_ONLY_FINAL_RE,
  DOCUMENT_INTENT_RE,
  DOCUMENT_READ_ONLY_RE,
  DOCUMENT_RENDER_TOOL_NAME,
  DOCUMENT_TOOL_NAME,
  DOCUMENT_WRITE_RE,
  type DocumentToolName,
} from './documentCompletionPatterns.js'

export function mentionsDocumentWork(text: string): boolean {
  return DOCUMENT_INTENT_RE.test(text)
}

function parseJsonRecord(value: string): Record<string, unknown> | undefined {
  try {
    const parsed: unknown = JSON.parse(value)
    return isRecord(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function hasDocumentCompletionPrompt(messages: readonly unknown[]): boolean {
  return messages.some(message =>
    textFromContent(messageContent(message)).includes(DOCUMENT_COMPLETION_PROMPT_MARKER),
  )
}

function documentToolName(value: unknown): DocumentToolName | undefined {
  if (value === DOCUMENT_TOOL_NAME || value === DOCUMENT_RENDER_TOOL_NAME) {
    return value
  }
  return undefined
}

function topLevelDocumentResultPayload(
  value: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (value === undefined) return undefined
  if (documentToolName(value.tool_id) !== undefined) return value
  const result = isRecord(value.result) ? value.result : undefined
  return documentToolName(result?.tool_id) !== undefined ? result : undefined
}

function documentToolUseName(block: Record<string, unknown>): DocumentToolName | undefined {
  const direct = documentToolName(block.name)
  if (direct !== undefined) return direct
  const input = isRecord(block.input) ? block.input : undefined
  return documentToolName(input?.tool_id)
}

function documentToolUseIdsAfter(
  messages: readonly unknown[],
  afterIndex: number,
): ReadonlyMap<string, DocumentToolName> {
  const toolUses = new Map<string, DocumentToolName>()
  for (let index = Math.max(0, afterIndex + 1); index < messages.length; index += 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (const block of content) {
      if (!isRecord(block) || block.type !== 'tool_use') continue
      const id = typeof block.id === 'string' ? block.id : undefined
      const name = documentToolUseName(block)
      if (id !== undefined && name !== undefined) toolUses.set(id, name)
    }
  }
  return toolUses
}

function documentResultPayloadForToolUse(
  value: Record<string, unknown> | undefined,
  expectedToolName: DocumentToolName,
): Record<string, unknown> | undefined {
  const payload = topLevelDocumentResultPayload(value)
  return documentToolName(payload?.tool_id) === expectedToolName ? payload : undefined
}

function latestDocumentResultPayloadAfter(
  messages: readonly unknown[],
  afterIndex: number,
): Record<string, unknown> | undefined {
  const documentToolUses = documentToolUseIdsAfter(messages, afterIndex)
  if (documentToolUses.size === 0) return undefined
  for (let index = messages.length - 1; index >= Math.max(0, afterIndex + 1); index -= 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (let blockIndex = content.length - 1; blockIndex >= 0; blockIndex -= 1) {
      const block = content[blockIndex]
      if (!isRecord(block) || block.type !== 'tool_result') continue
      if (typeof block.content !== 'string') continue
      const toolUseId = typeof block.tool_use_id === 'string' ? block.tool_use_id : undefined
      const toolUseName = toolUseId === undefined ? undefined : documentToolUses.get(toolUseId)
      if (toolUseName === undefined) continue
      const payload = documentResultPayloadForToolUse(parseJsonRecord(block.content), toolUseName)
      if (payload !== undefined) return payload
    }
  }
  return undefined
}

function documentStatus(value: Record<string, unknown>): string {
  return typeof value.status === 'string' ? value.status.toLowerCase() : 'ok'
}

function isDocumentAnswerSynthesisPayload(payload: Record<string, unknown>): boolean {
  const status = documentStatus(payload)
  if (payload.tool_id === DOCUMENT_RENDER_TOOL_NAME) return status === 'ok'
  return status === 'ok' || status === 'blocked' ||
    status === 'failed' || status === 'needs_input'
}

function documentResultHasDiffContract(record: Record<string, unknown>): boolean {
  return isRecord(record.diff) && Array.isArray(record.diff.changes)
}

function documentResultHasSavedExport(record: Record<string, unknown>): boolean {
  const savedExports = Array.isArray(record.saved_exports) ? record.saved_exports : []
  return savedExports.some(savedExport => {
    const localPath = isRecord(savedExport) ? savedExport.local_path : undefined
    return typeof localPath === 'string' && localPath.trim() !== ''
  })
}

function isDocumentWriteCompletionPayload(payload: Record<string, unknown>): boolean {
  if (payload.tool_id !== DOCUMENT_TOOL_NAME) return false
  const status = documentStatus(payload)
  if (status === 'blocked' || status === 'failed' || status === 'needs_input') return true
  return status === 'ok' &&
    (documentResultHasDiffContract(payload) || documentResultHasSavedExport(payload))
}

function hasDocumentResultAfter(
  messages: readonly unknown[],
  afterIndex: number,
  acceptsPayload: (value: Record<string, unknown>) => boolean,
): boolean {
  const documentToolUses = documentToolUseIdsAfter(messages, afterIndex)
  if (documentToolUses.size === 0) return false
  for (let index = Math.max(0, afterIndex + 1); index < messages.length; index += 1) {
    const content = messageContent(messages[index])
    if (!Array.isArray(content)) continue
    for (const block of content) {
      if (!isRecord(block) || block.type !== 'tool_result') continue
      if (typeof block.content !== 'string') continue
      const toolUseId = typeof block.tool_use_id === 'string' ? block.tool_use_id : undefined
      const toolUseName = toolUseId === undefined ? undefined : documentToolUses.get(toolUseId)
      if (toolUseName === undefined) continue
      const payload = documentResultPayloadForToolUse(parseJsonRecord(block.content), toolUseName)
      if (payload !== undefined && acceptsPayload(payload)) return true
    }
  }
  return false
}

function userTextRequiresDocumentWriteCompletion(userText: string): boolean {
  return DOCUMENT_WRITE_RE.test(userText) && !DOCUMENT_READ_ONLY_RE.test(userText)
}

export function hasTerminalDocumentCompletion({
  messages,
  userText,
}: {
  readonly messages: readonly unknown[]
  readonly userText: string
}): boolean {
  const latestUserIndex = latestUserMessageIndex(messages)
  return userTextRequiresDocumentWriteCompletion(userText)
    ? hasDocumentResultAfter(messages, latestUserIndex, isDocumentWriteCompletionPayload)
    : hasDocumentResultAfter(messages, latestUserIndex, isDocumentAnswerSynthesisPayload)
}

function documentChangeLines(result: Record<string, unknown> | undefined): string[] {
  const changes = isRecord(result?.diff) && Array.isArray(result.diff.changes)
    ? result.diff.changes
    : []
  return changes
    .map(change => {
      if (!isRecord(change)) return undefined
      const targetPath = String(change.target_path ?? 'document')
      const beforeValue = String(change.before_value ?? '')
      const afterValue = String(change.after_value ?? '')
      return `- ${targetPath}: ${beforeValue} -> ${afterValue}`
    })
    .filter((line): line is string => line !== undefined)
}

function savedExportLines(result: Record<string, unknown> | undefined): string[] {
  const savedExports = Array.isArray(result?.saved_exports) ? result.saved_exports : []
  return savedExports
    .map(savedExport => {
      const localPath = isRecord(savedExport) ? savedExport.local_path : undefined
      return typeof localPath === 'string' && localPath.trim() ? `- ${localPath}` : undefined
    })
    .filter((line): line is string => line !== undefined)
}

function documentDiffOnlyCompletionPromptFromResult(
  result: Record<string, unknown> | undefined,
): string | undefined {
  const lines = documentChangeLines(result)
  if (lines.length === 0) return undefined
  return [
    `${DOCUMENT_COMPLETION_PROMPT_MARKER}: the document tool_result for the latest citizen request is already visible in the TUI.`,
    'The citizen explicitly requested only the actually changed content.',
    'Reply in Korean with exactly these lines and nothing else:',
    '실제 변경된 내용:',
    ...lines,
    'Do not add document status, save/render/browser/artifact/viewer details, workflow summaries, visual diff explanations, or any extra sentence.',
  ].join('\n')
}

function documentDiffAndSaveOnlyCompletionPrompt(
  result: Record<string, unknown> | undefined,
): string | undefined {
  const changeLines = documentChangeLines(result)
  if (changeLines.length === 0) return undefined
  const lines = [
    `${DOCUMENT_COMPLETION_PROMPT_MARKER}: the document tool_result for the latest citizen request is already visible in the TUI.`,
    'The citizen explicitly requested only the actually changed content and save location.',
    'Reply in Korean with exactly these lines and nothing else:',
    '실제 변경된 내용:',
    ...changeLines,
  ]
  const saveLines = savedExportLines(result)
  if (saveLines.length > 0) {
    lines.push('저장 위치:', ...saveLines)
  } else {
    lines.push('Do not mention 저장 위치 or any saved path because saved_exports is absent.')
  }
  lines.push(
    'Do not add document status, render/browser/artifact/viewer details, workflow summaries, visual diff explanations, or any extra sentence.',
  )
  return lines.join('\n')
}

function documentDiffOnlyCompletionPrompt(
  userText: string,
  messages: readonly unknown[],
): string | undefined {
  const result = latestDocumentResultPayloadAfter(
    messages,
    latestUserMessageIndex(messages),
  )
  if (DOCUMENT_DIFF_AND_SAVE_ONLY_FINAL_RE.test(userText)) {
    return documentDiffAndSaveOnlyCompletionPrompt(result)
  }
  if (!DOCUMENT_DIFF_ONLY_FINAL_RE.test(userText)) return undefined
  return documentDiffOnlyCompletionPromptFromResult(result)
}

export function buildDocumentCompletionPrompt({
  messages,
  userText,
}: {
  readonly messages: readonly unknown[]
  readonly userText: string
}): string | undefined {
  if (hasDocumentCompletionPrompt(messages)) return undefined
  if (!hasTerminalDocumentCompletion({ messages, userText })) return undefined
  return documentDiffOnlyCompletionPrompt(userText, messages) ?? DOCUMENT_COMPLETION_PROMPT
}
