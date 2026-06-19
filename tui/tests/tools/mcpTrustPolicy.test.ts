import { describe, expect, test } from 'bun:test'
import { z } from 'zod/v4'
import {
  buildTool,
  getEmptyToolPermissionContext,
  type ToolPermissionContext,
} from '../../src/Tool.js'
import { assembleToolPool } from '../../src/tools.js'
import { ListMcpResourcesTool } from '../../src/tools/ListMcpResourcesTool/ListMcpResourcesTool.js'
import { createMcpAuthTool } from '../../src/tools/McpAuthTool/McpAuthTool.js'
import { ReadMcpResourceTool } from '../../src/tools/ReadMcpResourceTool/ReadMcpResourceTool.js'

type RequestLogEntry = {
  readonly serverName: string
  readonly method: string
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

function mcpCapability(serverName: string, toolName: string) {
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

function connectedMcpClient(serverName: string, requestLog: RequestLogEntry[]) {
  return {
    name: serverName,
    type: 'connected',
    capabilities: { resources: {} },
    config: { type: 'sdk', name: serverName, scope: 'local' },
    cleanup: async () => {},
    client: {
      request: async (request: { method: string; params?: { uri?: string } }) => {
        requestLog.push({ serverName, method: request.method })
        if (request.method === 'resources/list') {
          return {
            resources: [
              {
                uri: `mcp://${serverName}/resource`,
                name: `${serverName} resource`,
                mimeType: 'text/plain',
                description: `Resource from ${serverName}`,
              },
            ],
          }
        }
        if (request.method === 'resources/read') {
          return {
            contents: [
              {
                uri: request.params?.uri ?? `mcp://${serverName}/resource`,
                mimeType: 'text/plain',
                text: `${serverName} resource text`,
              },
            ],
          }
        }
        throw new Error(`Unexpected MCP request: ${request.method}`)
      },
    },
  }
}

function toolUseContext(
  mcpClients: readonly ReturnType<typeof connectedMcpClient>[],
  permissionContext: ToolPermissionContext = getEmptyToolPermissionContext(),
) {
  return {
    options: { mcpClients },
    getAppState: () => ({ toolPermissionContext: permissionContext }),
  }
}

function toolNames(permissionContext: ToolPermissionContext): readonly string[] {
  return assembleToolPool(permissionContext, [
    mcpCapability('ummaya', 'lookup-citizen-channel'),
    mcpCapability('external', 'write-record'),
    mcpCapability('externality', 'read-record'),
  ]).map(tool => tool.name)
}

describe('MCP trust policy', () => {
  test('requires_server_trust_before_mcp_tool_exposure', () => {
    const untrustedNames = toolNames(getEmptyToolPermissionContext())
    const trustedExternalNames = toolNames(
      contextWithRules({ alwaysAllowRules: ['mcp__external'] }),
    )
    const prefixAccidentNames = toolNames(
      contextWithRules({ alwaysAllowRules: ['mcp__externality'] }),
    )

    expect(untrustedNames).toContain('mcp__ummaya__lookup-citizen-channel')
    expect(untrustedNames).not.toContain('mcp__external__write-record')
    expect(trustedExternalNames).toContain('mcp__external__write-record')
    expect(prefixAccidentNames).not.toContain('mcp__external__write-record')
    expect(prefixAccidentNames).toContain('mcp__externality__read-record')
  })

  test('lists_and_reads_resources_only_for_trusted_servers', async () => {
    const requestLog: RequestLogEntry[] = []
    const ummayaClient = connectedMcpClient('ummaya', requestLog)
    const externalClient = connectedMcpClient('external', requestLog)
    const context = toolUseContext([ummayaClient, externalClient])

    const listResult = await ListMcpResourcesTool.call({}, context)
    const readResult = await ReadMcpResourceTool.call(
      { server: 'ummaya', uri: 'mcp://ummaya/resource' },
      context,
    )

    await expect(
      ListMcpResourcesTool.call({ server: 'external' }, context),
    ).rejects.toThrow('Server "external" is not trusted for MCP resource access')
    await expect(
      ReadMcpResourceTool.call(
        { server: 'external', uri: 'mcp://external/resource' },
        context,
      ),
    ).rejects.toThrow('Server "external" is not trusted for MCP resource access')

    expect(listResult.data.map(resource => resource.server)).toEqual(['ummaya'])
    expect(readResult.data.contents[0]?.text).toBe('ummaya resource text')
    expect(requestLog).toEqual([
      { serverName: 'ummaya', method: 'resources/list' },
      { serverName: 'ummaya', method: 'resources/read' },
    ])
  })

  test('auth_permission_is_server_scoped_without_prefix_accident', async () => {
    const authTool = createMcpAuthTool('external', {
      type: 'http',
      url: 'https://mcp.example.invalid',
      scope: 'local',
    })

    const prefixAccidentDecision = await authTool.checkPermissions(
      {},
      toolUseContext(
        [],
        contextWithRules({ alwaysAllowRules: ['mcp__externality'] }),
      ),
    )
    const trustedDecision = await authTool.checkPermissions(
      {},
      toolUseContext([], contextWithRules({ alwaysAllowRules: ['mcp__external'] })),
    )

    expect(prefixAccidentDecision.behavior).toBe('passthrough')
    expect(prefixAccidentDecision.suggestions).toEqual([
      {
        type: 'addRules',
        rules: [{ toolName: 'mcp__external', ruleContent: undefined }],
        behavior: 'allow',
        destination: 'localSettings',
      },
    ])
    expect(trustedDecision.behavior).toBe('allow')
  })

  test('mcp_mutation_tools_inherit_stricter_tier_policy', async () => {
    const authTool = createMcpAuthTool('external', {
      type: 'http',
      url: 'https://mcp.example.invalid',
      scope: 'local',
    })

    const untrustedDecision = await authTool.checkPermissions(
      {},
      toolUseContext([], getEmptyToolPermissionContext()),
    )

    expect(authTool.isReadOnly({})).toBe(false)
    expect(authTool.isConcurrencySafe({})).toBe(false)
    expect(untrustedDecision.behavior).toBe('passthrough')
    expect(untrustedDecision.message).toBe(
      'MCP server "external" requires trust before authentication can run.',
    )
  })

  test('auth_call_does_not_execute_untrusted_server_silently', async () => {
    const authTool = createMcpAuthTool('external', {
      type: 'claudeai-proxy',
      url: 'https://mcp.example.invalid',
      id: 'external-connector',
      scope: 'local',
    })

    await expect(authTool.call({}, toolUseContext([]))).rejects.toThrow(
      'MCP server "external" requires trust before authentication can run.',
    )
  })

  test('malformed_resource_inputs_fail_closed_before_server_execution', async () => {
    const requestLog: RequestLogEntry[] = []
    const context = toolUseContext([connectedMcpClient('ummaya', requestLog)])

    await expect(
      ReadMcpResourceTool.call({ server: '', uri: 'mcp://ummaya/resource' }, context),
    ).rejects.toThrow('MCP server name cannot be empty')
    await expect(
      ReadMcpResourceTool.call({ server: 'ummaya', uri: '' }, context),
    ).rejects.toThrow('MCP resource URI cannot be empty')

    expect(requestLog).toEqual([])
  })
})
