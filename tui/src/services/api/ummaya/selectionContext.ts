import type { Message } from '../../../types/message.js'
import { latestUserText } from './messages.js'

const RELATIVE_LOCATION_PROMPT_RE =
  /(주위|주변|인근|가까운|우리\s*동네|여기|이\s*근처|현재\s*위치|내\s*위치)/iu
const RELATIVE_HEALTH_PROMPT_RE =
  /(응급|응급실|응급의료|병원|의원|진료|야간진료|약국|의료|건강|아파|다쳤|발열|hospital|clinic|pharmacy|emergency|ER)/iu

type ToolResultBlock = {
  readonly type: 'tool_result'
  readonly content?: unknown
  readonly isError: boolean
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asToolResultBlock(value: unknown): ToolResultBlock | undefined {
  if (!isRecord(value)) return undefined
  if (value.type !== 'tool_result') return undefined
  return {
    type: 'tool_result',
    content: value.content,
    isError: value.is_error === true,
  }
}

function parseJsonObject(value: unknown): Record<string, unknown> | undefined {
  if (isRecord(value)) return value
  if (typeof value !== 'string' || !value.trim()) return undefined
  try {
    const parsed: unknown = JSON.parse(value)
    return isRecord(parsed) ? parsed : undefined
  } catch {
    return undefined
  }
}

function textField(
  source: Record<string, unknown>,
  fieldName: string,
): string | undefined {
  const value = source[fieldName]
  return typeof value === 'string' && value.trim() ? value.trim() : undefined
}

function numberField(
  source: Record<string, unknown>,
  fieldName: string,
): string | undefined {
  const value = source[fieldName]
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : undefined
}

function fieldIndicatesFailure(value: unknown): boolean {
  if (value === false) return true
  if (typeof value !== 'string') return false
  return /(error|fail|failed|failure|timeout|denied|unavailable|invalid)/iu.test(
    value.trim(),
  )
}

function hasExplicitFailure(source: Record<string, unknown>): boolean {
  if (fieldIndicatesFailure(source.ok)) return true
  if (fieldIndicatesFailure(source.success)) return true
  if (fieldIndicatesFailure(source.status)) return true
  const error = source.error
  if (typeof error === 'string') return error.trim().length > 0
  return error !== undefined && error !== null && error !== false
}

function payloadHasExplicitFailure(payload: Record<string, unknown>): boolean {
  if (hasExplicitFailure(payload)) return true
  const data = recordField(payload, 'data')
  return data !== undefined && hasExplicitFailure(data)
}

function recordField(
  source: Record<string, unknown>,
  fieldName: string,
): Record<string, unknown> | undefined {
  const value = source[fieldName]
  return isRecord(value) ? value : undefined
}

function firstTextField(
  sources: readonly Record<string, unknown>[],
  fieldNames: readonly string[],
): string | undefined {
  for (const source of sources) {
    for (const fieldName of fieldNames) {
      const value = textField(source, fieldName)
      if (value !== undefined) return value
    }
  }
  return undefined
}

function firstNumberField(
  sources: readonly Record<string, unknown>[],
  fieldNames: readonly string[],
): string | undefined {
  for (const source of sources) {
    for (const fieldName of fieldNames) {
      const value = numberField(source, fieldName)
      if (value !== undefined) return value
    }
  }
  return undefined
}

function locationCandidateRecords(
  result: Record<string, unknown>,
): readonly Record<string, unknown>[] {
  const candidates = [result]
  for (const slot of ['coords', 'poi', 'region', 'address', 'adm_cd'] as const) {
    const nested = recordField(result, slot)
    if (nested !== undefined) candidates.push(nested)
  }
  return candidates
}

function locationContextFromPayload(
  payload: Record<string, unknown>,
): string | undefined {
  if (payloadHasExplicitFailure(payload)) return undefined
  const data = isRecord(payload.data) ? payload.data : undefined
  const result = isRecord(payload.result)
    ? payload.result
    : data !== undefined && isRecord(data.result)
      ? data.result
      : data ?? payload
  const candidates = locationCandidateRecords(result)
  const latitude = firstNumberField(candidates, ['lat', 'latitude'])
  const longitude = firstNumberField(candidates, ['lon', 'longitude'])
  const x =
    firstTextField(candidates, ['x']) ??
    firstNumberField(candidates, ['x', 'nx'])
  const y =
    firstTextField(candidates, ['y']) ??
    firstNumberField(candidates, ['y', 'ny'])
  const regionName =
    firstTextField(candidates, ['rdd_da_name', 'address_name', 'name']) ??
    [
      firstTextField(candidates, ['region_1depth_name']),
      firstTextField(candidates, ['region_2depth_name']),
      firstTextField(candidates, ['region_3depth_name']),
    ]
      .filter(Boolean)
      .join(' ')
      .trim()
  const address =
    firstTextField(candidates, ['road_address', 'jibun_address'])
  if (!latitude && !longitude && !x && !y && !regionName && !address) {
    return undefined
  }
  return [
    '[prior_location_context]',
    regionName ? `region=${regionName}` : undefined,
    address ? `address=${address}` : undefined,
    latitude && longitude ? `lat=${latitude} lon=${longitude}` : undefined,
    x && y ? `x=${x} y=${y}` : undefined,
  ]
    .filter(Boolean)
    .join(' ')
}

function latestPriorLocationContext(messages: readonly Message[]): string | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message?.type !== 'user') continue
    const content = message.message.content
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const toolResult = asToolResultBlock(block)
      if (toolResult === undefined) continue
      if (toolResult.isError) continue
      const parsed = parseJsonObject(toolResult.content)
      if (parsed === undefined) continue
      const context = locationContextFromPayload(parsed)
      if (context !== undefined) return context
    }
  }
  return undefined
}

function userTextForSelectionIndex(message: Message): string {
  const content = message.message.content
  if (typeof content === 'string') return content.trim()
  if (!Array.isArray(content)) return ''
  return content
    .filter(isRecord)
    .filter(block => block.type === 'text' && typeof block.text === 'string')
    .map(block => String(block.text))
    .join('')
    .trim()
}

function latestCitizenTextIndex(messages: readonly Message[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message?.type !== 'user' || message.isMeta === true) continue
    if (userTextForSelectionIndex(message).length > 0) return index
  }
  return -1
}

export function hasCurrentTurnLocationContext(
  messages: readonly Message[],
): boolean {
  const latestIndex = latestCitizenTextIndex(messages)
  if (latestIndex < 0) return false
  for (let index = latestIndex + 1; index < messages.length; index += 1) {
    const message = messages[index]
    if (message?.type !== 'user') continue
    const content = message.message.content
    if (!Array.isArray(content)) continue
    for (const block of content) {
      const toolResult = asToolResultBlock(block)
      if (toolResult === undefined) continue
      if (toolResult.isError) continue
      const parsed = parseJsonObject(toolResult.content)
      if (parsed !== undefined && locationContextFromPayload(parsed) !== undefined) {
        return true
      }
    }
  }
  return false
}

export function selectionTextWithPriorLocationContext(
  messages: readonly Message[],
): string {
  const latest = latestUserText(messages)
  if (!RELATIVE_LOCATION_PROMPT_RE.test(latest)) return latest
  if (!RELATIVE_HEALTH_PROMPT_RE.test(latest)) return latest
  const locationContext = latestPriorLocationContext(messages)
  return locationContext === undefined ? latest : `${latest}\n${locationContext}`
}
