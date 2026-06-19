import { mock } from 'bun:test'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { z } from 'zod/v4'
import {
  clearManifestCache,
  ingestManifestFrame,
  isManifestSynced,
} from '../../../src/services/api/adapterManifest.js'
import type { ProviderOptions } from '../../../src/services/api/ummaya/types.js'
import { assembleToolPool } from '../../../src/tools.js'
import { getEmptyToolPermissionContext } from '../../../src/Tool.js'
import type { Tools } from '../../../src/Tool.js'
import type { Message } from '../../../src/types/message.js'
import { asSystemPrompt } from '../../../src/utils/systemPromptType.js'

const testDir = dirname(fileURLToPath(import.meta.url))
const tuiRoot = join(testDir, '../../..')

mock.module(join(tuiRoot, 'src/services/vcr.js'), () => ({
  withStreamingVCR: async function* <T>(
    _messages: unknown,
    run: () => AsyncGenerator<T>,
  ): AsyncGenerator<T> {
    yield* run()
  },
  withVCR: async <T>(_input: unknown, run: () => T | Promise<T>): Promise<T> => run(),
  withTokenCountVCR: async <T>(_messages: unknown, run: () => T | Promise<T>): Promise<T> => run(),
}))

const { queryModelWithStreaming } = await import('../../../src/services/api/ummaya.js')

const requestToolSchema = z.object({
  function: z.object({ name: z.string().optional() }).passthrough().optional(),
}).passthrough()

const capturedProviderRequestSchema = z.object({
  messages: z.array(z.unknown()),
  tools: z.array(requestToolSchema).optional(),
  tool_choice: z.unknown().optional(),
}).passthrough()

const adapterSelectionSchema = z.object({
  event: z.string(),
  manifest_hash: z.string(),
  query_source: z.string(),
  schema_projection_level: z.string(),
  selected_tools: z.array(z.string()),
  final_adapter_tools: z.array(z.string()),
  query_hash: z.string(),
}).passthrough()

export type CapturedProviderRequest = z.infer<typeof capturedProviderRequestSchema>

export function responseForTextDelta(text: string): Response {
  const encoder = new TextEncoder()
  const lines = [
    `data: {"id":"chatcmpl_provider_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":${JSON.stringify(text)}}}]}`,
    'data: {"choices":[{"finish_reason":"stop","delta":{}}],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
    'data: [DONE]',
  ]
  return responseFromSseLines(lines, 'req_provider_1')
}

export function responseForRawJsonToolCallText(params: {
  readonly name: string
  readonly arguments: Record<string, unknown>
}): Response {
  const text = JSON.stringify({
    name: params.name,
    arguments: params.arguments,
  })
  const lines = [
    `data: {"id":"chatcmpl_raw_json_tool_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":${JSON.stringify(text)}}}]}`,
    'data: {"choices":[{"finish_reason":"stop","delta":{}}],"usage":{"prompt_tokens":11,"completion_tokens":7}}',
    'data: [DONE]',
  ]
  return responseFromSseLines(lines, 'req_raw_json_tool_1')
}

export function responseForTextualToolCallText(params: {
  readonly name: string
  readonly arguments: Record<string, unknown>
  readonly prelude?: string
}): Response {
  const rawText = JSON.stringify({
    name: params.name,
    arguments: params.arguments,
  })
  const text = `${params.prelude ?? ''}<tool_call>${rawText}</tool_call>`
  const lines = [
    `data: {"id":"chatcmpl_textual_tool_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":${JSON.stringify(text)}}}]}`,
    'data: {"choices":[{"finish_reason":"stop","delta":{}}],"usage":{"prompt_tokens":11,"completion_tokens":7}}',
    'data: [DONE]',
  ]
  return responseFromSseLines(lines, 'req_textual_tool_1')
}

export function responseForEmptyStop(): Response {
  const lines = [
    'data: {"id":"chatcmpl_empty_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{}}]}',
    'data: {"choices":[{"finish_reason":"stop","delta":{}}],"usage":{"prompt_tokens":7,"completion_tokens":0}}',
    'data: [DONE]',
  ]
  return responseFromSseLines(lines, 'req_provider_empty')
}

