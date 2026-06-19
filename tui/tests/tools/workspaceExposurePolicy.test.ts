import { describe, expect, test } from 'bun:test'
import { mkdir, symlink, writeFile } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { join } from 'node:path'
import type { ToolUseContext } from '../../src/Tool.js'
import {
  getWorkspaceTools,
  WORKSPACE_EDIT_TOOL_NAME,
  WORKSPACE_GLOB_TOOL_NAME,
  WORKSPACE_GREP_TOOL_NAME,
  WORKSPACE_READ_TOOL_NAME,
  WORKSPACE_WRITE_TOOL_NAME,
} from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import { runWithCwdOverride } from '../../src/utils/cwd.js'
import { getEmptyToolPermissionContext } from '../../src/Tool.js'

function toolByName(name: string) {
  const tool = getWorkspaceTools().find(candidate => candidate.name === name)
  if (!tool) throw new Error(`Missing workspace tool: ${name}`)
  return tool
}

function makeContext(
  workspaceRoot: string,
  messages: ToolUseContext['messages'] = [],
): ToolUseContext {
  return {
    messages,
    readFileState: new Map(),
    getAppState: () => ({
      toolPermissionContext: getEmptyToolPermissionContext(),
    }),
  } as never
}

function userMessage(content: string): ToolUseContext['messages'][number] {
  return {
    type: 'user',
    message: {
      role: 'user',
      content,
    },
  } as never
}

describe('workspace exposure policy', () => {
  test('read_search_default_and_mutation_permission_gated', async () => {
    const workspaceRoot = await Bun.$`mktemp -d ${tmpdir()}/ummaya-workspace-policy.XXXXXX`.text()
    const root = workspaceRoot.trim()
    const context = makeContext(root)
    const glob = toolByName(WORKSPACE_GLOB_TOOL_NAME)
    const grep = toolByName(WORKSPACE_GREP_TOOL_NAME)
    const read = toolByName(WORKSPACE_READ_TOOL_NAME)
    const write = toolByName(WORKSPACE_WRITE_TOOL_NAME)
    const edit = toolByName(WORKSPACE_EDIT_TOOL_NAME)

    await writeFile(join(root, 'memo.txt'), 'hello workspace\n')

    await runWithCwdOverride(root, async () => {
      expect(await glob.checkPermissions({ pattern: '*.txt', path: root }, context)).toMatchObject({
        behavior: 'allow',
      })
      expect(
        await grep.checkPermissions({ pattern: 'workspace', path: root }, context),
      ).toMatchObject({ behavior: 'allow' })
      expect(
        await read.checkPermissions({ file_path: join(root, 'memo.txt') }, context),
      ).toMatchObject({ behavior: 'allow' })
      expect(
        await write.checkPermissions(
          { file_path: join(root, 'memo.txt'), content: 'mutated\n' },
          context,
        ),
      ).toMatchObject({ behavior: 'ask' })
      expect(
        await edit.checkPermissions(
          {
            file_path: join(root, 'memo.txt'),
            old_string: 'hello',
            new_string: 'bye',
          },
          context,
        ),
      ).toMatchObject({ behavior: 'ask' })
    })
  })

  test('denies_symlink_escape_from_allowed_roots', async () => {
    const workspaceRoot = await Bun.$`mktemp -d ${tmpdir()}/ummaya-workspace-policy.XXXXXX`.text()
    const root = workspaceRoot.trim()
    const outsideRoot = await Bun.$`mktemp -d ${tmpdir()}/ummaya-workspace-outside.XXXXXX`.text()
    const outside = outsideRoot.trim()
    const context = makeContext(root)
    const read = toolByName(WORKSPACE_READ_TOOL_NAME)

    await writeFile(join(outside, 'secret.txt'), 'outside workspace\n')
    await symlink(join(outside, 'secret.txt'), join(root, 'escaped.txt'))

    await runWithCwdOverride(root, async () => {
      await expect(
        read.validateInput?.({ file_path: join(root, 'escaped.txt') }, context),
      ).resolves.toEqual({
        result: false,
        message:
          'Path resolves outside the allowed workspace roots. Re-select the folder or use an explicit document primitive flow.',
        errorCode: 20,
      })
    })
  })

  test('downloads_inference_requires_user_text_hint', async () => {
    const workspaceRoot = await Bun.$`mktemp -d ${tmpdir()}/ummaya-workspace-policy.XXXXXX`.text()
    const root = workspaceRoot.trim()
    const glob = toolByName(WORKSPACE_GLOB_TOOL_NAME)
    const inferredInput: Record<string, unknown> = { pattern: '**/*.hwpx' }
    const notInferredInput: Record<string, unknown> = { pattern: '**/*.hwpx' }

    await runWithCwdOverride(root, async () => {
      await glob.validateInput?.(
        inferredInput,
        makeContext(root, [userMessage('다운로드 폴더에서 HWPX 문서를 찾아줘.')]),
      )
      await glob.validateInput?.(
        notInferredInput,
        makeContext(root, [userMessage('이 작업공간에서 HWPX 문서를 찾아줘.')]),
      )
    })

    expect(inferredInput.path).toBe(join(homedir(), 'Downloads'))
    expect(notInferredInput).not.toHaveProperty('path')
  })
})
