import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import {
  buildTool,
  getEmptyToolPermissionContext,
  type ToolPermissionContext,
} from '../../src/Tool.js'
import { getMergedTools } from '../../src/tools.js'

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

function contextWithDenyRules(
  alwaysDenyRules: readonly string[],
): ToolPermissionContext {
  return {
    ...getEmptyToolPermissionContext(),
    alwaysDenyRules: { session: alwaysDenyRules },
  }
}

describe('permission deny catalog filtering', () => {
  test('blanket_deny_removes_registered_cc_tool_from_model_catalog', () => {
    const names = getMergedTools(contextWithDenyRules(['mcp__ummaya']), [
      mcpTool('ummaya', 'Bash'),
    ]).map(tool => tool.name)

    expect(names).not.toContain('mcp__ummaya__Bash')
  })
})
