import { describe, expect, test } from 'bun:test'
import { buildTool, getEmptyToolPermissionContext } from '../../src/Tool.js'
import { assembleToolPool, getTools } from '../../src/tools.js'
import { z } from 'zod/v4'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../src/services/api/adapterManifest.js'
import type { AdapterManifestSyncFrame } from '../../src/ipc/frames.generated.js'
import { isDeferredTool } from '../../src/tools/ToolSearchTool/prompt.js'
import { ToolSearchTool } from '../../src/tools/ToolSearchTool/ToolSearchTool.js'
import {
  isRootPrimitiveToolName,
  selectTopKAdapterToolNamesForQuery,
} from '../../src/tools/AdapterTool/AdapterTool.js'
import {
  DESCRIPTION as FIND_DESCRIPTION,
  FIND_TOOL_PROMPT,
} from '../../src/tools/LookupPrimitive/prompt.js'
import {
  DESCRIPTION as LOCATE_DESCRIPTION,
  LOCATE_TOOL_PROMPT,
} from '../../src/tools/ResolveLocationPrimitive/prompt.js'
import { SEND_TOOL_PROMPT } from '../../src/tools/SubmitPrimitive/prompt.js'
import { CHECK_TOOL_PROMPT } from '../../src/tools/VerifyPrimitive/prompt.js'

const context7Tool = buildTool({
  name: 'mcp__context7__resolve-library-id',
  inputSchema: z.object({ libraryName: z.string() }),
  isEnabled: () => true,
  isReadOnly: () => true,
  isConcurrencySafe: () => true,
  description: async () => 'Context7 resolver',
  prompt: async () => 'Resolve documentation libraries',
  validateInput: async () => ({ result: true }),
  call: async () => ({ data: {} }),
  userFacingName: () => 'context7',
  mapToolResultToToolResultBlockParam: (data, toolUseID) => ({
    type: 'tool_result',
    tool_use_id: toolUseID,
    content: JSON.stringify(data),
  }),
  renderToolUseMessage: () => null,
  mcpInfo: { serverName: 'context7', toolName: 'resolve-library-id' },
})

