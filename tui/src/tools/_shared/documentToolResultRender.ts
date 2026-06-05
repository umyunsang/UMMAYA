import React from 'react'
import { PrimitiveDispatcher } from '../../components/primitive/index.js'

type DocumentRenderOptions = {
  verbose?: boolean
  isTranscriptMode?: boolean
}

/**
 * Auto-render a document tool result inline in the TUI — the same way Claude
 * Code renders a code diff after an edit, with no "show viewer" query. Driven
 * by `renderToolResultMessage`, invoked by the message loop for every resolved
 * tool result. See deep-research-migration-document-render.md (approach D).
 */
export function renderDocumentToolResultIfPresent(
  output: unknown,
  options: DocumentRenderOptions = {},
): React.ReactNode | null {
  const payload = extractDocumentToolResultPayload(output)
  if (payload === null) {
    return null
  }
  return React.createElement(PrimitiveDispatcher, {
    payload,
    expanded: options.verbose === true || options.isTranscriptMode === true,
  })
}

/**
 * Retired raster-availability gate.
 *
 * Previously this converted a successful `document_render` into a failure when
 * a page raster was unreadable, because review happened in an external browser
 * viewer that needed the image. Under deep-research-migration approach D the
 * user surface is the structural field-level diff (`StructuredDiffList`), which
 * renders from `diff.changes` and never depends on a raster — so the TUI no
 * longer fabricates a visual-render failure. Page rasters remain Evidence
 * Fabric evidence only (joinable by `correlation_id`).
 *
 * Kept as an identity pass-through so the model-facing primitive tools
 * (AdapterTool / LookupPrimitive / SubmitPrimitive) keep a stable call boundary;
 * full call-site removal is a tracked follow-up.
 */
export function applyDocumentVisualRenderGateToOutput(output: unknown): unknown {
  return output
}

/** The TUI never fabricates a render failure under approach D; backend status
 *  governs. Retained for call-boundary stability (see above). */
export function isDocumentVisualRenderFailedOutput(_output: unknown): boolean {
  return false
}

export function extractDocumentToolResultPayload(
  output: unknown,
): Record<string, unknown> | null {
  const direct = asDocumentToolResultPayload(output)
  if (direct !== null) {
    return direct
  }

  const wrapped = asRecord(output)
  if (wrapped === null) {
    return null
  }
  return asDocumentToolResultPayload(wrapped.result)
}

function asDocumentToolResultPayload(output: unknown): Record<string, unknown> | null {
  const record = asRecord(output)
  if (record === null) {
    return null
  }
  return (
    typeof record.tool_id === 'string' &&
    (record.tool_id === 'document' || record.tool_id.startsWith('document_')) &&
    typeof record.correlation_id === 'string' &&
    typeof record.text_summary === 'string' &&
    isDocumentStatus(record.status)
  )
    ? record
    : null
}

function isDocumentStatus(status: unknown): boolean {
  return (
    status === 'ok' ||
    status === 'blocked' ||
    status === 'failed' ||
    status === 'needs_input'
  )
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}
