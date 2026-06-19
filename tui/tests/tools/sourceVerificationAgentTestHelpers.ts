import { AgentTool } from '../../src/tools/AgentTool/AgentTool.js'
import { finalizeAgentTool } from '../../src/tools/AgentTool/agentToolUtils.js'
import { WebFetchTool } from '../../src/tools/WebFetchTool/WebFetchTool.js'
import {
  sourceVerification,
  toolResultText,
} from './sourceVerificationTestHelpers.js'

type FinalizeSourceAgentResultOptions = {
  readonly childToolName?: string
  readonly childToolResultText?: string
}

function childSourceToolResultText(): string {
  return toolResultText(
    WebFetchTool.mapToolResultToToolResultBlockParam(
      {
        bytes: 128,
        code: 200,
        codeText: 'OK',
        result: 'Verified source excerpt.',
        durationMs: 5,
        url: 'https://policy.example/source',
        sourceVerification: sourceVerification('WebFetch'),
      },
      'toolu-child-web-fetch',
    ),
  )
}

export function finalizeSourceAgentResult(
  options: FinalizeSourceAgentResultOptions = {},
) {
  const childToolName = options.childToolName ?? 'WebFetch'
  const childToolResultTextValue =
    options.childToolResultText ?? childSourceToolResultText()
  return finalizeAgentTool(
    [
      {
        type: 'assistant',
        message: {
          id: 'msg-tool-use',
          role: 'assistant',
          content: [
            {
              type: 'tool_use',
              id: 'toolu-child-web-fetch',
              name: childToolName,
              input: {
                url: 'https://policy.example/source',
                prompt: 'Extract cited facts only.',
              },
            },
          ],
          model: 'test-model',
          stop_reason: 'tool_use',
          stop_sequence: null,
          usage: {
            input_tokens: 10,
            output_tokens: 4,
            cache_creation_input_tokens: null,
            cache_read_input_tokens: null,
            server_tool_use: null,
            service_tier: null,
            cache_creation: null,
          },
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: 'toolu-child-web-fetch',
              content: childToolResultTextValue,
            },
          ],
        },
      },
      {
        type: 'assistant',
        message: {
          id: 'msg-final',
          role: 'assistant',
          content: [
            {
              type: 'text',
              text: 'Research result needs provenance approval.',
            },
          ],
          model: 'test-model',
          stop_reason: 'end_turn',
          stop_sequence: null,
          usage: {
            input_tokens: 12,
            output_tokens: 8,
            cache_creation_input_tokens: null,
            cache_read_input_tokens: null,
            server_tool_use: {
              web_search_requests: 0,
              web_fetch_requests: 1,
            },
            service_tier: 'standard',
            cache_creation: null,
          },
        },
      },
    ],
    'agent-source-runtime-14',
    {
      prompt: 'Collect source evidence.',
      resolvedAgentModel: 'test-model',
      isBuiltInAgent: false,
      startTime: Date.now(),
      agentType: 'general-purpose',
      isAsync: false,
      parentToolUseId: 'toolu-agent-parent',
    },
  )
}

export function agentToolResultText(
  agentResult: ReturnType<typeof finalizeSourceAgentResult>,
): string {
  return toolResultText(
    AgentTool.mapToolResultToToolResultBlockParam(
      {
        status: 'completed',
        prompt: 'Collect source evidence.',
        ...agentResult,
      },
      'toolu-agent-parent',
    ),
  )
}
