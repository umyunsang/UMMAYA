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
  getAdapterToolByName,
  isRootPrimitiveToolName,
  selectTopKAdapterToolNamesForQuery,
} from '../../src/tools/AdapterTool/AdapterTool.js'
import { LookupPrimitive } from '../../src/tools/LookupPrimitive/LookupPrimitive.js'
import {
  DESCRIPTION as FIND_DESCRIPTION,
  FIND_TOOL_PROMPT,
} from '../../src/tools/LookupPrimitive/prompt.js'
import {
  DESCRIPTION as LOCATE_DESCRIPTION,
  LOCATE_TOOL_PROMPT,
} from '../../src/tools/ResolveLocationPrimitive/prompt.js'
import { ResolveLocationPrimitive } from '../../src/tools/ResolveLocationPrimitive/ResolveLocationPrimitive.js'
import { SubmitPrimitive } from '../../src/tools/SubmitPrimitive/SubmitPrimitive.js'
import { SEND_TOOL_PROMPT } from '../../src/tools/SubmitPrimitive/prompt.js'
import { VerifyPrimitive } from '../../src/tools/VerifyPrimitive/VerifyPrimitive.js'
import { CHECK_TOOL_PROMPT } from '../../src/tools/VerifyPrimitive/prompt.js'
import {
  buildNmcAedCompletionPromptIfNeeded,
  buildNmcAedFollowupPromptIfNeeded,
} from '../../src/tools/_shared/nmcAedGuard.js'
import {
  buildAirKoreaCompletionPromptIfNeeded,
  buildAirKoreaFinalAnswerRepairPromptIfNeeded,
  buildGenericPendingFinalAnswerRepairPromptIfNeeded,
  buildTagoBusCompletionPromptIfNeeded,
  buildTagoBusFinalAnswerRepairPromptIfNeeded,
  buildTagoBusFollowupPromptIfNeeded,
  selectUmmayaToolChoiceOverride,
  shouldWithholdAirKoreaFinalAnswer,
  shouldWithholdGenericPendingFinalAnswer,
  shouldWithholdTagoBusFinalAnswer,
  shouldSuppressUmmayaToolCallsForAnswerSynthesis,
} from '../../src/tools/_shared/toolChoiceRepair.js'
import {
  deriveLocationQueryFromUserText,
  repairLocateQueryParamsFromConversation,
} from '../../src/tools/_shared/locationInputRepair.js'
import {
  buildProtectedCheckCompletionPromptIfNeeded,
  buildProtectedCheckFinalAnswerRepairPromptIfNeeded,
  shouldWithholdProtectedCheckToolCallText,
} from '../../src/tools/_shared/protectedCheckGuard.js'
import {
  buildKmaAnalysisCompletionPromptIfNeeded,
  buildKmaAnalysisFinalAnswerRepairPromptIfNeeded,
  buildKmaAnalysisMissingToolPromptIfNeeded,
  shouldWithholdKmaAnalysisToolCallText,
} from '../../src/tools/_shared/kmaAnalysisGuard.js'
import { normalizeDirectPublicDataToolInput } from '../../src/tools/_shared/directPublicDataGuard.js'
import {
  buildTextToolCallFinalAnswerRepairPromptIfNeeded,
  shouldWithholdTextToolCallFinalAnswer,
  stripTextToolCallBlocks,
} from '../../src/tools/_shared/textToolCallGuard.js'

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

