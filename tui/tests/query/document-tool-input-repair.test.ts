import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import { query } from '../../src/query.js'
import type { Tools } from '../../src/Tool.js'
import type { Message } from '../../src/types/message.js'
import { createAssistantMessage } from '../../src/utils/messages.js'
import {
  createNamedTool,
  queryParams,
  runQueryForPromptWithFirstAssistantContent,
} from './query-loop-visible-progress.helpers.js'

const D1_PROMPT =
  '/Users/um-yunsang/UMMAYA/.omo/evidence/final-tui-release-readiness-20260614/03-stage-a-manual-tui/document-fixtures/readonly-inspect.docx 문서의 구조와 빈칸만 확인해줘. 절대 수정하거나 저장하지 마.'
const D1_PATH =
  '/Users/um-yunsang/UMMAYA/.omo/evidence/final-tui-release-readiness-20260614/03-stage-a-manual-tui/document-fixtures/readonly-inspect.docx'
const documentToolInputSchema = z.object({
  correlation_id: z.string(),
  document: z.object({
    path: z.string().optional(),
    artifact_id: z.string().optional(),
    expected_format: z.string().optional(),
  }).passthrough(),
  operation: z.string(),
  instruction: z.string(),
}).passthrough()

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasBackendDocumentEnvelope(input: Record<string, unknown>): boolean {
  const document = isRecord(input.document) ? input.document : undefined
  return typeof input.correlation_id === 'string' &&
    input.correlation_id.trim().length > 0 &&
    document !== undefined &&
    document.path === D1_PATH &&
    input.operation === 'inspect' &&
    typeof input.instruction === 'string' &&
    input.instruction.includes('절대 수정하거나 저장하지 마')
}

function toolResultText(messages: readonly Message[]): string {
  return messages
    .flatMap(message => {
      const content = message.message.content
      if (message.type !== 'user' || !Array.isArray(content)) return []
      return content.flatMap(block => {
        if (!isRecord(block) || block.type !== 'tool_result') return []
        return typeof block.content === 'string' ? [block.content] : []
      })
    })
    .join('\n')
}

describe('document tool input repair at dispatch boundary', () => {
  test('repairs malformed provider document tool_use before execution for D1 readonly inspect', async () => {
    let observedInput: Record<string, unknown> | undefined
    const documentTool: Tools[number] = {
      ...createNamedTool('document'),
      inputSchema: documentToolInputSchema,
      async call(args) {
        observedInput = args
        if (!hasBackendDocumentEnvelope(args)) {
          return {
            data:
              "Document failed: Invalid parameters for tool 'document'. Missing or invalid fields: correlation_id, document. Field required; Field required.",
          }
        }
        return {
          data: {
            ok: true,
            result: {
              tool_id: 'document',
              status: 'ok',
              inspected_path: D1_PATH,
            },
          },
        }
      },
    }

    const emitted = await runQueryForPromptWithFirstAssistantContent({
      prompt: D1_PROMPT,
      firstContent: [
        {
          type: 'tool_use',
          id: 'call-document-d1',
          name: 'document',
          input: { operation: 'inspect' },
        },
      ],
      tools: [documentTool],
    })

    if (observedInput === undefined) {
      throw new Error('expected document tool to receive repaired input')
    }
    expect(toolResultText(emitted)).not.toContain('Invalid parameters')
    expect(hasBackendDocumentEnvelope(observedInput)).toBe(true)
    expect(toolResultText(emitted)).toContain('"status":"ok"')
  })

  test('turns document adapter errors into one fail-closed completion turn', async () => {
    const documentTool: Tools[number] = {
      ...createNamedTool('document'),
      async call() {
        return {
          data: {
            ok: false,
            error: {
              kind: 'dispatch_error',
              message:
                "Adapter 'document' raised FileNotFoundError: baselines.yaml",
            },
          },
        }
      },
    }
    const modelInputs: readonly Message[][] = []
    let callCount = 0
    const deps = {
      async *callModel({ messages }: { readonly messages: readonly Message[] }) {
        modelInputs.push([...messages])
        callCount += 1
        yield createAssistantMessage({
          content:
            callCount === 1
              ? [
                  {
                    type: 'tool_use',
                    id: 'call-document-d1',
                    name: 'document',
                    input: { operation: 'inspect' },
                  },
                ]
              : [{ type: 'text', text: '문서 검사 실패: 로컬 문서 경계에서 중단되었습니다.' }],
        })
      },
      microcompact: async (messages: readonly Message[]) => ({ messages }),
      autocompact: async () => ({ compactionResult: null, consecutiveFailures: undefined }),
      uuid: () => 'uuid-document-fail-closed',
    }
    const emitted: Message[] = []

    for await (const message of query(queryParams(D1_PROMPT, [documentTool], deps))) {
      if (message.type === 'assistant' || message.type === 'user') {
        emitted.push(message)
      }
    }

    expect(callCount).toBe(2)
    expect(JSON.stringify(modelInputs[1])).toContain('Document primitive result complete')
    expect(toolResultText(emitted)).toContain('"status":"failed"')
    expect(toolResultText(emitted)).not.toContain('Invalid parameters')
  })
})
