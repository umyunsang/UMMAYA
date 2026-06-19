export type RawJsonToolCallProposal = {
  readonly name: string
  readonly input: Record<string, unknown>
}

export const RAW_JSON_REGISTERED_TOOL_USE_ID_PREFIX = 'call_raw_json_tool_'
export const RAW_JSON_UNREGISTERED_TOOL_USE_ID_PREFIX =
  'call_raw_json_unregistered_tool_'

export function isUnregisteredRawJsonToolUseId(id: string): boolean {
  return id.startsWith(RAW_JSON_UNREGISTERED_TOOL_USE_ID_PREFIX)
}

export type RawJsonToolCallMalformedReason =
  | 'invalid_json'
  | 'top_level_contract_mismatch'
  | 'name_contract_mismatch'
  | 'arguments_contract_mismatch'

export type RawJsonToolCallNonProposalReason =
  | 'not_exact_top_level_json'
  | 'not_tool_like_json'

export type RawJsonToolCallClassification =
  | { readonly kind: 'registered'; readonly executable: true; readonly proposal: RawJsonToolCallProposal }
  | { readonly kind: 'unregistered'; readonly executable: false; readonly proposal: RawJsonToolCallProposal }
  | { readonly kind: 'malformed_input'; readonly executable: false; readonly reason: RawJsonToolCallMalformedReason }
  | { readonly kind: 'non_proposal'; readonly executable: false; readonly reason: RawJsonToolCallNonProposalReason }

type ExactRawJsonToolCallParseResult =
  | { readonly kind: 'proposal'; readonly proposal: RawJsonToolCallProposal }
  | { readonly kind: 'malformed_input'; readonly reason: RawJsonToolCallMalformedReason }
  | { readonly kind: 'non_proposal'; readonly reason: RawJsonToolCallNonProposalReason }

export type TrailingRawJsonToolCallProposal = {
  readonly prelude: string
  readonly proposal: RawJsonToolCallProposal
}

export type TextualToolCallProposalExtraction = {
  readonly text: string
  readonly proposals: readonly RawJsonToolCallProposal[]
}

