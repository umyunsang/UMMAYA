import { afterEach, describe, expect, test } from 'bun:test'
import {
  getEmptyToolPermissionContext,
} from '../../src/Tool.js'
import {
  assembleToolPool,
  getAllBaseTools,
  getTools,
} from '../../src/tools.js'
import {
  clearManifestCache,
} from '../../src/services/api/adapterManifest.js'
import { ToolSearchTool } from '../../src/tools/ToolSearchTool/ToolSearchTool.js'
import {
  formatDeferredToolLine,
  isDeferredTool,
} from '../../src/tools/ToolSearchTool/prompt.js'
import {
  expandedToolSearchTerms,
  selectRecoveredSupportToolNamesForQuery,
} from '../../src/tools/ToolSearchTool/supportIntentHints.js'
import {
  WORKSPACE_BASH_TOOL_NAME,
  WORKSPACE_WRITE_TOOL_NAME,
  getWorkspaceTools,
} from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import {
  defaultPrimitiveNames,
  ingestKmaAdapter,
  mcpTool,
  rawCcSupportNames,
  searchTools,
  sortedNames,
  withEnv,
} from './toolSearchCcSupport.helpers.js'

afterEach(() => {
  clearManifestCache()
})

describe('ToolSearch CC support hydration', () => {
  test('tool_search_prompt_names_support_intent_queries', async () => {
    const prompt = await ToolSearchTool.prompt({
      getToolPermissionContext: async () => getEmptyToolPermissionContext(),
      tools: assembleToolPool(getEmptyToolPermissionContext(), []),
      agents: [],
    })

    expect(prompt).toContain('source verification')
    expect(prompt).toContain('ListMcpResourcesTool')
    expect(prompt).toContain('Agent')
  })

  test('renders_deferred_support_search_hints_without_context_markup', async () => {
    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
    const webSearchTool = getAllBaseTools().find(tool => tool.name === 'WebSearch')

    expect(webSearchTool).toBeDefined()
    expect(webSearchTool ? isDeferredTool(webSearchTool) : false).toBe(true)

    const line = webSearchTool ? formatDeferredToolLine(webSearchTool) : ''

    expect(line).toContain('WebSearch')
    expect(line).toContain('search the web for current information')
    expect(line).not.toContain('<')
    expect(line).not.toContain('>')

    const result = await searchTools('current information', tools, 1)
    expect(result.data.matches).toEqual(['WebSearch'])
  })

  test('maps_korean_support_intents_to_recovered_cc_tools', async () => {
    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])

    const sourceResult = await searchTools(
      '출처 확인이 필요한 문서 작성 근거를 찾아줘',
      tools,
      2,
    )
    const mcpResult = await searchTools(
      '사용 가능한 MCP 리소스 목록을 신뢰 경계 확인 후 보여줘',
      tools,
      1,
    )
    const agentResult = await searchTools(
      '근거 조사를 별도 작업으로 나눠 진행하고 취소 가능 상태를 보여줘',
      tools,
      1,
    )

    expect(sourceResult.data.matches).toEqual(
      expect.arrayContaining(['WebSearch', 'WebFetch']),
    )
    expect(mcpResult.data.matches).toEqual(['ListMcpResourcesTool'])
    expect(agentResult.data.matches).toEqual(['Agent'])
  })

  test('does_not_map_ordinary_public_service_progress_wording_to_agent', async () => {
    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
    const ordinaryServicePrompt =
      '개인사업자 부가세 신고해야 하는데 매출 자료 모아서 납부까지 진행해줘.'

    const selectedSupportTools =
      selectRecoveredSupportToolNamesForQuery(ordinaryServicePrompt)
    const expandedTerms = expandedToolSearchTerms(
      ordinaryServicePrompt.toLowerCase(),
    )
    const result = await searchTools(ordinaryServicePrompt, tools, 3)

    expect(selectedSupportTools).not.toContain('Agent')
    expect(expandedTerms).not.toContain('agent')
    expect(result.data.matches).not.toContain('Agent')
  })

  test('does_not_map_generic_korean_list_or_status_prompts_to_mcp_support_tools', async () => {
    const genericPrompts = [
      '작업 목록 보여줘',
      '파일 목록 보여줘',
      '서버 상태 확인해줘',
    ] as const
    const explicitMcpPrompts = [
      '사용 가능한 MCP 리소스가 있으면 신뢰 경계를 확인한 뒤 목록만 보여줘',
      'MCP 서버 리소스 목록 보여줘',
    ] as const

    for (const prompt of genericPrompts) {
      const selectedSupportTools = selectRecoveredSupportToolNamesForQuery(prompt)
      const expandedTerms = expandedToolSearchTerms(prompt.toLowerCase())

      expect(selectedSupportTools).not.toContain('ListMcpResourcesTool')
      expect(expandedTerms).not.toContain('mcp')
      expect(expandedTerms).not.toContain('resources')
      expect(expandedTerms).not.toContain('servers')
    }

    for (const prompt of explicitMcpPrompts) {
      const selectedSupportTools = selectRecoveredSupportToolNamesForQuery(prompt)
      const expandedTerms = expandedToolSearchTerms(prompt.toLowerCase())

      expect(selectedSupportTools).toContain('ListMcpResourcesTool')
      expect(expandedTerms).toContain('mcp')
      expect(expandedTerms).toContain('resources')
    }
  })

  test('does_not_map_ordinary_document_prompts_to_source_support_tools', async () => {
    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])
    const ordinaryDocumentPrompts = [
      '문서를 읽어줘',
      '이 문서를 수정하지 말고 내용만 확인해줘',
      '/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지.hwpx 문서를 작성해줘',
    ] as const

    for (const prompt of ordinaryDocumentPrompts) {
      const selectedSupportTools = selectRecoveredSupportToolNamesForQuery(prompt)
      const result = await searchTools(prompt, tools, 3)

      expect(selectedSupportTools).not.toContain('WebSearch')
      expect(selectedSupportTools).not.toContain('WebFetch')
      expect(result.data.matches).not.toContain('WebSearch')
      expect(result.data.matches).not.toContain('WebFetch')
    }
  })

  test('workspace_write_and_shell_hints_force_visible_permission_boundary', () => {
    const workspaceTools = getWorkspaceTools()
    const writeTool = workspaceTools.find(
      tool => tool.name === WORKSPACE_WRITE_TOOL_NAME,
    )
    const shellTool = workspaceTools.find(
      tool => tool.name === WORKSPACE_BASH_TOOL_NAME,
    )

    expect(writeTool?.searchHint).toContain('permission')
    expect(writeTool?.searchHint).toContain('blocked')
    expect(shellTool?.searchHint).toContain('permission')
    expect(shellTool?.searchHint).toContain('blocked')
  })

  test('keeps_default_model_facing_tools_primitive_first', () => {
    const defaultNames = sortedNames(getTools(getEmptyToolPermissionContext()))
    const assembledNames = sortedNames(
      assembleToolPool(getEmptyToolPermissionContext(), []),
    )
    const registeredNames = sortedNames(getAllBaseTools())

    expect(defaultNames).toEqual(
      [...defaultPrimitiveNames].sort((left, right) =>
        left.localeCompare(right),
      ),
    )
    expect(assembledNames).toEqual(defaultNames)
    for (const supportName of rawCcSupportNames) {
      expect(defaultNames).not.toContain(supportName)
      expect(assembledNames).not.toContain(supportName)
    }
    expect(registeredNames).toEqual(
      expect.arrayContaining([...rawCcSupportNames]),
    )
  })

  test('hydrates_cc_support_tool_without_default_exposure', async () => {
    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])

    const result = await searchTools('select:Read', tools, 1)
    const readTool = getAllBaseTools().find(tool => tool.name === 'Read')

    expect(readTool).toBeDefined()
    expect(readTool ? isDeferredTool(readTool) : false).toBe(true)
    expect(tools.map(tool => tool.name)).not.toContain('Read')
    expect(result.data.matches).toEqual(['Read'])
    expect(result.data.total_deferred_tools).toBeGreaterThan(0)
  })

  test('distinguishes_ax_adapter_discovery_from_cc_support_hydration', async () => {
    ingestKmaAdapter()
    const tools = assembleToolPool(getEmptyToolPermissionContext(), [])

    const adapterResult = await searchTools(
      'current weather observation KMA',
      tools,
      1,
    )
    const supportResult = await searchTools('select:Read', tools, 1)

    expect(tools.map(tool => tool.name)).toContain('kma_current_observation')
    expect(tools.map(tool => tool.name)).not.toContain('Read')
    expect(adapterResult.data.matches).toEqual(['kma_current_observation'])
    expect(supportResult.data.matches).toEqual(['Read'])
  })

  test('does_not_hydrate_unsupported_untrusted_mcp_ant_or_test_only_tools', async () => {
    await withEnv('USER_TYPE', undefined, async () =>
      withEnv('NODE_ENV', 'production', async () => {
        const tools = assembleToolPool(getEmptyToolPermissionContext(), [
          mcpTool('context7', 'resolve-library-id'),
        ])

        const result = await searchTools(
          'select:Read,mcp__context7__resolve-library-id,Tungsten,TestingPermission',
          tools,
          4,
        )

        expect(tools.map(tool => tool.name)).not.toContain(
          'mcp__context7__resolve-library-id',
        )
        expect(result.data.matches).toEqual(['Read'])
        expect(result.data.matches).not.toContain(
          'mcp__context7__resolve-library-id',
        )
        expect(result.data.matches).not.toContain('Tungsten')
        expect(result.data.matches).not.toContain('TestingPermission')
      }),
    )
  })
})
