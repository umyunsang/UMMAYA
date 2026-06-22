import { describe, expect, test } from 'bun:test'
import { assembleToolPool } from '../../../src/tools.js'
import { getEmptyToolPermissionContext } from '../../../src/Tool.js'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../../src/services/api/adapterManifest.js'
import type { AdapterManifestSyncFrame } from '../../../src/ipc/frames.generated.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  createDiagnosticsTarget,
  getToolNames,
  ingestHealthLocationManifest,
  ingestMetarManifest,
  ingestTaxManifest,
  readAdapterSelection,
  responseForRawJsonToolCallText,
  responseForSplitWorkspaceToolCallArguments,
  responseForTextDelta,
  responseForTextDeltaChunks,
  responseForTextThenDocumentToolCall,
  responseForTextualToolCallText,
  serializedMessages,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

type TextDeltaEvent = {
  readonly type: 'stream_event'
  readonly event: {
    readonly type: 'content_block_delta'
    readonly delta: {
      readonly type: 'text_delta'
      readonly text: string
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isTextDeltaEvent(value: unknown): value is TextDeltaEvent {
  if (!isRecord(value) || value.type !== 'stream_event') return false
  const event = value.event
  if (!isRecord(event) || event.type !== 'content_block_delta') return false
  const delta = event.delta
  return isRecord(delta) &&
    delta.type === 'text_delta' &&
    typeof delta.text === 'string'
}

function textDeltas(events: readonly unknown[]): readonly string[] {
  return events
    .filter(isTextDeltaEvent)
    .map(event => event.event.delta.text)
}

describe('UMMAYA-named CC provider interface wired to FriendliAI client shim', () => {
  test('streams through services/api/ummaya.ts without backend chat_request', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({ content: 'hello' })],
        response: responseForTextDelta('Hello from K-EXAONE'),
      })
      expect(exchange.request.messages).toEqual([
        { role: 'system', content: expect.stringContaining('System prompt') },
        { role: 'user', content: 'hello' },
      ])
      expect(exchange.request).not.toHaveProperty('kind', 'chat_request')
      expect(JSON.stringify(exchange.events)).toContain('"type":"assistant"')
      expect(JSON.stringify(exchange.events)).toContain('"type":"message_start"')
    })
  })

  test('omits provider-unsupported metadata from FriendliAI chat requests', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({ content: 'hello' })],
      })
      expect(exchange.request).not.toHaveProperty('metadata')
    })
  })

  test('surfaces provider errors instead of completing with an empty assistant message', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({ content: '테스트: 한 문장으로 인사만 해줘.' })],
        response: new Response(
          JSON.stringify({ error: { message: 'Invalid FriendliAI API key' } }),
          {
            status: 401,
            statusText: 'Unauthorized',
            headers: {
              'content-type': 'application/json',
              'x-request-id': 'req_auth_failed',
            },
          },
        ),
      })
      const serializedEvents = JSON.stringify(exchange.events)
      expect(serializedEvents).toContain('"isApiErrorMessage":true')
      expect(serializedEvents).toContain('FriendliAI request failed')
      expect(serializedEvents).toContain('401 Unauthorized')
      expect(serializedEvents).toContain('req_auth_failed')
      expect(serializedEvents).not.toContain('"content":[]')
    })
  })

  test('forced tool choice keeps a deferred adapter schema in the provider request', async () => {
    await withFriendliEnv(async () => {
      ingestMetarManifest('a')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: 'hello' })],
          toolChoice: { type: 'tool', name: 'kma_apihub_url_air_metar_decoded' },
        })
        expect(getToolNames(exchange.request)).toContain('kma_apihub_url_air_metar_decoded')
        expect(exchange.request.tool_choice).toEqual({
          type: 'function',
          function: { name: 'kma_apihub_url_air_metar_decoded' },
        })
        expect(serializedMessages(exchange.request)).toContain(
          'Mandatory tool call: the host selected kma_apihub_url_air_metar_decoded',
        )
        expect(serializedMessages(exchange.request)).toContain(
          "Before the tool call, emit exactly one brief user-visible prelude in the user's language",
        )
        expect(serializedMessages(exchange.request)).not.toContain('You may emit')
      } finally {
        ingestMetarManifest(undefined)
      }
    })
  })

  test('records turn-local adapter selection diagnostics for provider requests', async () => {
    await withFriendliEnv(async () => {
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestMetarManifest('b')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: 'METAR airport weather 확인해줘' })],
        })
        const selection = readAdapterSelection(diagnostics.path)
        expect(selection).toEqual(expect.objectContaining({
          manifest_hash: 'b'.repeat(64),
          query_source: 'repl_main_thread',
          schema_projection_level: 'top_k_concrete_adapter_schemas',
        }))
        expect(selection.selected_tools).toContain('kma_apihub_url_air_metar_decoded')
        expect(selection.final_adapter_tools).toContain('kma_apihub_url_air_metar_decoded')
        expect(selection.query_hash).toMatch(/^[a-f0-9]{64}$/)
        expect(getToolNames(exchange.request)).toContain('kma_apihub_url_air_metar_decoded')
      } finally {
        ingestMetarManifest(undefined)
        delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
        diagnostics.cleanup()
      }
    })
  })

  test('does not expose adapters when only description-only temporal wording matches a route request', async () => {
    await withFriendliEnv(async () => {
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      clearManifestCache()
      ingestManifestFrame({
        kind: 'adapter_manifest_sync',
        version: '1.0',
        session_id: 'test-session',
        correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9DD',
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
            search_hint: '현재 날씨 기온 강수 습도 풍속 초단기실황 관측',
            llm_description:
              "시민이 '지금 기온' / '현재 비 와' / '오늘 날씨 어때' 묻는 경우 첫 호출.",
            input_schema_json: {
              type: 'object',
              properties: { nx: { type: 'integer' }, ny: { type: 'integer' } },
              required: ['nx', 'ny'],
              additionalProperties: false,
            },
          },
          {
            tool_id: 'tago_bus_route_search',
            name: 'TAGO Bus Route Search',
            primitive: 'find',
            policy_authority_url: 'https://www.data.go.kr/data/15098529/openapi.do',
            source_mode: 'live',
            search_hint: '15098529 TAGO 버스노선 cityCode routeNo bus route find',
            llm_description:
              'Search official TAGO bus route data by city_code and citizen-visible route_no.',
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
        ],
        manifest_hash: 'd'.repeat(64),
        emitter_pid: 12345,
      } satisfies AdapterManifestSyncFrame)
      try {
        const exchange = await captureProviderExchange({
          messages: [
            createUserMessage({
              content: '부산역에서 해운대까지 지금 대중교통으로 어떻게 가?',
            }),
          ],
        })
        const selection = readAdapterSelection(diagnostics.path)
        expect(selection.selected_tools).not.toContain('kma_current_observation')
        expect(selection.final_adapter_tools).not.toContain('kma_current_observation')
        expect(getToolNames(exchange.request)).not.toContain('kma_current_observation')
      } finally {
        clearManifestCache()
        delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
        diagnostics.cleanup()
      }
    })
  })

  test('keeps station emergency requests location-first before current location result', async () => {
    await withFriendliEnv(async () => {
      clearManifestCache()
      ingestManifestFrame({
        kind: 'adapter_manifest_sync',
        version: '1.0',
        session_id: 'test-session',
        correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9DE',
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
            search_hint: 'locate 위치 장소 키워드 POI 랜드마크 캠퍼스 역 병원 좌표 kakao keyword',
            llm_description: 'Locate named places, stations, landmarks, hospitals, and POIs.',
            input_schema_json: {
              type: 'object',
              properties: { query: { type: 'string' } },
              required: ['query'],
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
              '응급실 실시간 병상 응급의료센터 가까운 응급실 emergency room nearest ER',
            llm_description:
              "Nearby or night ER queries use locate first, then mode='region' with q0/q1.",
            input_schema_json: {
              type: 'object',
              properties: { mode: { type: 'string' }, q0: { type: 'string' } },
              required: ['mode'],
              additionalProperties: false,
            },
          },
          {
            tool_id: 'hira_medical_institution_detail',
            name: 'HIRA Medical Institution Detail',
            primitive: 'find',
            policy_authority_url: 'https://www.hira.or.kr/',
            source_mode: 'live',
            search_hint: '응급실 야간진료 병원 건강보험 상세 심평원 HIRA ykiho detail',
            llm_description:
              'Use only after a prior hospital search returns encrypted ykiho.',
            input_schema_json: {
              type: 'object',
              properties: { ykiho: { type: 'string' } },
              required: ['ykiho'],
              additionalProperties: false,
            },
          },
        ],
        manifest_hash: 'e'.repeat(64),
        emitter_pid: 12345,
      } satisfies AdapterManifestSyncFrame)
      try {
        const exchange = await captureProviderExchange({
          messages: [
            createUserMessage({
              content: '아이가 열이 나는데 하단역 근처 야간 응급실 어디야?',
            }),
          ],
        })
        const toolNames = getToolNames(exchange.request)
        expect(toolNames).toContain('kakao_keyword_search')
        expect(toolNames).not.toContain('nmc_emergency_search')
        expect(toolNames).not.toContain('hira_medical_institution_detail')
      } finally {
        clearManifestCache()
      }
    })
  })

  test('keeps Hometax adapters available for income tax refund requests', async () => {
    await withFriendliEnv(async () => {
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestTaxManifest('c')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({
            content: '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.',
          })],
        })
        const selection = readAdapterSelection(diagnostics.path)
        expect(selection.selected_tools).toContain('mock_lookup_module_hometax_simplified')
        expect(selection.final_adapter_tools).toContain('mock_lookup_module_hometax_simplified')
        expect(getToolNames(exchange.request)).toContain('mock_lookup_module_hometax_simplified')
        expect(getToolNames(exchange.request)).not.toContain('find')
      } finally {
        ingestMetarManifest(undefined)
        delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
        diagnostics.cleanup()
      }
    })
  })

  test('exposes concrete Hometax verify after lookup-capable TAX-001 requests without root check', async () => {
    await withFriendliEnv(async () => {
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestTaxManifest('d')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({
            content: '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.',
          })],
        })
        const selection = readAdapterSelection(diagnostics.path)
        const toolNames = getToolNames(exchange.request)
        expect(selection.final_adapter_tools).toEqual(expect.arrayContaining([
          'mock_lookup_module_hometax_simplified',
          'mock_verify_module_modid',
          'mock_submit_module_hometax_taxreturn',
        ]))
        expect(toolNames).toContain('mock_verify_module_modid')
        expect(toolNames).not.toContain('check')
        expect(toolNames).not.toContain('find')
        expect(toolNames).not.toContain('send')
      } finally {
        ingestMetarManifest(undefined)
        delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
        diagnostics.cleanup()
      }
    })
  })

  test('exposes TAX-001 Hometax adapters without root primitive provider tools', async () => {
    await withFriendliEnv(async () => {
      const diagnostics = createDiagnosticsTarget()
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      ingestTaxManifest('e')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({
            content: '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.',
          })],
        })
        const selection = readAdapterSelection(diagnostics.path)
        const toolNames = getToolNames(exchange.request)
        expect(selection.final_adapter_tools).toEqual(expect.arrayContaining([
          'mock_lookup_module_hometax_simplified',
          'mock_submit_module_hometax_taxreturn',
        ]))
        expect(toolNames).toEqual(expect.arrayContaining([
          'mock_lookup_module_hometax_simplified',
          'mock_submit_module_hometax_taxreturn',
        ]))
        expect(toolNames).not.toContain('find')
        expect(toolNames).not.toContain('locate')
        expect(toolNames).not.toContain('check')
        expect(toolNames).not.toContain('send')
      } finally {
        ingestMetarManifest(undefined)
        delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
        diagnostics.cleanup()
      }
    })
  })

  test('exposes_recovered_support_schemas_for_korean_support_intent_turns', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '출처 확인과 MCP 리소스 신뢰 경계 확인이 필요하고, 근거 조사를 별도 작업으로 나눠 진행해줘.',
        })],
      })
      expect(getToolNames(exchange.request)).toEqual(expect.arrayContaining([
        'WebSearch',
        'WebFetch',
        'ListMcpResourcesTool',
        'Agent',
      ]))
    })
  })

  test('forces_shell_support_tool_choice_without_forcing_source_or_write_support', async () => {
    await withFriendliEnv(async () => {
      const prompts = {
        source: '출처 확인이 필요한 문서 작성 근거를 찾아줘. 출처가 없으면 쓰지 말고 차단 상태를 알려줘.',
        write: '작업공간에 task17-productfix-temp-note.txt 테스트 메모를 쓰려면 먼저 나에게 승인 요청해. 승인 없이는 실행하지 마.',
        shell: 'git 상태를 확인해줘. 변경은 하지 마. 실제 명령 실행 권한이 필요하면 승인 요청 또는 차단 상태를 보여줘.',
        mcp: '사용 가능한 MCP 리소스가 있으면 신뢰 경계를 확인한 뒤 목록만 보여줘. 막히면 차단 상태와 이유를 알려줘.',
      }
      const source = await captureRequestForText(prompts.source)
      const write = await captureRequestForText(prompts.write)
      const shell = await captureRequestForText(prompts.shell)
      const mcp = await captureRequestForText(prompts.mcp)
      expect(getToolNames(source)).toEqual(expect.arrayContaining(['WebSearch', 'WebFetch']))
      expect(source.tool_choice).toBeUndefined()
      expect(getToolNames(write)).toContain('workspace_write')
      expect(write.tool_choice).toBeUndefined()
      expect(getToolNames(shell)).toContain('workspace_bash')
      expect(shell.tool_choice).toEqual({
        type: 'function',
        function: { name: 'workspace_bash' },
      })
      expect(getToolNames(mcp)).toContain('ListMcpResourcesTool')
      expect(mcp.tool_choice).toBeUndefined()
      for (const prompt of [
        '문서를 읽어줘',
        '이 문서를 수정하지 말고 내용만 확인해줘',
        '/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지.hwpx 문서를 작성해줘',
      ]) {
        const documentRequest = await captureRequestForText(prompt)
        expect(getToolNames(documentRequest)).not.toContain('WebSearch')
        expect(getToolNames(documentRequest)).not.toContain('WebFetch')
        expect(serializedMessages(documentRequest)).not.toContain('Mandatory tool call: the host selected WebSearch')
      }
    })
  })

  test('forces_shell_tool_choice_for_stage_a_shell_gauntlet_prompt', async () => {
    await withFriendliEnv(async () => {
      const request = await captureRequestForText(
        '먼저 현재 저장소의 git 상태를 확인해줘. 그 다음 내가 권한 요청을 거절할 테니 `.omo/evidence/final-tui-release-readiness-20260614/03-stage-a-manual-tui/shell-gauntlet-marker.txt`를 삭제하는 셸 명령을 시도해봐.',
      )
      expect(getToolNames(request)).toContain('workspace_bash')
      expect(request.tool_choice).toEqual({
        type: 'function',
        function: { name: 'workspace_bash' },
      })
      expect(serializedMessages(request)).toContain(
        'Mandatory tool call: the host selected workspace_bash',
      )
      expect(serializedMessages(request)).toContain(
        'still emit that destructive command so the host permission gate can prompt',
      )
      expect(serializedMessages(request)).toContain(
        'preserve leading dots in hidden paths such as .omo/',
      )
    })
  })

  test('forces_document_tool_choice_for_exact_local_readonly_document_inspect_prompt', async () => {
    await withFriendliEnv(async () => {
      const request = await captureRequestForText(
        '/Users/um-yunsang/UMMAYA/.omo/evidence/final-tui-release-readiness-20260614/03-stage-a-manual-tui/document-fixtures/readonly-inspect.docx 문서의 구조와 빈칸만 확인해줘. 절대 수정하거나 저장하지 마.',
      )

      expect(getToolNames(request)).toContain('document')
      expect(getToolNames(request)).not.toContain('WebSearch')
      expect(getToolNames(request)).not.toContain('WebFetch')
      expect(request.tool_choice).toEqual({
        type: 'function',
        function: { name: 'document' },
      })
      expect(serializedMessages(request)).toContain(
        'Mandatory tool call: the host selected document',
      )
    })
  })

  test('does_not_force_document_tool_choice_for_non_document_local_path', async () => {
    await withFriendliEnv(async () => {
      const request = await captureRequestForText(
        '/Users/um-yunsang/UMMAYA/tmp/readonly-inspect.txt 문서의 구조와 빈칸만 확인해줘. 절대 수정하거나 저장하지 마.',
      )

      expect(request.tool_choice).toBeUndefined()
      expect(serializedMessages(request)).not.toContain(
        'Mandatory tool call: the host selected document',
      )
    })
  })

  test('adds_agent_schema_without_forcing_agent_tool_choice', async () => {
    await withFriendliEnv(async () => {
      const request = await captureRequestForText(
        '근거 조사를 별도 작업으로 나눠 진행할 수 있으면 진행 상황과 취소 가능 상태를 보여줘. 작업 도구가 막히면 차단 상태와 이유를 알려줘.',
      )
      expect(getToolNames(request)).toContain('Agent')
      expect(request.tool_choice).toBeUndefined()
      expect(serializedMessages(request)).not.toContain('Mandatory tool call: the host selected Agent')
      expect(serializedMessages(request)).not.toContain('Do not answer with prose, do not ask a follow-up question, and do not choose another tool.')
    })
  })

  test('streams CC-style document intent prose before a document tool call', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식을 13주차 활동일지로 작성해줘. 활동기간은 2026.06.01부터 2026.06.07까지고, 작성이 끝나면 원본과 달라진 부분을 문서 화면으로 비교해서 내가 바로 확인할 수 있게 보여줘.',
        })],
        response: responseForTextThenDocumentToolCall(),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(visibleText).toContain('먼저 다운로드 폴더')
      expect(visibleText).toContain('"type":"content_block_delta"')
      expect(visibleText).toContain('"type":"text_delta"')
      expect(visibleText).toContain('"type":"tool_use"')
      expect(visibleText).toContain('"name":"document_inspect"')
    })
  })

  test('does not buffer ordinary brace prose as a raw JSON tool-call prefix', async () => {
    await withFriendliEnv(async () => {
      const chunks = [
        '날씨와 대기질은 ',
        '{공식 adapter 결과}',
        ' 기준으로 분리해 정리합니다.',
      ]
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '오늘 부산 사하구 날씨와 미세먼지를 알려줘.',
        })],
        response: responseForTextDeltaChunks(chunks),
      })
      expect(textDeltas(exchange.events)).toEqual(chunks)
      expect(JSON.stringify(exchange.events)).not.toContain('"type":"tool_use"')
    })
  })

  test('upgrades exact raw JSON tool-call text without painting it as prose', async () => {
    await withFriendliEnv(async () => {
      ingestHealthLocationManifest('r')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({
            content: '동아대학교 승학캠퍼스 주위 야간 응급실을 알려줘',
          })],
          response: responseForRawJsonToolCallText({
            name: 'kakao_address_search',
            arguments: { query: '동아대학교' },
          }),
        })
        const visibleText = JSON.stringify(exchange.events)
        expect(visibleText).toContain('"type":"tool_use"')
        expect(visibleText).toContain('"name":"kakao_address_search"')
        expect(visibleText).toContain('"query":"동아대학교"')
        expect(visibleText).not.toContain('"type":"content_block_delta"')
        expect(visibleText).not.toContain('"text":"{\\"name\\":\\"kakao_address_search\\"')
      } finally {
        ingestMetarManifest(undefined)
      }
    })
  })

  test('recovers unregistered raw JSON tool-call text without painting it as prose', async () => {
    await withFriendliEnv(async () => {
      ingestMetarManifest(undefined)
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '도구 호출 형식의 응답을 처리해줘.',
        })],
        response: responseForRawJsonToolCallText({
          name: 'unregistered_public_service_search',
          arguments: {
            query: 'nearby public-service request',
          },
        }),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(visibleText).toContain('"type":"tool_use"')
      expect(visibleText).toContain('"name":"unregistered_public_service_search"')
      expect(visibleText).toContain('"query":"nearby public-service request"')
      expect(visibleText).not.toContain('"type":"content_block_delta"')
      expect(visibleText).not.toContain('"text":"{\\"name\\":\\"unregistered_public_service_search\\"')
    })
  })

  test('recovers split raw JSON tool-call chunks without painting partial JSON', async () => {
    await withFriendliEnv(async () => {
      ingestMetarManifest(undefined)
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '도구 호출 형식의 응답을 처리해줘.',
        })],
        response: responseForTextDeltaChunks([
          '{',
          '"name":"unregistered_public_service_search","arguments":{"query":"nearby public-service request"}}',
        ]),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(textDeltas(exchange.events).join('')).toBe('')
      expect(visibleText).toContain('"type":"tool_use"')
      expect(visibleText).toContain('"name":"unregistered_public_service_search"')
      expect(visibleText).toContain('"query":"nearby public-service request"')
      expect(visibleText).not.toContain('"text":"{')
      expect(visibleText).not.toContain('\\"name\\":\\"unregistered_public_service_search\\"')
    })
  })

  test('recovers trailing raw JSON tool-call text after an assistant prelude', async () => {
    await withFriendliEnv(async () => {
      const trailingProposal = JSON.stringify({
        name: 'unregistered_public_service_search',
        arguments: {
          query: 'nearby public-service request',
        },
      })
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '도구 호출 형식의 응답을 처리해줘.',
        })],
        response: responseForTextDelta(
          `공식 도구를 사용하겠습니다.\n${trailingProposal}`,
        ),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(visibleText).toContain('공식 도구를 사용하겠습니다.')
      expect(visibleText).toContain('"type":"tool_use"')
      expect(visibleText).toContain('"name":"unregistered_public_service_search"')
      expect(visibleText).not.toContain('"text":"{\\"name\\":\\"unregistered_public_service_search\\"')
    })
  })

  test('recovers trailing raw JSON after ordinary brace prose without painting JSON', async () => {
    await withFriendliEnv(async () => {
      const prelude = '공식 값은 {adapter 결과} 기준으로 확인했습니다.\n'
      const trailingProposal = JSON.stringify({
        name: 'unregistered_public_service_search',
        arguments: {
          query: 'nearby public-service request',
        },
      })
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '도구 호출 형식의 응답을 처리해줘.',
        })],
        response: responseForTextDelta(`${prelude}${trailingProposal}`),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(textDeltas(exchange.events).join('')).toBe(prelude)
      expect(visibleText).toContain('"type":"tool_use"')
      expect(visibleText).toContain('"name":"unregistered_public_service_search"')
      expect(visibleText).not.toContain('"text":"{\\"name\\":\\"unregistered_public_service_search\\"')
    })
  })

  test('recovers textual tool-call blocks without painting tags or JSON as prose', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '도구 호출 형식의 응답을 처리해줘.',
        })],
        response: responseForTextualToolCallText({
          name: 'unregistered_public_service_search',
          arguments: {
            query: 'nearby public-service request',
          },
          prelude: '공식 도구를 사용하겠습니다.\n',
        }),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(visibleText).toContain('공식 도구를 사용하겠습니다.')
      expect(visibleText).toContain('"type":"tool_use"')
      expect(visibleText).toContain('"name":"unregistered_public_service_search"')
      expect(visibleText).not.toContain('<tool_call>')
      expect(visibleText).not.toContain('</tool_call>')
      expect(visibleText).not.toContain(
        '"text":"{\\"name\\":\\"unregistered_public_service_search\\"',
      )
    })
  })

  test('treats textual tool-call blocks outside the selected surface as unavailable', async () => {
    await withFriendliEnv(async () => {
      const disabledToolName = 'kma_apihub_url_air_metar_decoded'
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '도구 호출 형식의 응답을 처리해줘.',
        })],
        disabledProviderToolNames: [disabledToolName],
        response: responseForTextualToolCallText({
          name: disabledToolName,
          arguments: {
            org: 'RKPK',
          },
          prelude: '공식 도구를 사용하겠습니다.\n',
        }),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(getToolNames(exchange.request)).not.toContain(disabledToolName)
      expect(visibleText).toContain('공식 도구를 사용하겠습니다.')
      expect(visibleText).toContain('"type":"tool_use"')
      expect(visibleText).toContain('"name":"kma_apihub_url_air_metar_decoded"')
      expect(visibleText).toContain('"id":"call_raw_json_unregistered_tool_0"')
      expect(visibleText).not.toContain('"id":"call_textual_tool_0"')
      expect(visibleText).not.toContain('<tool_call>')
      expect(visibleText).not.toContain('</tool_call>')
    })
  })

  test('malformed_input converts malformed unregistered raw JSON tool-like text into a safe handoff', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: '도구 호출 형식의 응답을 처리해줘.',
        })],
        response: responseForTextDelta(JSON.stringify({
          tool: 'nmc_emergency_search',
          arguments: { location: '다대1동' },
        })),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(visibleText).toContain('"type":"content_block_delta"')
      expect(visibleText).toContain('Retry with a registered tool call')
      expect(visibleText).not.toContain('\\"tool\\":\\"nmc_emergency_search\\"')
      expect(visibleText).not.toContain('"type":"tool_use"')
      expect(visibleText).not.toContain('"name":"nmc_emergency_search"')
    })
  })

  test('keeps named-campus night ER requests location-first before current location result', async () => {
    await withFriendliEnv(async () => {
      ingestHealthLocationManifest('s')
      try {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({
            content: '동아대학교 승학캠퍼스 주위 야간 응급실을 알려줘',
          })],
        })
        const toolNames = getToolNames(exchange.request)
        expect(toolNames).toContain('kakao_keyword_search')
        expect(toolNames).toContain('kakao_address_search')
        expect(toolNames).not.toContain('hira_hospital_search')
      } finally {
        ingestMetarManifest(undefined)
      }
    })
  })

  test('accumulates streamed tool-call arguments by index before emitting tool_use', async () => {
    await withFriendliEnv(async () => {
      const exchange = await captureProviderExchange({
        messages: [createUserMessage({
          content: 'docs/configuration.md를 찾아서 설정 관련 핵심만 요약해줘.',
        })],
        response: responseForSplitWorkspaceToolCallArguments(),
      })
      const visibleText = JSON.stringify(exchange.events)
      expect(visibleText).toContain('"type":"tool_use"')
      expect(visibleText).toContain('"name":"workspace_grep"')
      expect(visibleText).toContain('"pattern":"configuration"')
      expect(visibleText).toContain('"path":"docs/configuration.md"')
      expect(visibleText).not.toContain('"input":{}')
    })
  })
})

async function captureRequestForText(prompt: string) {
  return (await captureProviderExchange({
    messages: [createUserMessage({ content: prompt })],
  })).request
}
