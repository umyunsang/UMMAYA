import { describe, expect, test } from 'bun:test'
import { homedir } from 'node:os'
import { getWorkspaceTools } from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import { ToolSearchTool } from '../../src/tools/ToolSearchTool/ToolSearchTool.js'

function toolByName(name: string) {
  const tool = getWorkspaceTools().find(candidate => candidate.name === name)
  if (!tool) throw new Error(`Missing workspace tool: ${name}`)
  return tool
}

describe('workspace tool adapters', () => {
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

  test('keeps path discovery available on turn one and defers heavier adapters', () => {
    const glob = toolByName('workspace_glob')
    const grep = toolByName('workspace_grep')
    const read = toolByName('workspace_read')
    const bash = toolByName('workspace_bash')

    expect(glob.alwaysLoad).toBe(true)
    expect(glob.shouldDefer).not.toBe(true)
    expect(grep.shouldDefer).toBe(true)
    expect(read.shouldDefer).toBe(true)
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

  test('infers Downloads path for natural workspace glob folder hints', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = { pattern: '**/*.hwpx' }

    await expect(
      glob.validateInput?.(
        input,
        {
          messages: [
            {
              type: 'user',
              message: {
                role: 'user',
                content:
                  '다운로드 폴더에 있는 주간활동일지 HWPX 문서를 찾아서 13주차로 작성해줘.',
              },
            },
          ],
        } as never,
      ),
    ).resolves.toEqual({ result: true })

    expect(input.path).toBe(`${homedir()}/Downloads`)
  })

  test('normalizes malformed HWPX glob patterns from natural document search hints', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = { pattern: '**/*.hwp *.hwpx' }

    await expect(
      glob.validateInput?.(
        input,
        {
          messages: [
            {
              type: 'user',
              message: {
                role: 'user',
                content:
                  '다운로드 폴더에 있는 주간활동일지 HWPX 문서를 찾아서 13주차로 작성해줘.',
              },
            },
          ],
        } as never,
      ),
    ).resolves.toEqual({ result: true })

    expect(input.pattern).toBe('**/*.hwpx')
    expect(input.path).toBe(`${homedir()}/Downloads`)
  })

  test('widens HWPX basename prefix globs for document title substring searches', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = { pattern: '**/주간활동일지*.hwpx' }

    await expect(
      glob.validateInput?.(
        input,
        {
          messages: [
            {
              type: 'user',
              message: {
                role: 'user',
                content:
                  '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 문서를 찾아줘.',
              },
            },
          ],
        } as never,
      ),
    ).resolves.toEqual({ result: true })

    expect(input.pattern).toBe('**/*주간활동일지*.hwpx')
    expect(input.path).toBe(`${homedir()}/Downloads`)
  })

  test('widens HWP basename prefix globs for downloaded public-form searches', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = { pattern: '**/참가서약서*.hwp' }

    await expect(
      glob.validateInput?.(
        input,
        {
          messages: [
            {
              type: 'user',
              message: {
                role: 'user',
                content:
                  '다운로드 폴더에 있는 2026년도 AX 아이디어 경진대회 참가서약서 HWP 문서를 찾아줘.',
              },
            },
          ],
        } as never,
      ),
    ).resolves.toEqual({ result: true })

    expect(input.pattern).toBe('**/*참가서약서*.hwp')
    expect(input.path).toBe(`${homedir()}/Downloads`)
  })

  test('keeps explicit workspace glob paths unchanged', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = {
      pattern: '**/*.hwpx',
      path: '/tmp',
    }

    await glob.validateInput?.(input, { messages: [] } as never)

    expect(input.path).toBe('/tmp')
  })

  test('loads deferred workspace adapters through ToolSearch', async () => {
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
    expect(result.data.total_deferred_tools).toBe(5)
  })
})
