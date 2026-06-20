import { afterEach, beforeEach, describe, expect, test } from 'bun:test'
import type {
  AdapterManifestSyncFrame,
  ChatRequestFrame,
  IPCFrame,
  ToolCallFrame,
  ToolResultFrame,
} from '../../src/ipc/frames.generated.js'
import {
  createHostedGatewayBridge,
  manifestUrlFromAdapterProxyUrl,
  shouldUseHostedGatewayBridge,
} from '../../src/ipc/hostedGatewayBridge.js'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../src/services/api/adapterManifest.js'

const originalFetch = globalThis.fetch
const originalEnv = { ...process.env }

function manifestFrame(): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: '',
    correlation_id: '019eded5-0000-7000-9000-000000000001',
    ts: new Date('2026-06-20T00:00:00.000Z').toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kma_current_observation',
        name: 'KMA current observation',
        primitive: 'find',
        policy_authority_url: 'https://www.data.go.kr/',
        source_mode: 'live',
        search_hint: 'weather observation',
        llm_description: 'Fetch current weather observations.',
        input_schema_json: {
          type: 'object',
          properties: {
            q: { type: 'string' },
          },
          required: ['q'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kakao_keyword_search',
        name: 'Kakao keyword search',
        primitive: 'locate',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: 'place lookup',
        llm_description: 'Resolve a Korean place into WGS-84 coordinates.',
        input_schema_json: {
          type: 'object',
          properties: {
            query: { type: 'string' },
          },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'hira_hospital_search',
        name: 'HIRA hospital search',
        primitive: 'find',
        policy_authority_url: 'https://www.data.go.kr/',
        source_mode: 'live',
        search_hint: 'hospital search',
        llm_description: 'Search Korean hospitals near WGS-84 coordinates.',
        input_schema_json: {
          type: 'object',
          properties: {
            xPos: { type: 'number' },
            yPos: { type: 'number' },
            radius: { type: 'integer' },
            dgsbjt: { type: 'string' },
          },
          required: ['xPos', 'yPos', 'radius'],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'a'.repeat(64),
    emitter_pid: 12345,
  }
}

function toolCallFrame(): ToolCallFrame {
  return {
    kind: 'tool_call',
    version: '1.0',
    session_id: 'session-1',
    correlation_id: '019eded5-0000-7000-9000-000000000002',
    ts: new Date('2026-06-20T00:00:01.000Z').toISOString(),
    role: 'tool',
    frame_seq: 0,
    call_id: 'toolu_1',
    name: 'kma_current_observation',
    arguments: { q: '부산' },
  }
}

function chatRequestFrame(): ChatRequestFrame {
  return {
    kind: 'chat_request',
    version: '1.0',
    session_id: 'session-1',
    correlation_id: '019eded5-0000-7000-9000-000000000099',
    ts: new Date('2026-06-20T00:00:01.000Z').toISOString(),
    role: 'tui',
    frame_seq: 0,
    messages: [
      {
        role: 'user',
        content: '동아대 승학캠퍼스 근처에서 오늘 전화해볼 수 있는 내과 찾아줘',
      },
    ],
  }
}

function kakaoLocateFrame(): ToolCallFrame {
  return {
    kind: 'tool_call',
    version: '1.0',
    session_id: 'session-1',
    correlation_id: '019eded5-0000-7000-9000-000000000003',
    ts: new Date('2026-06-20T00:00:02.000Z').toISOString(),
    role: 'tool',
    frame_seq: 0,
    call_id: 'toolu_locate',
    name: 'kakao_keyword_search',
    arguments: { query: '동아대학교 승학캠퍼스' },
  }
}

function roundedHiraFrame(): ToolCallFrame {
  return {
    kind: 'tool_call',
    version: '1.0',
    session_id: 'session-1',
    correlation_id: '019eded5-0000-7000-9000-000000000004',
    ts: new Date('2026-06-20T00:00:03.000Z').toISOString(),
    role: 'tool',
    frame_seq: 0,
    call_id: 'toolu_hira',
    name: 'hira_hospital_search',
    arguments: { xPos: 128, yPos: 35, radius: 2000, dgsbjt: '내과' },
  }
}

function nextFrameOfKind<T extends IPCFrame['kind']>(
  iterator: AsyncIterator<IPCFrame>,
  kind: T,
): Promise<Extract<IPCFrame, { kind?: T }>> {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      for (let index = 0; index < 5; index += 1) {
        const next = await iterator.next()
        if (next.done) break
        if (next.value.kind === kind) {
          resolve(next.value as Extract<IPCFrame, { kind?: T }>)
          return
        }
      }
      reject(new Error(`Frame ${kind} did not arrive.`))
    }
    void poll()
  })
}