const TOOL_CALL_OPEN = '<tool_call>'
const TOOL_CALL_CLOSE = '</tool_call>'
const RAW_JSON_TOOL_CALL_KEY_START_RE =
  /^\s*\{\s*["'](?:name|tool)["']\s*:\s*["'][^"']+["']/iu

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

function parseArguments(value: unknown): Record<string, unknown> | undefined {
  if (isRecord(value)) return value
  if (typeof value !== 'string') return undefined
  return parseJsonRecord(value)
}

function isToolLikeRecord(value: Record<string, unknown>): boolean {
  const topLevelKeys = Object.keys(value)
  return topLevelKeys.includes('name') ||
    topLevelKeys.includes('tool') ||
    topLevelKeys.includes('arguments')
}

function parseExactRawJsonToolCallProposal(params: {
  readonly text: string
}): ExactRawJsonToolCallParseResult {
  const trimmed = params.text.trim()
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) {
    return { kind: 'non_proposal', reason: 'not_exact_top_level_json' }
  }

  const parsed = parseJsonRecord(trimmed)
  if (parsed === undefined) {
    if (RAW_JSON_TOOL_CALL_KEY_START_RE.test(trimmed)) {
      return { kind: 'malformed_input', reason: 'invalid_json' }
    }
    return { kind: 'non_proposal', reason: 'not_tool_like_json' }
  }

  const topLevelKeys = Object.keys(parsed)
  if (
    topLevelKeys.length !== 2 ||
    !topLevelKeys.includes('name') ||
    !topLevelKeys.includes('arguments')
  ) {
    return isToolLikeRecord(parsed)
      ? { kind: 'malformed_input', reason: 'top_level_contract_mismatch' }
      : { kind: 'non_proposal', reason: 'not_tool_like_json' }
  }

  const name = parsed.name
  if (typeof name !== 'string' || name.trim().length === 0) {
    return { kind: 'malformed_input', reason: 'name_contract_mismatch' }
  }

  const input = parseArguments(parsed.arguments)
  if (input === undefined) {
    return { kind: 'malformed_input', reason: 'arguments_contract_mismatch' }
  }
  return { kind: 'proposal', proposal: { name, input } }
}

export function classifyRawJsonToolCallProposal(params: {
  readonly text: string
  readonly availableToolNames: readonly string[]
}): RawJsonToolCallClassification {
  const result = parseExactRawJsonToolCallProposal({ text: params.text })
  switch (result.kind) {
    case 'proposal': {
      const availableToolNames = new Set(params.availableToolNames)
      return availableToolNames.has(result.proposal.name)
        ? {
            kind: 'registered',
            executable: true,
            proposal: result.proposal,
          }
        : {
            kind: 'unregistered',
            executable: false,
            proposal: result.proposal,
          }
    }
    case 'malformed_input':
      return { kind: 'malformed_input', executable: false, reason: result.reason }
    case 'non_proposal':
      return { kind: 'non_proposal', executable: false, reason: result.reason }
  }
}

export function parseRawJsonToolCallProposal(params: {
  readonly text: string
}): RawJsonToolCallProposal | undefined {
  const result = parseExactRawJsonToolCallProposal(params)
  switch (result.kind) {
    case 'proposal':
      return result.proposal
    case 'malformed_input':
    case 'non_proposal':
      return undefined
  }
}

export function parseTrailingRawJsonToolCallProposal(params: {
  readonly text: string
}): TrailingRawJsonToolCallProposal | undefined {
  const trimmedEnd = params.text.trimEnd()
  let candidateStart = trimmedEnd.lastIndexOf('{')
  while (candidateStart >= 0) {
    const proposal = parseRawJsonToolCallProposal({
      text: trimmedEnd.slice(candidateStart),
    })
    if (proposal !== undefined) {
      return {
        prelude: trimmedEnd.slice(0, candidateStart).trimEnd(),
        proposal,
      }
    }
    if (candidateStart === 0) break
    candidateStart = trimmedEnd.lastIndexOf('{', candidateStart - 1)
  }
  return undefined
}

export function extractTextualToolCallProposals(params: {
  readonly text: string
}): TextualToolCallProposalExtraction | undefined {
  let searchStart = 0
  let cleanedText = ''
  const proposals: RawJsonToolCallProposal[] = []

  while (searchStart < params.text.length) {
    const openIndex = params.text.indexOf(TOOL_CALL_OPEN, searchStart)
    if (openIndex < 0) {
      cleanedText += params.text.slice(searchStart)
      break
    }

    const payloadStart = openIndex + TOOL_CALL_OPEN.length
    const closeIndex = params.text.indexOf(TOOL_CALL_CLOSE, payloadStart)
    if (closeIndex < 0) {
      return undefined
    }

    const proposal = parseRawJsonToolCallProposal({
      text: params.text.slice(payloadStart, closeIndex),
    })
    if (proposal === undefined) {
      return undefined
    }

    cleanedText += params.text.slice(searchStart, openIndex)
    proposals.push(proposal)
    searchStart = closeIndex + TOOL_CALL_CLOSE.length
  }

  if (proposals.length === 0) return undefined
  return {
    text: cleanedText.trimEnd(),
    proposals,
  }
}

export function textContainsToolCallProposal(text: string): boolean {
  return extractTextualToolCallProposals({ text }) !== undefined ||
    parseTrailingRawJsonToolCallProposal({ text }) !== undefined
}

export function textContainsMalformedToolCallProposal(text: string): boolean {
  if (textContainsToolCallProposal(text)) return false
  if (text.includes(TOOL_CALL_OPEN)) return true

  const trimmedEnd = text.trimEnd()
  let candidateStart = trimmedEnd.lastIndexOf('{')
  while (candidateStart >= 0) {
    const candidate = trimmedEnd.slice(candidateStart)
    if (RAW_JSON_TOOL_CALL_KEY_START_RE.test(candidate)) {
      return parseJsonRecord(candidate) === undefined
    }
    if (candidateStart === 0) break
    candidateStart = trimmedEnd.lastIndexOf('{', candidateStart - 1)
  }
  return false
}

export function stripToolCallProposalText(text: string): string {
  const textual = extractTextualToolCallProposals({ text })
  if (textual !== undefined) return textual.text
  const trailing = parseTrailingRawJsonToolCallProposal({ text })
  return trailing?.prelude ?? text
}
