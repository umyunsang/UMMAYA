import { describe, expect, test } from 'bun:test'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

function responseForReasoningThenDocumentPreludeAndToolCall(params: {
  readonly reasoning: string
  readonly prelude: string
}): Response {
  const encoder = new TextEncoder()
  const lines = [
    `data: {"id":"chatcmpl_reasoning_document_tool_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"reasoning_content":${JSON.stringify(params.reasoning)}}}]}`,
    `data: {"choices":[{"delta":{"content":${JSON.stringify(params.prelude)}}}]}`,
    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_document_1","type":"function","function":{"name":"document_inspect","arguments":"{\\"correlation_id\\":\\"doc-corr\\",\\"document\\":{\\"path\\":\\"/Users/um-yunsang/Downloads/readonly-inspect.docx\\",\\"expected_format\\":\\"docx\\"}}"}}]}}]}',
    'data: {"choices":[{"finish_reason":"tool_calls","delta":{}}],"usage":{"prompt_tokens":31,"completion_tokens":12}}',
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
    headers: {
      'content-type': 'text/event-stream',
      'x-request-id': 'req_reasoning_document_tool_1',
    },
  })
}

function eventText(event: unknown): string {
  return JSON.stringify(event)
}

async function withReasoningMode<T>(mode: string, run: () => Promise<T>): Promise<T> {
  const previous = process.env.UMMAYA_K_EXAONE_REASONING_MODE
  try {
    process.env.UMMAYA_K_EXAONE_REASONING_MODE = mode
    return await run()
  } finally {
    if (previous === undefined) {
      delete process.env.UMMAYA_K_EXAONE_REASONING_MODE
    } else {
      process.env.UMMAYA_K_EXAONE_REASONING_MODE = previous
    }
  }
}

describe('UMMAYA provider reasoning prelude painting', () => {
  test('streams visible prelude between reasoning and a native tool call', async () => {
    await withFriendliEnv(async () => {
      await withReasoningMode('deep', async () => {
        const reasoning = '문서 경계를 먼저 판단합니다.'
        const prelude = '문서 구조를 확인하기 위해 document 도구를 먼저 사용하겠습니다.\n'
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({
            content:
              '/Users/um-yunsang/Downloads/readonly-inspect.docx 문서의 구조와 빈칸만 확인해줘. 절대 수정하거나 저장하지 마.',
          })],
          response: responseForReasoningThenDocumentPreludeAndToolCall({
            reasoning,
            prelude,
          }),
        })
        const eventTexts = exchange.events.map(eventText)
        const reasoningIndex = eventTexts.findIndex(text =>
          text.includes('"type":"thinking_delta"') && text.includes(reasoning),
        )
        const preludeIndex = eventTexts.findIndex(text =>
          text.includes('"type":"text_delta"') && text.includes(prelude.trim()),
        )
        const toolUseIndex = eventTexts.findIndex(text =>
          text.includes('"type":"assistant"') &&
          text.includes('"type":"tool_use"') &&
          text.includes('"name":"document_inspect"'),
        )
        expect(reasoningIndex).toBeGreaterThanOrEqual(0)
        expect(preludeIndex).toBeGreaterThan(reasoningIndex)
        expect(toolUseIndex).toBeGreaterThan(preludeIndex)
      })
    })
  })
})
