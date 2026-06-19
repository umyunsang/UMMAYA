import type { BetaContentBlock } from 'src/sdk-compat.js'
import { logError } from '../../utils/log.js'
import { errorMessage } from '../../utils/errors.js'
import {
  buildSourceEvidence,
  buildSourceVerification,
  redactSourceVerificationText,
  type SourceVerificationEvidence,
} from '../WebFetchTool/sourceVerification.js'
import { WEB_SEARCH_TOOL_NAME } from './prompt.js'
import type { Output, SearchResult } from './schemas.js'

type WebSearchResultBlock = {
  readonly type: 'web_search_tool_result'
  readonly tool_use_id: string
  readonly content: unknown
}

type TextBlock = {
  readonly type: 'text'
  readonly text: string
}

type ServerToolUseBlock = {
  readonly type: 'server_tool_use'
}

function isWebSearchResultBlock(
  block: BetaContentBlock,
): block is WebSearchResultBlock {
  return block.type === 'web_search_tool_result'
}

function isTextBlock(block: BetaContentBlock): block is TextBlock {
  return block.type === 'text' && 'text' in block && typeof block.text === 'string'
}

function isServerToolUseBlock(
  block: BetaContentBlock,
): block is ServerToolUseBlock {
  return block.type === 'server_tool_use'
}

function isSearchHit(value: unknown): value is { readonly title: string; readonly url: string } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'title' in value &&
    typeof value.title === 'string' &&
    'url' in value &&
    typeof value.url === 'string'
  )
}

function providerErrorCode(content: unknown): string {
  if (
    typeof content === 'object' &&
    content !== null &&
    'error_code' in content &&
    typeof content.error_code === 'string'
  ) {
    return content.error_code
  }
  return 'provider_error'
}

function appendSearchResultEvidence(
  block: WebSearchResultBlock,
  results: (SearchResult | string)[],
  evidence: SourceVerificationEvidence[],
): void {
  if (!Array.isArray(block.content)) {
    const message = `Web search error: ${providerErrorCode(block.content)}`
    logError(new Error(message))
    results.push(message)
    evidence.push(
      buildSourceEvidence({
        toolId: WEB_SEARCH_TOOL_NAME,
        sourceUrl: null,
        title: 'Provider error',
        blockedOrUsed: 'blocked',
        rawText: message,
      }),
    )
    return
  }

  const hits = block.content.filter(isSearchHit).map(hit => ({
    title: hit.title,
    url: hit.url,
  }))
  for (const hit of hits) {
    evidence.push(
      buildSourceEvidence({
        toolId: WEB_SEARCH_TOOL_NAME,
        sourceUrl: hit.url,
        title: hit.title,
        blockedOrUsed: 'needs_input',
        rawText: `${hit.title}\n${hit.url}`,
      }),
    )
  }
  results.push({
    tool_use_id: block.tool_use_id,
    content: hits,
  })
}

export function makeOutputFromSearchResponse(
  result: readonly BetaContentBlock[],
  query: string,
  durationSeconds: number,
): Output {
  const results: (SearchResult | string)[] = []
  const evidence: SourceVerificationEvidence[] = []
  let textAcc = ''
  let inText = true

  for (const block of result) {
    if (isServerToolUseBlock(block)) {
      if (inText) {
        inText = false
        if (textAcc.trim().length > 0) {
          results.push(textAcc.trim())
        }
        textAcc = ''
      }
      continue
    }

    if (isWebSearchResultBlock(block)) {
      appendSearchResultEvidence(block, results, evidence)
    }

    if (isTextBlock(block)) {
      if (inText) {
        textAcc += block.text
      } else {
        inText = true
        textAcc = block.text
      }
    }
  }

  if (textAcc.length) {
    results.push(redactSourceVerificationText(textAcc.trim()))
  }
  if (evidence.length === 0) {
    evidence.push(
      buildSourceEvidence({
        toolId: WEB_SEARCH_TOOL_NAME,
        sourceUrl: null,
        title: 'No source URL returned',
        blockedOrUsed: 'needs_input',
        rawText: query,
      }),
    )
  }

  return {
    query,
    results,
    durationSeconds,
    sourceVerification: buildSourceVerification(evidence),
  }
}

export function makeBlockedOutputFromProviderError(
  query: string,
  startTime: number,
  error: unknown,
): Output {
  const message = `Source verification blocked: ${errorMessage(error)}`
  const safeMessage = redactSourceVerificationText(message)
  logError(new Error(message))
  return {
    query,
    results: [safeMessage],
    durationSeconds: (performance.now() - startTime) / 1000,
    sourceVerification: buildSourceVerification([
      buildSourceEvidence({
        toolId: WEB_SEARCH_TOOL_NAME,
        sourceUrl: null,
        title: 'Provider error',
        blockedOrUsed: 'blocked',
        rawText: message,
      }),
    ]),
  }
}
