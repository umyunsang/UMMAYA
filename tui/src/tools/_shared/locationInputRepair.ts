import type { Message } from '../../types/message.js'
import {
  resolveAdapter,
  type AdapterManifestEntry,
} from '../../services/api/adapterManifest.js'
import { isNonSyntheticUserMessageText } from './citizenUserText.js'

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined
}

function messageRecord(message: unknown): Record<string, unknown> | undefined {
  return asRecord(asRecord(message)?.message)
}

function messageRole(message: unknown): string | undefined {
  const outer = asRecord(message)
  const inner = messageRecord(message)
  if (typeof inner?.role === 'string') return inner.role
  if (typeof outer?.role === 'string') return outer.role
  return typeof outer?.type === 'string' ? outer.type : undefined
}

function textFromContent(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map(block => {
      const record = asRecord(block)
      return typeof record?.text === 'string' ? record.text : ''
    })
    .filter(Boolean)
    .join('\n')
}

function latestUserText(messages: readonly unknown[]): string {
  for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
    const message = messages[idx]
    if (messageRole(message) !== 'user') continue
    const text = textFromContent(messageRecord(message)?.content ?? asRecord(message)?.content)
    if (isNonSyntheticUserMessageText(message, text)) return text
  }
  return ''
}

function adapterRequiresQuery(entry: AdapterManifestEntry | undefined): boolean {
  if (!entry || entry.primitive !== 'locate') return false
  const schema = asRecord(entry.input_schema_json)
  const required = schema?.required
  if (!Array.isArray(required) || !required.includes('query')) return false
  const properties = asRecord(schema?.properties)
  return asRecord(properties?.query) !== undefined
}

function hasUsableQuery(params: Record<string, unknown>): boolean {
  return typeof params.query === 'string' && params.query.trim().length > 0
}

function cleanLocationCandidate(candidate: string): string | undefined {
  const cleaned = candidate
    .replace(/["'“”‘’]/g, '')
    .replace(/^(?:오늘|내일|모레|지금|현재|퇴근하고|방금|아까)\s+/u, '')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[은는이가을를의]$/u, '')
    .trim()

  if (cleaned.length < 2 || cleaned.length > 30) return undefined
  if (/^(?:사람|누구|어디|무엇|오늘|내일|지금)$/u.test(cleaned)) {
    return undefined
  }
  return cleaned
}

export function deriveLocationQueryFromUserText(text: string): string | undefined {
  const locativeMatch = text.match(
    /(?:^|[\s,.;!?])([가-힣A-Za-z0-9][가-힣A-Za-z0-9().·'/-]*(?:\s+[가-힣A-Za-z0-9][가-힣A-Za-z0-9().·'/-]*){0,3})\s*(?:에서|근처|주변|부근|인근|앞|쪽)(?=[은는이가을를에\s,.;!?]|$)/u,
  )
  const locativeCandidate = locativeMatch?.[1]
    ? cleanLocationCandidate(locativeMatch[1])
    : undefined
  if (locativeCandidate) return locativeCandidate

  const poiMatch = text.match(
    /([가-힣A-Za-z0-9][가-힣A-Za-z0-9().·'/-]*(?:역|공항|터미널|해수욕장|시장|공원|병원|학교|대학교|구청|시청|센터))/u,
  )
  return poiMatch?.[1] ? cleanLocationCandidate(poiMatch[1]) : undefined
}

export function repairLocateQueryParamsFromConversation(
  input: Record<string, unknown>,
  messages: readonly Message[],
): Record<string, unknown> {
  const toolId = typeof input.tool_id === 'string' ? input.tool_id : ''
  if (!adapterRequiresQuery(resolveAdapter(toolId))) return input

  const params = asRecord(input.params) ?? {}
  if (hasUsableQuery(params)) return input

  const query = deriveLocationQueryFromUserText(latestUserText(messages))
  if (!query) return input

  return {
    ...input,
    params: {
      ...params,
      query,
    },
  }
}
