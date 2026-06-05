// SPDX-License-Identifier: Apache-2.0
// Spec 2521 (2026-05-02) — verboseRender outbound-trace assertions.
//
// Exercises:
//   1. renderVerboseInputJson returns the full multi-line input JSON
//      so AssistantToolUseMessage's `<Text>({rendered})</Text>` wrapper
//      shows ``● lookup({\n  "tool_id": ..., "params": {...}\n})``.
//   2. renderVerboseOutputJson surfaces the envelope JSON
//      ("Response envelope:") AND, when traces are present at either the
//      top level or inside ``result``, renders the cyan
//      "Outbound API request #N — METHOD URL-SUMMARY → STATUS (Nms)" section
//      with request/response body blocks. The full URL remains in the
//      envelope JSON; the heading is bounded to avoid terminal corruption.

import { describe, expect, it, mock } from 'bun:test'
import { Box as InkBox, Text as InkText } from '../../../src/ink.js'
import { render } from 'ink-testing-library'
import { join } from 'node:path'
import React from 'react'

const TUI_ROOT = join(import.meta.dir, '../../..')

// Keep this test scoped to verboseRender itself. The real MessageResponse
// and ink facade pull the full theme stack, including bun:bundle-only modules
// that Bun's test runner does not reliably resolve.
await mock.module(join(TUI_ROOT, 'src/ink.js'), () => ({
  Box: InkBox,
  Text: InkText,
}))

await mock.module(join(TUI_ROOT, 'src/components/MessageResponse.js'), () => ({
  MessageResponse: ({ children }: { children?: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children),
}))

const { renderVerboseInputJson, renderVerboseOutputJson } = await import(
  '../../../src/tools/_shared/verboseRender.js'
)

describe('renderVerboseInputJson', () => {
  it('returns multi-line JSON for primitive input', () => {
    const out = renderVerboseInputJson({
      tool_id: 'kma_forecast_fetch',
      params: { lat: 37.5665, lon: 126.978 },
    })
    expect(out).toContain('"tool_id": "kma_forecast_fetch"')
    expect(out).toContain('"lat": 37.5665')
    expect(out).toContain('"lon": 126.978')
    // Leading + trailing newlines so the wrapping ``(...)`` paren lands
    // on its own line in AssistantToolUseMessage.
    expect(out.startsWith('\n')).toBe(true)
    expect(out.endsWith('\n')).toBe(true)
  })

  it('falls back to String() on non-serialisable input', () => {
    const circular: Record<string, unknown> = { a: 1 }
    circular['self'] = circular
    const out = renderVerboseInputJson(circular)
    // Doesn't crash; degrades to a string representation.
    expect(typeof out).toBe('string')
    expect(out.length).toBeGreaterThan(0)
  })
})

describe('renderVerboseOutputJson', () => {
  it('renders the envelope JSON header and body', () => {
    const ui = renderVerboseOutputJson({
      ok: true,
      result: { kind: 'timeseries', points: [] },
    })
    const { lastFrame } = render(<>{ui}</>)
    const out = lastFrame() ?? ''
    expect(out).toContain('Response envelope')
    expect(out).toContain('"ok": true')
    expect(out).toContain('"kind": "timeseries"')
  })

  it('surfaces top-level outbound_traces with method+url+status', () => {
    const ui = renderVerboseOutputJson({
      ok: true,
      result: { kind: 'timeseries', points: [] },
      outbound_traces: [
        {
          method: 'GET',
          url: 'https://apis.data.go.kr/.../getVilageFcst?serviceKey=***',
          response_status: 200,
          elapsed_ms: 842,
          request_body: null,
          response_body:
            '{\n  "response": {\n    "header": { "resultCode": "00" }\n  }\n}',
        },
      ],
    })
    const { lastFrame } = render(<>{ui}</>)
    const out = lastFrame() ?? ''
    expect(out).toContain('Outbound API request #1')
    expect(out).toContain('GET https://apis.data.go.kr/getVilageFcst?serviceKey')
    expect(out).toContain('→ 200')
    expect(out).toContain('842ms')
    expect(out).toContain('Response body')
    expect(out).toContain('"resultCode": "00"')
  })

  it('also picks up outbound_traces nested inside result', () => {
    const ui = renderVerboseOutputJson({
      ok: true,
      result: {
        kind: 'collection',
        items: [],
        outbound_traces: [
          {
            method: 'POST',
            url: 'https://example.kr/api/submit',
            response_status: 202,
            elapsed_ms: 117,
            request_body: '{\n  "name": "홍길동"\n}',
            response_body: '{\n  "received": true\n}',
          },
        ],
      },
    })
    const { lastFrame } = render(<>{ui}</>)
    const out = lastFrame() ?? ''
    expect(out).toContain('Outbound API request #1')
    expect(out).toContain('POST https://example.kr/submit')
    expect(out).toContain('→ 202')
    expect(out).toContain('117ms')
    expect(out).toContain('Request body')
    expect(out).toContain('"홍길동"')
    expect(out).toContain('"received": true')
  })

  it('renders multiple traces with sequential headers', () => {
    const ui = renderVerboseOutputJson({
      ok: true,
      result: { kind: 'record' },
      outbound_traces: [
        { method: 'GET', url: 'https://a.kr/1', response_status: 200, elapsed_ms: 10 },
        { method: 'GET', url: 'https://a.kr/2', response_status: 200, elapsed_ms: 12 },
        { method: 'GET', url: 'https://a.kr/3', response_status: 200, elapsed_ms: 9 },
      ],
    })
    const { lastFrame } = render(<>{ui}</>)
    const out = lastFrame() ?? ''
    expect(out).toContain('Outbound API request #1')
    expect(out).toContain('Outbound API request #2')
    expect(out).toContain('Outbound API request #3')
  })

  it('renders only the envelope when no traces present', () => {
    const ui = renderVerboseOutputJson({ ok: true, result: { kind: 'record' } })
    const { lastFrame } = render(<>{ui}</>)
    const out = lastFrame() ?? ''
    expect(out).toContain('Response envelope')
    expect(out).not.toContain('Outbound API request')
  })
})
