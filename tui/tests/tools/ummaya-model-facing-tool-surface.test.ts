import { describe, expect, test } from 'bun:test'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { z } from 'zod/v4'
import type { ToolUseContext, Tools } from '../../src/Tool.js'
import { buildTool, getEmptyToolPermissionContext } from '../../src/Tool.js'
import type { Message } from '../../src/types/message.js'
import { getDefaultAppState, type AppState } from '../../src/state/AppStateStore.js'
import { assembleToolPool, getTools } from '../../src/tools.js'
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
import {
  buildGenericPendingFinalAnswerRepairPromptIfNeeded,
  selectUmmayaToolChoiceOverride,
  shouldWithholdGenericPendingFinalAnswer,
} from '../../src/tools/_shared/toolChoiceRepair.js'
import {
  buildPublicDataTerminalRepairPrompt,
  shouldBlockStalePriorToolResultAnswer,
  shouldBlockUnsupportedRouteDetailAnswer,
} from '../../src/query/publicDataTerminalRepair.js'
import {
  buildUnavailableToolRepairPromptIfNeeded,
  shouldBlockFinalAnswerAfterUnavailableToolRepair,
} from '../../src/query/unavailableToolRepair.js'
import { createToolUnavailableErrorPayload } from '../../src/query/toolResultErrors.js'
import {
  classifyRawJsonToolCallProposal,
  stripToolCallProposalText,
  textContainsToolCallProposal,
} from '../../src/utils/rawJsonToolCall.js'
import {
  createFileStateCacheWithSizeLimit,
  READ_FILE_STATE_CACHE_SIZE,
} from '../../src/utils/fileStateCache.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'

const LEGACY_GUARD_MODULES = [
  'src/tools/_shared/nmcAedGuard.ts',
  'src/tools/_shared/protectedCheckGuard.ts',
  'src/tools/_shared/kmaAnalysisGuard.ts',
  'src/tools/_shared/directPublicDataGuard.ts',
  'src/tools/_shared/textToolCallGuard.ts',
] as const

