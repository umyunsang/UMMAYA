import type { Message as MessageType } from '../../types/message.js'
import {
  buildSourceVerification,
  sourceVerificationSchema,
  type SourceVerification,
  type SourceVerificationEvidence,
} from '../WebFetchTool/sourceVerification.js'
import { WEB_FETCH_TOOL_NAME } from '../WebFetchTool/prompt.js'
import { WEB_SEARCH_TOOL_NAME } from '../WebSearchTool/prompt.js'

const MAX_PROPAGATED_SOURCE_EVIDENCE = 20

type TrustedSourceToolName =
  | typeof WEB_FETCH_TOOL_NAME
  | typeof WEB_SEARCH_TOOL_NAME

type TrustedToolResultText = {
  readonly text: string
  readonly toolName: TrustedSourceToolName
}

type SourceEvidenceDraft = {
  toolId?: string
  sourceUrl?: string | null
  title?: string | null
  observedAt?: string
  citationHandle?: string
  blockedOrUsed?: SourceVerificationEvidence['blockedOrUsed']
  trust?: SourceVerificationEvidence['trust']
  promptInjection?: SourceVerificationEvidence['promptInjection']
  redacted?: boolean
}

function parseNullableField(value: string): string | null {
  return value === 'none' ? null : value
}

function parseBlockedOrUsed(
  value: string,
): SourceVerificationEvidence['blockedOrUsed'] | undefined {
  switch (value) {
    case 'blocked':
    case 'needs_input':
      return value
    default:
      return undefined
  }
}

function parsePromptInjection(
  value: string,
): SourceVerificationEvidence['promptInjection'] | undefined {
  switch (value) {
    case 'detected':
    case 'not_detected':
      return value
    default:
      return undefined
  }
}

function parseRedacted(value: string): boolean | undefined {
  switch (value) {
    case 'true':
      return true
    case 'false':
      return false
    default:
      return undefined
  }
}

function appendSourceEvidenceDraft(
  draft: SourceEvidenceDraft,
  evidence: SourceVerificationEvidence[],
  expectedToolId: TrustedSourceToolName,
): void {
  if (
    draft.toolId === undefined ||
    draft.toolId !== expectedToolId ||
    draft.sourceUrl === undefined ||
    draft.title === undefined ||
    draft.observedAt === undefined ||
    draft.citationHandle === undefined ||
    draft.blockedOrUsed === undefined ||
    draft.trust === undefined ||
    draft.promptInjection === undefined ||
    draft.redacted === undefined
  ) {
    return
  }
  evidence.push({
    toolId: draft.toolId,
    sourceUrl: draft.sourceUrl,
    title: draft.title,
    observedAt: draft.observedAt,
    citationHandle: draft.citationHandle,
    blockedOrUsed: draft.blockedOrUsed,
    trust: draft.trust,
    promptInjection: draft.promptInjection,
    redacted: draft.redacted,
  })
}

function parseSourceVerificationSegment(
  segment: string,
  evidence: SourceVerificationEvidence[],
  expectedToolId: TrustedSourceToolName,
): void {
  let draft: SourceEvidenceDraft = {}
  for (const line of segment.split('\n')) {
    const separatorIndex = line.indexOf(':')
    if (separatorIndex < 0) continue
    const key = line.slice(0, separatorIndex).trim()
    const value = line.slice(separatorIndex + 1).trim()
    if (key === 'tool_id') {
      appendSourceEvidenceDraft(draft, evidence, expectedToolId)
      if (evidence.length >= MAX_PROPAGATED_SOURCE_EVIDENCE) return
      draft = { toolId: value }
      continue
    }
    switch (key) {
      case 'source_url':
        draft.sourceUrl = parseNullableField(value)
        break
      case 'title':
        draft.title = parseNullableField(value)
        break
      case 'timestamp':
        draft.observedAt = value
        break
      case 'citation_handle':
        draft.citationHandle = value
        break
      case 'blocked_or_used':
        draft.blockedOrUsed = parseBlockedOrUsed(value)
        break
      case 'trust':
        draft.trust = value === 'untrusted_source' ? value : undefined
        break
      case 'prompt_injection':
        draft.promptInjection = parsePromptInjection(value)
        break
      case 'redacted':
        draft.redacted = parseRedacted(value)
        break
      default:
        break
    }
  }
  appendSourceEvidenceDraft(draft, evidence, expectedToolId)
}