describe('hosted gateway bridge', () => {
  beforeEach(() => {
    clearManifestCache()
    process.env = { ...originalEnv }
    process.env.UMMAYA_LIVE_ADAPTER_PROXY_URL = 'https://gateway.example/v1/adapters'
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    process.env = { ...originalEnv }
    clearManifestCache()
  })

  test('derives the manifest URL from the adapter endpoint', () => {
    expect(manifestUrlFromAdapterProxyUrl('https://gateway.example/v1/adapters')).toBe(
      'https://gateway.example/v1/manifest',
    )
  })

  test('uses hosted transport for packaged executions', () => {
    process.env.UMMAYA_PACKAGE_ROOT = '/tmp/package'
    delete process.env.UMMAYA_BACKEND_TRANSPORT
    expect(shouldUseHostedGatewayBridge()).toBe(true)
    process.env.UMMAYA_BACKEND_TRANSPORT = 'stdio'
    expect(shouldUseHostedGatewayBridge()).toBe(false)
  })

  test('fetches manifest and posts tool calls without client gateway secrets', async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = []
    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      requests.push({ url, init })
      if (url === 'https://gateway.example/v1/manifest') {
        return Response.json(manifestFrame())
      }
      if (url === 'https://gateway.example/v1/adapters/kma_current_observation') {
        return Response.json({
          ok: true,
          result: {
            kind: 'record',
            item: { value: 'live:부산' },
          },
        })
      }
      return Response.json({ detail: 'unexpected' }, { status: 404 })
    }

    const bridge = createHostedGatewayBridge({ sessionId: 'session-1' })
    const iterator = bridge.frames()[Symbol.asyncIterator]()
    ingestManifestFrame(await nextFrameOfKind(iterator, 'adapter_manifest_sync'))

    expect(bridge.send(toolCallFrame())).toBe(true)
    const result = await nextFrameOfKind(iterator, 'tool_result') as ToolResultFrame

    expect(result.call_id).toBe('toolu_1')
    expect(result.envelope.kind).toBe('find')
    expect((result.envelope as Record<string, unknown>).result).toEqual({
      kind: 'record',
      item: { value: 'live:부산' },
    })
    const post = requests.find((request) =>
      request.url.endsWith('/v1/adapters/kma_current_observation'),
    )
    expect(post).toBeDefined()
    expect(post?.init?.headers).not.toHaveProperty('authorization')
    expect(JSON.parse(String(post?.init?.body))).toEqual({
      schema_version: 'ummaya.live_adapter.v1',
      tool_id: 'kma_current_observation',
      primitive: 'find',
      request_id: 'toolu_1',
      params: { q: '부산' },
      session_identity: 'session-1',
    })
    await bridge.close()
  })

  test('repairs HIRA concrete calls with cached locate coordinates before gateway dispatch', async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = []
    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      requests.push({ url, init })
      if (url === 'https://gateway.example/v1/manifest') {
        return Response.json(manifestFrame())
      }
      if (url === 'https://gateway.example/v1/adapters/kakao_keyword_search') {
        return Response.json({
          ok: true,
          result: {
            kind: 'poi',
            name: '동아대학교 승학캠퍼스',
            lat: 35.11544607253305,
            lon: 128.96766921590506,
            source: 'kakao',
          },
        })
      }
      if (url === 'https://gateway.example/v1/adapters/hira_hospital_search') {
        return Response.json({
          ok: true,
          result: {
            kind: 'collection',
            items: [
              {
                yadmNm: '부산내과의원',
              },
            ],
          },
        })
      }
      return Response.json({ detail: 'unexpected' }, { status: 404 })
    }

    const bridge = createHostedGatewayBridge({ sessionId: 'session-1' })
    const iterator = bridge.frames()[Symbol.asyncIterator]()
    ingestManifestFrame(await nextFrameOfKind(iterator, 'adapter_manifest_sync'))

    expect(bridge.send(chatRequestFrame())).toBe(true)
    expect(bridge.send(kakaoLocateFrame())).toBe(true)
    await nextFrameOfKind(iterator, 'tool_result')
    expect(bridge.send(roundedHiraFrame())).toBe(true)
    const result = await nextFrameOfKind(iterator, 'tool_result') as ToolResultFrame

    expect(result.call_id).toBe('toolu_hira')
    const hiraPost = requests.find((request) =>
      request.url.endsWith('/v1/adapters/hira_hospital_search'),
    )
    expect(hiraPost).toBeDefined()
    expect(JSON.parse(String(hiraPost?.init?.body))).toEqual({
      schema_version: 'ummaya.live_adapter.v1',
      tool_id: 'hira_hospital_search',
      primitive: 'find',
      request_id: 'toolu_hira',
      params: {
        xPos: 128.96766921590506,
        yPos: 35.11544607253305,
        radius: 2000,
        dgsbjt: '내과',
      },
      session_identity: 'session-1',
    })
    await bridge.close()
  })
})
