import { describe, expect, test } from 'bun:test'
import { getAnthropicClient } from '../../../src/services/api/client.js'

function sseResponse(lines: string[]): Response {
  const encoder = new TextEncoder()
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const line of lines) {
          controller.enqueue(encoder.encode(`${line}\n\n`))
        }
        controller.close()
      },
    }),
    {
      status: 200,
      headers: { 'content-type': 'text/event-stream', 'x-request-id': 'req_1' },
    },
  )
}

describe('FriendliAI CC provider shim', () => {
  test('projects OpenAI tool-call SSE into CC stream events', async () => {
    let requestBody: Record<string, unknown> | undefined
    const fetchOverride = async (_input: string | URL | Request, init?: RequestInit) => {
      requestBody = JSON.parse(String(init?.body))
      return sseResponse([
        'data: {"id":"chatcmpl_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"kma_current_observation","arguments":"{\\"nx\\":97"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":",\\"ny\\":74}"}}]}}]}',
        'data: {"choices":[{"finish_reason":"tool_calls","delta":{}}],"usage":{"prompt_tokens":11,"completion_tokens":7}}',
        'data: [DONE]',
      ])
    }

    const client = (await getAnthropicClient({
      apiKey: 'friendli-token',
      maxRetries: 0,
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      fetchOverride,
    })) as {
      beta: {
        messages: {
          create: (
            params: Record<string, unknown>,
          ) => {
            withResponse: () => Promise<{ data: AsyncIterable<Record<string, unknown>> }>
          }
        }
      }
    }

    const result = await client.beta.messages
      .create({
        stream: true,
        model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
        max_tokens: 128,
        system: [{ type: 'text', text: 'System prompt' }],
        messages: [{ role: 'user', content: '부산 날씨' }],
        tools: [
          {
            name: 'kma_current_observation',
            description: 'Current KMA observation',
            input_schema: { type: 'object', properties: { nx: { type: 'number' } } },
          },
        ],
      })
      .withResponse()

    const events: Record<string, unknown>[] = []
    for await (const event of result.data) {
      events.push(event)
    }

    expect(requestBody?.['parallel_tool_calls']).toBe(false)
    expect(requestBody?.['messages']).toEqual([
      { role: 'system', content: 'System prompt' },
      { role: 'user', content: '부산 날씨' },
    ])
    expect(requestBody?.['tools']).toEqual([
      {
        type: 'function',
        function: {
          name: 'kma_current_observation',
          description: 'Current KMA observation',
          parameters: { type: 'object', properties: { nx: { type: 'number' } } },
        },
      },
    ])
    expect(events.map(event => event['type'])).toEqual([
      'message_start',
      'content_block_start',
      'content_block_delta',
      'content_block_delta',
      'content_block_stop',
      'message_delta',
      'message_stop',
    ])
    expect(events[1]).toMatchObject({
      type: 'content_block_start',
      index: 0,
      content_block: {
        type: 'tool_use',
        id: 'call_1',
        name: 'kma_current_observation',
      },
    })
    expect(events[5]).toMatchObject({
      type: 'message_delta',
      delta: { stop_reason: 'tool_use' },
      usage: { input_tokens: 11, output_tokens: 7 },
    })
  })

  test('inlines Pydantic-local JSON Schema refs before sending OpenAI tools', async () => {
    let requestBody: Record<string, unknown> | undefined
    const fetchOverride = async (_input: string | URL | Request, init?: RequestInit) => {
      requestBody = JSON.parse(String(init?.body))
      return new Response(
        JSON.stringify({
          id: 'chatcmpl_schema_refs',
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          choices: [{ message: { content: 'done' }, finish_reason: 'stop' }],
          usage: { prompt_tokens: 3, completion_tokens: 1 },
        }),
        { status: 200 },
      )
    }

    const client = (await getAnthropicClient({
      apiKey: 'friendli-token',
      maxRetries: 0,
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      fetchOverride,
    })) as {
      beta: {
        messages: { create: (params: Record<string, unknown>) => Promise<unknown> }
      }
    }

    await client.beta.messages.create({
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      max_tokens: 128,
      messages: [{ role: 'user', content: 'inspect document' }],
      tools: [
        {
          name: 'document_inspect',
          description: 'Inspect document',
          input_schema: {
            $defs: {
              DocumentFormat: {
                type: 'string',
                enum: ['hwpx', 'hwp', 'docx', 'pdf', 'xlsx', 'pptx'],
              },
              DocumentLocator: {
                type: 'object',
                properties: {
                  path: { type: 'string' },
                  expected_format: {
                    anyOf: [{ $ref: '#/$defs/DocumentFormat' }, { type: 'null' }],
                  },
                },
                required: ['path'],
              },
            },
            type: 'object',
            properties: {
              document: { $ref: '#/$defs/DocumentLocator' },
            },
            required: ['document'],
          },
        },
      ],
    })

    const requestTools = requestBody?.['tools'] as Array<{
      function: { parameters: Record<string, unknown> }
    }>
    const parameters = requestTools[0].function.parameters
    expect(JSON.stringify(parameters)).not.toContain('$defs')
    expect(JSON.stringify(parameters)).not.toContain('$ref')
    expect(parameters).toMatchObject({
      type: 'object',
      properties: {
        document: {
          type: 'object',
          properties: {
            expected_format: {
              anyOf: [{ type: 'string' }, { type: 'null' }],
            },
          },
        },
      },
    })
    expect(JSON.stringify(parameters)).toContain('hwpx')
  })

  test('closes assistant text before the first tool block so mid-loop text can paint', async () => {
    const fetchOverride = async () => {
      return sseResponse([
        'data: {"id":"chatcmpl_text_before_tool","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":"먼저 위치를 확인하겠습니다.\\n"}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"kakao_address_search","arguments":"{\\"query\\":\\"부산 사하구 다대1동\\"}"}}]}}]}',
        'data: {"choices":[{"finish_reason":"tool_calls","delta":{}}],"usage":{"prompt_tokens":11,"completion_tokens":7}}',
        'data: [DONE]',
      ])
    }

    const client = (await getAnthropicClient({
      apiKey: 'friendli-token',
      maxRetries: 0,
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      fetchOverride,
    })) as {
      beta: {
        messages: {
          create: (
            params: Record<string, unknown>,
          ) => {
            withResponse: () => Promise<{ data: AsyncIterable<Record<string, unknown>> }>
          }
        }
      }
    }

    const result = await client.beta.messages
      .create({
        stream: true,
        model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
        max_tokens: 128,
        messages: [{ role: 'user', content: '부산 날씨' }],
        tools: [
          {
            name: 'kakao_address_search',
            description: 'Address lookup',
            input_schema: { type: 'object', properties: { query: { type: 'string' } } },
          },
        ],
      })
      .withResponse()

    const events: Record<string, unknown>[] = []
    for await (const event of result.data) {
      events.push(event)
    }

    expect(events.map(event => event['type'])).toEqual([
      'message_start',
      'content_block_start',
      'content_block_delta',
      'content_block_stop',
      'content_block_start',
      'content_block_delta',
      'content_block_stop',
      'message_delta',
      'message_stop',
    ])
    expect(events[1]).toMatchObject({
      type: 'content_block_start',
      index: 0,
      content_block: { type: 'text' },
    })
    expect(events[3]).toMatchObject({ type: 'content_block_stop', index: 0 })
    expect(events[4]).toMatchObject({
      type: 'content_block_start',
      index: 1,
      content_block: {
        type: 'tool_use',
        id: 'call_1',
        name: 'kakao_address_search',
      },
    })
  })

  test('preserves prior tool_use and tool_result pairing in OpenAI messages', async () => {
    let requestBody: Record<string, unknown> | undefined
    const fetchOverride = async (_input: string | URL | Request, init?: RequestInit) => {
      requestBody = JSON.parse(String(init?.body))
      return new Response(
        JSON.stringify({
          id: 'chatcmpl_2',
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          choices: [{ message: { content: 'done' }, finish_reason: 'stop' }],
          usage: { prompt_tokens: 3, completion_tokens: 1 },
        }),
        { status: 200 },
      )
    }

    const client = (await getAnthropicClient({
      apiKey: 'friendli-token',
      maxRetries: 0,
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      fetchOverride,
    })) as {
      beta: {
        messages: { create: (params: Record<string, unknown>) => Promise<unknown> }
      }
    }

    await client.beta.messages.create({
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      max_tokens: 128,
      messages: [
        {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'call_1',
              name: 'kma_current_observation',
              input: { nx: 97, ny: 74 },
            },
          ],
        },
        {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'call_1',
              content: 'observation ok',
            },
          ],
        },
      ],
    })

    expect(requestBody?.['messages']).toEqual([
      {
        role: 'assistant',
        content: null,
        tool_calls: [
          {
            id: 'call_1',
            type: 'function',
            function: {
              name: 'kma_current_observation',
              arguments: '{"nx":97,"ny":74}',
            },
          },
        ],
      },
      { role: 'tool', tool_call_id: 'call_1', content: 'observation ok' },
    ])
  })

  test('sends explicit K-EXAONE reasoning parsing payload by default', async () => {
    let requestBody: Record<string, unknown> | undefined
    const fetchOverride = async (_input: string | URL | Request, init?: RequestInit) => {
      requestBody = JSON.parse(String(init?.body))
      return new Response(
        JSON.stringify({
          id: 'chatcmpl_reasoning_default',
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          choices: [{ message: { content: 'done' }, finish_reason: 'stop' }],
          usage: { prompt_tokens: 3, completion_tokens: 1 },
        }),
        { status: 200 },
      )
    }

    const client = (await getAnthropicClient({
      apiKey: 'friendli-token',
      maxRetries: 0,
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      fetchOverride,
    })) as {
      beta: {
        messages: { create: (params: Record<string, unknown>) => Promise<unknown> }
      }
    }

    await client.beta.messages.create({
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      max_tokens: 128,
      messages: [{ role: 'user', content: 'hi' }],
    })

    expect(requestBody).toMatchObject({
      chat_template_kwargs: { enable_thinking: false },
      parse_reasoning: true,
      include_reasoning: false,
    })
  })

  test('maps explicit deep reasoning mode to FriendliAI thinking payload', async () => {
    let requestBody: Record<string, unknown> | undefined
    const fetchOverride = async (_input: string | URL | Request, init?: RequestInit) => {
      requestBody = JSON.parse(String(init?.body))
      return new Response(
        JSON.stringify({
          id: 'chatcmpl_reasoning_deep',
          model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
          choices: [{ message: { content: 'done' }, finish_reason: 'stop' }],
          usage: { prompt_tokens: 3, completion_tokens: 1 },
        }),
        { status: 200 },
      )
    }

    const client = (await getAnthropicClient({
      apiKey: 'friendli-token',
      maxRetries: 0,
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      fetchOverride,
    })) as {
      beta: {
        messages: { create: (params: Record<string, unknown>) => Promise<unknown> }
      }
    }

    await client.beta.messages.create({
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      max_tokens: 128,
      messages: [{ role: 'user', content: 'hi' }],
      reasoning_mode: 'deep',
    })

    expect(requestBody).toMatchObject({
      chat_template_kwargs: { enable_thinking: true },
      parse_reasoning: true,
      include_reasoning: true,
    })
  })

  test('suppresses unexpected reasoning_content in default streaming mode', async () => {
    const fetchOverride = async () =>
      new Response(
        [
          'data: {"id":"chatcmpl_reasoning_suppressed","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"reasoning_content":"raw trace"}}]}',
          'data: {"choices":[{"delta":{"content":"visible answer"},"finish_reason":"stop"}]}',
          'data: [DONE]',
          '',
        ].join('\n\n'),
        { status: 200 },
      )

    const client = (await getAnthropicClient({
      apiKey: 'friendli-token',
      maxRetries: 0,
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      fetchOverride,
    })) as {
      beta: {
        messages: {
          create: (
            params: Record<string, unknown>,
          ) => {
            withResponse: () => Promise<{
              data: AsyncIterable<{
                type: string
                delta?: { type: string; thinking?: string; text?: string }
              }>
            }>
          }
        }
      }
    }

    const events: Array<{ type: string; delta?: { type: string; thinking?: string; text?: string } }> = []
    const result = await client.beta.messages
      .create({
        model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
        max_tokens: 128,
        messages: [{ role: 'user', content: 'hi' }],
        stream: true,
      })
      .withResponse()
    for await (const event of result.data) {
      events.push(event)
    }

    expect(events.some(event =>
      event.type === 'content_block_delta' &&
      event.delta?.type === 'thinking_delta'
    )).toBe(false)
    expect(events.find(event =>
      event.type === 'content_block_delta' &&
      event.delta?.type === 'text_delta'
    )?.delta?.text).toBe('visible answer')
  })

  test('forwards reasoning_content in explicit deep streaming mode', async () => {
    const fetchOverride = async () =>
      new Response(
        [
          'data: {"id":"chatcmpl_reasoning_deep_stream","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"reasoning_content":"deep trace"}}]}',
          'data: {"choices":[{"delta":{"content":"visible answer"},"finish_reason":"stop"}]}',
          'data: [DONE]',
          '',
        ].join('\n\n'),
        { status: 200 },
      )

    const client = (await getAnthropicClient({
      apiKey: 'friendli-token',
      maxRetries: 0,
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      fetchOverride,
    })) as {
      beta: {
        messages: {
          create: (
            params: Record<string, unknown>,
          ) => {
            withResponse: () => Promise<{
              data: AsyncIterable<{
                type: string
                delta?: { type: string; thinking?: string; text?: string }
              }>
            }>
          }
        }
      }
    }

    const events: Array<{ type: string; delta?: { type: string; thinking?: string; text?: string } }> = []
    const result = await client.beta.messages
      .create({
        model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
        max_tokens: 128,
        messages: [{ role: 'user', content: 'hi' }],
        reasoning_mode: 'deep',
        stream: true,
      })
      .withResponse()
    for await (const event of result.data) {
      events.push(event)
    }

    expect(events.find(event =>
      event.type === 'content_block_delta' &&
      event.delta?.type === 'thinking_delta'
    )?.delta?.thinking).toBe('deep trace')
  })
})
