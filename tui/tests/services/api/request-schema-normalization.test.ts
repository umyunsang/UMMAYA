import { describe, expect, test } from 'bun:test'
import type {
  ProviderRequest,
  QueryModelParams,
} from '../../../src/services/api/ummaya/types.js'
import { buildProviderRequest } from '../../../src/services/api/ummaya/request.js'
import type { Tool, ToolInputJSONSchema } from '../../../src/Tool.js'
import { getEmptyToolPermissionContext } from '../../../src/Tool.js'
import { SyntheticOutputTool } from '../../../src/tools/SyntheticOutputTool/SyntheticOutputTool.js'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import { asSystemPrompt } from '../../../src/utils/systemPromptType.js'

describe('provider request schema normalization', () => {
  test('inlines adapter local defs before serializing provider tool parameters', () => {
    const originalSchema = delegationSchema()
    const { request, originalSerialized } = buildRequestForSchema(originalSchema)
    const serializedRequest = JSON.stringify(request)
    const parameters = singleToolParameters(request)
    const properties = objectAt(parameters, 'properties')
    const delegationContext = objectAt(properties, 'delegation_context')

    expect(originalSerialized).toContain('"$ref":"#/$defs/DelegationToken"')
    expect(serializedRequest).not.toContain('"$ref"')
    expect(serializedRequest).not.toContain('#/$defs/DelegationToken')
    expect(parameters).not.toHaveProperty('$defs')
    expect(delegationContext).toMatchObject({
      type: 'object',
      required: ['token_id', 'scope'],
      additionalProperties: false,
    })
    expect(objectAt(delegationContext, 'properties')).toHaveProperty('token_id')
  })

  test('replaces unresolved local refs with open provider-safe placeholder schemas', () => {
    const { request } = buildRequestForSchema({
      type: 'object',
      properties: {
        delegation_context: { $ref: '#/$defs/MissingDelegationToken' },
      },
      required: ['delegation_context'],
      additionalProperties: false,
    })
    const serializedRequest = JSON.stringify(request)
    const parameters = singleToolParameters(request)
    const properties = objectAt(parameters, 'properties')
    const delegationContext = objectAt(properties, 'delegation_context')

    expect(serializedRequest).not.toContain('"$ref"')
    expect(serializedRequest).not.toContain('#/$defs')
    expect(parameters).not.toHaveProperty('$defs')
    expect(parameters).toMatchObject({ required: ['delegation_context'] })
    expect(delegationContext).toMatchObject({
      type: 'object',
      description: expect.stringContaining('unresolved local schema reference'),
      properties: {},
      additionalProperties: true,
    })
    expect(delegationContext).not.toHaveProperty('required')
  })
})

function buildRequestForSchema(schema: ToolInputJSONSchema): {
  readonly request: ProviderRequest
  readonly originalSerialized: string
} {
  const tool: Tool = {
    ...SyntheticOutputTool,
    name: 'tax_delegation_schema_probe',
    searchHint: 'tax delegation schema normalization',
    inputJSONSchema: schema,
  }
  const params: QueryModelParams = {
    messages: [createUserMessage({ content: 'Build provider request for tax delegation.' })],
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
      toolChoice: { type: 'tool', name: tool.name },
    },
  }
  return {
    request: buildProviderRequest(params),
    originalSerialized: JSON.stringify(tool.inputJSONSchema),
  }
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
          token_id: { type: 'string' },
          scope: { type: 'string' },
        },
        required: ['token_id', 'scope'],
        additionalProperties: false,
      },
    },
  }
}

function singleToolParameters(request: ProviderRequest): Record<string, unknown> {
  const parameters = request.tools?.[0]?.function.parameters
  if (!parameters) {
    throw new Error('Expected one provider tool parameters object')
  }
  return parameters
}

function objectAt(
  source: Record<string, unknown>,
  key: string,
): Record<string, unknown> {
  const value = source[key]
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error(`Expected ${key} to be an object`)
  }
  return value as Record<string, unknown>
}
