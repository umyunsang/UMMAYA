import { describe, expect, test } from 'bun:test'
import { getEmptyToolPermissionContext } from '../../src/Tool.js'
import { BashTool } from '../../src/tools/BashTool/BashTool.js'
import { FileEditTool } from '../../src/tools/FileEditTool/FileEditTool.js'
import { FileWriteTool } from '../../src/tools/FileWriteTool/FileWriteTool.js'
import { NotebookEditTool } from '../../src/tools/NotebookEditTool/NotebookEditTool.js'
import { AgentTool } from '../../src/tools/AgentTool/AgentTool.js'
import { filterToolsForAgent } from '../../src/tools/AgentTool/agentToolUtils.js'
import { assembleToolPool } from '../../src/tools.js'
import { WebFetchTool } from '../../src/tools/WebFetchTool/WebFetchTool.js'
import { WebSearchTool } from '../../src/tools/WebSearchTool/WebSearchTool.js'
import { ListMcpResourcesTool } from '../../src/tools/ListMcpResourcesTool/ListMcpResourcesTool.js'
import { ReadMcpResourceTool } from '../../src/tools/ReadMcpResourceTool/ReadMcpResourceTool.js'
import type { AssistantMessage } from '../../src/types/message.js'
import {
  WORKSPACE_BASH_TOOL_NAME,
  WORKSPACE_EDIT_TOOL_NAME,
  WORKSPACE_WRITE_TOOL_NAME,
} from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import {
  makeContext,
  mcpTool,
  permissionContext,
  promptInjectedSourceResultText,
  supportTool,
  workspaceTool,
} from './ccToolLayerAdversarialHelpers.js'

const DNS_LOOPBACK_WEB_FETCH_INPUT = {
  url: 'http://127.0.0.1.nip.io/metadata',
  prompt: 'Extract cited facts only.',
} as const

const WEB_FETCH_PARENT_MESSAGE = {
  role: 'assistant',
  content: [{ type: 'text', text: 'Fetch the requested URL.' }],
} satisfies AssistantMessage