describe('UMMAYA model-facing tool surface', () => {
  test('exposes public-service primitives, not Claude Code developer tools', () => {
    const names = getTools(getEmptyToolPermissionContext()).map(tool => tool.name)

    expect(names).toEqual(
      expect.arrayContaining(['ToolSearch', 'find', 'locate', 'send', 'check']),
    )
    expect(names).not.toContain('Bash')
    expect(names).not.toContain('Read')
    expect(names).not.toContain('Write')
    expect(names).not.toContain('Edit')
    expect(names).not.toContain('Glob')
    expect(names).not.toContain('Grep')
    expect(names).not.toContain('NotebookEdit')
  })

  test('keeps CC assembly shape while external MCP tools stay out of citizen turns', () => {
    clearManifestCache()
    const names = assembleToolPool(getEmptyToolPermissionContext(), [
      context7Tool,
    ]).map(tool => tool.name)

    expect(names).toEqual(['check', 'find', 'locate', 'send', 'ToolSearch'])
    expect(names).not.toContain('mcp__context7__resolve-library-id')
  })

  test('loads synced backend adapters as deferred CC Tool objects', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C1',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kma_current_observation',
          name: 'KMA Current Observation',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'KMA current weather observation getUltraSrtNcst',
          llm_description:
            'KMA APIHub current weather observation adapter. Use latitude-derived KMA grid values from locate before calling this tool.',
          input_schema_json: {
            type: 'object',
            properties: {
              nx: { type: 'integer', description: 'KMA grid X coordinate.' },
              ny: { type: 'integer', description: 'KMA grid Y coordinate.' },
            },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'a'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
    const adapter = tools.find(tool => tool.name === 'kma_current_observation')

    expect(adapter).toBeDefined()
    expect(adapter?.alwaysLoad).not.toBe(true)
    expect(adapter?.shouldDefer).toBe(true)
    expect(adapter ? isDeferredTool(adapter) : false).toBe(true)
    expect(adapter?.inputJSONSchema?.properties).toHaveProperty('nx')
    expect(adapter?.userFacingName({ nx: 97, ny: 74 })).toBe('find')
    expect(
      adapter?.renderToolUseMessage({ nx: 97, ny: 74 }, { verbose: false }),
    ).toBe('kma_current_observation')
  })

  test('ToolSearch retrieves a top adapter schema without loading every adapter', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C2',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kma_current_observation',
          name: 'KMA Current Observation',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'KMA current weather observation getUltraSrtNcst',
          llm_description:
            'KMA APIHub current weather observation adapter for current weather.',
          input_schema_json: {
            type: 'object',
            properties: {
              nx: { type: 'integer', description: 'KMA grid X coordinate.' },
              ny: { type: 'integer', description: 'KMA grid Y coordinate.' },
            },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'hira_hospital_search',
          name: 'HIRA Hospital Search',
          primitive: 'find',
          policy_authority_url: 'https://www.hira.or.kr/',
          source_mode: 'live',
          search_hint: 'hospital clinic medical institution search',
          llm_description: 'Hospital and clinic search adapter.',
          input_schema_json: {
            type: 'object',
            properties: {
              sido: { type: 'string' },
            },
            required: ['sido'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'b'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
    const result = await ToolSearchTool.call(
      { query: 'current weather observation KMA', max_results: 1 },
      {
        options: { tools },
        getAppState: () => ({ mcp: { clients: [] } }),
      } as never,
      async () => ({ behavior: 'allow', updatedInput: {} }),
      {} as never,
    )

    expect(result.data.matches).toEqual(['kma_current_observation'])
    expect(result.data.total_deferred_tools).toBe(2)
  })

  test('turn-local adapter retrieval selects only query-relevant concrete schemas', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C3',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kakao_address_search',
          name: 'Kakao Address Search',
          primitive: 'locate',
          policy_authority_url: 'https://developers.kakao.com/',
          source_mode: 'live',
          search_hint:
            'locate 위치 주소 행정동 법정동 동 읍 면 구 좌표 kakao address 부산 사하구 다대1동',
          llm_description:
            'Locate structured Korean administrative district text and return coordinates plus KMA nx/ny.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_current_observation',
          name: 'KMA Current Observation',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint:
            '현재 날씨 기온 강수 습도 풍속 초단기실황 관측 current weather observation',
          llm_description:
            'Current weather observation adapter. Requires base_date, base_time, nx, ny.',
          input_schema_json: {
            type: 'object',
            properties: {
              base_date: { type: 'string' },
              base_time: { type: 'string' },
              nx: { type: 'integer' },
              ny: { type: 'integer' },
            },
            required: ['base_date', 'base_time', 'nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'hira_hospital_search',
          name: 'HIRA Hospital Search',
          primitive: 'find',
          policy_authority_url: 'https://www.hira.or.kr/',
          source_mode: 'live',
          search_hint: 'hospital clinic medical institution search',
          llm_description: 'Hospital and clinic search adapter.',
          input_schema_json: {
            type: 'object',
            properties: { sido: { type: 'string' } },
            required: ['sido'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'c'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '부산 사하구 다대1동 현재 날씨 알려줘',
      5,
    )

    expect(selected).toContain('kakao_address_search')
    expect(selected).toContain('kma_current_observation')
    expect(selected).not.toContain('hira_hospital_search')
    expect(isRootPrimitiveToolName('find')).toBe(true)
    expect(isRootPrimitiveToolName('kma_current_observation')).toBe(false)
  })

  test('root primitive prompts prefer concrete adapter functions over wrappers', () => {
    expect(FIND_DESCRIPTION).toContain('concrete adapter functions')
    expect(LOCATE_DESCRIPTION).toContain('concrete location adapter functions')

    const promptText = [
      FIND_TOOL_PROMPT,
      LOCATE_TOOL_PROMPT,
      SEND_TOOL_PROMPT,
      CHECK_TOOL_PROMPT,
    ].join('\n')

    expect(promptText).toContain('Call concrete adapter functions directly')
    expect(promptText).toContain('Legacy root wrapper')
    expect(promptText).not.toContain('The function name is find')
    expect(promptText).not.toContain('The function name is locate')
    expect(promptText).not.toContain('block and calls find directly')
    expect(promptText).not.toContain(
      'kma_current_observation({ nx: 97, ny: 74 })',
    )
    expect(promptText).not.toContain(
      'params: { nx: 97, ny: 74 }',
    )
    expect(promptText).toContain(
      'kma_current_observation({ base_date:',
    )
  })

  test('turn-local adapter retrieval keeps domain tools when location terms are present', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C4',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'locate',
          name: 'Root Locate',
          primitive: 'locate',
          policy_authority_url: 'internal://locate',
          source_mode: 'live',
          search_hint: 'locate 위치 주소 좌표',
          llm_description: 'Legacy root wrapper.',
          input_schema_json: {
            type: 'object',
            properties: {},
            additionalProperties: true,
          },
        },
        {
          tool_id: 'kakao_address_search',
          name: 'Kakao Address Search',
          primitive: 'locate',
          policy_authority_url: 'https://developers.kakao.com/',
          source_mode: 'live',
          search_hint:
            'locate 위치 주소 행정동 법정동 동 읍 면 구 좌표 kakao address 부산 사하구 다대1동',
          llm_description:
            'Locate Korean administrative district text and return coordinates plus KMA nx/ny.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kakao_coord_to_region',
          name: 'Kakao Coordinate To Region',
          primitive: 'locate',
          policy_authority_url: 'https://developers.kakao.com/',
          source_mode: 'live',
          search_hint: 'locate 지역 시도 시군구 행정동 법정동 q0 q1 coord2region reverse geocode kakao',
          llm_description: 'Resolve coordinates to region names for NMC Q0/Q1.',
          input_schema_json: {
            type: 'object',
            properties: {
              lat: { type: 'number' },
              lon: { type: 'number' },
            },
            required: ['lat', 'lon'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'juso_adm_cd_lookup',
          name: 'Juso Admin Code',
          primitive: 'locate',
          policy_authority_url: 'https://business.juso.go.kr/',
          source_mode: 'live',
          search_hint: 'locate 주소 행정동 adm_cd admCd juso 도로명주소 법정동 코드',
          llm_description: 'Resolve administrative codes.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'sgis_adm_cd_lookup',
          name: 'SGIS Admin Code',
          primitive: 'locate',
          policy_authority_url: 'https://sgis.kostat.go.kr/',
          source_mode: 'live',
          search_hint: 'locate sgis 좌표 역지오코딩 행정동 adm_cd 통계청 region reverse geocode',
          llm_description: 'Resolve SGIS administrative codes.',
          input_schema_json: {
            type: 'object',
            properties: { lat: { type: 'number' }, lon: { type: 'number' } },
            required: ['lat', 'lon'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'nmc_emergency_search',
          name: 'NMC Emergency Search',
          primitive: 'find',
          policy_authority_url: 'https://www.nemc.or.kr/',
          source_mode: 'live',
          search_hint:
            '응급실 실시간 병상 응급의료센터 국립중앙의료원 가까운 응급실 emergency room bed availability nearest ER NMC real-time Korea',
          llm_description:
            "NMC emergency institution search. Nearby or night ER queries use locate first, then mode='region' with q0/q1.",
          input_schema_json: {
            type: 'object',
            properties: {
              mode: { type: 'string', enum: ['coordinate', 'region'] },
              q0: { type: 'string' },
              q1: { type: 'string' },
              origin_lat: { type: 'number' },
              origin_lon: { type: 'number' },
              limit: { type: 'integer' },
            },
            required: ['mode'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'hira_hospital_search',
          name: 'HIRA Hospital Search',
          primitive: 'find',
          policy_authority_url: 'https://www.hira.or.kr/',
          source_mode: 'live',
          search_hint:
            '병원 검색 진료과목 의료기관 정보 근처 병원 내과 외과 소아과 hospital search medical specialty clinic nearby HIRA healthcare Korea',
          llm_description: 'Hospital and clinic search adapter.',
          input_schema_json: {
            type: 'object',
            properties: {
              xPos: { type: 'number' },
              yPos: { type: 'number' },
              radius: { type: 'integer' },
            },
            required: ['xPos', 'yPos'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'd'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '부산 사하구 다대1동 근처 야간 응급실 알려줘',
      5,
    )

    expect(selected).toContain('kakao_address_search')
    expect(selected).toContain('nmc_emergency_search')
    expect(selected).toContain('hira_hospital_search')
    expect(selected).not.toContain('locate')
  })

  test('station emergency retrieval exposes POI locate before reverse geocode', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C5',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kakao_keyword_search',
          name: 'Kakao Keyword Search',
          primitive: 'locate',
          policy_authority_url: 'https://developers.kakao.com/',
          source_mode: 'live',
          search_hint:
            'locate 위치 장소 키워드 POI 랜드마크 캠퍼스 역 병원 좌표 kakao keyword 강남역 서울대병원',
          llm_description:
            'Use for named places, campuses, stations, landmarks, hospitals, businesses, and POIs.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kakao_coord_to_region',
          name: 'Kakao Coordinate To Region',
          primitive: 'locate',
          policy_authority_url: 'https://developers.kakao.com/',
          source_mode: 'live',
          search_hint:
            'locate 지역 시도 시군구 행정동 법정동 q0 q1 coord2region reverse geocode kakao',
          llm_description:
            'Use after a coordinate-producing locate adapter when a downstream public API needs q0/q1.',
          input_schema_json: {
            type: 'object',
            properties: { lat: { type: 'number' }, lon: { type: 'number' } },
            required: ['lat', 'lon'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'nmc_emergency_search',
          name: 'NMC Emergency Search',
          primitive: 'find',
          policy_authority_url: 'https://www.nemc.or.kr/',
          source_mode: 'live',
          search_hint:
            '응급실 실시간 병상 응급의료센터 국립중앙의료원 가까운 응급실 emergency room bed availability nearest ER NMC real-time Korea',
          llm_description:
            "NMC emergency institution search. Nearby or night ER queries use locate first, then mode='region' with q0/q1.",
          input_schema_json: {
            type: 'object',
            properties: {
              mode: { type: 'string', enum: ['coordinate', 'region'] },
              q0: { type: 'string' },
              q1: { type: 'string' },
            },
            required: ['mode'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'e'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '아이가 열이 나는데 하단역 근처 야간 응급실이 어디야?',
      5,
    )

    expect(selected).toContain('nmc_emergency_search')
    expect(selected).toContain('kakao_keyword_search')
    expect(selected).not.toContain('kakao_coord_to_region')
  })

  test('traffic-risk retrieval keeps KOROAD when location and weather terms coexist', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C6',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kakao_address_search',
          name: 'Kakao Address Search',
          primitive: 'locate',
          policy_authority_url: 'https://developers.kakao.com/',
          source_mode: 'live',
          search_hint: 'locate 위치 주소 행정동 법정동 좌표 kakao address 부산 사하구',
          llm_description: 'Resolve Korean administrative text to coordinates.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'koroad_accident_hazard_search',
          name: 'KOROAD Accident Hazard Search',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint:
            '교통사고 위험지점 사고다발구역 어린이보호구역 행정동코드 accident hazard hotspot road safety KOROAD',
          llm_description: 'KOROAD accident hazard search by administrative code.',
          input_schema_json: {
            type: 'object',
            properties: { adm_cd: { type: 'string' }, year: { type: 'integer' } },
            required: ['adm_cd', 'year'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'koroad_accident_search',
          name: 'KOROAD Accident Search',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint:
            '교통사고 위험지역 조회 사고다발구역 지자체별 위험지점 accident hotspot dangerous zone traffic safety municipality',
          llm_description: 'KOROAD accident hotspot search by si_do and gu_gun codes.',
          input_schema_json: {
            type: 'object',
            properties: { si_do: { type: 'integer' }, gu_gun: { type: 'integer' } },
            required: ['si_do', 'gu_gun'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_current_observation',
          name: 'KMA Current Observation',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '현재 날씨 비 예보 기상청 강수 KMA current weather rain forecast',
          llm_description: 'KMA current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'f'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '부산 사하구에서 운전 중 자주 사고 나는 도로 구간과 오늘 비 예보를 같이 확인해줘',
      5,
    )

    expect(selected).toContain('kakao_address_search')
    expect(selected).toContain('koroad_accident_hazard_search')
    expect(selected).not.toContain('koroad_accident_search')
    expect(selected).toContain('kma_current_observation')
  })
})
