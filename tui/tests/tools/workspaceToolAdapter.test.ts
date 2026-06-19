import { describe, expect, test } from 'bun:test'
import { getWorkspaceTools } from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import { ToolSearchTool } from '../../src/tools/ToolSearchTool/ToolSearchTool.js'
import {
  pureLoc,
  toolByName,
  workspaceAdapterSource,
} from './workspaceToolAdapter.helpers.js'

describe('workspace tool adapters', () => {
  test('keeps adapter orchestration split across cohesive policy modules', async () => {
    const moduleNames = [
      'allowedRootPolicy.ts',
      'documentFormatGuards.ts',
      'inputNormalization.ts',
      'mcpExposurePolicy.ts',
      'toolDefFactory.ts',
    ]
    const existenceChecks = await Promise.all(
      moduleNames.map(async fileName => ({
        fileName,
        exists: await Bun.file(
          `src/tools/WorkspaceToolAdapter/${fileName}`,
        ).exists(),
      })),
    )
    const missingModules = existenceChecks
      .filter(check => !check.exists)
      .map(check => check.fileName)
    const adapterSource = await workspaceAdapterSource('WorkspaceToolAdapter.ts')

    expect(missingModules).toEqual([])
    expect(pureLoc(adapterSource)).toBeLessThanOrEqual(250)
    expect(adapterSource).not.toContain('buildTool(')
    expect(adapterSource).not.toContain('DOCUMENT_FORMAT_PATH_RE')
    expect(adapterSource).not.toContain('normalizedDocumentGlobPattern')
    expect(adapterSource).not.toContain('validateWorkspacePathInsideAllowedRoots')
  })

  test('namespaces imported Claude Code file tools under workspace adapters', () => {
    const names = getWorkspaceTools().map(tool => tool.name)

    expect(names).toEqual([
      'workspace_glob',
      'workspace_grep',
      'workspace_read',
      'workspace_write',
      'workspace_edit',
      'workspace_bash',
    ])
    expect(names).not.toContain('Glob')
    expect(names).not.toContain('Grep')
    expect(names).not.toContain('Read')
    expect(names).not.toContain('Write')
    expect(names).not.toContain('Edit')
    expect(names).not.toContain('Bash')
  })

  test('keeps workspace read search available on turn one and defers heavier adapters', () => {
    const glob = toolByName('workspace_glob')
    const grep = toolByName('workspace_grep')
    const read = toolByName('workspace_read')
    const bash = toolByName('workspace_bash')

    expect(glob.alwaysLoad).toBe(true)
    expect(glob.shouldDefer).not.toBe(true)
    expect(grep.alwaysLoad).toBe(true)
    expect(grep.shouldDefer).not.toBe(true)
    expect(read.alwaysLoad).toBe(true)
    expect(read.shouldDefer).not.toBe(true)
    expect(bash.shouldDefer).toBe(true)
    expect(bash.alwaysLoad).not.toBe(true)
  })

  test('delegates core read/search semantics from the Claude Code tools', () => {
    const glob = toolByName('workspace_glob')
    const grep = toolByName('workspace_grep')
    const read = toolByName('workspace_read')
    const write = toolByName('workspace_write')
    const bash = toolByName('workspace_bash')

    expect(glob.isReadOnly({ pattern: '**/*.hwpx' })).toBe(true)
    expect(grep.isReadOnly({ pattern: '문서', path: '.' })).toBe(true)
    expect(read.isReadOnly({ file_path: '/tmp/example.txt' })).toBe(true)
    expect(write.isReadOnly({ file_path: '/tmp/example.txt', content: 'x' })).toBe(false)
    expect(bash.isReadOnly({ command: 'ls -la' })).toBe(true)
    expect(bash.isReadOnly({ command: 'rm -rf /tmp/example' })).toBe(false)
    expect(glob.inputSchema.shape).toHaveProperty('pattern')
  })

  test('rejects direct workspace writes to document binary formats', async () => {
    const write = toolByName('workspace_write')
    const edit = toolByName('workspace_edit')

    await expect(
      write.validateInput?.(
        {
          file_path: '/tmp/request.hwpx',
          content: 'raw bytes would corrupt the document contract',
        },
        {} as never,
      ),
    ).resolves.toEqual({
      result: false,
      message:
        'Document formats must be edited through the document primitive, not workspace_write.',
      errorCode: 1,
    })
    await expect(
      edit.validateInput?.(
        {
          file_path: '/tmp/request.docx',
          old_string: 'A',
          new_string: 'B',
        },
        {} as never,
      ),
    ).resolves.toEqual({
      result: false,
      message:
        'Document formats must be edited through the document primitive, not workspace_edit.',
      errorCode: 1,
    })
  })

  test('rejects sandbox override and document binary mutation through workspace bash', async () => {
    const bash = toolByName('workspace_bash')

    await expect(
      bash.validateInput?.(
        {
          command: 'echo ok',
          dangerouslyDisableSandbox: true,
        },
        {} as never,
      ),
    ).resolves.toEqual({
      result: false,
      message:
        'workspace_bash does not allow dangerouslyDisableSandbox. Use the normal permission and sandbox boundary.',
      errorCode: 2,
    })
    await expect(
      bash.validateInput?.(
        {
          command: 'python3 rewrite.py /tmp/request.hwpx',
        },
        {} as never,
      ),
    ).resolves.toEqual({
      result: false,
      message:
        'Document formats must be edited through the document primitive, not workspace_bash.',
      errorCode: 1,
    })
  })

  test('allows read-only document file discovery through workspace bash', async () => {
    const bash = toolByName('workspace_bash')

    await expect(
      bash.validateInput?.(
        {
          command: 'find . -name "*.hwpx"',
        },
        {} as never,
      ),
    ).resolves.toEqual({ result: true })
  })

  test('ToolSearch can select always-loaded read while counting only deferred workspace adapters', async () => {
    const result = await ToolSearchTool.call(
      { query: 'select:workspace_read', max_results: 1 },
      {
        options: { tools: [...getWorkspaceTools(), ToolSearchTool] },
        getAppState: () => ({ mcp: { clients: [] } }),
      } as never,
      async () => ({ behavior: 'allow', updatedInput: {} }),
      {} as never,
    )

    expect(result.data.matches).toEqual(['workspace_read'])
    expect(result.data.total_deferred_tools).toBe(3)
  })
})
