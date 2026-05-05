// SPDX-License-Identifier: Apache-2.0
//
// Lead-Diag-4 (2026-05-04, role='tool' wire conversion) — unit tests.
//
// Verifies the OpenAI Chat Completions multi-turn pairing invariant on
// the wire: every role='tool' message carries name + tool_call_id, every
// assistant turn that requested tool calls carries the matching tool_calls[]
// entry on the assistant message itself, and the wire ordering matches
// OpenAI's spec (assistant.tool_calls turn → role='tool' result(s) →
// next user/assistant turn).
//
// Strategy mirrors orphan.test.ts — pure-function unit test on the leaf
// builder so we avoid pulling autoCompact.ts → 'bun:bundle' through the
// resolver. The full queryModelWithStreaming generator is still covered
// by the existing fixture-based tests; this file targets ONLY the wire
// shape contract.

import { describe, test, expect } from 'bun:test'
import {
  buildChatMessagesFromTranscript,
  extractTextFromContent,
  serializeToolResultContent,
  serializeToolUseInput,
  findToolNameForResult,
} from '../../src/query/chatMessagesBuilder.js'
import type { ChatMessage } from '../../src/ipc/frames.generated.js'

// ---------------------------------------------------------------------------
// Fixtures — CC-shape transcript messages (Anthropic Messages API native)
// ---------------------------------------------------------------------------

function userPrompt(text: string) {
  return { type: 'user', message: { role: 'user', content: text } }
}

function assistantPrompt(text: string) {
  return { type: 'assistant', message: { role: 'assistant', content: text } }
}

function assistantToolUse(text: string, calls: Array<{ id: string; name: string; input: unknown }>) {
  const blocks: Array<unknown> = []
  if (text.length > 0) blocks.push({ type: 'text', text })
  for (const c of calls) {
    blocks.push({ type: 'tool_use', id: c.id, name: c.name, input: c.input })
  }
  return {
    type: 'assistant',
    message: { role: 'assistant', content: blocks },
  }
}

function userToolResult(results: Array<{ tool_use_id: string; content: unknown; is_error?: boolean }>) {
  return {
    type: 'user',
    message: {
      role: 'user',
      content: results.map((r) => ({
        type: 'tool_result',
        tool_use_id: r.tool_use_id,
        content: r.content,
        ...(r.is_error ? { is_error: true } : {}),
      })),
    },
  }
}

// ---------------------------------------------------------------------------
// Test 1 — string-content fast path (backward compat baseline)
// ---------------------------------------------------------------------------

describe('buildChatMessagesFromTranscript — string-content fast path', () => {
  test('preserves single-turn user+assistant prose 1:1', () => {
    const out = buildChatMessagesFromTranscript([
      userPrompt('강남역 근처 내과 알려줘'),
      assistantPrompt('네, 찾아드리겠습니다.'),
    ])
    expect(out).toEqual([
      { role: 'user', content: '강남역 근처 내과 알려줘' },
      { role: 'assistant', content: '네, 찾아드리겠습니다.' },
    ] as ChatMessage[])
  })

  test('returns empty-content fallback when transcript is empty', () => {
    const out = buildChatMessagesFromTranscript([])
    expect(out).toEqual([{ role: 'user', content: '' }])
  })

  test('skips system / progress / attachment turns', () => {
    const out = buildChatMessagesFromTranscript([
      { type: 'system', message: { role: 'system', content: 'ignored' } },
      { type: 'progress', toolUseID: 'X', data: {} },
      userPrompt('hi'),
    ])
    expect(out).toEqual([{ role: 'user', content: 'hi' }])
  })

  test('skips empty-string content (matches legacy extractText behaviour)', () => {
    const out = buildChatMessagesFromTranscript([
      userPrompt(''),
      assistantPrompt(''),
      userPrompt('real'),
    ])
    expect(out).toEqual([{ role: 'user', content: 'real' }])
  })
})

// ---------------------------------------------------------------------------
// Test 2 — assistant tool_use → tool_calls promotion
// ---------------------------------------------------------------------------