export function responseForTextThenDocumentToolCall(): Response {
  const lines = [
    'data: {"id":"chatcmpl_document_tool_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"content":"먼저 다운로드 폴더에서 HWPX 양식 파일을 찾고 문서 검사 도구를 사용하겠습니다.\\n"}}]}',
    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_document_1","type":"function","function":{"name":"document_inspect","arguments":"{\\"correlation_id\\":\\"doc-corr\\",\\"document\\":{\\"path\\":\\"/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지.hwpx\\",\\"expected_format\\":\\"hwpx\\"}}"}}]}}]}',
    'data: {"choices":[{"finish_reason":"tool_calls","delta":{}}],"usage":{"prompt_tokens":31,"completion_tokens":12}}',
    'data: [DONE]',
  ]
  return responseFromSseLines(lines, 'req_document_1')
}

export function responseForSplitWorkspaceToolCallArguments(): Response {
  const lines = [
    'data: {"id":"chatcmpl_workspace_tool_1","model":"LGAI-EXAONE/K-EXAONE-236B-A23B","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_workspace_grep_1","type":"function","function":{"name":"workspace_grep","arguments":"{\\"pattern\\":\\"configuration"}}]}}]}',
    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\",\\"path\\":\\"docs/configuration.md\\"}"}}]}}]}',
    'data: {"choices":[{"finish_reason":"tool_calls","delta":{}}],"usage":{"prompt_tokens":31,"completion_tokens":4}}',
    'data: [DONE]',
  ]
  return responseFromSseLines(lines, 'req_workspace_tool_1')
}

function responseFromSseLines(lines: readonly string[], requestId: string): Response {
  const encoder = new TextEncoder()
  return new Response(new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(`${line}\n\n`))
      }
      controller.close()
    },
  }), {
    status: 200,
    headers: { 'content-type': 'text/event-stream', 'x-request-id': requestId },
  })
}

export async function withFriendliEnv<T>(run: () => Promise<T>): Promise<T> {
  const previousToken = process.env.UMMAYA_FRIENDLI_TOKEN
  const previousDisableFallback = process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK
  try {
    process.env.UMMAYA_FRIENDLI_TOKEN = 'friendli-token'
    process.env.CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK = '1'
    return await run()
  } finally {
    restoreEnv('UMMAYA_FRIENDLI_TOKEN', previousToken)
    restoreEnv('CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK', previousDisableFallback)
  }
}

function restoreEnv(name: string, previousValue: string | undefined): void {
  if (previousValue === undefined) {
    delete process.env[name]
    return
  }
  process.env[name] = previousValue
}

export async function captureProviderExchange(params: {
  readonly messages: readonly Message[]
  readonly response?: Response
  readonly tools?: Tools
  readonly toolChoice?: ProviderOptions['toolChoice']
  readonly disabledProviderToolNames?: readonly string[]
  readonly fetchNeverResolves?: boolean
}): Promise<{
  readonly request: CapturedProviderRequest
  readonly events: readonly unknown[]
}> {
  if (!isManifestSynced()) {
    ingestMetarManifest('z')
  }
  let captured: CapturedProviderRequest | undefined
  const events: unknown[] = []
  for await (const event of queryModelWithStreaming({
    messages: params.messages,
    systemPrompt: asSystemPrompt(['System prompt']),
    thinkingConfig: { type: 'disabled' },
    tools: params.tools ?? assembleToolPool(getEmptyToolPermissionContext(), []),
    signal: new AbortController().signal,
    options: {
      getToolPermissionContext: async () => getEmptyToolPermissionContext(),
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      isNonInteractiveSession: false,
      querySource: 'repl_main_thread',
      agents: [],
      allowedAgentTypes: [],
      mcpTools: [],
      toolChoice: params.toolChoice,
      disabledProviderToolNames: params.disabledProviderToolNames,
      fetchOverride: async (_input, init) => {
        captured = parseProviderRequestBody(init?.body)
        if (params.fetchNeverResolves === true) {
          return await new Promise<Response>(() => {})
        }
        return params.response ?? responseForTextDelta('ok')
      },
    },
  })) {
    events.push(event)
  }
  if (captured === undefined) throw new Error('Provider request was not captured')
  return { request: captured, events }
}

