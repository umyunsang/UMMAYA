// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Spec 2521 / 2026-05-01.
//
// Verbose render helpers for the 4 primitives (LookupPrimitive,
// SubmitPrimitive, VerifyPrimitive, SubscribePrimitive). Mirrors the
// CC pattern used by BashTool / WebFetchTool: when ``verbose`` is set
// (Ctrl+O expand or transcript mode), surface the full request/response
// JSON to the citizen rather than the condensed summary.
//
// CC reference: tools/BashTool/UI.tsx:renderToolUseMessage(verbose)
//                tools/BashTool/UI.tsx:renderToolResultMessage(verbose)
//
// Citizen flow:
//   non-verbose → "● lookup(kma_forecast_fetch)" + condensed result
//   verbose     → "● lookup({\n  \"tool_id\": ..., \"params\": {...}\n})"
//                 + ⎿ Response: { "ok": true, "result": {...} }
//

import React from 'react'
import { Box, Text } from '../../ink.js'
import { MessageResponse } from '../../components/MessageResponse.js'

/**
 * Format the full primitive input as a multi-line JSON string.
 *
 * The returned string is interpolated into AssistantToolUseMessage's
 * ``<Text>({rendered})</Text>`` wrapper, so the closing paren ends up
 * on its own line — matches CC BashTool's multi-line command rendering.
 */
export function renderVerboseInputJson(input: unknown): string {
  try {
    return '\n' + JSON.stringify(input, null, 2) + '\n'
  } catch {
    return String(input)
  }
}

/**
 * Render the full primitive output envelope as a JSON code block under
 * the standard ⎿ MessageResponse gutter glyph.
 *
 * Used by the 4 primitives' ``renderToolResultMessage`` when
 * ``options.verbose`` (or transcript mode) is set.
 *
 * If the output (or its ``result``) carries an ``outbound_traces`` array
 * (populated by :mod:`kosmos.tools._outbound_trace` on the backend), the
 * outbound HTTP request/response JSON is rendered as a sibling section
 * BELOW the envelope JSON so the citizen/operator can see exactly what
 * hit the agency API and what came back.
 */
export function renderVerboseOutputJson(
  output: unknown,
  label = '응답 envelope',
): React.ReactNode {
  let body: string
  try {
    body = JSON.stringify(output, null, 2)
  } catch {
    body = String(output)
  }

  const traces = extractOutboundTraces(output)

  const children: React.ReactNode[] = [
    React.createElement(Text, { bold: true, key: 'label' }, `${label}:`),
    React.createElement(Text, { dimColor: true, key: 'body' }, body),
  ]

  traces.forEach((trace, idx) => {
    children.push(
      React.createElement(
        Text,
        { bold: true, color: 'cyan', key: `trace-${idx}-h` },
        `\n외부 API 요청 #${idx + 1} — ${trace.method} ${trace.url}` +
          (typeof trace.response_status === 'number'
            ? ` → ${trace.response_status}`
            : '') +
          (typeof trace.elapsed_ms === 'number'
            ? ` (${trace.elapsed_ms}ms)`
            : ''),
      ),
    )
    if (trace.request_body) {
      children.push(
        React.createElement(
          Text,
          { dimColor: true, key: `trace-${idx}-rq-h` },
          '요청 body:',
        ),
        React.createElement(
          Text,
          { dimColor: true, key: `trace-${idx}-rq` },
          String(trace.request_body),
        ),
      )
    }
    if (trace.response_body) {
      children.push(
        React.createElement(
          Text,
          { dimColor: true, key: `trace-${idx}-rs-h` },
          '응답 body:',
        ),
        React.createElement(
          Text,
          { dimColor: true, key: `trace-${idx}-rs` },
          String(trace.response_body),
        ),
      )
    }
  })

  return React.createElement(
    MessageResponse,
    null,
    React.createElement(Box, { flexDirection: 'column' }, ...children),
  )
}

type OutboundTrace = {
  method?: string
  url?: string
  request_body?: unknown
  response_status?: unknown
  response_body?: unknown
  elapsed_ms?: unknown
}

function extractOutboundTraces(output: unknown): OutboundTrace[] {
  if (!output || typeof output !== 'object') return []
  const obj = output as Record<string, unknown>
  // Primitive output schema: { ok: true, result: { outbound_traces: [...] } }
  // OR backend envelope: { kind, outbound_traces: [...] }
  const candidate =
    (obj.outbound_traces as unknown) ??
    ((obj.result as Record<string, unknown> | undefined)?.outbound_traces as unknown)
  if (!Array.isArray(candidate)) return []
  return candidate as OutboundTrace[]
}
