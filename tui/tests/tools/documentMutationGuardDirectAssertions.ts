import { expect } from 'bun:test'
import { join } from 'node:path'
import { callFileEditTool } from '../../src/tools/FileEditTool/call.js'
import { FileEditTool } from '../../src/tools/FileEditTool/FileEditTool.js'
import { callFileWriteTool } from '../../src/tools/FileWriteTool/call.js'
import { FileWriteTool } from '../../src/tools/FileWriteTool/FileWriteTool.js'
import { callNotebookEditTool } from '../../src/tools/NotebookEditTool/call.js'
import { NotebookEditTool } from '../../src/tools/NotebookEditTool/NotebookEditTool.js'
import { DOCUMENT_DERIVATIVE_MUTATION_MESSAGE } from '../../src/tools/WorkspaceToolAdapter/documentFormatGuards.js'
import {
  WORKSPACE_BASH_TOOL_NAME,
  WORKSPACE_EDIT_TOOL_NAME,
  WORKSPACE_WRITE_TOOL_NAME,
} from '../../src/tools/WorkspaceToolAdapter/toolNames.js'
import { runWithCwdOverride } from '../../src/utils/cwd.js'
import {
  DOCUMENT_EXTENSIONS,
  fileState,
  makeContext,
  notebookContent,
  parentMessage,
  withTempRoot,
  workspaceTool,
} from './documentMutationGuardTestHelpers.js'

const rawMutationRejection = {
  result: false,
  message: DOCUMENT_DERIVATIVE_MUTATION_MESSAGE,
  errorCode: 20,
} as const

export async function expectDirectFileWriteHelperRejected(): Promise<void> {
  const context = makeContext()
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      for (const extension of DOCUMENT_EXTENSIONS) {
        const filePath = join(root, `direct-write.${extension}`)
        await expect(
          callFileWriteTool(
            { file_path: filePath, content: 'raw document bytes' },
            context,
            parentMessage(),
          ),
        ).rejects.toThrow(DOCUMENT_DERIVATIVE_MUTATION_MESSAGE)
        expect(await Bun.file(filePath).exists()).toBe(false)
      }
    }),
  )
}

export async function expectDirectFileEditHelperRejected(): Promise<void> {
  const context = makeContext()
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      for (const extension of DOCUMENT_EXTENSIONS) {
        const filePath = join(root, `direct-edit.${extension}`)
        await Bun.write(filePath, 'old')
        context.readFileState.set(filePath, fileState('old'))
        await expect(
          callFileEditTool(
            { file_path: filePath, old_string: 'old', new_string: 'new' },
            context,
            parentMessage(),
          ),
        ).rejects.toThrow(DOCUMENT_DERIVATIVE_MUTATION_MESSAGE)
        expect(await Bun.file(filePath).text()).toBe('old')
      }
    }),
  )
}

export async function expectDirectNotebookEditHelperRejected(): Promise<void> {
  const context = makeContext()
  const originalNotebook = notebookContent('old')
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      for (const extension of DOCUMENT_EXTENSIONS) {
        const filePath = join(root, `direct-notebook.${extension}`)
        await Bun.write(filePath, originalNotebook)
        context.readFileState.set(filePath, fileState(originalNotebook))
        await expect(
          callNotebookEditTool(
            {
              notebook_path: filePath,
              cell_id: 'cell-1',
              new_source: 'new',
              edit_mode: 'replace',
            },
            context,
            parentMessage(),
          ),
        ).rejects.toThrow(DOCUMENT_DERIVATIVE_MUTATION_MESSAGE)
        expect(await Bun.file(filePath).text()).toBe(originalNotebook)
      }
    }),
  )
}

export async function expectRawDocumentMutationValidationBlocked(): Promise<void> {
  const context = makeContext()
  await withTempRoot(async root =>
    runWithCwdOverride(root, async () => {
      const hwpxPath = join(root, 'form.hwpx')
      const docxPath = join(root, 'form.docx')
      const pdfPath = join(root, 'form.pdf')
      const xlsxPath = join(root, 'form.xlsx')
      const pptxPath = join(root, 'form.pptx')
      await expect(
        FileWriteTool.validateInput({ file_path: hwpxPath, content: 'raw' }, context),
      ).resolves.toEqual(rawMutationRejection)
      await expect(
        FileEditTool.validateInput(
          { file_path: docxPath, old_string: 'old', new_string: 'new' },
          context,
        ),
      ).resolves.toEqual(rawMutationRejection)
      await expect(
        NotebookEditTool.validateInput(
          { notebook_path: pdfPath, new_source: 'raw', edit_mode: 'replace' },
          context,
        ),
      ).resolves.toEqual(rawMutationRejection)
      await expect(
        (await workspaceTool(WORKSPACE_WRITE_TOOL_NAME)).validateInput?.(
          { file_path: xlsxPath, content: 'raw' },
          context,
        ),
      ).resolves.toEqual({
        result: false,
        message:
          'Document formats must be edited through the document primitive, not workspace_write.',
        errorCode: 1,
      })
      await expect(
        (await workspaceTool(WORKSPACE_EDIT_TOOL_NAME)).validateInput?.(
          { file_path: pptxPath, old_string: 'old', new_string: 'new' },
          context,
        ),
      ).resolves.toEqual({
        result: false,
        message:
          'Document formats must be edited through the document primitive, not workspace_edit.',
        errorCode: 1,
      })
      await expect(
        (await workspaceTool(WORKSPACE_BASH_TOOL_NAME)).validateInput?.(
          { command: `python3 mutate.py ${hwpxPath}` },
          context,
        ),
      ).resolves.toEqual({
        result: false,
        message:
          'Document formats must be edited through the document primitive, not workspace_bash.',
        errorCode: 1,
      })
    }),
  )
}