function makeToolUseContext(
  messages: readonly Message[],
  tools: Tools = [],
): ToolUseContext {
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

function context7Tool() {
  return buildTool({
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
}

function toolNamed(name: string): Tools[number] {
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

function syncAdapters(entries: AdapterManifestSyncFrame['entries']): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C1',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries,
    manifest_hash: 'a'.repeat(64),
    emitter_pid: 12345,
  } satisfies AdapterManifestSyncFrame)
}

function kmaCurrentObservationEntry(): AdapterManifestSyncFrame['entries'][number] {
  return {
    tool_id: 'kma_current_observation',
    name: 'KMA Current Observation',
    primitive: 'find',
    policy_authority_url: 'https://apihub.kma.go.kr/',
    source_mode: 'live',
    search_hint: '현재 날씨 기상청 current weather observation',
    llm_description: 'KMA APIHub current weather observation adapter.',
    input_schema_json: {
      type: 'object',
      properties: {
        nx: { type: 'integer', description: 'KMA grid X coordinate.' },
        ny: { type: 'integer', description: 'KMA grid Y coordinate.' },
      },
      required: ['nx', 'ny'],
      additionalProperties: false,
    },
  }
}

function kakaoAddressEntry(): AdapterManifestSyncFrame['entries'][number] {
  return {
    tool_id: 'kakao_address_search',
    name: 'Kakao Address Search',
    primitive: 'locate',
    policy_authority_url: 'https://developers.kakao.com/',
    source_mode: 'live',
    search_hint: 'locate 위치 주소 행정동 좌표 kakao address 부산 사하구 다대1동',
    llm_description: 'Locate Korean administrative district text.',
    input_schema_json: {
      type: 'object',
      properties: { query: { type: 'string' } },
      required: ['query'],
      additionalProperties: false,
    },
  }
}

function hiraHospitalEntry(): AdapterManifestSyncFrame['entries'][number] {
  return {
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
  }
}

function simpleAuthEntry(): AdapterManifestSyncFrame['entries'][number] {
  return {
    tool_id: 'mock_verify_module_simple_auth',
    name: 'Simple Auth Module',
    primitive: 'check',
    policy_authority_url: 'https://www.gov.kr/',
    source_mode: 'mock',
    search_hint: '간편인증 정부24 주민등록등본 민원 발급 simple auth',
    llm_description: 'Simple auth check for protected Gov24 requests.',
    input_schema_json: {
      type: 'object',
      properties: { scope_list: { type: 'array', items: { type: 'string' } } },
      required: ['scope_list'],
      additionalProperties: false,
    },
  }
}

function gov24SubmitEntry(): AdapterManifestSyncFrame['entries'][number] {
  return {
    tool_id: 'mock_submit_module_gov24_minwon',
    name: 'Government24 civil petition submit',
    primitive: 'send',
    policy_authority_url: 'https://www.gov.kr/',
    source_mode: 'mock',
    search_hint: '정부24 주민등록등본 민원 신청 발급 제출',
    llm_description: 'Mock Government24 civil petition submission adapter.',
    input_schema_json: {
      type: 'object',
      properties: {
        form_code: { type: 'string' },
        delegation_token: { type: 'string' },
      },
      required: ['form_code', 'delegation_token'],
      additionalProperties: false,
    },
  }
}

function userToolResult(
  toolUseId: string,
  content: string,
  options: { readonly isError?: true } = {},
): Message {
  return createUserMessage({
    content: [
      options.isError === true
        ? {
            type: 'tool_result',
            tool_use_id: toolUseId,
            content,
            is_error: true,
          }
        : {
            type: 'tool_result',
            tool_use_id: toolUseId,
            content,
          },
    ],
  })
}

describe('UMMAYA model-facing tool surface', () => {
  test('exposes public-service primitives and workspace adapters, not raw Claude Code developer tools', () => {
    const names = getTools(getEmptyToolPermissionContext()).map(tool => tool.name)

    expect(names).toEqual(
      expect.arrayContaining([
        'ToolSearch',
        'find',
        'locate',
        'send',
        'check',
        'document',
        'workspace_glob',
        'workspace_grep',
        'workspace_read',
        'workspace_write',
        'workspace_edit',
        'workspace_bash',
      ]),
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
      context7Tool(),
    ]).map(tool => tool.name)

    expect(names).toEqual(
      expect.arrayContaining([
        'check',
        'find',
        'locate',
        'send',
        'ToolSearch',
        'workspace_glob',
        'workspace_bash',
      ]),
    )
    expect(names).not.toContain('mcp__context7__resolve-library-id')
    expect(names).not.toContain('Glob')
  })

  test('loads synced backend adapters as deferred CC Tool objects', () => {
    syncAdapters([kmaCurrentObservationEntry()])

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

  test('ToolSearch retrieves a top deferred adapter schema without loading every adapter', async () => {
    syncAdapters([
      kmaCurrentObservationEntry(),
      hiraHospitalEntry(),
      simpleAuthEntry(),
    ])
    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
    const context = makeToolUseContext([], tools)
    const result = await ToolSearchTool.call(
      { query: 'current weather observation KMA', max_results: 1 },
      context,
      async () => ({ behavior: 'allow' as const, updatedInput: {} }),
      createAssistantMessage({ content: 'search tools' }),
    )

    expect(result.data.matches).toEqual(['kma_current_observation'])
    expect(result.data.total_deferred_tools).toBeGreaterThanOrEqual(3)
  })

  test('turn-local retrieval selects concrete adapters and keeps root primitives separate', () => {
    syncAdapters([
      kakaoAddressEntry(),
      kmaCurrentObservationEntry(),
      hiraHospitalEntry(),
    ])

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

  test('legacy static guard modules stay deleted and client-side tool-choice forcing stays disabled', () => {
    for (const legacyModule of LEGACY_GUARD_MODULES) {
      expect(existsSync(join(process.cwd(), legacyModule))).toBe(false)
    }

    const repairSource = readFileSync(
      join(process.cwd(), 'src/tools/_shared/toolChoiceRepair.ts'),
      'utf8',
    )
    expect(repairSource).not.toContain('nmcAedGuard')
    expect(repairSource).not.toContain('protectedCheckGuard')
    expect(repairSource).not.toContain('kmaAnalysisGuard')
    expect(repairSource).not.toContain('directPublicDataGuard')
    expect(repairSource).not.toContain('textToolCallGuard')
    expect(
      selectUmmayaToolChoiceOverride({
        messages: [createUserMessage({ content: '부산역에서 1001번 버스 곧 와?' })],
        tools: [
          toolNamed('tago_bus_route_search'),
          toolNamed('tago_bus_arrival_search'),
        ],
      }),
    ).toBeUndefined()
  })

  test('current public-data repair withholds plan-only answers after tool evidence', () => {
    const messages = [
      createUserMessage({ content: '퇴근하고 해운대 산책 갈 건데 지금 비 와?' }),
      userToolResult(
        'weather-1',
        JSON.stringify({
          ok: true,
          result: { kind: 'record', item: { t1h: 21.4, rn1: 0 } },
        }),
      ),
    ]
    const candidate = createAssistantMessage({
      content: '사용자에게 현재 상황과 예보를 바탕으로 답변을 제공하겠습니다.',
    })

    expect(shouldWithholdGenericPendingFinalAnswer({ messages, candidate })).toBe(true)
    expect(
      buildGenericPendingFinalAnswerRepairPromptIfNeeded({
        messages: [...messages, candidate],
      }),
    ).toContain('Final answer repair')
    expect(buildPublicDataTerminalRepairPrompt({ messages, candidate })).toContain(
      'Final answer repair',
    )
  })

  test('current unavailable-tool repair blocks unsupported adapter claims without static fallback', () => {
    const messages = [
      createUserMessage({ content: '근처 공공서비스 신청 가능 여부를 조회해줘' }),
      createAssistantMessage({
        content: [
          {
            type: 'tool_use',
            id: 'missing-1',
            name: 'unregistered_public_service_search',
            input: {},
          },
        ],
      }),
      userToolResult(
        'missing-1',
        JSON.stringify(createToolUnavailableErrorPayload(
          'unregistered_public_service_search',
        )),
        { isError: true },
      ),
    ]
    const candidate = createAssistantMessage({
      content: '신청 가능한 기관과 처리 결과를 확인했습니다.',
    })
    const repairPrompt = buildUnavailableToolRepairPromptIfNeeded({
      messages,
      candidate,
    })

    expect(repairPrompt).toContain('Unavailable tool boundary')
    expect(
      shouldBlockFinalAnswerAfterUnavailableToolRepair({
        messages: [
          ...messages,
          createAssistantMessage({ content: repairPrompt ?? '' }),
        ],
        candidate,
      }),
    ).toBe(true)
  })

  test('current public-data terminal guard blocks route and stale-result claims at query seam', () => {
    const routeMessages = [
      createUserMessage({ content: '부산역에서 해운대까지 지금 대중교통으로 어떻게 가?' }),
      createAssistantMessage({
        content: [
          {
            type: 'tool_use',
            id: 'loc-1',
            name: 'kakao_keyword_search',
            input: { query: '부산역' },
          },
        ],
      }),
      userToolResult(
        'loc-1',
        JSON.stringify({
          ok: true,
          result: { kind: 'poi', name: '부산역', lat: 35.11, lon: 129.04 },
        }),
      ),
    ]
    const routeCandidate = createAssistantMessage({
      content: '1호선을 타고 수영역에서 환승하면 약 40분이고 요금은 1,400원입니다.',
    })

    expect(
      shouldBlockUnsupportedRouteDetailAnswer({
        messages: routeMessages,
        candidate: routeCandidate,
      }),
    ).toBe(true)
    expect(
      buildPublicDataTerminalRepairPrompt({
        messages: routeMessages,
        candidate: routeCandidate,
      }),
    ).toContain('Unsupported route answer repair')

    const staleMessages = [
      createUserMessage({ content: '다대1동 근처 응급실 알려줘' }),
      userToolResult(
        'prior-er',
        JSON.stringify({
          ok: true,
          result: { kind: 'collection', items: [{ record: { name: '큐병원' } }] },
        }),
      ),
      createAssistantMessage({ content: '다대1동 근처 응급실은 큐병원입니다.' }),
      createUserMessage({ content: '부산역 근처 야간에 바로 갈 수 있는 병원 알려줘' }),
      userToolResult(
        'current-hospital',
        JSON.stringify({
          ok: true,
          result: {
            kind: 'collection',
            items: [{ record: { name: '부산역야간의원' } }],
          },
        }),
      ),
    ]
    const staleCandidate = createAssistantMessage({
      content: '부산역 근처에서는 이전 검색의 큐병원을 이용하면 됩니다.',
    })
    expect(
      shouldBlockStalePriorToolResultAnswer({
        messages: staleMessages,
        candidate: staleCandidate,
      }),
    ).toBe(true)
  })

  test('current raw JSON parser strips textual tool-call proposals without static text guard', () => {
    const proposalText =
      '확인했습니다.\n' +
      '<tool_call>{"name":"tago_bus_arrival_search","arguments":{"city_code":"21"}}</tool_call>'

    expect(textContainsToolCallProposal(proposalText)).toBe(true)
    expect(stripToolCallProposalText(proposalText)).toBe('확인했습니다.')
    expect(
      classifyRawJsonToolCallProposal({
        text: '{"name":"tago_bus_arrival_search","arguments":{"city_code":"21"}}',
        availableToolNames: ['tago_bus_arrival_search'],
      }),
    ).toEqual({
      kind: 'registered',
      executable: true,
      proposal: {
        name: 'tago_bus_arrival_search',
        input: { city_code: '21' },
      },
    })
  })

  test('protected check and submit adapters remain permission-gated concrete tools', async () => {
    syncAdapters([simpleAuthEntry(), gov24SubmitEntry()])

    const selected = selectTopKAdapterToolNamesForQuery(
      '정부24에서 주민등록등본 발급 민원 신청해줘',
      5,
    )
    expect(selected).toContain('mock_verify_module_simple_auth')
    expect(selected).toContain('mock_submit_module_gov24_minwon')

    const checkTool = getAdapterToolByName('mock_verify_module_simple_auth')
    if (checkTool === undefined) {
      throw new TypeError('Expected mock_verify_module_simple_auth adapter.')
    }
    const checkPermission = await checkTool.checkPermissions(
      { scope_list: ['gov24.resident_registration'] },
      makeToolUseContext([]),
    )
    expect(checkPermission.behavior).toBe('ask')
    expect(checkPermission.message).toContain('권한 위임 필요')

    const sendTool = getAdapterToolByName('mock_submit_module_gov24_minwon')
    if (sendTool === undefined) {
      throw new TypeError('Expected mock_submit_module_gov24_minwon adapter.')
    }
    const sendPermission = await sendTool.checkPermissions(
      { form_code: 'resident-registration', delegation_token: 'mock-token' },
      makeToolUseContext([]),
    )
    expect(sendPermission.behavior).toBe('ask')
    expect(sendPermission.message).toContain('제출 요청')
  })
})