function parseProviderRequestBody(body: BodyInit | null | undefined): CapturedProviderRequest {
  if (typeof body !== 'string') throw new Error('Expected string provider request body')
  const parsed: unknown = JSON.parse(body)
  return capturedProviderRequestSchema.parse(parsed)
}

export function getToolNames(request: CapturedProviderRequest): string[] {
  return request.tools?.flatMap(tool => {
    const name = tool.function?.name
    return name === undefined ? [] : [name]
  }) ?? []
}

export function serializedMessages(request: CapturedProviderRequest): string {
  return JSON.stringify(request.messages)
}

export function ingestMetarManifest(hashChar: string | undefined): void {
  clearManifestCache()
  if (hashChar === undefined) return
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9EF',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [{
      tool_id: 'kma_apihub_url_air_metar_decoded',
      name: 'KMA APIHub decoded METAR',
      primitive: 'find',
      policy_authority_url: 'https://apihub.kma.go.kr/',
      source_mode: 'live',
      search_hint: 'METAR SPECI decoded airport weather aviation',
      llm_description: 'Decoded METAR airport weather.',
      input_schema_json: {
        type: 'object',
        properties: { org: { type: 'string' } },
        additionalProperties: false,
      },
    }],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

export function ingestTaxManifest(hashChar: string): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9TX',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kakao_address_search',
        name: 'Kakao address search',
        primitive: 'find',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '주소 위치 검색 kakao address',
        llm_description: 'Address lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_current_observation',
        name: 'KMA current observation',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '날씨 기상 관측 현재 기온',
        llm_description: 'Weather observation adapter.',
        input_schema_json: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mock_lookup_module_hometax_simplified',
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
      {
        tool_id: 'mock_verify_module_modid',
        name: 'Mock Mobile ID verification',
        primitive: 'check',
        policy_authority_url: 'https://www.mobileid.go.kr/',
        source_mode: 'mock',
        search_hint: '모바일ID 본인확인 인증 위임 동의 홈택스 종합소득세 신고',
        llm_description: 'Mock Mobile ID verification adapter for tax delegation.',
        input_schema_json: {
          type: 'object',
          properties: {
            scope_list: { type: 'array', items: { type: 'string' } },
            purpose_ko: { type: 'string' },
            purpose_en: { type: 'string' },
          },
          required: ['scope_list', 'purpose_ko', 'purpose_en'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mock_submit_module_hometax_taxreturn',
        name: 'Mock Hometax tax-return submit',
        primitive: 'send',
        policy_authority_url: 'https://www.hometax.go.kr/',
        source_mode: 'mock',
        search_hint: '홈택스 종합소득세 신고 제출 환급 계좌 접수번호',
        llm_description: 'Mock Hometax tax-return submission adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            tax_year: { type: 'integer' },
            refund_account: { type: 'string' },
          },
          required: ['tax_year'],
          additionalProperties: true,
        },
      },
    ],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

