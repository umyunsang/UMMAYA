import { afterEach, beforeEach, describe, expect, mock, test } from 'bun:test'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { CanUseToolFn } from '../../src/hooks/useCanUseTool.js'
import type { AdapterManifestSyncFrame } from '../../src/ipc/frames.generated.js'
import type { DispatchPrimitiveOpts } from '../../src/tools/_shared/dispatchPrimitive.js'
import type { AssistantMessage, Message, UserMessage } from '../../src/types/message.js'
import type { ToolUseContext, Tools } from '../../src/Tool.js'
import { getDefaultAppState, type AppState } from '../../src/state/AppStateStore.js'
import { createFileStateCacheWithSizeLimit, READ_FILE_STATE_CACHE_SIZE } from '../../src/utils/fileStateCache.js'

type DispatchObservation = {
  readonly primitive: DispatchPrimitiveOpts['primitive']
  readonly toolName: string | undefined
  readonly args: Record<string, unknown>
}

const testDir = dirname(fileURLToPath(import.meta.url))
const tuiRoot = join(testDir, '../..')
const dispatchObservations: DispatchObservation[] = []

const dispatchPrimitiveMock = mock(
  async (opts: DispatchPrimitiveOpts) => {
    dispatchObservations.push({
      primitive: opts.primitive,
      toolName: opts.toolName,
      args: opts.args,
    })
    if (
      opts.toolName === 'kakao_keyword_search' &&
      opts.args.query === '다대포해수욕장'
    ) {
      return {
        data: {
          ok: true,
          result: {
            kind: 'poi',
            name: '다대포해수욕장',
            lat: 35.0465263488422,
            lon: 128.962741189119,
            source: 'kakao',
          },
        },
      }
    }
    return {
      data: {
        ok: true,
        invoked_tool_name: opts.toolName,
        args: opts.args,
      },
    }
  },
)

await mock.module(join(tuiRoot, 'src/tools/_shared/dispatchPrimitive.js'), () => ({
  dispatchPrimitive: dispatchPrimitiveMock,
}))

await mock.module(join(tuiRoot, 'src/ipc/bridgeSingleton.js'), () => ({
  getOrCreateUmmayaBridge: () => ({
    send: () => true,
    async *frames() {},
    close: async () => {},
    onFrame: undefined,
    applied_frame_seqs: new Set<string>(),
    setSessionCredentials: () => {},
    lastSeenCorrelationId: null,
    lastSeenFrameSeq: null,
    signalDrop: () => {},
  }),
  getUmmayaBridgeSessionId: () => 'test-session',
}))

const { clearManifestCache, ingestManifestFrame } = await import(
  '../../src/services/api/adapterManifest.js'
)
const { runToolUseBlocks } = await import('../../src/query/toolRunner.js')
const { getAdapterToolByName } = await import(
  '../../src/tools/AdapterTool/AdapterTool.js'
)
const { getAllBaseTools } = await import('../../src/tools.js')
const { createAssistantMessage, createUserMessage } = await import(
  '../../src/utils/messages.js'
)
const { RAW_JSON_UNREGISTERED_TOOL_USE_ID_PREFIX } = await import(
  '../../src/utils/rawJsonToolCall.js'
)

const TAX_TOOL_NAME = 'mock_lookup_module_hometax_simplified'
const VERIFY_TOOL_NAME = 'mock_verify_module_modid'
const MOJ_TOOL_NAME = 'moj_village_lawyer_lookup'
const TAGO_ROUTE_TOOL_NAME = 'tago_bus_route_search'
const TAGO_ROUTE_STATION_TOOL_NAME = 'tago_bus_route_station_search'
const NMC_AED_TOOL_NAME = 'nmc_aed_site_locate'
const ROOT_FIND_TOOL = getAllBaseTools().find(tool => tool.name === 'find')

if (!ROOT_FIND_TOOL) {
  throw new Error('Expected root find tool to be available in base tools.')
}

