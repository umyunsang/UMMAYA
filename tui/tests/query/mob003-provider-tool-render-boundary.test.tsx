import { afterEach, beforeEach, describe, expect, test } from 'bun:test'
import type {
  ToolResultBlockParam,
  ToolUseBlockParam,
} from '@anthropic-ai/sdk/resources/index.mjs'
import React from 'react'
import { TerminalSizeContext } from '../../src/ink/components/TerminalSizeContext.js'
import type { AdapterManifestSyncFrame } from '../../src/ipc/frames.generated.js'
import { AssistantToolUseMessage } from '../../src/components/messages/AssistantToolUseMessage.js'
import { UserToolResultMessage } from '../../src/components/messages/UserToolResultMessage/UserToolResultMessage.js'
import {
  buildMessageLookups,
  createAssistantMessage,
  normalizeMessages,
} from '../../src/utils/messages.js'
import { createUserMessage } from '../../src/utils/userMessageFactories.js'
import { renderToString } from '../../src/utils/staticRender.js'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../src/services/api/adapterManifest.js'
import type { Message, NormalizedUserMessage } from '../../src/types/message.js'

const KMA_AVIATION_TOOL = 'kma_apihub_url_air_metar_decoded'
const TOOL_USE_ID = 'call-mob003-kma-aviation-1'

function kmaAviationManifestFrame(): AdapterManifestSyncFrame {
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    role: 'backend',
    session_id: 'session-mob003-render',
    correlation_id: 'correlation-mob003-render',
    frame_seq: 0,
    ts: '2026-06-16T00:00:00.000Z',
    entries: [
      {
        tool_id: KMA_AVIATION_TOOL,
        name: 'KMA APIHub decoded aviation METAR',
        primitive: 'find',
        source_mode: 'live',
        policy_authority_url: 'https://apihub.kma.go.kr/',
        search_hint: '김해공항 제주 항공기상 METAR aviation delay RKPK',
        llm_description:
          'Fetch decoded KMA aviation METAR data for an airport station.',
        input_schema_json: {
          type: 'object',
          properties: {
            stn: {
              type: 'string',
              description: 'KMA aviation station or airport code.',
            },
          },
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'b'.repeat(64),
    emitter_pid: 4321,
  }
}

function toolUseBlock(): ToolUseBlockParam {
  return {
    type: 'tool_use',
    id: TOOL_USE_ID,
    name: KMA_AVIATION_TOOL,
    input: { stn: 'RKPK' },
  }
}

function toolResultBlock(): ToolResultBlockParam {
  return {
    type: 'tool_result',
    tool_use_id: TOOL_USE_ID,
    is_error: true,
    content:
      'KMA aviation safe handoff: decoded METAR channel unavailable in this run.',
  }
}

function messagesWithKmaToolUse(): {
  readonly messages: readonly Message[]
  readonly toolUse: ToolUseBlockParam
  readonly toolResult: ToolResultBlockParam
  readonly normalizedUser: NormalizedUserMessage
  readonly lookups: ReturnType<typeof buildMessageLookups>
} {
  const toolUse = toolUseBlock()
  const toolResult = toolResultBlock()
  const messages = [
    createAssistantMessage({
      content: [
        { type: 'text', text: '항공기상 확인을 위해 공식 기상 채널을 조회합니다.' },
        toolUse,
      ],
    }),
    createUserMessage({
      content: [toolResult],
    }),
  ] satisfies Message[]
  const normalizedMessages = normalizeMessages(messages)
  const normalizedUser = normalizedMessages.find(
    (message): message is NormalizedUserMessage => message.type === 'user',
  )
  if (!normalizedUser) {
    throw new Error('expected normalized user tool_result message')
  }
  return {
    messages,
    toolUse,
    toolResult,
    normalizedUser,
    lookups: buildMessageLookups(normalizedMessages, messages),
  }
}

async function renderWithTerminal(node: React.ReactElement): Promise<string> {
  return renderToString(
    <TerminalSizeContext.Provider value={{ columns: 120, rows: 24 }}>
      {node}
    </TerminalSizeContext.Provider>,
    120,
  )
}

beforeEach(() => {
  clearManifestCache()
  ingestManifestFrame(kmaAviationManifestFrame())
})

afterEach(() => {
  clearManifestCache()
})

describe('MOB-003 adapter tool-use render boundary', () => {
  test('renders manifest-known provider adapter tool_use when the current tool list is stale', async () => {
    const { toolUse, lookups } = messagesWithKmaToolUse()
    const frame = await renderWithTerminal(
      <AssistantToolUseMessage
        param={toolUse}
        addMargin={false}
        tools={[]}
        commands={[]}
        verbose={false}
        inProgressToolUseIDs={new Set()}
        progressMessagesForMessage={[]}
        shouldAnimate={false}
        shouldShowDot={false}
        lookups={lookups}
      />,
    )

    expect(frame).toContain(KMA_AVIATION_TOOL)
  })

  test('renders manifest-known provider adapter tool_result errors when the current tool list is stale', async () => {
    const { toolResult, normalizedUser, lookups } = messagesWithKmaToolUse()
    const frame = await renderWithTerminal(
      <UserToolResultMessage
        param={toolResult}
        message={normalizedUser}
        lookups={lookups}
        progressMessagesForMessage={[]}
        tools={[]}
        verbose={false}
        width={120}
      />,
    )

    expect(frame).toContain('KMA aviation safe handoff')
  })
})
