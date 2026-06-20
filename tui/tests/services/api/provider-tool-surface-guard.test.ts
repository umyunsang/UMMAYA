import { describe, expect, test } from 'bun:test'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../../src/services/api/adapterManifest.js'
import { createAssistantMessage } from '../../../src/utils/messages.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  createDiagnosticsTarget,
  getToolNames,
  ingestCivilDeathSurfaceManifest,
  ingestDjtcSurfaceManifest,
  ingestGov24Manifest,
  ingestHealthLocationManifest,
  ingestHousingHandoffManifest,
  ingestMetarManifest,
  ingestTaxManifest,
  ingestUtilitySurfaceManifest,
  ingestWelfareSurfaceManifest,
  readAdapterSelection,
  serializedMessages,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

const HOMETAX_LOOKUP_TOOL_NAME = 'mock_lookup_module_hometax_simplified'
const VERIFY_TOOL_NAME = 'mock_verify_module_modid'
const SUBMIT_TOOL_NAME = 'mock_submit_module_hometax_taxreturn'
const TAX_PROMPT =
  '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.'
const HLT_PROMPT =
  '아이가 밤에 열이 높아. 지금 갈 수 있는 응급실이나 야간진료 병원 찾고 보험 적용되는지도 알려줘.'
const HLT_LOCATED_NIGHT_HOSPITAL_PROMPT =
  '부산역 근처 야간에 바로 갈 수 있는 병원 알려줘.'
const HLT_RELATIVE_ER_PROMPT =
  '주위에 지금 바로 갈수있는 응급실 알려줘.'
const CIV_BIRTH_PROMPT =
  '아기가 태어났어. 출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 등록까지 도와줘.'
const WEL_PREGNANCY_PROMPT =
  '임신했는데 받을 수 있는 지원금, 진료비 바우처, 출산휴가 관련 신청을 한 번에 정리하고 신청해줘.'
const WEL_LOW_INCOME_PROMPT =
  '생활비가 부족해. 내가 받을 수 있는 기초생활, 주거급여, 긴급복지 지원을 찾아서 신청 가능한 것부터 진행해줘.'
const UTL_UTILITY_PROMPT =
  '전기, 수도, 도시가스 요금 이번 달 얼마나 나왔는지 보고 자동이체 신청까지 해줘.'
const HOU_FIRST_HOME_PROMPT =
  '생애최초 주택구입인데 대출, 취득세 감면, 등기, 전입까지 빠뜨리지 않게 순서대로 진행해줘.'
const CIV_DEATH_PROMPT =
  '아버지가 돌아가셨어. 사망신고, 장례 지원, 국민연금 유족급여, 재산 관련 절차를 순서대로 알려줘.'
const DJTC_SEGMENT_PROMPT =
  '대전 도시철도 0101역에서 0102역까지 소요시간, 거리, 요금을 DJTC 공식 도구로 조회해줘. 한전이나 날씨나 결제 도구로 대체하지 마.'
const GOV24_READ_ONLY_PROMPT =
  '정부24 주민등록등본 발급 가능 여부와 준비물을 확인해줘.'
const GOV24_SUBMIT_PROMPT =
  '정부24에서 주민등록등본 온라인 발급 신청을 진행해줘. 접수번호가 나오면 알려줘.'
const SUPPORT_WORKSPACE_PROMPT =
  '이 작업공간에서 `docs/configuration.md`와 `docs/vision.md`를 찾아서 설정 관련 핵심만 요약해줘. 파일은 수정하지 마.'
