import { extname, isAbsolute, resolve } from 'path'
import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import { getCwd } from '../../utils/cwd.js'
import { isENOENT } from '../../utils/errors.js'
import { getFileModificationTime } from '../../utils/file.js'
import { readFileSyncWithMetadata } from '../../utils/fileRead.js'
import { safeParseJSON } from '../../utils/json.js'
import { documentDerivativeMutationValidationForResolvedTarget } from '../DocumentPrimitive/documentMutationGuard.js'
import { isNotebookDocument } from './notebookModel.js'

export type NotebookEditInput = {
  notebook_path: string
  cell_id?: string
  new_source: string
  cell_type?: 'code' | 'markdown'
  edit_mode?: 'replace' | 'insert' | 'delete'
}

export async function validateNotebookEditInput(
  { notebook_path, cell_type, cell_id, edit_mode = 'replace' }: NotebookEditInput,
  toolUseContext: ToolUseContext,
): Promise<ValidationResult> {
  const fullPath = isAbsolute(notebook_path)
    ? notebook_path
    : resolve(getCwd(), notebook_path)
  const documentValidation =
    documentDerivativeMutationValidationForResolvedTarget(fullPath)
  if (documentValidation !== null) return documentValidation

  if (fullPath.startsWith('\\\\') || fullPath.startsWith('//')) {
    return { result: true }
  }

  if (extname(fullPath) !== '.ipynb') {
    return {
      result: false,
      message:
        'File must be a Jupyter notebook (.ipynb file). For editing other file types, use the FileEdit tool.',
      errorCode: 2,
    }
  }

  if (
    edit_mode !== 'replace' &&
    edit_mode !== 'insert' &&
    edit_mode !== 'delete'
  ) {
    return {
      result: false,
      message: 'Edit mode must be replace, insert, or delete.',
      errorCode: 4,
    }
  }

  if (edit_mode === 'insert' && !cell_type) {
    return {
      result: false,
      message: 'Cell type is required when using edit_mode=insert.',
      errorCode: 5,
    }
  }

  const readTimestamp = toolUseContext.readFileState.get(fullPath)
  if (!readTimestamp) {
    return {
      result: false,
      message: 'File has not been read yet. Read it first before writing to it.',
      errorCode: 9,
    }
  }
  if (getFileModificationTime(fullPath) > readTimestamp.timestamp) {
    return {
      result: false,
      message:
        'File has been modified since read, either by the user or by a linter. Read it again before attempting to write it.',
      errorCode: 10,
    }
  }

  let content: string
  try {
    content = readFileSyncWithMetadata(fullPath).content
  } catch (e) {
    if (isENOENT(e)) {
      return {
        result: false,
        message: 'Notebook file does not exist.',
        errorCode: 1,
      }
    }
    throw e
  }

  const notebook = safeParseJSON(content)
  if (!isNotebookDocument(notebook)) {
    return {
      result: false,
      message: 'Notebook is not valid JSON.',
      errorCode: 6,
    }
  }

  if (!cell_id) {
    if (edit_mode !== 'insert') {
      return {
        result: false,
        message: 'Cell ID must be specified when not inserting a new cell.',
        errorCode: 7,
      }
    }
  } else {
    const cellIndex = notebook.cells.findIndex(cell => cell.id === cell_id)

    if (cellIndex === -1) {
      const parsedCellIndex = parseNotebookCellId(cell_id)
      if (parsedCellIndex !== undefined) {
        if (!notebook.cells[parsedCellIndex]) {
          return {
            result: false,
            message: `Cell with index ${parsedCellIndex} does not exist in notebook.`,
            errorCode: 7,
          }
        }
      } else {
        return {
          result: false,
          message: `Cell with ID "${cell_id}" not found in notebook.`,
          errorCode: 8,
        }
      }
    }
  }

  return { result: true }
}

function parseNotebookCellId(cellId: string): number | undefined {
  const match = cellId.match(/^cell-(\d+)$/u)
  const indexValue = match?.[1]
  if (indexValue === undefined) return undefined
  return Number.parseInt(indexValue, 10)
}
