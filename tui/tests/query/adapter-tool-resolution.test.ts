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
const { createAssistantMessage, createUserMessage } = await import(
  '../../src/utils/messages.js'
)
const { RAW_JSON_UNREGISTERED_TOOL_USE_ID_PREFIX } = await import(
  '../../src/utils/rawJsonToolCall.js'
)

const TAX_TOOL_NAME = 'mock_lookup_module_hometax_simplified'
const VERIFY_TOOL_NAME = 'mock_verify_module_modid'

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

function makeTaxAndVerifyManifestFrame(): AdapterManifestSyncFrame {
  const taxFrame = makeTaxManifestFrame()
  const verifyFrame = makeVerifyManifestFrame()
  return {
    ...taxFrame,
    entries: [...taxFrame.entries, ...verifyFrame.entries],
    manifest_hash: 'e'.repeat(64),
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
})