function makeTaxManifestFrame(): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9TX',
    ts: new Date('2026-06-15T00:00:00.000Z').toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: TAX_TOOL_NAME,
        name: 'Mock Hometax simplified lookup',
        primitive: 'find',
        policy_authority_url: 'https://www.hometax.go.kr/',
        source_mode: 'mock',
        search_hint: '홈택스 종합소득세 소득세 신고 환급 환급계좌 국세청',
        llm_description: 'Mock Hometax income-tax lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            year: { type: 'integer' },
            resident_id_prefix: { type: 'string' },
          },
          required: ['year', 'resident_id_prefix'],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'c'.repeat(64),
    emitter_pid: 12345,
  }
}

function makeVerifyManifestFrame(): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9TY',
    ts: new Date('2026-06-15T00:00:00.000Z').toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: VERIFY_TOOL_NAME,
        name: 'Mock mobile ID verification',
        primitive: 'check',
        policy_authority_url: 'https://www.mois.go.kr/',
        source_mode: 'mock',
        search_hint: '모바일 신분증 모바일ID 본인확인 인증',
        llm_description: 'Mock mobile ID verification adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            scope_list: {
              type: 'array',
              items: { type: 'string' },
            },
            purpose_ko: { type: 'string' },
          },
          required: ['scope_list'],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'd'.repeat(64),
    emitter_pid: 12345,
  }
}

function makeNmcAedManifestFrame(): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9NMC',
    ts: new Date('2026-06-15T00:00:00.000Z').toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: NMC_AED_TOOL_NAME,
        name: 'NMC AED site locate',
        primitive: 'find',
        policy_authority_url: 'https://www.e-gen.or.kr/',
        source_mode: 'live',
        search_hint: 'AED 자동심장충격기 제세동기 응급의료 사하구 다대포',
        llm_description: 'Locate AED sites from the NMC official service.',
        input_schema_json: {
          type: 'object',
          properties: {
            q0: { type: 'string' },
            q1: { type: 'string' },
            origin_lat: { type: 'number' },
            origin_lon: { type: 'number' },
          },
          required: ['q0', 'q1'],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'd'.repeat(64),
    emitter_pid: 12345,
  }
}

function makeKakaoKeywordManifestFrame(): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9KAK',
    ts: new Date('2026-06-15T00:00:00.000Z').toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kakao_keyword_search',
        name: 'Kakao keyword search',
        primitive: 'find',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '카카오 키워드 위치 검색 다대포 해수욕장 AED',
        llm_description: 'Kakao keyword location search adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            query: { type: 'string' },
          },
          required: ['query'],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'k'.repeat(64),
    emitter_pid: 12345,
  }
}

function makeNmcAedAndKakaoManifestFrame(): AdapterManifestSyncFrame {
  const nmcFrame = makeNmcAedManifestFrame()
  const kakaoFrame = makeKakaoKeywordManifestFrame()
  return {
    ...nmcFrame,
    entries: [...nmcFrame.entries, ...kakaoFrame.entries],
    manifest_hash: 'f'.repeat(64),
  }
}

function makeTaxAndVerifyManifestFrame(): AdapterManifestSyncFrame {
  const taxFrame = makeTaxManifestFrame()
  const verifyFrame = makeVerifyManifestFrame()
  return {
    ...taxFrame,
    entries: [...taxFrame.entries, ...verifyFrame.entries],
    manifest_hash: 'e'.repeat(64),
  }
}