export function ingestGov24Manifest(hashChar: string): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4FGV',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'mock_lookup_module_gov24_certificate',
        name: 'Mock Gov24 certificate lookup',
        primitive: 'find',
        policy_authority_url: 'https://www.gov.kr/',
        source_mode: 'mock',
        search_hint: '정부24 주민등록등본 등본 증명서 발급 가능 여부 준비물 조회',
        llm_description: 'Mock Gov24 certificate lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            certificate_type: { type: 'string' },
            purpose: { type: 'string' },
          },
          required: ['certificate_type', 'purpose'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mock_verify_module_simple_auth',
        name: 'Mock simple auth verification',
        primitive: 'check',
        policy_authority_url: 'https://www.gov.kr/',
        source_mode: 'mock',
        search_hint: '정부24 간편인증 본인확인 주민등록등본 발급 신청',
        llm_description: 'Mock simple authentication for Gov24 delegation.',
        input_schema_json: {
          type: 'object',
          properties: {
            scope_list: { type: 'array', items: { type: 'string' } },
            purpose_ko: { type: 'string' },
            purpose_en: { type: 'string' },
          },
          required: ['scope_list', 'purpose_ko', 'purpose_en'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mock_submit_module_gov24_minwon',
        name: 'Mock Gov24 minwon submit',
        primitive: 'send',
        policy_authority_url: 'https://www.gov.kr/',
        source_mode: 'mock',
        search_hint: '정부24 주민등록등본 민원 신청 접수 발급',
        llm_description: 'Mock Gov24 civil petition submission adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            minwon_type: { type: 'string' },
            applicant_name: { type: 'string' },
            delivery_method: { type: 'string' },
            session_id: { type: 'string' },
          },
          required: ['minwon_type', 'applicant_name', 'delivery_method', 'session_id'],
          additionalProperties: true,
        },
      },
    ],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

export function ingestHealthLocationManifest(hashChar: string): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9HL',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kakao_keyword_search',
        name: 'Kakao keyword search',
        primitive: 'find',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '카카오 키워드 위치 검색 병원 약국 응급실 야간진료 임신 진료비 바우처 지원금',
        llm_description: 'Kakao keyword location search adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kakao_address_search',
        name: 'Kakao address search',
        primitive: 'find',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '카카오 주소 위치 검색 병원 응급실 야간진료 임신 진료비 바우처 지원금',
        llm_description: 'Kakao address lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'hira_hospital_search',
        name: 'HIRA hospital search',
        primitive: 'find',
        policy_authority_url: 'https://www.hira.or.kr/',
        source_mode: 'live',
        search_hint: '응급실 야간진료 병원 건강보험 심평원 HIRA 임신 진료비 바우처 지원금',
        llm_description: 'HIRA hospital search adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            location: { type: 'string' },
            subject: { type: 'string' },
          },
          required: ['location'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'nmc_emergency_search',
        name: 'NMC emergency search',
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
        tool_id: 'hira_medical_institution_detail',
        name: 'HIRA medical institution detail',
        primitive: 'find',
        policy_authority_url: 'https://www.hira.or.kr/',
        source_mode: 'live',
        search_hint: '응급실 야간진료 병원 건강보험 상세 심평원 HIRA 임신 진료비 바우처 지원금',
        llm_description: 'HIRA medical institution detail adapter.',
        input_schema_json: {
          type: 'object',
          properties: { ykiho: { type: 'string' } },
          required: ['ykiho'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kakao_address_search',
        name: 'Kakao address search',
        primitive: 'find',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '생활비 지원 복지센터 주민센터 주소 위치 검색 kakao',
        llm_description: 'Stale local address adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_current_observation',
        name: 'KMA current observation',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '날씨 기상 현재 관측 병원 이동 임신 진료비 바우처 지원금',
        llm_description: 'Weather observation adapter.',
        input_schema_json: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_short_term_forecast',
        name: 'KMA short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '건강보험 아기 출생 병원 기상 예보 단기예보 임신 진료비 바우처 지원금',
        llm_description: 'KMA short-term forecast adapter.',
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
        tool_id: 'kma_ultra_short_term_forecast',
        name: 'KMA ultra short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '건강보험 아기 출생 병원 기상 예보 초단기예보 임신 진료비 바우처 지원금',
        llm_description: 'KMA ultra short-term forecast adapter.',
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
    ],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

export function ingestWelfareSurfaceManifest(hashChar: string): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9WL',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kakao_keyword_search',
        name: 'Kakao keyword search',
        primitive: 'find',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '생활비 지원 복지센터 주민센터 주변 위치 검색 kakao',
        llm_description: 'Stale local facility location adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_current_observation',
        name: 'KMA current observation',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '생활비 지원 날씨 기상 현재 관측',
        llm_description: 'Stale weather observation adapter.',
        input_schema_json: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_short_term_forecast',
        name: 'KMA short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '생활비 지원 날씨 기상 단기예보',
        llm_description: 'Stale weather forecast adapter.',
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
        tool_id: 'kma_ultra_short_term_forecast',
        name: 'KMA ultra short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '생활비 지원 날씨 기상 초단기예보',
        llm_description: 'Stale ultra-short weather forecast adapter.',
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
        tool_id: 'mohw_welfare_eligibility_search',
        name: 'MOHW welfare eligibility search',
        primitive: 'find',
        policy_authority_url: 'https://www.bokjiro.go.kr/',
        source_mode: 'live',
        search_hint: '생활비 기초생활 주거급여 긴급복지 저소득 차상위 복지혜택 보건복지부 사회보장정보원 신청',
        llm_description: 'MOHW/SSIS welfare service catalog search adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            search_wrd: { type: 'string' },
            trgter_indvdl_array: { type: 'string' },
            order_by: { type: 'string' },
            num_of_rows: { type: 'integer' },
          },
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mock_welfare_application_submit_v1',
        name: 'Mock welfare application submit',
        primitive: 'send',
        policy_authority_url: 'https://www.gov.kr/',
        source_mode: 'mock',
        search_hint: '복지 급여신청 기초생활 주거급여 긴급복지 저소득 마이데이터 신청',
        llm_description: 'Mock welfare benefit application submission adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            applicant_id: { type: 'string' },
            benefit_code: { type: 'string' },
            application_type: { type: 'string' },
            household_size: { type: 'integer' },
          },
          required: [
            'applicant_id',
            'benefit_code',
            'application_type',
            'household_size',
          ],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