const ROOT_PRIMITIVE_TOOL_NAMES = ['find', 'locate', 'check', 'send'] as const
const NON_ADAPTER_PROVIDER_TOOL_NAMES = [
  'workspace_read',
  'workspace_grep',
  'workspace_bash',
  'workspace_write',
  'workspace_edit',
  'workspace_glob',
  'document',
  'ToolSearch',
] as const
const HEALTH_LOCATION_TOOL_NAMES = [
  'kakao_keyword_search',
  'kakao_address_search',
  'hira_hospital_search',
  'hira_medical_institution_detail',
  'kma_current_observation',
  'kma_short_term_forecast',
  'kma_ultra_short_term_forecast',
] as const
const WELFARE_TOOL_NAMES = [
  'mohw_welfare_eligibility_search',
  'mock_welfare_application_submit_v1',
] as const
const UTILITY_TOOL_NAMES = [
  'kepco_contract_power_usage',
  'mock_kftc_opengiro_bill_send_v1',
  'mock_kftc_opengiro_payment_send_v1',
] as const
const STALE_LOCATION_WEATHER_TOOL_NAMES = [
  'kakao_keyword_search',
  'kakao_address_search',
  'kakao_coord_to_region',
  'kma_current_observation',
  'kma_short_term_forecast',
  'kma_ultra_short_term_forecast',
  'kma_forecast_fetch',
  'kma_apihub_url_air_amos_minute',
] as const
const CIV_DEATH_TOOL_NAMES = [
  'bfc_funeral_area_fee',
  'reb_real_estate_stat_table',
  'mohw_welfare_eligibility_search',
] as const
const DJTC_SEGMENT_TOOL_NAME = 'djtc_subway_segment_fare_time_check'
const STALE_DJTC_SUBSTITUTE_TOOL_NAMES = [
  'kakao_keyword_search',
  'kma_current_observation',
  'kepco_contract_power_usage',
  'mock_kftc_opengiro_payment_send_v1',
] as const
const NONEXISTENT_SURVIVOR_PENSION_TOOL_NAMES = [
  'nps_survivor_pension_lookup',
  'nps_survivor_pension_submit',
] as const
const GOV24_LOOKUP_TOOL_NAME = 'mock_lookup_module_gov24_certificate'
const GOV24_VERIFY_TOOL_NAME = 'mock_verify_module_simple_auth'
const GOV24_SUBMIT_TOOL_NAME = 'mock_submit_module_gov24_minwon'
const KMA_CURRENT_OBSERVATION_TOOL_NAME = 'kma_current_observation'
const AIRKOREA_CTPRVN_AIR_QUALITY_TOOL_NAME = 'airkorea_ctprvn_air_quality'
const WEATHER_AIR_QUALITY_PROMPT =
  '오늘 부산 사하구 날씨랑 미세먼지 상태를 확인해줘. 날씨와 대기질 출처를 나눠서 알려줘.'

function publicDataEntry(
  toolId: string,
  searchHint: string,
  inputProperties: Record<string, unknown>,
) {
  return {
    tool_id: toolId,
    name: toolId,
    primitive: 'find' as const,
    policy_authority_url: 'https://www.data.go.kr/',
    source_mode: 'live' as const,
    search_hint: searchHint,
    llm_description: searchHint,
    input_schema_json: {
      type: 'object',
      properties: inputProperties,
      required: Object.keys(inputProperties),
      additionalProperties: false,
    },
  }
}

function ingestWeatherAirQualityManifest(): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'provider-surface-weather-air',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9WA',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      publicDataEntry(
        KMA_CURRENT_OBSERVATION_TOOL_NAME,
        '기상청 KMA 날씨 기상 현재 관측 부산 사하구',
        { location: { type: 'string' } },
      ),
      publicDataEntry(
        AIRKOREA_CTPRVN_AIR_QUALITY_TOOL_NAME,
        'AirKorea 에어코리아 대기질 미세먼지 초미세먼지 부산',
        { sido_name: { type: 'string' } },
      ),
      publicDataEntry(
        'moj_village_lawyer_lookup',
        '법무부 마을변호사 부산 사하구',
        { region: { type: 'string' } },
      ),
    ],
    manifest_hash: 'a'.repeat(64),
    emitter_pid: 12345,
  })
}

function locatedNightHospitalAfterCurrentLocationMessages() {
  return [
    createUserMessage({ content: HLT_LOCATED_NIGHT_HOSPITAL_PROMPT }),
    createAssistantMessage({
      content: [{
        type: 'tool_use',
        id: 'toolu-current-busan-station-locate',
        name: 'kakao_keyword_search',
        input: { query: '부산역' },
      }],
    }),
    createUserMessage({
      content: [{
        type: 'tool_result',
        tool_use_id: 'toolu-current-busan-station-locate',
        content: JSON.stringify({
          ok: true,
          data: {
            status: 'ok',
            result: {
              kind: 'bundle',
              poi: {
                kind: 'place',
                name: '부산역',
                address_name: '부산 동구 초량동',
                road_address: '부산 동구 중앙대로 206',
                lat: 35.11520340622514,
                lon: 129.04154985192403,
              },
            },
          },
        }),
      }],
    }),
  ]
}

function relativeEmergencyAfterCurrentLocationMessages() {
  return [
    createUserMessage({ content: HLT_RELATIVE_ER_PROMPT }),
    createAssistantMessage({
      content: [{
        type: 'tool_use',
        id: 'toolu-current-neighborhood-locate',
        name: 'kakao_address_search',
        input: { query: '다대1동' },
      }],
    }),
    createUserMessage({
      content: [{
        type: 'tool_result',
        tool_use_id: 'toolu-current-neighborhood-locate',
        content: JSON.stringify({
          ok: true,
          data: {
            status: 'ok',
            result: {
              kind: 'bundle',
              coords: {
                lat: 35.059152,
                lon: 128.971316,
                nx: 96,
                ny: 74,
              },
              region: {
                address_name: '부산 사하구 다대1동',
              },
            },
          },
        }),
      }],
    }),
  ]
}

