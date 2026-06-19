import { isAbsolute, resolve } from 'path'
import type { ToolResult, ToolUseContext } from '../../Tool.js'
import type { AssistantMessage } from '../../types/message.js'
import { getCwd } from '../../utils/cwd.js'
import { getFileModificationTime, writeTextContent } from '../../utils/file.js'
import { readFileSyncWithMetadata } from '../../utils/fileRead.js'
import { jsonParse, jsonStringify } from '../../utils/slowOperations.js'
import { documentDerivativeMutationValidationForResolvedTarget } from '../DocumentPrimitive/documentMutationGuard.js'
import { isNotebookDocument, type NotebookCellRecord } from './notebookModel.js'
import type { NotebookEditInput } from './validateInput.js'

export type NotebookEditOutput = {
  new_source: string
  cell_id?: string
  cell_type: 'code' | 'markdown'
  language: string
  edit_mode: string
  error?: string
  notebook_path: string
  original_file: string
  updated_file: string
}

export async function callNotebookEditTool(
  {
    notebook_path,
    new_source,
    cell_id,
    cell_type,
    edit_mode: originalEditMode,
  }: NotebookEditInput,
  { readFileState, updateFileHistoryState }: ToolUseContext,
  parentMessage: AssistantMessage,
): Promise<ToolResult<NotebookEditOutput>> {
  const fullPath = isAbsolute(notebook_path)
    ? notebook_path
    : resolve(getCwd(), notebook_path)
  const documentValidation =
    documentDerivativeMutationValidationForResolvedTarget(fullPath)
  if (documentValidation !== null) throw new Error(documentValidation.message)

  const { fileHistoryEnabled, fileHistoryTrackEdit } = await import(
    '../../utils/fileHistory.js'
  )
  if (fileHistoryEnabled()) {
    await fileHistoryTrackEdit(
      updateFileHistoryState,
      fullPath,
      parentMessage.uuid,
    )
  }

  try {
    const { content, encoding, lineEndings } =
      readFileSyncWithMetadata(fullPath)
    const parsed: unknown = jsonParse(content)
    if (!isNotebookDocument(parsed)) {
      return invalidNotebookResult(new_source, cell_type, cell_id, fullPath)
    }

    const notebook = parsed
    let cellIndex = resolveCellIndex(
      notebook.cells,
      cell_id,
      originalEditMode,
    )

    let editMode = originalEditMode
    if (editMode === 'replace' && cellIndex === notebook.cells.length) {
      editMode = 'insert'
      if (!cell_type) {
        cell_type = 'code'
      }
    }

    const language = notebook.metadata.language_info?.name ?? 'python'
    const newCellId = resolveNewCellId(
      notebook.nbformat,
      notebook.nbformat_minor,
      editMode,
      cell_id,
    )

    if (editMode === 'delete') {
      notebook.cells.splice(cellIndex, 1)
    } else if (editMode === 'insert') {
      notebook.cells.splice(
        cellIndex,
        0,
        createNotebookCell(cell_type, newCellId, new_source),
      )
    } else {
      const targetCell = notebook.cells[cellIndex]
      if (targetCell === undefined) {
        throw new Error('Notebook cell index is out of bounds')
      }
      targetCell.source = new_source
      if (targetCell.cell_type === 'code') {
        targetCell.execution_count = null
        targetCell.outputs = []
      }
      if (cell_type && cell_type !== targetCell.cell_type) {
        targetCell.cell_type = cell_type
      }
    }

    const updatedContent = jsonStringify(notebook, null, 1)
    writeTextContent(fullPath, updatedContent, encoding, lineEndings)
    readFileState.set(fullPath, {
      content: updatedContent,
      timestamp: getFileModificationTime(fullPath),
      offset: undefined,
      limit: undefined,
    })

    return {
      data: {
        new_source,
        cell_type: cell_type ?? 'code',
        language,
        edit_mode: editMode ?? 'replace',
        cell_id: newCellId,
        error: '',
        notebook_path: fullPath,
        original_file: content,
        updated_file: updatedContent,
      },
    }
  } catch (error) {
    if (error instanceof Error) {
      return {
        data: buildErrorOutput(
          new_source,
          cell_type,
          cell_id,
          fullPath,
          error.message,
        ),
      }
    }
    return {
      data: buildErrorOutput(
        new_source,
        cell_type,
        cell_id,
        fullPath,
        'Unknown error occurred while editing notebook',
      ),
    }
  }
}

function resolveCellIndex(
  cells: NotebookCellRecord[],
  cellId: string | undefined,
  originalEditMode: 'replace' | 'insert' | 'delete' | undefined,
): number {
  if (!cellId) {
    return 0
  }

  let cellIndex = cells.findIndex(cell => cell.id === cellId)
  if (cellIndex === -1) {
    const parsedCellIndex = parseNotebookCellId(cellId)
    if (parsedCellIndex !== undefined) {
      cellIndex = parsedCellIndex
    }
  }

  return originalEditMode === 'insert' ? cellIndex + 1 : cellIndex
}

function parseNotebookCellId(cellId: string): number | undefined {
  const match = cellId.match(/^cell-(\d+)$/u)
  const indexValue = match?.[1]
  if (indexValue === undefined) return undefined
  return Number.parseInt(indexValue, 10)
}

function resolveNewCellId(
  nbformat: number,
  nbformatMinor: number,
  editMode: 'replace' | 'insert' | 'delete' | undefined,
  cellId: string | undefined,
): string | undefined {
  if (nbformat <= 4 && (nbformat !== 4 || nbformatMinor < 5)) {
    return undefined
  }
  if (editMode === 'insert') {
    return Math.random().toString(36).substring(2, 15)
  }
  return cellId
}

function createNotebookCell(
  cellType: 'code' | 'markdown' | undefined,
  newCellId: string | undefined,
  newSource: string,
): NotebookCellRecord {
  if (cellType === 'markdown') {
    return {
      cell_type: 'markdown',
      id: newCellId,
      source: newSource,
      metadata: {},
    }
  }

  return {
    cell_type: 'code',
    id: newCellId,
    source: newSource,
    metadata: {},
    execution_count: null,
    outputs: [],
  }
}

function invalidNotebookResult(
  newSource: string,
  cellType: 'code' | 'markdown' | undefined,
  cellId: string | undefined,
  notebookPath: string,
): ToolResult<NotebookEditOutput> {
  return {
    data: buildErrorOutput(
      newSource,
      cellType,
      cellId,
      notebookPath,
      'Notebook is not valid JSON.',
    ),
  }
}

function buildErrorOutput(
  newSource: string,
  cellType: 'code' | 'markdown' | undefined,
  cellId: string | undefined,
  notebookPath: string,
  error: string,
): NotebookEditOutput {
  return {
    new_source: newSource,
    cell_type: cellType ?? 'code',
    language: 'python',
    edit_mode: 'replace',
    error,
    cell_id: cellId,
    notebook_path: notebookPath,
    original_file: '',
    updated_file: '',
  }
}