describe('CC tool layer adversarial audit', () => {
  test('pin: shell bypass mode still asks for destructive and protected AX commands', async () => {
    const context = makeContext({
      toolPermissionContext: permissionContext('bypassPermissions'),
      tools: [BashTool],
    })

    const destructive = await BashTool.checkPermissions(
      { command: 'git reset --hard HEAD' },
      context,
    )
    const protectedAx = await BashTool.checkPermissions(
      { command: 'curl https://www.gov.kr/portal/main' },
      context,
    )

    for (const decision of [destructive, protectedAx]) {
      expect(decision.behavior).toBe('ask')
      expect(decision.decisionReason?.type).toBe('safetyCheck')
      expect(decision.message).toContain('requires explicit approval')
    }
  })

  test('pin: untrusted MCP tools stay hidden unless exact server trust exists', () => {
    const untrusted = assembleToolPool(getEmptyToolPermissionContext(), [
      mcpTool('ummaya', 'lookup-citizen-channel'),
      mcpTool('context7', 'resolve-library-id'),
    ]).map(tool => tool.name)
    const trusted = assembleToolPool(permissionContext('default', ['mcp__context7']), [
      mcpTool('context7', 'resolve-library-id'),
    ]).map(tool => tool.name)
    const toolOnlyTrust = assembleToolPool(
      permissionContext('default', ['mcp__context7__resolve-library-id']),
      [mcpTool('context7', 'resolve-library-id')],
    ).map(tool => tool.name)

    expect(untrusted).toContain('mcp__ummaya__lookup-citizen-channel')
    expect(untrusted).not.toContain('mcp__context7__resolve-library-id')
    expect(trusted).toContain('mcp__context7__resolve-library-id')
    expect(toolOnlyTrust).not.toContain('mcp__context7__resolve-library-id')
  })

  test('malformed_input: support tool inputs reject before execution', async () => {
    const emptyReadResource = ReadMcpResourceTool.inputSchema.safeParse({
      server: 'ummaya',
      uri: '',
    })
    const emptyListServer = ListMcpResourcesTool.inputSchema.safeParse({
      server: '',
    })
    const invalidWebFetch = await WebFetchTool.validateInput({
      url: 'not a url',
      prompt: 'Extract cited facts only.',
    })
    const invalidWebSearch = await WebSearchTool.validateInput({ query: '' })
    const invalidAgent = AgentTool.inputSchema.safeParse({
      description: 'Research',
      prompt: 'Collect evidence.',
      run_in_background: 'yes',
    })

    expect(emptyReadResource.success).toBe(false)
    expect(emptyListServer.success).toBe(false)
    expect(invalidWebFetch.result).toBe(false)
    expect(invalidWebSearch.result).toBe(false)
    expect(invalidAgent.success).toBe(false)
  })

  test('malformed_input: webfetch rejects private targets before permission suggestions', async () => {
    const blockedUrls = [
      'ftp://example.com/resource',
      'https://127.0.0.1/',
      'https://169.254.169.254/latest/meta-data/',
      'https://192.168.0.1/',
      'https://localhost/',
      'https://service.internal/',
      DNS_LOOPBACK_WEB_FETCH_INPUT.url,
    ] as const

    for (const url of blockedUrls) {
      const decision = await WebFetchTool.checkPermissions(
        { url, prompt: 'Extract cited facts only.' },
        makeContext(),
      )

      expect(decision.behavior).toBe('deny')
      expect(decision.message).toContain('unsafe URL')
      expect(Object.hasOwn(decision, 'suggestions')).toBe(false)
    }
  })

  test('malformed_input: webfetch rejects DNS-resolved private target before validation and fetch', async () => {
    const validation = await WebFetchTool.validateInput(
      DNS_LOOPBACK_WEB_FETCH_INPUT,
      makeContext(),
    )
    const decision = await WebFetchTool.checkPermissions(
      DNS_LOOPBACK_WEB_FETCH_INPUT,
      makeContext(),
    )
    const result = await WebFetchTool.call(
      DNS_LOOPBACK_WEB_FETCH_INPUT,
      makeContext(),
      async () => ({
        behavior: 'allow',
        updatedInput: DNS_LOOPBACK_WEB_FETCH_INPUT,
      }),
      WEB_FETCH_PARENT_MESSAGE,
    )
    const firstEvidence = result.data.sourceVerification?.evidence.at(0)

    expect(validation.result).toBe(false)
    expect(decision.behavior).toBe('deny')
    expect(Object.hasOwn(decision, 'suggestions')).toBe(false)
    expect(result.data.codeText).toBe('Source Verification Blocked')
    expect(result.data.result).toContain('Source verification blocked:')
    expect(result.data.result).toContain('resolved to a private')
    expect(result.data.result).not.toContain('Provider error')
    expect(firstEvidence).toMatchObject({
      blockedOrUsed: 'blocked',
      sourceUrl: null,
    })
  })

  test('pin: raw file, notebook, and workspace document mutations are blocked', async () => {
    const context = makeContext()

    await expect(
      FileWriteTool.validateInput(
        { file_path: 'form.hwpx', content: 'raw' },
        context,
      ),
    ).resolves.toMatchObject({ result: false, errorCode: 20 })
    await expect(
      FileEditTool.validateInput(
        { file_path: 'form.docx', old_string: 'old', new_string: 'new' },
        context,
      ),
    ).resolves.toMatchObject({ result: false, errorCode: 20 })
    await expect(
      NotebookEditTool.validateInput(
        { notebook_path: 'form.pdf', new_source: 'raw', edit_mode: 'replace' },
        context,
      ),
    ).resolves.toMatchObject({ result: false, errorCode: 20 })
    await expect(
      workspaceTool(WORKSPACE_WRITE_TOOL_NAME).validateInput?.(
        { file_path: 'form.xlsx', content: 'raw' },
        context,
      ),
    ).resolves.toMatchObject({ result: false, errorCode: 1 })
    await expect(
      workspaceTool(WORKSPACE_EDIT_TOOL_NAME).validateInput?.(
        { file_path: 'form.pptx', old_string: 'old', new_string: 'new' },
        context,
      ),
    ).resolves.toMatchObject({ result: false, errorCode: 1 })
    await expect(
      workspaceTool(WORKSPACE_BASH_TOOL_NAME).validateInput?.(
        { command: 'python3 mutate.py form.hwpx' },
        context,
      ),
    ).resolves.toMatchObject({ result: false, errorCode: 1 })
  })

  test('pin: prompt-injected source text stays untrusted and non-mutating', () => {
    const text = promptInjectedSourceResultText()

    expect(text).toContain('trust: untrusted_source')
    expect(text).toContain('prompt_injection: detected')
    expect(text).toContain('document_mutation_allowed: false')
    expect(text).toContain('permission_policy_mutation_allowed: false')
    expect(text).toContain('blocked_or_used: blocked')
  })

  test('pin: agent workers cannot inherit protected document, send, or check permission', async () => {
    const visibleToWorker = filterToolsForAgent({
      tools: [
        supportTool('document'),
        supportTool('send'),
        supportTool('check'),
        supportTool('TodoWrite'),
      ],
      isBuiltIn: true,
      permissionMode: 'acceptEdits',
    }).map(tool => tool.name)
    const decision = await AgentTool.checkPermissions(
      {
        description: 'Mutate protected document',
        prompt: 'Use document, send, and check directly.',
        mode: 'bypassPermissions',
      },
      makeContext({
        toolPermissionContext: permissionContext('default', ['document', 'send']),
      }),
    )

    expect(visibleToWorker).not.toContain('document')
    expect(visibleToWorker).not.toContain('send')
    expect(visibleToWorker).not.toContain('check')
    expect(visibleToWorker).toContain('TodoWrite')
    expect(decision.behavior).toBe('deny')
    expect(decision.message).toContain('coordinator parent permission')
  })
})