function collectSourceVerificationSegments(text: string): string[] {
  const segments: string[] = []
  const openTag = '<source_verification>'
  const closeTag = '</source_verification>'
  let searchStart = 0
  while (searchStart < text.length) {
    const openIndex = text.indexOf(openTag, searchStart)
    if (openIndex < 0) return segments
    const contentStart = openIndex + openTag.length
    const closeIndex = text.indexOf(closeTag, contentStart)
    if (closeIndex < 0) return segments
    segments.push(text.slice(contentStart, closeIndex))
    searchStart = closeIndex + closeTag.length
  }
  return segments
}

function trustedSourceToolName(value: string | undefined): TrustedSourceToolName | undefined {
  switch (value) {
    case WEB_FETCH_TOOL_NAME:
      return WEB_FETCH_TOOL_NAME
    case WEB_SEARCH_TOOL_NAME:
      return WEB_SEARCH_TOOL_NAME
    default:
      return undefined
  }
}

function collectToolUseNameById(
  agentMessages: readonly MessageType[],
): ReadonlyMap<string, string> {
  const toolUseNameById = new Map<string, string>()
  for (const message of agentMessages) {
    if (message.type !== 'assistant') continue
    const { content } = message.message
    if (!Array.isArray(content)) continue
    for (const block of content) {
      if (
        block.type === 'tool_use' &&
        typeof block.id === 'string' &&
        typeof block.name === 'string'
      ) {
        toolUseNameById.set(block.id, block.name)
      }
    }
  }
  return toolUseNameById
}

function collectToolResultText(
  message: MessageType,
  toolUseNameById: ReadonlyMap<string, string>,
): TrustedToolResultText[] {
  if (message.type !== 'user') return []
  const { content } = message.message
  if (!Array.isArray(content)) return []
  const texts: TrustedToolResultText[] = []
  for (const block of content) {
    if (block.type !== 'tool_result' || typeof block.tool_use_id !== 'string') {
      continue
    }
    const toolName = trustedSourceToolName(toolUseNameById.get(block.tool_use_id))
    if (toolName === undefined) continue
    if (typeof block.content === 'string') {
      texts.push({ text: block.content, toolName })
      continue
    }
    if (!Array.isArray(block.content)) continue
    for (const contentBlock of block.content) {
      if (
        typeof contentBlock === 'object' &&
        contentBlock !== null &&
        'text' in contentBlock &&
        typeof contentBlock.text === 'string'
      ) {
        texts.push({ text: contentBlock.text, toolName })
      }
    }
  }
  return texts
}

function validatedSourceVerification(
  evidence: readonly SourceVerificationEvidence[],
): SourceVerification | undefined {
  const verification = buildSourceVerification(evidence)
  return sourceVerificationSchema.safeParse(verification).success
    ? verification
    : undefined
}

export function extractSourceVerificationFromMessages(
  agentMessages: readonly MessageType[],
): SourceVerification | undefined {
  const evidence: SourceVerificationEvidence[] = []
  const toolUseNameById = collectToolUseNameById(agentMessages)
  for (const message of agentMessages) {
    for (const { text, toolName } of collectToolResultText(message, toolUseNameById)) {
      for (const segment of collectSourceVerificationSegments(text)) {
        parseSourceVerificationSegment(segment, evidence, toolName)
        if (evidence.length >= MAX_PROPAGATED_SOURCE_EVIDENCE) {
          return validatedSourceVerification(
            evidence.slice(0, MAX_PROPAGATED_SOURCE_EVIDENCE),
          )
        }
      }
    }
  }
  return evidence.length > 0 ? validatedSourceVerification(evidence) : undefined
}
