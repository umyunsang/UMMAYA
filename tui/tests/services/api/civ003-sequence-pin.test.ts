import { describe, expect, test } from 'bun:test'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  createDiagnosticsTarget,
  getToolNames,
  ingestCivilDeathSurfaceManifest,
  readAdapterSelection,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

const CIV003_PROMPT =
  '아버지가 돌아가셨어. 사망신고, 장례 지원, 국민연금 유족급여, 재산 관련 절차를 순서대로 알려줘.'

function responseForCiv003ToolCallOnly(): Response {
  const encoder = new TextEncoder()
  const lines = [
    'data: {"id":"chatcmpl_civ003_tool","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_civ003_bfc","type":"function","function":{"name":"bfc_funeral_area_fee","arguments":"{\\"page_no\\":1,\\"num_of_rows\\":10}"}}]}}]}',
    'data: {"choices":[{"finish_reason":"tool_calls","delta":{}}],"usage":{"prompt_tokens":31,"completion_tokens":4}}',
    'data: [DONE]',
  ]
  return new Response(new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(`${line}\n\n`))
      }
      controller.close()
    },
  }), {
    status: 200,
    headers: { 'content-type': 'text/event-stream', 'x-request-id': 'req_civ003_tool' },
  })
}

describe('CIV-003 provider tool-call PIN', () => {
  test('parses one-turn CIV-003 OpenAI-compatible tool call into a CC tool_use block', async () => {
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestCivilDeathSurfaceManifest('c')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: CIV003_PROMPT })],
          response: responseForCiv003ToolCallOnly(),
        })

        const selection = readAdapterSelection(diagnostics.path)
        expect(selection.final_adapter_tools).toContain('bfc_funeral_area_fee')
        expect(getToolNames(exchange.request)).toContain('bfc_funeral_area_fee')
        expect(JSON.stringify(exchange.events)).toContain('"type":"tool_use"')
        expect(JSON.stringify(exchange.events)).toContain('"name":"bfc_funeral_area_fee"')
      } finally {
        delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
        if (previousDiagnostics !== undefined) {
          process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = previousDiagnostics
        }
        diagnostics.cleanup()
      }
    })
  })
})
