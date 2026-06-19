export type NotebookCellRecord = {
  cell_type: 'code' | 'markdown'
  id?: string
  source: string | string[]
  metadata: Record<string, unknown>
  execution_count?: number | null
  outputs?: unknown[]
}

export type NotebookDocument = {
  cells: NotebookCellRecord[]
  metadata: {
    language_info?: {
      name?: string
    }
  }
  nbformat: number
  nbformat_minor: number
}

export function isNotebookDocument(value: unknown): value is NotebookDocument {
  if (!isRecord(value)) return false

  const cells = value.cells
  const metadata = value.metadata
  return (
    Array.isArray(cells) &&
    cells.every(isNotebookCellRecord) &&
    isRecord(metadata) &&
    typeof value.nbformat === 'number' &&
    typeof value.nbformat_minor === 'number'
  )
}

function isNotebookCellRecord(value: unknown): value is NotebookCellRecord {
  if (!isRecord(value)) return false

  const cellType = value.cell_type
  const source = value.source
  return (
    (cellType === 'code' || cellType === 'markdown') &&
    (typeof source === 'string' ||
      (Array.isArray(source) &&
        source.every(item => typeof item === 'string'))) &&
    isRecord(value.metadata)
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
