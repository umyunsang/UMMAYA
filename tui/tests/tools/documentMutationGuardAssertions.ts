import { expect } from 'bun:test'
import { symlink } from 'node:fs/promises'
import { join } from 'node:path'
import { callFileEditTool } from '../../src/tools/FileEditTool/call.js'
import { FileEditTool } from '../../src/tools/FileEditTool/FileEditTool.js'
import { callFileWriteTool } from '../../src/tools/FileWriteTool/call.js'
import { FileWriteTool } from '../../src/tools/FileWriteTool/FileWriteTool.js'
import { callNotebookEditTool } from '../../src/tools/NotebookEditTool/call.js'
import { NotebookEditTool } from '../../src/tools/NotebookEditTool/NotebookEditTool.js'
import { DOCUMENT_DERIVATIVE_MUTATION_MESSAGE } from '../../src/tools/WorkspaceToolAdapter/documentFormatGuards.js'
import { runWithCwdOverride } from '../../src/utils/cwd.js'
import {
  fileState,
  makeContext,
  notebookContent,
  parentMessage,
  withTempRoot,
} from './documentMutationGuardTestHelpers.js'

async function rejectionMessageFor(
  attempt: () => Promise<unknown>,
): Promise<string | undefined> {
  try {
    await attempt()
    return undefined
  } catch (error) {
    if (error instanceof Error) return error.message
    throw error
  }
}

const rawMutationRejection = {
  result: false,
  message: DOCUMENT_DERIVATIVE_MUTATION_MESSAGE,
  errorCode: 20,
} as const

export async function expectFileWriteSymlinkAliasRejected(): Promise<void> {
  const context = makeContext()
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      const targetPath = join(root, 'target.docx')
      const aliasPath = join(root, 'alias.txt')
      const original = 'docx-original-bytes'
      await Bun.write(targetPath, original)
      await symlink('target.docx', aliasPath)
      context.readFileState.set(aliasPath, fileState(original))
      const rejectionMessage = await rejectionMessageFor(() =>
        callFileWriteTool(
          { file_path: aliasPath, content: 'mutated-through-alias' },
          context,
          parentMessage(),
        ),
      )
      expect(await Bun.file(targetPath).text()).toBe(original)
      expect(rejectionMessage).toBe(DOCUMENT_DERIVATIVE_MUTATION_MESSAGE)
      await expect(
        FileWriteTool.validateInput(
          { file_path: aliasPath, content: 'mutated-through-alias' },
          context,
        ),
      ).resolves.toEqual(rawMutationRejection)
    }),
  )
}

export async function expectDanglingFileWriteSymlinkRejected(): Promise<void> {
  const context = makeContext()
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      const targetPath = join(root, 'missing-target.docx')
      const aliasPath = join(root, 'alias.txt')
      await symlink('missing-target.docx', aliasPath)
      const rejectionMessage = await rejectionMessageFor(() =>
        callFileWriteTool(
          { file_path: aliasPath, content: 'created-through-alias' },
          context,
          parentMessage(),
        ),
      )
      expect(await Bun.file(targetPath).exists()).toBe(false)
      expect(rejectionMessage).toBe(DOCUMENT_DERIVATIVE_MUTATION_MESSAGE)
      await expect(
        FileWriteTool.validateInput(
          { file_path: aliasPath, content: 'created-through-alias' },
          context,
        ),
      ).resolves.toEqual(rawMutationRejection)
    }),
  )
}

export async function expectFileEditSymlinkAliasRejected(): Promise<void> {
  const context = makeContext()
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      const targetPath = join(root, 'target.docx')
      const aliasPath = join(root, 'alias.txt')
      const original = 'old document text'
      await Bun.write(targetPath, original)
      await symlink('target.docx', aliasPath)
      context.readFileState.set(aliasPath, fileState(original))
      const rejectionMessage = await rejectionMessageFor(() =>
        callFileEditTool(
          { file_path: aliasPath, old_string: 'old', new_string: 'new' },
          context,
          parentMessage(),
        ),
      )
      expect(await Bun.file(targetPath).text()).toBe(original)
      expect(rejectionMessage).toBe(DOCUMENT_DERIVATIVE_MUTATION_MESSAGE)
      await expect(
        FileEditTool.validateInput(
          { file_path: aliasPath, old_string: 'old', new_string: 'new' },
          context,
        ),
      ).resolves.toEqual(rawMutationRejection)
    }),
  )
}

export async function expectNotebookSymlinkAliasRejected(): Promise<void> {
  const context = makeContext()
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      const targetPath = join(root, 'target.docx')
      const aliasPath = join(root, 'alias.ipynb')
      const original = notebookContent('old')
      await Bun.write(targetPath, original)
      await symlink('target.docx', aliasPath)
      context.readFileState.set(aliasPath, fileState(original))
      const rejectionMessage = await rejectionMessageFor(() =>
        callNotebookEditTool(
          {
            notebook_path: aliasPath,
            cell_id: 'cell-1',
            new_source: 'new',
            edit_mode: 'replace',
          },
          context,
          parentMessage(),
        ),
      )
      expect(await Bun.file(targetPath).text()).toBe(original)
      expect(rejectionMessage).toBe(DOCUMENT_DERIVATIVE_MUTATION_MESSAGE)
      await expect(
        NotebookEditTool.validateInput(
          {
            notebook_path: aliasPath,
            cell_id: 'cell-1',
            new_source: 'new',
            edit_mode: 'replace',
          },
          context,
        ),
      ).resolves.toEqual(rawMutationRejection)
    }),
  )
}

export async function expectNonDocumentSymlinkAliasMutationAllowed(): Promise<void> {
  const context = makeContext()
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      const targetPath = join(root, 'target.txt')
      const aliasPath = join(root, 'alias.txt')
      await Bun.write(targetPath, 'old text')
      await symlink('target.txt', aliasPath)
      context.readFileState.set(aliasPath, fileState('old text'))
      await callFileWriteTool(
        { file_path: aliasPath, content: 'new text' },
        context,
        parentMessage(),
      )
      expect(await Bun.file(targetPath).text()).toBe('new text')

      context.readFileState.set(aliasPath, fileState('new text'))
      await callFileEditTool(
        { file_path: aliasPath, old_string: 'new', new_string: 'edited' },
        context,
        parentMessage(),
      )
      expect(await Bun.file(targetPath).text()).toBe('edited text')
    }),
  )
}