describe('buildChatMessagesFromTranscript — assistant tool_use', () => {
  test('promotes tool_use blocks to OpenAI tool_calls[] on assistant message', () => {
    const out = buildChatMessagesFromTranscript([
      userPrompt('서울 날씨 알려줘'),
      assistantToolUse('잠시만요, 확인해보겠습니다.', [
        {
          id: 'call_001',
          name: 'lookup',
          input: { mode: 'fetch', tool_id: 'kma_short_term_forecast', params: { nx: 60, ny: 127 } },
        },
      ]),
    ])

    expect(out).toHaveLength(2)
    expect(out[0]).toEqual({ role: 'user', content: '서울 날씨 알려줘' })
    expect(out[1]?.role).toBe('assistant')
    expect(out[1]?.content).toBe('잠시만요, 확인해보겠습니다.')
    expect(out[1]?.tool_calls).toHaveLength(1)
    expect(out[1]?.tool_calls?.[0]).toEqual({
      id: 'call_001',
      type: 'function',
      function: {
        name: 'lookup',
        arguments: JSON.stringify({
          mode: 'fetch',
          tool_id: 'kma_short_term_forecast',
          params: { nx: 60, ny: 127 },
        }),
      },
    })
  })

  test('handles parallel tool calls in a single assistant turn', () => {
    const out = buildChatMessagesFromTranscript([
      userPrompt('병원과 약국 둘 다 찾아줘'),
      assistantToolUse('', [
        { id: 'call_a', name: 'lookup', input: { tool_id: 'hira_hospital_search' } },
        { id: 'call_b', name: 'lookup', input: { tool_id: 'mohw_pharmacy_search' } },
      ]),
    ])
    expect(out[1]?.tool_calls).toHaveLength(2)
    expect(out[1]?.tool_calls?.[0]?.id).toBe('call_a')
    expect(out[1]?.tool_calls?.[1]?.id).toBe('call_b')
    // Empty content is allowed by OpenAI spec when tool_calls is set.
    expect(out[1]?.content).toBe('')
  })

  test('drops tool_use blocks missing id or name (defensive)', () => {
    const out = buildChatMessagesFromTranscript([
      userPrompt('hi'),
      assistantToolUse('', [
        { id: '', name: 'lookup', input: {} },
        { id: 'call_x', name: '', input: {} },
        { id: 'call_y', name: 'verify', input: { ok: true } },
      ]),
    ])
    // Only the well-formed call survives; empty assistant text + 1 call.
    expect(out[1]?.tool_calls).toHaveLength(1)
    expect(out[1]?.tool_calls?.[0]?.id).toBe('call_y')
  })

  test('drops thinking blocks (CC also drops them at API boundary)', () => {
    const out = buildChatMessagesFromTranscript([
      userPrompt('hi'),
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            { type: 'thinking', thinking: 'CoT body' },
            { type: 'text', text: '안녕하세요' },
          ],
        },
      },
    ])
    expect(out).toEqual([
      { role: 'user', content: 'hi' },
      { role: 'assistant', content: '안녕하세요' },
    ])
  })
})

// ---------------------------------------------------------------------------
// Test 3 — user tool_result → role='tool' promotion (the Lead-Diag-4 fix)
// ---------------------------------------------------------------------------

