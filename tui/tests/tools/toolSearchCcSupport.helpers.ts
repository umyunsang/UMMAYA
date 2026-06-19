import { z } from 'zod/v4'
import {
  buildTool,
  getEmptyToolPermissionContext,
  type Tools,
} from '../../src/Tool.js'
import type { AdapterManifestSyncFrame } from '../../src/ipc/frames.generated.js'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../src/services/api/adapterManifest.js'
import { ToolSearchTool } from '../../src/tools/ToolSearchTool/ToolSearchTool.js'

export const defaultPrimitiveNames = [
  'ToolSearch',
  'find',
  'locate',
  'send',
  'check',
  'document',
  'workspace_glob',
  'workspace_grep',
  'workspace_read',
  'workspace_write',
  'workspace_edit',
  'workspace_bash',
] as const

export const rawCcSupportNames = [
  'Read',
  'Edit',
  'Write',
  'Bash',
  'Glob',
  'Grep',
  'WebFetch',
  'WebSearch',
] as const

export function sortedNames(tools: Tools): readonly string[] {
  return tools.map(tool => tool.name).sort((left, right) => left.localeCompare(right))
}

export function mcpTool(serverName: string, toolName: string) {
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

export async function withEnv<T>(
  name: string,
  value: string | undefined,
  run: () => Promise<T> | T,
): Promise<T> {
  const previous = process.env[name]
  if (value === undefined) {
    delete process.env[name]
  } else {
    process.env[name] = value
  }
  try {
    return await run()
  } finally {
    if (previous === undefined) {
      delete process.env[name]
    } else {
      process.env[name] = previous
    }
  }
}

export async function searchTools(query: string, tools: Tools, maxResults = 5) {
  return ToolSearchTool.call(
    { query, max_results: maxResults },
    {
      options: { tools },
      getAppState: () => ({ mcp: { clients: [] } }),
    } as never,
    async () => ({ behavior: 'allow', updatedInput: {} }),
    {} as never,
  )
}

export function ingestKmaAdapter(): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9D1',
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
        search_hint: 'KMA current weather observation getUltraSrtNcst',
        llm_description:
          'KMA APIHub current weather observation adapter. Use latitude-derived KMA grid values from locate before calling this tool.',
        input_schema_json: {
          type: 'object',
          properties: {
            nx: { type: 'integer', description: 'KMA grid X coordinate.' },
            ny: { type: 'integer', description: 'KMA grid Y coordinate.' },
          },
          required: ['nx', 'ny'],
          additionalProperties: false,
        },
      },
    ],
    manifest_hash: 'c'.repeat(64),
    emitter_pid: 12345,
  } satisfies AdapterManifestSyncFrame)
}
