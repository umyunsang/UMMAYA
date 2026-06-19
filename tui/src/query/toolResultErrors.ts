export const TOOL_RESULT_ERROR_CODES = {
  toolUnavailable: 'tool_unavailable',
} as const

export type ToolUnavailableErrorPayload = {
  readonly ok: false
  readonly error: {
    readonly code: typeof TOOL_RESULT_ERROR_CODES.toolUnavailable
    readonly tool_name: string
  }
}

const ADAPTER_NOT_FOUND_RE =
  /AdapterNotFound:\s*'([^']+)'\s+is not in the synced backend manifest or the internal tools list/iu

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseJsonRecord(value: string): Record<string, unknown> | undefined {
  try {
    const parsed: unknown = JSON.parse(value)
    return isRecord(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function recordFromValue(value: unknown): Record<string, unknown> | undefined {
  if (typeof value === 'string') return parseJsonRecord(value)
  return isRecord(value) ? value : undefined
}

function adapterNameFromText(value: string): string | undefined {
  const match = ADAPTER_NOT_FOUND_RE.exec(value)
  const name = match?.[1]?.trim()
  return name && name.length > 0 ? name : undefined
}

function firstString(...values: readonly unknown[]): string | undefined {
  return values.find((value): value is string =>
    typeof value === 'string' && value.trim().length > 0
  )
}

export function createToolUnavailableErrorPayload(
  toolName: string,
): ToolUnavailableErrorPayload {
  return {
    ok: false,
    error: {
      code: TOOL_RESULT_ERROR_CODES.toolUnavailable,
      tool_name: toolName,
    },
  }
}

export function parseAdapterNotFoundToolName(value: unknown): string | undefined {
  if (typeof value === 'string') return adapterNameFromText(value)
  const record = recordFromValue(value)
  if (record === undefined) return undefined

  const error = isRecord(record.error) ? record.error : undefined
  const message = firstString(
    error?.message,
    record.message,
    record.toolUseResult,
  )
  const fromMessage = message !== undefined
    ? adapterNameFromText(message)
    : undefined
  if (fromMessage !== undefined) return fromMessage

  const code = firstString(error?.code, record.errorCode)
  const toolName = firstString(
    error?.tool_name,
    record.tool_name,
    record.tool_id,
  )
  return code === 'AdapterNotFound' ? toolName : undefined
}

export function parseToolUnavailableError(
  value: unknown,
): ToolUnavailableErrorPayload | undefined {
  const record = recordFromValue(value)
  if (record === undefined || record.ok !== false) return undefined

  const error = isRecord(record.error) ? record.error : undefined
  if (error === undefined) return undefined

  const code = error.code
  const toolName = error.tool_name
  if (
    code !== TOOL_RESULT_ERROR_CODES.toolUnavailable ||
    typeof toolName !== 'string' ||
    toolName.trim().length === 0
  ) {
    return undefined
  }

  return createToolUnavailableErrorPayload(toolName)
}