describe('buildChatMessagesFromTranscript — tool_result promotion', () => {
  test('promotes a single tool_result to role=tool with name + tool_call_id', () => {
    const out = buildChatMessagesFromTranscript([
      userPrompt('날씨 알려줘'),
      assistantToolUse('', [{ id: 'call_001', name: 'lookup', input: { foo: 1 } }]),
      userToolResult([
        { tool_use_id: 'call_001', content: { ok: true, result: { t1h: '18.7°C' } } },
      ]),
    ])

    expect(out).toHaveLength(3)
    expect(out[0]?.role).toBe('user')
    expect(out[1]?.role).toBe('assistant')
    expect(out[1]?.tool_calls?.[0]?.id).toBe('call_001')

    // The Lead-Diag-4 critical assertion: tool_result becomes role='tool'.
    expect(out[2]).toEqual({
      role: 'tool',
      name: 'lookup',
      tool_call_id: 'call_001',
      content: JSON.stringify({ ok: true, result: { t1h: '18.7°C' } }),
    })
  })

  test('emits parallel tool_results in arrival order (preserves OpenAI semantics)', () => {
    const out = buildChatMessagesFromTranscript([
      userPrompt('두 가지'),
      assistantToolUse('', [
        { id: 'call_a', name: 'lookup', input: {} },
        { id: 'call_b', name: 'verify', input: {} },
      ]),
      userToolResult([
        { tool_use_id: 'call_a', content: 'result-a' },
        { tool_use_id: 'call_b', content: 'result-b' },
      ]),
    ])

    expect(out).toHaveLength(4) // user + assistant + tool_a + tool_b
    expect(out[2]?.role).toBe('tool')
    expect(out[2]?.tool_call_id).toBe('call_a')
    expect(out[2]?.name).toBe('lookup')
    expect(out[3]?.role).toBe('tool')
    expect(out[3]?.tool_call_id).toBe('call_b')
    expect(out[3]?.name).toBe('verify')
  })

  test('falls back to call_id as name when no prior tool_use is found', () => {
    // Defensive case: the assistant tool_use turn was lost (compaction edge
    // case). The wire validator still requires a non-empty name, so we use
    // the call_id verbatim.
    const out = buildChatMessagesFromTranscript([
      userPrompt('hi'),
      userToolResult([{ tool_use_id: 'orphan_call_xyz', content: 'data' }]),
    ])
    expect(out[1]).toEqual({
      role: 'tool',
      name: 'orphan_call_xyz',
      tool_call_id: 'orphan_call_xyz',
      content: 'data',
    })
  })

  test('skips tool_result blocks with empty tool_use_id', () => {
    const out = buildChatMessagesFromTranscript([
      userToolResult([{ tool_use_id: '', content: 'data' }]),
    ])
    expect(out).toEqual([{ role: 'user', content: '' }])
  })

  test('full round-trip — multi-turn lookup → tool_result → next-user-turn', () => {
    // The end-to-end shape that K-EXAONE MUST receive across two turns.
    // Turn 1: user asks; assistant calls lookup; user/tool returns result.
    // Turn 2: user asks a SECOND question — the spec-multi-turn-contamination
    // bug is that K-EXAONE reasoned over turn-1 state because the wire
    // collapsed the tool_result envelope into a role='user' JSON blob,
    // causing tail-attention to anchor on the 12 KB tool result instead of
    // turn 2's actual prompt.
    const out = buildChatMessagesFromTranscript([
      userPrompt('강남역 근처 내과 알려줘'),
      assistantToolUse('', [
        {
          id: 'call_lookup_1',
          name: 'lookup',
          input: { mode: 'search', q: '강남역 내과' },
        },
      ]),
      userToolResult([
        {
          tool_use_id: 'call_lookup_1',
          content: { results: ['Hospital A', 'Hospital B'] },
        },
      ]),
      userPrompt('재난 알림 구독해줘'),
    ])

    // OpenAI Chat Completions spec ordering:
    //   user → assistant(tool_calls) → tool → user
    // Tail message MUST be the second user prompt — anchoring K-EXAONE's
    // attention on it, not on the tool_result blob.
    expect(out).toHaveLength(4)
    expect(out[0]).toEqual({ role: 'user', content: '강남역 근처 내과 알려줘' })
    expect(out[1]?.role).toBe('assistant')
    expect(out[1]?.tool_calls?.[0]?.id).toBe('call_lookup_1')
    expect(out[2]).toEqual({
      role: 'tool',
      name: 'lookup',
      tool_call_id: 'call_lookup_1',
      content: JSON.stringify({ results: ['Hospital A', 'Hospital B'] }),
    })
    expect(out[3]).toEqual({ role: 'user', content: '재난 알림 구독해줘' })
  })

  test('handles user message with mixed tool_result + text blocks', () => {
    // Edge case: a user message containing both a tool_result and a free-text
    // block (rare but valid in CC). OpenAI spec requires tool messages to
    // appear AFTER the assistant tool_calls turn that produced them, and the
    // user's free-text becomes a separate user message.
    const out = buildChatMessagesFromTranscript([
      assistantToolUse('', [{ id: 'call_x', name: 'lookup', input: {} }]),
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            { type: 'tool_result', tool_use_id: 'call_x', content: 'data' },
            { type: 'text', text: '추가로 한 가지 더' },
          ],
        },
      },
    ])

    expect(out).toHaveLength(3)
    expect(out[0]?.role).toBe('assistant')
    expect(out[1]?.role).toBe('tool')
    expect(out[1]?.tool_call_id).toBe('call_x')
    expect(out[2]).toEqual({ role: 'user', content: '추가로 한 가지 더' })
  })

  test('serialises non-string tool_result content as JSON', () => {
    const out = buildChatMessagesFromTranscript([
      assistantToolUse('', [{ id: 'c', name: 't', input: {} }]),
      userToolResult([{ tool_use_id: 'c', content: { nested: { foo: 'bar' } } }]),
    ])
    expect(out[1]?.content).toBe('{"nested":{"foo":"bar"}}')
  })
})