function makeMojManifestFrame(): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9TZ',
    ts: new Date('2026-06-15T00:00:00.000Z').toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: MOJ_TOOL_NAME,
        name: 'MOJ village lawyer lookup',
        primitive: 'find',
        policy_authority_url: 'https://www.data.go.kr/data/15121954/openapi.do',
        source_mode: 'live',
        search_hint: '법무부 마을변호사 지역별 현황 부산 사하구',
        llm_description: 'Search official MOJ village lawyer regional assignment rows.',
        input_schema_json: {
          type: 'object',
          properties: {
            page_no: {
              type: 'integer',
              default: 1,
            },
            num_of_rows: {
              type: 'integer',
              default: 20,
            },
            state: {
              anyOf: [{ type: 'string', minLength: 1 }, { type: 'null' }],
              default: null,
            },
            city: {
              anyOf: [{ type: 'string', minLength: 1 }, { type: 'null' }],
              default: null,
            },
            village: {
              anyOf: [{ type: 'string', minLength: 1 }, { type: 'null' }],
              default: null,
            },
          },
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'f'.repeat(64),
    emitter_pid: 12345,
  }
}

function makeTagoManifestFrame(): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9TA',
    ts: new Date('2026-06-15T00:00:00.000Z').toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: TAGO_ROUTE_TOOL_NAME,
        name: 'TAGO bus route lookup',
        primitive: 'find',
        policy_authority_url: 'https://www.data.go.kr/data/15098529/openapi.do',
        source_mode: 'live',
        search_hint: 'TAGO 버스노선 cityCode routeNo',
        llm_description: 'Search official TAGO bus route data by city_code and route_no.',
        input_schema_json: {
          type: 'object',
          properties: {
            city_code: { type: 'string' },
            route_no: { type: 'string' },
          },
          required: ['city_code', 'route_no'],
          additionalProperties: false,
        },
      },
      {
        tool_id: TAGO_ROUTE_STATION_TOOL_NAME,
        name: 'TAGO bus route-station lookup',
        primitive: 'find',
        policy_authority_url: 'https://www.data.go.kr/data/15098529/openapi.do',
        source_mode: 'live',
        search_hint: 'TAGO 노선별 경유정류소 routeId nodenm',
        llm_description: 'Search official TAGO route-station data by city_code and route_id.',
        input_schema_json: {
          type: 'object',
          properties: {
            city_code: { type: 'string' },
            route_id: { type: 'string' },
            node_nm: {
              anyOf: [{ type: 'string', minLength: 1 }, { type: 'null' }],
              default: null,
            },
            updown_cd: {
              anyOf: [{ type: 'string', minLength: 1 }, { type: 'null' }],
              default: null,
            },
          },
          required: ['city_code', 'route_id'],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'a'.repeat(64),
    emitter_pid: 12345,
  }
}

function requireAdapterTool(name: string) {
  const tool = getAdapterToolByName(name)
  if (tool === undefined) {
    throw new Error(`Expected ${name} to be present in the test manifest.`)
  }
  return tool
}

function makeToolUseContext(tools: Tools, messages: readonly Message[]): ToolUseContext {
  let appState: AppState = getDefaultAppState()
  return {
    options: {
      commands: [],
      debug: false,
      mainLoopModel: 'test-model',
      tools,
      verbose: false,
      thinkingConfig: { type: 'disabled' },
      mcpClients: [],
      mcpResources: {},
      isNonInteractiveSession: false,
      agentDefinitions: { activeAgents: [], allAgents: [], allowedAgentTypes: [] },
    },
    abortController: new AbortController(),
    readFileState: createFileStateCacheWithSizeLimit(READ_FILE_STATE_CACHE_SIZE),
    getAppState: () => appState,
    setAppState: update => {
      appState = update(appState)
    },
    setInProgressToolUseIDs: () => {},
    setResponseLength: () => {},
    updateFileHistoryState: () => {},
    updateAttributionState: () => {},
    messages: [...messages],
  } satisfies ToolUseContext
}

const allowTool: CanUseToolFn = async (_tool, input) => ({
  behavior: 'allow',
  updatedInput: input,
})

const denyTool: CanUseToolFn = async () => ({
  behavior: 'deny',
  message: 'permission_denied: test citizen denied protected adapter execution',
  decisionReason: {
    type: 'other',
    reason: 'test-denied',
  },
})

