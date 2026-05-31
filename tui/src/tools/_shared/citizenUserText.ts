const SYNTHETIC_USER_CONTEXT_RE =
  /<available_adapters\b|<\/available_adapters>|<available-deferred-tools\b|<\/available-deferred-tools>|##\s*Available tools|Current session context|Concrete UMMAYA|Pick a concrete adapter from <available_adapters>|Prefer concrete adapter function calls|<tool_use_error\b|<\/tool_use_error>|AdapterNotFound:|Permission delegation required:|tool-choice mismatch|Required follow-up for this tool chain|Emergency evidence chain complete|KMA analyzed weather-chart|Protected-domain/iu

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : undefined
}

function messageContent(message: unknown): unknown {
  const outer = asRecord(message)
  const inner = asRecord(outer?.message)
  return inner?.content ?? outer?.content
}

function contentHasToolResult(content: unknown): boolean {
  if (!Array.isArray(content)) return false
  return content.some(block => asRecord(block)?.type === 'tool_result')
}

export function isSyntheticUserMessage(message: unknown): boolean {
  const outer = asRecord(message)
  const inner = asRecord(outer?.message)
  return (
    outer?.isMeta === true ||
    inner?.isMeta === true ||
    outer?.isCompactSummary === true ||
    outer?.isVisibleInTranscriptOnly === true ||
    outer?.toolUseResult !== undefined ||
    outer?.sourceToolAssistantUUID !== undefined ||
    contentHasToolResult(messageContent(message))
  )
}

export function isSyntheticUserText(text: string): boolean {
  const trimmed = text.trim()
  return trimmed.length > 0 && SYNTHETIC_USER_CONTEXT_RE.test(trimmed)
}

export function isNonSyntheticUserText(text: string): boolean {
  return text.trim().length > 0 && !isSyntheticUserText(text)
}

export function isNonSyntheticUserMessageText(
  message: unknown,
  text: string,
): boolean {
  return !isSyntheticUserMessage(message) && isNonSyntheticUserText(text)
}