// ---------------------------------------------------------------------------
// Test 4 — pure helper contracts
// ---------------------------------------------------------------------------

describe('extractTextFromContent', () => {
  test('returns string verbatim', () => {
    expect(extractTextFromContent('hello')).toBe('hello')
  })

  test('joins text blocks with newlines', () => {
    expect(
      extractTextFromContent([
        { type: 'text', text: 'one' },
        { type: 'text', text: 'two' },
      ]),
    ).toBe('one\ntwo')
  })

  test('returns empty string for unknown shapes', () => {
    expect(extractTextFromContent(undefined)).toBe('')
    expect(extractTextFromContent(123)).toBe('')
    expect(extractTextFromContent({})).toBe('')
  })

  test('tolerates legacy {type:text, content:...} fixtures', () => {
    expect(extractTextFromContent([{ type: 'text', content: 'legacy' }])).toBe(
      'legacy',
    )
  })
})

describe('serializeToolResultContent', () => {
  test('returns string verbatim', () => {
    expect(serializeToolResultContent('plain')).toBe('plain')
  })

  test('returns empty for null/undefined', () => {
    expect(serializeToolResultContent(null)).toBe('')
    expect(serializeToolResultContent(undefined)).toBe('')
  })

  test('JSON-encodes objects', () => {
    expect(serializeToolResultContent({ a: 1 })).toBe('{"a":1}')
  })
})

describe('serializeToolUseInput', () => {
  test('returns string verbatim', () => {
    expect(serializeToolUseInput('{"raw":1}')).toBe('{"raw":1}')
  })

  test('returns "{}" for null/undefined', () => {
    expect(serializeToolUseInput(null)).toBe('{}')
    expect(serializeToolUseInput(undefined)).toBe('{}')
  })

  test('JSON-encodes objects', () => {
    expect(serializeToolUseInput({ q: 'hi' })).toBe('{"q":"hi"}')
  })
})

describe('findToolNameForResult', () => {
  test('returns null for empty id', () => {
    expect(findToolNameForResult('', [])).toBeNull()
  })

  test('returns null when no assistant message has matching id', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'hi' },
      {
        role: 'assistant',
        content: '',
        tool_calls: [
          { id: 'call_other', type: 'function', function: { name: 'verify', arguments: '{}' } },
        ],
      },
    ]
    expect(findToolNameForResult('call_xxx', messages)).toBeNull()
  })

  test('returns name from matching assistant tool_calls entry', () => {
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        content: '',
        tool_calls: [
          { id: 'call_a', type: 'function', function: { name: 'lookup', arguments: '{}' } },
          { id: 'call_b', type: 'function', function: { name: 'verify', arguments: '{}' } },
        ],
      },
    ]
    expect(findToolNameForResult('call_a', messages)).toBe('lookup')
    expect(findToolNameForResult('call_b', messages)).toBe('verify')
  })

  test('walks BACKWARDS — most recent matching assistant turn wins', () => {
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        content: '',
        tool_calls: [
          { id: 'dup', type: 'function', function: { name: 'first', arguments: '{}' } },
        ],
      },
      { role: 'tool', name: 'first', tool_call_id: 'dup', content: 'r1' },
      { role: 'user', content: 'again' },
      {
        role: 'assistant',
        content: '',
        tool_calls: [
          { id: 'dup', type: 'function', function: { name: 'second', arguments: '{}' } },
        ],
      },
    ]
    // Ambiguous case: walking backwards, the SECOND assistant turn (with
    // the same id) wins. Real KOSMOS turns generate unique UUIDs so this
    // is a defensive contract test rather than a real-world scenario.
    expect(findToolNameForResult('dup', messages)).toBe('second')
  })
})
