import { createHash, randomUUID } from 'node:crypto'
import { appendFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { getSessionId } from '../../../bootstrap/state.js'
import {
  appendRouteDiagnostic,
  hashRouteDiagnosticText,
} from '../../../tools/AdapterTool/routeDiagnostics.js'
import { getUmmayaUserTierRoot } from '../../../utils/ummayaPaths.js'
import { logForDebugging } from '../../../utils/debug.js'
import { latestUserText } from './messages.js'
import type { QueryModelParams } from './types.js'

export type ProviderTurnEvidenceContext = {
  readonly session_id: string
  readonly correlation_id: string
  readonly frame_hash: string
  readonly query_hash: string
  readonly query_source: string
  readonly model: string
}

type ProviderTurnEvidenceEvent = 'provider_turn_start' | 'provider_turn_complete'

type ProviderTurnEvidenceRecord = ProviderTurnEvidenceContext & {
  readonly schema_version: 'ummaya.tui.turn_evidence.v1'
  readonly ts: string
  readonly event: ProviderTurnEvidenceEvent
  readonly source: 'provider_direct'
  readonly sanitized: true
}

export function createProviderTurnEvidenceContext(
  params: QueryModelParams,
): ProviderTurnEvidenceContext {
  const sessionId = getSessionId()
  const correlationId = randomUUID()
  const queryHash = hashRouteDiagnosticText(latestUserText(params.messages))
  const querySource = params.options.querySource
  const model = params.options.model
  return {
    session_id: sessionId,
    correlation_id: correlationId,
    frame_hash: hashFrame({
      sessionId,
      correlationId,
      queryHash,
      querySource,
      model,
    }),
    query_hash: queryHash,
    query_source: querySource,
    model,
  }
}

export function appendProviderTurnEvidence(
  event: ProviderTurnEvidenceEvent,
  context: ProviderTurnEvidenceContext,
): void {
  appendRouteDiagnostic(event, {
    session_id: context.session_id,
    correlation_id: context.correlation_id,
    frame_hash: context.frame_hash,
    query_hash: context.query_hash,
    query_source: context.query_source,
    model: context.model,
  })

  const memdirFile = evidenceFilePath(context.session_id)
  if (memdirFile === null) return
  const record: ProviderTurnEvidenceRecord = {
    schema_version: 'ummaya.tui.turn_evidence.v1',
    ts: new Date().toISOString(),
    event,
    source: 'provider_direct',
    sanitized: true,
    ...context,
  }
  try {
    mkdirSync(join(getUmmayaUserTierRoot(), 'evidence', 'tui-turns'), {
      recursive: true,
    })
    appendFileSync(memdirFile, `${JSON.stringify(record)}\n`, {
      encoding: 'utf8',
      mode: 0o600,
    })
  } catch (error) {
    if (error instanceof Error) {
      logForDebugging(`provider turn evidence write failed: ${error.message}`)
      return
    }
    throw error
  }
}

export function appendProviderOutputEvidence(
  event: unknown,
  context: ProviderTurnEvidenceContext,
): void {
  const summary = providerOutputSummary(event)
  appendRouteDiagnostic('provider_output', {
    session_id: context.session_id,
    correlation_id: context.correlation_id,
    frame_hash: context.frame_hash,
    query_hash: context.query_hash,
    query_source: context.query_source,
    model: context.model,
    output_type: summary.outputType,
    stream_event_type: summary.streamEventType,
    assistant_text_chars: summary.assistantTextChars,
    assistant_tool_use_count: summary.assistantToolUseCount,
    assistant_content_block_count: summary.assistantContentBlockCount,
    is_api_error_message: summary.isApiErrorMessage,
  })
}

function evidenceFilePath(sessionId: string): string | null {
  if (!process.env.UMMAYA_MEMDIR_USER) return null
  return join(getUmmayaUserTierRoot(), 'evidence', 'tui-turns', `${sessionId}.jsonl`)
}

function providerOutputSummary(event: unknown): {
  readonly outputType: string
  readonly streamEventType: string | null
  readonly assistantTextChars: number
  readonly assistantToolUseCount: number
  readonly assistantContentBlockCount: number
  readonly isApiErrorMessage: boolean
} {
  if (!isRecord(event)) {
    return emptyProviderOutputSummary('unknown')
  }
  const type = typeof event.type === 'string' ? event.type : 'unknown'
  if (type === 'stream_event') {
    const streamEvent = isRecord(event.event) ? event.event : {}
    return {
      ...emptyProviderOutputSummary(type),
      streamEventType:
        typeof streamEvent.type === 'string' ? streamEvent.type : null,
    }
  }
  if (type !== 'assistant') {
    return emptyProviderOutputSummary(type)
  }
  const message = isRecord(event.message) ? event.message : {}
  const content = Array.isArray(message.content) ? message.content : []
  let assistantTextChars = 0
  let assistantToolUseCount = 0
  for (const block of content) {
    if (!isRecord(block)) continue
    if (block.type === 'text' && typeof block.text === 'string') {
      assistantTextChars += block.text.length
    }
    if (block.type === 'tool_use') {
      assistantToolUseCount += 1
    }
  }
  return {
    outputType: type,
    streamEventType: null,
    assistantTextChars,
    assistantToolUseCount,
    assistantContentBlockCount: content.length,
    isApiErrorMessage: event.isApiErrorMessage === true,
  }
}

function emptyProviderOutputSummary(outputType: string) {
  return {
    outputType,
    streamEventType: null,
    assistantTextChars: 0,
    assistantToolUseCount: 0,
    assistantContentBlockCount: 0,
    isApiErrorMessage: false,
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hashFrame(payload: {
  readonly sessionId: string
  readonly correlationId: string
  readonly queryHash: string
  readonly querySource: string
  readonly model: string
}): string {
  return createHash('sha256')
    .update(JSON.stringify(payload), 'utf8')
    .digest('hex')
}
