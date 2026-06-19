import { describe, expect, test } from 'bun:test'
import type { Tool, ToolInputJSONSchema } from '../../../src/Tool.js'
import { getEmptyToolPermissionContext } from '../../../src/Tool.js'
import { buildProviderRequest } from '../../../src/services/api/ummaya/request.js'
import type {
  ProviderRequest,
  QueryModelParams,
} from '../../../src/services/api/ummaya/types.js'
import { SyntheticOutputTool } from '../../../src/tools/SyntheticOutputTool/SyntheticOutputTool.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import { asSystemPrompt } from '../../../src/utils/systemPromptType.js'

describe('UMMAYA provider schema normalization', () => {
  test('inlines local delegation defs only in provider request parameters', () => {
    const originalSchema = delegationSchema()
    const { request, tool } = buildRequestForSchema(originalSchema)
    const serializedRequest = JSON.stringify(request)
    const serializedOriginalSchema = JSON.stringify(tool.inputJSONSchema)
    const parameters = singleToolParameters(request)
    const properties = recordAt(parameters, 'properties')
    const delegationContext = recordAt(properties, 'delegation_context')

    expect(serializedOriginalSchema).toContain('"$ref":"#/$defs/DelegationToken"')
    expect(serializedOriginalSchema).toContain('"$defs"')
    expect(serializedRequest).not.toContain('#/$defs/DelegationToken')
    expect(serializedRequest).not.toContain('"$ref"')
    expect(serializedRequest).not.toContain('"$defs"')
    expect(parameters).not.toHaveProperty('$defs')
    expect(delegationContext).toMatchObject({
      type: 'object',
      required: ['delegation_token', 'scope'],
      additionalProperties: false,
    })
    expect(recordAt(delegationContext, 'properties')).toHaveProperty(
      'delegation_token',
    )
  })

  test('uses an open provider-safe object for unresolved local refs', () => {
    const { request } = buildRequestForSchema({
      type: 'object',
      properties: {
        malformed_input: { $ref: '#/$defs/MissingDelegationToken' },
      },
      required: ['malformed_input'],
      additionalProperties: false,
    })
    const serializedRequest = JSON.stringify(request)
    const malformedInput = recordAt(
      recordAt(singleToolParameters(request), 'properties'),
      'malformed_input',
    )

    expect(serializedRequest).not.toContain('"$ref"')
    expect(serializedRequest).not.toContain('"$defs"')
    expect(malformedInput).toMatchObject({
      type: 'object',
      description: expect.stringContaining('unresolved local schema reference'),
      properties: {},
      additionalProperties: true,
    })
    expect(malformedInput).not.toHaveProperty('required')
  })
})

function buildRequestForSchema(schema: ToolInputJSONSchema): {
  readonly request: ProviderRequest
  readonly tool: Tool
} {
  const tool: Tool = {
    ...SyntheticOutputTool,
    name: 'tax_delegation_schema_probe',
    searchHint: 'tax delegation schema normalization',
    inputJSONSchema: schema,
  }
  const params: QueryModelParams = {
    messages: [
      createUserMessage({
        content: 'Build provider request for schema normalization.',
      }),
    ],
    systemPrompt: asSystemPrompt(['System prompt']),
    tools: [tool],
    signal: new AbortController().signal,
    options: {
      getToolPermissionContext: async () => getEmptyToolPermissionContext(),
      model: 'LGAI-EXAONE/K-EXAONE-236B-A23B',
      isNonInteractiveSession: false,
      querySource: 'repl_main_thread',
      agents: [],
      allowedAgentTypes: [],
      mcpTools: [],
    },
  }
  return { request: buildProviderRequest(params), tool }
}

function delegationSchema(): ToolInputJSONSchema {
  return {
    type: 'object',
    properties: {
      delegation_context: { $ref: '#/$defs/DelegationToken' },
      tax_year: { type: 'integer' },
    },
    required: ['delegation_context', 'tax_year'],
    additionalProperties: false,
    $defs: {
      DelegationToken: {
        type: 'object',
        properties: {
          delegation_token: { type: 'string' },
          scope: { type: 'string' },
        },
        required: ['delegation_token', 'scope'],
        additionalProperties: false,
      },
    },
  }
}

function singleToolParameters(request: ProviderRequest): Record<string, unknown> {
  const parameters = request.tools?.[0]?.function.parameters
  if (!parameters) {
    throw new Error('Expected provider request to contain one tool schema')
  }
  return parameters
}

function recordAt(
  source: Record<string, unknown>,
  key: string,
): Record<string, unknown> {
  const value = source[key]
  if (!isRecord(value)) {
    throw new Error(`Expected ${key} to be an object`)
  }
  return value
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