function toolResultText(messages: readonly UserMessage[]): string {
  return messages
    .flatMap(message => {
      const content = message.message.content
      if (!Array.isArray(content)) return []
      return content.flatMap(block => {
        if (
          typeof block !== 'object' ||
          block === null ||
          !('type' in block) ||
          block.type !== 'tool_result' ||
          !('content' in block)
        ) {
          return []
        }
        return typeof block.content === 'string' ? [block.content] : []
      })
    })
    .join('\n')
}

describe('query runner adapter tool resolution', () => {
  beforeEach(() => {
    clearManifestCache()
    dispatchObservations.length = 0
    dispatchPrimitiveMock.mockClear()
  })

  afterEach(() => {
    clearManifestCache()
    dispatchObservations.length = 0
    dispatchPrimitiveMock.mockClear()
  })

  test('resolves manifest-backed TAX adapter when execution tool snapshot is stale', async () => {
    ingestManifestFrame(makeTaxManifestFrame())
    const priorMessages = [
      createUserMessage({
        content: '종합소득세 환급 계좌 상태를 홈택스에서 확인해줘.',
      }),
    ]
    const block = {
      type: 'tool_use',
      id: 'toolu-tax001-execution',
      name: TAX_TOOL_NAME,
      input: {
        year: 2025,
        resident_id_prefix: '900101',
      },
    }
    const assistantMessage: AssistantMessage = createAssistantMessage({
      content: [block],
    })

    const results = await runToolUseBlocks({
      blocks: [block],
      assistantMessage,
      messages: [...priorMessages, assistantMessage],
      toolUseContext: makeToolUseContext([], priorMessages),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).not.toContain('tool_unavailable')
    expect(dispatchPrimitiveMock).toHaveBeenCalledTimes(1)
    expect(dispatchObservations).toEqual([
      {
        primitive: 'find',
        toolName: TAX_TOOL_NAME,
        args: {
          year: 2025,
          resident_id_prefix: '900101',
        },
      },
    ])
    expect(toolResultText(results)).toContain(`"invoked_tool_name":"${TAX_TOOL_NAME}"`)
  })

  test('keeps fail-closed unavailable result when missing from execution snapshot and manifest', async () => {
    ingestManifestFrame(makeTaxManifestFrame())
    const missingName = 'mock_lookup_module_hometax_not_in_manifest'
    const block = {
      type: 'tool_use',
      id: 'toolu-tax001-missing',
      name: missingName,
      input: {},
    }
    const assistantMessage: AssistantMessage = createAssistantMessage({
      content: [block],
    })

    const results = await runToolUseBlocks({
      blocks: [block],
      assistantMessage,
      messages: [assistantMessage],
      toolUseContext: makeToolUseContext([], []),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).toContain('"code":"tool_unavailable"')
    expect(toolResultText(results)).toContain(`"tool_name":"${missingName}"`)
    expect(dispatchPrimitiveMock).not.toHaveBeenCalled()
  })

  test('keeps fail-closed unavailable result when manifest adapter is outside the selected execution surface', async () => {
    ingestManifestFrame(makeTaxAndVerifyManifestFrame())
    const priorMessages = [
      createUserMessage({
        content: '모바일 신분증으로 본인확인만 진행해줘.',
      }),
    ]
    const block = {
      type: 'tool_use',
      id: `${RAW_JSON_UNREGISTERED_TOOL_USE_ID_PREFIX}0`,
      name: TAX_TOOL_NAME,
      input: {
        year: 2025,
        resident_id_prefix: '900101',
      },
    }
    const assistantMessage: AssistantMessage = createAssistantMessage({
      content: [block],
    })

    const results = await runToolUseBlocks({
      blocks: [block],
      assistantMessage,
      messages: [...priorMessages, assistantMessage],
      toolUseContext: makeToolUseContext(
        [requireAdapterTool(VERIFY_TOOL_NAME)],
        priorMessages,
      ),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).toContain('"code":"tool_unavailable"')
    expect(toolResultText(results)).toContain(`"tool_name":"${TAX_TOOL_NAME}"`)
    expect(dispatchPrimitiveMock).not.toHaveBeenCalled()
  })

  test('blocks manifest-backed protected adapter dispatch when permission is denied', async () => {
    ingestManifestFrame(makeVerifyManifestFrame())
    const priorMessages = [
      createUserMessage({
        content: '모바일 신분증으로 본인확인해줘.',
      }),
    ]
    const block = {
      type: 'tool_use',
      id: 'toolu-id001-protected-denied',
      name: VERIFY_TOOL_NAME,
      input: {
        scope_list: ['check:modid.identity'],
        purpose_ko: '모바일 신분증 본인확인',
      },
    }
    const assistantMessage: AssistantMessage = createAssistantMessage({
      content: [block],
    })

    const results = await runToolUseBlocks({
      blocks: [block],
      assistantMessage,
      messages: [...priorMessages, assistantMessage],
      toolUseContext: makeToolUseContext([], priorMessages),
      canUseTool: denyTool,
    })

    expect(toolResultText(results)).toContain('permission_denied')
    expect(dispatchPrimitiveMock).not.toHaveBeenCalled()
  })

  test('accepts Pydantic nullable default optional fields from adapter manifest', async () => {
    ingestManifestFrame(makeMojManifestFrame())
    const priorMessages = [
      createUserMessage({
        content: '부산 사하구 마을변호사를 법무부 공식 도구로 찾아줘.',
      }),
    ]
    const block = {
      type: 'tool_use',
      id: 'toolu-moj-optional-village',
      name: MOJ_TOOL_NAME,
      input: {
        state: '부산',
        city: '사하구',
      },
    }
    const assistantMessage: AssistantMessage = createAssistantMessage({
      content: [block],
    })

    const results = await runToolUseBlocks({
      blocks: [block],
      assistantMessage,
      messages: [...priorMessages, assistantMessage],
      toolUseContext: makeToolUseContext([], priorMessages),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).not.toContain('InputValidationError')
    expect(dispatchPrimitiveMock).toHaveBeenCalledTimes(1)
    expect(dispatchObservations).toEqual([
      {
        primitive: 'find',
        toolName: MOJ_TOOL_NAME,
        args: {
          page_no: 1,
          num_of_rows: 20,
          state: '부산',
          city: '사하구',
          village: null,
        },
      },
    ])
  })

  test('backfills MOJ village lawyer region from citizen text on root find calls', async () => {
    ingestManifestFrame(makeMojManifestFrame())
    const priorMessages = [
      createUserMessage({
        content:
          '날씨로 대체하지 마. 부산 사하구 마을변호사 정보를 법무부 자료로 확인해줘',
      }),
    ]
    const block = {
      type: 'tool_use',
      id: 'toolu-moj-root-find-region-backfill',
      name: 'find',
      input: {
        tool_id: MOJ_TOOL_NAME,
        params: {},
      },
    }
    const assistantMessage: AssistantMessage = createAssistantMessage({
      content: [block],
    })

    const results = await runToolUseBlocks({
      blocks: [block],
      assistantMessage,
      messages: [...priorMessages, assistantMessage],
      toolUseContext: makeToolUseContext([ROOT_FIND_TOOL], priorMessages),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).not.toContain('InputValidationError')
    expect(dispatchPrimitiveMock).toHaveBeenCalledTimes(1)
    expect(dispatchObservations).toEqual([
      {
        primitive: 'find',
        toolName: undefined,
        args: {
          tool_id: MOJ_TOOL_NAME,
          params: {
            state: '부산',
            city: '사하구',
          },
        },
      },
    ])
  })

  test('blocks TAGO route substitution after official zero-result evidence', async () => {
    ingestManifestFrame(makeTagoManifestFrame())
    const citizenPrompt = createUserMessage({
      content: '부산 1001번 버스 노선과 정류장, 도착정보를 TAGO 공식 도구로 찾아줘.',
    })
    const zeroRouteBlock = {
      type: 'tool_use',
      id: 'toolu-tago-zero-route',
      name: TAGO_ROUTE_TOOL_NAME,
      input: {
        city_code: '21',
        route_no: '1001',
      },
    }
    const zeroRouteAssistant = createAssistantMessage({
      content: [zeroRouteBlock],
    })
    const zeroRouteResult = createUserMessage({
      content: [
        {
          type: 'tool_result',
          tool_use_id: zeroRouteBlock.id,
          content: JSON.stringify({
            ok: true,
            result: {
              kind: 'collection',
              items: [],
              total_count: 0,
            },
          }),
        },
      ],
      toolUseResult: {
        ok: true,
        result: {
          kind: 'collection',
          items: [],
          total_count: 0,
        },
      },
      sourceToolAssistantUUID: zeroRouteAssistant.uuid,
    })
    const substituteBlock = {
      type: 'tool_use',
      id: 'toolu-tago-substitute-route',
      name: TAGO_ROUTE_TOOL_NAME,
      input: {
        city_code: '21',
        route_no: '141',
      },
    }
    const substituteAssistant: AssistantMessage = createAssistantMessage({
      content: [substituteBlock],
    })

    const results = await runToolUseBlocks({
      blocks: [substituteBlock],
      assistantMessage: substituteAssistant,
      messages: [
        citizenPrompt,
        zeroRouteAssistant,
        zeroRouteResult,
        substituteAssistant,
      ],
      toolUseContext: makeToolUseContext([], [citizenPrompt]),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).toContain('TAGO route lookup already returned zero official rows')
    expect(toolResultText(results)).toContain('route_no=1001')
    expect(toolResultText(results)).toContain('without citizen confirmation')
    expect(results[0]?.message.content[0]?.type).toBe('tool_result')
    expect(results[0]?.message.content[0]?.is_error).not.toBe(true)
    expect(dispatchPrimitiveMock).not.toHaveBeenCalled()
  })

  test('normalizes empty nullable adapter string fields before backend dispatch', async () => {
    ingestManifestFrame(makeTagoManifestFrame())
    const priorMessages = [
      createUserMessage({
        content: '부산 1001번 버스의 전체 경유 정류장을 TAGO 공식 도구로 찾아줘.',
      }),
    ]
    const block = {
      type: 'tool_use',
      id: 'toolu-tago-empty-node-name',
      name: TAGO_ROUTE_STATION_TOOL_NAME,
      input: {
        city_code: '21',
        route_id: 'BSB5201001000',
        node_nm: '',
      },
    }
    const assistantMessage: AssistantMessage = createAssistantMessage({
      content: [block],
    })

    const results = await runToolUseBlocks({
      blocks: [block],
      assistantMessage,
      messages: [...priorMessages, assistantMessage],
      toolUseContext: makeToolUseContext([], priorMessages),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).not.toContain('InputValidationError')
    expect(dispatchPrimitiveMock).toHaveBeenCalledTimes(1)
    expect(dispatchObservations).toEqual([
      {
        primitive: 'find',
        toolName: TAGO_ROUTE_STATION_TOOL_NAME,
        args: {
          city_code: '21',
          route_id: 'BSB5201001000',
          node_nm: null,
          updown_cd: null,
        },
      },
    ])
  })

  test('backfills direct AED concrete calls with prior locate origin coordinates', async () => {
    ingestManifestFrame(makeNmcAedManifestFrame())
    const citizenPrompt = createUserMessage({
      content: '다대포해수욕장 근처 AED 위치를 찾아줘. 가장 가까운 곳부터 알려줘.',
    })
    const locateBlock = {
      type: 'tool_use',
      id: 'toolu-kakao-dadaepo',
      name: 'kakao_keyword_search',
      input: { query: '다대포해수욕장' },
    }
    const locateAssistant = createAssistantMessage({
      content: [locateBlock],
    })
    const locateResult = createUserMessage({
      content: [
        {
          type: 'tool_result',
          tool_use_id: locateBlock.id,
          content: JSON.stringify({
            ok: true,
            result: {
              kind: 'poi',
              name: '다대포해수욕장',
              lat: 35.0465263488422,
              lon: 128.962741189119,
              source: 'kakao',
            },
          }),
        },
      ],
      sourceToolAssistantUUID: locateAssistant.uuid,
    })
    const aedBlock = {
      type: 'tool_use',
      id: 'toolu-nmc-aed-direct',
      name: NMC_AED_TOOL_NAME,
      input: {
        q0: '부산광역시',
        q1: '사하구',
      },
    }
    const aedAssistant: AssistantMessage = createAssistantMessage({
      content: [aedBlock],
    })

    const results = await runToolUseBlocks({
      blocks: [aedBlock],
      assistantMessage: aedAssistant,
      messages: [citizenPrompt, locateAssistant, locateResult, aedAssistant],
      toolUseContext: makeToolUseContext([], [citizenPrompt]),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).not.toContain('InputValidationError')
    expect(dispatchPrimitiveMock).toHaveBeenCalledTimes(1)
    expect(dispatchObservations).toEqual([
      {
        primitive: 'find',
        toolName: NMC_AED_TOOL_NAME,
        args: {
          q0: '부산광역시',
          q1: '사하구',
          origin_lat: 35.0465263488422,
          origin_lon: 128.962741189119,
        },
      },
    ])
  })

  test('replaces rounded direct AED origin with prior precise locate coordinates', async () => {
    ingestManifestFrame(makeNmcAedManifestFrame())
    const citizenPrompt = createUserMessage({
      content: '다대포해수욕장 근처 AED 위치를 찾아줘. 가장 가까운 곳부터 알려줘.',
    })
    const locateBlock = {
      type: 'tool_use',
      id: 'toolu-kakao-dadaepo-rounded',
      name: 'kakao_keyword_search',
      input: { query: '다대포해수욕장' },
    }
    const locateAssistant = createAssistantMessage({
      content: [locateBlock],
    })
    const locateResult = createUserMessage({
      content: [
        {
          type: 'tool_result',
          tool_use_id: locateBlock.id,
          content: JSON.stringify({
            ok: true,
            result: {
              kind: 'poi',
              name: '다대포해수욕장',
              lat: 35.0465263488422,
              lon: 128.962741189119,
              source: 'kakao',
            },
          }),
        },
      ],
      sourceToolAssistantUUID: locateAssistant.uuid,
    })
    const aedBlock = {
      type: 'tool_use',
      id: 'toolu-nmc-aed-rounded',
      name: NMC_AED_TOOL_NAME,
      input: {
        q0: '부산광역시',
        q1: '사하구',
        origin_lat: 35,
        origin_lon: 129,
      },
    }
    const aedAssistant: AssistantMessage = createAssistantMessage({
      content: [aedBlock],
    })

    const results = await runToolUseBlocks({
      blocks: [aedBlock],
      assistantMessage: aedAssistant,
      messages: [citizenPrompt, locateAssistant, locateResult, aedAssistant],
      toolUseContext: makeToolUseContext([], [citizenPrompt]),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).not.toContain('InputValidationError')
    expect(dispatchPrimitiveMock).toHaveBeenCalledTimes(1)
    expect(dispatchObservations).toEqual([
      {
        primitive: 'find',
        toolName: NMC_AED_TOOL_NAME,
        args: {
          q0: '부산광역시',
          q1: '사하구',
          origin_lat: 35.0465263488422,
          origin_lon: 128.962741189119,
        },
      },
    ])
  })

  test('resolves exact AED origin when the model keeps calling NMC directly', async () => {
    ingestManifestFrame(makeNmcAedAndKakaoManifestFrame())
    const citizenPrompt = createUserMessage({
      content: '다대포해수욕장 근처 AED 위치를 찾아줘. 가장 가까운 곳부터 알려줘.',
    })
    const failedAddressBlock = {
      type: 'tool_use',
      id: 'toolu-kakao-address-failed',
      name: 'kakao_address_search',
      input: { query: '부산 사하구 다대포해수욕장' },
    }
    const failedAddressAssistant = createAssistantMessage({
      content: [failedAddressBlock],
    })
    const failedAddressResult = createUserMessage({
      content: [
        {
          type: 'tool_result',
          tool_use_id: failedAddressBlock.id,
          content: JSON.stringify({
            ok: false,
            result: { kind: 'error', reason: 'not_found' },
          }),
          is_error: true,
        },
      ],
      sourceToolAssistantUUID: failedAddressAssistant.uuid,
    })
    const aedBlock = {
      type: 'tool_use',
      id: 'toolu-nmc-aed-without-origin',
      name: NMC_AED_TOOL_NAME,
      input: {
        q0: '부산광역시',
        q1: '사하구',
      },
    }
    const aedAssistant: AssistantMessage = createAssistantMessage({
      content: [aedBlock],
    })

    const results = await runToolUseBlocks({
      blocks: [aedBlock],
      assistantMessage: aedAssistant,
      messages: [
        citizenPrompt,
        failedAddressAssistant,
        failedAddressResult,
        aedAssistant,
      ],
      toolUseContext: makeToolUseContext([], [citizenPrompt]),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).not.toContain('MissingPreciseOrigin')
    expect(dispatchPrimitiveMock).toHaveBeenCalledTimes(2)
    expect(dispatchObservations).toEqual([
      {
        primitive: 'find',
        toolName: 'kakao_keyword_search',
        args: {
          query: '다대포해수욕장',
        },
      },
      {
        primitive: 'find',
        toolName: NMC_AED_TOOL_NAME,
        args: {
          q0: '부산광역시',
          q1: '사하구',
          origin_lat: 35.0465263488422,
          origin_lon: 128.962741189119,
        },
      },
    ])
  })

  test('blocks direct AED distance calls when only generic Kakao origin exists', async () => {
    ingestManifestFrame(makeNmcAedManifestFrame())
    const citizenPrompt = createUserMessage({
      content: '다대포해수욕장 근처 AED 위치를 찾아줘. 가장 가까운 곳부터 알려줘.',
    })
    const locateBlock = {
      type: 'tool_use',
      id: 'toolu-kakao-generic-aed',
      name: 'kakao_keyword_search',
      input: { query: '사하구 AED' },
    }
    const locateAssistant = createAssistantMessage({
      content: [locateBlock],
    })
    const locateResult = createUserMessage({
      content: [
        {
          type: 'tool_result',
          tool_use_id: locateBlock.id,
          content: JSON.stringify({
            ok: true,
            result: {
              kind: 'poi',
              name: '사하구 AED',
              lat: 35.104448,
              lon: 128.974933,
              source: 'kakao',
            },
          }),
        },
      ],
      sourceToolAssistantUUID: locateAssistant.uuid,
    })
    const aedBlock = {
      type: 'tool_use',
      id: 'toolu-nmc-aed-generic',
      name: NMC_AED_TOOL_NAME,
      input: {
        q0: '부산광역시',
        q1: '사하구',
      },
    }
    const aedAssistant: AssistantMessage = createAssistantMessage({
      content: [aedBlock],
    })

    const results = await runToolUseBlocks({
      blocks: [aedBlock],
      assistantMessage: aedAssistant,
      messages: [citizenPrompt, locateAssistant, locateResult, aedAssistant],
      toolUseContext: makeToolUseContext([], [citizenPrompt]),
      canUseTool: allowTool,
    })

    expect(toolResultText(results)).toContain('MissingPreciseOrigin')
    expect(toolResultText(results)).toContain('다대포해수욕장')
    expect(dispatchPrimitiveMock).not.toHaveBeenCalled()
  })
})
