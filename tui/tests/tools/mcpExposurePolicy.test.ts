import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import {
  buildTool,
  getEmptyToolPermissionContext,
  type ToolPermissionContext,
} from '../../src/Tool.js'
import { assembleToolPool } from '../../src/tools.js'

function mcpTool(serverName: string, toolName: string) {
  const name = `mcp__${serverName}__${toolName}`
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
    mcpInfo: { serverName, toolName },
  })
}

function contextWithRules(rules: {
  readonly alwaysAllowRules?: readonly string[]
  readonly alwaysDenyRules?: readonly string[]
}): ToolPermissionContext {
  return {
    ...getEmptyToolPermissionContext(),
    alwaysAllowRules: { session: rules.alwaysAllowRules ?? [] },
    alwaysDenyRules: { session: rules.alwaysDenyRules ?? [] },
  }
}

function catalogNames(permissionContext: ToolPermissionContext): readonly string[] {
  return assembleToolPool(permissionContext, [
    mcpTool('ummaya', 'lookup-citizen-channel'),
    mcpTool('context7', 'resolve-library-id'),
  ]).map(tool => tool.name)
}

describe('MCP exposure policy', () => {
  test('filters_untrusted_mcp_tools_before_model_exposure', () => {
    const names = catalogNames(getEmptyToolPermissionContext())

    expect(names).toContain('mcp__ummaya__lookup-citizen-channel')
    expect(names).not.toContain('mcp__context7__resolve-library-id')
  })

  test('allows_trusted_configured_mcp_only_after_server_trust_record', () => {
    const untrustedNames = catalogNames(getEmptyToolPermissionContext())
    const toolOnlyTrustNames = catalogNames(
      contextWithRules({
        alwaysAllowRules: ['mcp__context7__resolve-library-id'],
      }),
    )
    const trustedNames = catalogNames(
      contextWithRules({ alwaysAllowRules: ['mcp__context7'] }),
    )
    const deniedTrustedNames = catalogNames(
      contextWithRules({
        alwaysAllowRules: ['mcp__context7'],
        alwaysDenyRules: ['mcp__context7'],
      }),
    )

    expect(untrustedNames).not.toContain('mcp__context7__resolve-library-id')
    expect(toolOnlyTrustNames).not.toContain(
      'mcp__context7__resolve-library-id',
    )
    expect(trustedNames).toContain('mcp__context7__resolve-library-id')
    expect(deniedTrustedNames).not.toContain(
      'mcp__context7__resolve-library-id',
    )
  })
})