function relativeEmergencyAfterPriorBundleLocationMessages() {
  return [
    createUserMessage({ content: '다대1동 지금 날씨알려줘' }),
    createAssistantMessage({
      content: [{
        type: 'tool_use',
        id: 'toolu-prior-dadae-location',
        name: 'kakao_address_search',
        input: { query: '다대1동' },
      }],
    }),
    createUserMessage({
      content: [{
        type: 'tool_result',
        tool_use_id: 'toolu-prior-dadae-location',
        content: JSON.stringify({
          ok: true,
          result: {
            kind: 'bundle',
            coords: {
              lat: 35.059152,
              lon: 128.971316,
              nx: 96,
              ny: 74,
            },
            region: {
              address_name: '부산 사하구 다대1동',
            },
          },
        }),
      }],
    }),
    createAssistantMessage({
      content: [{
        type: 'text',
        text: '부산 사하구 다대1동 현재 날씨를 확인했습니다.',
      }],
    }),
    createUserMessage({ content: HLT_RELATIVE_ER_PROMPT }),
  ]
}

function restoreRouteDiagnostics(previousValue: string | undefined): void {
  if (previousValue === undefined) {
    delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
    return
  }
  process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = previousValue
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function toolParameters(
  request: Parameters<typeof getToolNames>[0],
  toolName: string,
): Record<string, unknown> {
  const tool = request.tools?.find(candidate => candidate.function?.name === toolName)
  if (!tool?.function) {
    throw new Error(`Expected provider request to contain ${toolName}.`)
  }
  const fn = tool.function as { readonly parameters?: unknown }
  if (!isRecord(fn.parameters)) {
    throw new Error(`Expected ${toolName} to expose provider parameters.`)
  }
  return fn.parameters
}

function postLookupMessages() {
  const lookupAssistant = createAssistantMessage({
    content: [
      {
        type: 'tool_use',
        id: 'toolu-tax001-completed-lookup',
        name: HOMETAX_LOOKUP_TOOL_NAME,
        input: { year: 2025, resident_id_prefix: '000000' },
      },
    ],
  })
  return [
    createUserMessage({ content: TAX_PROMPT }),
    lookupAssistant,
    createUserMessage({
      content: [
        {
          type: 'tool_result',
          tool_use_id: 'toolu-tax001-completed-lookup',
          content: JSON.stringify({
            ok: true,
            tool_id: HOMETAX_LOOKUP_TOOL_NAME,
            scope: 'find:hometax.simplified',
          }),
        },
      ],
      toolUseResult: {
        ok: true,
        tool_id: HOMETAX_LOOKUP_TOOL_NAME,
        scope: 'find:hometax.simplified',
      },
    }),
  ]
}

function expectNoNonAdapterProviderTools(toolNames: readonly string[]): void {
  for (const toolName of [
    ...ROOT_PRIMITIVE_TOOL_NAMES,
    ...NON_ADAPTER_PROVIDER_TOOL_NAMES,
  ]) {
    expect(toolNames).not.toContain(toolName)
  }
}

function expectProviderToolsMatchSelectedAdapters(params: {
  readonly toolNames: readonly string[]
  readonly selectedAdapterToolNames: readonly string[]
}): void {
  expect([...params.toolNames].sort()).toEqual(
    [...params.selectedAdapterToolNames].sort(),
  )
}

describe('provider request tool surface guard', () => {
  test('forces a concrete adapter choice for compositional weather and air-quality requests', async () => {
    await withFriendliEnv(async () => {
      ingestWeatherAirQualityManifest()

      const exchange = await captureProviderExchange({
        messages: [createUserMessage({ content: WEATHER_AIR_QUALITY_PROMPT })],
      })

      const toolNames = getToolNames(exchange.request)
      expect(toolNames).toContain(KMA_CURRENT_OBSERVATION_TOOL_NAME)
      expect(toolNames).toContain(AIRKOREA_CTPRVN_AIR_QUALITY_TOOL_NAME)
      expect(toolNames).not.toContain('WebSearch')
      expect(toolNames).not.toContain('WebFetch')
      expect(exchange.request.tool_choice?.type).toBe('function')
      expect(toolNames).toContain(exchange.request.tool_choice?.function.name)
      expect(serializedMessages(exchange.request)).toContain(
        `Mandatory tool call: the host selected ${exchange.request.tool_choice?.function.name}`,
      )
    })
  })

  test('moves forced adapter choice past successful prior public-data tool results', async () => {
    await withFriendliEnv(async () => {
      ingestWeatherAirQualityManifest()
      const airQualityToolUseId = 'toolu-airquality-done'

      const exchange = await captureProviderExchange({
        messages: [
          createUserMessage({ content: WEATHER_AIR_QUALITY_PROMPT }),
          createAssistantMessage({
            content: [{
              type: 'tool_use',
              id: airQualityToolUseId,
              name: AIRKOREA_CTPRVN_AIR_QUALITY_TOOL_NAME,
              input: { sido_name: '부산' },
            }],
          }),
          createUserMessage({
            content: [{
              type: 'tool_result',
              tool_use_id: airQualityToolUseId,
              content: JSON.stringify({
                ok: true,
                result: { kind: 'collection', items: [] },
              }),
            }],
          }),
        ],
      })

      expect(getToolNames(exchange.request)).toContain(
        AIRKOREA_CTPRVN_AIR_QUALITY_TOOL_NAME,
      )
      expect(getToolNames(exchange.request)).toContain(KMA_CURRENT_OBSERVATION_TOOL_NAME)
      expect(exchange.request.tool_choice).toEqual({
        type: 'function',
        function: { name: KMA_CURRENT_OBSERVATION_TOOL_NAME },
      })
    })
  })

  test('exposes initial TAX-001 Hometax adapters without workspace or support tools', async () => {
    // Given: a fresh TAX-001 provider turn with the tax adapter manifest synced.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestTaxManifest('f')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: TAX_PROMPT })],
        })

        // Then: concrete TAX-001 adapters are exposed and root primitives are displaced.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain(HOMETAX_LOOKUP_TOOL_NAME)
        expect(toolNames).toContain(VERIFY_TOOL_NAME)
        expect(toolNames).toContain(SUBMIT_TOOL_NAME)
        expectNoNonAdapterProviderTools(toolNames)
        expect(selection.final_adapter_tools).toContain(HOMETAX_LOOKUP_TOOL_NAME)
        expect(selection.final_adapter_tools).toContain(VERIFY_TOOL_NAME)
        expect(selection.final_adapter_tools).toContain(SUBMIT_TOOL_NAME)
        expectProviderToolsMatchSelectedAdapters({
          toolNames,
          selectedAdapterToolNames: selection.final_adapter_tools,
        })
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('exposes post-lookup TAX-001 verify and submit while disabling lookup and root check', async () => {
    // Given: the query loop has completed Hometax lookup and disabled only that lookup adapter.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestTaxManifest('f')
      try {
        // When: the provider request is built from the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: postLookupMessages(),
          disabledProviderToolNames: [HOMETAX_LOOKUP_TOOL_NAME],
        })

        // Then: manifest top-K cannot re-expose the completed lookup, but verify remains available.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain(VERIFY_TOOL_NAME)
        expect(toolNames).toContain(SUBMIT_TOOL_NAME)
        expect(toolNames).not.toContain(HOMETAX_LOOKUP_TOOL_NAME)
        expectNoNonAdapterProviderTools(toolNames)
        expect(selection.final_adapter_tools).toContain(VERIFY_TOOL_NAME)
        expect(selection.final_adapter_tools).toContain(SUBMIT_TOOL_NAME)
        expect(selection.final_adapter_tools).not.toContain(HOMETAX_LOOKUP_TOOL_NAME)
        expectProviderToolsMatchSelectedAdapters({
          toolNames,
          selectedAdapterToolNames: selection.final_adapter_tools,
        })
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('keeps hidden final-answer repair prompt out of post-lookup TAX-001 provider routing', async () => {
    // Given: TAX lookup succeeded, then the loop injected a hidden repair prompt for final-answer recovery.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestTaxManifest('m')
      try {
        // When: the provider request is built with lookup disabled for the next turn.
        const exchange = await captureProviderExchange({
          messages: [
            ...postLookupMessages(),
            createUserMessage({
              content:
                'Final answer repair: successful tool_result evidence already exists, but the previous assistant message was still a plan or promise to answer later.',
              isMeta: true,
            }),
          ],
          disabledProviderToolNames: [HOMETAX_LOOKUP_TOOL_NAME],
        })

        // Then: routing still uses the original citizen tax prompt, not the hidden generic repair text.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain(VERIFY_TOOL_NAME)
        expect(toolNames).toContain(SUBMIT_TOOL_NAME)
        expect(toolNames).not.toContain(HOMETAX_LOOKUP_TOOL_NAME)
        expect(toolNames).not.toContain('kakao_address_search')
        expect(toolNames).not.toContain('kma_current_observation')
        expectNoNonAdapterProviderTools(toolNames)
        expect(selection.final_adapter_tools).toContain(VERIFY_TOOL_NAME)
        expect(selection.final_adapter_tools).toContain(SUBMIT_TOOL_NAME)
        expect(selection.final_adapter_tools).not.toContain(HOMETAX_LOOKUP_TOOL_NAME)
        expect(selection.final_adapter_tools).not.toContain('kakao_address_search')
        expect(selection.final_adapter_tools).not.toContain('kma_current_observation')
        expectProviderToolsMatchSelectedAdapters({
          toolNames,
          selectedAdapterToolNames: selection.final_adapter_tools,
        })
        expect(serializedMessages(exchange.request)).toContain(
          'Final answer repair: successful tool_result evidence already exists',
        )
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('withholds Gov24 submit surface for read-only certificate guidance', async () => {
    // Given: a citizen asks only whether a Gov24 certificate can be issued and what to prepare.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestGov24Manifest('g')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: GOV24_READ_ONLY_PROMPT })],
        })

        // Then: the model can inspect the Gov24 lookup adapter, but cannot jump into check/send.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain(GOV24_LOOKUP_TOOL_NAME)
        expect(toolNames).not.toContain(GOV24_VERIFY_TOOL_NAME)
        expect(toolNames).not.toContain(GOV24_SUBMIT_TOOL_NAME)
        expect(selection.final_adapter_tools).toContain(GOV24_LOOKUP_TOOL_NAME)
        expect(selection.final_adapter_tools).not.toContain(GOV24_VERIFY_TOOL_NAME)
        expect(selection.final_adapter_tools).not.toContain(GOV24_SUBMIT_TOOL_NAME)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('keeps Gov24 check and submit surface for explicit minwon application', async () => {
    // Given: a citizen explicitly asks UMMAYA to proceed with a Gov24 application.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestGov24Manifest('i')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: GOV24_SUBMIT_PROMPT })],
        })

        // Then: the protected application chain remains available.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain(GOV24_VERIFY_TOOL_NAME)
        expect(toolNames).toContain(GOV24_SUBMIT_TOOL_NAME)
        expect(selection.final_adapter_tools).toContain(GOV24_VERIFY_TOOL_NAME)
        expect(selection.final_adapter_tools).toContain(GOV24_SUBMIT_TOOL_NAME)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('withholds location-dependent health adapters when HLT prompt has no location', async () => {
    // Given: the HLT-001 prompt asks for nearby care but does not provide a usable location.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('h')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: HLT_PROMPT })],
        })

        // Then: location-dependent health tools are withheld until the citizen gives a location.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        for (const toolName of HEALTH_LOCATION_TOOL_NAMES) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        expect(toolNames).toEqual([])
        expect(selection.final_adapter_tools).toEqual([])
        expect(serializedMessages(exchange.request)).toContain(HLT_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('keeps located night-hospital surface location-first before current location result', async () => {
    // Given: the citizen gives a location and asks for night hospital care.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('h')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: HLT_LOCATED_NIGHT_HOSPITAL_PROMPT })],
        })

        // Then: only location adapters are available until the current turn has a successful location result.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain('kakao_keyword_search')
        expect(toolNames).toContain('kakao_address_search')
        expect(toolNames).not.toContain('hira_hospital_search')
        expect(toolNames).not.toContain('nmc_emergency_search')
        expect(selection.final_adapter_tools).not.toContain('hira_hospital_search')
        expect(toolNames).not.toContain('kma_current_observation')
        expect(toolNames).not.toContain('kma_short_term_forecast')
        expect(toolNames).not.toContain('kma_ultra_short_term_forecast')
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('exposes located night-hospital medical adapters after current location result', async () => {
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('h')
      try {
        const exchange = await captureProviderExchange({
          messages: locatedNightHospitalAfterCurrentLocationMessages(),
        })

        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).not.toContain('kakao_keyword_search')
        expect(toolNames).not.toContain('kakao_address_search')
        expect(selection.final_adapter_tools).not.toContain('kakao_keyword_search')
        expect(selection.final_adapter_tools).not.toContain('kakao_address_search')
        expect(toolNames).toContain('hira_hospital_search')
        expect(toolNames).toContain('nmc_emergency_search')
        expect(selection.final_adapter_tools).toContain('hira_hospital_search')
        expect(selection.final_adapter_tools).toContain('nmc_emergency_search')
        expect(toolNames).not.toContain('kma_current_observation')
        expect(toolNames).not.toContain('kma_short_term_forecast')
        expect(toolNames).not.toContain('kma_ultra_short_term_forecast')
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('keeps relative-location emergency surface location-first before current location result', async () => {
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('h')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: HLT_RELATIVE_ER_PROMPT })],
        })

        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain('kakao_keyword_search')
        expect(toolNames).toContain('kakao_address_search')
        expect(toolNames).not.toContain('nmc_emergency_search')
        expect(toolNames).not.toContain('hira_hospital_search')
        expect(selection.final_adapter_tools).not.toContain('nmc_emergency_search')
        expect(selection.final_adapter_tools).not.toContain('hira_hospital_search')
        expect(toolNames).not.toContain('kma_current_observation')
        expect(toolNames).not.toContain('kma_short_term_forecast')
        expect(toolNames).not.toContain('kma_ultra_short_term_forecast')
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('exposes relative-location emergency medical adapters after current location result', async () => {
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('h')
      try {
        const exchange = await captureProviderExchange({
          messages: relativeEmergencyAfterCurrentLocationMessages(),
        })

        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).not.toContain('kakao_keyword_search')
        expect(toolNames).not.toContain('kakao_address_search')
        expect(selection.final_adapter_tools).not.toContain('kakao_keyword_search')
        expect(selection.final_adapter_tools).not.toContain('kakao_address_search')
        expect(toolNames).toContain('nmc_emergency_search')
        expect(toolNames).toContain('hira_hospital_search')
        expect(selection.final_adapter_tools).toContain('nmc_emergency_search')
        expect(selection.final_adapter_tools).toContain('hira_hospital_search')
        expect(toolNames).not.toContain('kma_current_observation')
        expect(toolNames).not.toContain('kma_short_term_forecast')
        expect(toolNames).not.toContain('kma_ultra_short_term_forecast')
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('uses prior bundle location context for relative emergency medical routing', async () => {
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('h')
      try {
        const exchange = await captureProviderExchange({
          messages: relativeEmergencyAfterPriorBundleLocationMessages(),
        })

        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).not.toContain('kakao_keyword_search')
        expect(toolNames).not.toContain('kakao_address_search')
        expect(selection.final_adapter_tools).not.toContain('kakao_keyword_search')
        expect(selection.final_adapter_tools).not.toContain('kakao_address_search')
        expect(toolNames).toContain('nmc_emergency_search')
        expect(toolNames).toContain('hira_hospital_search')
        expect(selection.final_adapter_tools).toContain('nmc_emergency_search')
        expect(selection.final_adapter_tools).toContain('hira_hospital_search')
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('withholds KMA forecast adapters when CIV birth prompt has no location', async () => {
    // Given: CIV-002 mentions a newborn and health-insurance registration, but no address.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('c')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: CIV_BIRTH_PROMPT })],
        })

        // Then: KMA forecast tools are not exposed as a substitute for civil-service routing.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        for (const toolName of HEALTH_LOCATION_TOOL_NAMES) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        expect(toolNames).toEqual([])
        expect(selection.final_adapter_tools).toEqual([])
        expect(serializedMessages(exchange.request)).toContain(CIV_BIRTH_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('withholds location-dependent adapters when WEL pregnancy prompt has no location', async () => {
    // Given: WEL-001 asks for pregnancy benefits and medical vouchers without a location.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('w')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: WEL_PREGNANCY_PROMPT })],
        })

        // Then: location tools are not exposed as a substitute for welfare routing.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        for (const toolName of HEALTH_LOCATION_TOOL_NAMES) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        expect(toolNames).toEqual([])
        expect(selection.final_adapter_tools).toEqual([])
        expect(serializedMessages(exchange.request)).toContain(WEL_PREGNANCY_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('exposes WEL-002 welfare adapters without stale location or weather surface', async () => {
    // Given: WEL-002 asks for low-income welfare support, and stale location/weather candidates are also indexed.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestWelfareSurfaceManifest('l')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: WEL_LOW_INCOME_PROMPT })],
        })

        // Then: welfare adapters are exposed, but stale location/weather adapters are suppressed.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        for (const toolName of WELFARE_TOOL_NAMES) {
          expect(toolNames).toContain(toolName)
          expect(selection.final_adapter_tools).toContain(toolName)
        }
        for (const toolName of STALE_LOCATION_WEATHER_TOOL_NAMES) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        expectNoNonAdapterProviderTools(toolNames)
        expectProviderToolsMatchSelectedAdapters({
          toolNames,
          selectedAdapterToolNames: selection.final_adapter_tools,
        })
        expect(serializedMessages(exchange.request)).toContain(WEL_LOW_INCOME_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('exposes UTL-001 utility billing adapters without stale Kakao or KMA surface', async () => {
    // Given: UTL-001 asks for utility bills and autopay, and stale location/weather candidates are also indexed.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestUtilitySurfaceManifest('u')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: UTL_UTILITY_PROMPT })],
        })

        // Then: utility adapters are exposed, but stale Kakao/KMA adapters are suppressed.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        for (const toolName of UTILITY_TOOL_NAMES) {
          expect(toolNames).toContain(toolName)
          expect(selection.final_adapter_tools).toContain(toolName)
        }
        for (const toolName of STALE_LOCATION_WEATHER_TOOL_NAMES) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        expectNoNonAdapterProviderTools(toolNames)
        expectProviderToolsMatchSelectedAdapters({
          toolNames,
          selectedAdapterToolNames: selection.final_adapter_tools,
        })
        expect(serializedMessages(exchange.request)).toContain(UTL_UTILITY_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('exposes DJTC subway segment adapter without stale weather, utility, or payment surface', async () => {
    // Given: a DJTC fare/time prompt includes adversarial substitute-tool negatives.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestDjtcSurfaceManifest('j')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: DJTC_SEGMENT_PROMPT })],
        })

        // Then: the model sees the official DJTC adapter, not semantic substitutes.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain(DJTC_SEGMENT_TOOL_NAME)
        expect(selection.final_adapter_tools).toContain(DJTC_SEGMENT_TOOL_NAME)
        for (const toolName of STALE_DJTC_SUBSTITUTE_TOOL_NAMES) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        expectNoNonAdapterProviderTools(toolNames)
        expectProviderToolsMatchSelectedAdapters({
          toolNames,
          selectedAdapterToolNames: selection.final_adapter_tools,
        })
        expect(serializedMessages(exchange.request)).toContain(DJTC_SEGMENT_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('keeps HOU-002 first-home handoff free of stale Kakao or KMA surface', async () => {
    // Given: HOU-002 has no exact local-tax/registry/move-in submit adapter, while stale location/weather candidates are indexed.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHousingHandoffManifest('o')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: HOU_FIRST_HOME_PROMPT })],
        })

        // Then: no stale local/weather or root workspace surface is offered as a false housing workflow adapter.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        for (const toolName of STALE_LOCATION_WEATHER_TOOL_NAMES) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        expect(toolNames).toEqual([])
        expect(selection.final_adapter_tools).toEqual([])
        expect(serializedMessages(exchange.request)).toContain(HOU_FIRST_HOME_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('exposes CIV-003 death and bereavement adapters without stale Kakao or KMA surface', async () => {
    // Given: CIV-003 asks for death registration, funeral support, survivor benefits, and estate steps.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestCivilDeathSurfaceManifest('d')
      try {
        // When: the provider request is built through the real Friendli request path.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: CIV_DEATH_PROMPT })],
        })

        // Then: the model sees relevant real civic adapters, not stale location/weather/support tools.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        for (const toolName of [
          ...STALE_LOCATION_WEATHER_TOOL_NAMES,
          ...NONEXISTENT_SURVIVOR_PENSION_TOOL_NAMES,
        ]) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        for (const toolName of CIV_DEATH_TOOL_NAMES) {
          expect(toolNames).toContain(toolName)
          expect(selection.final_adapter_tools).toContain(toolName)
        }
        expectNoNonAdapterProviderTools(toolNames)
        expectProviderToolsMatchSelectedAdapters({
          toolNames,
          selectedAdapterToolNames: selection.final_adapter_tools,
        })
        expect(serializedMessages(exchange.request)).toContain(CIV_DEATH_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('keeps explicitly forced adapter even when disabled for top-K auto-add', async () => {
    // Given: forced tool choice is an explicit host decision rather than top-K recovery.
    await withFriendliEnv(async () => {
      ingestTaxManifest('g')
      try {
        // When: Hometax lookup is forced even though pending progression disabled it for auto-add.
        const exchange = await captureProviderExchange({
          messages: postLookupMessages(),
          disabledProviderToolNames: [HOMETAX_LOOKUP_TOOL_NAME],
          toolChoice: { type: 'tool', name: HOMETAX_LOOKUP_TOOL_NAME },
        })

        // Then: the provider request keeps the forced adapter and mandatory instruction.
        expect(getToolNames(exchange.request)).toContain(HOMETAX_LOOKUP_TOOL_NAME)
        expect(exchange.request.tool_choice).toEqual({
          type: 'function',
          function: { name: HOMETAX_LOOKUP_TOOL_NAME },
        })
        expect(serializedMessages(exchange.request)).toContain(
          `Mandatory tool call: the host selected ${HOMETAX_LOOKUP_TOOL_NAME}`,
        )
      } finally {
        ingestMetarManifest(undefined)
      }
    })
  })

  test('keeps support source tools for non-public-service support prompts', async () => {
    // Given: a source-support prompt that is not a public-service adapter intent.
    await withFriendliEnv(async () => {
      ingestMetarManifest(undefined)

      // When: the provider request is built through the real Friendli request path.
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content:
            '출처 확인이 필요한 문서 작성 근거를 찾아줘. 출처가 없으면 차단 상태를 알려줘.',
        })],
      })

      // Then: support sentinel recovery still exposes source tools without forcing one.
      const toolNames = getToolNames(exchange.request)
      expect(toolNames).toContain('WebSearch')
      expect(toolNames).toContain('WebFetch')
      expect(exchange.request.tool_choice).toBeUndefined()
    })
  })

  test('keeps explicit workspace support prompt on workspace-only surface after public-service history', async () => {
    // Given: a prior public-service manifest is loaded, but the next request explicitly asks for workspace files.
    await withFriendliEnv(async () => {
      const previousDiagnostics = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestHealthLocationManifest('s')
      try {
        // When: the provider request is built for the S1 support sentinel prompt.
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: SUPPORT_WORKSPACE_PROMPT })],
        })

        // Then: workspace support tools are available without stale public-service adapters.
        const toolNames = getToolNames(exchange.request)
        const selection = readAdapterSelection(diagnostics.path)
        expect(toolNames).toContain('workspace_grep')
        expect(toolNames).toContain('workspace_read')
        expect(toolParameters(exchange.request, 'workspace_grep')).toEqual(
          expect.objectContaining({
            required: expect.arrayContaining(['pattern']),
          }),
        )
        expect(toolParameters(exchange.request, 'workspace_read')).toEqual(
          expect.objectContaining({
            required: expect.arrayContaining(['file_path']),
          }),
        )
        for (const toolName of HEALTH_LOCATION_TOOL_NAMES) {
          expect(toolNames).not.toContain(toolName)
          expect(selection.final_adapter_tools).not.toContain(toolName)
        }
        expect(selection.final_adapter_tools).toEqual([])
        expect(serializedMessages(exchange.request)).toContain(SUPPORT_WORKSPACE_PROMPT)
      } finally {
        ingestMetarManifest(undefined)
        restoreRouteDiagnostics(previousDiagnostics)
        diagnostics.cleanup()
      }
    })
  })

  test('preserves workspace tool_use and tool_result pairing for support answer synthesis', async () => {
    // Given: S1 has already searched the workspace and now needs the provider to synthesize the answer.
    await withFriendliEnv(async () => {
      const workspaceSearchAssistant = createAssistantMessage({
        content: [
          {
            type: 'tool_use',
            id: 'call-workspace-grep-1',
            name: 'workspace_grep',
            input: { path: 'docs', pattern: 'configuration' },
          },
        ],
      })

      // When: the next provider request is built after the workspace tool result.
      const exchange = await captureProviderExchange({
        messages: [
          createUserMessage({ content: SUPPORT_WORKSPACE_PROMPT }),
          workspaceSearchAssistant,
          createUserMessage({
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-workspace-grep-1',
                content: JSON.stringify({
                  mode: 'files_with_matches',
                  numFiles: 1,
                  filenames: ['docs/configuration.md'],
                }),
              },
            ],
            toolUseResult: {
              mode: 'files_with_matches',
              numFiles: 1,
              filenames: ['docs/configuration.md'],
            },
            sourceToolAssistantUUID: workspaceSearchAssistant.uuid,
          }),
        ],
      })

      // Then: OpenAI-compatible tool_calls and role=tool messages preserve the CC pairing.
      expect(exchange.request.messages.slice(1)).toEqual([
        { role: 'user', content: SUPPORT_WORKSPACE_PROMPT },
        {
          role: 'assistant',
          content: '',
          tool_calls: [
            {
              id: 'call-workspace-grep-1',
              type: 'function',
              function: {
                name: 'workspace_grep',
                arguments: '{"path":"docs","pattern":"configuration"}',
              },
            },
          ],
        },
        {
          role: 'tool',
          name: 'workspace_grep',
          tool_call_id: 'call-workspace-grep-1',
          content:
            '{"mode":"files_with_matches","numFiles":1,"filenames":["docs/configuration.md"]}',
        },
      ])
    })
  })

  test('does not forward orphaned repair tool_use blocks without matching tool_result', async () => {
    // Given: a previous provider proposal was withheld for repair and never executed as a tool.
    await withFriendliEnv(async () => {
      ingestTaxManifest('o')
      const orphanedAssistant = createAssistantMessage({
        content: [
          { type: 'text', text: '본인확인을 먼저 진행하겠습니다.' },
          {
            type: 'tool_use',
            id: 'orphan-tax-verify-1',
            name: VERIFY_TOOL_NAME,
            input: { scope_list: ['tax.submit'], purpose_ko: '세금 신고' },
          },
        ],
      })

      try {
        // When: the next provider request is built for a new tax prompt.
        const exchange = await captureProviderExchange({
          messages: [
            createUserMessage({ content: TAX_PROMPT }),
            orphanedAssistant,
            createUserMessage({
              content:
                'Final answer repair: successful tool_result evidence already exists, but the previous assistant message was still a plan or promise to answer later.',
              isMeta: true,
            }),
            createAssistantMessage({
              content: '현재는 공식 신청 채널 확인으로 안내합니다.',
            }),
            createUserMessage({
              content:
                '아파트 팔았는데 양도소득세 얼마나 나오는지 계산하고 신고 절차까지 안내해줘.',
            }),
          ],
        })

        // Then: unpaired assistant tool_calls are not forwarded as executed history.
        const serialized = serializedMessages(exchange.request)
        expect(serialized).toContain('아파트 팔았는데 양도소득세')
        expect(serialized).not.toContain('orphan-tax-verify-1')
        expect(serialized).not.toContain('"tool_calls"')
      } finally {
        ingestMetarManifest(undefined)
      }
    })
  })
})