export function ingestUtilitySurfaceManifest(hashChar: string): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9UT',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kakao_keyword_search',
        name: 'Kakao keyword search',
        primitive: 'locate',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '전기 수도 도시가스 요금 자동이체 주변 위치 검색 kakao',
        llm_description: 'Stale local place search adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_current_observation',
        name: 'KMA current observation',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '전기 수도 도시가스 요금 날씨 기상 현재 관측',
        llm_description: 'Stale weather observation adapter.',
        input_schema_json: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_short_term_forecast',
        name: 'KMA short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '전기 수도 도시가스 요금 날씨 기상 단기예보',
        llm_description: 'Stale weather forecast adapter.',
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
        tool_id: 'kepco_contract_power_usage',
        name: 'KEPCO contract power usage',
        primitive: 'find',
        policy_authority_url: 'https://bigdata.kepco.co.kr/',
        source_mode: 'live',
        search_hint: '전기 요금 한전 KEPCO 계약종별 전력사용량 조회 이번 달 고지서',
        llm_description: 'KEPCO contract-type power usage and billing lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            year: { type: 'string', minLength: 4, maxLength: 4 },
            month: { type: 'string', minLength: 1, maxLength: 2 },
            metro_cd: { type: ['string', 'null'], default: null },
            city_cd: { type: ['string', 'null'], default: null },
            cntr_cd: { type: ['string', 'null'], default: null },
          },
          required: ['year', 'month'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mock_kftc_opengiro_bill_send_v1',
        name: 'Mock KFTC OpenGiro bill send',
        primitive: 'send',
        policy_authority_url: 'https://developers.kftc.or.kr/dev/openapi/open-giro/index',
        source_mode: 'mock',
        search_hint: '오픈지로 금융결제원 지로 공과금 전기 수도 도시가스 요금 고지 청구 자동이체 부과',
        llm_description: 'Mock OpenGiro bill service adapter for utility bill registration.',
        input_schema_json: {
          type: 'object',
          properties: {
            operation: {
              type: 'string',
              enum: ['create_bill', 'cancel_bill', 'check_payment_status'],
              default: 'create_bill',
            },
            giro_no: { type: 'string', minLength: 4, maxLength: 32 },
            bill_reference: { type: 'string', minLength: 1, maxLength: 64 },
            amount_krw: { type: ['integer', 'null'], minimum: 1, maximum: 99999999 },
            due_date: { type: ['string', 'null'], format: 'date' },
            payer_reference: { type: 'string', minLength: 1, maxLength: 64 },
            live_probe_requested: { type: 'boolean', default: false },
          },
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mock_kftc_opengiro_payment_send_v1',
        name: 'Mock KFTC OpenGiro payment send',
        primitive: 'send',
        policy_authority_url: 'https://developers.kftc.or.kr/dev/openapi/open-giro/pay-service',
        source_mode: 'mock',
        search_hint: '오픈지로 금융결제원 지로 공과금 전기 수도 도시가스 요금 납부 결제URL 자동이체',
        llm_description: 'Mock OpenGiro payment service adapter for utility payment and autopay setup.',
        input_schema_json: {
          type: 'object',
          properties: {
            operation: {
              type: 'string',
              enum: [
                'create_inquiry_payment_url',
                'create_input_payment_url',
                'create_link_payment_url',
                'query_payment_result',
              ],
              default: 'create_link_payment_url',
            },
            giro_no: { type: 'string', minLength: 4, maxLength: 32 },
            payment_reference: { type: 'string', minLength: 1, maxLength: 64 },
            amount_krw: { type: ['integer', 'null'], minimum: 1, maximum: 99999999 },
            payer_reference: { type: 'string', minLength: 1, maxLength: 64 },
            redirect_return_url: { type: ['string', 'null'], maxLength: 512 },
            live_probe_requested: { type: 'boolean', default: false },
          },
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

export function ingestHousingHandoffManifest(hashChar: string): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9HO',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kakao_keyword_search',
        name: 'Kakao keyword search',
        primitive: 'locate',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '생애최초 주택구입 대출 취득세 감면 등기 전입 주변 위치 검색 kakao',
        llm_description: 'Stale local place search adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kakao_address_search',
        name: 'Kakao address search',
        primitive: 'locate',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '주택구입 등기 전입 주소 위치 검색 kakao',
        llm_description: 'Stale address lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kakao_coord_to_region',
        name: 'Kakao coord to region',
        primitive: 'locate',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '사망신고 장례 지원 국민연금 유족급여 재산 주소 좌표 행정구역 kakao',
        llm_description: 'Stale reverse-geocoding adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            x: { type: 'string' },
            y: { type: 'string' },
          },
          required: ['x', 'y'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_current_observation',
        name: 'KMA current observation',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '주택구입 이사 전입 날씨 기상 현재 관측',
        llm_description: 'Stale weather observation adapter.',
        input_schema_json: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_short_term_forecast',
        name: 'KMA short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '주택구입 이사 전입 날씨 기상 단기예보',
        llm_description: 'Stale weather forecast adapter.',
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
        tool_id: 'kma_ultra_short_term_forecast',
        name: 'KMA ultra short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '주택구입 이사 전입 날씨 기상 초단기예보',
        llm_description: 'Stale ultra-short weather forecast adapter.',
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
    ],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

export function ingestCivilDeathSurfaceManifest(hashChar: string): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9CD',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      {
        tool_id: 'kakao_keyword_search',
        name: 'Kakao keyword search',
        primitive: 'locate',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '사망신고 장례 지원 국민연금 유족급여 재산 주변 위치 검색 kakao',
        llm_description: 'Stale local place search adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kakao_address_search',
        name: 'Kakao address search',
        primitive: 'locate',
        policy_authority_url: 'https://developers.kakao.com/',
        source_mode: 'live',
        search_hint: '사망신고 장례 지원 국민연금 유족급여 재산 주소 위치 검색 kakao',
        llm_description: 'Stale address lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_current_observation',
        name: 'KMA current observation',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '사망신고 장례 지원 날씨 기상 현재 관측',
        llm_description: 'Stale weather observation adapter.',
        input_schema_json: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
          additionalProperties: false,
        },
      },
      {
        tool_id: 'kma_short_term_forecast',
        name: 'KMA short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '사망신고 장례 지원 날씨 기상 단기예보',
        llm_description: 'Stale weather forecast adapter.',
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
        tool_id: 'kma_ultra_short_term_forecast',
        name: 'KMA ultra short-term forecast',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '사망신고 장례 지원 날씨 기상 초단기예보',
        llm_description: 'Stale ultra-short weather forecast adapter.',
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
        tool_id: 'kma_forecast_fetch',
        name: 'KMA forecast fetch',
        primitive: 'find',
        policy_authority_url: 'https://data.kma.go.kr/',
        source_mode: 'live',
        search_hint: '사망신고 장례 지원 날씨 기상 예보 forecast',
        llm_description: 'Stale KMA forecast adapter.',
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
        tool_id: 'kma_apihub_url_air_amos_minute',
        name: 'KMA APIHub AMOS minute aviation weather',
        primitive: 'find',
        policy_authority_url: 'https://apihub.kma.go.kr/',
        source_mode: 'live',
        search_hint: '사망신고 장례 지원 날씨 기상 항공기상 공항 AMOS minute',
        llm_description: 'Stale KMA aviation weather adapter.',
        input_schema_json: {
          type: 'object',
          properties: { tm: { type: 'string' } },
          additionalProperties: false,
        },
      },
      {
        tool_id: 'bfc_funeral_area_fee',
        name: 'BFC funeral area fee',
        primitive: 'find',
        policy_authority_url: 'https://www.data.go.kr/data/15157485/openapi.do',
        source_mode: 'live',
        search_hint: '사망 장례 장례식장 시설사용료 장례비 funeral area fee',
        llm_description: 'Busan public funeral facility fee lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            page_no: { type: 'integer', default: 1 },
            num_of_rows: { type: 'integer', default: 10 },
          },
          additionalProperties: false,
        },
      },
      {
        tool_id: 'reb_real_estate_stat_table',
        name: 'REB real estate statistic table',
        primitive: 'find',
        policy_authority_url: 'https://www.data.go.kr/data/15134761/openapi.do',
        source_mode: 'live',
        search_hint: '재산 상속 부동산 등기 한국부동산원 통계표 real estate property registry',
        llm_description: 'REB real-estate statistic table lookup adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            p_index: { type: 'integer', default: 1 },
            p_size: { type: 'integer', default: 100 },
            statbl_id: { type: ['string', 'null'], default: null },
          },
          additionalProperties: false,
        },
      },
      {
        tool_id: 'mohw_welfare_eligibility_search',
        name: 'MOHW welfare eligibility search',
        primitive: 'find',
        policy_authority_url: 'https://www.bokjiro.go.kr/',
        source_mode: 'live',
        search_hint: '장례 지원 유족 복지 급여 혜택 사망가족 보건복지부 복지로',
        llm_description: 'MOHW/SSIS welfare service catalog search adapter.',
        input_schema_json: {
          type: 'object',
          properties: {
            search_wrd: { type: 'string' },
            trgter_indvdl_array: { type: 'string' },
            order_by: { type: 'string' },
            num_of_rows: { type: 'integer' },
          },
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: hashChar.repeat(64),
    emitter_pid: 12345,
  })
}

export function createDiagnosticsTarget(): {
  readonly path: string
  readonly cleanup: () => void
} {
  const diagnosticsDir = mkdtempSync(join(tmpdir(), 'ummaya-route-diagnostics-'))
  return {
    path: join(diagnosticsDir, 'route.jsonl'),
    cleanup: () => rmSync(diagnosticsDir, { recursive: true, force: true }),
  }
}

export function readAdapterSelection(path: string): z.infer<typeof adapterSelectionSchema> {
  const lines = readFileSync(path, 'utf8').trim().split('\n')
  for (const line of lines) {
    const parsed: unknown = JSON.parse(line)
    const record = adapterSelectionSchema.safeParse(parsed)
    if (record.success && record.data.event === 'adapter_selection') return record.data
  }
  throw new Error('adapter_selection diagnostic was not captured')
}