function toolNamed(name: string) {
  return buildTool({
    name,
    inputSchema: z.object({}),
    isEnabled: () => true,
    isReadOnly: () => true,
    isConcurrencySafe: () => true,
    description: async () => name,
    prompt: async () => name,
    validateInput: async () => ({ result: true }),
    call: async () => ({ data: {} }),
    userFacingName: () => name,
    mapToolResultToToolResultBlockParam: (data, toolUseID) => ({
      type: 'tool_result',
      tool_use_id: toolUseID,
      content: JSON.stringify(data),
    }),
    renderToolUseMessage: () => null,
  })
}

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

  test('PPS bid wording exposes bid search before location adapters', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D0',
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
          search_hint: '주소 행정동 부산시 구군 도로명 address',
          llm_description: 'Kakao address lookup.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'pps_bid_public_info',
          name: 'PPS Bid Public Info',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15129394/openapi.do',
          source_mode: 'live',
          search_hint:
            '조달청 나라장터 공사 입찰공고 bid public info inqryBgnDt inqryEndDt bidNtceNm',
          llm_description: 'Search PPS bid notices by date range and bid title keyword.',
          input_schema_json: {
            type: 'object',
            properties: {
              inqry_bgn_dt: { type: 'string' },
              inqry_end_dt: { type: 'string' },
              bid_ntce_nm: { type: 'string' },
            },
            required: ['inqry_bgn_dt', 'inqry_end_dt'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'e'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '이번 주 부산시 전기공사 입찰 올라온 거 있어?',
      5,
    )

    expect(selected[0]).toBe('pps_bid_public_info')
    expect(selected).not.toContain('kakao_address_search')
  })

  test('PPS bid wording forces synced concrete adapter even before tool pool refresh', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9A1',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'pps_bid_public_info',
          name: 'PPS Bid Public Info',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15129394/openapi.do',
          source_mode: 'live',
          search_hint: '조달청 나라장터 부산 전기공사 입찰공고',
          llm_description: 'Search PPS bid notices.',
          input_schema_json: {
            type: 'object',
            properties: {
              inqry_bgn_dt: { type: 'string' },
              inqry_end_dt: { type: 'string' },
              inqry_div: { type: 'string' },
              bid_ntce_nm: { type: 'string' },
              indstryty_nm: { type: 'string' },
              region_name: { type: 'string' },
              prtcpt_lmt_rgn_nm: { type: 'string' },
            },
            required: ['inqry_bgn_dt', 'inqry_end_dt'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'a'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '이번 주 부산시 전기공사 입찰 올라온 거 있어?',
          },
        },
      ] as any,
      tools: [toolNamed('find'), toolNamed('locate'), toolNamed('ToolSearch')],
    })

    expect(override).toEqual({
      type: 'tool',
      name: 'pps_bid_public_info',
    })
  })

  test('direct public-data wording rejects unrelated primitive substitutions', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D9',
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
          search_hint: 'locate 위치 장소 키워드 POI kakao keyword',
          llm_description: 'POI location search.',
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
          search_hint: '현재 날씨 기상청 current weather observation',
          llm_description: 'KMA current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'pps_bid_public_info',
          name: 'PPS Bid Public Info',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15129394/openapi.do',
          source_mode: 'live',
          search_hint: '조달청 나라장터 전기공사 입찰공고',
          llm_description: 'Search PPS bid notices.',
          input_schema_json: {
            type: 'object',
            properties: {
              inqry_bgn_dt: { type: 'string' },
              inqry_end_dt: { type: 'string' },
            },
            required: ['inqry_bgn_dt', 'inqry_end_dt'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'airkorea_ctprvn_air_quality',
          name: 'AirKorea Air Quality',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15073861/openapi.do',
          source_mode: 'live',
          search_hint: '에어코리아 미세먼지 대기질',
          llm_description: 'AirKorea city/province air quality.',
          input_schema_json: {
            type: 'object',
            properties: { sido_name: { type: 'string' } },
            required: ['sido_name'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_analysis_weather_chart_image',
          name: 'KMA Chart Image',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '기상청 분석일기도 비구름 흐름 weather chart',
          llm_description: 'KMA analyzed weather-chart image.',
          input_schema_json: {
            type: 'object',
            properties: { anal_time: { type: 'string' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: '9'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const ppsContext = {
      options: { tools: [] },
      messages: [{ role: 'user', content: '이번 주 부산시 전기공사 입찰 올라온 거 있어?' }],
    } as any
    const ppsLocate = await ResolveLocationPrimitive.validateInput!(
      { tool_id: 'kakao_keyword_search', params: { query: '부산' } },
      ppsContext,
    )
    expect(ppsLocate.result).toBe(false)
    if (!ppsLocate.result) expect(ppsLocate.message).toContain('pps_bid_public_info')

    const ppsTool = getAdapterToolByName('pps_bid_public_info')
    expect(ppsTool).toBeDefined()
    const broadPps = normalizeDirectPublicDataToolInput(
      'pps_bid_public_info',
      ppsContext,
      {
        inqry_bgn_dt: '202605200000',
        inqry_end_dt: '202605262359',
        indstryty_nm: '전기공사업',
      },
    ) as Record<string, unknown>
    expect(broadPps.inqry_bgn_dt).not.toBe('202605200000')
    expect(broadPps.inqry_end_dt).not.toBe('202605262359')
    expect(broadPps.bid_ntce_nm).toBe('전기공사')
    expect(broadPps.indstryty_nm).toBe('전기공사업')
    expect(broadPps.prtcpt_lmt_rgn_nm).toBe('부산광역시')
    expect(broadPps.region_name).toBe('부산광역시')

    const airContext = {
      options: { tools: [] },
      messages: [{ role: 'user', content: '지금 부산 중구 미세먼지 괜찮아? 마스크 써야 해?' }],
    } as any
    const airWeather = await LookupPrimitive.validateInput!(
      { tool_id: 'kma_current_observation', params: { nx: 98, ny: 75 } },
      airContext,
    )
    expect(airWeather.result).toBe(false)
    if (!airWeather.result) expect(airWeather.message).toContain('airkorea_ctprvn_air_quality')
    const broadAirKorea = normalizeDirectPublicDataToolInput(
      'airkorea_ctprvn_air_quality',
      airContext,
      { sido_name: '부산광역시', num_of_rows: 10 },
    ) as Record<string, unknown>
    expect(broadAirKorea.sido_name).toBe('부산')
    expect(broadAirKorea.num_of_rows).toBe(100)

    const weatherContext = {
      options: { tools: [] },
      messages: [{ role: 'user', content: '퇴근하고 해운대 산책 갈 건데 지금 비 와? 우산 챙겨야 해?' }],
    } as any
    const airTool = getAdapterToolByName('airkorea_ctprvn_air_quality')
    expect(airTool).toBeDefined()
    const weatherAir = await airTool!.validateInput!(
      { sido_name: '부산' },
      weatherContext,
    )
    expect(weatherAir.result).toBe(false)
    if (!weatherAir.result) {
      expect(weatherAir.message).toContain('KMA weather/location adapters')
    }

    const weatherWithMetaContext = {
      options: { tools: [] },
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '퇴근하고 해운대 산책 갈 건데 지금 비 와? 우산 챙겨야 해?',
          },
        },
        {
          type: 'user',
          isMeta: true,
          message: {
            role: 'user',
            content:
              '## Available tools\n' +
              'kma_apihub_url_analysis_weather_chart_image: 비구름 바람 흐름 분석 차트 이미지.',
          },
        },
      ],
    } as any
    const weatherWithMetaAir = await airTool!.validateInput!(
      { sido_name: '부산' },
      weatherWithMetaContext,
    )
    expect(weatherWithMetaAir.result).toBe(false)
    if (!weatherWithMetaAir.result) {
      expect(weatherWithMetaAir.message).toContain('KMA weather/location adapters')
      expect(weatherWithMetaAir.message).not.toContain(
        'kma_apihub_url_analysis_weather_chart_image',
      )
    }

    const chartContext = {
      options: { tools: [] },
      messages: [
        { role: 'user', content: '오늘 오후 전국 비구름 흐름이 어떤지 공식 기상도나 위성 자료 기준으로 설명해줘' },
      ],
    } as any
    const chartWeather = await LookupPrimitive.validateInput!(
      { tool_id: 'kma_current_observation', params: { nx: 61, ny: 128 } },
      chartContext,
    )
    expect(chartWeather.result).toBe(false)
    if (!chartWeather.result) {
      expect(chartWeather.message).toContain('kma_apihub_url_analysis_weather_chart_image')
      expect(chartWeather.message).toContain('YYYYMMDDHHMM')
      expect(chartWeather.message).toContain('UTC')
    }

    const chartTool = getAdapterToolByName('kma_apihub_url_analysis_weather_chart_image')
    expect(chartTool).toBeDefined()
    const badChartTime = await chartTool!.validateInput!(
      { anal_time: '2026052822' },
      chartContext,
    )
    expect(badChartTime.result).toBe(false)
    if (!badChartTime.result) {
      expect(badChartTime.message).toContain('YYYYMMDDHHMM')
      expect(badChartTime.message).toContain('UTC')
    }

    const chartWithExtraParam = await LookupPrimitive.validateInput!(
      {
        tool_id: 'kma_apihub_url_analysis_weather_chart_image',
        params: { anal_time: '202605281200', org: 'K' },
      },
      chartContext,
    )
    expect(chartWithExtraParam.result).toBe(false)
    if (!chartWithExtraParam.result) {
      expect(chartWithExtraParam.message).toContain('org')
      expect(chartWithExtraParam.message).toContain('anal_time')
    }
  })

  test('bus arrival wording exposes TAGO adapters and rejects unrelated substitutions', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9DA',
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
          search_hint: 'locate 위치 장소 키워드 POI kakao keyword 부산역',
          llm_description: 'POI location search.',
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
          search_hint: '현재 날씨 기상청 current weather observation',
          llm_description: 'KMA current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
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
          search_hint: '병원 의료기관 hospital search',
          llm_description: 'Hospital and clinic search adapter.',
          input_schema_json: {
            type: 'object',
            properties: { xPos: { type: 'number' }, yPos: { type: 'number' } },
            required: ['xPos', 'yPos'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'tago_bus_station_search',
          name: 'TAGO Bus Station Search',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15098534/openapi.do',
          source_mode: 'live',
          search_hint: 'TAGO 버스정류소 정류장 nodeNm nodeNo station bus',
          llm_description: 'TAGO bus station lookup.',
          input_schema_json: {
            type: 'object',
            properties: {
              city_code: { type: 'string' },
              node_nm: { type: 'string' },
              node_no: { type: 'string' },
            },
            required: ['city_code'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'tago_bus_arrival_search',
          name: 'TAGO Bus Arrival Search',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15098530/openapi.do',
          source_mode: 'live',
          search_hint: 'TAGO 버스도착 정류소 nodeId arrival bus 언제 와',
          llm_description: 'TAGO bus arrival lookup.',
          input_schema_json: {
            type: 'object',
            properties: {
              city_code: { type: 'string' },
              node_id: { type: 'string' },
              route_no: {
                type: 'string',
                description: 'Optional client-side filter against returned TAGO routeno.',
              },
              route_id: {
                type: 'string',
                description: 'Optional client-side filter against returned TAGO routeid.',
              },
            },
            required: ['city_code', 'node_id'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'tago_bus_route_search',
          name: 'TAGO Bus Route Search',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15098529/openapi.do',
          source_mode: 'live',
          search_hint: 'TAGO 버스노선 노선번호 routeNo route bus 1001',
          llm_description: 'TAGO bus route lookup.',
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
          tool_id: 'tago_bus_route_station_search',
          name: 'TAGO Bus Route Station Search',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15098529/openapi.do',
          source_mode: 'live',
          search_hint: 'TAGO 노선별 경유정류소 routeId nodenm nodeid bus stop',
          llm_description: 'TAGO bus route passing-stop lookup.',
          input_schema_json: {
            type: 'object',
            properties: {
              city_code: { type: 'string' },
              route_id: { type: 'string' },
              node_nm: {
                type: 'string',
                description: 'Optional client-side filter against returned TAGO nodenm.',
              },
            },
            required: ['city_code', 'route_id'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: '8'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '부산역 앞 1001번 버스 언제 와?',
      5,
    )

    expect(selected).toContain('tago_bus_station_search')
    expect(selected).toContain('tago_bus_arrival_search')
    expect(selected).toContain('tago_bus_route_search')
    expect(selected).toContain('tago_bus_route_station_search')
    expect(selected).not.toContain('hira_hospital_search')
    expect(selected).not.toContain('kma_current_observation')

    const arrivalTool = getAdapterToolByName('tago_bus_arrival_search')
    const arrivalSchema = arrivalTool?.inputJSONSchema
    expect(arrivalSchema?.properties?.route_no?.description).toContain('routeno')
    expect(arrivalSchema?.properties?.route_id?.description).toContain('routeid')

    const context = {
      options: { tools: [] },
      messages: [{ role: 'user', content: '부산역 앞 1001번 버스 언제 와?' }],
    } as any

    const weather = await LookupPrimitive.validateInput!(
      { tool_id: 'kma_current_observation', params: { nx: 98, ny: 76 } },
      context,
    )
    expect(weather.result).toBe(false)
    if (!weather.result) expect(weather.message).toContain('TAGO')

    const wrongBusanCode = await LookupPrimitive.validateInput!(
      { tool_id: 'tago_bus_station_search', params: { city_code: '11', node_nm: '부산역' } },
      context,
    )
    expect(wrongBusanCode.result).toBe(false)
    if (!wrongBusanCode.result) {
      expect(wrongBusanCode.message).toContain('Busan=21')
      expect(wrongBusanCode.message).toContain('11')
    }

    const arrivalWithoutRouteFilter = await LookupPrimitive.validateInput!(
      {
        tool_id: 'tago_bus_arrival_search',
        params: { city_code: '21', node_id: 'BSB509960000' },
      },
      context,
    )
    expect(arrivalWithoutRouteFilter.result).toBe(false)
    if (!arrivalWithoutRouteFilter.result) {
      expect(arrivalWithoutRouteFilter.message).toContain('route_no:"1001"')
      expect(arrivalWithoutRouteFilter.message).toContain('tago_bus_route_station_search')
    }
  })

  test('bus route-place loop forces route station and arrival follow-ups', () => {
    const tools = [
      toolNamed('tago_bus_route_search'),
      toolNamed('tago_bus_route_station_search'),
      toolNamed('tago_bus_arrival_search'),
    ]
    const firstTurn = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산역에서 1001번 버스 곧 와?',
        },
      },
    ] as any

    expect(selectUmmayaToolChoiceOverride({ messages: firstTurn, tools })).toEqual({
      type: 'tool',
      name: 'tago_bus_route_search',
    })

    const afterRouteSearch = [
      ...firstTurn,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'route-1',
              name: 'tago_bus_route_search',
              input: { city_code: '21', route_no: '1001' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'route-1',
              content: JSON.stringify({
                ok: true,
                result: {
                  kind: 'collection',
                  items: [{ record: { routeid: 'BSB5201001000', routeno: '1001' } }],
                },
              }),
            },
          ],
        },
      },
    ] as any

    const routeStationPrompt = buildTagoBusFollowupPromptIfNeeded({
      messages: afterRouteSearch,
      availableToolNames: tools.map(tool => tool.name),
    })
    expect(routeStationPrompt).toContain('tago_bus_route_station_search')
    expect(routeStationPrompt).toContain('node_nm:"부산역"')
    expect(selectUmmayaToolChoiceOverride({ messages: afterRouteSearch, tools })).toEqual({
      type: 'tool',
      name: 'tago_bus_route_station_search',
    })

    const afterRouteStation = [
      ...afterRouteSearch,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'route-station-1',
              name: 'tago_bus_route_station_search',
              input: { city_code: '21', route_id: 'BSB5201001000', node_nm: '부산역' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'route-station-1',
              content: JSON.stringify({
                ok: true,
                result: {
                  kind: 'collection',
                  items: [{ record: { nodeid: 'BSB509960000', nodenm: '부산역' } }],
                },
              }),
            },
          ],
        },
      },
    ] as any

    const arrivalPrompt = buildTagoBusFollowupPromptIfNeeded({
      messages: afterRouteStation,
      availableToolNames: tools.map(tool => tool.name),
    })
    expect(arrivalPrompt).toContain('tago_bus_arrival_search')
    expect(arrivalPrompt).toContain('route_no:"1001"')
    expect(selectUmmayaToolChoiceOverride({ messages: afterRouteStation, tools })).toEqual({
      type: 'tool',
      name: 'tago_bus_arrival_search',
    })

    const afterArrival = [
      ...afterRouteStation,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'arrival-1',
              name: 'tago_bus_arrival_search',
              input: {
                city_code: '21',
                node_id: 'BSB509960000',
                route_no: '1001',
              },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'arrival-1',
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
        },
      },
    ] as any

    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({
        messages: afterArrival,
        tools,
      }),
    ).toBe(true)
    expect(selectUmmayaToolChoiceOverride({ messages: afterArrival, tools })).toBeUndefined()
    expect(buildTagoBusCompletionPromptIfNeeded({ messages: afterArrival })).toContain(
      'TAGO bus arrival evidence chain complete',
    )
    const pendingBusFinal = {
      type: 'assistant',
      message: {
        role: 'assistant',
        content: '다른 부산역 관련 정류장도 확인해보겠습니다.',
      },
    } as any
    const pendingBusSearchFinal = {
      type: 'assistant',
      message: {
        role: 'assistant',
        content:
          '부산역에서 해운대 방향 버스를 찾기 위해 먼저 해운대 방향의 버스 노선을 검색해 보겠습니다.',
      },
    } as any
    expect(
      shouldWithholdTagoBusFinalAnswer({
        messages: afterArrival,
        candidate: pendingBusFinal,
      }),
    ).toBe(true)
    expect(
      buildTagoBusFinalAnswerRepairPromptIfNeeded({
        messages: [...afterArrival, pendingBusFinal],
      }),
    ).toContain('TAGO bus final answer repair')
    const afterArrivalSourceOnly = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산역에서 해운대 가려고 하는데 지금 버스 도착 정보 좀 봐줘',
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'arrival-hidden',
              content: JSON.stringify({
                ok: true,
                result: {
                  kind: 'collection',
                  items: [],
                  total_count: 0,
                  meta: { source: 'tago_bus_arrival_search' },
                },
              }),
            },
          ],
        },
      },
    ] as any
    expect(
      shouldWithholdTagoBusFinalAnswer({
        messages: afterArrivalSourceOnly,
        candidate: pendingBusFinal,
      }),
    ).toBe(true)
    expect(
      shouldWithholdTagoBusFinalAnswer({
        messages: afterArrivalSourceOnly,
        candidate: pendingBusSearchFinal,
      }),
    ).toBe(true)
  })

  test('bus stop arrival wording without route number converges to station then arrival', () => {
    const tools = [
      toolNamed('tago_bus_station_search'),
      toolNamed('tago_bus_arrival_search'),
      toolNamed('tago_bus_route_search'),
    ]
    const firstTurn = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산역 정류장에 지금 버스 도착 정보 좀 봐줘',
        },
      },
    ] as any

    expect(selectUmmayaToolChoiceOverride({ messages: firstTurn, tools })).toEqual({
      type: 'tool',
      name: 'tago_bus_station_search',
    })

    const afterStation = [
      ...firstTurn,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'station-1',
              name: 'tago_bus_station_search',
              input: { city_code: '21', node_nm: '부산역' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'station-1',
              content: JSON.stringify({
                ok: true,
                result: {
                  kind: 'collection',
                  items: [{ record: { nodeid: 'BSB169100203', nodenm: '부산역' } }],
                },
              }),
            },
          ],
        },
      },
    ] as any

    const arrivalPrompt = buildTagoBusFollowupPromptIfNeeded({
      messages: afterStation,
      availableToolNames: tools.map(tool => tool.name),
    })
    expect(arrivalPrompt).toContain('tago_bus_arrival_search')
    expect(arrivalPrompt).toContain('best matching node_id')
    expect(arrivalPrompt).toContain('Do not switch to route search')
    expect(selectUmmayaToolChoiceOverride({ messages: afterStation, tools })).toEqual({
      type: 'tool',
      name: 'tago_bus_arrival_search',
    })

    const afterArrival = [
      ...afterStation,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'arrival-1',
              name: 'tago_bus_arrival_search',
              input: { city_code: '21', node_id: 'BSB169100203' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'arrival-1',
              content: JSON.stringify({
                ok: true,
                result: { kind: 'collection', items: [], total_count: 0 },
              }),
            },
          ],
        },
      },
    ] as any

    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({
        messages: afterArrival,
        tools,
      }),
    ).toBe(true)
    expect(buildTagoBusCompletionPromptIfNeeded({ messages: afterArrival })).toContain(
      'TAGO bus arrival evidence chain complete',
    )
  })

  test('origin-destination bus wording without route number does not force stop-arrival evidence', () => {
    const tools = [
      toolNamed('tago_bus_station_search'),
      toolNamed('tago_bus_arrival_search'),
      toolNamed('tago_bus_route_search'),
    ]
    const firstTurn = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산역에서 해운대 가려고 하는데 지금 버스 도착 정보 좀 봐줘',
        },
      },
    ] as any

    expect(selectUmmayaToolChoiceOverride({ messages: firstTurn, tools })).toEqual({
      type: 'tool',
      name: 'tago_bus_station_search',
    })

    const afterStation = [
      ...firstTurn,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'station-od',
              name: 'tago_bus_station_search',
              input: { city_code: '21', node_nm: '부산역' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'station-od',
              content: JSON.stringify({
                ok: true,
                result: {
                  kind: 'collection',
                  items: [{ record: { nodeid: 'BSB169100203', nodenm: '부산역' } }],
                },
              }),
            },
          ],
        },
      },
    ] as any

    const followupPrompt = buildTagoBusFollowupPromptIfNeeded({
      messages: afterStation,
      availableToolNames: tools.map(tool => tool.name),
    })
    expect(followupPrompt).toContain('origin-destination limitation')
    expect(followupPrompt).toContain('Do not call tago_bus_arrival_search')
    expect(selectUmmayaToolChoiceOverride({ messages: afterStation, tools })).toBeUndefined()
  })

  test('public-data mismatch repair forces the named target, not PPS by default', () => {
    const busMessages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산역에서 1001번 버스 곧 와?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'locate-1',
              name: 'locate',
              input: {
                tool_id: 'kakao_keyword_search',
                params: { query: '부산역' },
              },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'locate-1',
              is_error: true,
              content:
                '<tool_use_error>Public-data tool-choice mismatch: the latest citizen request matches TAGO bus adapters. Call TAGO bus adapters through the correct primitive instead of kakao_keyword_search.</tool_use_error>',
            },
          ],
        },
      },
    ] as any
    const tools = [
      toolNamed('pps_bid_public_info'),
      toolNamed('tago_bus_route_search'),
      toolNamed('tago_bus_route_station_search'),
      toolNamed('tago_bus_arrival_search'),
      toolNamed('airkorea_ctprvn_air_quality'),
    ]

    expect(selectUmmayaToolChoiceOverride({ messages: busMessages, tools })).toEqual({
      type: 'tool',
      name: 'tago_bus_route_search',
    })

    const airMessages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산 중구 미세먼지 지금 어때? 마스크 써야 해?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'locate-2',
              name: 'locate',
              input: {
                tool_id: 'kakao_address_search',
                params: { query: '부산 중구' },
              },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'locate-2',
              is_error: true,
              content:
                "<tool_use_error>Public-data tool-choice mismatch: the latest citizen request matches airkorea_ctprvn_air_quality. Call airkorea_ctprvn_air_quality through the correct primitive instead of kakao_address_search. params should include sido_name:'부산'.</tool_use_error>",
            },
          ],
        },
      },
    ] as any

    expect(selectUmmayaToolChoiceOverride({ messages: airMessages, tools })).toEqual({
      type: 'tool',
      name: 'airkorea_ctprvn_air_quality',
    })

    const airFirstTurn = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산 중구 미세먼지 지금 어때? 마스크 써야 해?',
        },
      },
    ] as any
    expect(selectUmmayaToolChoiceOverride({ messages: airFirstTurn, tools })).toEqual({
      type: 'tool',
      name: 'airkorea_ctprvn_air_quality',
    })

    const afterAirKorea = [
      ...airFirstTurn,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'air-1',
              name: 'airkorea_ctprvn_air_quality',
              input: { sido_name: '부산' },
            },
          ],
        },
      },
    ] as any
    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({
        messages: afterAirKorea,
        tools,
      }),
    ).toBe(true)
    const airKoreaCompletionPrompt = buildAirKoreaCompletionPromptIfNeeded({
      messages: afterAirKorea,
    })
    expect(airKoreaCompletionPrompt).toContain('actual tool_result')
    expect(airKoreaCompletionPrompt).toContain('do not infer the citizen place district')
    const airKoreaNearestClaim = {
      type: 'assistant',
      message: {
        role: 'assistant',
        content:
          '해운대와 가장 가까운 측정소는 좌동이고 다른 측정소는 동쪽에 있습니다. 시 전체 평균입니다.',
      },
    } as any
    expect(
      shouldWithholdAirKoreaFinalAnswer({
        messages: afterAirKorea,
        candidate: airKoreaNearestClaim,
      }),
    ).toBe(true)
    expect(
      buildAirKoreaFinalAnswerRepairPromptIfNeeded({
        messages: [...afterAirKorea, airKoreaNearestClaim],
      }),
    ).toContain('city/province station data')
  })

  test('textual tool-call final answers are withheld and repaired after tool evidence', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산역에서 1001번 버스 곧 와?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'bus-arrival-1',
              name: 'tago_bus_arrival_search',
              input: { city_code: '21', node_id: 'BSB509950000', route_no: '1001' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'bus-arrival-1',
              content: '{"ok":true,"result":{"items":[]}}',
            },
          ],
        },
      },
    ] as any
    const candidate = {
      type: 'assistant',
      message: {
        role: 'assistant',
        content: [
          {
            type: 'text',
            text:
              '다른 정류장도 확인해보겠습니다.\n' +
              '<tool_call>{"name":"tago_bus_arrival_search","arguments":{"city_code":"21"}}</tool_call>',
          },
        ],
      },
    } as any

    expect(
      shouldWithholdTextToolCallFinalAnswer({
        messages,
        candidate,
      }),
    ).toBe(true)
    expect(
      buildTextToolCallFinalAnswerRepairPromptIfNeeded({
        messages: [...messages, candidate],
      }),
    ).toContain('Textual tool-call final-answer repair')
    expect(
      shouldWithholdTextToolCallFinalAnswer({
        messages: [messages[0]],
        candidate,
      }),
    ).toBe(true)
    expect(stripTextToolCallBlocks('확인했습니다.\n<tool_call>{"name":"x"}</tool_call>')).toBe(
      '확인했습니다.',
    )
  })

  test('generic pending final answers are withheld after tool evidence', () => {
    const messages = [
      {
        type: 'user',
        message: { role: 'user', content: '퇴근하고 해운대 산책 갈 건데 지금 비 와?' },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'weather-1',
              content: JSON.stringify({
                ok: true,
                result: {
                  kind: 'record',
                  item: { t1h: 21.4, rn1: 0, reh: 71, base_time: '0200' },
                },
              }),
            },
          ],
        },
      },
    ] as any
    const candidate = {
      type: 'assistant',
      message: {
        role: 'assistant',
        content: '사용자에게 현재 상황과 예보를 바탕으로 답변을 제공하겠습니다.',
      },
    } as any

    expect(
      shouldWithholdGenericPendingFinalAnswer({
        messages,
        candidate,
      }),
    ).toBe(true)
    expect(
      buildGenericPendingFinalAnswerRepairPromptIfNeeded({
        messages: [...messages, candidate],
      }),
    ).toContain('Final answer repair')
  })

  test('airport aviation retrieval exposes APIHub METAR before locate', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D1',
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
          search_hint: 'locate 위치 장소 키워드 POI 랜드마크 공항 kakao keyword',
          llm_description: 'POI location search.',
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
          search_hint: '현재 날씨 기상청 current weather observation',
          llm_description: 'KMA current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_amos_minute',
          name: 'KMA APIHub AMOS',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'KMA APIHub AMOS 항공기상 공항기상 활주로 RVR',
          llm_description: 'AMOS minute aviation weather. Gimhae/RKPK is not supported.',
          input_schema_json: {
            type: 'object',
            properties: { stn: { type: 'string' } },
            required: ['stn'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint:
            'KMA APIHub METAR SPECI 해독자료 항공기상 RKPK Gimhae RVR safe_weather',
          llm_description:
            'Decoded METAR. station 153 is Gimhae Airport / RKPK. Use safe_weather.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' }, help: { type: 'integer' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'g'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      'kma_apihub_url_air_metar_decoded 도구로 김해공항 station 153 RKPK METAR safe_weather RVR 바람 기압',
      5,
    )

    expect(selected[0]).toBe('kma_apihub_url_air_metar_decoded')
    expect(selected).not.toContain('kma_apihub_url_air_amos_minute')
    expect(selected).not.toContain('kakao_keyword_search')
    expect(selected).not.toContain('kma_current_observation')
  })

  test('natural flight wording exposes APIHub METAR before locate', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D2',
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
          search_hint: 'locate 위치 장소 키워드 POI 랜드마크 공항 kakao keyword',
          llm_description: 'POI location search.',
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
          search_hint: '현재 날씨 기상청 current weather observation',
          llm_description: 'KMA current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_amos_minute',
          name: 'KMA APIHub AMOS',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'KMA APIHub AMOS 항공기상 공항기상 활주로 RVR',
          llm_description: 'AMOS minute aviation weather. Gimhae/RKPK is not supported.',
          input_schema_json: {
            type: 'object',
            properties: { stn: { type: 'string' } },
            required: ['stn'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint:
            'KMA APIHub METAR SPECI 해독자료 항공기상 RKPK Gimhae RVR safe_weather flight takeoff',
          llm_description:
            'Decoded METAR. station 153 is Gimhae Airport / RKPK. Use safe_weather.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' }, help: { type: 'integer' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'h'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '오늘 저녁에 김해공항에서 서울 가는 비행기 예약했는데 날씨 어때? 비행기 뜰만한가?',
      5,
    )

    expect(selected[0]).toBe('kma_apihub_url_air_metar_decoded')
    expect(selected).not.toContain('kma_apihub_url_air_amos_minute')
    expect(selected).not.toContain('kakao_keyword_search')
    expect(selected).not.toContain('kma_current_observation')
  })

  test('airport aviation wording forces concrete METAR tool choice on first live turn', () => {
    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘',
          },
        },
      ] as any,
      tools: [
        toolNamed('locate'),
        toolNamed('kakao_keyword_search'),
        toolNamed('kma_current_observation'),
        toolNamed('kma_apihub_url_air_metar_decoded'),
        toolNamed('kma_apihub_url_air_amos_minute'),
      ],
    })

    expect(override).toEqual({
      type: 'tool',
      name: 'kma_apihub_url_air_metar_decoded',
    })
  })

  test('KMA aviation wording forces synced adapter before tool pool refresh', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9A2',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub METAR decoded',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '항공기상 METAR 김해 김포 RKPK RKSS 시정 바람',
          llm_description: 'Decoded airport METAR evidence.',
          input_schema_json: {
            type: 'object',
            properties: {
              tm: { type: 'string' },
              org: { type: 'string' },
              help: { type: 'integer' },
            },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'b'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘',
          },
        },
      ] as any,
      tools: [toolNamed('find'), toolNamed('locate'), toolNamed('kma_current_observation')],
    })

    expect(override).toEqual({
      type: 'tool',
      name: 'kma_apihub_url_air_metar_decoded',
    })
  })

  test('airport runway wording prefers AMOS when the adapter is visible', () => {
    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '김포공항 활주로 쪽 RVR이랑 바람 괜찮아? 오늘 밤 비행기 지연될 정도야?',
          },
        },
      ] as any,
      tools: [
        toolNamed('kma_apihub_url_air_metar_decoded'),
        toolNamed('kma_apihub_url_air_amos_minute'),
      ],
    })

    expect(override).toEqual({
      type: 'tool',
      name: 'kma_apihub_url_air_amos_minute',
    })
  })

  test('airport aviation tool choice override stops after an aviation tool was attempted', () => {
    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '오늘 밤 김해공항에서 비행기 뜰만해? 바람이랑 시정도 봐줘',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'metar-1',
                name: 'kma_apihub_url_air_metar_decoded',
                input: { org: 'RKPK' },
              },
            ],
          },
        },
      ] as any,
      tools: [
        toolNamed('kma_apihub_url_air_metar_decoded'),
        toolNamed('kma_apihub_url_air_amos_minute'),
      ],
    })

    expect(override).toBeUndefined()
  })

  test('route aviation wording forces AMOS follow-up after METAR when Gimpo is still in scope', () => {
    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'metar-1',
                name: 'kma_apihub_url_air_metar_decoded',
                input: { org: 'RKPK' },
              },
            ],
          },
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'metar-1',
                content: JSON.stringify({
                  ok: true,
                  result: { kind: 'record', item: { airport: 'RKPK' } },
                }),
              },
            ],
          },
        },
      ] as any,
      tools: [
        toolNamed('kma_apihub_url_air_metar_decoded'),
        toolNamed('kma_apihub_url_air_amos_minute'),
      ],
    })

    expect(override).toEqual({
      type: 'tool',
      name: 'kma_apihub_url_air_amos_minute',
    })
  })

  test('route aviation wording forces synced AMOS follow-up before tool pool refresh', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9A4',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kma_apihub_url_air_amos_minute',
          name: 'KMA APIHub AMOS minute',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '항공기상 AMOS 김포 RKSS 활주로 RVR 바람',
          llm_description: 'Airport AMOS minute evidence.',
          input_schema_json: {
            type: 'object',
            properties: {
              tm: { type: 'string' },
              stn: { type: 'string' },
            },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'd'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'metar-1',
                name: 'kma_apihub_url_air_metar_decoded',
                input: { org: 'K' },
              },
            ],
          },
        },
      ] as any,
      tools: [toolNamed('find'), toolNamed('locate'), toolNamed('kma_apihub_url_air_metar_decoded')],
    })

    expect(override).toEqual({
      type: 'tool',
      name: 'kma_apihub_url_air_amos_minute',
    })
  })

  test('route aviation wording suppresses further tools once required aviation evidence exists', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content:
            '오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'metar-1',
              name: 'kma_apihub_url_air_metar_decoded',
              input: { org: 'RKPK' },
            },
            {
              type: 'tool_use',
              id: 'amos-1',
              name: 'kma_apihub_url_air_amos_minute',
              input: { stn: '110' },
            },
          ],
        },
      },
    ] as any
    const tools = [
      toolNamed('find'),
      toolNamed('kma_current_observation'),
      toolNamed('kma_apihub_url_air_metar_decoded'),
      toolNamed('kma_apihub_url_air_amos_minute'),
    ]

    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({ messages, tools }),
    ).toBe(true)
    expect(selectUmmayaToolChoiceOverride({ messages, tools })).toBeUndefined()
  })

  test('Gimpo runway wording exposes APIHub AMOS before METAR', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D3',
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
          search_hint: 'locate 위치 장소 키워드 POI 랜드마크 공항 kakao keyword',
          llm_description: 'POI location search.',
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
          search_hint: '현재 날씨 기상청 current weather observation',
          llm_description: 'KMA current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_amos_minute',
          name: 'KMA APIHub AMOS',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint:
            'KMA APIHub AMOS 항공기상 공항기상 활주로 RVR 김포공항 stn110 runway visibility wind',
          llm_description:
            'AMOS minute aviation weather. Use station 110 for Gimpo runway-area current conditions.',
          input_schema_json: {
            type: 'object',
            properties: { stn: { type: 'string' } },
            required: ['stn'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint:
            'KMA APIHub METAR SPECI 해독자료 항공기상 RKSS Gimpo safe_weather flight takeoff',
          llm_description:
            'Decoded METAR. station 110 is Gimpo Airport / RKSS. Use safe_weather.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' }, help: { type: 'integer' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'i'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '김포공항에서 제주 가는 밤 비행기인데 활주로 쪽 바람이랑 시정 괜찮아? 지연될 정도야?',
      5,
    )

    expect(selected[0]).toBe('kma_apihub_url_air_amos_minute')
    expect(selected).toContain('kma_apihub_url_air_metar_decoded')
    expect(selected).not.toContain('kakao_keyword_search')
    expect(selected).not.toContain('kma_current_observation')
  })

  test('analysis-data wording exposes KMA analyzed grid adapters', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D4',
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
          search_hint: 'locate 위치 장소 키워드 POI 랜드마크 공항 kakao keyword',
          llm_description: 'POI location search.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kakao_address_search',
          name: 'Kakao Address Search',
          primitive: 'locate',
          policy_authority_url: 'https://developers.kakao.com/',
          source_mode: 'live',
          search_hint: 'locate 주소 도로명 지번 공항 kakao address geocode',
          llm_description: 'Address geocoding for street addresses.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_short_term_forecast',
          name: 'KMA Short Term Forecast',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '단기예보 기상청 예보 forecast nx ny',
          llm_description: 'KMA village forecast.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_high_resolution_grid_point',
          name: 'KMA APIHub high-resolution grid point',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint:
            '고해상도 격자자료 분석자료 객관분석 500m 특정지점 기온 습도 풍속 풍향 시정 objective analysis grid point lat lon',
          llm_description:
            'KMA 500m high-resolution analyzed grid values. After locate returns coordinates, call this with lat/lon.',
          input_schema_json: {
            type: 'object',
            properties: { lat: { type: 'number' }, lon: { type: 'number' } },
            required: ['lat', 'lon'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_aws_objective_analysis_grid',
          name: 'KMA APIHub AWS objective analysis',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'AWS 객관분석 격자자료 분석자료 objective analysis grid',
          llm_description: 'AWS objective-analysis grid product.',
          input_schema_json: {
            type: 'object',
            properties: { obs: { type: 'string' } },
            required: ['obs'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'j'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '김해공항 주변은 기상청이 이미 분석한 자료로 보면 비나 바람 상태 괜찮아?',
      5,
    )

    expect(selected).toContain('kma_apihub_url_high_resolution_grid_point')
    expect(selected).toContain('kma_apihub_url_aws_objective_analysis_grid')
    expect(selected).toContain('kakao_address_search')
    expect(selected[0]).toBe('kakao_keyword_search')
    expect(selected.indexOf('kakao_keyword_search')).toBeLessThan(
      selected.indexOf('kakao_address_search'),
    )
    expect(selected.slice(0, 3)).not.toContain('kma_short_term_forecast')
  })

  test('analysis map wording exposes chart adapter instead of airport tools', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D5',
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
          search_hint: 'locate 위치 장소 키워드 POI 랜드마크 공항 kakao keyword',
          llm_description: 'POI location search.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_amos_minute',
          name: 'KMA APIHub AMOS',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'AMOS 공항기상관측 매분자료 활주로 기상실황 김포공항 stn110',
          llm_description: 'AMOS airport weather.',
          input_schema_json: {
            type: 'object',
            properties: { stn: { type: 'string' } },
            required: ['stn'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'METAR SPECI 해독자료 항공기상 공항기상',
          llm_description: 'Decoded METAR.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' } },
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_analysis_weather_chart_image',
          name: 'KMA APIHub analysis weather chart',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint:
            '분석일기도 일기도 지도 이미지 수치모델 분석자료 비구름 바람흐름 synoptic chart image',
          llm_description:
            'KMA analyzed weather-chart imagery or metadata for an analysis time.',
          input_schema_json: {
            type: 'object',
            properties: { anal_time: { type: 'string' } },
            required: ['anal_time'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'k'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '공항 관측값 말고 기상청에서 이미 분석한 일기도나 지도 자료 기준으로 오늘 저녁 남부 쪽 비구름이랑 바람 흐름은 어때?',
      5,
    )

    expect(selected[0]).toBe('kma_apihub_url_analysis_weather_chart_image')
    expect(selected).not.toContain('kakao_keyword_search')
    expect(selected).not.toContain('kma_apihub_url_air_amos_minute')
    expect(selected).not.toContain('kma_apihub_url_air_metar_decoded')
  })

  test('analysis map wording rejects point-grid tool substitution at validation time', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D6',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kma_apihub_url_high_resolution_grid_point',
          name: 'KMA APIHub high-resolution grid point',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '고해상도 격자자료 분석자료 특정지점 lat lon',
          llm_description: 'KMA point-grid analyzed values.',
          input_schema_json: {
            type: 'object',
            properties: { lat: { type: 'number' }, lon: { type: 'number' } },
            required: ['lat', 'lon'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_analysis_weather_chart_image',
          name: 'KMA APIHub analysis weather chart',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '분석일기도 일기도 지도 이미지 비구름 바람흐름',
          llm_description: 'KMA analyzed weather-chart imagery.',
          input_schema_json: {
            type: 'object',
            properties: { anal_time: { type: 'string' } },
            required: ['anal_time'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'l'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const context = {
      options: { tools: [] },
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '공항 관측값 말고 기상청에서 이미 분석한 일기도나 지도 자료 기준으로 오늘 저녁 남부 쪽 비구름이랑 바람 흐름은 어때?',
          },
        },
      ],
    } as any

    const rootResult = await LookupPrimitive.validateInput!(
      {
        tool_id: 'kma_apihub_url_high_resolution_grid_point',
        params: { lat: 35.1, lon: 129.0 },
      },
      context,
    )
    expect(rootResult.result).toBe(false)
    if (!rootResult.result) {
      expect(rootResult.message).toContain('weather chart/map')
    }

    const concreteTool = getAdapterToolByName('kma_apihub_url_high_resolution_grid_point')
    expect(concreteTool).toBeDefined()
    const concreteResult = await concreteTool!.validateInput!(
      { lat: 35.1, lon: 129.0 },
      context,
    )
    expect(concreteResult.result).toBe(false)
    if (!concreteResult.result) {
      expect(concreteResult.message).toContain('weather chart/map')
    }
  })

  test('analysis map wording forces chart first and suppresses substitutes after attempt', () => {
    const firstTurn = [
      {
        type: 'user',
        message: {
          role: 'user',
          content:
            '기상청에서 이미 분석한 일기도나 지도 기준으로 오늘 저녁 남부 쪽 비구름이랑 바람 흐름 어때?',
        },
      },
    ] as any
    const tools = [
      toolNamed('kma_apihub_url_analysis_weather_chart_image'),
      toolNamed('kma_apihub_url_high_resolution_grid_point'),
      toolNamed('kma_current_observation'),
    ]

    expect(selectUmmayaToolChoiceOverride({ messages: firstTurn, tools })).toEqual({
      type: 'tool',
      name: 'kma_apihub_url_analysis_weather_chart_image',
    })

    const afterChartAttempt = [
      ...firstTurn,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'chart-1',
              name: 'kma_apihub_url_analysis_weather_chart_image',
              input: { anal_time: '202605270000' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'chart-1',
              content: JSON.stringify({
                ok: false,
                error: { kind: 'upstream_error', message: '403 approval required' },
              }),
            },
          ],
        },
      },
    ] as any

    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({
        messages: afterChartAttempt,
        tools,
      }),
    ).toBe(true)
    expect(selectUmmayaToolChoiceOverride({ messages: afterChartAttempt, tools })).toBeUndefined()
    expect(buildKmaAnalysisCompletionPromptIfNeeded({ messages: afterChartAttempt })).toContain(
      'KMA analyzed weather-chart evidence chain complete',
    )

    const prematureLocationQuestion = [
      ...firstTurn,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'text',
              text:
                '전국 비구름 흐름을 보려면 먼저 현재 계신 지역을 알려주세요.',
            },
          ],
        },
      },
    ] as any
    expect(
      buildKmaAnalysisMissingToolPromptIfNeeded({
        messages: prematureLocationQuestion,
      }),
    ).toContain('Required KMA analyzed weather-chart lookup')

    const afterRootPrimitiveChartAttempt = [
      ...firstTurn,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'root-chart-1',
              name: 'find',
              input: {
                tool_id: 'kma_apihub_url_analysis_weather_chart_image',
                params: { anal_time: '202605281200' },
              },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'root-chart-1',
              content: JSON.stringify({
                ok: false,
                error: { kind: 'invalid_params', message: 'Missing org' },
              }),
            },
          ],
        },
      },
    ] as any

    expect(
      buildKmaAnalysisCompletionPromptIfNeeded({
        messages: afterRootPrimitiveChartAttempt,
      }),
    ).toContain('KMA analyzed weather-chart evidence chain complete')

    const badJsonAnswer = [
      ...afterChartAttempt,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'text',
              text: '{"name": "kma_apihub_url_analysis_weather_chart_image", "arguments": {"anal_time": "202605271500"}}',
            },
          ],
        },
      },
    ] as any

    expect(
      shouldWithholdKmaAnalysisToolCallText({
        messages: afterChartAttempt,
        candidate: badJsonAnswer.at(-1),
      }),
    ).toBe(true)
    expect(
      buildKmaAnalysisFinalAnswerRepairPromptIfNeeded({
        messages: badJsonAnswer,
      }),
    ).toContain('final-answer repair')

    const repairedAttempt = [
      ...badJsonAnswer,
      {
        type: 'user',
        message: {
          role: 'user',
          content:
            'KMA analyzed weather-chart final-answer repair: do not print tool calls.',
        },
      },
    ] as any
    expect(
      buildKmaAnalysisFinalAnswerRepairPromptIfNeeded({
        messages: repairedAttempt,
      }),
    ).toBeUndefined()

    const invalidLocationFollowupAnswer = [
      ...afterChartAttempt,
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'text',
              text:
                '기상청 분석일기도 이미지 조회가 성공했습니다. 다만 현재 위치 정보가 없어 정확한 좌표나 지역명을 알려주시면 카카오 도구를 사용해 더 확인하겠습니다.',
            },
          ],
        },
      },
    ] as any
    expect(
      shouldWithholdKmaAnalysisToolCallText({
        messages: afterChartAttempt,
        candidate: invalidLocationFollowupAnswer.at(-1),
      }),
    ).toBe(true)
    expect(
      buildKmaAnalysisFinalAnswerRepairPromptIfNeeded({
        messages: invalidLocationFollowupAnswer,
      }),
    ).toContain('Do not ask for coordinates')
  })

  test('analysis map wording forces synced chart adapter before tool pool refresh', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9A3',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'kma_apihub_url_analysis_weather_chart_image',
          name: 'KMA APIHub Analysis Weather Chart Image',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '기상청 분석일기도 일기도 지도 비구름 바람 흐름',
          llm_description: 'Official KMA analyzed weather chart image lookup.',
          input_schema_json: {
            type: 'object',
            properties: {
              anal_time: { type: 'string' },
              image_type: { type: 'string' },
            },
            required: ['anal_time'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'c'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '기상청 분석일기도 기준으로 오늘 저녁 남부 비구름이랑 바람 흐름 봐줘',
          },
        },
      ] as any,
      tools: [toolNamed('find'), toolNamed('locate'), toolNamed('kma_current_observation')],
    })

    expect(override).toEqual({
      type: 'tool',
      name: 'kma_apihub_url_analysis_weather_chart_image',
    })
  })

  test('AED wording rejects ER adapter substitution at validation time', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D7',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'nmc_emergency_search',
          name: 'NMC Emergency Search',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint: '응급실 응급의료센터 emergency room ER hospital',
          llm_description: 'NMC emergency-room institution search.',
          input_schema_json: {
            type: 'object',
            properties: { mode: { type: 'string' }, q0: { type: 'string' } },
            required: ['mode'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'nmc_aed_site_locate',
          name: 'NMC AED Site Locate',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint: 'AED 자동심장충격기 자동제세동기 위치 NMC',
          llm_description: 'NMC AED site lookup.',
          input_schema_json: {
            type: 'object',
            properties: { q0: { type: 'string' }, q1: { type: 'string' } },
            additionalProperties: false,
          },
        },
        {
          tool_id: 'hira_hospital_search',
          name: 'HIRA Hospital Search',
          primitive: 'find',
          policy_authority_url: 'https://www.hira.or.kr/',
          source_mode: 'live',
          search_hint: '병원 검색 진료과목 의료기관 정보 hospital clinic HIRA',
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
      '부산역 근처에서 사람이 쓰러졌어. 제일 가까운 응급실이나 AED 어디로 가야 해?',
      5,
    )
    expect(selected).toContain('nmc_emergency_search')
    expect(selected).toContain('nmc_aed_site_locate')

    const context = {
      options: { tools: [] },
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '부산역 근처에서 사람이 쓰러졌어. 제일 가까운 응급실이나 AED 어디로 가야 해?',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: '이제 AED(자동심장충격기) 위치도 찾아드리겠습니다.',
          },
        },
      ],
    } as any

    const erAndAedContext = {
      ...context,
      messages: [
        context.messages[0],
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: '부산역 주변 응급실과 AED를 순서대로 검색하겠습니다.',
          },
        },
      ],
    } as any
    const erResult = await LookupPrimitive.validateInput!(
      { tool_id: 'nmc_emergency_search', params: { mode: 'region', q0: '부산' } },
      erAndAedContext,
    )
    expect(erResult.result).toBe(true)

    const rootResult = await LookupPrimitive.validateInput!(
      { tool_id: 'nmc_emergency_search', params: { mode: 'region', q0: '부산' } },
      context,
    )
    expect(rootResult.result).toBe(false)
    if (!rootResult.result) {
      expect(rootResult.message).toContain('nmc_aed_site_locate')
    }

    const concreteTool = getAdapterToolByName('nmc_emergency_search')
    expect(concreteTool).toBeDefined()
    const concreteResult = await concreteTool!.validateInput!(
      { mode: 'region', q0: '부산' },
      context,
    )
    expect(concreteResult.result).toBe(false)
    if (!concreteResult.result) {
      expect(concreteResult.message).toContain('nmc_aed_site_locate')
    }

    const hiraTool = getAdapterToolByName('hira_hospital_search')
    expect(hiraTool).toBeDefined()
    const hiraResult = await hiraTool!.validateInput!(
      { xPos: 129.0415, yPos: 35.1152, radius: 3000 },
      {
        options: { tools: [] },
        messages: [
          {
            role: 'user',
            content: '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
          },
        ],
      } as any,
    )
    expect(hiraResult.result).toBe(false)
    if (!hiraResult.result) {
      expect(hiraResult.message).toContain('nmc_emergency_search')
      expect(hiraResult.message).toContain('nmc_aed_site_locate')
    }
  })

  test('collapse emergency loop requires AED follow-up after successful ER lookup', () => {
    const prompt = buildNmcAedFollowupPromptIfNeeded({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'er-1',
                name: 'nmc_emergency_search',
                input: { mode: 'region', q0: '부산광역시', q1: '동구' },
              },
            ],
          },
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'er-1',
                content: JSON.stringify({
                  ok: true,
                  result: { kind: 'collection', items: [{ name: '응급실' }] },
                }),
              },
            ],
          },
        },
      ],
      availableToolNames: ['nmc_aed_site_locate'],
    })

    expect(prompt).toContain('nmc_aed_site_locate')
    expect(prompt).toContain('Do not write final')

    const rootPrimitivePrompt = buildNmcAedFollowupPromptIfNeeded({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'root-er',
                name: 'find',
                input: {
                  tool_id: 'nmc_emergency_search',
                  params: { mode: 'region', q0: '부산광역시', q1: '동구' },
                },
              },
            ],
          },
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'root-er',
                content: JSON.stringify({
                  ok: true,
                  result: { kind: 'collection', items: [{ name: '응급실' }] },
                }),
              },
            ],
          },
        },
      ] as any,
      availableToolNames: ['nmc_aed_site_locate'],
    })
    expect(rootPrimitivePrompt).toContain('nmc_aed_site_locate')
  })

  test('collapse emergency loop forces AED tool choice after successful ER lookup', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content:
            '해운대에서 산책 중인데 사람이 의식을 잃은 것 같아. 지금 어디로 가야 해?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'er-1',
              name: 'nmc_emergency_search',
              input: { mode: 'region', q0: '부산광역시', q1: '해운대구' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'er-1',
              content: JSON.stringify({
                ok: true,
                result: { kind: 'collection', items: [{ name: '응급실' }] },
              }),
            },
          ],
        },
      },
    ] as any
    const tools = [
      toolNamed('nmc_emergency_search'),
      toolNamed('nmc_aed_site_locate'),
    ]

    expect(selectUmmayaToolChoiceOverride({ messages, tools })).toEqual({
      type: 'tool',
      name: 'nmc_aed_site_locate',
    })
  })

  test('collapse emergency loop forces ER tool choice after region resolution', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'region-1',
              name: 'locate',
              input: {
                tool_id: 'kakao_coord_to_region',
                params: { lat: 35.11520340622514, lon: 129.04154985192403 },
              },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'region-1',
              content: JSON.stringify({
                ok: true,
                result: {
                  kind: 'region',
                  region_1depth_name: '부산광역시',
                  region_2depth_name: '동구',
                  region_3depth_name: '초량동',
                },
              }),
            },
          ],
        },
      },
    ] as any
    const tools = [
      toolNamed('locate'),
      toolNamed('nmc_emergency_search'),
      toolNamed('nmc_aed_site_locate'),
    ]

    expect(selectUmmayaToolChoiceOverride({ messages, tools })).toEqual({
      type: 'tool',
      name: 'nmc_emergency_search',
    })
  })

  test('collapse emergency loop forces region conversion after POI location', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'poi-1',
              name: 'locate',
              input: {
                tool_id: 'kakao_keyword_search',
                params: { query: '부산역' },
              },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'poi-1',
              content: JSON.stringify({
                ok: true,
                result: {
                  kind: 'poi',
                  name: '부산역',
                  lat: 35.11520340622514,
                  lon: 129.04154985192403,
                },
              }),
            },
          ],
        },
      },
    ] as any
    const tools = [
      toolNamed('locate'),
      toolNamed('kakao_coord_to_region'),
      toolNamed('nmc_emergency_search'),
      toolNamed('nmc_aed_site_locate'),
    ]

    expect(selectUmmayaToolChoiceOverride({ messages, tools })).toEqual({
      type: 'tool',
      name: 'kakao_coord_to_region',
    })
  })

  test('collapse emergency loop suppresses further tools once AED was attempted', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content:
            '해운대에서 산책 중인데 사람이 의식을 잃은 것 같아. 지금 어디로 가야 해?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'aed-1',
              name: 'nmc_aed_site_locate',
              input: { q0: '부산광역시', q1: '해운대구' },
            },
          ],
        },
      },
    ] as any
    const tools = [
      toolNamed('nmc_emergency_search'),
      toolNamed('nmc_aed_site_locate'),
    ]

    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({ messages, tools }),
    ).toBe(true)
  })

  test('collapse emergency loop adds completion prompt after ER and AED attempts', () => {
    const prompt = buildNmcAedCompletionPromptIfNeeded({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '해운대에서 산책 중인데 사람이 의식을 잃은 것 같아. 지금 어디로 가야 해?',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'er-1',
                name: 'nmc_emergency_search',
                input: { mode: 'region', q0: '부산광역시', q1: '해운대구' },
              },
              {
                type: 'tool_use',
                id: 'aed-1',
                name: 'nmc_aed_site_locate',
                input: { q0: '부산광역시', q1: '해운대구' },
              },
            ],
          },
        },
      ],
    })

    expect(prompt).toContain('Emergency evidence chain complete')
    expect(prompt).toContain('Do not emit <tool_call>')
    expect(prompt).toContain('Do not invent distances')
    expect(prompt).toContain('walking times')
    expect(prompt).toContain('Copy AED org, buildAddress, buildPlace')
  })

  test('collapse emergency repair prompts are scoped to the latest user turn', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content:
            '강남역 11번 출구 근처에서 사람이 쓰러졌어. 응급실과 AED를 찾아줘.',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'er-1',
              name: 'nmc_emergency_search',
              input: { mode: 'region', q0: '서울특별시', q1: '강남구' },
            },
            {
              type: 'tool_use',
              id: 'aed-1',
              name: 'nmc_aed_site_locate',
              input: { q0: '서울특별시', q1: '강남구' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'er-1',
              content: JSON.stringify({
                ok: true,
                result: { kind: 'collection', items: [{ name: '응급실' }] },
              }),
            },
            {
              type: 'tool_result',
              tool_use_id: 'aed-1',
              content: JSON.stringify({
                ok: true,
                result: { kind: 'collection', items: [{ org: 'AED' }] },
              }),
            },
          ],
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: '119를 먼저 호출하고 응급실과 AED 위치를 안내합니다.',
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content:
            '부산 지역 디지털출판이나 전자책 제작 관련 공공입찰 공고가 있는지 찾아줘.',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'pps-1',
              name: 'pps_bid_public_info',
              input: { keyword: '전자책', region: '부산' },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'pps-1',
              content: JSON.stringify({
                ok: true,
                result: { kind: 'collection', items: [] },
              }),
            },
          ],
        },
      },
    ] as any

    expect(
      buildNmcAedFollowupPromptIfNeeded({
        messages,
        availableToolNames: ['nmc_aed_site_locate'],
      }),
    ).toBeUndefined()
    expect(buildNmcAedCompletionPromptIfNeeded({ messages })).toBeUndefined()
  })

  test('collapse emergency loop does not require AED once AED was attempted', () => {
    const prompt = buildNmcAedFollowupPromptIfNeeded({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'er-1',
                name: 'nmc_emergency_search',
                input: { mode: 'region', q0: '부산광역시', q1: '동구' },
              },
              {
                type: 'tool_use',
                id: 'aed-1',
                name: 'nmc_aed_site_locate',
                input: { q0: '부산광역시', q1: '동구' },
              },
            ],
          },
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'er-1',
                content: JSON.stringify({
                  ok: true,
                  result: { kind: 'collection', items: [{ name: '응급실' }] },
                }),
              },
            ],
          },
        },
      ],
      availableToolNames: ['nmc_aed_site_locate'],
    })

    expect(prompt).toBeUndefined()
  })

  test('collapse emergency loop waits when AED adapter is not visible', () => {
    const prompt = buildNmcAedFollowupPromptIfNeeded({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'er-1',
                name: 'nmc_emergency_search',
                input: { mode: 'region', q0: '부산광역시', q1: '동구' },
              },
            ],
          },
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'er-1',
                content: JSON.stringify({
                  ok: true,
                  result: { kind: 'collection', items: [{ name: '응급실' }] },
                }),
              },
            ],
          },
        },
      ],
      availableToolNames: ['nmc_emergency_search'],
    })

    expect(prompt).toBeUndefined()
  })

  test('collapse emergency loop ignores non-medical emergency call-box phrasing', () => {
    const prompt = buildNmcAedFollowupPromptIfNeeded({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '부산역 근처 비상벨이나 안심벨 위치 알려줘.',
          },
        },
        {
          type: 'assistant',
          message: {
            role: 'assistant',
            content: [
              {
                type: 'tool_use',
                id: 'er-1',
                name: 'nmc_emergency_search',
                input: { mode: 'region', q0: '부산광역시', q1: '동구' },
              },
            ],
          },
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'er-1',
                content: JSON.stringify({
                  ok: true,
                  result: { kind: 'collection', items: [{ name: '응급실' }] },
                }),
              },
            ],
          },
        },
      ],
      availableToolNames: ['nmc_aed_site_locate'],
    })

    expect(prompt).toBeUndefined()
  })

  test('implicit collapse emergency retrieval exposes POI, ER, and AED schemas', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D8',
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
            'locate 위치 장소 키워드 POI 랜드마크 캠퍼스 역 병원 좌표 kakao keyword 부산역',
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
        {
          tool_id: 'nmc_aed_site_locate',
          name: 'NMC AED Site Locate',
          primitive: 'find',
          policy_authority_url: 'https://www.nemc.or.kr/',
          source_mode: 'live',
          search_hint:
            'AED 자동심장충격기 자동제세동기 위치 국립중앙의료원 NMC emergency cardiac arrest defibrillator',
          llm_description: 'NMC AED site lookup.',
          input_schema_json: {
            type: 'object',
            properties: {
              q0: { type: 'string' },
              q1: { type: 'string' },
              lat: { type: 'number' },
              lon: { type: 'number' },
            },
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_current_observation',
          name: 'KMA Current Observation',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '현재 날씨 기온 강수 습도 풍속 초단기실황 관측',
          llm_description: 'Current weather observation adapter.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'mois_emergency_call_box_lookup',
          name: 'MOIS Emergency Call Box Lookup',
          primitive: 'find',
          policy_authority_url: 'https://www.safemap.go.kr/',
          source_mode: 'live',
          search_hint: '안전비상벨 긴급신고함 방범벨 emergency call box MOIS',
          llm_description: 'Safety emergency call box lookup.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'd'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
      5,
    )

    expect(selected).toContain('kakao_keyword_search')
    expect(selected).toContain('nmc_emergency_search')
    expect(selected).toContain('nmc_aed_site_locate')
    expect(selected).not.toContain('kma_current_observation')
    expect(selected).not.toContain('mois_emergency_call_box_lookup')

    const noPlaceSelected = selectTopKAdapterToolNamesForQuery(
      '사람이 쓰러졌어. 지금 어디로 가야 해?',
      5,
    )

    expect(noPlaceSelected).toContain('nmc_emergency_search')
    expect(noPlaceSelected).toContain('nmc_aed_site_locate')
  })

  test('lookup primitive prompt prefers direct concrete adapter calls', () => {
    expect(FIND_DESCRIPTION).toContain('Prefer concrete lookup adapter functions')
    expect(LOCATE_DESCRIPTION).toContain('concrete location adapter functions')

    const promptText = [
      FIND_TOOL_PROMPT,
      LOCATE_TOOL_PROMPT,
      SEND_TOOL_PROMPT,
      CHECK_TOOL_PROMPT,
    ].join('\n')

    expect(FIND_TOOL_PROMPT).toContain(
      'Call concrete adapter functions directly after their schemas are loaded',
    )
    expect(FIND_TOOL_PROMPT).toContain(
      'kma_current_observation({ base_date: "YYYYMMDD"',
    )
    expect(FIND_TOOL_PROMPT).toContain('Legacy root wrapper')
    expect(FIND_TOOL_PROMPT).toContain(
      'find accepts { tool_id, params } for old transcripts and compatibility paths',
    )
    expect(FIND_TOOL_PROMPT).not.toContain('Call find with { tool_id, params }')
    expect(FIND_TOOL_PROMPT).not.toContain(
      'call it through find({ tool_id, params })',
    )
    expect(promptText).not.toContain('The function name is find')
    expect(promptText).not.toContain('The function name is locate')
    expect(promptText).not.toContain('block and calls find directly')
  })

  test('root primitive schemas normalize same-primitive nested adapter envelopes', () => {
    expect(
      ResolveLocationPrimitive.inputSchema.parse({
        tool_id: 'locate',
        params: { tool_id: 'kakao_keyword_search', query: '해운대' },
      }),
    ).toEqual({
      tool_id: 'kakao_keyword_search',
      params: { query: '해운대' },
    })

    expect(
      ResolveLocationPrimitive.inputSchema.parse({
        tool_id: 'kakao_keyword_search',
        params: { tool_id: 'kakao_keyword_search', query: '김포공항' },
      }),
    ).toEqual({
      tool_id: 'kakao_keyword_search',
      params: { query: '김포공항' },
    })

    expect(
      VerifyPrimitive.inputSchema.parse({
        tool_id: 'check',
        params: {
          tool_id: 'mock_verify_mobile_id',
          scope_list: ['check:mobile_id.identity'],
        },
      }),
    ).toEqual({
      tool_id: 'mock_verify_mobile_id',
      params: { scope_list: ['check:mobile_id.identity'] },
    })

    expect(
      SubmitPrimitive.inputSchema.parse({
        tool_id: 'send',
        params: {
          tool_id: 'mock_submit_module_gov24_minwon',
          delegation_context: { token: 'test' },
        },
      }),
    ).toEqual({
      tool_id: 'mock_submit_module_gov24_minwon',
      params: { delegation_context: { token: 'test' } },
    })
  })

  test('locate root wrapper repairs missing query from the latest user location phrase', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D9',
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
          search_hint: 'locate 위치 장소 키워드 POI kakao keyword',
          llm_description: 'Kakao POI keyword search.',
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
          search_hint: 'reverse geocode region',
          llm_description: 'Coordinate to region lookup.',
          input_schema_json: {
            type: 'object',
            properties: { lat: { type: 'number' }, lon: { type: 'number' } },
            required: ['lat', 'lon'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'm'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    expect(
      deriveLocationQueryFromUserText(
        '해운대에서 산책 중인데 사람이 의식을 잃은 것 같아. 지금 어디로 가야 해?',
      ),
    ).toBe('해운대')
    expect(deriveLocationQueryFromUserText('부산역 근처에 사람이 쓰러졌어.')).toBe(
      '부산역',
    )

    const repaired = repairLocateQueryParamsFromConversation(
      { tool_id: 'kakao_keyword_search', params: {} },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '해운대에서 산책 중인데 사람이 의식을 잃은 것 같아. 지금 어디로 가야 해?',
          },
        },
      ] as any,
    )

    expect(repaired).toEqual({
      tool_id: 'kakao_keyword_search',
      params: { query: '해운대' },
    })
    expect(
      repairLocateQueryParamsFromConversation(
        { tool_id: 'kakao_coord_to_region', params: {} },
        [
          {
            type: 'user',
            message: { role: 'user', content: '해운대에서 산책 중이야.' },
          },
        ] as any,
      ),
    ).toEqual({ tool_id: 'kakao_coord_to_region', params: {} })
    expect(
      repairLocateQueryParamsFromConversation(
        { tool_id: 'kakao_keyword_search', params: {} },
        [
          {
            type: 'user',
            message: { role: 'user', content: '사람이 쓰러졌어. 지금 어디로 가야 해?' },
          },
        ] as any,
      ),
    ).toEqual({ tool_id: 'kakao_keyword_search', params: {} })
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

  test('lifestyle rain query selects KMA and POI location over unrelated public data', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C7',
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
          search_hint: '장소 키워드 POI 랜드마크 해운대 해수욕장 keyword place station',
          llm_description: 'Resolve POI/place names to coordinates.',
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
          search_hint: '현재 날씨 비 강수 우산 초단기실황 기상청 KMA current weather rain',
          llm_description: 'KMA current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_ultra_short_term_forecast',
          name: 'KMA Ultra Short Term Forecast',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '초단기예보 강수 비 우산 기상청 KMA precipitation forecast',
          llm_description: 'KMA ultra-short-term forecast.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_short_term_forecast',
          name: 'KMA Short Term Forecast',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '단기예보 내일 비 예보 기온 기상청 KMA weather forecast temperature',
          llm_description: 'KMA short-term weather forecast.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'bfc_funeral_area_fee',
          name: 'BFC Funeral Area Fee',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint: '부산 장례식장 시설 사용료 funeral area fee public data',
          llm_description: 'Busan funeral facility fee data.',
          input_schema_json: {
            type: 'object',
            properties: { page_no: { type: 'integer' } },
            required: ['page_no'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'a'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '퇴근하고 해운대 산책 갈 건데 지금 비 와? 우산 챙겨야 해?',
      5,
    )

    expect(selected).toContain('kakao_keyword_search')
    expect(selected).toContain('kma_current_observation')
    expect(selected).toContain('kma_ultra_short_term_forecast')
    expect(selected).not.toContain('bfc_funeral_area_fee')

    const forecastSelected = selectTopKAdapterToolNamesForQuery(
      '내일 아침 부산 사상구 비 예보랑 기온 알려줘',
      5,
    )

    expect(forecastSelected).toContain('kma_short_term_forecast')
    expect(forecastSelected).not.toContain('bfc_funeral_area_fee')
  })

  test('public safety and assistive location wording keeps dedicated adapters', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C8',
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
          search_hint: '장소 키워드 POI 위치 keyword place station',
          llm_description: 'Resolve POI/place names to coordinates.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'mois_emergency_call_box_lookup',
          name: 'MOIS Emergency Call Box',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint: '안전비상벨 비상벨 긴급신고함 위치 emergency call box safety bell',
          llm_description: 'Safety bell and emergency call-box location data.',
          input_schema_json: {
            type: 'object',
            properties: { road_address: { type: 'string' } },
            additionalProperties: false,
          },
        },
        {
          tool_id: 'gyeryong_assistive_device_charging_place_locate',
          name: 'Gyeryong Assistive Charger',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint: '계룡시 전동보장구 전동휠체어 보장구 충전소 충전 장소 accessibility charger',
          llm_description: 'Assistive-device charger location data.',
          input_schema_json: {
            type: 'object',
            properties: { current_page: { type: 'integer' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'b'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    expect(
      selectTopKAdapterToolNamesForQuery(
        '가까운 비상벨이나 긴급신고함 위치 알려줘',
        5,
      ),
    ).toContain('mois_emergency_call_box_lookup')
    expect(
      selectTopKAdapterToolNamesForQuery('계룡시 전동보장구 충전소 어디 있어?', 5),
    ).toContain('gyeryong_assistive_device_charging_place_locate')
  })

  test('hospital detail wording keeps HIRA detail adapter', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C9',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'hira_hospital_search',
          name: 'HIRA Hospital Search',
          primitive: 'find',
          policy_authority_url: 'https://www.hira.or.kr/',
          source_mode: 'live',
          search_hint: '병원 검색 진료과목 의료기관 정보 hospital search medical specialty',
          llm_description: 'Hospital and clinic search adapter.',
          input_schema_json: {
            type: 'object',
            properties: { xPos: { type: 'number' }, yPos: { type: 'number' } },
            required: ['xPos', 'yPos'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'hira_medical_institution_detail',
          name: 'HIRA Medical Institution Detail',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint: '의료기관 상세정보 병원 상세 진료과 진료과목 진료시간 ykiho hospital detail',
          llm_description: 'HIRA hospital detail adapter using ykiho.',
          input_schema_json: {
            type: 'object',
            properties: { ykiho: { type: 'string' } },
            required: ['ykiho'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'c'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const selected = selectTopKAdapterToolNamesForQuery(
      '해운대 근처 병원 상세정보랑 진료과 확인해줘',
      5,
    )

    expect(selected).toContain('hira_hospital_search')
    expect(selected).toContain('hira_medical_institution_detail')
  })

  test('airport aviation wording rejects locate and ordinary weather substitution', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9E0',
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
          search_hint: 'locate 위치 장소 키워드 POI 공항 kakao keyword',
          llm_description: 'POI location search.',
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
          search_hint: '현재 기상 실황 관측 weather observation',
          llm_description: 'Ordinary KMA current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'METAR SPECI 해독자료 항공기상 공항기상 시정 풍향 풍속 RKPK RKSS',
          llm_description: 'Decoded METAR airport weather.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' }, help: { type: 'integer' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'e'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const context = {
      options: { tools: [] },
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘',
          },
        },
      ],
    } as any

    const locateResult = await ResolveLocationPrimitive.validateInput!(
      { tool_id: 'kakao_keyword_search', params: { query: '김해공항' } },
      context,
    )
    expect(locateResult.result).toBe(false)
    if (!locateResult.result) {
      expect(locateResult.message).toContain('kma_apihub_url_air_metar_decoded')
    }

    const weatherTool = getAdapterToolByName('kma_current_observation')
    expect(weatherTool).toBeDefined()
    const weatherResult = await weatherTool!.validateInput!({ nx: 98, ny: 76 }, context)
    expect(weatherResult.result).toBe(false)
    if (!weatherResult.result) {
      expect(weatherResult.message).toContain('airport METAR')
    }
  })

  test('airport aviation guard ignores synthetic available adapter context', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9E2',
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
          search_hint: 'locate 위치 장소 키워드 POI 공항 kakao keyword',
          llm_description: 'POI location search.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'METAR SPECI 해독자료 항공기상 공항기상 시정 풍향 풍속 RKPK RKSS',
          llm_description: 'Decoded METAR airport weather.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' }, help: { type: 'integer' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'a'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const context = {
      options: { tools: [] },
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?',
          },
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '<available_adapters query="부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?">\n' +
              'kma_apihub_url_air_metar_decoded: METAR SPECI 김해공항 김포공항 시정 visibility\n' +
              '</available_adapters>',
          },
        },
      ],
    } as any

    const locateResult = await ResolveLocationPrimitive.validateInput!(
      { tool_id: 'kakao_keyword_search', params: { query: '부산역' } },
      context,
    )
    expect(locateResult.result).toBe(true)
  })

  test('airport aviation guard reads top-level SDK user messages', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9E3',
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
          search_hint: 'locate 위치 장소 키워드 POI 공항 kakao keyword',
          llm_description: 'POI location search.',
          input_schema_json: {
            type: 'object',
            properties: { query: { type: 'string' } },
            required: ['query'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_apihub_url_air_metar_decoded',
          name: 'KMA APIHub decoded METAR',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'METAR SPECI 해독자료 항공기상 공항기상 시정 풍향 풍속 RKPK RKSS',
          llm_description: 'Decoded METAR airport weather.',
          input_schema_json: {
            type: 'object',
            properties: { org: { type: 'string' }, help: { type: 'integer' } },
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'd'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const context = {
      options: { tools: [] },
      messages: [
        {
          role: 'user',
          content: '오늘 밤 김해에서 김포 가는데 비행기 뜰만해? 바람이랑 시정도 봐줘',
        },
      ],
    } as any

    const locateResult = await ResolveLocationPrimitive.validateInput!(
      { tool_id: 'kakao_keyword_search', params: { query: '김해공항' } },
      context,
    )
    expect(locateResult.result).toBe(false)
  })

  test('protected certificate wording rejects find aliases for identity tools', async () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9E1',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'mock_verify_module_simple_auth',
          name: 'Simple Auth Module',
          primitive: 'check',
          policy_authority_url: 'https://www.gov.kr/',
          source_mode: 'mock',
          search_hint: '간편인증 소득금액증명원 증명원 정부24 홈택스 simple auth',
          llm_description: 'Mock simple-auth verification adapter.',
          input_schema_json: {
            type: 'object',
            properties: { scope_list: { type: 'array', items: { type: 'string' } } },
            required: ['scope_list'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'mock_verify_mobile_id',
          name: 'Mobile ID',
          primitive: 'check',
          policy_authority_url: 'https://www.mobileid.go.kr/',
          source_mode: 'mock',
          search_hint: '모바일신분증 모바일 ID 본인확인 mobile id',
          llm_description: 'Mock Mobile ID verification adapter.',
          input_schema_json: {
            type: 'object',
            properties: { scope_list: { type: 'array', items: { type: 'string' } } },
            required: ['scope_list'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'f'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const context = {
      options: { tools: [] },
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '소득금액증명원 오늘 바로 필요해. 모바일신분증이나 간편인증으로 처리해줘',
          },
        },
      ],
    } as any

    const aliasResult = await LookupPrimitive.validateInput!(
      { tool_id: 'mobile_id', params: {} },
      context,
    )
    expect(aliasResult.result).toBe(false)
    if (!aliasResult.result) {
      expect(aliasResult.message).toContain('mock_verify_mobile_id')
      expect(aliasResult.message).toContain('check')
    }

    const checkThroughFind = await LookupPrimitive.validateInput!(
      {
        tool_id: 'mock_verify_module_simple_auth',
        params: { scope_list: ['check:ganpyeon.identity'] },
      },
      context,
    )
    expect(checkThroughFind.result).toBe(false)
    if (!checkThroughFind.result) {
      expect(checkThroughFind.message).toContain('Do not call check adapters through find')
    }
  })

  test('protected certificate wording forces concrete check adapter tool choice', () => {
    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: {
            role: 'user',
            content: '소득금액증명원 오늘 바로 필요해. 간편인증으로 처리해야 해',
          },
        },
      ] as any,
      tools: [
        toolNamed('find'),
        toolNamed('mobile_id'),
        toolNamed('mock_verify_mobile_id'),
        toolNamed('mock_verify_module_simple_auth'),
        toolNamed('mock_verify_ganpyeon_injeung'),
      ],
    })

    expect(override).toEqual({
      type: 'tool',
      name: 'mock_verify_module_simple_auth',
    })
  })

  test('protected certificate wording retrieves and forces check adapter before unrelated find tools', () => {
    clearManifestCache()
    ingestManifestFrame({
      kind: 'adapter_manifest_sync',
      version: '1.0',
      session_id: 'test-session',
      correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9A2',
      ts: new Date().toISOString(),
      role: 'backend',
      frame_seq: 0,
      entries: [
        {
          tool_id: 'koroad_accident_hazard_search',
          name: 'Koroad Hazard',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/',
          source_mode: 'live',
          search_hint: '도로 사고 위험 지역',
          llm_description: 'Road accident hazard lookup.',
          input_schema_json: {
            type: 'object',
            properties: { adm_cd: { type: 'string' }, year: { type: 'integer' } },
            required: ['adm_cd', 'year'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'kma_current_observation',
          name: 'KMA Current Observation',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: '기상청 현재 날씨 관측',
          llm_description: 'Current weather observation.',
          input_schema_json: {
            type: 'object',
            properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
            required: ['nx', 'ny'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'mock_verify_module_simple_auth',
          name: 'Simple Auth Module',
          primitive: 'check',
          policy_authority_url: 'https://www.gov.kr/',
          source_mode: 'mock',
          search_hint: '간편인증 소득금액증명원 증명원 홈택스 정부24 simple auth',
          llm_description: 'Mock simple-auth verification adapter.',
          input_schema_json: {
            type: 'object',
            properties: { scope_list: { type: 'array', items: { type: 'string' } } },
            required: ['scope_list'],
            additionalProperties: false,
          },
        },
        {
          tool_id: 'mock_verify_mobile_id',
          name: 'Mobile ID',
          primitive: 'check',
          policy_authority_url: 'https://www.mobileid.go.kr/',
          source_mode: 'mock',
          search_hint: '모바일 신분증 모바일ID 본인확인',
          llm_description: 'Mock Mobile ID verification adapter.',
          input_schema_json: {
            type: 'object',
            properties: { scope_list: { type: 'array', items: { type: 'string' } } },
            required: ['scope_list'],
            additionalProperties: false,
          },
        },
      ],
      manifest_hash: 'b'.repeat(64),
      emitter_pid: 12345,
    } satisfies AdapterManifestSyncFrame)

    const query = '소득금액증명원 오늘 바로 필요해. 간편인증이나 모바일 신분증으로 처리할 수 있어?'
    const selected = selectTopKAdapterToolNamesForQuery(query, 5)
    expect(selected[0]).toBe('mock_verify_mobile_id')
    expect(selected).toContain('mock_verify_module_simple_auth')
    expect(selected).not.toContain('koroad_accident_hazard_search')
    expect(selected).not.toContain('kma_current_observation')

    const override = selectUmmayaToolChoiceOverride({
      messages: [
        {
          type: 'user',
          message: { role: 'user', content: query },
        },
      ] as any,
      tools: [toolNamed('find'), toolNamed('check'), toolNamed('ToolSearch')],
    })
    expect(override).toEqual({
      type: 'tool',
      name: 'mock_verify_mobile_id',
    })
  })

  test('protected certificate wording suppresses further tools after a check attempt', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '소득금액증명원 오늘 바로 필요해. 간편인증으로 발급 가능해?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'check-1',
              name: 'mock_verify_module_simple_auth',
              input: { scope_list: ['check:ganpyeon.identity'] },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'check-1',
              content: JSON.stringify({
                ok: false,
                error: { kind: 'permission_denied', message: 'denied' },
              }),
            },
          ],
        },
      },
    ] as any
    const tools = [
      toolNamed('check'),
      toolNamed('mock_verify_module_simple_auth'),
      toolNamed('mock_verify_mobile_id'),
    ]

    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({ messages, tools }),
    ).toBe(true)
    expect(selectUmmayaToolChoiceOverride({ messages, tools })).toBeUndefined()
    expect(buildProtectedCheckCompletionPromptIfNeeded({ messages })).toContain(
      'Protected-domain evidence chain complete',
    )
  })

  test('protected certificate final answer repair withholds printed tool-call text', () => {
    const messages = [
      {
        type: 'user',
        message: {
          role: 'user',
          content: '소득금액증명원 오늘 바로 필요해. 간편인증이나 모바일 신분증으로 처리할 수 있어?',
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'check-1',
              name: 'mock_verify_mobile_id',
              input: { scope_list: ['check:mobile_id.identity'] },
            },
          ],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'check-1',
              content: JSON.stringify({
                ok: false,
                error: { kind: 'permission_denied', message: 'denied' },
              }),
            },
          ],
        },
      },
    ] as any
    const candidate = {
      type: 'assistant',
      message: {
        role: 'assistant',
        content: [
          {
            type: 'text',
            text: '<tool_call>{"name":"check_mobile_id_auth","arguments":{"service_code":"INCOME_CERTIFICATE"}}</tool_call>',
          },
        ],
      },
    } as any

    expect(
      shouldWithholdProtectedCheckToolCallText({ messages, candidate }),
    ).toBe(true)
    expect(
      buildProtectedCheckFinalAnswerRepairPromptIfNeeded({
        messages: [...messages, candidate],
      }),
    ).toContain('Protected-domain final-answer repair')
  })
})
